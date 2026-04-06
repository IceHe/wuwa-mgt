package app

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"slices"
	"strconv"
	"strings"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"
)

var (
	allowedFlagKeys = map[string]string{
		"daily_task":                   "daily",
		"daily_nest":                   "daily",
		"weekly_door":                  "weekly",
		"weekly_boss":                  "weekly",
		"weekly_synthesis":             "weekly",
		"version_matrix_soldier":       "fv",
		"version_small_coral_exchange": "fv",
		"version_hologram_challenge":   "fv",
		"version_echo_template_adjust": "fv",
		"hv_trial_character":           "hv",
		"monthly_tower_exchange":       "monthly",
		"four_week_tower":              "four_week",
		"four_week_ruins":              "four_week",
		"range_lahailuo_cube":          "range",
		"range_music_game":             "range",
	}
	allowedTacetValues = map[string]struct{}{
		"": {}, "爱弥斯": {}, "西格莉卡": {}, "旧暗": {}, "旧雷": {}, "达妮娅": {},
	}
	doneStatuses = map[string]struct{}{"done": {}, "skipped": {}}
)

type App struct {
	cfg        Config
	db         *sql.DB
	httpClient *http.Client
	server     *http.Server
}

func New(cfg Config) (*App, error) {
	db, err := sql.Open("pgx", cfg.DatabaseURL)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(10)
	db.SetMaxIdleConns(10)
	db.SetConnMaxLifetime(30 * time.Minute)

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := db.PingContext(ctx); err != nil {
		return nil, err
	}

	app := &App{
		cfg: cfg,
		db:  db,
		httpClient: &http.Client{
			Timeout: time.Duration(cfg.AuthValidateTimeoutSeconds * float64(time.Second)),
		},
	}
	if err := app.runMigrations(ctx); err != nil {
		return nil, err
	}
	return app, nil
}

func (a *App) Close() error {
	if a.db != nil {
		return a.db.Close()
	}
	return nil
}

func (a *App) Run(port int) error {
	mux := http.NewServeMux()
	a.registerRoutes(mux)

	a.server = &http.Server{
		Addr:    fmt.Sprintf("%s:%d", a.cfg.Host, port),
		Handler: a.apiPrefixHandler(a.authMiddleware(mux)),
	}
	return a.server.ListenAndServe()
}

func (a *App) registerRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/healthz", a.handleHealthz)
	mux.HandleFunc("/auth/ping", a.handleAuthPing)

	mux.HandleFunc("/accounts", a.dispatchAccountsCollection)
	mux.HandleFunc("/accounts/", a.dispatchAccountsRoutes)

	mux.HandleFunc("/cleanup-timer/weekly-summary", a.dispatchMethod(http.MethodGet, a.handleCleanupWeeklySummary))
	mux.HandleFunc("/cleanup-timer/sessions", a.dispatchCleanupSessionsCollection)
	mux.HandleFunc("/cleanup-timer/sessions/", a.dispatchCleanupSessionsRoutes)

	mux.HandleFunc("/dashboard/accounts", a.dispatchMethod(http.MethodGet, a.handleDashboardAccounts))
	mux.HandleFunc("/periodic/accounts", a.dispatchMethod(http.MethodGet, a.handlePeriodicAccounts))

	mux.HandleFunc("/task-templates", a.dispatchTaskTemplatesCollection)
	mux.HandleFunc("/task-templates/", a.dispatchTaskTemplatesRoutes)
	mux.HandleFunc("/task-instances", a.dispatchTaskInstancesCollection)
	mux.HandleFunc("/task-instances/", a.dispatchTaskInstancesRoutes)
}

func (a *App) dispatchMethod(method string, next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != method {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		next(w, r)
	}
}

func (a *App) dispatchAccountsCollection(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		a.handleListAccounts(w, r)
	case http.MethodPost:
		a.handleCreateAccount(w, r)
	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
}

func (a *App) dispatchAccountsRoutes(w http.ResponseWriter, r *http.Request) {
	path := strings.TrimPrefix(r.URL.Path, "/accounts/")
	parts := strings.Split(strings.Trim(path, "/"), "/")
	if len(parts) == 0 || parts[0] == "" {
		http.NotFound(w, r)
		return
	}

	if parts[0] == "by-id" {
		if len(parts) < 2 || parts[1] == "" {
			http.NotFound(w, r)
			return
		}
		r.SetPathValue("id", parts[1])
		switch {
		case len(parts) == 2 && r.Method == http.MethodGet:
			a.handleGetAccountByID(w, r)
		case len(parts) == 3 && parts[2] == "update" && r.Method == http.MethodPost:
			a.handleUpdateAccountByID(w, r)
		case len(parts) == 3 && parts[2] == "delete" && r.Method == http.MethodPost:
			a.handleDeleteAccountByID(w, r)
		case len(parts) == 3 && parts[2] == "checkins" && r.Method == http.MethodPost:
			a.handleSetCheckinByID(w, r)
		case len(parts) == 3 && parts[2] == "tacet" && r.Method == http.MethodPost:
			a.handleSetTacetByID(w, r)
		case len(parts) == 4 && parts[2] == "cleanup-timer" && parts[3] == "start" && r.Method == http.MethodPost:
			a.handleStartCleanupTimerByID(w, r)
		case len(parts) == 4 && parts[2] == "cleanup-timer" && parts[3] == "pause" && r.Method == http.MethodPost:
			a.handlePauseCleanupTimerByID(w, r)
		case len(parts) == 4 && parts[2] == "cleanup-timer" && parts[3] == "today" && r.Method == http.MethodGet:
			a.handleGetCleanupTimerTodayByID(w, r)
		case len(parts) == 3 && parts[2] == "energy" && r.Method == http.MethodGet:
			a.handleGetEnergyByID(w, r)
		case len(parts) == 4 && parts[2] == "energy" && parts[3] == "set" && r.Method == http.MethodPost:
			a.handleSetEnergyByID(w, r)
		case len(parts) == 4 && parts[2] == "energy" && parts[3] == "spend" && r.Method == http.MethodPost:
			a.handleSpendEnergyByID(w, r)
		case len(parts) == 4 && parts[2] == "energy" && parts[3] == "gain" && r.Method == http.MethodPost:
			a.handleGainEnergyByID(w, r)
		default:
			http.NotFound(w, r)
		}
		return
	}

	r.SetPathValue("account_id", parts[0])
	switch {
	case len(parts) == 1 && r.Method == http.MethodPatch:
		a.handleUpdateAccountByAccountID(w, r)
	case len(parts) == 1 && r.Method == http.MethodDelete:
		a.handleDeleteAccountByAccountID(w, r)
	case len(parts) == 2 && parts[1] == "update" && r.Method == http.MethodPost:
		a.handleUpdateAccountByAccountID(w, r)
	case len(parts) == 2 && parts[1] == "delete" && r.Method == http.MethodPost:
		a.handleDeleteAccountByAccountID(w, r)
	case len(parts) == 2 && parts[1] == "energy" && r.Method == http.MethodGet:
		a.handleGetEnergyByAccountID(w, r)
	case len(parts) == 3 && parts[1] == "energy" && parts[2] == "set" && r.Method == http.MethodPost:
		a.handleSetEnergyByAccountID(w, r)
	case len(parts) == 3 && parts[1] == "energy" && parts[2] == "spend" && r.Method == http.MethodPost:
		a.handleSpendEnergyByAccountID(w, r)
	case len(parts) == 3 && parts[1] == "energy" && parts[2] == "gain" && r.Method == http.MethodPost:
		a.handleGainEnergyByAccountID(w, r)
	default:
		http.NotFound(w, r)
	}
}

func (a *App) dispatchCleanupSessionsCollection(w http.ResponseWriter, r *http.Request) {
	switch {
	case r.Method == http.MethodGet:
		a.handleListCleanupSessions(w, r)
	case r.Method == http.MethodPost:
		a.handleCreateCleanupSessionManual(w, r)
	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
}

func (a *App) dispatchCleanupSessionsRoutes(w http.ResponseWriter, r *http.Request) {
	path := strings.TrimPrefix(r.URL.Path, "/cleanup-timer/sessions/")
	if path == "manual" && r.Method == http.MethodPost {
		a.handleCreateCleanupSessionManual(w, r)
		return
	}
	if r.Method != http.MethodDelete {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	r.SetPathValue("session_id", strings.Trim(path, "/"))
	a.handleDeleteCleanupSession(w, r)
}

func (a *App) dispatchTaskTemplatesCollection(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		a.handleListTaskTemplates(w, r)
	case http.MethodPost:
		a.handleCreateTaskTemplate(w, r)
	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
}

func (a *App) dispatchTaskTemplatesRoutes(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPatch {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	r.SetPathValue("template_id", strings.Trim(strings.TrimPrefix(r.URL.Path, "/task-templates/"), "/"))
	a.handleUpdateTaskTemplate(w, r)
}

func (a *App) dispatchTaskInstancesCollection(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		a.handleListTaskInstances(w, r)
	case http.MethodPost:
		a.handleCreateTaskInstance(w, r)
	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
}

func (a *App) dispatchTaskInstancesRoutes(w http.ResponseWriter, r *http.Request) {
	path := strings.Trim(strings.TrimPrefix(r.URL.Path, "/task-instances/"), "/")
	if path == "generate" && r.Method == http.MethodPost {
		a.handleGenerateTaskInstances(w, r)
		return
	}
	if r.Method != http.MethodPatch {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	r.SetPathValue("instance_id", path)
	a.handleUpdateTaskInstance(w, r)
}

func (a *App) apiPrefixHandler(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api" || strings.HasPrefix(r.URL.Path, "/api/") {
			cloned := r.Clone(r.Context())
			cloned.URL = cloneURL(r.URL)
			stripped := strings.TrimPrefix(r.URL.Path, "/api")
			if stripped == "" {
				stripped = "/"
			}
			cloned.URL.Path = stripped
			cloned.URL.RawPath = stripped
			next.ServeHTTP(w, cloned)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func cloneURL(in *url.URL) *url.URL {
	if in == nil {
		return &url.URL{}
	}
	cloned := *in
	return &cloned
}

func (a *App) authMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodOptions || r.URL.Path == "/healthz" {
			next.ServeHTTP(w, r)
			return
		}
		token := extractTokenFromHeaders(r)
		if token == "" {
			writeError(w, http.StatusUnauthorized, "missing token")
			return
		}
		valid, reason := a.validateTokenByAuthService(r.Context(), token)
		if !valid {
			statusCode := http.StatusUnauthorized
			if reason == "forbidden" || reason == "invalid permission" {
				statusCode = http.StatusForbidden
			}
			writeError(w, statusCode, reason)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func extractTokenFromHeaders(r *http.Request) string {
	auth := strings.TrimSpace(r.Header.Get("Authorization"))
	if auth != "" && strings.HasPrefix(strings.ToLower(auth), "bearer ") {
		token := strings.TrimSpace(auth[7:])
		if token != "" {
			return token
		}
	}
	return strings.TrimSpace(r.Header.Get("X-Token"))
}

func (a *App) validateTokenByAuthService(ctx context.Context, token string) (bool, string) {
	payload := map[string]string{
		"token":      token,
		"permission": a.cfg.AuthRequiredPermission,
	}
	body, _ := json.Marshal(payload)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, a.cfg.AuthBaseURL+"/api/validate", strings.NewReader(string(body)))
	if err != nil {
		return false, "auth service unavailable"
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := a.httpClient.Do(req)
	if err != nil {
		return false, "auth service unavailable"
	}
	defer resp.Body.Close()
	var data struct {
		Valid  bool   `json:"valid"`
		Reason string `json:"reason"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		return false, "invalid auth response"
	}
	if data.Valid {
		return true, ""
	}
	reason := strings.TrimSpace(data.Reason)
	if reason == "" {
		reason = "forbidden"
	}
	return false, reason
}

func (a *App) runMigrations(ctx context.Context) error {
	stmts := []string{
		`DO $$
		BEGIN
			IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='account_daily_flags')
			AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='account_checkins') THEN
				ALTER TABLE account_daily_flags RENAME TO account_checkins;
			END IF;
		END $$;`,
		`CREATE TABLE IF NOT EXISTS accounts (
			account_id SERIAL PRIMARY KEY,
			id VARCHAR(64),
			abbr VARCHAR(32),
			nickname VARCHAR(128) NOT NULL DEFAULT '',
			phone_number VARCHAR(32),
			remark TEXT,
			tacet VARCHAR(32) NOT NULL DEFAULT '',
			full_waveplate_at TIMESTAMPTZ NOT NULL DEFAULT now(),
			full_waveplate_crystal INTEGER NOT NULL DEFAULT 0,
			is_active BOOLEAN NOT NULL DEFAULT TRUE,
			created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
			updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
		)`,
		`DO $$
		BEGIN
			IF EXISTS (
				SELECT 1 FROM information_schema.columns
				WHERE table_name='accounts' AND column_name='id' AND data_type IN ('bigint', 'integer')
			) AND NOT EXISTS (
				SELECT 1 FROM information_schema.columns
				WHERE table_name='accounts' AND column_name='account_id'
			) THEN
				ALTER TABLE accounts RENAME COLUMN id TO account_id;
			END IF;
		END $$;`,
		`DO $$ BEGIN
			IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='accounts' AND column_name='account_identifier')
			AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='accounts' AND column_name='id') THEN
				ALTER TABLE accounts RENAME COLUMN account_identifier TO id;
			END IF;
		END $$;`,
		`DO $$ BEGIN
			IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='accounts' AND column_name='feature_id')
			AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='accounts' AND column_name='id') THEN
				ALTER TABLE accounts RENAME COLUMN feature_id TO id;
			END IF;
		END $$;`,
		`DO $$ BEGIN
			IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='accounts' AND column_name='account_code')
			AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='accounts' AND column_name='abbr') THEN
				ALTER TABLE accounts RENAME COLUMN account_code TO abbr;
			END IF;
		END $$;`,
		`DO $$ BEGIN
			IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='accounts' AND column_name='account_name')
			AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='accounts' AND column_name='nickname') THEN
				ALTER TABLE accounts RENAME COLUMN account_name TO nickname;
			END IF;
		END $$;`,
		`DO $$ BEGIN
			IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='accounts' AND column_name='phone')
			AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='accounts' AND column_name='phone_number') THEN
				ALTER TABLE accounts RENAME COLUMN phone TO phone_number;
			END IF;
		END $$;`,
		`DO $$ BEGIN
			IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='accounts' AND column_name='note')
			AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='accounts' AND column_name='remark') THEN
				ALTER TABLE accounts RENAME COLUMN note TO remark;
			END IF;
		END $$;`,
		`ALTER TABLE accounts ADD COLUMN IF NOT EXISTS full_waveplate_at TIMESTAMPTZ`,
		`ALTER TABLE accounts ADD COLUMN IF NOT EXISTS full_waveplate_crystal INTEGER DEFAULT 0`,
		`ALTER TABLE accounts ADD COLUMN IF NOT EXISTS tacet VARCHAR(32) DEFAULT ''`,
		`ALTER TABLE accounts ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE`,
		`ALTER TABLE accounts ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now()`,
		`ALTER TABLE accounts ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now()`,
		`ALTER TABLE accounts ADD COLUMN IF NOT EXISTS last_waveplate INTEGER DEFAULT 0`,
		`ALTER TABLE accounts ADD COLUMN IF NOT EXISTS last_waveplate_updated_at TIMESTAMPTZ DEFAULT now()`,
		`ALTER TABLE accounts ADD COLUMN IF NOT EXISTS waveplate_crystal INTEGER DEFAULT 0`,
		`UPDATE accounts SET
			last_waveplate = COALESCE(last_waveplate, 0),
			waveplate_crystal = COALESCE(waveplate_crystal, 0),
			last_waveplate_updated_at = COALESCE(last_waveplate_updated_at, now()),
			full_waveplate_at = COALESCE(full_waveplate_at, COALESCE(last_waveplate_updated_at, now()) + (GREATEST(0, 240 - LEAST(GREATEST(COALESCE(last_waveplate, 0), 0), 240)) * INTERVAL '6 minutes')),
			full_waveplate_crystal = COALESCE(full_waveplate_crystal, COALESCE(waveplate_crystal, 0)),
			tacet = CASE WHEN tacet IS NULL OR tacet IN ('未选定', '?') THEN '' ELSE tacet END,
			is_active = COALESCE(is_active, TRUE),
			created_at = COALESCE(created_at, now()),
			updated_at = COALESCE(updated_at, now())`,
		`CREATE UNIQUE INDEX IF NOT EXISTS ix_accounts_id ON accounts (id)`,
		`CREATE UNIQUE INDEX IF NOT EXISTS ix_accounts_abbr ON accounts (abbr)`,
		`CREATE TABLE IF NOT EXISTS account_checkins (
			id SERIAL PRIMARY KEY,
			account_id INTEGER NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
			status_date DATE NOT NULL,
			period_type VARCHAR(16) NOT NULL DEFAULT 'daily',
			period_key VARCHAR(32) NOT NULL DEFAULT '',
			flag_key VARCHAR(64) NOT NULL,
			status VARCHAR(16) NOT NULL DEFAULT 'todo',
			is_done BOOLEAN NOT NULL DEFAULT FALSE,
			updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
		)`,
		`ALTER TABLE account_checkins ADD COLUMN IF NOT EXISTS period_type VARCHAR(16) DEFAULT 'daily'`,
		`ALTER TABLE account_checkins ADD COLUMN IF NOT EXISTS period_key VARCHAR(32) DEFAULT ''`,
		`ALTER TABLE account_checkins ADD COLUMN IF NOT EXISTS status VARCHAR(16) DEFAULT 'todo'`,
		`ALTER TABLE account_checkins ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now()`,
		`UPDATE account_checkins SET
			period_type = COALESCE(NULLIF(period_type, ''), 'daily'),
			period_key = COALESCE(NULLIF(period_key, ''), status_date::text),
			status = CASE
				WHEN status IN ('done', 'skipped') THEN status
				WHEN is_done THEN 'done'
				ELSE 'todo'
			END,
			is_done = CASE
				WHEN status IN ('done', 'skipped') THEN TRUE
				WHEN status = 'todo' THEN FALSE
				ELSE is_done
			END,
			flag_key = CASE
				WHEN flag_key = 'daily_done' THEN 'daily_task'
				WHEN flag_key = 'nest_cleared' THEN 'daily_nest'
				WHEN flag_key = 'door' THEN 'weekly_door'
				ELSE flag_key
			END`,
		`CREATE INDEX IF NOT EXISTS ix_account_checkins_period_type ON account_checkins (period_type)`,
		`CREATE INDEX IF NOT EXISTS ix_account_checkins_period_key ON account_checkins (period_key)`,
		`CREATE INDEX IF NOT EXISTS ix_account_checkins_status ON account_checkins (status)`,
		`CREATE INDEX IF NOT EXISTS ix_account_checkins_account_period ON account_checkins (account_id, period_type, period_key)`,
		`CREATE UNIQUE INDEX IF NOT EXISTS uq_account_checkin_compound ON account_checkins (account_id, period_type, period_key, flag_key)`,
		`CREATE TABLE IF NOT EXISTS account_cleanup_sessions (
			id SERIAL PRIMARY KEY,
			account_id INTEGER NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
			biz_date DATE NOT NULL,
			started_at TIMESTAMPTZ NOT NULL,
			ended_at TIMESTAMPTZ NULL,
			duration_sec INTEGER NOT NULL DEFAULT 0,
			status VARCHAR(16) NOT NULL DEFAULT 'running',
			created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
			updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
		)`,
		`ALTER TABLE account_cleanup_sessions ADD COLUMN IF NOT EXISTS biz_date DATE`,
		`ALTER TABLE account_cleanup_sessions ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ`,
		`ALTER TABLE account_cleanup_sessions ADD COLUMN IF NOT EXISTS ended_at TIMESTAMPTZ`,
		`ALTER TABLE account_cleanup_sessions ADD COLUMN IF NOT EXISTS duration_sec INTEGER DEFAULT 0`,
		`ALTER TABLE account_cleanup_sessions ADD COLUMN IF NOT EXISTS status VARCHAR(16) DEFAULT 'running'`,
		`ALTER TABLE account_cleanup_sessions ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now()`,
		`ALTER TABLE account_cleanup_sessions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now()`,
		`UPDATE account_cleanup_sessions SET
			status = CASE WHEN ended_at IS NULL THEN 'running' ELSE 'paused' END
			WHERE status IS NULL OR status NOT IN ('running', 'paused')`,
		`UPDATE account_cleanup_sessions SET
			duration_sec = CASE
				WHEN ended_at IS NOT NULL THEN GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (ended_at - started_at)))::INT)
				ELSE COALESCE(duration_sec, 0)
			END
			WHERE duration_sec IS NULL OR duration_sec < 0`,
		`UPDATE account_cleanup_sessions SET
			biz_date = COALESCE(biz_date, (started_at AT TIME ZONE 'Asia/Shanghai')::DATE, CURRENT_DATE)`,
		`CREATE INDEX IF NOT EXISTS ix_account_cleanup_sessions_account_id ON account_cleanup_sessions (account_id)`,
		`CREATE INDEX IF NOT EXISTS ix_account_cleanup_sessions_biz_date ON account_cleanup_sessions (biz_date)`,
		`CREATE INDEX IF NOT EXISTS ix_account_cleanup_sessions_status ON account_cleanup_sessions (status)`,
		`CREATE INDEX IF NOT EXISTS ix_account_cleanup_sessions_started_at ON account_cleanup_sessions (started_at)`,
		`CREATE INDEX IF NOT EXISTS ix_account_cleanup_sessions_ended_at ON account_cleanup_sessions (ended_at)`,
		`CREATE TABLE IF NOT EXISTS task_templates (
			id SERIAL PRIMARY KEY,
			name VARCHAR(128) NOT NULL,
			task_type VARCHAR(32) NOT NULL,
			default_priority INTEGER NOT NULL DEFAULT 3,
			description TEXT NULL,
			is_active BOOLEAN NOT NULL DEFAULT TRUE,
			created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
			updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
		)`,
		`CREATE TABLE IF NOT EXISTS task_instances (
			id SERIAL PRIMARY KEY,
			account_id INTEGER NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
			template_id INTEGER NOT NULL REFERENCES task_templates(id) ON DELETE CASCADE,
			period_key VARCHAR(64) NOT NULL,
			status VARCHAR(16) NOT NULL DEFAULT 'todo',
			start_at TIMESTAMPTZ NOT NULL,
			deadline_at TIMESTAMPTZ NULL,
			priority INTEGER NOT NULL DEFAULT 3,
			note TEXT NULL,
			completed_at TIMESTAMPTZ NULL,
			created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
			updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
		)`,
		`CREATE UNIQUE INDEX IF NOT EXISTS uq_task_instance_period ON task_instances (account_id, template_id, period_key)`,
		`CREATE INDEX IF NOT EXISTS ix_task_instances_account_id ON task_instances (account_id)`,
		`CREATE INDEX IF NOT EXISTS ix_task_instances_period_key ON task_instances (period_key)`,
	}
	for _, stmt := range stmts {
		if _, err := a.db.ExecContext(ctx, stmt); err != nil {
			return fmt.Errorf("migration failed: %w", err)
		}
	}
	return nil
}

func (a *App) now() time.Time {
	return time.Now().In(a.cfg.Location)
}

func (a *App) today() time.Time {
	return time.Date(a.now().Year(), a.now().Month(), a.now().Day(), 0, 0, 0, 0, a.cfg.Location)
}

func (a *App) resetDay(now time.Time) time.Time {
	current := now.In(a.cfg.Location)
	day := time.Date(current.Year(), current.Month(), current.Day(), 0, 0, 0, 0, a.cfg.Location)
	if current.Hour() < a.cfg.ResetHour {
		return day.AddDate(0, 0, -1)
	}
	return day
}

func (a *App) toAppTZ(t time.Time) time.Time {
	if t.IsZero() {
		return t
	}
	return t.In(a.cfg.Location)
}

func mondayOfWeek(day time.Time) time.Time {
	weekday := int(day.Weekday())
	if weekday == 0 {
		weekday = 7
	}
	return day.AddDate(0, 0, -(weekday - 1))
}

func weeklyPeriodKey(day time.Time) string {
	return mondayOfWeek(day).Format("2006-01-02") + "W"
}

func fourWeekWindow(anchor, day time.Time) (time.Time, time.Time) {
	deltaDays := int(day.Sub(anchor).Hours() / 24)
	windowIndex := deltaDays / fourWeekDays
	start := anchor.AddDate(0, 0, windowIndex*fourWeekDays)
	end := start.AddDate(0, 0, fourWeekDays-1)
	return start, end
}

func rangePeriodKey(start, end time.Time) string {
	return start.Format("2006-01-02") + "_" + end.Format("2006-01-02")
}

func (a *App) resolvePeriod(flagKey string, day time.Time) (string, string, time.Time, error) {
	periodType, ok := allowedFlagKeys[flagKey]
	if !ok {
		return "", "", time.Time{}, fmt.Errorf("unsupported flag_key: %s", flagKey)
	}
	switch periodType {
	case "daily":
		return periodType, day.Format("2006-01-02"), day, nil
	case "weekly":
		monday := mondayOfWeek(day)
		return periodType, weeklyPeriodKey(day), monday, nil
	case "monthly":
		start := time.Date(day.Year(), day.Month(), 1, 0, 0, 0, 0, day.Location())
		return periodType, day.Format("2006-01"), start, nil
	case "fv":
		return periodType, "fv-" + a.cfg.CurrentFVStart.Format("2006-01-02"), a.cfg.CurrentFVStart, nil
	case "hv":
		return periodType, "hv-" + a.cfg.CurrentHVStart.Format("2006-01-02"), a.cfg.CurrentHVStart, nil
	case "four_week":
		anchor := a.cfg.FourWeekRuinsAnchor
		if flagKey == "four_week_tower" {
			anchor = a.cfg.FourWeekTowerAnchor
		}
		start, end := fourWeekWindow(anchor, day)
		return periodType, rangePeriodKey(start, end), start, nil
	case "range":
		if flagKey == "range_music_game" {
			return periodType, rangePeriodKey(a.cfg.MusicGameRangeStart, a.cfg.MusicGameRangeEnd), a.cfg.MusicGameRangeStart, nil
		}
		return periodType, rangePeriodKey(a.cfg.LahailuoRangeStart, a.cfg.LahailuoRangeEnd), a.cfg.LahailuoRangeStart, nil
	default:
		return "", "", time.Time{}, fmt.Errorf("unsupported period type for flag: %s", flagKey)
	}
}

func accountPhonePtr(value sql.NullString) *string {
	if !value.Valid {
		return nil
	}
	s := value.String
	return &s
}

func accountRemarkPtr(value sql.NullString) *string {
	if !value.Valid {
		return nil
	}
	s := value.String
	return &s
}

func (a *App) accountPayload(account Account, now time.Time) AccountOut {
	currentWP, currentCrystal := currentResourcesFromFullTime(account.FullWaveplateAt, account.FullWaveplateCrystal, now)
	toFullSeconds := secondsToWaveplateFullFromFullTime(account.FullWaveplateAt, now)
	toFull := (toFullSeconds + 59) / 60
	return AccountOut{
		AccountID:               account.AccountID,
		ID:                      account.ID,
		PhoneNumber:             accountPhonePtr(account.PhoneNumber),
		Nickname:                account.Nickname,
		Abbr:                    account.Abbr,
		Remark:                  accountRemarkPtr(account.Remark),
		Tacet:                   account.Tacet,
		IsActive:                account.IsActive,
		CurrentWaveplate:        currentWP,
		CurrentWaveplateCrystal: currentCrystal,
		FullWaveplateAt:         account.FullWaveplateAt,
		WaveplateFullInMinutes:  toFull,
		CreatedAt:               account.CreatedAt,
		UpdatedAt:               account.UpdatedAt,
	}
}

func (a *App) energyPayload(account Account, now time.Time) EnergyOut {
	currentWP, currentCrystal := currentResourcesFromFullTime(account.FullWaveplateAt, account.FullWaveplateCrystal, now)
	toFullSeconds := secondsToWaveplateFullFromFullTime(account.FullWaveplateAt, now)
	toFull := (toFullSeconds + 59) / 60
	return EnergyOut{
		AccountID:               account.AccountID,
		ID:                      account.ID,
		CurrentWaveplate:        currentWP,
		CurrentWaveplateCrystal: currentCrystal,
		FullWaveplateAt:         account.FullWaveplateAt,
		WaveplateFullInMinutes:  toFull,
		ETAWaveplateFull:        account.FullWaveplateAt,
		WarnLevel:               warnLevel(currentWP),
	}
}

func isDoneStatus(status string) bool {
	_, ok := doneStatuses[strings.TrimSpace(strings.ToLower(status))]
	return ok
}

func validateTacet(value string) error {
	if _, ok := allowedTacetValues[value]; !ok {
		return fmt.Errorf("unsupported tacet: %s", value)
	}
	return nil
}

func validateTaskStatus(status string) bool {
	return slices.Contains([]string{"todo", "done", "skipped"}, status)
}

func validateTaskType(taskType string) bool {
	return slices.Contains([]string{"daily", "weekly", "version", "half_version", "special"}, taskType)
}

func runningDurationSeconds(startedAt, now time.Time) int {
	seconds := int(now.Sub(startedAt).Seconds())
	if seconds < 0 {
		return 0
	}
	return seconds
}

func (a *App) applyEnergySet(account *Account, payload energySetInput, now time.Time) error {
	currentWP, currentCrystal := currentResourcesFromFullTime(account.FullWaveplateAt, account.FullWaveplateCrystal, now)
	if payload.FullWaveplateAt != nil {
		fullAt := a.toAppTZ(*payload.FullWaveplateAt)
		if err := validateFullWaveplateAt(now, fullAt); err != nil {
			return err
		}
		account.FullWaveplateAt = fullAt
		if payload.CurrentWaveplateCrystal == nil {
			return nil
		}
		fullCrystal, err := fullCrystalFromCurrentCrystal(*payload.CurrentWaveplateCrystal, fullAt, now)
		if err != nil {
			return err
		}
		account.FullWaveplateCrystal = fullCrystal
		return nil
	}

	targetWP := 0
	if payload.CurrentWaveplate != nil {
		targetWP = *payload.CurrentWaveplate
	}
	targetCrystal := currentCrystal
	if payload.CurrentWaveplateCrystal != nil {
		targetCrystal = *payload.CurrentWaveplateCrystal
	}
	if payload.CurrentWaveplateCrystal != nil && targetWP == currentWP {
		fullCrystal, err := fullCrystalFromCurrentCrystal(targetCrystal, account.FullWaveplateAt, now)
		if err != nil {
			return err
		}
		account.FullWaveplateCrystal = fullCrystal
		return nil
	}
	fullAt, fullCrystal := fullTimeFromCurrentResources(targetWP, targetCrystal, now)
	account.FullWaveplateAt = fullAt
	account.FullWaveplateCrystal = fullCrystal
	return nil
}

func (a *App) applyQuickEnergyChange(account *Account, currentWP, nextWP, nextCrystal int, now time.Time) error {
	if nextWP < WaveplateCap {
		nextRecoverSeconds := WaveplateRecoverSeconds
		if currentWP < WaveplateCap {
			nextRecoverSeconds = secondsToNextWaveplateRecoverFromFullTime(account.FullWaveplateAt, now)
		}
		account.FullWaveplateAt = fullTimeFromCurrentWaveplateAndNextRecover(nextWP, nextRecoverSeconds, now)
		account.FullWaveplateCrystal = nextCrystal
		return nil
	}
	if currentWP < WaveplateCap {
		account.FullWaveplateAt = now
		account.FullWaveplateCrystal = nextCrystal
		return nil
	}
	fullCrystal, err := fullCrystalFromCurrentCrystal(nextCrystal, account.FullWaveplateAt, now)
	if err != nil {
		return err
	}
	account.FullWaveplateCrystal = fullCrystal
	return nil
}

func decodeJSON(r *http.Request, out any) error {
	defer r.Body.Close()
	data, err := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	if err != nil {
		return err
	}
	if len(strings.TrimSpace(string(data))) == 0 {
		data = []byte("{}")
	}
	return json.Unmarshal(data, out)
}

func writeJSON(w http.ResponseWriter, statusCode int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	_ = json.NewEncoder(w).Encode(payload)
}

func writeError(w http.ResponseWriter, statusCode int, detail string) {
	writeJSON(w, statusCode, map[string]string{"detail": detail})
}

func parseIntParam(value string) (int, error) {
	n, err := strconv.Atoi(strings.TrimSpace(value))
	if err != nil {
		return 0, errors.New("invalid integer")
	}
	return n, nil
}

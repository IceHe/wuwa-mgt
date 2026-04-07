package app

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"net/http"
	"slices"
	"sort"
	"strconv"
	"strings"
	"time"
)

type createAccountInput struct {
	ID                      string     `json:"id"`
	PhoneNumber             *string    `json:"phone_number"`
	Nickname                string     `json:"nickname"`
	Abbr                    string     `json:"abbr"`
	Remark                  *string    `json:"remark"`
	Tacet                   string     `json:"tacet"`
	IsActive                *bool      `json:"is_active"`
	CurrentWaveplate        *int       `json:"current_waveplate"`
	CurrentWaveplateCrystal *int       `json:"current_waveplate_crystal"`
	FullWaveplateAt         *time.Time `json:"full_waveplate_at"`
}

type updateAccountInput struct {
	PhoneNumber             *string    `json:"phone_number"`
	Nickname                *string    `json:"nickname"`
	Abbr                    *string    `json:"abbr"`
	Remark                  *string    `json:"remark"`
	Tacet                   *string    `json:"tacet"`
	IsActive                *bool      `json:"is_active"`
	CurrentWaveplate        *int       `json:"current_waveplate"`
	CurrentWaveplateCrystal *int       `json:"current_waveplate_crystal"`
	FullWaveplateAt         *time.Time `json:"full_waveplate_at"`
}

type energySetInput struct {
	CurrentWaveplate        *int       `json:"current_waveplate"`
	CurrentWaveplateCrystal *int       `json:"current_waveplate_crystal"`
	FullWaveplateAt         *time.Time `json:"full_waveplate_at"`
}

type spendEnergyInput struct {
	Cost int `json:"cost"`
}

type gainEnergyInput struct {
	Amount int `json:"amount"`
}

type checkinInput struct {
	FlagKey string  `json:"flag_key"`
	IsDone  *bool   `json:"is_done"`
	Status  *string `json:"status"`
}

type tacetInput struct {
	Tacet string `json:"tacet"`
}

type cleanupManualInput struct {
	AccountID   int        `json:"account_id"`
	BizDate     *string    `json:"biz_date"`
	DurationSec *int       `json:"duration_sec"`
	StartedAt   *time.Time `json:"started_at"`
	EndedAt     *time.Time `json:"ended_at"`
}

type createTaskTemplateInput struct {
	Name            string  `json:"name"`
	TaskType        string  `json:"task_type"`
	DefaultPriority *int    `json:"default_priority"`
	Description     *string `json:"description"`
	IsActive        *bool   `json:"is_active"`
}

type updateTaskTemplateInput struct {
	Name            *string `json:"name"`
	TaskType        *string `json:"task_type"`
	DefaultPriority *int    `json:"default_priority"`
	Description     *string `json:"description"`
	IsActive        *bool   `json:"is_active"`
}

type createTaskInstanceInput struct {
	AccountID  int        `json:"account_id"`
	TemplateID int        `json:"template_id"`
	PeriodKey  string     `json:"period_key"`
	Status     string     `json:"status"`
	StartAt    time.Time  `json:"start_at"`
	DeadlineAt *time.Time `json:"deadline_at"`
	Priority   *int       `json:"priority"`
	Note       *string    `json:"note"`
}

type updateTaskInstanceInput struct {
	Status     *string    `json:"status"`
	DeadlineAt *time.Time `json:"deadline_at"`
	Priority   *int       `json:"priority"`
	Note       *string    `json:"note"`
}

type generateTaskInstancesInput struct {
	PeriodKey  string     `json:"period_key"`
	StartAt    time.Time  `json:"start_at"`
	DeadlineAt *time.Time `json:"deadline_at"`
	TaskType   *string    `json:"task_type"`
}

func (a *App) withTimeout(r *http.Request) (context.Context, context.CancelFunc) {
	return context.WithTimeout(r.Context(), 10*time.Second)
}

func (a *App) handleHealthz(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (a *App) handleAuthPing(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]bool{"ok": true})
}

func (a *App) handleCreateAccount(w http.ResponseWriter, r *http.Request) {
	var input createAccountInput
	if err := decodeJSON(r, &input); err != nil {
		writeError(w, http.StatusBadRequest, "invalid json")
		return
	}
	if strings.TrimSpace(input.ID) == "" || strings.TrimSpace(input.Abbr) == "" || strings.TrimSpace(input.Nickname) == "" {
		writeError(w, http.StatusBadRequest, "id, abbr and nickname are required")
		return
	}
	if input.CurrentWaveplate == nil && input.FullWaveplateAt == nil {
		writeError(w, http.StatusBadRequest, "current_waveplate or full_waveplate_at is required")
		return
	}
	if err := validateTacet(input.Tacet); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	now := a.now()
	currentCrystal := 0
	if input.CurrentWaveplateCrystal != nil {
		currentCrystal = *input.CurrentWaveplateCrystal
	}
	var fullAt time.Time
	var fullCrystal int
	var err error
	if input.FullWaveplateAt != nil {
		fullAt = a.toAppTZ(*input.FullWaveplateAt)
		if err = validateFullWaveplateAt(now, fullAt); err != nil {
			writeError(w, http.StatusBadRequest, err.Error())
			return
		}
		fullCrystal, err = fullCrystalFromCurrentCrystal(currentCrystal, fullAt, now)
		if err != nil {
			writeError(w, http.StatusBadRequest, err.Error())
			return
		}
	} else {
		fullAt, fullCrystal = fullTimeFromCurrentResources(*input.CurrentWaveplate, currentCrystal, now)
	}

	isActive := true
	if input.IsActive != nil {
		isActive = *input.IsActive
	}

	ctx, cancel := a.withTimeout(r)
	defer cancel()
	query := `INSERT INTO accounts (id, abbr, nickname, phone_number, remark, tacet, is_active, full_waveplate_at, full_waveplate_crystal, created_at, updated_at)
	VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,now(),now())
	RETURNING account_id, id, abbr, nickname, phone_number, remark, tacet, full_waveplate_at, full_waveplate_crystal, is_active, created_at, updated_at`
	var account Account
	err = a.db.QueryRowContext(ctx, query,
		input.ID, input.Abbr, input.Nickname, nullableString(input.PhoneNumber), nullableString(input.Remark),
		input.Tacet, isActive, fullAt, fullCrystal,
	).Scan(
		&account.AccountID, &account.ID, &account.Abbr, &account.Nickname, &account.PhoneNumber, &account.Remark,
		&account.Tacet, &account.FullWaveplateAt, &account.FullWaveplateCrystal, &account.IsActive, &account.CreatedAt, &account.UpdatedAt,
	)
	if err != nil {
		if isUniqueViolation(err) {
			writeError(w, http.StatusConflict, "id or abbr already exists")
			return
		}
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, a.accountPayload(account, now))
}

func nullableString(value *string) any {
	if value == nil {
		return nil
	}
	return *value
}

func (a *App) handleListAccounts(w http.ResponseWriter, r *http.Request) {
	activeOnly := r.URL.Query().Get("active_only") == "true"
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	query := `SELECT account_id, id, abbr, nickname, phone_number, remark, tacet, full_waveplate_at, full_waveplate_crystal, is_active, created_at, updated_at
	FROM accounts`
	if activeOnly {
		query += ` WHERE is_active IS TRUE`
	}
	query += ` ORDER BY created_at DESC`
	rows, err := a.db.QueryContext(ctx, query)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	defer rows.Close()
	now := a.now()
	out := make([]AccountOut, 0)
	for rows.Next() {
		account, err := scanAccount(rows)
		if err != nil {
			writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
		out = append(out, a.accountPayload(account, now))
	}
	writeJSON(w, http.StatusOK, out)
}

func scanAccount(scanner interface{ Scan(dest ...any) error }) (Account, error) {
	var account Account
	err := scanner.Scan(
		&account.AccountID, &account.ID, &account.Abbr, &account.Nickname, &account.PhoneNumber, &account.Remark,
		&account.Tacet, &account.FullWaveplateAt, &account.FullWaveplateCrystal, &account.IsActive, &account.CreatedAt, &account.UpdatedAt,
	)
	return account, err
}

func (a *App) fetchAccountByID(ctx context.Context, gameID string) (Account, error) {
	row := a.db.QueryRowContext(ctx, `SELECT account_id, id, abbr, nickname, phone_number, remark, tacet, full_waveplate_at, full_waveplate_crystal, is_active, created_at, updated_at
	FROM accounts WHERE id = $1`, gameID)
	account, err := scanAccount(row)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return Account{}, errNotFound("account not found")
		}
		return Account{}, err
	}
	return account, nil
}

func (a *App) fetchAccountByAccountID(ctx context.Context, accountID int) (Account, error) {
	row := a.db.QueryRowContext(ctx, `SELECT account_id, id, abbr, nickname, phone_number, remark, tacet, full_waveplate_at, full_waveplate_crystal, is_active, created_at, updated_at
	FROM accounts WHERE account_id = $1`, accountID)
	account, err := scanAccount(row)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return Account{}, errNotFound("account not found")
		}
		return Account{}, err
	}
	return account, nil
}

type notFoundError struct{ message string }

func (e notFoundError) Error() string { return e.message }

func errNotFound(message string) error { return notFoundError{message: message} }

func isNotFound(err error) bool {
	var target notFoundError
	return errors.As(err, &target)
}

func (a *App) handleGetAccountByID(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	account, err := a.fetchAccountByID(ctx, r.PathValue("id"))
	if err != nil {
		a.writeErrorForFetch(w, err)
		return
	}
	writeJSON(w, http.StatusOK, a.accountPayload(account, a.now()))
}

func (a *App) writeErrorForFetch(w http.ResponseWriter, err error) {
	if isNotFound(err) {
		writeError(w, http.StatusNotFound, err.Error())
		return
	}
	writeError(w, http.StatusInternalServerError, err.Error())
}

func (a *App) handleUpdateAccountByAccountID(w http.ResponseWriter, r *http.Request) {
	accountID, err := strconv.Atoi(r.PathValue("account_id"))
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid account_id")
		return
	}
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	account, err := a.fetchAccountByAccountID(ctx, accountID)
	if err != nil {
		a.writeErrorForFetch(w, err)
		return
	}
	a.updateAccount(w, r, account)
}

func (a *App) handleUpdateAccountByID(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	account, err := a.fetchAccountByID(ctx, r.PathValue("id"))
	if err != nil {
		a.writeErrorForFetch(w, err)
		return
	}
	a.updateAccount(w, r, account)
}

func (a *App) updateAccount(w http.ResponseWriter, r *http.Request, account Account) {
	var input updateAccountInput
	if err := decodeJSON(r, &input); err != nil {
		writeError(w, http.StatusBadRequest, "invalid json")
		return
	}
	if input.Tacet != nil {
		if err := validateTacet(*input.Tacet); err != nil {
			writeError(w, http.StatusBadRequest, err.Error())
			return
		}
	}
	now := a.now()
	if input.CurrentWaveplate != nil || input.CurrentWaveplateCrystal != nil || input.FullWaveplateAt != nil {
		energyPayload := energySetInput{
			CurrentWaveplate:        input.CurrentWaveplate,
			CurrentWaveplateCrystal: input.CurrentWaveplateCrystal,
			FullWaveplateAt:         input.FullWaveplateAt,
		}
		if err := a.applyEnergySet(&account, energyPayload, now); err != nil {
			writeError(w, http.StatusBadRequest, err.Error())
			return
		}
	}

	ctx, cancel := a.withTimeout(r)
	defer cancel()
	query := `UPDATE accounts SET
		phone_number = COALESCE($2, phone_number),
		nickname = COALESCE($3, nickname),
		abbr = COALESCE($4, abbr),
		remark = COALESCE($5, remark),
		tacet = COALESCE($6, tacet),
		is_active = COALESCE($7, is_active),
		full_waveplate_at = $8,
		full_waveplate_crystal = $9,
		updated_at = now()
	WHERE account_id = $1
	RETURNING account_id, id, abbr, nickname, phone_number, remark, tacet, full_waveplate_at, full_waveplate_crystal, is_active, created_at, updated_at`
	row := a.db.QueryRowContext(ctx, query,
		account.AccountID,
		nullableString(input.PhoneNumber),
		nullableString(input.Nickname),
		nullableString(input.Abbr),
		nullableString(input.Remark),
		nullableString(input.Tacet),
		input.IsActive,
		account.FullWaveplateAt,
		account.FullWaveplateCrystal,
	)
	updated, err := scanAccount(row)
	if err != nil {
		if isUniqueViolation(err) {
			writeError(w, http.StatusConflict, "id or abbr already exists")
			return
		}
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, a.accountPayload(updated, a.now()))
}

func (a *App) handleDeleteAccountByAccountID(w http.ResponseWriter, r *http.Request) {
	accountID, err := strconv.Atoi(r.PathValue("account_id"))
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid account_id")
		return
	}
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	res, err := a.db.ExecContext(ctx, `DELETE FROM accounts WHERE account_id = $1`, accountID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	affected, _ := res.RowsAffected()
	if affected == 0 {
		writeError(w, http.StatusNotFound, "account not found")
		return
	}
	writeJSON(w, http.StatusOK, map[string]bool{"ok": true})
}

func (a *App) handleDeleteAccountByID(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	res, err := a.db.ExecContext(ctx, `DELETE FROM accounts WHERE id = $1`, r.PathValue("id"))
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	affected, _ := res.RowsAffected()
	if affected == 0 {
		writeError(w, http.StatusNotFound, "account not found")
		return
	}
	writeJSON(w, http.StatusOK, map[string]bool{"ok": true})
}

func (a *App) handleSetCheckinByID(w http.ResponseWriter, r *http.Request) {
	var input checkinInput
	if err := decodeJSON(r, &input); err != nil {
		writeError(w, http.StatusBadRequest, "invalid json")
		return
	}
	if input.Status == nil && input.IsDone == nil {
		writeError(w, http.StatusBadRequest, "status or is_done is required")
		return
	}
	periodType, periodKey, statusDate, err := a.resolvePeriod(input.FlagKey, a.resetDay(a.now()))
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	resolvedStatus := "todo"
	if input.Status != nil {
		resolvedStatus = strings.TrimSpace(strings.ToLower(*input.Status))
	} else if input.IsDone != nil && *input.IsDone {
		resolvedStatus = "done"
	}
	if !validateTaskStatus(resolvedStatus) {
		writeError(w, http.StatusBadRequest, "status must be todo, done or skipped")
		return
	}
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	account, err := a.fetchAccountByID(ctx, r.PathValue("id"))
	if err != nil {
		a.writeErrorForFetch(w, err)
		return
	}
	isDone := isDoneStatus(resolvedStatus)
	query := `INSERT INTO account_checkins (account_id, status_date, period_type, period_key, flag_key, status, is_done, updated_at)
	VALUES ($1,$2,$3,$4,$5,$6,$7,now())
	ON CONFLICT (account_id, period_type, period_key, flag_key)
	DO UPDATE SET status_date = EXCLUDED.status_date, status = EXCLUDED.status, is_done = EXCLUDED.is_done, updated_at = now()`
	_, err = a.db.ExecContext(ctx, query, account.AccountID, statusDate.Format("2006-01-02"), periodType, periodKey, input.FlagKey, resolvedStatus, isDone)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"ok": true, "flag_key": input.FlagKey, "status": resolvedStatus, "is_done": isDone})
}

func (a *App) handleSetTacetByID(w http.ResponseWriter, r *http.Request) {
	var input tacetInput
	if err := decodeJSON(r, &input); err != nil {
		writeError(w, http.StatusBadRequest, "invalid json")
		return
	}
	if err := validateTacet(input.Tacet); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	res, err := a.db.ExecContext(ctx, `UPDATE accounts SET tacet = $2, updated_at = now() WHERE id = $1`, r.PathValue("id"), input.Tacet)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	affected, _ := res.RowsAffected()
	if affected == 0 {
		writeError(w, http.StatusNotFound, "account not found")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"ok": true, "tacet": input.Tacet})
}

func (a *App) accountCleanupState(ctx context.Context, account Account, day, now time.Time) (CleanupTimerStateOut, error) {
	var pausedSec int
	if err := a.db.QueryRowContext(ctx, `SELECT COALESCE(SUM(duration_sec), 0) FROM account_cleanup_sessions WHERE account_id = $1 AND biz_date = $2 AND status = 'paused'`, account.AccountID, day.Format("2006-01-02")).Scan(&pausedSec); err != nil {
		return CleanupTimerStateOut{}, err
	}
	rows, err := a.db.QueryContext(ctx, `SELECT id, account_id, biz_date, started_at, ended_at, duration_sec, status FROM account_cleanup_sessions WHERE account_id = $1 AND status = 'running' ORDER BY started_at DESC LIMIT 1`, account.AccountID)
	if err != nil {
		return CleanupTimerStateOut{}, err
	}
	defer rows.Close()
	var running *CleanupSession
	if rows.Next() {
		session, err := scanCleanupSession(rows)
		if err != nil {
			return CleanupTimerStateOut{}, err
		}
		running = &session
	}
	var runningSeconds int
	var runningStartedAt *time.Time
	var runningSessionID *int
	if running != nil {
		runningSeconds = runningDurationSeconds(running.StartedAt, now)
		started := running.StartedAt
		runningStartedAt = &started
		id := running.ID
		runningSessionID = &id
	}
	return CleanupTimerStateOut{
		AccountID:        account.AccountID,
		ID:               account.ID,
		Abbr:             account.Abbr,
		Nickname:         account.Nickname,
		BizDate:          day.Format("2006-01-02"),
		TodayTotalSec:    pausedSec + runningSeconds,
		TodayPausedSec:   pausedSec,
		Running:          running != nil,
		RunningStartedAt: runningStartedAt,
		RunningSessionID: runningSessionID,
	}, nil
}

func scanCleanupSession(scanner interface{ Scan(dest ...any) error }) (CleanupSession, error) {
	var session CleanupSession
	err := scanner.Scan(&session.ID, &session.AccountID, &session.BizDate, &session.StartedAt, &session.EndedAt, &session.DurationSec, &session.Status)
	return session, err
}

func (a *App) handleStartCleanupTimerByID(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	account, err := a.fetchAccountByID(ctx, r.PathValue("id"))
	if err != nil {
		a.writeErrorForFetch(w, err)
		return
	}
	now := a.now()
	today := a.resetDay(now)
	var existing int
	err = a.db.QueryRowContext(ctx, `SELECT COUNT(1) FROM account_cleanup_sessions WHERE account_id = $1 AND status = 'running'`, account.AccountID).Scan(&existing)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	if existing == 0 {
		_, err = a.db.ExecContext(ctx, `INSERT INTO account_cleanup_sessions (account_id, biz_date, started_at, status, duration_sec, created_at, updated_at)
			VALUES ($1,$2,$3,'running',0,now(),now())`, account.AccountID, today.Format("2006-01-02"), now)
		if err != nil {
			writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
	}
	state, err := a.accountCleanupState(ctx, account, today, now)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, state)
}

func (a *App) handlePauseCleanupTimerByID(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	account, err := a.fetchAccountByID(ctx, r.PathValue("id"))
	if err != nil {
		a.writeErrorForFetch(w, err)
		return
	}
	now := a.now()
	today := a.resetDay(now)
	rows, err := a.db.QueryContext(ctx, `SELECT id, account_id, biz_date, started_at, ended_at, duration_sec, status FROM account_cleanup_sessions WHERE account_id = $1 AND status = 'running' ORDER BY started_at DESC LIMIT 1`, account.AccountID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	defer rows.Close()
	if rows.Next() {
		session, err := scanCleanupSession(rows)
		if err != nil {
			writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
		duration := runningDurationSeconds(session.StartedAt, now)
		_, err = a.db.ExecContext(ctx, `UPDATE account_cleanup_sessions SET ended_at = $2, duration_sec = $3, status = 'paused', updated_at = now() WHERE id = $1`, session.ID, now, duration)
		if err != nil {
			writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
	}
	state, err := a.accountCleanupState(ctx, account, today, now)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, state)
}

func (a *App) handleGetCleanupTimerTodayByID(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	account, err := a.fetchAccountByID(ctx, r.PathValue("id"))
	if err != nil {
		a.writeErrorForFetch(w, err)
		return
	}
	now := a.now()
	state, err := a.accountCleanupState(ctx, account, a.resetDay(now), now)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, state)
}

func (a *App) handleCleanupWeeklySummary(w http.ResponseWriter, r *http.Request) {
	days := 7
	if value := strings.TrimSpace(r.URL.Query().Get("days")); value != "" {
		parsed, err := strconv.Atoi(value)
		if err != nil || parsed < 1 || parsed > 90 {
			writeError(w, http.StatusBadRequest, "days must be between 1 and 90")
			return
		}
		days = parsed
	}
	now := a.now()
	endDay := a.resetDay(now)
	startDay := endDay.AddDate(0, 0, -(days - 1))
	dayDuration := map[string]int{}
	dayKeys := make([]string, 0, days)
	for i := 0; i < days; i++ {
		key := startDay.AddDate(0, 0, i).Format("2006-01-02")
		dayKeys = append(dayKeys, key)
		dayDuration[key] = 0
	}
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	rows, err := a.db.QueryContext(ctx, `SELECT biz_date, COALESCE(SUM(duration_sec), 0)
		FROM account_cleanup_sessions
		WHERE biz_date >= $1 AND biz_date <= $2 AND status = 'paused'
		GROUP BY biz_date`, startDay.Format("2006-01-02"), endDay.Format("2006-01-02"))
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	for rows.Next() {
		var bizDate time.Time
		var total int
		if err := rows.Scan(&bizDate, &total); err != nil {
			rows.Close()
			writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
		dayDuration[bizDate.Format("2006-01-02")] += total
	}
	rows.Close()

	accountDuration := map[int]int{}
	rows, err = a.db.QueryContext(ctx, `SELECT account_id, COALESCE(SUM(duration_sec), 0)
		FROM account_cleanup_sessions
		WHERE biz_date >= $1 AND biz_date <= $2 AND status = 'paused'
		GROUP BY account_id`, startDay.Format("2006-01-02"), endDay.Format("2006-01-02"))
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	for rows.Next() {
		var accountID, total int
		if err := rows.Scan(&accountID, &total); err != nil {
			rows.Close()
			writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
		accountDuration[accountID] = total
	}
	rows.Close()

	rows, err = a.db.QueryContext(ctx, `SELECT id, account_id, biz_date, started_at, ended_at, duration_sec, status
		FROM account_cleanup_sessions
		WHERE status = 'running' AND biz_date >= $1 AND biz_date <= $2`, startDay.Format("2006-01-02"), endDay.Format("2006-01-02"))
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	for rows.Next() {
		session, err := scanCleanupSession(rows)
		if err != nil {
			rows.Close()
			writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
		live := runningDurationSeconds(session.StartedAt, now)
		key := session.BizDate.Format("2006-01-02")
		dayDuration[key] += live
		accountDuration[session.AccountID] += live
	}
	rows.Close()

	accountMeta := map[int]Account{}
	if len(accountDuration) > 0 {
		ids := make([]int, 0, len(accountDuration))
		for id := range accountDuration {
			ids = append(ids, id)
		}
		sort.Ints(ids)
		query, args := intInQuery(`SELECT account_id, id, abbr, nickname, phone_number, remark, tacet, full_waveplate_at, full_waveplate_crystal, is_active, created_at, updated_at FROM accounts WHERE account_id IN (%s)`, ids)
		rows, err = a.db.QueryContext(ctx, query, args...)
		if err != nil {
			writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
		for rows.Next() {
			account, err := scanAccount(rows)
			if err != nil {
				rows.Close()
				writeError(w, http.StatusInternalServerError, err.Error())
				return
			}
			accountMeta[account.AccountID] = account
		}
		rows.Close()
	}

	daily := make([]CleanupWeeklyDayOut, 0, len(dayKeys))
	totalDuration := 0
	for _, key := range dayKeys {
		duration := dayDuration[key]
		daily = append(daily, CleanupWeeklyDayOut{BizDate: key, DurationSec: duration})
		totalDuration += duration
	}

	type accountDurationRow struct {
		AccountID   int
		DurationSec int
	}
	accountRows := make([]accountDurationRow, 0, len(accountDuration))
	for accountID, duration := range accountDuration {
		accountRows = append(accountRows, accountDurationRow{AccountID: accountID, DurationSec: duration})
	}
	sort.Slice(accountRows, func(i, j int) bool { return accountRows[i].DurationSec > accountRows[j].DurationSec })
	byAccount := make([]CleanupWeeklyAccountOut, 0, len(accountRows))
	for _, row := range accountRows {
		account, ok := accountMeta[row.AccountID]
		if !ok {
			continue
		}
		byAccount = append(byAccount, CleanupWeeklyAccountOut{
			AccountID: row.AccountID, ID: account.ID, Abbr: account.Abbr, Nickname: account.Nickname, DurationSec: row.DurationSec,
		})
	}
	writeJSON(w, http.StatusOK, CleanupWeeklySummaryOut{
		RangeStart:       startDay.Format("2006-01-02"),
		RangeEnd:         endDay.Format("2006-01-02"),
		TotalDurationSec: totalDuration,
		Daily:            daily,
		ByAccount:        byAccount,
	})
}

func intInQuery(base string, ids []int) (string, []any) {
	parts := make([]string, 0, len(ids))
	args := make([]any, 0, len(ids))
	for i, id := range ids {
		parts = append(parts, fmt.Sprintf("$%d", i+1))
		args = append(args, id)
	}
	return fmt.Sprintf(base, strings.Join(parts, ",")), args
}

func (a *App) handleListCleanupSessions(w http.ResponseWriter, r *http.Request) {
	days := 7
	if value := strings.TrimSpace(r.URL.Query().Get("days")); value != "" {
		parsed, err := strconv.Atoi(value)
		if err != nil || parsed < 1 || parsed > 90 {
			writeError(w, http.StatusBadRequest, "days must be between 1 and 90")
			return
		}
		days = parsed
	}
	var accountFilter *int
	if value := strings.TrimSpace(r.URL.Query().Get("account_id")); value != "" {
		parsed, err := strconv.Atoi(value)
		if err != nil {
			writeError(w, http.StatusBadRequest, "invalid account_id")
			return
		}
		accountFilter = &parsed
	}
	now := a.now()
	endDay := a.resetDay(now)
	startDay := endDay.AddDate(0, 0, -(days - 1))
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	query := `SELECT s.id, s.account_id, s.biz_date, s.started_at, s.ended_at, s.duration_sec, s.status,
		a.account_id, a.id, a.abbr, a.nickname, a.phone_number, a.remark, a.tacet, a.full_waveplate_at, a.full_waveplate_crystal, a.is_active, a.created_at, a.updated_at
		FROM account_cleanup_sessions s
		JOIN accounts a ON a.account_id = s.account_id
		WHERE s.biz_date >= $1 AND s.biz_date <= $2`
	args := []any{startDay.Format("2006-01-02"), endDay.Format("2006-01-02")}
	if accountFilter != nil {
		query += ` AND s.account_id = $3`
		args = append(args, *accountFilter)
	}
	query += ` ORDER BY s.started_at DESC`
	rows, err := a.db.QueryContext(ctx, query, args...)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	defer rows.Close()
	out := make([]CleanupSessionOut, 0)
	for rows.Next() {
		var session CleanupSession
		var account Account
		if err := rows.Scan(
			&session.ID, &session.AccountID, &session.BizDate, &session.StartedAt, &session.EndedAt, &session.DurationSec, &session.Status,
			&account.AccountID, &account.ID, &account.Abbr, &account.Nickname, &account.PhoneNumber, &account.Remark, &account.Tacet,
			&account.FullWaveplateAt, &account.FullWaveplateCrystal, &account.IsActive, &account.CreatedAt, &account.UpdatedAt,
		); err != nil {
			writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
		duration := session.DurationSec
		if session.Status == "running" {
			duration = runningDurationSeconds(session.StartedAt, now)
		}
		var endedAt *time.Time
		if session.EndedAt.Valid {
			value := session.EndedAt.Time
			endedAt = &value
		}
		out = append(out, CleanupSessionOut{
			ID: session.ID, AccountID: account.AccountID, AccountGameID: account.ID, AccountAbbr: account.Abbr, AccountNickname: account.Nickname,
			BizDate: session.BizDate.Format("2006-01-02"), StartedAt: session.StartedAt, EndedAt: endedAt, DurationSec: duration, Status: session.Status,
		})
	}
	writeJSON(w, http.StatusOK, out)
}

func (a *App) handleCreateCleanupSessionManual(w http.ResponseWriter, r *http.Request) {
	var input cleanupManualInput
	if err := decodeJSON(r, &input); err != nil {
		writeError(w, http.StatusBadRequest, "invalid json")
		return
	}
	hasDurationMode := input.DurationSec != nil
	hasPeriodMode := input.StartedAt != nil || input.EndedAt != nil
	if hasDurationMode && hasPeriodMode {
		writeError(w, http.StatusBadRequest, "duration mode and period mode cannot be mixed")
		return
	}
	if !hasDurationMode && (input.StartedAt == nil || input.EndedAt == nil) {
		writeError(w, http.StatusBadRequest, "started_at and ended_at are required when using period mode")
		return
	}
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	account, err := a.fetchAccountByAccountID(ctx, input.AccountID)
	if err != nil {
		a.writeErrorForFetch(w, err)
		return
	}
	var bizDate time.Time
	var startedAt time.Time
	var endedAt time.Time
	var durationSec int
	if hasDurationMode {
		if input.BizDate == nil {
			writeError(w, http.StatusBadRequest, "biz_date is required when duration_sec is provided")
			return
		}
		bizDate, err = time.ParseInLocation("2006-01-02", *input.BizDate, a.cfg.Location)
		if err != nil {
			writeError(w, http.StatusBadRequest, "invalid biz_date")
			return
		}
		startedAt = bizDate
		endedAt = startedAt.Add(time.Duration(*input.DurationSec) * time.Second)
		durationSec = *input.DurationSec
	} else {
		startedAt = a.toAppTZ(*input.StartedAt)
		endedAt = a.toAppTZ(*input.EndedAt)
		if !endedAt.After(startedAt) {
			writeError(w, http.StatusBadRequest, "ended_at must be later than started_at")
			return
		}
		durationSec = int(endedAt.Sub(startedAt).Seconds())
		if durationSec <= 0 {
			writeError(w, http.StatusBadRequest, "duration must be greater than 0 seconds")
			return
		}
		if durationSec > 86400 {
			writeError(w, http.StatusBadRequest, "duration cannot exceed 24 hours")
			return
		}
		if input.BizDate != nil {
			bizDate, err = time.ParseInLocation("2006-01-02", *input.BizDate, a.cfg.Location)
			if err != nil {
				writeError(w, http.StatusBadRequest, "invalid biz_date")
				return
			}
		} else {
			bizDate = a.resetDay(startedAt)
		}
	}
	row := a.db.QueryRowContext(ctx, `INSERT INTO account_cleanup_sessions (account_id, biz_date, started_at, ended_at, duration_sec, status, created_at, updated_at)
		VALUES ($1,$2,$3,$4,$5,'paused',now(),now())
		RETURNING id, account_id, biz_date, started_at, ended_at, duration_sec, status`,
		account.AccountID, bizDate.Format("2006-01-02"), startedAt, endedAt, durationSec)
	session, err := scanCleanupSession(row)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	ended := session.EndedAt.Time
	writeJSON(w, http.StatusOK, CleanupSessionOut{
		ID: session.ID, AccountID: account.AccountID, AccountGameID: account.ID, AccountAbbr: account.Abbr, AccountNickname: account.Nickname,
		BizDate: session.BizDate.Format("2006-01-02"), StartedAt: session.StartedAt, EndedAt: &ended, DurationSec: session.DurationSec, Status: session.Status,
	})
}

func (a *App) handleDeleteCleanupSession(w http.ResponseWriter, r *http.Request) {
	sessionID, err := strconv.Atoi(r.PathValue("session_id"))
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid session_id")
		return
	}
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	res, err := a.db.ExecContext(ctx, `DELETE FROM account_cleanup_sessions WHERE id = $1`, sessionID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	affected, _ := res.RowsAffected()
	if affected == 0 {
		writeError(w, http.StatusNotFound, "cleanup session not found")
		return
	}
	writeJSON(w, http.StatusOK, map[string]bool{"ok": true})
}

func (a *App) handleGetEnergyByAccountID(w http.ResponseWriter, r *http.Request) {
	accountID, err := strconv.Atoi(r.PathValue("account_id"))
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid account_id")
		return
	}
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	account, err := a.fetchAccountByAccountID(ctx, accountID)
	if err != nil {
		a.writeErrorForFetch(w, err)
		return
	}
	writeJSON(w, http.StatusOK, a.energyPayload(account, a.now()))
}

func (a *App) handleGetEnergyByID(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	account, err := a.fetchAccountByID(ctx, r.PathValue("id"))
	if err != nil {
		a.writeErrorForFetch(w, err)
		return
	}
	writeJSON(w, http.StatusOK, a.energyPayload(account, a.now()))
}

func (a *App) setEnergy(w http.ResponseWriter, r *http.Request, account Account) {
	var input energySetInput
	if err := decodeJSON(r, &input); err != nil {
		writeError(w, http.StatusBadRequest, "invalid json")
		return
	}
	if input.CurrentWaveplate == nil && input.FullWaveplateAt == nil {
		writeError(w, http.StatusBadRequest, "current_waveplate or full_waveplate_at is required")
		return
	}
	now := a.now()
	if err := a.applyEnergySet(&account, input, now); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	row := a.db.QueryRowContext(ctx, `UPDATE accounts SET full_waveplate_at = $2, full_waveplate_crystal = $3, updated_at = now()
		WHERE account_id = $1
		RETURNING account_id, id, abbr, nickname, phone_number, remark, tacet, full_waveplate_at, full_waveplate_crystal, is_active, created_at, updated_at`,
		account.AccountID, account.FullWaveplateAt, account.FullWaveplateCrystal)
	updated, err := scanAccount(row)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, a.energyPayload(updated, now))
}

func (a *App) handleSetEnergyByAccountID(w http.ResponseWriter, r *http.Request) {
	accountID, err := strconv.Atoi(r.PathValue("account_id"))
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid account_id")
		return
	}
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	account, err := a.fetchAccountByAccountID(ctx, accountID)
	if err != nil {
		a.writeErrorForFetch(w, err)
		return
	}
	a.setEnergy(w, r, account)
}

func (a *App) handleSetEnergyByID(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	account, err := a.fetchAccountByID(ctx, r.PathValue("id"))
	if err != nil {
		a.writeErrorForFetch(w, err)
		return
	}
	a.setEnergy(w, r, account)
}

func (a *App) changeEnergy(w http.ResponseWriter, r *http.Request, account Account, mode string) {
	now := a.now()
	currentWP, currentCrystal := currentResourcesFromFullTime(account.FullWaveplateAt, account.FullWaveplateCrystal, now)
	switch mode {
	case "spend":
		var input spendEnergyInput
		if err := decodeJSON(r, &input); err != nil {
			writeError(w, http.StatusBadRequest, "invalid json")
			return
		}
		if !slices.Contains([]int{40, 60, 80, 120}, input.Cost) {
			writeError(w, http.StatusBadRequest, "cost must be one of 40, 60, 80, 120")
			return
		}
		if currentWP+currentCrystal < input.Cost {
			writeError(w, http.StatusBadRequest, fmt.Sprintf("not enough waveplate: current %d + crystal %d < cost %d", currentWP, currentCrystal, input.Cost))
			return
		}
		nextWP, nextCrystal := spendResources(currentWP, currentCrystal, input.Cost)
		if err := a.applyQuickEnergyChange(&account, currentWP, nextWP, nextCrystal, now); err != nil {
			writeError(w, http.StatusBadRequest, err.Error())
			return
		}
	case "gain":
		var input gainEnergyInput
		if err := decodeJSON(r, &input); err != nil {
			writeError(w, http.StatusBadRequest, "invalid json")
			return
		}
		if !slices.Contains([]int{40, 60}, input.Amount) {
			writeError(w, http.StatusBadRequest, "amount must be one of 40, 60")
			return
		}
		nextWP, nextCrystal := addResources(currentWP, currentCrystal, input.Amount)
		if err := a.applyQuickEnergyChange(&account, currentWP, nextWP, nextCrystal, now); err != nil {
			writeError(w, http.StatusBadRequest, err.Error())
			return
		}
	}
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	tx, err := a.db.BeginTx(ctx, nil)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	defer tx.Rollback()
	row := tx.QueryRowContext(ctx, `UPDATE accounts SET full_waveplate_at = $2, full_waveplate_crystal = $3, updated_at = now()
		WHERE account_id = $1
		RETURNING account_id, id, abbr, nickname, phone_number, remark, tacet, full_waveplate_at, full_waveplate_crystal, is_active, created_at, updated_at`,
		account.AccountID, account.FullWaveplateAt, account.FullWaveplateCrystal)
	updated, err := scanAccount(row)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	if err := tx.Commit(); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, a.energyPayload(updated, now))
}

func (a *App) handleSpendEnergyByAccountID(w http.ResponseWriter, r *http.Request) {
	accountID, err := strconv.Atoi(r.PathValue("account_id"))
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid account_id")
		return
	}
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	account, err := a.fetchAccountByAccountID(ctx, accountID)
	if err != nil {
		a.writeErrorForFetch(w, err)
		return
	}
	a.changeEnergy(w, r, account, "spend")
}

func (a *App) handleSpendEnergyByID(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	account, err := a.fetchAccountByID(ctx, r.PathValue("id"))
	if err != nil {
		a.writeErrorForFetch(w, err)
		return
	}
	a.changeEnergy(w, r, account, "spend")
}

func (a *App) handleGainEnergyByAccountID(w http.ResponseWriter, r *http.Request) {
	accountID, err := strconv.Atoi(r.PathValue("account_id"))
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid account_id")
		return
	}
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	account, err := a.fetchAccountByAccountID(ctx, accountID)
	if err != nil {
		a.writeErrorForFetch(w, err)
		return
	}
	a.changeEnergy(w, r, account, "gain")
}

func (a *App) handleGainEnergyByID(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	account, err := a.fetchAccountByID(ctx, r.PathValue("id"))
	if err != nil {
		a.writeErrorForFetch(w, err)
		return
	}
	a.changeEnergy(w, r, account, "gain")
}

func isUniqueViolation(err error) bool {
	return strings.Contains(strings.ToLower(err.Error()), "duplicate key") || strings.Contains(strings.ToLower(err.Error()), "unique")
}

func (a *App) handleDashboardAccounts(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	rows, err := a.db.QueryContext(ctx, `SELECT account_id, id, abbr, nickname, phone_number, remark, tacet, full_waveplate_at, full_waveplate_crystal, is_active, created_at, updated_at
		FROM accounts WHERE is_active IS TRUE ORDER BY abbr`)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	defer rows.Close()
	accounts := make([]Account, 0)
	accountIDs := make([]int, 0)
	for rows.Next() {
		account, err := scanAccount(rows)
		if err != nil {
			writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
		accounts = append(accounts, account)
		accountIDs = append(accountIDs, account.AccountID)
	}
	if len(accounts) == 0 {
		writeJSON(w, http.StatusOK, []DashboardAccountOut{})
		return
	}

	now := a.now()
	today := a.resetDay(now)
	todayKey := today.Format("2006-01-02")
	weekKey := weeklyPeriodKey(today)

	flagsMap := map[int]map[string]string{}
	inClause, args := intInQueryWithStart("%s", accountIDs, 1)
	query := fmt.Sprintf(`SELECT account_id, status_date, period_type, period_key, flag_key, status, is_done
		FROM account_checkins
		WHERE account_id IN (%s)
		AND ((period_type = 'daily' AND period_key = $%d) OR (period_type = 'weekly' AND period_key = $%d))`,
		inClause, len(args)+1, len(args)+2)
	args = append(args, todayKey, weekKey)
	rows, err = a.db.QueryContext(ctx, query, args...)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	for rows.Next() {
		var item AccountCheckin
		if err := rows.Scan(&item.AccountID, &item.StatusDate, &item.PeriodType, &item.PeriodKey, &item.FlagKey, &item.Status, &item.IsDone); err != nil {
			rows.Close()
			writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
		normalized := normalizeCheckinStatus(item.Status, item.IsDone)
		if _, ok := flagsMap[item.AccountID]; !ok {
			flagsMap[item.AccountID] = map[string]string{}
		}
		flagsMap[item.AccountID][item.FlagKey] = normalized
	}
	rows.Close()

	taskCounts := map[int][2]int{}
	query, args = intInQuery(`SELECT account_id,
		COALESCE(SUM(CASE WHEN status = 'todo' THEN 1 ELSE 0 END), 0),
		COALESCE(SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END), 0)
		FROM task_instances WHERE account_id IN (%s) GROUP BY account_id`, accountIDs)
	rows, err = a.db.QueryContext(ctx, query, args...)
	if err == nil {
		for rows.Next() {
			var accountID, todoCount, doneCount int
			if err := rows.Scan(&accountID, &todoCount, &doneCount); err != nil {
				rows.Close()
				writeError(w, http.StatusInternalServerError, err.Error())
				return
			}
			taskCounts[accountID] = [2]int{todoCount, doneCount}
		}
		rows.Close()
	}

	cleanupPaused := map[int]int{}
	inClause, args = intInQueryWithStart("%s", accountIDs, 1)
	query = fmt.Sprintf(`SELECT account_id, COALESCE(SUM(duration_sec), 0)
		FROM account_cleanup_sessions
		WHERE account_id IN (%s) AND biz_date = $%d AND status = 'paused'
		GROUP BY account_id`, inClause, len(args)+1)
	args = append(args, todayKey)
	rows, err = a.db.QueryContext(ctx, query, args...)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	for rows.Next() {
		var accountID, total int
		if err := rows.Scan(&accountID, &total); err != nil {
			rows.Close()
			writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
		cleanupPaused[accountID] = total
	}
	rows.Close()

	runningMap := map[int]CleanupSession{}
	query, args = intInQuery(`SELECT id, account_id, biz_date, started_at, ended_at, duration_sec, status
		FROM account_cleanup_sessions
		WHERE account_id IN (%s) AND status = 'running'`, accountIDs)
	rows, err = a.db.QueryContext(ctx, query, args...)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	for rows.Next() {
		session, err := scanCleanupSession(rows)
		if err != nil {
			rows.Close()
			writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
		existing, ok := runningMap[session.AccountID]
		if !ok || session.StartedAt.After(existing.StartedAt) {
			runningMap[session.AccountID] = session
		}
	}
	rows.Close()

	out := make([]DashboardAccountOut, 0, len(accounts))
	for _, account := range accounts {
		currentWP, currentCrystal := currentResourcesFromFullTime(account.FullWaveplateAt, account.FullWaveplateCrystal, now)
		toFullSeconds := secondsToWaveplateFullFromFullTime(account.FullWaveplateAt, now)
		toFull := (toFullSeconds + 59) / 60
		accountFlags := flagsMap[account.AccountID]
		dailyTaskStatus := defaultStatus(accountFlags["daily_task"])
		dailyNestStatus := defaultStatus(accountFlags["daily_nest"])
		weeklyDoorStatus := defaultStatus(accountFlags["weekly_door"])
		weeklyBossStatus := defaultStatus(accountFlags["weekly_boss"])
		weeklySynthesisStatus := defaultStatus(accountFlags["weekly_synthesis"])
		pausedSec := cleanupPaused[account.AccountID]
		runningSession, running := runningMap[account.AccountID]
		totalSec := pausedSec
		var runningStartedAt *time.Time
		if running {
			totalSec += runningDurationSeconds(runningSession.StartedAt, now)
			started := runningSession.StartedAt
			runningStartedAt = &started
		}
		counts := taskCounts[account.AccountID]
		out = append(out, DashboardAccountOut{
			AccountID:               account.AccountID,
			ID:                      account.ID,
			Abbr:                    account.Abbr,
			Nickname:                account.Nickname,
			PhoneNumber:             accountPhonePtr(account.PhoneNumber),
			Remark:                  accountRemarkPtr(account.Remark),
			Tacet:                   account.Tacet,
			CurrentWaveplate:        currentWP,
			CurrentWaveplateCrystal: currentCrystal,
			WarnLevel:               warnLevel(currentWP),
			DailyTask:               isDoneStatus(dailyTaskStatus),
			DailyNest:               isDoneStatus(dailyNestStatus),
			WeeklyDoor:              isDoneStatus(weeklyDoorStatus),
			WeeklyBoss:              isDoneStatus(weeklyBossStatus),
			WeeklySynthesis:         isDoneStatus(weeklySynthesisStatus),
			DailyTaskStatus:         dailyTaskStatus,
			DailyNestStatus:         dailyNestStatus,
			WeeklyDoorStatus:        weeklyDoorStatus,
			WeeklyBossStatus:        weeklyBossStatus,
			WeeklySynthesisStatus:   weeklySynthesisStatus,
			CleanupTodayTotalSec:    totalSec,
			CleanupTodayPausedSec:   pausedSec,
			CleanupRunning:          running,
			CleanupRunningStartedAt: runningStartedAt,
			WaveplateFullInMinutes:  toFull,
			ETAWaveplateFull:        account.FullWaveplateAt,
			TodoCount:               counts[0],
			DoneCount:               counts[1],
		})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].ETAWaveplateFull.Before(out[j].ETAWaveplateFull) })
	writeJSON(w, http.StatusOK, out)
}

func defaultStatus(status string) string {
	if status == "" {
		return "todo"
	}
	return status
}

func normalizeCheckinStatus(status string, isDone bool) string {
	normalized := strings.TrimSpace(strings.ToLower(status))
	if normalized == "todo" || normalized == "done" || normalized == "skipped" {
		return normalized
	}
	if isDone {
		return "done"
	}
	return "todo"
}

func intInQueryWithStart(base string, ids []int, start int) (string, []any) {
	parts := make([]string, 0, len(ids))
	args := make([]any, 0, len(ids))
	for i, id := range ids {
		parts = append(parts, fmt.Sprintf("$%d", start+i))
		args = append(args, id)
	}
	return fmt.Sprintf(base, strings.Join(parts, ",")), args
}

func (a *App) handlePeriodicAccounts(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	rows, err := a.db.QueryContext(ctx, `SELECT account_id, id, abbr, nickname, phone_number, remark, tacet, full_waveplate_at, full_waveplate_crystal, is_active, created_at, updated_at
		FROM accounts WHERE is_active IS TRUE ORDER BY abbr`)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	defer rows.Close()
	accounts := make([]Account, 0)
	accountIDs := make([]int, 0)
	for rows.Next() {
		account, err := scanAccount(rows)
		if err != nil {
			writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
		accounts = append(accounts, account)
		accountIDs = append(accountIDs, account.AccountID)
	}
	if len(accounts) == 0 {
		writeJSON(w, http.StatusOK, []PeriodicAccountOut{})
		return
	}
	trackedKeys := []string{
		"version_matrix_soldier",
		"version_small_coral_exchange",
		"version_hologram_challenge",
		"version_echo_template_adjust",
		"hv_trial_character",
		"monthly_tower_exchange",
		"four_week_tower",
		"four_week_ruins",
		"range_lahailuo_cube",
		"range_music_game",
	}
	expectedSet := map[string]struct{}{}
	today := a.today()
	for _, flagKey := range trackedKeys {
		periodType, periodKey, _, err := a.resolvePeriod(flagKey, today)
		if err != nil {
			writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
		expectedSet[periodType+"|"+periodKey] = struct{}{}
	}
	inClause, accountArgs := intInQueryWithStart("%s", accountIDs, 1)
	accountQuery := fmt.Sprintf(`SELECT account_id, status_date, period_type, period_key, flag_key, status, is_done
		FROM account_checkins WHERE account_id IN (%s) AND flag_key = ANY($%d)`, inClause, len(accountArgs)+1)
	args := append(accountArgs, trackedKeys)
	rows, err = a.db.QueryContext(ctx, accountQuery, args...)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	flagsMap := map[int]map[string]string{}
	for rows.Next() {
		var item AccountCheckin
		if err := rows.Scan(&item.AccountID, &item.StatusDate, &item.PeriodType, &item.PeriodKey, &item.FlagKey, &item.Status, &item.IsDone); err != nil {
			rows.Close()
			writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
		if _, ok := expectedSet[item.PeriodType+"|"+item.PeriodKey]; !ok {
			continue
		}
		if _, ok := flagsMap[item.AccountID]; !ok {
			flagsMap[item.AccountID] = map[string]string{}
		}
		flagsMap[item.AccountID][item.FlagKey] = normalizeCheckinStatus(item.Status, item.IsDone)
	}
	rows.Close()

	out := make([]PeriodicAccountOut, 0, len(accounts))
	for _, account := range accounts {
		flags := flagsMap[account.AccountID]
		vms := defaultStatus(flags["version_matrix_soldier"])
		vsce := defaultStatus(flags["version_small_coral_exchange"])
		vhc := defaultStatus(flags["version_hologram_challenge"])
		veta := defaultStatus(flags["version_echo_template_adjust"])
		hvtc := defaultStatus(flags["hv_trial_character"])
		mte := defaultStatus(flags["monthly_tower_exchange"])
		fwt := defaultStatus(flags["four_week_tower"])
		fwr := defaultStatus(flags["four_week_ruins"])
		rlc := defaultStatus(flags["range_lahailuo_cube"])
		rmg := defaultStatus(flags["range_music_game"])
		out = append(out, PeriodicAccountOut{
			AccountID:                       account.AccountID,
			ID:                              account.ID,
			Abbr:                            account.Abbr,
			Nickname:                        account.Nickname,
			PhoneNumber:                     accountPhonePtr(account.PhoneNumber),
			CreatedAt:                       account.CreatedAt,
			UpdatedAt:                       account.UpdatedAt,
			VersionMatrixSoldier:            isDoneStatus(vms),
			VersionMatrixSoldierStatus:      vms,
			VersionSmallCoralExchange:       isDoneStatus(vsce),
			VersionSmallCoralExchangeStatus: vsce,
			VersionHologramChallenge:        isDoneStatus(vhc),
			VersionHologramChallengeStatus:  vhc,
			VersionEchoTemplateAdjust:       isDoneStatus(veta),
			VersionEchoTemplateAdjustStatus: veta,
			HVTrialCharacter:                isDoneStatus(hvtc),
			HVTrialCharacterStatus:          hvtc,
			MonthlyTowerExchange:            isDoneStatus(mte),
			MonthlyTowerExchangeStatus:      mte,
			FourWeekTower:                   isDoneStatus(fwt),
			FourWeekTowerStatus:             fwt,
			FourWeekRuins:                   isDoneStatus(fwr),
			FourWeekRuinsStatus:             fwr,
			RangeLahailuoCube:               isDoneStatus(rlc),
			RangeLahailuoCubeStatus:         rlc,
			RangeMusicGame:                  isDoneStatus(rmg),
			RangeMusicGameStatus:            rmg,
		})
	}
	writeJSON(w, http.StatusOK, out)
}

func (a *App) handleCreateTaskTemplate(w http.ResponseWriter, r *http.Request) {
	var input createTaskTemplateInput
	if err := decodeJSON(r, &input); err != nil {
		writeError(w, http.StatusBadRequest, "invalid json")
		return
	}
	if strings.TrimSpace(input.Name) == "" || !validateTaskType(input.TaskType) {
		writeError(w, http.StatusBadRequest, "invalid task template payload")
		return
	}
	defaultPriority := 3
	if input.DefaultPriority != nil {
		defaultPriority = *input.DefaultPriority
	}
	isActive := true
	if input.IsActive != nil {
		isActive = *input.IsActive
	}
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	row := a.db.QueryRowContext(ctx, `INSERT INTO task_templates (name, task_type, default_priority, description, is_active, created_at, updated_at)
		VALUES ($1,$2,$3,$4,$5,now(),now())
		RETURNING id, name, task_type, default_priority, description, is_active`,
		input.Name, input.TaskType, defaultPriority, nullableString(input.Description), isActive)
	var out TaskTemplate
	if err := row.Scan(&out.ID, &out.Name, &out.TaskType, &out.DefaultPriority, &out.Description, &out.IsActive); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (a *App) handleListTaskTemplates(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	rows, err := a.db.QueryContext(ctx, `SELECT id, name, task_type, default_priority, description, is_active
		FROM task_templates ORDER BY task_type, default_priority`)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	defer rows.Close()
	out := make([]TaskTemplate, 0)
	for rows.Next() {
		var item TaskTemplate
		if err := rows.Scan(&item.ID, &item.Name, &item.TaskType, &item.DefaultPriority, &item.Description, &item.IsActive); err != nil {
			writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
		out = append(out, item)
	}
	writeJSON(w, http.StatusOK, out)
}

func (a *App) handleUpdateTaskTemplate(w http.ResponseWriter, r *http.Request) {
	templateID, err := strconv.Atoi(r.PathValue("template_id"))
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid template_id")
		return
	}
	var input updateTaskTemplateInput
	if err := decodeJSON(r, &input); err != nil {
		writeError(w, http.StatusBadRequest, "invalid json")
		return
	}
	if input.TaskType != nil && !validateTaskType(*input.TaskType) {
		writeError(w, http.StatusBadRequest, "invalid task_type")
		return
	}
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	row := a.db.QueryRowContext(ctx, `UPDATE task_templates SET
		name = COALESCE($2, name),
		task_type = COALESCE($3, task_type),
		default_priority = COALESCE($4, default_priority),
		description = COALESCE($5, description),
		is_active = COALESCE($6, is_active),
		updated_at = now()
		WHERE id = $1
		RETURNING id, name, task_type, default_priority, description, is_active`,
		templateID,
		nullableString(input.Name),
		nullableString(input.TaskType),
		input.DefaultPriority,
		nullableString(input.Description),
		input.IsActive,
	)
	var out TaskTemplate
	if err := row.Scan(&out.ID, &out.Name, &out.TaskType, &out.DefaultPriority, &out.Description, &out.IsActive); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			writeError(w, http.StatusNotFound, "template not found")
			return
		}
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (a *App) handleCreateTaskInstance(w http.ResponseWriter, r *http.Request) {
	var input createTaskInstanceInput
	if err := decodeJSON(r, &input); err != nil {
		writeError(w, http.StatusBadRequest, "invalid json")
		return
	}
	status := input.Status
	if status == "" {
		status = "todo"
	}
	if strings.TrimSpace(input.PeriodKey) == "" || !validateTaskStatus(status) {
		writeError(w, http.StatusBadRequest, "invalid task instance payload")
		return
	}
	priority := 3
	if input.Priority != nil {
		priority = *input.Priority
	}
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	if !a.rowExists(ctx, `SELECT 1 FROM accounts WHERE account_id = $1`, input.AccountID) {
		writeError(w, http.StatusNotFound, "account not found")
		return
	}
	if !a.rowExists(ctx, `SELECT 1 FROM task_templates WHERE id = $1`, input.TemplateID) {
		writeError(w, http.StatusNotFound, "template not found")
		return
	}
	var completedAt any
	if status == "done" {
		completedAt = a.now()
	}
	row := a.db.QueryRowContext(ctx, `INSERT INTO task_instances (account_id, template_id, period_key, status, start_at, deadline_at, priority, note, completed_at, created_at, updated_at)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,now(),now())
		RETURNING id, account_id, template_id, period_key, status, start_at, deadline_at, priority, note, completed_at`,
		input.AccountID, input.TemplateID, input.PeriodKey, status, input.StartAt, input.DeadlineAt, priority, nullableString(input.Note), completedAt,
	)
	item, err := scanTaskInstance(row)
	if err != nil {
		if isUniqueViolation(err) {
			writeError(w, http.StatusConflict, "task instance already exists for this period")
			return
		}
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, item)
}

func (a *App) rowExists(ctx context.Context, query string, args ...any) bool {
	var exists int
	err := a.db.QueryRowContext(ctx, query, args...).Scan(&exists)
	return err == nil
}

func scanTaskInstance(scanner interface{ Scan(dest ...any) error }) (TaskInstance, error) {
	var item TaskInstance
	var deadline sql.NullTime
	var note sql.NullString
	var completed sql.NullTime
	err := scanner.Scan(&item.ID, &item.AccountID, &item.TemplateID, &item.PeriodKey, &item.Status, &item.StartAt, &deadline, &item.Priority, &note, &completed)
	if err != nil {
		return TaskInstance{}, err
	}
	if deadline.Valid {
		value := deadline.Time
		item.DeadlineAt = &value
	}
	if note.Valid {
		value := note.String
		item.Note = &value
	}
	if completed.Valid {
		value := completed.Time
		item.CompletedAt = &value
	}
	return item, nil
}

func (a *App) handleListTaskInstances(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	query := `SELECT id, account_id, template_id, period_key, status, start_at, deadline_at, priority, note, completed_at FROM task_instances WHERE 1=1`
	args := []any{}
	index := 1
	if value := strings.TrimSpace(r.URL.Query().Get("account_id")); value != "" {
		accountID, err := strconv.Atoi(value)
		if err != nil {
			writeError(w, http.StatusBadRequest, "invalid account_id")
			return
		}
		query += fmt.Sprintf(` AND account_id = $%d`, index)
		args = append(args, accountID)
		index++
	}
	if value := strings.TrimSpace(r.URL.Query().Get("period_key")); value != "" {
		query += fmt.Sprintf(` AND period_key = $%d`, index)
		args = append(args, value)
		index++
	}
	query += ` ORDER BY priority, deadline_at`
	rows, err := a.db.QueryContext(ctx, query, args...)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	defer rows.Close()
	out := make([]TaskInstance, 0)
	for rows.Next() {
		item, err := scanTaskInstance(rows)
		if err != nil {
			writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
		out = append(out, item)
	}
	writeJSON(w, http.StatusOK, out)
}

func (a *App) handleUpdateTaskInstance(w http.ResponseWriter, r *http.Request) {
	instanceID, err := strconv.Atoi(r.PathValue("instance_id"))
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid instance_id")
		return
	}
	var input updateTaskInstanceInput
	if err := decodeJSON(r, &input); err != nil {
		writeError(w, http.StatusBadRequest, "invalid json")
		return
	}
	if input.Status != nil && !validateTaskStatus(*input.Status) {
		writeError(w, http.StatusBadRequest, "invalid status")
		return
	}
	var completedAt any
	if input.Status != nil {
		switch *input.Status {
		case "done":
			completedAt = a.now()
		case "todo", "skipped":
			completedAt = nil
		}
	}
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	row := a.db.QueryRowContext(ctx, `UPDATE task_instances SET
		status = COALESCE($2, status),
		deadline_at = COALESCE($3, deadline_at),
		priority = COALESCE($4, priority),
		note = COALESCE($5, note),
		completed_at = CASE
			WHEN $2 = 'done' THEN $6
			WHEN $2 IN ('todo', 'skipped') THEN NULL
			ELSE completed_at
		END,
		updated_at = now()
		WHERE id = $1
		RETURNING id, account_id, template_id, period_key, status, start_at, deadline_at, priority, note, completed_at`,
		instanceID, nullableString(input.Status), input.DeadlineAt, input.Priority, nullableString(input.Note), completedAt,
	)
	item, err := scanTaskInstance(row)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			writeError(w, http.StatusNotFound, "instance not found")
			return
		}
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, item)
}

func (a *App) handleGenerateTaskInstances(w http.ResponseWriter, r *http.Request) {
	var input generateTaskInstancesInput
	if err := decodeJSON(r, &input); err != nil {
		writeError(w, http.StatusBadRequest, "invalid json")
		return
	}
	if strings.TrimSpace(input.PeriodKey) == "" {
		writeError(w, http.StatusBadRequest, "period_key is required")
		return
	}
	if input.TaskType != nil && *input.TaskType != "" && !validateTaskType(*input.TaskType) {
		writeError(w, http.StatusBadRequest, "invalid task_type")
		return
	}
	ctx, cancel := a.withTimeout(r)
	defer cancel()
	accountRows, err := a.db.QueryContext(ctx, `SELECT account_id FROM accounts WHERE is_active IS TRUE`)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	accountIDs := make([]int, 0)
	for accountRows.Next() {
		var accountID int
		if err := accountRows.Scan(&accountID); err != nil {
			accountRows.Close()
			writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
		accountIDs = append(accountIDs, accountID)
	}
	accountRows.Close()
	templateQuery := `SELECT id, default_priority FROM task_templates WHERE is_active IS TRUE`
	args := []any{}
	if input.TaskType != nil && *input.TaskType != "" {
		templateQuery += ` AND task_type = $1`
		args = append(args, *input.TaskType)
	}
	rows, err := a.db.QueryContext(ctx, templateQuery, args...)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	type tpl struct {
		ID       int
		Priority int
	}
	templates := make([]tpl, 0)
	for rows.Next() {
		var item tpl
		if err := rows.Scan(&item.ID, &item.Priority); err != nil {
			rows.Close()
			writeError(w, http.StatusInternalServerError, err.Error())
			return
		}
		templates = append(templates, item)
	}
	rows.Close()

	created := 0
	for _, accountID := range accountIDs {
		for _, template := range templates {
			res, err := a.db.ExecContext(ctx, `INSERT INTO task_instances (account_id, template_id, period_key, status, start_at, deadline_at, priority, created_at, updated_at)
				VALUES ($1,$2,$3,'todo',$4,$5,$6,now(),now())
				ON CONFLICT (account_id, template_id, period_key) DO NOTHING`,
				accountID, template.ID, input.PeriodKey, input.StartAt, input.DeadlineAt, template.Priority,
			)
			if err != nil {
				writeError(w, http.StatusInternalServerError, err.Error())
				return
			}
			if affected, _ := res.RowsAffected(); affected > 0 {
				created++
			}
		}
	}
	writeJSON(w, http.StatusOK, map[string]int{"created": created})
}

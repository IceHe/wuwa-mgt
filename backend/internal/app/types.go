package app

import (
	"database/sql"
	"time"
)

type Account struct {
	AccountID            int
	ID                   string
	Abbr                 string
	Nickname             string
	PhoneNumber          sql.NullString
	Remark               sql.NullString
	Tacet                string
	FullWaveplateAt      time.Time
	FullWaveplateCrystal int
	IsActive             bool
	CreatedAt            time.Time
	UpdatedAt            time.Time
}

type AccountCheckin struct {
	AccountID  int
	StatusDate time.Time
	PeriodType string
	PeriodKey  string
	FlagKey    string
	Status     string
	IsDone     bool
}

type CleanupSession struct {
	ID          int
	AccountID   int
	BizDate     time.Time
	StartedAt   time.Time
	EndedAt     sql.NullTime
	DurationSec int
	Status      string
}

type TaskTemplate struct {
	ID              int     `json:"id"`
	Name            string  `json:"name"`
	TaskType        string  `json:"task_type"`
	DefaultPriority int     `json:"default_priority"`
	Description     *string `json:"description"`
	IsActive        bool    `json:"is_active"`
}

type TaskInstance struct {
	ID          int        `json:"id"`
	AccountID   int        `json:"account_id"`
	TemplateID  int        `json:"template_id"`
	PeriodKey   string     `json:"period_key"`
	Status      string     `json:"status"`
	StartAt     time.Time  `json:"start_at"`
	DeadlineAt  *time.Time `json:"deadline_at"`
	Priority    int        `json:"priority"`
	Note        *string    `json:"note"`
	CompletedAt *time.Time `json:"completed_at"`
}

type AccountOut struct {
	AccountID               int       `json:"account_id"`
	ID                      string    `json:"id"`
	PhoneNumber             *string   `json:"phone_number"`
	Nickname                string    `json:"nickname"`
	Abbr                    string    `json:"abbr"`
	Remark                  *string   `json:"remark"`
	Tacet                   string    `json:"tacet"`
	IsActive                bool      `json:"is_active"`
	CurrentWaveplate        int       `json:"current_waveplate"`
	CurrentWaveplateCrystal int       `json:"current_waveplate_crystal"`
	FullWaveplateAt         time.Time `json:"full_waveplate_at"`
	WaveplateFullInMinutes  int       `json:"waveplate_full_in_minutes"`
	CreatedAt               time.Time `json:"created_at"`
	UpdatedAt               time.Time `json:"updated_at"`
}

type EnergyOut struct {
	AccountID               int       `json:"account_id"`
	ID                      string    `json:"id"`
	CurrentWaveplate        int       `json:"current_waveplate"`
	CurrentWaveplateCrystal int       `json:"current_waveplate_crystal"`
	FullWaveplateAt         time.Time `json:"full_waveplate_at"`
	WaveplateFullInMinutes  int       `json:"waveplate_full_in_minutes"`
	ETAWaveplateFull        time.Time `json:"eta_waveplate_full"`
	WarnLevel               string    `json:"warn_level"`
}

type DashboardAccountOut struct {
	AccountID               int        `json:"account_id"`
	ID                      string     `json:"id"`
	Abbr                    string     `json:"abbr"`
	Nickname                string     `json:"nickname"`
	PhoneNumber             *string    `json:"phone_number"`
	Remark                  *string    `json:"remark"`
	Tacet                   string     `json:"tacet"`
	CurrentWaveplate        int        `json:"current_waveplate"`
	CurrentWaveplateCrystal int        `json:"current_waveplate_crystal"`
	WarnLevel               string     `json:"warn_level"`
	DailyTask               bool       `json:"daily_task"`
	DailyNest               bool       `json:"daily_nest"`
	WeeklyDoor              bool       `json:"weekly_door"`
	WeeklyBoss              bool       `json:"weekly_boss"`
	WeeklySynthesis         bool       `json:"weekly_synthesis"`
	DailyTaskStatus         string     `json:"daily_task_status"`
	DailyNestStatus         string     `json:"daily_nest_status"`
	WeeklyDoorStatus        string     `json:"weekly_door_status"`
	WeeklyBossStatus        string     `json:"weekly_boss_status"`
	WeeklySynthesisStatus   string     `json:"weekly_synthesis_status"`
	CleanupTodayTotalSec    int        `json:"cleanup_today_total_sec"`
	CleanupTodayPausedSec   int        `json:"cleanup_today_paused_sec"`
	CleanupRunning          bool       `json:"cleanup_running"`
	CleanupRunningStartedAt *time.Time `json:"cleanup_running_started_at"`
	WaveplateFullInMinutes  int        `json:"waveplate_full_in_minutes"`
	ETAWaveplateFull        time.Time  `json:"eta_waveplate_full"`
	TodoCount               int        `json:"todo_count"`
	DoneCount               int        `json:"done_count"`
}

type PeriodicAccountOut struct {
	AccountID                       int       `json:"account_id"`
	ID                              string    `json:"id"`
	Abbr                            string    `json:"abbr"`
	Nickname                        string    `json:"nickname"`
	PhoneNumber                     *string   `json:"phone_number"`
	CreatedAt                       time.Time `json:"created_at"`
	UpdatedAt                       time.Time `json:"updated_at"`
	VersionMatrixSoldier            bool      `json:"version_matrix_soldier"`
	VersionMatrixSoldierStatus      string    `json:"version_matrix_soldier_status"`
	VersionSmallCoralExchange       bool      `json:"version_small_coral_exchange"`
	VersionSmallCoralExchangeStatus string    `json:"version_small_coral_exchange_status"`
	VersionHologramChallenge        bool      `json:"version_hologram_challenge"`
	VersionHologramChallengeStatus  string    `json:"version_hologram_challenge_status"`
	VersionEchoTemplateAdjust       bool      `json:"version_echo_template_adjust"`
	VersionEchoTemplateAdjustStatus string    `json:"version_echo_template_adjust_status"`
	HVTrialCharacter                bool      `json:"hv_trial_character"`
	HVTrialCharacterStatus          string    `json:"hv_trial_character_status"`
	MonthlyTowerExchange            bool      `json:"monthly_tower_exchange"`
	MonthlyTowerExchangeStatus      string    `json:"monthly_tower_exchange_status"`
	FourWeekTower                   bool      `json:"four_week_tower"`
	FourWeekTowerStatus             string    `json:"four_week_tower_status"`
	FourWeekRuins                   bool      `json:"four_week_ruins"`
	FourWeekRuinsStatus             string    `json:"four_week_ruins_status"`
	RangeLahailuoCube               bool      `json:"range_lahailuo_cube"`
	RangeLahailuoCubeStatus         string    `json:"range_lahailuo_cube_status"`
	RangeMusicGame                  bool      `json:"range_music_game"`
	RangeMusicGameStatus            string    `json:"range_music_game_status"`
}

type CleanupTimerStateOut struct {
	AccountID        int        `json:"account_id"`
	ID               string     `json:"id"`
	Abbr             string     `json:"abbr"`
	Nickname         string     `json:"nickname"`
	BizDate          string     `json:"biz_date"`
	TodayTotalSec    int        `json:"today_total_sec"`
	TodayPausedSec   int        `json:"today_paused_sec"`
	Running          bool       `json:"running"`
	RunningStartedAt *time.Time `json:"running_started_at"`
	RunningSessionID *int       `json:"running_session_id"`
}

type CleanupWeeklyDayOut struct {
	BizDate     string `json:"biz_date"`
	DurationSec int    `json:"duration_sec"`
}

type CleanupWeeklyAccountOut struct {
	AccountID   int    `json:"account_id"`
	ID          string `json:"id"`
	Abbr        string `json:"abbr"`
	Nickname    string `json:"nickname"`
	DurationSec int    `json:"duration_sec"`
}

type CleanupWeeklySummaryOut struct {
	RangeStart       string                    `json:"range_start"`
	RangeEnd         string                    `json:"range_end"`
	TotalDurationSec int                       `json:"total_duration_sec"`
	Daily            []CleanupWeeklyDayOut     `json:"daily"`
	ByAccount        []CleanupWeeklyAccountOut `json:"by_account"`
}

type CleanupSessionOut struct {
	ID              int        `json:"id"`
	AccountID       int        `json:"account_id"`
	AccountGameID   string     `json:"account_game_id"`
	AccountAbbr     string     `json:"account_abbr"`
	AccountNickname string     `json:"account_nickname"`
	BizDate         string     `json:"biz_date"`
	StartedAt       time.Time  `json:"started_at"`
	EndedAt         *time.Time `json:"ended_at"`
	DurationSec     int        `json:"duration_sec"`
	Status          string     `json:"status"`
}

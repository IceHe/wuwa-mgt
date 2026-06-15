package app

import "testing"

func TestResolvePeriodWindowUsesUpdatedVersionAnchors(t *testing.T) {
	loc := mustLocation(t)
	app := &App{
		cfg: Config{
			CurrentFVStart: mustDateInLocation("", "2026-06-08", loc),
			CurrentHVStart: mustDateInLocation("", "2026-06-08", loc),
		},
	}
	day := mustDateInLocation("", "2026-06-08", loc)

	fvFlags := []string{
		"version_matrix_soldier",
		"version_small_coral_exchange",
		"version_hologram_challenge",
		"version_echo_template_adjust",
		"version_mainline",
		"temp_racing",
		"temp_roguelike",
	}

	for _, flagKey := range fvFlags {
		periodType, periodKey, start, end, err := app.resolvePeriodWindow(flagKey, day)
		if err != nil {
			t.Fatalf("resolvePeriodWindow(%q) returned error: %v", flagKey, err)
		}
		if periodType != "fv" {
			t.Fatalf("resolvePeriodWindow(%q) periodType = %q, want fv", flagKey, periodType)
		}
		if periodKey != "fv-2026-06-08" {
			t.Fatalf("resolvePeriodWindow(%q) periodKey = %q, want fv-2026-06-08", flagKey, periodKey)
		}
		if got := start.Format("2006-01-02"); got != "2026-06-08" {
			t.Fatalf("resolvePeriodWindow(%q) start = %s, want 2026-06-08", flagKey, got)
		}
		if got := end.Format("2006-01-02"); got != "2026-07-09" {
			t.Fatalf("resolvePeriodWindow(%q) end = %s, want 2026-07-09", flagKey, got)
		}
	}

	periodType, periodKey, start, end, err := app.resolvePeriodWindow("hv_trial_character", day)
	if err != nil {
		t.Fatalf("resolvePeriodWindow(hv_trial_character) returned error: %v", err)
	}
	if periodType != "hv" {
		t.Fatalf("resolvePeriodWindow(hv_trial_character) periodType = %q, want hv", periodType)
	}
	if periodKey != "hv-2026-06-08" {
		t.Fatalf("resolvePeriodWindow(hv_trial_character) periodKey = %q, want hv-2026-06-08", periodKey)
	}
	if got := start.Format("2006-01-02"); got != "2026-06-08" {
		t.Fatalf("resolvePeriodWindow(hv_trial_character) start = %s, want 2026-06-08", got)
	}
	if got := end.Format("2006-01-02"); got != "2026-06-23" {
		t.Fatalf("resolvePeriodWindow(hv_trial_character) end = %s, want 2026-06-23", got)
	}
}

func TestResolvePeriodWindowUsesDefaultLengthForNormalVersions(t *testing.T) {
	loc := mustLocation(t)
	app := &App{
		cfg: Config{
			CurrentFVStart: mustDateInLocation("", "2026-07-10", loc),
			CurrentHVStart: mustDateInLocation("", "2026-07-31", loc),
		},
	}
	day := mustDateInLocation("", "2026-07-31", loc)

	periodType, periodKey, start, end, err := app.resolvePeriodWindow("version_mainline", day)
	if err != nil {
		t.Fatalf("resolvePeriodWindow(version_mainline) returned error: %v", err)
	}
	if periodType != "fv" {
		t.Fatalf("resolvePeriodWindow(version_mainline) periodType = %q, want fv", periodType)
	}
	if periodKey != "fv-2026-07-10" {
		t.Fatalf("resolvePeriodWindow(version_mainline) periodKey = %q, want fv-2026-07-10", periodKey)
	}
	if got := start.Format("2006-01-02"); got != "2026-07-10" {
		t.Fatalf("resolvePeriodWindow(version_mainline) start = %s, want 2026-07-10", got)
	}
	if got := end.Format("2006-01-02"); got != "2026-08-20" {
		t.Fatalf("resolvePeriodWindow(version_mainline) end = %s, want 2026-08-20", got)
	}

	periodType, periodKey, start, end, err = app.resolvePeriodWindow("hv_trial_character", day)
	if err != nil {
		t.Fatalf("resolvePeriodWindow(hv_trial_character) returned error: %v", err)
	}
	if periodType != "hv" {
		t.Fatalf("resolvePeriodWindow(hv_trial_character) periodType = %q, want hv", periodType)
	}
	if periodKey != "hv-2026-07-31" {
		t.Fatalf("resolvePeriodWindow(hv_trial_character) periodKey = %q, want hv-2026-07-31", periodKey)
	}
	if got := start.Format("2006-01-02"); got != "2026-07-31" {
		t.Fatalf("resolvePeriodWindow(hv_trial_character) start = %s, want 2026-07-31", got)
	}
	if got := end.Format("2006-01-02"); got != "2026-08-20" {
		t.Fatalf("resolvePeriodWindow(hv_trial_character) end = %s, want 2026-08-20", got)
	}
}

func TestResolvePeriodWindowSupportsDailySmallRun(t *testing.T) {
	loc := mustLocation(t)
	app := &App{}
	day := mustDateInLocation("", "2026-05-01", loc)

	periodType, periodKey, start, end, err := app.resolvePeriodWindow("daily_small_run", day)
	if err != nil {
		t.Fatalf("resolvePeriodWindow(daily_small_run) returned error: %v", err)
	}
	if periodType != "daily" {
		t.Fatalf("resolvePeriodWindow(daily_small_run) periodType = %q, want daily", periodType)
	}
	if periodKey != "2026-05-01" {
		t.Fatalf("resolvePeriodWindow(daily_small_run) periodKey = %q, want 2026-05-01", periodKey)
	}
	if got := start.Format("2006-01-02"); got != "2026-05-01" {
		t.Fatalf("resolvePeriodWindow(daily_small_run) start = %s, want 2026-05-01", got)
	}
	if got := end.Format("2006-01-02"); got != "2026-05-01" {
		t.Fatalf("resolvePeriodWindow(daily_small_run) end = %s, want 2026-05-01", got)
	}
}

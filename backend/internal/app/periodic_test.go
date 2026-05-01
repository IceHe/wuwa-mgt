package app

import "testing"

func TestResolvePeriodWindowUsesUpdatedVersionAnchors(t *testing.T) {
	loc := mustLocation(t)
	app := &App{
		cfg: Config{
			CurrentFVStart: mustDateInLocation("", "2026-04-30", loc),
			CurrentHVStart: mustDateInLocation("", "2026-04-30", loc),
		},
	}
	day := mustDateInLocation("", "2026-05-01", loc)

	fvFlags := []string{
		"version_matrix_soldier",
		"version_small_coral_exchange",
		"version_hologram_challenge",
		"version_echo_template_adjust",
		"v33_gifts_of_grand_celebration",
		"v33_bountiful_waves",
		"v33_star_bouncing",
		"v33_cubie_derby_championship",
	}

	for _, flagKey := range fvFlags {
		periodType, periodKey, start, end, err := app.resolvePeriodWindow(flagKey, day)
		if err != nil {
			t.Fatalf("resolvePeriodWindow(%q) returned error: %v", flagKey, err)
		}
		if periodType != "fv" {
			t.Fatalf("resolvePeriodWindow(%q) periodType = %q, want fv", flagKey, periodType)
		}
		if periodKey != "fv-2026-04-30" {
			t.Fatalf("resolvePeriodWindow(%q) periodKey = %q, want fv-2026-04-30", flagKey, periodKey)
		}
		if got := start.Format("2006-01-02"); got != "2026-04-30" {
			t.Fatalf("resolvePeriodWindow(%q) start = %s, want 2026-04-30", flagKey, got)
		}
		if got := end.Format("2006-01-02"); got != "2026-06-10" {
			t.Fatalf("resolvePeriodWindow(%q) end = %s, want 2026-06-10", flagKey, got)
		}
	}

	periodType, periodKey, start, end, err := app.resolvePeriodWindow("hv_trial_character", day)
	if err != nil {
		t.Fatalf("resolvePeriodWindow(hv_trial_character) returned error: %v", err)
	}
	if periodType != "hv" {
		t.Fatalf("resolvePeriodWindow(hv_trial_character) periodType = %q, want hv", periodType)
	}
	if periodKey != "hv-2026-04-30" {
		t.Fatalf("resolvePeriodWindow(hv_trial_character) periodKey = %q, want hv-2026-04-30", periodKey)
	}
	if got := start.Format("2006-01-02"); got != "2026-04-30" {
		t.Fatalf("resolvePeriodWindow(hv_trial_character) start = %s, want 2026-04-30", got)
	}
	if got := end.Format("2006-01-02"); got != "2026-05-20" {
		t.Fatalf("resolvePeriodWindow(hv_trial_character) end = %s, want 2026-05-20", got)
	}
}

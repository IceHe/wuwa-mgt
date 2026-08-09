package app

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestDashboardEnergyRevisionEndpointReturnsCurrentValue(t *testing.T) {
	app := &App{}
	app.energyRevision.Store(7)

	req := httptest.NewRequest(http.MethodGet, "/dashboard/energy-revision", nil)
	rr := httptest.NewRecorder()

	app.handleDashboardEnergyRevision(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", rr.Code, http.StatusOK)
	}
	var out DashboardEnergyRevisionOut
	if err := json.Unmarshal(rr.Body.Bytes(), &out); err != nil {
		t.Fatalf("unmarshal response: %v", err)
	}
	if out.Revision != 7 {
		t.Fatalf("revision = %d, want 7", out.Revision)
	}
}

func TestNotifyDashboardEnergyRevisionUsesTokenWhenConfigured(t *testing.T) {
	app := &App{cfg: Config{EnergyNotifyToken: "secret"}}

	req := httptest.NewRequest(http.MethodPost, "/internal/dashboard/energy-revision", nil)
	req.RemoteAddr = "203.0.113.10:1234"
	rr := httptest.NewRecorder()
	app.handleNotifyDashboardEnergyRevision(rr, req)

	if rr.Code != http.StatusUnauthorized {
		t.Fatalf("unauthenticated status = %d, want %d", rr.Code, http.StatusUnauthorized)
	}
	if got := app.energyRevisionValue(); got != 0 {
		t.Fatalf("revision after rejected request = %d, want 0", got)
	}

	req = httptest.NewRequest(http.MethodPost, "/internal/dashboard/energy-revision", nil)
	req.RemoteAddr = "203.0.113.10:1234"
	req.Header.Set("X-Notify-Token", "secret")
	rr = httptest.NewRecorder()
	app.handleNotifyDashboardEnergyRevision(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("authorized status = %d, want %d", rr.Code, http.StatusOK)
	}
	var out DashboardEnergyRevisionOut
	if err := json.Unmarshal(rr.Body.Bytes(), &out); err != nil {
		t.Fatalf("unmarshal response: %v", err)
	}
	if out.Revision != 1 {
		t.Fatalf("revision = %d, want 1", out.Revision)
	}
}

func TestNotifyDashboardEnergyRevisionAllowsLoopbackWithoutToken(t *testing.T) {
	app := &App{}

	req := httptest.NewRequest(http.MethodPost, "/internal/dashboard/energy-revision", nil)
	req.RemoteAddr = "127.0.0.1:4567"
	rr := httptest.NewRecorder()

	app.handleNotifyDashboardEnergyRevision(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("loopback status = %d, want %d", rr.Code, http.StatusOK)
	}
	if got := app.energyRevisionValue(); got != 1 {
		t.Fatalf("revision = %d, want 1", got)
	}
}

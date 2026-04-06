package app

import (
	"testing"
	"time"
)

func mustLocation(t *testing.T) *time.Location {
	t.Helper()
	loc, err := time.LoadLocation("Asia/Shanghai")
	if err != nil {
		t.Fatalf("load location: %v", err)
	}
	return loc
}

func TestSpendBelowCapPreservesNextRecoverPhase(t *testing.T) {
	loc := mustLocation(t)
	now := time.Date(2026, 3, 31, 12, 0, 0, 0, loc)
	fullAt := now.Add(5*time.Hour + 56*time.Minute)

	currentWP, currentCrystal := currentResourcesFromFullTime(fullAt, 0, now)
	if currentWP != 180 || currentCrystal != 0 {
		t.Fatalf("unexpected current resources: %d, %d", currentWP, currentCrystal)
	}

	nextWP, nextCrystal := spendResources(currentWP, currentCrystal, 60)
	nextRecover := secondsToNextWaveplateRecoverFromFullTime(fullAt, now)
	shiftedFullAt := fullTimeFromCurrentWaveplateAndNextRecover(nextWP, nextRecover, now)

	if nextWP != 120 || nextCrystal != 0 {
		t.Fatalf("unexpected next resources: %d, %d", nextWP, nextCrystal)
	}
	if nextRecover != 120 {
		t.Fatalf("unexpected next recover: %d", nextRecover)
	}
	if secondsToNextWaveplateRecoverFromFullTime(shiftedFullAt, now) != 120 {
		t.Fatalf("recover phase was not preserved")
	}
}

func TestApplyEnergySetCrystalOnlyBelowCapPreservesFullTime(t *testing.T) {
	loc := mustLocation(t)
	now := time.Date(2026, 3, 31, 12, 0, 0, 0, loc)
	fullAt := now.Add(5*time.Hour + 56*time.Minute)
	account := Account{
		AccountID:            1,
		ID:                   "test_id",
		Abbr:                 "t",
		Nickname:             "test",
		FullWaveplateAt:      fullAt,
		FullWaveplateCrystal: 8,
		IsActive:             true,
	}
	currentWP, _ := currentResourcesFromFullTime(account.FullWaveplateAt, account.FullWaveplateCrystal, now)
	beforeNext := secondsToNextWaveplateRecoverFromFullTime(account.FullWaveplateAt, now)

	app := &App{cfg: Config{Location: loc}}
	payload := energySetInput{
		CurrentWaveplate:        &currentWP,
		CurrentWaveplateCrystal: intPtr(33),
	}
	if err := app.applyEnergySet(&account, payload, now); err != nil {
		t.Fatalf("applyEnergySet failed: %v", err)
	}

	if !account.FullWaveplateAt.Equal(fullAt) {
		t.Fatalf("full time changed: %v != %v", account.FullWaveplateAt, fullAt)
	}
	if secondsToNextWaveplateRecoverFromFullTime(account.FullWaveplateAt, now) != beforeNext {
		t.Fatalf("recover phase changed")
	}
	afterWP, afterCrystal := currentResourcesFromFullTime(account.FullWaveplateAt, account.FullWaveplateCrystal, now)
	if afterWP != currentWP || afterCrystal != 33 {
		t.Fatalf("unexpected resources after update: %d, %d", afterWP, afterCrystal)
	}
}

func intPtr(value int) *int {
	return &value
}

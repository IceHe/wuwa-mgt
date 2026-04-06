package app

import (
	"errors"
	"fmt"
	"math"
	"time"
)

const (
	WaveplateCap            = 240
	WaveplateRecoverSeconds = 6 * 60
	WaveplateCrystalCap     = 480
	CrystalRecoverSeconds   = 12 * 60
	fourWeekDays            = 28
)

func clampWaveplate(value int) int {
	if value < 0 {
		return 0
	}
	if value > WaveplateCap {
		return WaveplateCap
	}
	return value
}

func clampWaveplateCrystal(value int) int {
	if value < 0 {
		return 0
	}
	if value > WaveplateCrystalCap {
		return WaveplateCrystalCap
	}
	return value
}

func normalizeResources(waveplate, crystal int) (int, int) {
	wp := waveplate
	if wp < 0 {
		wp = 0
	}
	cr := crystal
	if cr < 0 {
		cr = 0
	}
	if wp > WaveplateCap {
		cr += wp - WaveplateCap
		wp = WaveplateCap
	}
	return wp, clampWaveplateCrystal(cr)
}

func secondsToWaveplateFullFromCurrent(waveplate int) int {
	wp := clampWaveplate(waveplate)
	if wp >= WaveplateCap {
		return 0
	}
	return (WaveplateCap - wp) * WaveplateRecoverSeconds
}

func secondsToWaveplateFullFromFullTime(fullAt, now time.Time) int {
	seconds := int(fullAt.Sub(now).Seconds())
	if seconds < 0 {
		return 0
	}
	return seconds
}

func secondsToNextWaveplateRecoverFromFullTime(fullAt, now time.Time) int {
	delta := secondsToWaveplateFullFromFullTime(fullAt, now)
	next := delta % WaveplateRecoverSeconds
	if next == 0 {
		return WaveplateRecoverSeconds
	}
	return next
}

func currentResourcesFromFullTime(fullAt time.Time, fullCrystal int, now time.Time) (int, int) {
	baseCrystal := clampWaveplateCrystal(fullCrystal)
	deltaSeconds := int(fullAt.Sub(now).Seconds())
	if deltaSeconds > 0 {
		missing := minInt(WaveplateCap, int(math.Ceil(float64(deltaSeconds)/float64(WaveplateRecoverSeconds))))
		return WaveplateCap - missing, baseCrystal
	}

	crystalGained := maxInt(0, int(now.Sub(fullAt).Seconds())/CrystalRecoverSeconds)
	return WaveplateCap, clampWaveplateCrystal(baseCrystal + crystalGained)
}

func fullTimeFromCurrentResources(waveplate, crystal int, now time.Time) (time.Time, int) {
	wp, cr := normalizeResources(waveplate, crystal)
	return now.Add(time.Duration(secondsToWaveplateFullFromCurrent(wp)) * time.Second), cr
}

func fullTimeFromCurrentWaveplateAndNextRecover(waveplate, nextRecoverSeconds int, now time.Time) time.Time {
	wp := clampWaveplate(waveplate)
	if wp >= WaveplateCap {
		return now
	}
	missing := WaveplateCap - wp
	next := maxInt(1, minInt(WaveplateRecoverSeconds, nextRecoverSeconds))
	totalSeconds := ((missing - 1) * WaveplateRecoverSeconds) + next
	return now.Add(time.Duration(totalSeconds) * time.Second)
}

func fullCrystalFromCurrentCrystal(currentCrystal int, fullAt, now time.Time) (int, error) {
	cr := clampWaveplateCrystal(currentCrystal)
	if fullAt.After(now) {
		return cr, nil
	}
	crystalGained := maxInt(0, int(now.Sub(fullAt).Seconds())/CrystalRecoverSeconds)
	base := cr - crystalGained
	if base < 0 {
		return 0, errors.New("current_waveplate_crystal is too small for the selected full_waveplate_at")
	}
	return clampWaveplateCrystal(base), nil
}

func spendResources(waveplate, crystal, cost int) (int, int) {
	wp, cr := normalizeResources(waveplate, crystal)
	remain := maxInt(0, cost)
	useWP := minInt(wp, remain)
	wp -= useWP
	remain -= useWP
	if remain > 0 {
		cr = maxInt(0, cr-remain)
	}
	return wp, cr
}

func addResources(waveplate, crystal, amount int) (int, int) {
	wp, cr := normalizeResources(waveplate, crystal)
	increase := maxInt(0, amount)
	wp += increase
	if wp > WaveplateCap {
		cr = minInt(WaveplateCrystalCap, cr+(wp-WaveplateCap))
		wp = WaveplateCap
	}
	return wp, cr
}

func validateFullWaveplateAt(now, fullAt time.Time) error {
	deltaSeconds := int(fullAt.Sub(now).Seconds())
	maxSeconds := secondsToWaveplateFullFromCurrent(0)
	if deltaSeconds > maxSeconds {
		return fmt.Errorf("full_waveplate_at too far in future (max %d seconds)", maxSeconds)
	}
	return nil
}

func warnLevel(waveplate int) string {
	wp := clampWaveplate(waveplate)
	if wp >= 235 {
		return "danger"
	}
	if wp >= 220 {
		return "warning"
	}
	return "normal"
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}

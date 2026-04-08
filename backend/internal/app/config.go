package app

import (
	"bufio"
	"errors"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	DatabaseURL                string
	AppTZ                      string
	ResetHour                  int
	AuthBaseURL                string
	AuthRequiredPermission     string
	AuthValidateTimeoutSeconds float64
	FourWeekTowerAnchor        time.Time
	FourWeekRuinsAnchor        time.Time
	CurrentFVStart             time.Time
	CurrentHVStart             time.Time
	PlateRangeStart            time.Time
	PlateRangeEnd              time.Time
	MusicGameRangeStart        time.Time
	MusicGameRangeEnd          time.Time
	Host                       string
	Port                       int
	Location                   *time.Location
}

func LoadConfig(root string) (Config, error) {
	if err := loadDotEnv(filepath.Join(root, ".env")); err != nil {
		return Config{}, err
	}
	if err := loadDotEnv(filepath.Join(root, "backend", ".env")); err != nil {
		return Config{}, err
	}

	appTZ := getenv("APP_TZ", "Asia/Shanghai")
	loc, err := time.LoadLocation(appTZ)
	if err != nil {
		return Config{}, err
	}

	resetHour, err := strconv.Atoi(getenv("RESET_HOUR", "4"))
	if err != nil {
		return Config{}, err
	}
	if resetHour < 0 || resetHour > 23 {
		return Config{}, errors.New("RESET_HOUR must be 0..23")
	}

	port, err := strconv.Atoi(getenv("PORT", "8765"))
	if err != nil {
		return Config{}, err
	}

	cfg := Config{
		DatabaseURL:                normalizeDatabaseURL(getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")),
		AppTZ:                      appTZ,
		ResetHour:                  resetHour,
		AuthBaseURL:                strings.TrimRight(getenv("AUTH_BASE_URL", "http://127.0.0.1:8080"), "/"),
		AuthRequiredPermission:     getenv("AUTH_REQUIRED_PERMISSION", "manage"),
		AuthValidateTimeoutSeconds: getenvFloat("AUTH_VALIDATE_TIMEOUT_SECONDS", 3),
		FourWeekTowerAnchor:        mustDateInLocation("FOUR_WEEK_TOWER_ANCHOR", "2026-03-30", loc),
		FourWeekRuinsAnchor:        mustDateInLocation("FOUR_WEEK_RUINS_ANCHOR", "2026-03-16", loc),
		CurrentFVStart:             mustDateInLocation("CURRENT_FV_START", "2026-03-19", loc),
		CurrentHVStart:             mustDateInLocation("CURRENT_HV_START", "2026-03-19", loc),
		PlateRangeStart:            mustDateInLocation("", "2026-03-26", loc),
		PlateRangeEnd:              mustDateInLocation("", "2026-04-13", loc),
		MusicGameRangeStart:        mustDateInLocation("", "2026-03-19", loc),
		MusicGameRangeEnd:          mustDateInLocation("", "2026-04-29", loc),
		Host:                       getenv("HOST", "0.0.0.0"),
		Port:                       port,
		Location:                   loc,
	}

	return cfg, nil
}

func loadDotEnv(path string) error {
	file, err := os.Open(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil
	}
	if err != nil {
		return err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		key, value, found := strings.Cut(line, "=")
		if !found {
			continue
		}
		key = strings.TrimSpace(key)
		if key == "" {
			continue
		}
		if _, exists := os.LookupEnv(key); exists {
			continue
		}
		os.Setenv(key, strings.TrimSpace(value))
	}
	return scanner.Err()
}

func getenv(key, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
}

func getenvFloat(key string, fallback float64) float64 {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	parsed, err := strconv.ParseFloat(value, 64)
	if err != nil {
		return fallback
	}
	return parsed
}

func mustDateInLocation(key, fallback string, loc *time.Location) time.Time {
	value := fallback
	if key != "" {
		value = getenv(key, fallback)
	}
	parsed, err := time.ParseInLocation("2006-01-02", value, loc)
	if err != nil {
		panic(err)
	}
	return parsed
}

func normalizeDatabaseURL(url string) string {
	return strings.Replace(url, "postgresql+psycopg://", "postgresql://", 1)
}

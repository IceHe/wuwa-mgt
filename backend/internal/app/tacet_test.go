package app

import "testing"

func TestValidateTacetAllowsDashboardOptions(t *testing.T) {
	values := []string{
		"",
		"爱弥斯",
		"西格莉卡",
		"旧暗",
		"旧雷",
		"达妮娅",
		"绯雪",
		"洛瑟拉",
	}

	for _, value := range values {
		if err := validateTacet(value); err != nil {
			t.Fatalf("validateTacet(%q) returned error: %v", value, err)
		}
	}
}

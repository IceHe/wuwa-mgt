package app

import "testing"

func TestValidateTacetAllowsFreeText(t *testing.T) {
	values := []string{
		"",
		"爱弥斯",
		"西格莉卡",
		"新无音区",
		"自定义 Tacet 123",
	}

	for _, value := range values {
		if err := validateTacet(value); err != nil {
			t.Fatalf("validateTacet(%q) returned error: %v", value, err)
		}
	}
}

func TestValidateTacetRejectsOverlongText(t *testing.T) {
	value := ""
	for range 129 {
		value += "a"
	}

	if err := validateTacet(value); err == nil {
		t.Fatal("validateTacet accepted overlong text")
	}
}

func TestNormalizeTacetTrimsSpace(t *testing.T) {
	if got := normalizeTacet("  新无音区  "); got != "新无音区" {
		t.Fatalf("normalizeTacet returned %q, want 新无音区", got)
	}
}

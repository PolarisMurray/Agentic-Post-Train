package dotenv

import (
	"os"
	"path/filepath"
	"testing"
)

func TestParseLine(t *testing.T) {
	cases := []struct {
		line, key, value string
		ok               bool
	}{
		{"KEY=value", "KEY", "value", true},
		{"export KEY=value", "KEY", "value", true},
		{`KEY="quoted # not a comment"`, "KEY", "quoted # not a comment", true},
		{"KEY='single'", "KEY", "single", true},
		{"KEY=value # comment", "KEY", "value", true},
		{"KEY=", "KEY", "", true},
		{"# comment", "", "", false},
		{"", "", "", false},
		{"no equals sign", "", "", false},
	}
	for _, c := range cases {
		key, value, ok := parseLine(c.line)
		if key != c.key || value != c.value || ok != c.ok {
			t.Errorf("parseLine(%q) = (%q, %q, %v), want (%q, %q, %v)", c.line, key, value, ok, c.key, c.value, c.ok)
		}
	}
}

func TestLoadFileKeepsExistingVariables(t *testing.T) {
	path := filepath.Join(t.TempDir(), ".env")
	if err := os.WriteFile(path, []byte("DOTENV_TEST_NEW=from-file\nDOTENV_TEST_SET=from-file\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	t.Setenv("DOTENV_TEST_SET", "from-shell")
	t.Setenv("DOTENV_TEST_NEW", "")
	os.Unsetenv("DOTENV_TEST_NEW")

	if err := LoadFile(path); err != nil {
		t.Fatal(err)
	}
	if got := os.Getenv("DOTENV_TEST_NEW"); got != "from-file" {
		t.Errorf("DOTENV_TEST_NEW = %q, want from-file", got)
	}
	if got := os.Getenv("DOTENV_TEST_SET"); got != "from-shell" {
		t.Errorf("DOTENV_TEST_SET = %q, the shell value should win", got)
	}
}

func TestFindStopsAtRepoRoot(t *testing.T) {
	outer := t.TempDir()
	repo := filepath.Join(outer, "repo")
	sub := filepath.Join(repo, "a", "b")
	if err := os.MkdirAll(sub, 0o755); err != nil {
		t.Fatal(err)
	}
	os.WriteFile(filepath.Join(outer, ".env"), []byte("X=1"), 0o600)
	if got := find(sub); got != filepath.Join(outer, ".env") {
		t.Errorf("without a repo root, find = %q", got)
	}

	os.Mkdir(filepath.Join(repo, ".git"), 0o755)
	if got := find(sub); got != "" {
		t.Errorf("find crossed the repo root: %q", got)
	}
	os.WriteFile(filepath.Join(repo, ".env"), []byte("X=1"), 0o600)
	if got := find(sub); got != filepath.Join(repo, ".env") {
		t.Errorf("find = %q, want the repo .env", got)
	}
}

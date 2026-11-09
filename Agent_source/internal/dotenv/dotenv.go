// Package dotenv loads KEY=VALUE pairs from a .env file into the environment,
// so API keys can live in a git-ignored file instead of the shell profile.
package dotenv

import (
	"bufio"
	"os"
	"path/filepath"
	"strings"
)

// Load finds the nearest .env file, starting at the current directory and
// walking up to the git repository root, and sets every variable that is not
// already set. It returns the path it loaded, or "" if none was found.
func Load() (string, error) {
	dir, err := os.Getwd()
	if err != nil {
		return "", err
	}
	path := find(dir)
	if path == "" {
		return "", nil
	}
	return path, LoadFile(path)
}

func find(dir string) string {
	for {
		candidate := filepath.Join(dir, ".env")
		if info, err := os.Stat(candidate); err == nil && !info.IsDir() {
			return candidate
		}
		if _, err := os.Stat(filepath.Join(dir, ".git")); err == nil {
			return "" // stop at the repository root
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			return ""
		}
		dir = parent
	}
}

// LoadFile sets the variables from path. Existing environment variables win.
func LoadFile(path string) error {
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		key, value, ok := parseLine(scanner.Text())
		if !ok {
			continue
		}
		if _, exists := os.LookupEnv(key); !exists {
			os.Setenv(key, value)
		}
	}
	return scanner.Err()
}

func parseLine(line string) (key, value string, ok bool) {
	line = strings.TrimSpace(line)
	if line == "" || strings.HasPrefix(line, "#") {
		return "", "", false
	}
	line = strings.TrimPrefix(line, "export ")
	key, value, ok = strings.Cut(line, "=")
	key = strings.TrimSpace(key)
	if !ok || key == "" {
		return "", "", false
	}
	value = strings.TrimSpace(value)
	if len(value) >= 2 && (value[0] == '"' || value[0] == '\'') && value[len(value)-1] == value[0] {
		value = value[1 : len(value)-1]
	} else if i := strings.Index(value, " #"); i >= 0 {
		value = strings.TrimSpace(value[:i])
	}
	return key, value, true
}

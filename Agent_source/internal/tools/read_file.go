package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

const maxReadBytes = 64 * 1024

type ReadFile struct {
	// Root is the workspace directory relative paths are resolved against.
	// It does not stop absolute paths or "../" yet; confinement comes with
	// the write and shell tools.
	Root string
}

func (t *ReadFile) Name() string { return "read_file" }

func (t *ReadFile) Description() string {
	return "Read a text file and return its content. Paths are relative to the workspace root."
}

func (t *ReadFile) Parameters() json.RawMessage {
	return json.RawMessage(`{
  "type": "object",
  "properties": {
    "path": {"type": "string", "description": "File path relative to the workspace root."}
  },
  "required": ["path"]
}`)
}

func (t *ReadFile) Run(ctx context.Context, raw json.RawMessage) (string, error) {
	var args struct {
		Path string `json:"path"`
	}
	if err := json.Unmarshal(raw, &args); err != nil {
		return "", fmt.Errorf("invalid arguments: %w", err)
	}
	if args.Path == "" {
		return "", fmt.Errorf("path is empty")
	}
	path := args.Path
	if !filepath.IsAbs(path) {
		path = filepath.Join(t.Root, path)
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	if len(data) > maxReadBytes {
		return string(data[:maxReadBytes]) + fmt.Sprintf("\n... [truncated: file is %d bytes]", len(data)), nil
	}
	return string(data), nil
}

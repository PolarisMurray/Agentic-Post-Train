package loop

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/PolarisMurray/Agentic-Post-Train/Agent_source/internal/llm"
	"github.com/PolarisMurray/Agentic-Post-Train/Agent_source/internal/tools"
)

// scriptedModel returns canned responses in order and records every request.
type scriptedModel struct {
	responses []llm.Message
	requests  []llm.ChatRequest
}

func (m *scriptedModel) Chat(ctx context.Context, req llm.ChatRequest) (*llm.ChatResponse, error) {
	m.requests = append(m.requests, req)
	if len(m.responses) == 0 {
		return nil, errors.New("script exhausted")
	}
	msg := m.responses[0]
	m.responses = m.responses[1:]
	msg.Role = llm.RoleAssistant
	return &llm.ChatResponse{Message: msg, Usage: llm.Usage{TotalTokens: 10}}, nil
}

func call(id, name, args string) llm.ToolCall {
	return llm.ToolCall{ID: id, Type: "function", Function: llm.FunctionCall{Name: name, Arguments: args}}
}

func TestRunFeedsToolResultsBack(t *testing.T) {
	root := t.TempDir()
	if err := os.WriteFile(filepath.Join(root, "a.txt"), []byte("hello"), 0o644); err != nil {
		t.Fatal(err)
	}
	model := &scriptedModel{responses: []llm.Message{
		{ToolCalls: []llm.ToolCall{call("c1", "read_file", `{"path":"a.txt"}`)}},
		{ToolCalls: []llm.ToolCall{call("c2", "read_file", `{"path":"missing.txt"}`)}},
		{Content: "the file says hello"},
	}}
	agent := &Agent{
		Model:        model,
		ModelName:    "m",
		Tools:        tools.NewRegistry(&tools.ReadFile{Root: root}),
		SystemPrompt: "sys",
	}

	res, err := agent.Run(context.Background(), "what is in a.txt?")
	if err != nil {
		t.Fatal(err)
	}
	if res.Final != "the file says hello" || res.Steps != 3 || res.Usage.TotalTokens != 30 {
		t.Errorf("unexpected result: final=%q steps=%d usage=%+v", res.Final, res.Steps, res.Usage)
	}

	// system, user, assistant, tool, assistant, tool, assistant
	roles := []llm.Role{"system", "user", "assistant", "tool", "assistant", "tool", "assistant"}
	if len(res.Messages) != len(roles) {
		t.Fatalf("got %d messages, want %d", len(res.Messages), len(roles))
	}
	for i, r := range roles {
		if res.Messages[i].Role != r {
			t.Errorf("message %d role = %s, want %s", i, res.Messages[i].Role, r)
		}
	}
	if m := res.Messages[3]; m.ToolCallID != "c1" || m.Content != "hello" {
		t.Errorf("read_file result = %+v", m)
	}
	if m := res.Messages[5]; m.ToolCallID != "c2" || !strings.HasPrefix(m.Content, "Error: ") {
		t.Errorf("tool errors should go back to the model, got %+v", m)
	}
	// The second request must carry the first round's tool result.
	if got := len(model.requests[1].Messages); got != 4 {
		t.Errorf("second request has %d messages, want 4", got)
	}
	if len(model.requests[0].Tools) != 1 || model.requests[0].Model != "m" {
		t.Errorf("request missing tools/model: %+v", model.requests[0])
	}
}

func TestRunStopsAtMaxSteps(t *testing.T) {
	again := llm.Message{ToolCalls: []llm.ToolCall{call("c", "read_file", `{"path":"x"}`)}}
	model := &scriptedModel{responses: []llm.Message{again, again, again}}
	agent := &Agent{
		Model:    model,
		Tools:    tools.NewRegistry(&tools.ReadFile{Root: t.TempDir()}),
		MaxSteps: 2,
	}

	res, err := agent.Run(context.Background(), "task")
	if !errors.Is(err, ErrMaxSteps) {
		t.Fatalf("err = %v, want ErrMaxSteps", err)
	}
	if res.Steps != 2 || len(model.requests) != 2 {
		t.Errorf("steps=%d requests=%d, want 2", res.Steps, len(model.requests))
	}
}

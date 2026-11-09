// Package loop implements the agent loop:
// call the model -> run the tool calls it asks for -> append the results -> repeat,
// until the model answers without tool calls or the step budget runs out.
package loop

import (
	"context"
	"errors"
	"fmt"
	"io"
	"strings"

	"github.com/PolarisMurray/Agentic-Post-Train/Agent_source/internal/llm"
	"github.com/PolarisMurray/Agentic-Post-Train/Agent_source/internal/tools"
)

var ErrMaxSteps = errors.New("agent stopped: step limit reached before the task finished")

type Agent struct {
	Model        llm.ChatModel
	ModelName    string
	Tools        *tools.Registry
	SystemPrompt string
	MaxSteps     int       // model calls per run; 0 means 30
	Log          io.Writer // progress output; nil means silent
}

type Result struct {
	// Final is the model's last answer (the message without tool calls).
	Final string
	// Messages is the full conversation, including the system prompt.
	Messages []llm.Message
	Steps    int
	Usage    llm.Usage
}

func (a *Agent) Run(ctx context.Context, task string) (*Result, error) {
	maxSteps := a.MaxSteps
	if maxSteps <= 0 {
		maxSteps = 30
	}
	res := &Result{}
	if a.SystemPrompt != "" {
		res.Messages = append(res.Messages, llm.Message{Role: llm.RoleSystem, Content: a.SystemPrompt})
	}
	res.Messages = append(res.Messages, llm.Message{Role: llm.RoleUser, Content: task})

	for step := 1; step <= maxSteps; step++ {
		res.Steps = step
		resp, err := a.Model.Chat(ctx, llm.ChatRequest{
			Model:    a.ModelName,
			Messages: res.Messages,
			Tools:    a.Tools.Specs(),
		})
		if err != nil {
			return res, fmt.Errorf("step %d: %w", step, err)
		}
		res.Usage.PromptTokens += resp.Usage.PromptTokens
		res.Usage.CompletionTokens += resp.Usage.CompletionTokens
		res.Usage.TotalTokens += resp.Usage.TotalTokens

		msg := resp.Message
		res.Messages = append(res.Messages, msg)
		if len(msg.ToolCalls) == 0 {
			res.Final = msg.Content
			return res, nil
		}

		// Tool calls run in order: a later call often depends on an earlier one.
		for _, call := range msg.ToolCalls {
			a.logf("[%d] > %s %s\n", step, call.Function.Name, call.Function.Arguments)
			output, err := a.Tools.Call(ctx, call.Function.Name, call.Function.Arguments)
			if err != nil {
				output = "Error: " + err.Error()
			}
			a.logf("    %s\n", preview(output, 200))
			res.Messages = append(res.Messages, llm.Message{
				Role:       llm.RoleTool,
				ToolCallID: call.ID,
				Content:    output,
			})
		}
	}
	return res, ErrMaxSteps
}

func (a *Agent) logf(format string, args ...any) {
	if a.Log != nil {
		fmt.Fprintf(a.Log, format, args...)
	}
}

func preview(s string, n int) string {
	s = strings.Join(strings.Fields(s), " ")
	runes := []rune(s)
	if len(runes) > n {
		return string(runes[:n]) + " ..."
	}
	return s
}

// DefaultSystemPrompt describes the environment and working style to the model.
func DefaultSystemPrompt(workspaceRoot string) string {
	return fmt.Sprintf(`You are a coding agent working in a local repository at %s.

Use the tools to look at the code before answering. Paths are relative to the workspace root.
When you are done, reply with your answer and make no further tool calls.`, workspaceRoot)
}

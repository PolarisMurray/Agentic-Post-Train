// Package tools defines the tools the agent can call and the registry that
// dispatches model tool calls to them.
package tools

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/PolarisMurray/Agentic-Post-Train/Agent_source/internal/llm"
)

type Tool interface {
	Name() string
	Description() string
	// Parameters is the JSON Schema of the tool's arguments object.
	Parameters() json.RawMessage
	// Run executes the tool. A returned error is reported back to the model
	// as the tool result, so the model can recover from it.
	Run(ctx context.Context, args json.RawMessage) (string, error)
}

type Registry struct {
	tools map[string]Tool
	order []string
}

func NewRegistry(ts ...Tool) *Registry {
	r := &Registry{tools: make(map[string]Tool)}
	for _, t := range ts {
		r.tools[t.Name()] = t
		r.order = append(r.order, t.Name())
	}
	return r
}

func (r *Registry) Specs() []llm.ToolSpec {
	specs := make([]llm.ToolSpec, 0, len(r.order))
	for _, name := range r.order {
		t := r.tools[name]
		specs = append(specs, llm.ToolSpec{
			Type: "function",
			Function: llm.FunctionSpec{
				Name:        t.Name(),
				Description: t.Description(),
				Parameters:  t.Parameters(),
			},
		})
	}
	return specs
}

func (r *Registry) Call(ctx context.Context, name, arguments string) (string, error) {
	t, ok := r.tools[name]
	if !ok {
		return "", fmt.Errorf("unknown tool %q", name)
	}
	if arguments == "" {
		arguments = "{}"
	}
	if !json.Valid([]byte(arguments)) {
		return "", fmt.Errorf("arguments for %s are not valid JSON: %s", name, arguments)
	}
	return t.Run(ctx, json.RawMessage(arguments))
}

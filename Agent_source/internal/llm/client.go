// Package llm is a minimal client for OpenAI-compatible Chat Completions APIs
// (OpenAI, Moonshot/Kimi, vLLM, SGLang, Ollama, ...).
package llm

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

type Role string

const (
	RoleSystem    Role = "system"
	RoleUser      Role = "user"
	RoleAssistant Role = "assistant"
	RoleTool      Role = "tool"
)

type Message struct {
	Role       Role       `json:"role"`
	Content    string     `json:"content"`
	ToolCalls  []ToolCall `json:"tool_calls,omitempty"`
	ToolCallID string     `json:"tool_call_id,omitempty"`
}

type ToolCall struct {
	ID       string       `json:"id"`
	Type     string       `json:"type"`
	Function FunctionCall `json:"function"`
}

type FunctionCall struct {
	Name string `json:"name"`
	// Arguments is a JSON object encoded as a string, as returned by the API.
	Arguments string `json:"arguments"`
}

// ToolSpec describes a callable function to the model.
type ToolSpec struct {
	Type     string       `json:"type"`
	Function FunctionSpec `json:"function"`
}

type FunctionSpec struct {
	Name        string          `json:"name"`
	Description string          `json:"description"`
	Parameters  json.RawMessage `json:"parameters"`
}

type ChatRequest struct {
	Model    string     `json:"model"`
	Messages []Message  `json:"messages"`
	Tools    []ToolSpec `json:"tools,omitempty"`
}

type Usage struct {
	PromptTokens     int `json:"prompt_tokens"`
	CompletionTokens int `json:"completion_tokens"`
	TotalTokens      int `json:"total_tokens"`
}

type ChatResponse struct {
	Message Message
	Usage   Usage
}

// ChatModel is what the agent loop depends on, so tests can swap in a fake.
type ChatModel interface {
	Chat(ctx context.Context, req ChatRequest) (*ChatResponse, error)
}

type Client struct {
	BaseURL    string
	APIKey     string
	HTTPClient *http.Client
}

func NewClient(baseURL, apiKey string) *Client {
	return &Client{
		BaseURL:    strings.TrimRight(baseURL, "/"),
		APIKey:     apiKey,
		HTTPClient: &http.Client{Timeout: 5 * time.Minute},
	}
}

type apiResponse struct {
	Choices []struct {
		Message Message `json:"message"`
	} `json:"choices"`
	Usage Usage `json:"usage"`
}

func (c *Client) Chat(ctx context.Context, req ChatRequest) (*ChatResponse, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, c.BaseURL+"/chat/completions", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	httpReq.Header.Set("Content-Type", "application/json")
	if c.APIKey != "" {
		httpReq.Header.Set("Authorization", "Bearer "+c.APIKey)
	}

	httpResp, err := c.HTTPClient.Do(httpReq)
	if err != nil {
		return nil, err
	}
	defer httpResp.Body.Close()
	raw, err := io.ReadAll(httpResp.Body)
	if err != nil {
		return nil, err
	}
	if httpResp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("chat completions: HTTP %d: %s", httpResp.StatusCode, raw)
	}

	var parsed apiResponse
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return nil, fmt.Errorf("chat completions: decode response: %w", err)
	}
	if len(parsed.Choices) == 0 {
		return nil, errors.New("chat completions: response has no choices")
	}
	msg := parsed.Choices[0].Message
	msg.Role = RoleAssistant
	return &ChatResponse{Message: msg, Usage: parsed.Usage}, nil
}

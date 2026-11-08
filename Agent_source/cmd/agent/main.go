// Command agent runs a minimal coding agent against an OpenAI-compatible model.
//
//	export OPENAI_API_KEY=...
//	agent -model gpt-4.1 -workdir ./myproject "what does this project do?"
package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"strings"

	"github.com/PolarisMurray/Agentic-Post-Train/Agent_source/internal/llm"
	"github.com/PolarisMurray/Agentic-Post-Train/Agent_source/internal/loop"
	"github.com/PolarisMurray/Agentic-Post-Train/Agent_source/internal/tools"
)

func main() {
	var (
		workdir  = flag.String("workdir", ".", "workspace root")
		model    = flag.String("model", os.Getenv("AGENT_MODEL"), "model name (env AGENT_MODEL)")
		baseURL  = flag.String("base-url", envOr("OPENAI_BASE_URL", "https://api.openai.com/v1"), "OpenAI-compatible API base URL (env OPENAI_BASE_URL)")
		maxSteps = flag.Int("max-steps", 30, "maximum number of model calls")
	)
	flag.Usage = func() {
		fmt.Fprintln(os.Stderr, "usage: agent [flags] <task>\n\nThe API key is read from OPENAI_API_KEY.\n\nflags:")
		flag.PrintDefaults()
	}
	flag.Parse()

	task := strings.TrimSpace(strings.Join(flag.Args(), " "))
	if task == "" {
		flag.Usage()
		os.Exit(2)
	}
	if *model == "" {
		fatal("no model given; pass -model or set AGENT_MODEL")
	}
	root, err := filepath.Abs(*workdir)
	if err != nil {
		fatal(err.Error())
	}

	agent := &loop.Agent{
		Model:        llm.NewClient(*baseURL, os.Getenv("OPENAI_API_KEY")),
		ModelName:    *model,
		Tools:        tools.NewRegistry(&tools.ReadFile{Root: root}),
		SystemPrompt: loop.DefaultSystemPrompt(root),
		MaxSteps:     *maxSteps,
		Log:          os.Stderr,
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()
	res, err := agent.Run(ctx, task)
	if res != nil {
		fmt.Fprintf(os.Stderr, "[done] steps=%d tokens=%d\n", res.Steps, res.Usage.TotalTokens)
	}
	if err != nil {
		fatal(err.Error())
	}
	fmt.Println(res.Final)
}

func fatal(msg string) {
	fmt.Fprintln(os.Stderr, "error:", msg)
	os.Exit(1)
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

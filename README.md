<p align="center">
  <a href="README.md"><img alt="English" src="https://img.shields.io/badge/English-blue?style=for-the-badge"></a>
  <a href="README.zh-CN.md"><img alt="简体中文" src="https://img.shields.io/badge/简体中文-lightgrey?style=for-the-badge"></a>
</p>

# Agentic-Post-Train

A hands-on repository for **post-training LLMs for agentic capabilities**.

This repo does two things:

1. **Agent_source**: Quickly rewrite mainstream open-source agent frameworks in Go / Python, compare their designs, and distill them into our own agent runtime.
2. **Post-Train**: Use trajectories produced by that agent to run SFT and RL, improving the model's agentic abilities (tool use, multi-step planning, code execution, etc.).

The two parts form a closed loop: the agent collects data and runs environments, Post-Train trains the model, and the trained model is plugged back into the agent for evaluation.

```
            ┌──────────── trajectories / env feedback ───────────┐
            │                                                    ▼
   ┌─────────────────┐                                 ┌──────────────────┐
   │  Agent_source   │                                 │    Post-Train    │
   │  (Go / Python)  │                                 │  SFT  →  RL      │
   └─────────────────┘                                 └──────────────────┘
            ▲                                                    │
            └────────── trained model back for evaluation ───────┘
```

---

## Repository Layout

```
Agentic-Post-Train/
├── Agent_source/        # Agent framework rewrites & comparison
├── Post-Train/
│   ├── SFT/             # Supervised fine-tuning: trajectory data, formatting, training
│   └── RL/              # Reinforcement learning: rollout, reward design, policy optimization
├── scripts/
│   └── fetch_upstream.sh  # Clone upstream repos at pinned commits
├── third_party/         # Upstream sources (local only, git-ignored)
├── third_party.lock     # Upstream repo URLs + pinned commits
├── .gitignore
├── .gitattributes
├── .editorconfig
├── README.md            # English
└── README.zh-CN.md      # 简体中文
```

> The layout will be refined as the project evolves. Each subdirectory will get its own README once it has content.

---

## Agent_source: Rewriting & Comparing Open-Source Agent Frameworks

### References

| Reference | Upstream | Focus |
| --- | --- | --- |
| **Codex** | [openai/codex](https://github.com/openai/codex) (Codex CLI, mainly Rust) | Agent loop, tool-calling protocol, sandboxing & command approval, context management |
| **Kimi** | [MoonshotAI/kimi-cli](https://github.com/MoonshotAI/kimi-cli) (Python) | Tool system, multi-turn task orchestration, how it pairs with Kimi models' agentic abilities |

### Language Split

- **Go**: The core agent runtime: agent loop, tool execution, sandbox, concurrent rollout, CLI. Chosen for simple deployment (single binary) and easy concurrency, well suited to running environments at scale to collect trajectories.
- **Python**: Everything that interfaces with training: data processing, reward functions, evaluation scripts, and modules that reuse the Python ecosystem directly.

### Comparison Dimensions

While rewriting, we record how Codex and Kimi differ along these dimensions and compile them into a comparison doc:

1. **Agent Loop**: single-turn / multi-turn structure, termination conditions, error recovery
2. **Tool Calling**: tool definition format, call parsing, parallel calls, result injection
3. **Execution & Safety**: sandboxing, command approval, filesystem permissions
4. **Context Management**: history compaction, long-context strategy, memory
5. **Prompt & Protocol**: system prompt organization, message format, thinking / reasoning handling
6. **Trainability**: how easily trajectories can be exported and fed into SFT / RL data pipelines

### Principles

- Understand first, then rewrite: document how upstream implements each module before writing the Go / Python version.
- Keep only what matters for agentic post-training. Full feature parity is not a goal.
- Upstream sources are cloned locally under `third_party/` for reference only and are never committed (ignored in `.gitignore`). Commits are pinned in `third_party.lock`; run `./scripts/fetch_upstream.sh` to reproduce them.
- Rewritten code follows upstream licenses, with sources noted in the relevant files.

---

## Post-Train

### SFT

- Collect trajectories from agent runs; clean, filter, and format them into training samples
- Chat template handling and loss masking for multi-turn dialogue + tool calls
- Training scripts and configs

### RL

- Rollout in agent environments (reusing the Agent_source runtime)
- Reward design: task completion, verifiable outcomes (tests passing, answer matching, etc.)
- Implementation and comparison of policy optimization algorithms (e.g. PPO / GRPO)

---

## Roadmap

- [x] Repo initialization, layout, git config
- [x] Agent_source: pin and fetch upstream repos (codex, kimi-cli)
- [ ] Agent_source: map out the architecture of codex / kimi-cli
- [ ] Agent_source: minimal Go agent loop + basic tools (shell / file read & write)
- [ ] Agent_source: Codex vs Kimi comparison doc v1
- [ ] Agent_source: define trajectory export format
- [ ] Post-Train/SFT: trajectory → SFT data pipeline + first training run
- [ ] Post-Train/RL: rollout environment integration + first RL run

---

## Requirements

- Go ≥ 1.22
- Python ≥ 3.10

The Python agent uses the OpenAI SDK. Install it in a virtualenv:

```bash
cd Agent_source/python
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/agent --workdir ../.. "what does this repo do?"
```

### API keys

Keys live in a `.env` file at the repo root. It is git-ignored; only the `.env.example` template is committed.

```bash
cp .env.example .env && chmod 600 .env   # then fill in OPENAI_API_KEY, OPENAI_BASE_URL, AGENT_MODEL
```

Both the Go and Python agents load the nearest `.env` (searching up to the repo root) on startup. Variables already set in the shell take precedence.

Dependencies are managed per sub-project (`go.mod` for Go, `pyproject.toml` for Python).

## License

TBD. Code rewritten from upstream projects follows the upstream LICENSE.

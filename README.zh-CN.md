<p align="center">
  <a href="README.md"><img alt="English" src="https://img.shields.io/badge/English-lightgrey?style=for-the-badge"></a>
  <a href="README.zh-CN.md"><img alt="简体中文" src="https://img.shields.io/badge/简体中文-blue?style=for-the-badge"></a>
</p>

# Agentic-Post-Train

面向 **Agent 能力的后训练（Post-Training）** 实践仓库。

这个仓库做两件事：

1. **Agent_source**：用 Go / Python 快速改写主流开源 Agent 框架，对比它们的设计，沉淀出一套自己的 Agent 运行时。
2. **Post-Train**：基于这套 Agent 产出的轨迹（trajectory），做 SFT 和 RL，提升模型的 agentic 能力（工具调用、多步规划、代码执行等）。

两部分形成闭环：Agent 负责采数据、跑环境，Post-Train 负责训模型，训完的模型再接回 Agent 评测。

```
            ┌──────────────── 轨迹 / 环境反馈 ────────────────┐
            │                                                 ▼
   ┌─────────────────┐                              ┌──────────────────┐
   │  Agent_source   │                              │    Post-Train    │
   │  (Go / Python)  │                              │  SFT  →  RL      │
   └─────────────────┘                              └──────────────────┘
            ▲                                                 │
            └──────────────── 训练后的模型回接评测 ────────────┘
```

---

## 目录结构

```
Agentic-Post-Train/
├── Agent_source/        # Agent 框架改写与对比
├── Post-Train/
│   ├── SFT/             # 监督微调：轨迹数据构造、格式化、训练
│   └── RL/              # 强化学习：rollout、奖励设计、策略优化
├── scripts/
│   └── fetch_upstream.sh  # 按锁定的 commit 拉取上游仓库
├── third_party/         # 上游源码（仅本地，git 忽略）
├── third_party.lock     # 上游仓库地址 + 锁定的 commit
├── .gitignore
├── .gitattributes
├── .editorconfig
├── README.md            # English
└── README.zh-CN.md      # 简体中文
```

> 目录会随项目推进逐步细化，每个子目录有内容后会补充各自的 README。

---

## Agent_source：开源 Agent 框架改写与对比

### 参考对象

| 参考 | 上游 | 主要关注点 |
| --- | --- | --- |
| **Codex** | [openai/codex](https://github.com/openai/codex)（Codex CLI，主体为 Rust） | agent loop、工具调用协议、沙箱与命令执行审批、上下文管理 |
| **Kimi** | [MoonshotAI/kimi-cli](https://github.com/MoonshotAI/kimi-cli)（Python） | 工具体系、多轮任务编排、与 Kimi 模型的 agentic 能力配合方式 |

### 语言分工

- **Go**：Agent 运行时主体：agent loop、工具执行、沙箱、并发 rollout、CLI。看重的是部署简单（单二进制）、并发好写，适合大规模批量跑环境采轨迹。
- **Python**：和训练侧对接的部分：数据处理、奖励函数、评测脚本，以及需要直接复用 Python 生态的模块。

### 对比维度

改写过程中按下面几个维度记录 Codex 与 Kimi 的差异，最终整理成对比文档：

1. **Agent Loop**：单轮 / 多轮结构、终止条件、错误恢复
2. **工具调用**：工具定义格式、调用解析、并行调用、结果回填
3. **执行与安全**：沙箱方式、命令审批、文件系统权限
4. **上下文管理**：历史压缩、长上下文策略、记忆
5. **Prompt 与协议**：system prompt 组织、消息格式、thinking / reasoning 处理
6. **可训练性**：轨迹是否易于导出、是否方便接入 SFT / RL 数据管线

### 原则

- 先读懂、再改写：每个模块先写清楚上游的实现方式，再给出 Go / Python 版本。
- 只保留对 agent 后训练有用的部分，不追求功能完全对齐。
- 上游源码只在本地 `third_party/` 下克隆作参考，不提交进本仓库（已在 `.gitignore` 中忽略）。版本锁定在 `third_party.lock`，执行 `./scripts/fetch_upstream.sh` 即可复现。
- 改写代码遵守上游的开源协议，相关文件注明来源。

---

## Post-Train

### SFT

- 从 Agent 运行中收集轨迹，清洗、过滤、格式化成训练样本
- 多轮对话 + 工具调用的 chat template 处理与 loss mask
- 训练脚本与配置

### RL

- 基于 Agent 环境的 rollout（复用 Agent_source 的运行时）
- 奖励设计：任务完成度、可验证结果（测试通过、答案匹配等）
- 策略优化算法（如 PPO / GRPO 等）的实现与对比

---

## Roadmap

- [x] 仓库初始化、目录结构、git 配置
- [x] Agent_source：锁定并拉取上游仓库（codex、kimi-cli）
- [ ] Agent_source：梳理 codex / kimi-cli 各自架构
- [ ] Agent_source：Go 版最小 agent loop + 基础工具（shell / 读写文件）
- [ ] Agent_source：Codex vs Kimi 对比文档 v1
- [ ] Agent_source：轨迹导出格式定义
- [ ] Post-Train/SFT：轨迹 → SFT 数据管线 + 首个训练实验
- [ ] Post-Train/RL：rollout 环境接入 + 首个 RL 实验

---

## 环境

- Go ≥ 1.22
- Python ≥ 3.10

Python 版基于 OpenAI SDK，装在虚拟环境里：

```bash
cd Agent_source/python
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/agent --workdir ../.. "这个仓库是做什么的？"
```

### API key

key 放在仓库根目录的 `.env` 文件里。它被 git 忽略，只有模板 `.env.example` 会提交。

```bash
cp .env.example .env && chmod 600 .env   # 然后填 OPENAI_API_KEY、OPENAI_BASE_URL、AGENT_MODEL
```

Go 版和 Python 版启动时都会自动读取最近的 `.env`（向上查找，最远到仓库根目录）。shell 里已经设置的同名环境变量优先。

具体依赖在各子项目中单独管理（Go 用 `go.mod`，Python 用 `pyproject.toml`）。

## License

待定。改写自上游的代码以上游 LICENSE 为准。

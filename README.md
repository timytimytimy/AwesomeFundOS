# AwesomeFundOS

AwesomeFundOS 是一个基于 Codex 生态的 Local-first 多 Agent 主观投资组织操作系统。

它的目标不是做荐股机器人、量化回测平台或自动交易系统，而是模拟一家小型主观私募基金的组织能力：研究、辩论、风控、决策、复盘、学习和进化。

## V1 定位

V1 聚焦 A 股主观投资研究场景，用户只输入投资议题、股票或问题，系统自主检索公开资料，组织多个长期 Agent 完成投资委员会式研究决策备忘录，并通过 Harness 评估质量，将合格经验沉淀为 Agent 的长期能力候选。

## 核心闭环

```text
用户问题
  -> ChiefOfStaff 编排与选人
  -> 自主检索公开资料
  -> EvidencePack
  -> Tool / Source Adapter Harness
  -> Learning Source Registry
  -> Agent-specific ContextPack
  -> 多 Agent 分工研究与辩论
  -> Agent-level Harness / Context & Skill Quality
  -> FundManager 模拟投委会决策备忘录
  -> Runtime / Context / Evolution Harness
  -> ReviewArchive / Watchlist / Paper Portfolio Review / Attribution
  -> Outcome Tracking / Market Replay
  -> Memory / Principles / Skill 升级候选
  -> EvolutionGate
  -> Capability Versioning / Approval Queue
  -> Human-approved Capability Apply
  -> Agent 长期能力版本更新
```

## 文档入口

- 整体 PRD: `docs/prd/overall-prd.md`
- 模块 PRD: `docs/prd/modules/`
- 默认 Agent 名册: `specs/agents/default-roster.yaml`
- 数据结构 Schema: `specs/schemas/`
- 投委会工作流: `specs/workflows/investment-committee.workflow.yaml`
- CLI 规格: `specs/cli/commands.md`
- Codex 实现计划: `specs/tasks/implementation-plan.md`

## V1 验证

本地安装 CLI：

```bash
python3 -m pip install -e .
fundos --help
```

快速健康检查：

```bash
fundos system doctor
```

`doctor` 会检查本地安装入口、19 个 Agent Card、19 个 source Skill、Codex Skill 导出 dry-run、strict repository audit，以及 `real_trade_allowed=False` / `broker_integration=disabled` 安全边界。

本地完整质量门：

```bash
scripts/verify_v1.sh
```

该脚本会运行全量 unittest、`fundos system audit --strict` 和 `git diff --check`，并显式校验 `real_trade_allowed=False` 与 `broker_integration=disabled`。GitHub Actions 使用同一个脚本作为 CI 入口。

为兼容 PEP 668 / Homebrew Python 等 externally-managed 环境，`scripts/verify_v1.sh` 会默认创建并复用仓库内 `.venv-fundos-verify`，不会向系统 Python 写入包。

## Codex Skill 导出

仓库内的 canonical Skills 位于 `specs/skills/*/SKILL.md`。如果需要把 AwesomeFundOS 的 19 个 Agent Skills 导出为 Codex 可发现的 Skill 目录，可以运行：

```bash
fundos skills export --out ./skills
# 或不安装 console script 时：
python3 -m fundos.cli skills export --out ./skills
```

该命令会生成 `./skills/fundos-*/SKILL.md` 和 `./skills/awesomefundos-skills-manifest.yaml`。导出的 Skills 仍保持 `real_trade_allowed=false` 与 `broker_integration=disabled`，只用于研究、观察池和 Paper Portfolio 工作流。

## 内置离线研究场景

V1 提供跨行业、跨市场状态的 deterministic fixture catalog，用于离线验证 Agent 分工、EvidencePack、ContextPack、Outcome Tracking 和 Harness：

```bash
fundos fixtures list
fundos run --fixture-id robotics
fundos run --fixture-id consumer_healthcare
fundos run --fixture-id cyclical_macro
fundos run --fixture-id policy_event
```

这些 fixture 覆盖公告、政策、新闻、行情摘要、社媒情绪和历史案例六类来源；社媒/KOL 只作为情绪或假设线索，不能成为直接买卖依据。所有场景都保持 `real_trade_allowed=false` 与 `broker_integration=disabled`。

## 合规边界

V1 输出为模拟投委会研究决策备忘录、观察池动作和模拟组合观点，不构成投资建议，不接真实交易，不自动下单。

Portfolio Review 和 Outcome Tracking 仅复盘观察池和 Paper Portfolio 的过程质量、证据引用、风控约束、离线行情 fixture 结果和后验数据缺口；它不是收益承诺、真实交易归因或买卖信号。

Capability Apply 只允许把已通过 EvolutionGate 且处于 `pending_human_apply` 的能力候选，在显式 `--approver` 下写入受控 managed block 或 `applied-capabilities.yaml`；不得自动改写核心 `agent.md`、Profile、Risk Limit、Tool Permission，也不得开启真实交易权限。

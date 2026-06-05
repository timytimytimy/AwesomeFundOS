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

## 合规边界

V1 输出为模拟投委会研究决策备忘录、观察池动作和模拟组合观点，不构成投资建议，不接真实交易，不自动下单。

Portfolio Review 和 Outcome Tracking 仅复盘观察池和 Paper Portfolio 的过程质量、证据引用、风控约束、离线行情 fixture 结果和后验数据缺口；它不是收益承诺、真实交易归因或买卖信号。

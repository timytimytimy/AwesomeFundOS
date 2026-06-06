# Context Management PRD

## 1. 模块目标

Context Management 负责把全量 EvidencePack 压缩、过滤、路由为 Agent-specific ContextPack。它是一等核心模块，而不是普通摘要功能。

设计原则：Vertical agents are context-shaped agents。

## 2. 核心流程

```text
Raw Sources / Tool Results
  -> EvidencePack
  + Agent Persistent Thread Summary
  -> Context Manager
  -> Agent-specific ContextPack
  -> Agent Output
  -> Context Quality Harness
```

## 3. ContextPolicy

每个 Agent 必须有 ContextPolicy。

字段：

- preferred_source_types
- preferred_evidence_tiers
- preferred_claim_types
- time_horizon
- max_token_budget
- excluded_context
- compression_style
- must_preserve
- forbidden_focus
- required_focus

## 4. ContextPack

ContextPack 是某个 Agent 在某个阶段看到的上下文包。

核心字段：

- context_pack_id
- run_id
- agent_id
- role
- task_stage
- context_budget_tokens
- included_evidence
- included_claims
- compressed_summaries
- contradiction_table
- missing_evidence
- excluded_evidence_summary
- thread_memory_summary
- required_focus
- forbidden_focus
- output_schema

`thread_memory_summary` 是长期 Thread 的只读检索摘要，不是自动上下文污染。它只允许纳入：最近 accepted memory lessons、quarantined/rejected candidates、尚未关闭的 research gaps 和最近事件索引；必须过滤任何 real trade / broker 泄漏，并在 ContextBudgetManifest 中记录 `thread_summary_included`。Agent 可以用它维持长期连续性和避免重复错误，但不能让它覆盖当前 EvidencePack、ToolPolicy、MemoryPolicy 或 Harness 结果。

Agent 输出必须通过 `thread_memory_influence` 显式声明哪些 accepted memory lessons 被用作本轮推理的只读上下文影响。该字段至少记录 candidate_id、semantic_memory_path、approval_mode、usage=`retrieval_context_only`、controls 和安全边界。未声明的长期记忆不得隐式影响结论。

Agent 输出还必须通过 `reasoning_layers` 明确分离：`current_evidence_conclusions`、`thread_memory_influences` 和 `hypotheses_to_validate`。当前证据结论必须能回链 Evidence ID / Claim ID；历史记忆只能作为 retrieval context；假设必须带 validation_required，不得被当作事实或买卖信号。

`hypotheses_to_validate` 不是一次性文本。Context / Task DAG 需要把它们压缩成可追踪的 follow-up research gap：保留来源 Agent、Evidence ID、Claim ID、原始假设和 validation_required，使垂直 Agent 在后续 Thread 中能看到“哪些假设尚未被 primary 或 cross-validated evidence 关闭”，而不是把低等级信号混入事实结论。

## 5. 角色化上下文策略

### FundManager

看高层摘要、各 Agent 结论、核心争议、风险收益、证据缺口、模拟仓位条件。

### 行业研究员

看政策、产业链、技术路径、供需、下游方案、chokepoint、行业案例、Serenity 方法论片段。

### 公司研究员

看公告、财报、产品矩阵、客户订单、竞争格局、治理风险、行业结论摘要。

### 交易员

看价格趋势、量价、相对强弱、板块热度、催化时间表、风险事件、研究结论摘要、历史类似交易案例。

### 风控

看核心假设、证据等级、模拟仓位、流动性、估值、财务风险、争议点、最强反方观点、极端情景。

### 反方

看 Bull case、证据缺口、低等级来源、估值和拥挤度、替代解释、失败案例、反例、泡沫案例。

## 6. Context Quality Harness

评分维度：

- relevance
- compression_fidelity
- evidence_traceability
- role_specificity
- information_sufficiency
- noise_control
- leakage_control
- contradiction_preservation

V1 的 Context Quality Harness 不只给全局平均分，还必须按 Agent 输出：

- ContextPack 是否为该 Agent 专属，而非全量 run dump；
- included_evidence 是否能回链 Evidence ID；
- allowed_claims 是否能回链 Claim ID；
- Agent 输出中的 key_claims 是否来自该 ContextPack；
- contradiction_table、missing_evidence、excluded_evidence_summary 是否保留；
- thread_memory_summary 是否保留已接受经验、隔离/拒绝候选和未关闭证据缺口，且只作为 retrieval input；
- Agent 输出中的 thread_memory_influence 是否能回链到 ContextPack 的 accepted memory lessons；
- Agent 输出中的 reasoning_layers 是否把当前证据、记忆影响和待验证假设分层，并保持证据回链和安全边界；
- Skill 的 Context Management 规则是否进入运行时 Skill Contract。

产物路径：`runs/{run_id}/harness/agent-harness.yaml`。

## 7. 验收标准

- 每个 selected agent 均获得独立 ContextPack。
- ContextPack 能回链到 EvidencePack。
- 压缩摘要不丢失关键争议和证据等级。
- 不同角色获得明显不同的上下文内容和输出约束。
- Harness 能对 ContextPack 评分并指出缺陷。
- Harness 能把 ContextPack 评分纳入 `agent_harness_quality`。
- ContextPack 必须从 `SKILL.md` 抽取 `Guardrails`，并要求 Agent runtime 输出 `skill_guardrails_applied` 与 `guardrail_checks`；Context / Harness 压缩不得丢失 `real_trade_allowed=false`、`broker_integration=disabled`、EvolutionGate、以及 Profile/Skill/Tool/Memory/Thread/Harness/Evolution 边界。
- ContextPack 能在有 runtime thread 时纳入安全的 Thread summary，并保持 no-real-trade / broker-disabled 边界。

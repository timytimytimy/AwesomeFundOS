# Harness PRD

## 1. 模块目标

Harness 负责持续评估 Agent、Context、Evidence、Tools、Collaboration、Decision 和 Evolution Candidate 的质量。它不是测试脚本附属品，而是系统进化的 gatekeeper。

## 2. V1 Harness 层级

### Level 1 Runtime Quality Harness

每次 run 立即评估：

- evidence_quality
- reasoning_quality
- role_consistency
- decision_quality
- collaboration_quality
- tool_usage_quality

### Level 2 Evolution Gate Harness

评估升级候选：

- memory_update_quality
- principle_update_quality
- skill_candidate_quality
- source_quality
- testability
- overfitting_risk
- role_drift_risk
- risk_regression_risk

### Context Quality Harness

评估 ContextPack：

- relevance
- compression_fidelity
- evidence_traceability
- role_specificity
- information_sufficiency
- noise_control
- leakage_control
- contradiction_preservation

V1 需要额外生成 Agent-level harness artifact，用于把 Context、Skill、Agent Card 和实际 Agent 输出绑定起来评估：

```text
runs/{run_id}/harness/agent-harness.yaml
```

Agent-level harness 对每个 selected agent 输出：

- context_compression_quality：检查 included_evidence、allowed_claims、Evidence ID / Claim ID 回链、contradiction_table、missing_evidence 和 excluded_evidence_summary；
- skill_invocation_quality：检查 `SKILL.md` 是否加载、关键 section 是否存在、runtime skill path 是否与 ContextPack 一致、role checklist 和 evidence rules 是否进入输出；
- role_consistency_quality：检查 agent_id / role 是否一致、agent card 是否加载、declared skills 是否对齐、边界和免责声明是否存在；
- blocking_issues：低于阈值或越界时产生阻断项。

Harness Evaluation 需要把该摘要写入 `agent_harness_quality`，并在有有效产物时把 `agent_harness` 放入 accepted_outputs。

### Historical Case Replay Harness

Harness 必须把学习 pattern 放入历史案例回放，而不是让 Agent 直接套用案例结论。V1 回放产物：

```text
runs/{run_id}/harness/historical-case-replay.yaml
```

回放输入：

- run-scoped `learning/patterns.yaml`；
- 内置小型 historical case library；
- 每个 pattern 的 `validation_gates`。

回放输出：patterns_replayed、cases_available、case_results_total、fit_score、overfit_risk、verdict、lessons_checked、failure_modes_checked、controls。

核心控制：`case_replay_is_not_trade_signal`、`direct_case_mapping_forbidden`、`primary_evidence_still_required`。

Harness Evaluation 需要把回放摘要写入 `case_replay_quality`，并把 `historical_case_replay` 放入 dimension_scores。

### Level 3 Outcome Tracking Stub

V1 只做轻量结构，但必须形成可评测的复盘闭环：

- watchlist_tracking
- paper_portfolio_review
- process_attribution
- review_learning_candidates
- outcome_evaluation_schema

Portfolio Review 产物：

```text
runs/{run_id}/portfolio/portfolio-review.yaml
runs/{run_id}/portfolio/attribution.jsonl
runs/{run_id}/portfolio/review-candidates.jsonl
```

复盘输入：`watchlist.yaml`、`paper-portfolio.yaml`、`portfolio-actions.jsonl`、风控约束和证据引用。

复盘输出：reviewed_actions、attribution_items、learning_candidates、real_trade_violations、review_verdict、controls。

核心控制：`paper_only`、`no_broker_integration`、`no_real_trade_action`、`review_before_upgrade`。

V1 没有真实行情/成交回放 adapter，因此 attribution 只评价过程质量、证据数量、触发条件、风控约束和后验数据缺口；不得把 Portfolio Review 解释为真实收益归因或买卖信号。

## 3. EvaluationReport

每次 run 输出 EvaluationReport：

- run_id
- overall_score
- dimension_scores
- context_quality_scores
- portfolio_quality
- portfolio_review_quality
- agent_harness_quality
- case_replay_quality
- agent_scores
- collaboration_graph
- tool_usage_findings
- blocking_issues
- accepted_outputs
- rejected_outputs
- improvement_suggestions

## 4. EvolutionGateResult

对每个升级候选输出：

- candidate_id
- candidate_type
- source_agent
- decision: accept | reject | quarantine | needs_more_evidence
- scores
- required_follow_up_tests
- rationale

## 5. 硬性阻断条件

以下情况应阻断高置信输出或能力升级：

- 高影响结论缺少来源；
- 证据主要来自低等级社媒；
- 反方或风控未参与；
- FundManager 未回应关键争议；
- ContextPack 丢失关键矛盾；
- Skill 候选不可测试；
- 升级候选明显过拟合单一案例；
- Agent 出现角色漂移；
- 输出真实投资建议或交易指令。

## 6. 验收标准

- `fundos eval --run <run>` 能生成 EvaluationReport。
- `fundos evolve --run <run>` 能生成 EvolutionGateResult。
- Harness 能给出维度分数和阻断项。
- Harness 能读取 Watchlist / Paper Portfolio Review，并输出 `portfolio_review_quality`。
- Harness 能读取 per-agent Context / Skill / Role 评分，并输出 `agent_harness_quality`。
- Harness 能拒绝低质量升级候选。
- 所有评分依据能引用 artifact / evidence / context / output id。

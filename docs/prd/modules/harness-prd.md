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

V1 只做轻量结构：

- watchlist_tracking
- paper_portfolio_stub
- outcome_evaluation_schema

## 3. EvaluationReport

每次 run 输出 EvaluationReport：

- run_id
- overall_score
- dimension_scores
- context_quality_scores
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
- Harness 能拒绝低质量升级候选。
- 所有评分依据能引用 artifact / evidence / context / output id。

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

### Capability Regression Harness

能力候选即使通过 EvolutionGate，也必须在人工 apply 前经过 regression harness。产物：

```text
runs/{run_id}/harness/capability-regression.yaml
```

Regression Harness 检查：

- required_tests 是否存在对应 artifact；
- historical_case_replay 是否有结果且 score 达标；
- agent_harness 的 role_consistency / skill_invocation 是否达标；
- evaluation-report 的 evidence_quality 和 tier_1_primary_fact 覆盖是否达标；
- 候选是否试图触碰 core_profile / org_structure / tool_permission / risk_limit；
- 候选是否试图开启真实交易。

未通过时，registry 中该候选 `application_status=blocked_regression`，并禁止 `fundos capabilities apply` 应用。

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
- context_management_quality：检查 context_budget_manifest、loss_accounting、token budget、角色化压缩和证据损失可审计性；
- thread_memory_summary_quality：检查长期 Thread 摘要是否可用、是否只作为 retrieval input、是否被 ContextBudgetManifest 记录、是否保留 accepted lessons / quarantined candidates / rejected candidates / open research gaps / recent events，且是否保持 no-real-trade / broker-disabled 边界；
- memory_lesson_traceability_quality：检查 Agent 输出是否显式声明哪些 accepted memory lessons 影响了本轮推理，candidate_id 是否与 ContextPack 的 Thread Summary 一致，usage 是否限定为 `retrieval_context_only`，以及是否保持安全边界；
- reasoning_layer_separation_quality：检查 Agent 输出是否分离 current evidence conclusions、thread memory influences 和 hypotheses to validate；事实结论必须有 Evidence ID / Claim ID，假设必须有 validation_required，记忆影响必须是 retrieval-only；
- agent_reasoning_hypothesis_followup_quality：检查 `reasoning_layers.hypotheses_to_validate` 是否被路由为 Research Gap Follow-up task，是否保留 source_agent_id / Evidence ID / Claim ID / validation_required，是否去重，且只允许 follow-up research brief，不允许真实交易或 broker 动作；
- skill_invocation_quality：检查 `SKILL.md` 是否加载、关键 section 是否存在、runtime skill path 是否与 ContextPack 一致、role checklist、evidence rules 和 Guardrails 是否进入输出；
- skill_guardrails：检查每个 Agent 的 runtime 输出是否实际声明并遵守 Skill Guardrails，包括 `real_trade_allowed=false`、`broker_integration=disabled`、Profile/Skill/Tool/Memory/Thread/Harness/Evolution 边界、KOL/书籍/课程/案例只作为 hypothesis/checklist/failure pattern、以及 durable learning 必须经过 Harness 和 EvolutionGate；
- role_consistency_quality：检查 agent_id / role 是否一致、agent card 是否加载、declared skills 是否对齐、边界和免责声明是否存在；
- blocking_issues：低于阈值或越界时产生阻断项。

Harness Evaluation 需要把该摘要写入 `agent_harness_quality`，把 thread summary 聚合分数写入 `context_management_quality.thread_memory_summary_quality`，把 Guardrails 聚合分数写入 `agent_harness_quality.skill_guardrails`，把假设路由质量写入 `task_dag_quality.agent_reasoning_hypothesis_quality`，并在有有效产物时把 `agent_harness`、`context_management`、`thread_memory_summary`、`memory_lesson_traceability`、`reasoning_layer_separation`、`skill_guardrails`、`agent_reasoning_hypothesis_followups` 放入 accepted_outputs。

### Agent Performance / Promotion Harness

V1 需要把单次 run 的 Agent 表现沉淀为长期 ledger，用于晋升观察、降权观察和复训建议。产物：

```text
runs/{run_id}/harness/agent-performance.yaml
agents/{agent_id}/performance/performance_ledger.jsonl
agents/{agent_id}/performance/evaluation_history.jsonl
agents/{agent_id}/performance/promotion_history.jsonl
```

输入：`harness/agent-harness.yaml`、`evaluations/evaluation-report.yaml`、selected_agents。

输出：final_score、component_scores、recommended_action、blocking_issues。

边界：promotion 不提升资金权限、不改 risk_limit、不改 tool_permission；demotion 不删除记忆，只进入复训或降权观察。

### Tool / Source Adapter Harness

V1 需要把工具调用和来源质量作为一等 Harness，而不是只看最终 EvidencePack。产物：

```text
runs/{run_id}/harness/tool-harness.yaml
```

Tool Harness 评估：

- adapter_coverage：public research 是否接入、是否取得一手公告/政策/行情类来源、低等级公开来源是否占主导；
- source_boundary_quality：KOL / 大V / 书籍 / 课程 / 历史案例是否被正确标记为 methodology / hypothesis，而非直接事实或买卖信号；
- source_tier_counts 与 source_type_counts；
- high_confidence_allowed：只有公开检索中存在一手来源且低等级来源未主导时才允许高置信升级；
- blocking_issues：缺 public research、公开检索无一手来源、社媒来源主导、KOL 降权边界缺失等。

核心控制：`primary_source_required_for_high_confidence`、`kol_is_hypothesis_not_trade_signal`、`book_and_case_are_methodology_only`、`social_signal_never_direct_buy`。

Harness Evaluation 需要把该摘要写入 `tool_harness_quality`。如果 `high_confidence_allowed=false`，最终结论必须维持证据不足或低置信状态。

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

### Level 3 Outcome Tracking / Market Replay Harness

V1 只做轻量结构，但必须形成可评测的复盘闭环。支持离线 market replay fixture，不接实时行情、不接券商、不生成真实交易动作：

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

Outcome Tracking 产物：

```text
runs/{run_id}/portfolio/outcome-tracking.yaml
runs/{run_id}/portfolio/outcome-attribution.jsonl
```

复盘输入：`watchlist.yaml`、`paper-portfolio.yaml`、`portfolio-actions.jsonl`、风控约束和证据引用。

复盘输出：reviewed_actions、attribution_items、learning_candidates、real_trade_violations、review_verdict、controls。

Outcome Tracking 输出：actions_evaluated、actions_missing_market_replay、market_replay_items、return_pct、max_drawdown_pct、max_favorable_excursion_pct、max_adverse_excursion_pct、review_verdict、outcome_quality_score。

核心控制：`paper_only`、`no_broker_integration`、`no_real_trade_action`、`review_before_upgrade`。

Outcome Tracking 核心控制：`paper_only`、`market_replay_is_not_trade_signal`、`no_real_trade_action`、`no_broker_integration`、`outcome_tracking_requires_fixture_or_adapter`。

V1 没有真实成交回放 adapter；离线行情 fixture 只用于后验训练和 Harness 评分，不得把 Outcome Tracking 解释为真实收益归因或买卖信号。没有行情 fixture 时，必须记录 `missing_market_replay`，不能把缺数据当作通过。

### Failure Pattern Extraction Harness

Harness 需要把失败样本结构化为可回放、可审计、可用于未来复训的错误模式库。V1 产物：

```text
runs/{run_id}/learning/failure-patterns.yaml
memory/organization/failure-pattern-library.jsonl
```

抽取输入：

- `reflections/*.reflection.yaml` 中的 missed_evidence、reasoning_errors、tool_usage_errors、bias_detected；
- `evaluations/evaluation-report.yaml` 中的 blocking_issues；
- `portfolio/outcome-tracking.yaml` 中的 missed_opportunity_review 和 risk_control_review。

Harness 输出：pattern_count、category_counts、severity_counts、patterns、controls。

核心控制：`review_before_evolution`、`failure_patterns_are_not_trade_signals`、`no_real_trade_action`、`do_not_delete_historical_errors`。

Failure Pattern Library 是 Evolution 的负反馈输入：后续 capability candidate 必须能解释它要降低哪类错误、如何测试该改进，以及是否会引入新的角色漂移或风险回归。

## 3. EvaluationReport

每次 run 输出 EvaluationReport：

- run_id
- overall_score
- dimension_scores
- context_quality_scores
- portfolio_quality
- portfolio_review_quality
- outcome_tracking_quality
- agent_harness_quality
- context_management_quality
- tool_harness_quality
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
- Harness 能读取离线 Market Replay Outcome Tracking，并输出 `outcome_tracking_quality`。
- Harness 能读取 per-agent Context / Skill / Role 评分，并输出 `agent_harness_quality`。
- Harness 能读取工具和来源边界评分，并输出 `tool_harness_quality`。
- Harness 能生成 `learning/failure-patterns.yaml` 并把组织级错误模式追加到 `memory/organization/failure-pattern-library.jsonl`。
- Harness 能拒绝低质量升级候选。
- 所有评分依据能引用 artifact / evidence / context / output id。

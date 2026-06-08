# Learning & Evolution PRD

## 1. 模块目标

Learning & Evolution 模块负责从外部学习源、历史案例、投委会复盘和 Agent 运行表现中提炼可测试经验，并通过 EvolutionGate 将合格经验转化为 Agent 的 Memory、Decision Principles、Skills、Checklists、Workflows 和 Tool Policies 升级。

## 2. 学习源

V1 Seed Library 小而精，包含：

- Serenity / aleabitoreddit；
- 里海；
- Howard Marks；
- Stan Druckenmiller；
- George Soros；
- Jesse Livermore；
- William O'Neil / CANSLIM；
- Mark Minervini；
- Peter Lynch；
- Buffett / Munger；
- A 股经典案例类型；
- 失败、泡沫、爆雷、反转、政策驱动案例类型。

## 3. 共享组织知识库 + 角色专属学习路径

### 3.1 共享组织知识库

- source_registry
- evidence_pack_store
- case_library
- market_state_library
- mistake_pattern_library
- organization_lessons
- accepted_skill_library

V1 必须把学习源登记为可审计 registry，而不是让 Agent 直接从大 V、书籍、课程或案例中吸收结论。运行级产物：

```text
runs/{run_id}/learning/source-registry.yaml
```

初始化级组织产物：

```text
memory/organization/learning-source-registry.yaml
```

Registry 至少包含：source_count、source_tier_counts、source_type_counts、allowed_learning_outputs、not_allowed_outputs、validation_required、required_gates_for_evolution、requires_primary_validation、adoption_policy 和 boundary_policy。

Serenity、里海、知名交易员、研究员、知名大 V、课程、书籍和历史案例可以进入 registry，但默认只能作为 methodology / hypothesis / checklist / case_pattern 来源。任何能力升级候选如果引用这些来源，必须满足 registry 声明的 gates，例如 primary_evidence_check、target_market_adaptation、historical_case_replay、bear_case_review、role_drift_check 和 evidence_quality_check。

### 3.2 角色专属学习路径

- FundManager: cycle thinking, second-level thinking, risk-reward, capital allocation
- IndustryAnalyst: supply-chain chokepoint, industry lifecycle, policy-to-demand mapping
- CompanyAnalyst: financial analysis, business quality, governance risk, valuation
- Trader: price-volume, entry-exit, position management, stop loss
- RiskManager: drawdown, liquidity, exposure limits, tail risk
- BearDebater: thesis attack, fraud detection, bubble detection, alternative explanations

## 4. Distillation Pipeline

```text
Public Sources / Cases / Books / Courses
  -> Source Registry
  -> Evidence Extraction
  -> Pattern Distillation
  -> Skill / Principle / Memory Candidate
  -> Harness Evaluation
  -> Accepted / Quarantined / Rejected Upgrade
  -> Agent Capability Versioning
```

## 5. Upgrade Scope V1

允许自动提出并经 Harness 通过后升级：

- memory
- mistake_patterns
- market_state_patterns
- case_library
- decision_principles
- research_checklists
- analysis_workflows
- skill_versions
- tool_usage_policies

需要人工或管理员批准：

- core_profile
- role
- risk_preference
- tool_permissions
- capital_authority
- creating_new_agents
- deleting_agents
- changing_harness_standards

### 5.1 V1 受控写回规则

EvolutionGate 的 `accept` 不等于任意改写系统。V1 只允许将已接受候选写入可审计、可回滚的长期记忆与 ledger：

- `memory/agents/{agent_id}/semantic_memory.md`
- `memory/agents/{agent_id}/evolution-ledger.jsonl`
- `memory/organization/evolution-ledger.jsonl`
- `runs/{run_id}/evolution/memory-writeback-summary.yaml`

V1 禁止自动写回：

- core profile；
- role / risk_preference；
- tool permissions；
- capital authority；
- risk limits；
- organization structure。

### 5.1.1 Thread Lifecycle to Learning Candidates

Agent Thread 是长期连续性日志，不等同于自动记忆。V1 必须把部分可验证的 Thread lifecycle event 转化为 `agent_learning_candidate`，再交由 EvolutionGate 评测，而不是直接改写 Agent 能力。

第一类支持事件是 `research_gap_followup_closed`：当某个 Agent 先把研究缺口标记为 `needs_evidence`，随后该缺口通过 accepted EvidenceItem 关闭时，系统可以生成一个 `reflection_update / agent_memory` 候选。候选必须记录：

- owner agent；
- task_id；
- research gap category；
- accepted_evidence_ids；
- 原始 Thread event log 路径；
- required_tests，包括 role drift、evidence quality 和 historical case replay。

该候选只能表达“未来类似任务要保留证据缺口、引用已验收证据 ID、在缺口关闭前保持 confidence cap”等复盘经验；不得提出买卖指令、风控放宽、工具权限升级、broker 接入或 core profile 修改。

Agent 输出中的 `reasoning_layers.hypotheses_to_validate` 必须进入同一 follow-up 生命周期：Task DAG 将其转换为 `source=agent_reasoning_layer` 的研究缺口任务，保留 `source_agent_id`、`source_evidence_id`、`source_claim_id` 和 `validation_required`，并对同一 Agent / Evidence / Claim 去重。该任务关闭前，相关假设只能作为待验证研究问题存在；关闭时，`followups answer/close` 必须继续把这些 origin metadata 写入 Thread event payload 和 learning candidate metadata；关闭后也只能通过 accepted EvidenceItem 触发上述候选生成与 EvolutionGate 评测，不能直接升级 Profile、Skill、Tool Policy 或交易权限。

EvolutionGate 必须继续保留这类 hypothesis-origin metadata，而不是在评测结果中压扁成普通 reflection。`evolution-gate-results.jsonl`、accepted/quarantine/rejected 分区、agent evolution ledger 和 semantic memory 写回都必须保留或摘要记录：`source=agent_reasoning_layer`、`source_agent_id`、`source_evidence_id`、`source_claim_id`、`hypothesis` 和 `validation_required`。同时必须输出 `hypothesis_origin_quality`，至少检查 source_agent_id、source_claim_id、validation_required 和安全边界是否存在；metadata 中任何 `real_trade_allowed` 或 `broker_integration` 输入都必须被清洗为 `real_trade_allowed=false`、`broker_integration=disabled`。该链路用于审计“某个 Agent 的某条推理假设如何变成研究缺口、如何关闭、如何形成可回滚经验”，不得成为买卖指令或真实交易权限。

### 5.2 Capability Versioning / Approval Queue

Principle、Skill、Checklist、Workflow、Tool Policy 类候选即使被 EvolutionGate 接受，也不能直接改写 source-controlled `agent.md`、`SKILL.md`、Profile、Tool Permission 或 Risk Limit。V1 必须把它们写入可审计的能力候选注册表：

```text
memory/agents/{agent_id}/capabilities/{principle|skill|checklist|workflow|tool_policy}.jsonl
memory/organization/capability-ledger.jsonl
runs/{run_id}/evolution/capability-candidates.jsonl
runs/{run_id}/evolution/capability-version-summary.yaml
```

能力版本记录必须包含 candidate_id、run_id、source_agent、target_agent、capability_kind、candidate_type、target_scope、proposal、source_basis、required_tests、scores、controls、approval_mode、application_status、reversible、mutated_agent_card=false、mutated_runtime_skill=false、real_trade_allowed=false、broker_integration=disabled。

默认 `application_status=pending_human_apply`。只有后续人工或更高等级审批流才能把候选合并进受控 runtime 能力文件；V1 自动 evolve 流程只登记候选和 ledger，不直接修改运行时技能文件。

### 5.3 Human-approved Capability Apply

V1 提供 `fundos capabilities list` 和 `fundos capabilities apply <candidate_id> --approver <human>` 作为人工审批入口。

Apply 约束：

- 只允许应用 `pending_human_apply` 候选；
- 必须显式提供 human approver；
- skill 候选只能追加 managed block 到 runtime `skills/{agent_id}/SKILL.md`，并带 `FUNDOS_CAPABILITY:{candidate_id}` 可回滚标记；
- principle / workflow / checklist / tool_policy 候选写入 runtime `agents/{agent_id}/applied-capabilities.yaml`；
- registry 更新为 `application_status=applied`，并写入 `memory/organization/capability-apply-ledger.jsonl`；
- 不改写 source-controlled `specs/agents/agent-cards/**/agent.md` 或 `specs/skills/**/SKILL.md`；
- 不改写核心 Profile、Risk Limit、Tool Permission、Organization Structure；
- `real_trade_allowed=false`，`broker_integration=disabled` 必须保持不变。

### 5.4 Capability Regression Harness

在人工 apply 之前，系统必须运行 capability regression harness，避免一次 run 的候选绕过历史案例、角色漂移和证据质量检查。

产物：

```text
runs/{run_id}/harness/capability-regression.yaml
```

Regression Harness 输入：

- `memory/agents/{agent_id}/capabilities/{kind}.jsonl` 中的 `pending_human_apply` 候选；
- run 级 `evolution/capability-candidates.jsonl`；
- `harness/historical-case-replay.yaml`；
- `harness/agent-harness.yaml`；
- `evaluations/evaluation-report.yaml`；
- 候选声明的 `required_tests`。

Regression Harness 输出：candidates_total、passed_candidates、blocked_candidates、candidate_results、blocking_issues、application_status_after_regression。

如果缺少 required_tests 对应 artifact，或 case replay / role consistency / evidence quality 分数低于门槛，候选必须变为 `blocked_regression`，并追加 `capability_regression_required` follow-up test。`fundos capabilities apply` 必须拒绝 blocked regression 的候选。

每次写回必须包含：candidate_id、run_id、source_agent、target_agent、candidate_type、target_scope、proposal、source_basis、required_tests、scores、controls、approval_mode、reversible、real_trade_allowed=false、broker_integration=disabled。

若写回候选来自 `agent_reasoning_layer` hypothesis origin，ledger 必须额外包含 `metadata` 和 `hypothesis_origin_quality`；semantic memory 必须以简短审计字段记录 hypothesis_source、source_agent_id、source_evidence_id、source_claim_id 和 validation_required，避免垂直 Agent 在后续 context 压缩中丢失原始假设来源。

### 5.5 Failure Pattern Library

V1 必须把失败、证据缺口、工具错误、偏见和后验错失沉淀为独立的错误模式库，作为 EvolutionGate 和未来能力升级的负样本输入，而不是只记录成功经验。

运行级产物：

```text
runs/{run_id}/learning/failure-patterns.yaml
```

组织级产物：

```text
memory/organization/failure-pattern-library.jsonl
```

输入来源：

- Agent reflections：missed_evidence、reasoning_errors、tool_usage_errors、bias_detected；
- EvaluationReport：blocking_issues；
- Agent Harness：Skill Guardrails 违规，包括 `skill_guardrails_not_applied`、`guardrails_applied=false`、`guardrail_safety_respected=false`；
- Outcome Tracking：missed_opportunity_review、risk_control_review；
- Portfolio Review 和未来 Case Replay 的负反馈。

每条 failure pattern 至少包含：pattern_id、run_id、agent_id、category、description、severity、prevention_check、metadata、tags、review_before_evolution=true、real_trade_allowed=false、broker_integration=disabled。

边界：

- failure pattern 是复盘和训练材料，不是买卖信号；
- 不因单次失败直接改写 Agent 核心 Profile、风险偏好或工具权限；
- 历史错误不得删除，只能追加修正、降权或标记已处理；
- 能力升级候选必须先说明如何避免相关 failure pattern，再进入 capability regression 或人工 apply。

当 failure pattern 来自 Agent Harness 的 Skill Guardrails 违规时，Agent Learning 生成的候选必须保留原始 harness metadata，例如 source、artifact_path、blocking_issues、guardrails_applied、guardrail_safety_respected 和 score。该候选进入 EvolutionGate 前仍保持 `real_trade_allowed=false`、`broker_integration=disabled`，并且只能作为复盘、checklist 或受控能力候选，不能成为真实交易或权限升级依据。

## 6. Self Reflection

每个 Agent 在 run 结束后生成：

- what_i_believed
- what_i_got_right
- what_i_got_wrong
- missed_evidence
- reasoning_errors
- tool_usage_errors
- bias_detected
- proposed_memory_updates
- proposed_skill_updates
- proposed_principle_updates
- confidence

## 7. 防过拟合机制

升级候选不得直接因为一次成功案例被接受。EvolutionGate 应检查：

- 是否有多案例支持；
- 是否适用市场状态明确；
- 是否包含失败边界；
- 是否可测试；
- 是否与角色一致；
- 是否破坏风控；
- 是否会污染其他 Agent。

V1 的 `historical_case_replay` 只验证 pattern 是否可作为 checklist / hypothesis generator；即使回放通过，也不能产生直接买卖、直接映射标的或提高真实风险权限。

## 8. 验收标准

- 能从 run 生成 reflection 和 upgrade candidates。
- 能为 run 生成 learning/source-registry.yaml，并把组织级 registry 物化到 memory/organization。
- 能标注学习源和 source tier。
- EvolutionGate 能读取 source registry gates；缺少必要 gates 的升级候选必须 quarantine，不能直接写入长期记忆。
- 能通过 EvolutionGate 输出 accept / reject / quarantine / needs_more_evidence。
- 被接受升级能版本化写入对应 Agent 的 memory 与 evolution-ledger；principles / skillset 的直接改写必须进入后续审批流。
- 被接受的 principle / skill / checklist / workflow / tool policy 候选能进入 capability registry，并保持 pending_human_apply；被 quarantine / reject 的能力候选只进入 run 级 capability-candidates 队列。
- EvolutionGate 后必须生成 `harness/capability-regression.yaml`，并把未通过回归测试的能力候选标记为 `blocked_regression`。
- pending_human_apply 能通过 `fundos capabilities apply ... --approver ...` 受控应用到 runtime managed block 或 applied-capabilities.yaml，并记录 capability-apply-ledger；缺少 approver 时必须拒绝。
- 能从 reflections、evaluation blocking issues 和 outcome tracking 中生成 `learning/failure-patterns.yaml`，并追加到 `memory/organization/failure-pattern-library.jsonl`。
- `fundos failures summary` 能汇总组织级 failure pattern 数量、category_counts 和 severity_counts。
- 被拒绝升级保留拒绝理由，不能删除。

## Acceptance Criteria

- Source registry records learning sources, source tiers, allowed outputs, forbidden outputs, required gates, adoption policy and boundary policy.
- EvolutionGate scores source quality, testability, overfitting risk, role drift risk and risk regression risk before any durable learning.
- Accepted memory candidates write only reversible semantic memory and ledgers; capability candidates enter pending_human_apply and require regression plus human approver.
- Failure patterns from reflections, evaluation, Agent Harness and outcome tracking feed future candidates as negative examples.
- Source-controlled `agent.md` and `SKILL.md` are never mutated by automatic evolve/apply flows.
- Safety boundary: `real_trade_allowed=false`, `broker_integration=disabled`, capability upgrades cannot open broker or real-trade permissions.

## Capability Benchmark Fixture

Learning / Evolution must provide a deterministic benchmark fixture that proves capability versions can be compared before and after human-approved apply. The fixture is intentionally narrow: it tests a skill candidate for a trader Agent, but exercises the full route from candidate registry to regression, skill benchmark, approval, managed runtime block, ledger update, and after-apply snapshot.

The benchmark is not allowed to promote a KOL, book, course, or historical case into direct buy/sell evidence. Methodology and case replay remain hypothesis/checklist inputs only. A candidate that fails replay, evidence quality, role consistency, skill benchmark, or safety gates must remain blocked and cannot be applied.

## Capability Matrix Fixture

Learning Evolution includes an isolated capability matrix fixture for non-skill capability kinds and blocking cases. The fixture creates controlled `principle`, `workflow`, `checklist`, and unsafe `tool_policy` / missing-artifact candidates, runs Capability Regression, applies only human-approved non-skill candidates to runtime `agents/{agent_id}/applied-capabilities.yaml`, and verifies blocked candidates are not applied.

Output artifact: `harness/capability-matrix-fixture.yaml`.

Required checks:

- principle, workflow, and checklist candidates must pass regression and apply through the managed runtime capability path;
- protected scopes such as tool permissions must remain `blocked_regression` and require separate governance;
- candidates whose required test artifacts are missing must remain `blocked_regression`;
- blocked candidates must not appear in runtime applied capabilities;
- source-controlled Agent Cards, source Skills, Profiles, risk limits, and tool permissions must not be mutated;
- safety boundary remains `real_trade_allowed=false`, `broker_integration=disabled`.

Acceptance additions:

- `fundos harness capability-benchmark` returns pass only when before/after snapshots show a real controlled capability delta.
- `system audit --strict` includes `evolution.capability_benchmark_fixture_before_after_apply`.
- Automatic benchmark/apply flows do not mutate source-controlled `agent.md`, `SKILL.md`, tool permissions, risk limits, broker settings, or real-trade authority.

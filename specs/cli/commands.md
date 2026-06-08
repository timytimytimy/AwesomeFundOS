# AwesomeFundOS CLI Spec

## 1. 命令概览

V1 CLI 名称建议为 `fundos`。

```bash
fundos init
fundos run --topic "机器人产业链投资机会"
fundos run --stock 300750
fundos run --question "当前 A 股低空经济是否值得进入观察池？"
fundos run --topic "机器人产业链投资机会" --research-fixture examples/fixtures/robotics-public-research.json --market-replay-fixture examples/fixtures/robotics-market-replay.yaml
fundos run --topic "机器人产业链投资机会" --research-cache cache/research
fundos eval --run runs/2026-06-05-robotics
fundos evolve --run runs/2026-06-05-robotics
fundos inspect --run runs/2026-06-05-robotics
fundos roster list
fundos memory show --agent fund_manager
fundos capabilities list
fundos capabilities apply cand_2026-06-05-robotics_002 --approver human-name
fundos performance show --agent tech_growth_analyst
fundos failures summary
fundos skills export --out ./skills
fundos sources ingest --run runs/2026-06-05-robotics --fixture examples/fixtures/source-candidates.yaml
fundos cases list
fundos followups list --run runs/2026-06-05-robotics
fundos followups show --run runs/2026-06-05-robotics --task-id 2026-06-05-robotics:research_gap:001
fundos followups answer --run runs/2026-06-05-robotics --task-id 2026-06-05-robotics:research_gap:001
fundos followups close --run runs/2026-06-05-robotics --task-id 2026-06-05-robotics:research_gap:001 --evidence accepted-evidence.yaml
fundos threads show --agent fund_manager
fundos governance summary --run runs/2026-06-05-robotics
fundos system doctor
fundos system audit --strict
```

### 1.1 `fundos skills export --out <dir>`

把 source-controlled `specs/skills/*/SKILL.md` 导出为 Codex 可发现的 Skill 目录：

- 输出目录结构为 `<dir>/fundos-{agent_id}/SKILL.md`。
- 同步写入 `<dir>/awesomefundos-skills-manifest.yaml`，记录 agent_id、skill_name、source_path、target_path 和安全边界。
- 不改变 `agent.md`、Profile、Memory、Tool Permission 或风险限制。
- 导出后的 Skill 仍保持 `real_trade_allowed=false`、`broker_integration=disabled`，仅用于 research / watchlist / Paper Portfolio。

### 1.2 `fundos system doctor`

快速检查当前仓库是否可以直接交给 Codex / CLI 使用：

- 校验 `pyproject.toml` 是否声明 `fundos` console script；
- 校验默认 roster 是否可加载且包含 19 个 Agent；
- 校验每个 roster Agent 都有 source-controlled `agent.md` 和 `SKILL.md`；
- 执行 Codex Skill 导出 dry-run，确认 19 个 `fundos-*` Skill 目录可生成；
- 运行 repository-level strict audit；
- 显式输出 `doctor_status`、通过/失败检查数、`real_trade_allowed=False` 与 `broker_integration=disabled`。

任一检查失败时返回非 0；该命令不创建真实交易连接，不改写 Agent Card / Skill / Profile / Tool Permission。

## 2. `fundos init`

初始化本地目录：

```text
agents/
configs/
harness/
memory/
runs/
skills/
tools/
```

要求：

- 不覆盖已有用户文件；
- 如目录已存在，输出 skipped；
- 加载 `specs/agents/default-roster.yaml`。

## 3. `fundos run`

### 3.1 输入形式

```bash
fundos run --topic <topic>
fundos run --stock <stock_code>
fundos run --question <question>
```

### 3.2 默认行为

1. 创建 run workspace；
2. ChiefOfStaff 解析任务；
3. Agent Staffing；
4. 自主检索并生成 EvidencePack；
5. 写入 Public Research Cache / Manifest；
6. 生成 Agent-specific ContextPack；
7. 多 Agent 分析和辩论；
8. FundManager 输出模拟投委会备忘录；
9. Watchlist / Paper Portfolio / Outcome Tracking；
10. Harness 评估；
11. ReviewArchivist 归档。

### 3.3 输出目录

```text
runs/{date}-{slug}/
  run.yaml
  task-brief.md
  selected-agents.yaml
  evidence/evidence-pack.yaml
  evidence/public-research-manifest.yaml
  tools/tool-adapter-manifest.yaml
  context/{agent_id}.context-pack.yaml
  agent_work/{agent_id}.md
  debate/
  risk/
  system/operating-system-manifest.yaml
  harness/historical-case-replay.yaml
  decision/
  evaluations/
  archive/
  reflections/
  evolution/
```

`run.yaml` 必须包含参与 Agent 的 concrete `model_records`，用于审计 Codex runtime 策略是否真正落地。每条记录至少包含：agent_id、model、model_policy_id、reasoning_effort、skill_versions、tool_versions、tool_contract_id、runtime_mode、real_trade_allowed、broker_integration。V1 固定保持 `runtime_mode=local_file_protocol`、`real_trade_allowed=false`、`broker_integration=disabled`，并禁止用 stub model/tool version 代表真实 runtime 状态。

`system/operating-system-manifest.yaml` 是 run 级 Agent OS 清单，必须把 selected agents 与 source-controlled Agent Card / SKILL / ContextPolicy / ToolPolicy / MemoryPolicy、runtime model records、Thread manifest、Harness artifacts、Evolution artifacts 和安全边界连接起来。该清单用于证明本次运行加载的是一个有 Profile、Skills、Tools、Memory、Thread、Harness、Evolution 能力的组织系统，而不是一组散落的输出文件。系统还必须同步生成 `system/operating-system-manifest.md`，作为人类可读的审计摘要，方便投委会复盘、人工检查和 Codex 后续上下文压缩。

该清单结构受 `specs/schemas/operating-system-manifest.schema.yaml` 约束，必须显式声明 artifact_type、runtime_mode、selected_agent_count、model_record_count、loaded_asset_counts、agents、model_records、harness_artifacts、memory_thread_artifacts、evolution_artifacts、evolution_summary、safety_invariants、real_trade_allowed 和 broker_integration。`fundos system audit --strict --run <run>` 必须校验运行产物中的 manifest 是否满足该 schema；缺少 evolution_summary / safety_invariants 的必填字段，或违反 runtime / broker / paper-only 枚举边界时，strict audit 必须失败。

`fundos eval` 和 `fundos evolve` 必须刷新该清单。`evolve` 后 manifest 必须额外纳入 `evolution/evolution-gate-results.jsonl`、memory writeback、capability version summary、agent performance 和 agent governance artifacts，并汇总 gate_results、memory_writes、approved_candidates、pending_human_apply；这些汇总仍必须保持 `real_trade_allowed=false`、`broker_integration=disabled`。

## 4. `fundos eval --run`

重新运行 Harness，生成：

- EvaluationReport；
- Context Quality scores；
- Agent scores；
- Blocking issues。

## 5. `fundos evolve --run`

读取 reflections 和 candidates，运行 EvolutionGate，输出：

- accepted candidates；
- rejected candidates；
- quarantined candidates；
- required follow-up tests。
- memory-writeback-summary。
- capability-candidates / capability-version-summary。

默认不直接改写核心 Profile。V1 中仅当候选被 EvolutionGate 判定为 `accept`，且 target_scope / candidate_type 不涉及 core_profile、org_structure、tool_permission、risk_limit 等受保护范围时，才允许写入受控长期记忆：

```text
memory/agents/{agent_id}/semantic_memory.md
memory/agents/{agent_id}/evolution-ledger.jsonl
memory/organization/evolution-ledger.jsonl
runs/{run_id}/evolution/memory-writeback-summary.yaml
```

写回必须记录 candidate_id、run_id、source_agent、target_agent、source_basis、required_tests、scores、controls、approval_mode，并保持可审计、可回滚、不触发真实交易。

如果候选来自 Agent 推理层的 hypothesis follow-up 生命周期，`evolve` 必须把 origin metadata 继续写入 EvolutionGate 结果和 memory ledger：`source=agent_reasoning_layer`、source_agent_id、source_evidence_id、source_claim_id、hypothesis、validation_required。semantic memory 预览必须保留简短审计字段 `hypothesis_source`、`source_agent_id`、`source_evidence_id`、`source_claim_id` 和 `validation_required`，并继续显示 `real_trade_allowed=false`、`broker_integration=disabled`。任何输入 metadata 试图打开真实交易或 broker 集成都必须被清洗为 disabled。

`evolve` 还会把每个候选的 EvolutionGate 结果反写到目标 Agent 的长期 Thread：accepted / quarantined / rejected 分别追加 `evolution_candidate_accepted`、`evolution_candidate_quarantined`、`evolution_candidate_rejected`。如果 accepted 候选触发受控长期记忆写回，还会追加 `memory_writeback_applied`，payload 包含 candidate_id、approval_mode、semantic_memory_path、ledger path 和安全边界。Thread 记录的是可审计生命周期，不代表 profile、工具权限、风控或 broker 状态被自动修改。

如果候选来自 `learning/failure-patterns.yaml` 中的 `skill_guardrail_violation`，`evolve` 必须保留 Agent Harness 违规 metadata，例如 `source=agent_harness`、`artifact_path=harness/agent-harness.yaml`、blocking_issues、guardrails_applied 和 guardrail_safety_respected。该类候选只能走 checklist / workflow / memory 修复链路，不能直接修改 source-controlled Agent Card、SKILL、Tool Permission、Risk Limit、真实交易或 broker 状态。

Principle / skill / checklist / workflow / tool policy 升级候选不直接改写 `agent.md` 或 `SKILL.md`。被接受候选进入：

```text
memory/agents/{agent_id}/capabilities/{kind}.jsonl
memory/organization/capability-ledger.jsonl
runs/{run_id}/evolution/capability-candidates.jsonl
runs/{run_id}/evolution/capability-version-summary.yaml
```

默认 `application_status=pending_human_apply`。

## 6. `fundos capabilities list / apply`

`fundos capabilities list` 从本地 runtime 的 `memory/agents/*/capabilities/*.jsonl` 汇总所有 `pending_human_apply` 候选，输出 candidate_id、target_agent、capability_kind 和 registry_path。

`fundos capabilities apply <candidate_id> --approver <human>` 是 V1 的人工审批应用入口：

- `--approver` 必填；缺失时必须返回非 0；
- 只应用 `application_status=pending_human_apply` 的候选；
- 如果候选被 `harness/capability-regression.yaml` 标记为 `blocked_regression`，apply 必须拒绝；
- skill 候选只追加带 `FUNDOS_CAPABILITY:{candidate_id}` 标记的 managed block 到 runtime `skills/{agent_id}/SKILL.md`；
- principle / workflow / checklist / tool_policy 候选写入 `agents/{agent_id}/applied-capabilities.yaml`；
- 更新 registry 为 `application_status=applied`，并写入 `memory/organization/capability-apply-ledger.jsonl`；
- 不改写 source-controlled specs，不改写核心 Agent Card / Profile，不开启真实交易或券商集成。

## 7. `fundos inspect --run`

展示 run 状态、artifact 索引、Agent 参与情况、评分摘要和阻断项。

V1 输出必须包含 Agent OS 装配摘要，至少包括：

- `os_manifest` 与 `os_manifest_markdown` 路径；
- `runtime_mode`；
- `model_records` 数量；
- `all_runtime_assets`；
- `loaded_agent_assets`，覆盖 Agent Card / SKILL / ContextPolicy / ToolPolicy / MemoryPolicy；
- Harness / Memory Thread / Evolution artifact 数量；
- `evolution_gate_results` 与 `pending_human_apply`；
- `paper_portfolio_only`、`kol_is_hypothesis_only`、`real_trade_allowed`、`broker_integration` 安全边界。

## 8. `fundos roster list`

列出默认 Agent、角色、能力、ContextPolicy、ModelPolicy。

## 9. `fundos memory show --agent`

展示指定 Agent 的已接受长期记忆摘要、错误模式和能力版本历史。

V1 输出包括：

- semantic memory 路径；
- evolution ledger 路径；
- accepted lesson 数量；
- ledger entry 数量；
- latest candidate / run / candidate_type；
- approval_mode；
- reversible；
- real_trade_allowed；
- broker_integration；
- semantic memory preview。

如果目标 Agent 尚无长期记忆，命令返回非 0，并输出 `memory_not_found: {agent_id}`。

## 10. `fundos performance show --agent`

展示指定 Agent 的长期表现摘要，读取：

```text
agents/{agent_id}/performance/performance_ledger.jsonl
agents/{agent_id}/performance/evaluation_history.jsonl
agents/{agent_id}/performance/promotion_history.jsonl
```

输出 runs_evaluated、average_score、latest_score、latest_action、promote_watch_count、downgrade_watch_count。Performance 只影响组织观察、复训、降权或晋升建议，不改变真实资金权限、风险限额或交易权限。

## 11. `fundos followups list / show`

`fundos followups list --run <run>` 先 reconcile 已存在的 `follow_up/results/*.yaml`，再读取 `workflow/research-gap-tasks.yaml`，列出由 Evaluation / Research Task DAG 生成的后续研究缺口任务，包括 task_id、category、owner_agent_id、priority、status、brief_path 和 result_path。

`fundos followups show --run <run> --task-id <task_id>` 展示单个 follow-up task 的元数据和 `follow_up/research_gap_<category>.md` brief 正文，方便调度器或人类 operator 把任务交给对应 Agent 继续研究。

`fundos followups answer --run <run> --task-id <task_id>` 让任务归属 Agent 产出一个结构化 follow-up result，写入：

```text
follow_up/results/{task_id}.yaml
follow_up/results/{task_id}.md
```

V1 的 answer 不伪造缺失数据，只输出 `status=needs_evidence`、evidence_requests、source_quality_rules、context_update_request 和下一步需要 rerun 的 Harness。它用于把缺口研究变成可执行的 Agent work item，而不是直接补全事实或形成买卖结论。

`answer` 成功后会自动把结果回写到：

```text
workflow/research-gap-tasks.yaml
workflow/task-dag.yaml
harness/task-dag-harness.yaml
```

缺口任务会从 `planned` 进入 `answered_needs_evidence`，并记录 `answer_status`、`result_path`、answered/pending 计数和安全状态。若 follow-up result 违反 no-real-trade 或 broker-disabled 约束，任务进入 `answered_unsafe_blocked`，但不会获得任何真实交易能力。

同时，`answer` 会向任务归属 Agent 的长期线程追加 `research_gap_followup_answered` 事件，并刷新本 run 的 `memory/agent-thread-manifest.yaml`。事件 payload 包含 task_id、category、status、result_path 和 evidence_request_count，使垂直研究员或交易员能够在后续复盘、Memory 和 Evolution 中追踪自己曾经提出过哪些证据缺口，而不是只在单次 run 内短暂存在。

`fundos followups close --run <run> --task-id <task_id> --evidence <yaml-or-json>` 将人工或工具补齐并已验收的 EvidenceItem 写回 `evidence/evidence-pack.yaml`，更新 `research_plan_coverage`，并把对应缺口任务、Task DAG 节点和 Task DAG Harness 从 `answered_needs_evidence` 推进到：

```text
closed_by_accepted_evidence
```

`--evidence` 文件可以是 `evidence_items: [...]` 映射或 EvidenceItem 数组。close 只接受结构化 EvidenceItem，不接受自由文本观点；写回后仍保持 `real_trade_allowed=false`、`broker_integration=disabled`。被接受的 EvidenceItem 必须有 id、source_type、source_tier、summary、confidence 和非空 claims；source_tier 只能是 tier_1_primary_fact、tier_2_canonical_framework 或 tier_3_verified_public_practitioner；source_type 必须匹配该 research gap category 的可接受来源类型。低质量社媒、空 claims、错 category 或任何真实交易/broker 泄漏都会被 `evidence_validation_failed` 拒绝，不能关闭缺口。

后续再次运行 `fundos eval --run <run>` 或重新生成 Research Task DAG 时，已关闭的缺口必须继续保留在 manifest / DAG / Harness 中，不能因为 `research_plan_coverage.missing_categories` 已移除该 category 而丢失审计历史。

`close` 成功后会向原任务归属 Agent 的长期线程追加 `research_gap_followup_closed` 事件，并刷新本 run 的 `memory/agent-thread-manifest.yaml`。事件 payload 包含 task_id、category、closure_status、accepted_evidence_count、accepted_evidence_ids、closed_count 和 pending_count；如果任务来自 `reasoning_layers.hypotheses_to_validate`，还必须保留 source、source_agent_id、source_evidence_id、source_claim_id、hypothesis 和 validation_required。该线程事件只记录研究学习闭环，不改变 Agent profile、权限、真实资金动作或 broker 状态。

Evaluation 会把已关闭缺口作为一等 Harness 信号：`research_gap_followup_quality` 输出 `closed_count`、`closed_categories`、`accepted_evidence_count` 和 `accepted_evidence_ids`，并在 `accepted_outputs` 中加入 `research_gap_closures`。关闭缺口会提高 `dimension_scores.research_gap_followup`，但仍不产生真实交易权限。

约束：

- follow-up task 只能产生研究 brief、证据请求和 source-quality notes；
- 不允许真实交易指令；
- 不允许 broker action / order placement；
- 没有补齐证据前不得升级为高置信结论。

## 12. `fundos failures summary`

展示组织级 Failure Pattern Library 摘要，读取：

```text
memory/organization/failure-pattern-library.jsonl
```

输出 pattern_count、category_counts、severity_counts、latest_pattern_id、review_before_evolution、real_trade_allowed=false 和 broker_integration=disabled。

Failure Pattern Library 只用于复盘、复训、能力升级候选评估和 Harness 负反馈，不得解释为交易信号，也不得触发真实交易动作。

如果 Agent Harness 发现 Skill Guardrails 未被应用或安全边界未被遵守，`fundos failures summary` 的来源库中应出现 `skill_guardrail_violation` category；后续 `fundos evolve --run` 会把它转成可审计 Agent Learning Candidate，并继续保持 no-real-trade / broker-disabled 边界。

## 13. `fundos sources ingest --run --fixture`

把外部学习源候选摄取到指定 run workspace，用于从知名交易员、研究员、公开大V、课程、书籍和历史案例中提炼能力，但所有材料必须先进入隔离与评测流程。

输入 fixture 可以是 YAML list，也可以是：

```yaml
candidates:
  - source_id: serenity_x_thread_robotics
    display_name: Serenity robotics X thread
    source_type: public_practitioner
    url: https://x.com/aleabitoreddit/status/123
    author: Serenity
    summary: 机器人产业链瓶颈研究思路
    claims:
      - 先从系统架构找瓶颈，再映射公司
    requested_outputs: [research_lens, checklist]
    target_agents: [tech_growth_analyst]
```

输出：

```text
runs/{run_id}/learning/source-ingestion-report.yaml
runs/{run_id}/learning/source-candidates.jsonl
runs/{run_id}/learning/source-quarantine.jsonl
runs/{run_id}/learning/pattern-candidates.jsonl
runs/{run_id}/evolution/candidates.jsonl
```

约束：

- 所有 pattern candidate 初始状态必须是 `quarantine`；
- KOL / social / practitioner 来源只能作为研究 lens、checklist、hypothesis 或 failure pattern，不能形成直接买卖信号；
- 课程和书籍只能保留 metadata、URL、用户自写摘要和抽象模式，不能复制付费文本；
- 进入 Evolution 的候选只能是 `status=proposed`，必须包含 historical case replay、primary evidence check、role drift check、evidence quality check 等 gates；
- 不开启真实交易，不接券商，不自动下单。

## 13. `fundos cases list`

展示 source-controlled Historical Case Library 摘要，包括 case_count、case_type_counts、agent_case_counts、real_trade_allowed=false 和 broker_integration=disabled。

Case Library 只用于训练、复盘、评测和 EvolutionGate，不得把单个历史案例直接映射成买卖信号。

## 14. `fundos threads show --agent`

展示指定 Agent 的长期 Thread 摘要，读取：

```text
memory/agents/{agent_id}/thread.yaml
memory/agents/{agent_id}/thread-events.jsonl
```

输出包括 thread_id、event_count、latest_event_type、latest_run_id、continuity_scope、real_trade_allowed 和 broker_integration。

Agent Thread 是每个 Agent 的长期身份和连续性日志，不等同于自动记忆写入；能力或记忆升级仍必须通过 EvolutionGate / capability approval。

## 15. `fundos governance summary --run`

展示指定 run 的 Agent Governance 摘要，读取：

```text
runs/{run_id}/harness/agent-governance.yaml
memory/organization/agent-governance-ledger.jsonl
agents/{agent_id}/governance/seat-history.jsonl
```

Governance 用于晋升观察、降权观察、复训、席位竞争和组织学习，不改变真实资金权限、不删除记忆、不改写核心 Profile，不开启真实交易。

## 16. 全局合规要求

所有 `fundos run` 输出必须包含：

```text
研究分析，不构成投资建议；不接真实交易，不自动下单。
```

## 17. Tool Adapter Contracts

V1 的工具层先以 source-controlled contract 固化，不直接接券商、不下单、不写真实交易。运行 `fundos init`、`fundos run`、`fundos eval` 时会生成：

```text
tools/tool-adapter-manifest.yaml
```

该 manifest 校验默认 Agent 声明的工具是否都映射到只读 adapter contract，并检查 `real_trade_allowed=false`、`broker_integration=disabled`、ToolResult / Evidence traceability。

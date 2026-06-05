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
fundos sources ingest --run runs/2026-06-05-robotics --fixture examples/fixtures/source-candidates.yaml
fundos cases list
fundos threads show --agent fund_manager
fundos governance summary --run runs/2026-06-05-robotics
```

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
  harness/historical-case-replay.yaml
  decision/
  evaluations/
  archive/
  reflections/
  evolution/
```

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

## 11. `fundos failures summary`

展示组织级 Failure Pattern Library 摘要，读取：

```text
memory/organization/failure-pattern-library.jsonl
```

输出 pattern_count、category_counts、severity_counts、latest_pattern_id、review_before_evolution、real_trade_allowed=false 和 broker_integration=disabled。

Failure Pattern Library 只用于复盘、复训、能力升级候选评估和 Harness 负反馈，不得解释为交易信号，也不得触发真实交易动作。

## 12. `fundos sources ingest --run --fixture`

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

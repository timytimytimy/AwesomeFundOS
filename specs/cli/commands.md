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

## 11. 全局合规要求

所有 `fundos run` 输出必须包含：

```text
研究分析，不构成投资建议；不接真实交易，不自动下单。
```

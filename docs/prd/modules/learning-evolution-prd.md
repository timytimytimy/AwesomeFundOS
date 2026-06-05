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

每次写回必须包含：candidate_id、run_id、source_agent、target_agent、candidate_type、target_scope、proposal、source_basis、required_tests、scores、controls、approval_mode、reversible、real_trade_allowed=false、broker_integration=disabled。

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

## 8. 验收标准

- 能从 run 生成 reflection 和 upgrade candidates。
- 能标注学习源和 source tier。
- 能通过 EvolutionGate 输出 accept / reject / quarantine / needs_more_evidence。
- 被接受升级能版本化写入对应 Agent 的 memory 与 evolution-ledger；principles / skillset 的直接改写必须进入后续审批流。
- 被拒绝升级保留拒绝理由，不能删除。

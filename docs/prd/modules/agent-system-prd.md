# Agent System PRD

## 1. 模块目标

Agent System 负责定义、加载、运行和维护 AwesomeFundOS 中的长期 Agent。每个 Agent 都应是可配置、可记忆、可评估、可进化的独立个体，而不是一段一次性 Prompt。

## 2. 核心对象

### 2.1 AgentProfile

描述 Agent 的身份、角色、风格、风险偏好、能力边界、偏见、弱点和成长记录。

必备字段：

- `id`
- `name`
- `role`
- `mandate`
- `investment_style`
- `risk_preference`
- `time_horizon`
- `personality`
- `decision_principles`
- `capability_boundaries`
- `biases`
- `weaknesses`
- `skills`
- `tools`
- `context_policy_id`
- `model_policy_id`
- `memory_namespace`
- `performance_metrics`

### 2.2 Agent Runtime State

记录当前 Agent 在一次 Run 中的执行状态。

- selected / not_selected
- assigned_task
- context_pack_id
- output_artifact_ids
- tool_calls
- evaluation_scores
- reflection_status

### 2.3 Agent Memory

每个 Agent 拥有独立记忆：

```text
memory/agents/{agent_id}/
  episodic_memory.jsonl
  semantic_memory.md
  case_memory.jsonl
  mistake_memory.jsonl
  market_state_memory.jsonl
```

### 2.4 Performance Ledger

每个 Agent 拥有长期绩效账本：

```text
agents/{agent_id}/performance/performance_ledger.jsonl
agents/{agent_id}/performance/evaluation_history.jsonl
agents/{agent_id}/performance/promotion_history.jsonl
```

V1 需要由 `fundos evolve --run` 生成 run 级 performance artifact：

```text
runs/{run_id}/harness/agent-performance.yaml
```

Performance Harness 根据 `agent-harness.yaml` 和 `evaluation-report.yaml` 为每个参与 Agent 记录 context_compression、skill_invocation、role_consistency、contribution_quality、context_fit、harness_overall 和 final_score，并给出：

- `promote_watch`：进入晋升观察，不改变核心权限；
- `maintain`：保持当前职责；
- `retrain_or_downgrade_watch`：进入复训或降权观察；
- `needs_more_observations`：证据不足，继续观察。

所有 promotion / demotion 都只是组织层建议：不得改变真实资金权限、risk_limit、tool_permission、core_profile，也不得删除长期记忆。

## 3. 默认 Agent Roster

V1 默认 19 个 Agent，详见 `specs/agents/default-roster.yaml`。

### 核心运营 Agent

- chief_of_staff
- fund_manager
- risk_manager
- bear_debater
- learning_curator
- evaluation_harness
- review_archivist

### 研究员池

- tech_growth_analyst
- advanced_manufacturing_analyst
- consumer_healthcare_analyst
- cyclical_macro_analyst
- policy_event_analyst

### 公司研究员池

- quality_growth_company_analyst
- turnaround_value_company_analyst
- fraud_governance_analyst

### 交易员池

- position_trend_trader
- swing_trader
- event_driven_trader
- defensive_execution_trader

## 4. Agent Staffing System

### 4.1 目标

根据用户问题、市场、行业、周期、风险和所需能力，动态选择 7-10 个 Agent 参与一次投委会。

### 4.2 强制参与 Agent

- chief_of_staff
- fund_manager
- risk_manager
- bear_debater
- evaluation_harness
- review_archivist

LearningCurator 可在学习和进化阶段参与，不必每次前置参与。

### 4.3 选择规则

输入：

- market
- asset_type
- sector
- topic_type
- investment_horizon
- catalyst_type
- required_analysis
- risk_type

输出：

- selected_agents
- selection_reason
- excluded_agents_summary
- max_agents_per_run

## 5. Agent 权限边界

Agent 可以：

- 执行分配任务；
- 调用授权工具；
- 读取分配的 ContextPack；
- 提出 Memory / Principle / Skill / Workflow 升级候选；
- 进行自我复盘。

Agent 不可以：

- 未经 Harness 直接修改核心 Profile；
- 越权读取未分配上下文；
- 修改其他 Agent 记忆；
- 跳过风控、反方或 Harness；
- 生成真实投资建议或交易指令；
- 删除历史错误记录。

## 6. 验收标准

- 能从默认 Roster 加载 19 个 Agent。
- 每个 Agent 有 Profile、ContextPolicy、ModelPolicy、Skillset 和 Tool policy。
- 每次 run 能动态选择 7-10 个 Agent，并记录选择原因。
- 每个 Agent 输出都能绑定 context_pack_id、skill_versions、tool_versions、model_policy。
- Harness 能按 Agent 维度评分。
- Harness 能检查 Agent Card / Skill Contract / ContextPack / structured output 的一致性，并生成 `harness/agent-harness.yaml`。

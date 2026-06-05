# AwesomeFundOS Codex Implementation Plan

## 1. 实现原则

- 先实现 Local-first CLI 和文件协议，不先做 Web App。
- 先实现可运行的最小闭环，再扩展真实数据源和更复杂 Harness。
- 所有 artifacts 使用 Markdown + YAML/JSON，便于 Codex 读取和修改。
- 所有重要结论必须可追溯到 Evidence ID / Claim ID。
- V1 输出模拟投委会研究备忘录，不输出真实投资建议。

## 2. Phase 0: Repo Scaffold

目标：创建运行时目录和基础配置。

任务：

1. 创建目录：
   - `agents/`
   - `configs/`
   - `harness/`
   - `memory/`
   - `runs/`
   - `skills/`
   - `tools/`
2. 将 `specs/agents/default-roster.yaml` 转为可加载配置。
3. 增加基础 README 和开发说明。
4. 选择实现语言。建议：Python 优先，便于 CLI、YAML、文件处理和后续工具集成。

验收：

- `fundos init` 可创建目录且幂等。
- 能读取默认 roster 并打印 Agent 列表。

## 3. Phase 1: Core CLI and Run Workspace

目标：实现 `fundos run` 的文件级骨架。

任务：

1. 实现 CLI 入口。
2. 支持 `--topic`、`--stock`、`--question`。
3. 创建 run_id 和 run workspace。
4. 写入 `run.yaml` 和 `task-brief.md`。
5. 实现 Agent Staffing 的规则引擎第一版。
6. 写入 `selected-agents.yaml`。

验收：

- 命令能创建完整 run 目录。
- 不联网也能生成任务简报和选人结果。

## 4. Phase 2: EvidencePack Stub + Public Retrieval Interface

目标：先实现 EvidencePack 数据结构和工具接口，再逐步接真实数据源。

任务：

1. 实现 EvidencePack schema validator。
2. 实现 ToolResult -> EvidenceItem 转换器。
3. 实现占位工具：
   - web_search
   - news_search
   - announcement_search
   - financial_report_parser
   - market_data_query
   - case_library_reader
4. 为每个 EvidenceItem 打 source_tier。
5. 抽取 Claim。

验收：

- 给定 mock tool results 能生成合法 EvidencePack。
- EvidencePack 中每个 claim 有 id、type、confidence。

## 5. Phase 3: Context Manager

目标：实现 EvidencePack -> Agent-specific ContextPack。

任务：

1. 定义 ContextPolicy 配置。
2. 实现按 source_type / source_tier / relevant_to / task_stage 过滤。
3. 实现压缩摘要接口。
4. 生成每个 selected agent 的 ContextPack。
5. 保留 contradiction_table 和 missing_evidence。

验收：

- 每个 selected agent 都有 ContextPack。
- 行业、公司、交易、风控、反方获得不同上下文。
- ContextPack 能回链 Evidence ID / Claim ID。
- `harness/agent-harness.yaml` 能评估 ContextPack 的压缩、追溯、矛盾保留和噪声控制。

## 6. Phase 4: Agent Output Protocol

目标：先用文件协议定义 Agent 输出，不急于接复杂并发 Agent Runtime。

任务：

1. 为每类 Agent 定义输出模板。
2. 实现 prompt/render 层，将 Profile + ContextPack + OutputSchema 组合成任务指令。
3. 支持 Codex SDK 或本地 LLM 调用占位接口。
4. 保存 `agent_work/{agent_id}.md` 和 `.structured.yaml`。
5. 检查输出是否引用证据。

验收：

- 每个 selected agent 可生成结构化输出文件。
- 输出违反角色边界时能被标记。
- Agent-level Harness 能检查 Agent Card、Skill Contract、Role Checklist、Evidence Rules 和 structured output 的一致性。

## 7. Phase 5: Debate, Risk Review, Final Memo

目标：完成模拟投委会主流程。

任务：

1. BearDebater 读取研究输出并生成 issue table。
2. RiskManager 生成 risk review。
3. FundManager 读取所有输出并生成 final decision memo。
4. 使用 `decision-memo.schema.yaml` 校验结构化备忘录。
5. 输出 disclaimer。

验收：

- 每次 run 都生成 final decision memo。
- Memo 包含决策标签、触发条件、kill criteria、证据引用。

## 8. Phase 6: Harness V1

目标：实现 Runtime Quality + Context Quality + Evolution Gate 的基础评分。

任务：

1. 实现 EvaluationReport schema validator。
2. 实现规则型检查：
   - source coverage
   - tool / source adapter coverage
   - missing evidence
   - role consistency keywords / schema checks
   - forbidden investment advice language
   - context traceability
3. 实现 LLM-as-judge 接口，用于推理质量、协作质量和决策质量评分。
4. 输出 EvaluationReport。
5. 实现 blocking issue 机制。

验收：

- `fundos eval --run` 可生成评分报告。
- `harness/tool-harness.yaml` 能评估 public research、一手来源覆盖、KOL/社媒边界和高置信阻断。
- 缺来源、缺反方、缺风控、真实交易指令等问题会被阻断。

## 9. Phase 7: Reflection and EvolutionGate

V1 增加 Learning Source Registry：

- `fundos init` 物化 `memory/organization/learning-source-registry.yaml`。
- `fundos run` 物化 `learning/source-registry.yaml`。
- EvolutionGate 读取 registry 中的 `required_gates_for_evolution`，引用 KOL / 大V / 书籍 / 课程 / 案例的候选如果缺少必要 gate，必须 quarantine。

目标：实现 Agent 自我复盘和受控进化。

任务：

1. 为每个 Agent 生成 reflection。
2. 提取 evolution candidates。
3. 实现 EvolutionGate 规则：
   - source_quality
   - testability
   - overfitting_risk
   - role_drift_risk
   - risk_regression_risk
4. 将 accepted / rejected / quarantined 结果写入 evolution 目录。
5. accepted 后只写入非核心能力文件，不改 core profile。

验收：

- `fundos evolve --run` 能处理 candidates。
- 低质量或不可测试候选会被拒绝。
- 被接受候选有版本记录。

## 10. Phase 8: Watchlist / Paper Portfolio Review

目标：追踪后验，不做真实交易。

任务：

1. 定义 WatchlistItem schema。
2. 定义 PaperPortfolioAction schema。
3. 从 DecisionMemo 写入观察池动作。
4. 支持后续 review_date。
5. 生成 Portfolio Review、Attribution JSONL 和 Review Learning Candidates。
6. outcome tracking 支持离线 market replay fixture，V1 记录 return、drawdown、MFE/MAE、missed opportunity / risk review，不接真实交易。

验收：

- simulated_long_candidate / watchlist 等结果能写入 stub。
- `portfolio/portfolio-review.yaml`、`portfolio/attribution.jsonl`、`portfolio/review-candidates.jsonl` 能随 run / eval 生成。
- Harness 输出 `portfolio_review_quality`。
- Harness 输出 `outcome_tracking_quality`。
- 不产生真实下单指令。

## 11. Phase 9: Capability Regression / Human Apply

目标：让 Agent 能力可以自我学习并升级，但升级前必须通过回归测试和人工审批。

任务：

1. EvolutionGate 接受的 principle / skill / checklist / workflow / tool_policy 候选进入 capability registry。
2. 生成 `harness/capability-regression.yaml`，检查 required_tests 对应的 historical case replay、agent harness、evidence quality 等产物。
3. 未通过回归的候选标记为 `blocked_regression`，并追加 follow-up tests。
4. 通过回归的候选保持 `pending_human_apply`。
5. `fundos capabilities apply <candidate_id> --approver <human>` 只允许人工审批后受控写入 runtime managed block 或 `applied-capabilities.yaml`。

验收：

- `fundos evolve --run` 生成 capability registry 和 `harness/capability-regression.yaml`。
- 缺少 required_tests artifact 的候选不能被 apply。
- 缺少 `--approver` 时 apply 返回非 0。
- 不改写 source-controlled `agent.md` / `SKILL.md`，不改写核心 profile / risk limit / tool permission。
- 不开启真实交易或券商集成。

## 12. 后续 V2

- 接入稳定公开数据源；
- Codex App Server dashboard；
- 更完整的历史案例库；
- 多市场 Market Adapter；
- 更细粒度 Skill version regression benchmark；
- 更完整的 Agent promotion / demotion 审批、席位竞争和长期绩效归因；
- 多 FundManager 风格竞争；
- 组合级 Paper Portfolio performance attribution。

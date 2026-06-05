# AwesomeFundOS V1 整体 PRD

## 1. 背景

AwesomeFundOS 是一个基于 Codex CLI、Codex SDK、Codex App Server、Threads、Skills、Harness 等能力构建的多 Agent 投资组织操作系统。系统灵感来自小型主观私募基金，而不是量化基金。它不以因子、回测和自动交易为核心，而是试图模拟顶级主观交易员、基金经理、研究员和投委会的组织化决策过程。

## 2. 产品愿景

构建一个可进化的多 Agent 投资组织。每个 Agent 都是具有长期身份、人格、能力边界、记忆、绩效记录和成长路径的独立个体。系统通过公开资料检索、案例学习、投委会辩论、Harness 评估和受控进化机制，不断积累组织经验，提升主观投资研究与决策质量。

## 3. V1 目标

V1 验证一个最小但完整的组织闭环：

1. 用户只输入投资问题，不提供材料。
2. 系统自主检索公开数据、公告、财报、新闻、历史案例和学习源。
3. 系统形成 EvidencePack，并为不同 Agent 压缩生成专属 ContextPack。
4. 多个长期 Agent 按角色完成行业、公司、交易、风控、反方和最终决策工作。
5. FundManager 输出模拟投委会研究决策备忘录。
6. Harness 评估证据、推理、角色一致性、协作、工具使用、上下文质量和能力升级候选。
7. ReviewArchivist 归档运行结果，LearningCurator 提炼学习候选。
8. EvolutionGate 审核 Memory、Principles、Skills、Checklists、Workflows、Tool Policies 的升级候选。

## 4. 非目标

V1 不做：

- 真实投资建议；
- 自动交易；
- 券商接口；
- 实时盘口和 tick 数据；
- 完整 Web App；
- 大规模统计显著性回测；
- 未经审核的 Agent 自我改写；
- 付费课程或受版权保护书籍的全文抓取。

## 5. 默认市场范围

```yaml
default_market: CN_A_SHARE
supported_markets_v1:
  - CN_A_SHARE
future_markets:
  - HK_STOCK
  - US_STOCK
  - ETF
  - COMMODITY
  - CRYPTO
```

系统应通过 Market Adapter 预留扩展能力，但 V1 只要求 A 股场景可用。

## 6. V1 用户场景

### 6.1 主题研究

```bash
fundos run --topic "机器人产业链投资机会"
```

系统自主识别主题、检索资料、选择相关研究员和交易员，输出投委会备忘录和观察池动作。

### 6.2 个股研究

```bash
fundos run --stock 300750
```

系统自主拉取股票资料、公告、财报、新闻、价格摘要、行业上下文和风险案例，输出模拟研究决策。

### 6.3 投资问题

```bash
fundos run --question "当前 A 股低空经济是否值得进入观察池？"
```

系统以问题为中心进行自主检索、辩论和评估。

### 6.4 学习与进化

```bash
fundos evolve --run runs/2026-06-05-robotics
```

系统从当次运行中提取复盘、错误、经验和 Skill 候选，交由 EvolutionGate 评估。

## 7. 默认 Agent 组织

V1 默认内置 19 个 Agent，但每次运行动态选择 7-10 个参与。

### 7.1 核心运营 Agent

- ChiefOfStaffAgent / OrchestratorAgent
- FundManagerAgent
- RiskManagerAgent
- BearDebaterAgent
- LearningCuratorAgent
- EvaluationHarnessAgent
- ReviewArchivistAgent

### 7.2 行业 / 主题研究员

- TechGrowthAnalyst
- AdvancedManufacturingAnalyst
- ConsumerHealthcareAnalyst
- CyclicalMacroAnalyst
- PolicyEventAnalyst

### 7.3 公司研究员

- QualityGrowthCompanyAnalyst
- TurnaroundValueCompanyAnalyst
- FraudAndGovernanceAnalyst

### 7.4 交易员

- PositionTrendTrader
- SwingTrader
- EventDrivenTrader
- DefensiveExecutionTrader

## 8. Agent 模型

每个 Agent 是 Persistent Autonomous Agent，包含：

- Profile；
- Skills；
- Tools；
- ContextPolicy；
- ModelPolicy；
- Persistent Thread；
- Memory；
- Performance Ledger；
- Reflection Log；
- Evolution Candidates；
- Accepted / Rejected Upgrade History。

Agent 可以自主提出 Memory、Decision Principles、Skills、Checklists、Workflows 和 Tool Policies 的升级候选，但不能直接修改 Core Profile、权限、组织结构或 Harness 标准。

## 9. 数据与证据原则

V1 采用 public-data-first，自主检索，强制引用，可缓存，可插拔工具原则。

所有重要结论必须追溯到 EvidencePack 中的 Evidence ID 和 Claim ID。系统必须区分：

- 一手事实；
- 二手分析；
- 已验证公开实践者方法论；
- 专家观点；
- 社媒信号；
- 未验证传闻；
- Agent 推断。

## 10. 学习系统

系统从以下来源学习：

- 知名交易员；
- 知名基金经理；
- 知名研究员；
- 已验证公开实践者和大 V；
- 经典交易书籍和合法摘要；
- 公开课程材料和用户拥有的笔记；
- 经典交易案例；
- 历史失败案例；
- A 股市场状态案例。

V1 使用小而精 Seed Library，默认包含 Serenity / aleabitoreddit、里海、少数经典交易投资框架和经典案例类型。

## 11. Source Quality Tier

```yaml
source_tiers:
  tier_1_primary_fact: 一手事实和原始材料
  tier_2_canonical_framework: 经典且可反复验证的投资框架
  tier_3_verified_public_practitioner: 经市场长期验证的公开投资实践者 / 大V / 研究者
  tier_4_expert_opinion: 专家、研究员、基金经理公开观点
  tier_5_social_signal: 普通社媒、大V、社区、论坛、短视频
  tier_6_unverified: 匿名、传闻、不可追溯内容
```

Serenity / aleabitoreddit 属于 `tier_3_verified_public_practitioner`，可作为方法论源、研究视角源、案例选择源和 Skill 候选源，但不能直接作为公司事实或最终交易依据。

## 12. Context Management 原则

垂直 Agent 是 context-shaped agents。不同 Agent 不应看到同一份无差别上下文。系统必须通过 Context Manager 将 EvidencePack 压缩路由为 Agent-specific ContextPack。

ContextPack 必须保留：

- Evidence ID；
- Claim ID；
- 证据等级；
- 关键矛盾；
- 缺失证据；
- 任务边界；
- 输出 schema。

## 13. Harness 分层

V1 Harness 必须实现：

1. Runtime Quality Harness；
2. Evolution Gate Harness；
3. Context Quality Harness。

V1 轻量设计：

- Outcome Tracking Schema；
- Watchlist Tracking；
- Paper Portfolio Stub。

## 14. Thread 设计

采用 Agent Persistent Thread + Run Workspace 混合模式。

- Agent Persistent Thread 保存身份、长期原则、已接受经验、绩效摘要和能力版本历史。
- Run Workspace 保存当次用户问题、证据、上下文包、Agent 输出、辩论过程、决策备忘录、评估报告和升级候选。
- 只有通过 EvolutionGate 的内容才能写回长期记忆。

## 15. 输出形态

V1 输出模拟投委会研究决策备忘录，包括：

- 投资问题重述；
- 核心结论；
- 行业分析；
- 公司分析；
- 交易结构；
- 风控意见；
- 反方意见；
- FundManager 最终模拟决策；
- 观察池 / Paper Portfolio 动作；
- 触发条件；
- 降级 / 退出条件；
- Harness 评分；
- 复盘和升级候选。

所有输出必须包含：研究分析，不构成投资建议。

## 16. 成功指标

V1 成功不是短期收益，而是：

- 每次运行能自主检索并形成 EvidencePack；
- Agent 输出符合角色边界；
- 重要结论可追溯；
- 反方和风控能实质影响最终结论；
- Harness 能指出具体缺陷；
- Agent 能提出可测试的升级候选；
- EvolutionGate 能拒绝低质量升级；
- 运行结果可复盘、可重现、可迭代。

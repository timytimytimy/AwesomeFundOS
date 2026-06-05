# AwesomeFundOS 第一版结果报告

研究分析，不构成投资建议；不接真实交易，不自动下单。

## 系统能力总览

- 默认 Agent roster：19 个独立角色。
- 本次示例动态选择 Agent：9 个，包含 chief_of_staff, fund_manager, risk_manager, bear_debater, evaluation_harness, review_archivist, tech_growth_analyst, quality_growth_company_analyst, position_trend_trader。
- 已实现模块：CLI run/init/eval/evolve/report、EvidencePack、ContextPack、结构化 Agent 输出、模拟投委会 Memo、Harness Evaluation、Historical Case Replay、Watchlist/Paper Portfolio Review、EvolutionGate、Learning Pattern 蒸馏。
- V1 范围：本地优先、模拟投委会、观察池/Paper Portfolio，不接真实交易、不自动下单。

## Agent Runtime Assets

- 每个 Agent 都有 source-controlled `agent.md / SKILL.md`，并在运行时进入 ContextPack 与结构化输出。
- agent.md 数量：19。
- SKILL.md 数量：19。

## 学习源与蒸馏 Pattern

- Seed learning sources：10 个。
- Run-scoped distilled patterns：6 个。
- Pattern IDs：a_share_theme_diffusion_case, howard_marks_cycle_risk, lihai_a_share_market_state, serenity_scheme_first_chokepoint, oneil_canslim_growth, minervini_trend_template

### 代表性学习源

- serenity_aleabitoreddit / Serenity / aleabitoreddit / tier_3_verified_public_practitioner
- lihai_a_share / 里海 A股交易框架 / tier_3_verified_public_practitioner
- howard_marks / Howard Marks / Oaktree memos / tier_2_canonical_framework
- druckenmiller / Stan Druckenmiller / tier_2_canonical_framework
- soros_reflexivity / George Soros / Reflexivity / tier_2_canonical_framework
- livermore / Jesse Livermore / tier_2_canonical_framework
- william_oneil_canslim / William O'Neil / CAN SLIM / tier_2_canonical_framework
- mark_minervini / Mark Minervini / Trend Template / SEPA / tier_2_canonical_framework
- peter_lynch / Peter Lynch / tier_2_canonical_framework
- buffett_munger / Buffett / Munger / tier_2_canonical_framework

## 示例运行：机器人产业链投资机会

- run_id：2026-06-06-cn-topic
- market：CN_A_SHARE
- final label：continue_research
- stance：constructive
- conviction：low
- hypothetical_position_range：0%，仅进入观察和研究队列

### Evidence Coverage

- source_type：policy=2, financial_report=1, market_data=1, practitioner_source=2, book_summary=5, learning_pattern=6, announcement=1, web=2, case=1
- source_tier：tier_1_primary_fact=5, tier_3_verified_public_practitioner=4, tier_2_canonical_framework=10, tier_4_expert_opinion=1, tier_5_social_signal=1

### Agent Learning Pattern 示例

- bear_debater：stance=cautious_attack，confidence=medium，patterns=a_share_theme_diffusion_case, howard_marks_cycle_risk, serenity_scheme_first_chokepoint
- chief_of_staff：stance=constructive_but_evidence_capped，confidence=medium，patterns=none
- evaluation_harness：stance=constructive_but_evidence_capped，confidence=medium，patterns=none
- fund_manager：stance=continue_research，confidence=medium，patterns=a_share_theme_diffusion_case, howard_marks_cycle_risk
- position_trend_trader：stance=wait_for_price_confirmation，confidence=medium，patterns=lihai_a_share_market_state, minervini_trend_template, oneil_canslim_growth
- quality_growth_company_analyst：stance=constructive_but_evidence_capped，confidence=medium，patterns=oneil_canslim_growth

### Agent Card / Skill Runtime 示例

- bear_debater：agent_card=specs/agents/agent-cards/bear_debater/agent.md；skill=specs/skills/bear_debater/SKILL.md；checklist_items=4
- chief_of_staff：agent_card=specs/agents/agent-cards/chief_of_staff/agent.md；skill=specs/skills/chief_of_staff/SKILL.md；checklist_items=4
- evaluation_harness：agent_card=specs/agents/agent-cards/evaluation_harness/agent.md；skill=specs/skills/evaluation_harness/SKILL.md；checklist_items=4
- fund_manager：agent_card=specs/agents/agent-cards/fund_manager/agent.md；skill=specs/skills/fund_manager/SKILL.md；checklist_items=4
- position_trend_trader：agent_card=specs/agents/agent-cards/position_trend_trader/agent.md；skill=specs/skills/position_trend_trader/SKILL.md；checklist_items=4
- quality_growth_company_analyst：agent_card=specs/agents/agent-cards/quality_growth_company_analyst/agent.md；skill=specs/skills/quality_growth_company_analyst/SKILL.md；checklist_items=4

## Watchlist / Paper Portfolio

- watchlist_items：1
- paper_actions：1
- reviewed_actions：1
- attribution_items：1
- review_learning_candidates：1
- review_verdict：paper_review_recorded
- real_trade_allowed：False
- artifact_paths：portfolio/watchlist.yaml；portfolio/paper-portfolio.yaml；portfolio/portfolio-actions.jsonl；portfolio/portfolio-review.yaml；portfolio/attribution.jsonl；portfolio/review-candidates.jsonl


## 投委会 Memo 摘要

- Thesis：机器人产业链投资机会 已有 2 条 fixture/public 一手证据线索和 4 条公开检索结果进入 EvidencePack；仍需真实公告、财报、行情和案例回放继续验证。
- Bull case：若一手公告、政策和产业证据继续确认需求、订单、核心零部件瓶颈和公司映射，研究优先级可提升。
- Bear case：社媒热度和方法论源不能替代订单、收入、客户和价格行为验证；若只有叙事则不得升级。
- Risk review：主要风险是证据链不完整、低等级信号污染、产业链映射过度推断、价格序列缺失。
- Kill criteria：缺少一手证据; 关键假设被公告或财报证伪; 反方和风控提出未解决阻断项; 社媒热度成为主要依据

## Harness / Evaluation

- overall_score：77.7
- dimension_scores：evidence_quality=95, reasoning_quality=70, role_consistency=82, decision_quality=72, collaboration_quality=75, tool_usage_quality=70, context_quality=80, historical_case_replay=74.8
- context_quality_scores：relevance=82, compression_fidelity=78, evidence_traceability=86, role_specificity=82, information_sufficiency=70, noise_control=84, leakage_control=85, contradiction_preservation=80
- portfolio_quality：watchlist_items=1, paper_actions=1, real_trade_violations=0, review_dates_present=1
- portfolio_review_quality：reviewed_actions=1, attribution_items=1, learning_candidates=1, real_trade_violations=0, review_verdict=paper_review_recorded
- case_replay_quality：patterns_replayed=3, case_results_total=9, passed_results=8, high_overfit_results=1, case_replay_score=74.8
- historical_case_replay：patterns_replayed=3, case_results_total=9, case_replay_score=74.8
- blocking_issues：none

## EvolutionGate

- decision counts：quarantine=1, accept=1
- memory_writes：1
- approval_mode：evolution_gate_v1_auto_controlled
- agent_writes：fund_manager=1
- written_paths：memory/agents/fund_manager/evolution-ledger.jsonl; memory/agents/fund_manager/semantic_memory.md; memory/organization/evolution-ledger.jsonl
- cand_2026-06-06-cn-topic_001：quarantine，scores=source_quality=75, testability=95, overfitting_risk=25, role_drift_risk=20, expected_value=80，memory_write_allowed=False
- portfolio_review_ppa_2026-06-06-cn-topic_001：accept，scores=source_quality=85, testability=95, overfitting_risk=40, role_drift_risk=20, expected_value=65，memory_write_allowed=True

## V2 Gaps

- 接入真实公告、财报、交易所问询、互动易和政策数据源。
- 接入真实行情/价格序列，支持买点、卖点、仓位和 drawdown 的可评测判断。
- 扩展历史案例库与 outcome tracking，让回放从小型内置案例升级为多市场状态、多行业、多失败模式的后验评测。
- 将 Paper Portfolio Review 从过程归因扩展为接入真实行情后的定期 outcome tracking。
- 将 EvolutionGate V1 自动受控写回升级为更完整的人工/规则审批流、回滚 UI 和长期绩效归因。

## 可重复运行命令

```bash
python3 -m fundos.cli init
python3 -m fundos.cli run --topic '机器人产业链投资机会' --research-fixture examples/fixtures/robotics-public-research.json
python3 -m fundos.cli evolve --run runs/<run_id>
python3 -m fundos.cli report --run runs/<run_id> --out reports/first-version-result.md
```


# Evidence System PRD

## 1. 模块目标

Evidence System 负责从公开来源自主检索、抽取、分级、缓存和结构化证据，为多 Agent 投资决策提供可追溯事实基础。

## 2. 数据策略

V1 用户不提供材料。系统必须自主检索：

- 公司公告；
- 财报；
- 交易所信息；
- 官方政策；
- 新闻；
- 行业资料；
- 价格和成交摘要；
- 历史案例；
- 学习源和方法论源。

V1 不要求：

- 实时 tick；
- 盘口十档；
- 付费金融终端；
- 自动交易。

## 3. EvidencePack

EvidencePack 是一次 run 的全量证据仓。

核心字段：

- run_id
- market
- query
- retrieval_plan
- evidence_items
- claim_index
- source_coverage
- unresolved_gaps

## 4. Source Quality Tier

```yaml
tier_1_primary_fact:
  use: factual_claim, case_reconstruction, final_decision_evidence

tier_2_canonical_framework:
  use: framework_learning, principle_candidate, skill_candidate

tier_3_verified_public_practitioner:
  use: research_lens, pattern_distillation, case_selection, skill_candidate

tier_4_expert_opinion:
  use: hypothesis_generation, framework_comparison

tier_5_social_signal:
  use: sentiment_mapping, narrative_tracking, early_signal_discovery

tier_6_unverified:
  use: weak_signal_only
```

## 5. Verified Public Practitioner

高质量大 V 或公开实践者不是普通社媒信号。系统应支持 Source Promotion：

- identity_traceability
- methodology_clarity
- historical_case_quality
- market_validation
- falsification_attitude
- transferability
- source_integrity

通过后可标记为 `tier_3_verified_public_practitioner`。

Serenity / aleabitoreddit 在 V1 默认属于该层级，可作为方法论源，但不能直接作为事实或买卖依据。

## 6. Claim 抽取

每个证据项应抽取 Claim：

- claim_id
- claim_text
- claim_type: fact | opinion | inference | hypothesis
- source_id
- confidence
- relevant_to
- contradicts
- supports

## 7. 证据使用约束

- 无来源不得形成高置信结论。
- KOL 或社媒不得作为财务事实依据。
- 高影响结论必须优先使用 tier_1 或多源交叉验证。
- 低等级证据可作为线索，但必须被标注。
- 所有重要结论必须能回链到 Evidence ID / Claim ID。

## 8. Tool / Source Adapter Harness

Evidence System 必须向 Harness 暴露工具和来源质量，而不是只输出扁平证据列表。V1 产物：

```text
runs/{run_id}/harness/tool-harness.yaml
```

该产物至少包含：

- adapter_coverage：public research items、primary public items、low-tier public items；
- source_tier_counts / source_type_counts；
- source_boundary_quality：KOL / 书籍 / 案例 / 社媒是否按证据等级正确降权；
- blocking_issues；
- high_confidence_allowed。

Serenity、知名大 V、交易课程和经典书籍可以贡献方法论、checklist、假设和案例选择，但 Tool Harness 必须阻止它们绕过一手公告、财报、政策或行情证据直接生成买卖结论。

## 9. Public Research Cache / Manifest

V1 公开资料检索必须可审计、可复现、可缓存。每次 run 需要生成：

```text
cache/research/{cache_key}.json
runs/{run_id}/evidence/public-research-manifest.yaml
```

Cache entry 记录 query、adapter_name、limit、created_at、results、retrieval_id、source_hash 和 boundary_controls。Manifest 记录 result_count、cache_status_counts、source_tier_counts、source_type_counts 和每个结果的 retrieval_id / source_hash。

边界：cache 是审计轨迹，不是真实性来源；缓存命中不能提高 source tier；社媒和大 V 仍然必须遵守 `social_signal_never_direct_buy` 与 `kol_is_hypothesis_not_trade_signal`。

## 10. 验收标准

- 给定 topic / stock / question，系统能生成 EvidencePack。
- EvidencePack 中每个 evidence item 有 source tier、timestamp、summary、claims。
- 至少支持 source coverage report。
- 能识别证据缺口和冲突。
- 能为 Context Manager 提供按 Agent 过滤的证据索引。
- Tool Harness 能检查 adapter 覆盖、来源等级、KOL/社媒边界和高置信阻断。
- 每次 run 生成 public-research-manifest，并能用 cache/research 复现公开检索输入。

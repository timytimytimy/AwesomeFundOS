from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fundos.io import DISCLAIMER, REPO_ROOT, read_yaml
from fundos.capabilities import load_capability_summary
from fundos.learning import build_learning_source_registry
from fundos.memory import load_memory_writeback_summary


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_first_version_report(run_path: Path) -> str:
    if not run_path.is_absolute():
        run_path = REPO_ROOT / run_path
    roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
    seed = read_yaml(REPO_ROOT / "specs" / "learning" / "seed-library.yaml")
    run_doc = read_yaml(run_path / "run.yaml")
    selected = read_yaml(run_path / "selected-agents.yaml")["selected_agents"]
    evidence = read_yaml(run_path / "evidence" / "evidence-pack.yaml")
    learning = read_yaml(run_path / "learning" / "patterns.yaml")
    source_registry = read_optional_yaml(run_path / "learning" / "source-registry.yaml", build_learning_source_registry())
    memo = read_yaml(run_path / "decision" / "final-decision-memo.yaml")
    evaluation = read_yaml(run_path / "evaluations" / "evaluation-report.yaml")
    watchlist = read_optional_yaml(run_path / "portfolio" / "watchlist.yaml", {"items": []})
    paper_portfolio = read_optional_yaml(run_path / "portfolio" / "paper-portfolio.yaml", {"actions": []})
    portfolio_review = read_optional_yaml(run_path / "portfolio" / "portfolio-review.yaml", {"reviewed_actions": 0, "attribution_items": [], "learning_candidates": []})
    case_replay = read_optional_yaml(run_path / "harness" / "historical-case-replay.yaml", {"patterns_replayed": 0, "case_results_total": 0, "case_replay_score": 0})
    agent_harness = read_optional_yaml(run_path / "harness" / "agent-harness.yaml", {"agent_count": 0, "aggregate_scores": {}})
    tool_harness = read_optional_yaml(run_path / "harness" / "tool-harness.yaml", {"overall_score": 0, "adapter_coverage": {}, "source_boundary_quality": {}})
    evolution = load_jsonl(run_path / "evolution" / "evolution-gate-results.jsonl")
    memory_writeback = load_memory_writeback_summary(run_path)
    capability_summary = load_capability_summary(run_path)
    agent_outputs = load_agent_outputs(run_path)

    source_counts = count_by(evidence["evidence_items"], "source_type")
    tier_counts = count_by(evidence["evidence_items"], "source_tier")
    selected_ids = [item["agent_id"] for item in selected]
    pattern_ids = [pattern["id"] for pattern in learning.get("patterns", [])]
    evolution_counts = count_by(evolution, "decision")
    final = memo["final_decision"]

    lines = [
        "# AwesomeFundOS 第一版结果报告",
        "",
        DISCLAIMER,
        "",
        "## 系统能力总览",
        "",
        f"- 默认 Agent roster：{len(roster.get('agents', []))} 个独立角色。",
        f"- 本次示例动态选择 Agent：{len(selected_ids)} 个，包含 {', '.join(selected_ids)}。",
        "- 已实现模块：CLI run/init/eval/evolve/report、EvidencePack、ContextPack、结构化 Agent 输出、模拟投委会 Memo、Harness Evaluation、Historical Case Replay、Watchlist/Paper Portfolio Review、EvolutionGate、Learning Pattern 蒸馏。",
        "- V1 范围：本地优先、模拟投委会、观察池/Paper Portfolio，不接真实交易、不自动下单。",
        "",
        "## Agent Runtime Assets",
        "",
        "- 每个 Agent 都有 source-controlled `agent.md / SKILL.md`，并在运行时进入 ContextPack 与结构化输出。",
        f"- agent.md 数量：{len(list((REPO_ROOT / 'specs' / 'agents' / 'agent-cards').glob('*/agent.md')))}。",
        f"- SKILL.md 数量：{len(list((REPO_ROOT / 'specs' / 'skills').glob('*/SKILL.md')))}。",
        "",
        "## 学习源与蒸馏 Pattern",
        "",
        f"- Seed learning sources：{len(seed.get('sources', []))} 个。",
        f"- Learning Source Registry：{source_registry.get('source_count', 0)} 个来源，tiers={inline_counts(source_registry.get('source_tier_counts', {}))}。",
        "- Learning boundary controls：" + ", ".join(source_registry.get("boundary_policy", {}).get("controls", [])[:5]),
        f"- Run-scoped distilled patterns：{len(pattern_ids)} 个。",
        "- Pattern IDs：" + ", ".join(pattern_ids),
        "",
        "### 代表性学习源",
        "",
    ]
    for source in seed.get("sources", [])[:10]:
        lines.append(f"- {source['id']} / {source['display_name']} / {source['source_tier']}")
    lines += [
        "",
        f"## 示例运行：{run_doc['input']['value']}",
        "",
        f"- run_id：{run_doc['run_id']}",
        f"- market：{run_doc['market']}",
        f"- final label：{final['label']}",
        f"- stance：{final['stance']}",
        f"- conviction：{final['conviction']}",
        f"- hypothetical_position_range：{final['hypothetical_position_range']}",
        "",
        "### Evidence Coverage",
        "",
        "- source_type：" + inline_counts(source_counts),
        "- source_tier：" + inline_counts(tier_counts),
        "",
        "### Agent Learning Pattern 示例",
        "",
    ]
    for output in agent_outputs[:6]:
        patterns = [p["pattern_id"] for p in output.get("learning_patterns", [])]
        lines.append(f"- {output['agent_id']}：stance={output['stance']}，confidence={output['confidence']}，patterns={', '.join(patterns) if patterns else 'none'}")
    lines += [
        "",
        "### Agent Card / Skill Runtime 示例",
        "",
    ]
    for output in agent_outputs[:6]:
        runtime = output.get("agent_runtime", {})
        lines.append(f"- {output['agent_id']}：agent_card={runtime.get('agent_card_path')}；skill={runtime.get('skill_path')}；checklist_items={len(output.get('role_checklist_applied', []))}")
    lines += [
        "",
        "## Watchlist / Paper Portfolio",
        "",
        f"- watchlist_items：{len(watchlist.get('items', []))}",
        f"- paper_actions：{len(paper_portfolio.get('actions', []))}",
        f"- reviewed_actions：{portfolio_review.get('reviewed_actions', 0)}",
        f"- attribution_items：{len(portfolio_review.get('attribution_items', []))}",
        f"- review_learning_candidates：{len(portfolio_review.get('learning_candidates', []))}",
        f"- review_verdict：{portfolio_review.get('review_verdict', 'not_reviewed')}",
        f"- real_trade_allowed：{any(action.get('real_trade_allowed') for action in paper_portfolio.get('actions', []))}",
        "- artifact_paths：portfolio/watchlist.yaml；portfolio/paper-portfolio.yaml；portfolio/portfolio-actions.jsonl；portfolio/portfolio-review.yaml；portfolio/attribution.jsonl；portfolio/review-candidates.jsonl",
        "",
        "",
        "## 投委会 Memo 摘要",
        "",
        f"- Thesis：{memo['thesis']}",
        f"- Bull case：{memo['bull_case']}",
        f"- Bear case：{memo['bear_case']}",
        f"- Risk review：{memo['risk_review']}",
        "- Kill criteria：" + "; ".join(memo.get("kill_criteria", [])),
        "",
        "## Harness / Evaluation",
        "",
        f"- overall_score：{evaluation['overall_score']}",
        "- dimension_scores：" + inline_counts(evaluation.get("dimension_scores", {})),
        "- context_quality_scores：" + inline_counts(evaluation.get("context_quality_scores", {})),
        "- portfolio_quality：" + inline_counts(evaluation.get("portfolio_quality", {})),
        "- portfolio_review_quality：" + inline_counts(evaluation.get("portfolio_review_quality", {})),
        "- agent_harness_quality：" + inline_counts(evaluation.get("agent_harness_quality", {})),
        "- agent_harness：agent_count=" + str(agent_harness.get("agent_count", 0)) + "，aggregate_scores=" + inline_counts(agent_harness.get("aggregate_scores", {})),
        "- tool_harness_quality：" + inline_counts(evaluation.get("tool_harness_quality", {})),
        "- tool_harness：overall_score=" + str(tool_harness.get("overall_score", 0)) + "，adapter_coverage=" + inline_counts(tool_harness.get("adapter_coverage", {})),
        "- case_replay_quality：" + inline_counts(evaluation.get("case_replay_quality", {})),
        f"- historical_case_replay：patterns_replayed={case_replay.get('patterns_replayed', 0)}, case_results_total={case_replay.get('case_results_total', 0)}, case_replay_score={case_replay.get('case_replay_score', 0)}",
        "- blocking_issues：" + ("; ".join(evaluation.get("blocking_issues", [])) if evaluation.get("blocking_issues") else "none"),
        "",
        "## EvolutionGate",
        "",
        "- decision counts：" + inline_counts(evolution_counts),
        f"- memory_writes：{memory_writeback.get('memory_writes', 0)}",
        f"- capability_approved_candidates：{capability_summary.get('approved_candidates', 0)}",
        f"- capability_pending_human_apply：{capability_summary.get('pending_human_apply', 0)}",
        "- capability_agent_versions：" + inline_counts(capability_summary.get("agent_versions", {})),
        f"- approval_mode：{memory_writeback.get('approval_mode')}",
        "- agent_writes：" + inline_counts(memory_writeback.get("agent_writes", {})),
        "- written_paths：" + ("; ".join(memory_writeback.get("written_paths", [])) if memory_writeback.get("written_paths") else "none"),
    ]
    for row in evolution:
        lines.append(f"- {row['candidate_id']}：{row['decision']}，scores={inline_counts(row.get('scores', {}))}，memory_write_allowed={row.get('memory_write_allowed')}")
    lines += [
        "",
        "## V2 Gaps",
        "",
        "- 接入真实公告、财报、交易所问询、互动易和政策数据源。",
        "- 接入真实行情/价格序列，支持买点、卖点、仓位和 drawdown 的可评测判断。",
        "- 扩展历史案例库与 outcome tracking，让回放从小型内置案例升级为多市场状态、多行业、多失败模式的后验评测。",
        "- 将 Paper Portfolio Review 从过程归因扩展为接入真实行情后的定期 outcome tracking。",
        "- 将 EvolutionGate V1 自动受控写回升级为更完整的人工/规则审批流、回滚 UI 和长期绩效归因。",
        "",
        "## 可重复运行命令",
        "",
        "```bash",
        "python3 -m fundos.cli init",
        "python3 -m fundos.cli run --topic '机器人产业链投资机会' --research-fixture examples/fixtures/robotics-public-research.json",
        "python3 -m fundos.cli evolve --run runs/<run_id>",
        "python3 -m fundos.cli report --run runs/<run_id> --out reports/first-version-result.md",
        "```",
        "",
    ]
    return "\n".join(lines)


def load_agent_outputs(run_path: Path) -> list[dict[str, Any]]:
    outputs = []
    for path in sorted((run_path / "agent_work").glob("*.structured.yaml")):
        outputs.append(read_yaml(path))
    return outputs


def read_optional_yaml(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return read_yaml(path)


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return counts


def inline_counts(counts: dict[str, Any]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in counts.items())


def write_first_version_report(run_path: Path, out_path: Path) -> Path:
    text = build_first_version_report(run_path)
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text + "\n", encoding="utf-8")
    return out_path

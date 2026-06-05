from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fundos.io import DISCLAIMER, REPO_ROOT, read_yaml, write_yaml
from fundos.tool_adapters import adapter_lookup, load_tool_adapter_contracts

SPEC_REL = "specs/tools/fixture-adapter-runtime.yaml"
TOOL_RUNTIME_VERSION = "0.1.0"
DEFAULT_TOOL_SEQUENCE = [
    "market_data_query",
    "announcement_search",
    "financial_report_parser",
    "policy_search",
    "news_search",
    "web_search",
    "case_library_reader",
    "memory_retrieval",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_tool_runtime_spec() -> dict[str, Any]:
    spec = read_yaml(REPO_ROOT / SPEC_REL)
    spec["source_path"] = SPEC_REL
    return spec


def default_tool_runtime_report() -> dict[str, Any]:
    return {
        "version": TOOL_RUNTIME_VERSION,
        "artifact_type": "tool_runtime_report",
        "tool_runtime_quality_score": 0,
        "tool_call_count": 0,
        "evidence_items_created": 0,
        "blocked_tool_calls": 0,
        "adapters_called": [],
        "source_tier_counts": {},
        "blocking_issues": ["missing_tool_runtime_report"],
        "controls": [],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def load_tool_runtime_report(run_path: Path | None) -> dict[str, Any]:
    if not run_path:
        return default_tool_runtime_report()
    path = run_path / "tools" / "tool-runtime-report.yaml"
    if not path.exists():
        return default_tool_runtime_report()
    loaded = read_yaml(path) or {}
    report = default_tool_runtime_report()
    report.update(loaded)
    return report


def run_fixture_tool_runtime(
    run_path: Path,
    selected_agents: list[dict[str, Any]],
    evidence_pack: dict[str, Any],
    requested_tools: list[str] | None = None,
) -> dict[str, Any]:
    spec = load_tool_runtime_spec()
    fixture_lookup = runtime_adapter_lookup(spec)
    contract_lookup = adapter_lookup(load_tool_adapter_contracts())
    query = str(evidence_pack.get("query") or "market")
    run_id = str(evidence_pack.get("run_id") or read_run_id(run_path) or "run")
    tools = requested_tools or infer_requested_tools(selected_agents, fixture_lookup)
    rows: list[dict[str, Any]] = []
    evidence_items: list[dict[str, Any]] = []
    for index, tool_id in enumerate(tools, start=1):
        canonical = canonical_tool_id(tool_id, fixture_lookup)
        contract = contract_lookup.get(tool_id) or contract_lookup.get(canonical or "")
        fixture = fixture_lookup.get(canonical or "")
        tool_result_id = f"{run_id}:{tool_id}:{index:03d}"
        if not fixture or not contract or not contract_allowed(contract):
            rows.append(blocked_call(run_id, tool_id, tool_result_id, query, "forbidden_or_unknown_tool"))
            continue
        evidence_id = f"TR{index:03d}"
        item = tool_runtime_evidence_item(evidence_id, tool_result_id, canonical or tool_id, fixture, query, run_id)
        evidence_items.append(item)
        rows.append(succeeded_call(run_id, canonical or tool_id, tool_result_id, query, fixture, item))
    write_jsonl(run_path / "tools" / "tool-call-ledger.jsonl", rows)
    merge_tool_evidence_into_memory(evidence_pack, evidence_items)
    merge_tool_evidence_into_pack(run_path, evidence_items)
    write_yaml(run_path / "evidence" / "tool-runtime-evidence.yaml", {
        "artifact_type": "tool_runtime_evidence",
        "run_id": run_id,
        "evidence_items": evidence_items,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    })
    blocked = [row for row in rows if row.get("status") == "blocked"]
    succeeded = [row for row in rows if row.get("status") == "succeeded"]
    blocking = [f"{row['reason']}:{row['adapter_id']}" for row in blocked]
    source_tier_counts = count_by(evidence_items, "source_tier")
    report = {
        "version": TOOL_RUNTIME_VERSION,
        "artifact_type": "tool_runtime_report",
        "runtime_id": spec.get("runtime_id"),
        "source_path": spec.get("source_path"),
        "run_id": run_id,
        "tool_runtime_quality_score": quality_score(rows, evidence_items, spec.get("controls", [])),
        "tool_call_count": len(rows),
        "succeeded_tool_calls": len(succeeded),
        "blocked_tool_calls": len(blocked),
        "evidence_items_created": len(evidence_items),
        "adapters_called": sorted({row["adapter_id"] for row in succeeded}),
        "source_tier_counts": source_tier_counts,
        "ledger_path": "tools/tool-call-ledger.jsonl",
        "evidence_path": "evidence/tool-runtime-evidence.yaml",
        "blocking_issues": blocking,
        "controls": spec.get("controls", []),
        "disclaimer": DISCLAIMER,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    write_yaml(run_path / "tools" / "tool-runtime-report.yaml", report)
    return report


def merge_tool_evidence_into_memory(evidence_pack: dict[str, Any], evidence_items: list[dict[str, Any]]) -> None:
    existing = evidence_pack.get("evidence_items", [])
    non_tool = [item for item in existing if item.get("source_id") != "fixture_tool_runtime"]
    evidence_pack["evidence_items"] = non_tool + evidence_items
    plan = list(evidence_pack.get("retrieval_plan", []))
    if "fixture_tool_runtime" not in plan:
        plan.append("fixture_tool_runtime")
    evidence_pack["retrieval_plan"] = plan
    evidence_pack["unresolved_gaps"] = [gap for gap in evidence_pack.get("unresolved_gaps", []) if "public retrieval interface stub" not in str(gap)]


def merge_tool_evidence_into_pack(run_path: Path, evidence_items: list[dict[str, Any]]) -> None:
    path = run_path / "evidence" / "evidence-pack.yaml"
    if not path.exists():
        return
    pack = read_yaml(path) or {}
    existing = pack.get("evidence_items", [])
    non_tool = [item for item in existing if item.get("source_id") != "fixture_tool_runtime"]
    pack["evidence_items"] = non_tool + evidence_items
    plan = list(pack.get("retrieval_plan", []))
    if "fixture_tool_runtime" not in plan:
        plan.append("fixture_tool_runtime")
    pack["retrieval_plan"] = plan
    gaps = [gap for gap in pack.get("unresolved_gaps", []) if "public retrieval interface stub" not in str(gap)]
    if not evidence_items:
        gaps.append("Fixture Tool Runtime did not create evidence items.")
    pack["unresolved_gaps"] = gaps
    write_yaml(path, pack)


def runtime_adapter_lookup(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for adapter in spec.get("fixture_adapters", []):
        lookup[adapter["adapter_id"]] = adapter
        for alias in adapter.get("aliases", []) or []:
            lookup[alias] = adapter
    return lookup


def canonical_tool_id(tool_id: str, fixture_lookup: dict[str, dict[str, Any]]) -> str | None:
    adapter = fixture_lookup.get(tool_id)
    if adapter:
        return adapter.get("adapter_id", tool_id)
    return None


def infer_requested_tools(selected_agents: list[dict[str, Any]], fixture_lookup: dict[str, dict[str, Any]]) -> list[str]:
    explicit: list[str] = []
    for agent in selected_agents:
        for tool in agent.get("tools", []) or []:
            if tool in fixture_lookup and tool not in explicit:
                explicit.append(tool)
    if explicit:
        return explicit
    return list(DEFAULT_TOOL_SEQUENCE)


def contract_allowed(contract: dict[str, Any]) -> bool:
    return (
        contract.get("permission_level") == "read_only_analysis"
        and contract.get("real_trade_allowed") is False
        and contract.get("broker_integration") == "disabled"
        and contract.get("category") not in {"broker_api", "order_placement", "real_trade_execution"}
    )


def blocked_call(run_id: str, adapter_id: str, tool_result_id: str, query: str, reason: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "adapter_id": adapter_id,
        "tool_result_id": tool_result_id,
        "query": query,
        "status": "blocked",
        "reason": reason,
        "permission_level": "read_only_analysis",
        "evidence_item_ids": [],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
        "called_at": now_iso(),
    }


def succeeded_call(run_id: str, adapter_id: str, tool_result_id: str, query: str, fixture: dict[str, Any], evidence_item: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "adapter_id": adapter_id,
        "tool_result_id": tool_result_id,
        "query": query,
        "status": "succeeded",
        "permission_level": "read_only_analysis",
        "source_type": fixture.get("source_type"),
        "source_tier": fixture.get("source_tier"),
        "evidence_item_ids": [evidence_item["id"]],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
        "called_at": now_iso(),
    }


def tool_runtime_evidence_item(evidence_id: str, tool_result_id: str, adapter_id: str, fixture: dict[str, Any], query: str, run_id: str) -> dict[str, Any]:
    source_tier = fixture.get("source_tier", "tier_4_expert_opinion")
    confidence = "high" if source_tier == "tier_1_primary_fact" else "medium" if source_tier in {"tier_2_canonical_framework", "tier_3_verified_public_practitioner", "approved_memory"} else "low"
    summary = f"{fixture.get('default_summary', '')} Subject: {query}."
    return {
        "id": evidence_id,
        "run_id": run_id,
        "tool_result_id": tool_result_id,
        "adapter_id": adapter_id,
        "source_id": "fixture_tool_runtime",
        "source_type": fixture.get("source_type", "tool_runtime"),
        "source_tier": source_tier,
        "title": f"{adapter_id} fixture result",
        "url": "",
        "published_at": "",
        "retrieved_at": now_iso(),
        "raw_excerpt": summary,
        "summary": summary,
        "confidence": confidence,
        "not_allowed_outputs": ["direct_buy_signal", "direct_sell_signal", "real_order", "broker_action"],
        "claims": [
            {
                "claim_id": f"{evidence_id}-C001",
                "claim_text": summary,
                "claim_type": "fact" if source_tier == "tier_1_primary_fact" else "hypothesis" if source_tier.startswith("tier_4") else "methodology_or_context",
                "confidence": confidence,
                "relevant_to": ["tool_runtime", adapter_id],
                "supports": [],
                "contradicts": [],
            }
        ],
    }


def quality_score(rows: list[dict[str, Any]], evidence_items: list[dict[str, Any]], controls: list[str]) -> int:
    score = 50
    if rows:
        score += 10
    if evidence_items and len(evidence_items) == sum(1 for row in rows if row.get("status") == "succeeded"):
        score += 15
    if any(item.get("source_tier") == "tier_1_primary_fact" for item in evidence_items):
        score += 10
    if all(row.get("permission_level") == "read_only_analysis" for row in rows):
        score += 5
    if all(row.get("real_trade_allowed") is False and row.get("broker_integration") == "disabled" for row in rows):
        score += 5
    if {"all_fixture_tools_are_read_only", "tool_call_ledger_required"}.issubset(set(controls)):
        score += 5
    score -= min(40, sum(1 for row in rows if row.get("status") == "blocked") * 15)
    return max(0, min(100, score))


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return counts


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def read_run_id(run_path: Path) -> str | None:
    path = run_path / "run.yaml"
    if not path.exists():
        return None
    return (read_yaml(path) or {}).get("run_id")

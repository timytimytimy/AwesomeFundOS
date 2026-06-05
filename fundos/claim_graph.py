from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.io import DISCLAIMER, REPO_ROOT, read_yaml, write_yaml

SPEC_REL = "specs/evidence/claim-graph.yaml"
CLAIM_GRAPH_VERSION = "0.1.0"
LOW_TIERS = {"tier_5_social_signal", "tier_6_unverified"}
METHODOLOGY_TIERS = {"tier_2_canonical_framework", "tier_3_verified_public_practitioner"}


def load_claim_graph_spec() -> dict[str, Any]:
    spec = read_yaml(REPO_ROOT / SPEC_REL)
    spec["source_path"] = SPEC_REL
    return spec


def default_claim_graph_report() -> dict[str, Any]:
    return {
        "version": CLAIM_GRAPH_VERSION,
        "artifact_type": "claim_graph_report",
        "traceability_score": 0,
        "claim_node_count": 0,
        "evidence_node_count": 0,
        "decision_claim_count": 0,
        "agent_claim_count": 0,
        "tool_result_node_count": 0,
        "unsupported_decision_claims": [],
        "low_tier_decision_claims": [],
        "blocking_issues": ["missing_claim_graph_report"],
        "controls": [],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def load_claim_graph_report(run_path: Path | None) -> dict[str, Any]:
    if not run_path:
        return default_claim_graph_report()
    path = run_path / "harness" / "claim-graph.yaml"
    if not path.exists():
        return default_claim_graph_report()
    loaded = read_yaml(path) or {}
    report = default_claim_graph_report()
    report.update(loaded)
    return report


def write_claim_graph(run_path: Path, evidence_pack: dict[str, Any]) -> dict[str, Any]:
    spec = load_claim_graph_spec()
    run_id = evidence_pack.get("run_id") or read_run_id(run_path)
    evidence_items = evidence_pack.get("evidence_items", [])
    claim_lookup = build_claim_lookup(evidence_items)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    add_evidence_and_claim_nodes(nodes, edges, evidence_items, spec)
    add_tool_result_nodes(nodes, edges, evidence_items)
    decision_refs = add_decision_nodes(run_path, nodes, edges, claim_lookup)
    agent_refs = add_agent_output_nodes(run_path, nodes, edges, claim_lookup)
    unsupported = unsupported_refs(decision_refs, claim_lookup)
    low_tier = low_tier_refs(decision_refs, claim_lookup)
    blocking = []
    if unsupported:
        blocking.append("unsupported_decision_claims")
    if low_tier:
        blocking.append("low_tier_decision_claim_used")
    tool_evidence_without_trace = [item.get("id") for item in evidence_items if item.get("source_id") == "fixture_tool_runtime" and not item.get("tool_result_id")]
    if tool_evidence_without_trace:
        blocking.append("tool_evidence_missing_tool_result_id")
    score = traceability_score(evidence_items, decision_refs, agent_refs, unsupported, low_tier, tool_evidence_without_trace)
    graph = {
        "version": CLAIM_GRAPH_VERSION,
        "artifact_type": "claim_graph",
        "graph_id": spec.get("graph_id"),
        "source_path": spec.get("source_path"),
        "run_id": run_id,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
        "controls": spec.get("controls", []),
        "disclaimer": DISCLAIMER,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    report = {
        "version": CLAIM_GRAPH_VERSION,
        "artifact_type": "claim_graph_report",
        "graph_id": spec.get("graph_id"),
        "source_path": spec.get("source_path"),
        "run_id": run_id,
        "traceability_score": score,
        "claim_node_count": count_kind(nodes, "claim"),
        "evidence_node_count": count_kind(nodes, "evidence"),
        "decision_claim_count": len(decision_refs),
        "agent_claim_count": len(agent_refs),
        "tool_result_node_count": count_kind(nodes, "tool_result"),
        "unsupported_decision_claims": unsupported,
        "low_tier_decision_claims": low_tier,
        "tool_evidence_without_trace": tool_evidence_without_trace,
        "blocking_issues": blocking,
        "controls": spec.get("controls", []),
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    write_yaml(run_path / "evidence" / "claim-graph.yaml", graph)
    write_yaml(run_path / "harness" / "claim-graph.yaml", report)
    return report


def build_claim_lookup(evidence_items: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for item in evidence_items:
        for claim in item.get("claims", []) or []:
            lookup[(str(item.get("id")), str(claim.get("claim_id")))] = {"evidence": item, "claim": claim}
    return lookup


def add_evidence_and_claim_nodes(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], evidence_items: list[dict[str, Any]], spec: dict[str, Any]) -> None:
    eligible = set(spec.get("source_tier_policy", {}).get("decision_eligible_tiers", []))
    for item in evidence_items:
        evidence_node_id = f"evidence:{item.get('id')}"
        nodes.append({
            "node_id": evidence_node_id,
            "kind": "evidence",
            "evidence_id": item.get("id"),
            "source_id": item.get("source_id", "seed_or_pack"),
            "source_type": item.get("source_type"),
            "source_tier": item.get("source_tier"),
            "tool_result_id": item.get("tool_result_id"),
            "real_trade_allowed": False,
            "broker_integration": "disabled",
        })
        for claim in item.get("claims", []) or []:
            claim_node_id = f"claim:{item.get('id')}:{claim.get('claim_id')}"
            source_tier = item.get("source_tier")
            nodes.append({
                "node_id": claim_node_id,
                "kind": "claim",
                "evidence_id": item.get("id"),
                "claim_id": claim.get("claim_id"),
                "claim_type": claim.get("claim_type"),
                "confidence": claim.get("confidence"),
                "source_tier": source_tier,
                "source_type": item.get("source_type"),
                "decision_eligible": source_tier in eligible and source_tier not in LOW_TIERS,
                "methodology_only": source_tier in METHODOLOGY_TIERS or item.get("source_type") in {"practitioner_source", "book_summary", "learning_pattern", "case"},
                "real_trade_allowed": False,
                "broker_integration": "disabled",
            })
            edges.append({"kind": "contains_claim", "from": evidence_node_id, "to": claim_node_id})
            edges.append({"kind": "supported_by", "from": claim_node_id, "to": evidence_node_id})


def add_tool_result_nodes(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], evidence_items: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for item in evidence_items:
        tool_result_id = item.get("tool_result_id")
        if not tool_result_id:
            continue
        node_id = f"tool_result:{tool_result_id}"
        if tool_result_id not in seen:
            nodes.append({
                "node_id": node_id,
                "kind": "tool_result",
                "tool_result_id": tool_result_id,
                "adapter_id": item.get("adapter_id"),
                "source_tier": item.get("source_tier"),
                "real_trade_allowed": False,
                "broker_integration": "disabled",
            })
            seen.add(tool_result_id)
        edges.append({"kind": "derived_from_tool_result", "from": f"evidence:{item.get('id')}", "to": node_id})


def add_decision_nodes(run_path: Path, nodes: list[dict[str, Any]], edges: list[dict[str, Any]], claim_lookup: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, str]]:
    path = run_path / "decision" / "final-decision-memo.yaml"
    if not path.exists():
        return []
    memo = read_yaml(path) or {}
    node_id = "decision:final-decision-memo"
    nodes.append({"node_id": node_id, "kind": "decision", "memo_type": memo.get("memo_type"), "real_trade_allowed": False, "broker_integration": "disabled"})
    refs = normalize_refs(memo.get("evidence_references", []))
    for ref in refs:
        target = claim_node_id(ref)
        kind = "cited_by_decision" if ref_tuple(ref) in claim_lookup else "unsupported_decision_ref"
        edges.append({"kind": kind, "from": node_id, "to": target})
    return refs


def add_agent_output_nodes(run_path: Path, nodes: list[dict[str, Any]], edges: list[dict[str, Any]], claim_lookup: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    agent_dir = run_path / "agent_work"
    if not agent_dir.exists():
        return refs
    for path in sorted(agent_dir.glob("*.structured.yaml")):
        output = read_yaml(path) or {}
        agent_id = output.get("agent_id") or path.stem.replace(".structured", "")
        node_id = f"agent_output:{agent_id}"
        nodes.append({"node_id": node_id, "kind": "agent_output", "agent_id": agent_id, "stance": output.get("stance"), "confidence": output.get("confidence"), "real_trade_allowed": False, "broker_integration": "disabled"})
        for ref in normalize_refs(output.get("key_claims", [])):
            refs.append(ref)
            target = claim_node_id(ref)
            kind = "cited_by_agent" if ref_tuple(ref) in claim_lookup else "unsupported_agent_ref"
            edges.append({"kind": kind, "from": node_id, "to": target})
    return refs


def normalize_refs(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    refs = []
    for row in rows or []:
        evidence_id = row.get("evidence_id")
        claim_id = row.get("claim_id")
        if evidence_id and claim_id:
            refs.append({"evidence_id": str(evidence_id), "claim_id": str(claim_id)})
    return refs


def unsupported_refs(refs: list[dict[str, str]], claim_lookup: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, str]]:
    return [ref for ref in refs if ref_tuple(ref) not in claim_lookup]


def low_tier_refs(refs: list[dict[str, str]], claim_lookup: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, str]]:
    low = []
    for ref in refs:
        found = claim_lookup.get(ref_tuple(ref))
        if found and found["evidence"].get("source_tier") in LOW_TIERS:
            low.append({**ref, "source_tier": found["evidence"].get("source_tier")})
    return low


def claim_node_id(ref: dict[str, str]) -> str:
    return f"claim:{ref.get('evidence_id')}:{ref.get('claim_id')}"


def ref_tuple(ref: dict[str, str]) -> tuple[str, str]:
    return (str(ref.get("evidence_id")), str(ref.get("claim_id")))


def traceability_score(evidence_items: list[dict[str, Any]], decision_refs: list[dict[str, str]], agent_refs: list[dict[str, str]], unsupported: list[dict[str, str]], low_tier: list[dict[str, str]], tool_missing: list[str]) -> int:
    score = 60
    if evidence_items:
        score += 10
    if decision_refs:
        score += 10
    if agent_refs:
        score += 5
    if any(item.get("tool_result_id") for item in evidence_items):
        score += 10
    if all(item.get("claims") for item in evidence_items):
        score += 5
    score -= min(40, len(unsupported) * 12)
    score -= min(30, len(low_tier) * 15)
    score -= min(20, len(tool_missing) * 10)
    return max(0, min(100, score))


def count_kind(nodes: list[dict[str, Any]], kind: str) -> int:
    return sum(1 for node in nodes if node.get("kind") == kind)


def read_run_id(run_path: Path) -> str | None:
    path = run_path / "run.yaml"
    if not path.exists():
        return None
    return (read_yaml(path) or {}).get("run_id")

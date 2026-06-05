from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fundos.io import DISCLAIMER, REPO_ROOT, read_yaml, write_yaml

SPEC_REL = "specs/tools/agent-tool-use-reconciliation.yaml"
AGENT_TOOL_USE_VERSION = "0.1.0"
FORBIDDEN_TOOLS = {
    "broker_api",
    "order_placement",
    "real_trade_execution",
    "account_login",
    "capital_transfer",
    "margin_borrowing",
}


def load_agent_tool_use_spec() -> dict[str, Any]:
    spec = read_yaml(REPO_ROOT / SPEC_REL)
    spec["source_path"] = SPEC_REL
    return spec


def default_agent_tool_use_report() -> dict[str, Any]:
    return {
        "version": AGENT_TOOL_USE_VERSION,
        "artifact_type": "agent_tool_use_report",
        "overall_score": 0,
        "agent_count": 0,
        "agents_with_missing_required_tools": 0,
        "agents_with_forbidden_tool_calls": 0,
        "succeeded_tool_calls": 0,
        "linked_tool_results": 0,
        "blocking_issues": ["missing_agent_tool_use_report"],
        "controls": [],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def load_agent_tool_use_report(run_path: Path | None) -> dict[str, Any]:
    if not run_path:
        return default_agent_tool_use_report()
    path = run_path / "harness" / "agent-tool-use.yaml"
    if not path.exists():
        return default_agent_tool_use_report()
    loaded = read_yaml(path) or {}
    report = default_agent_tool_use_report()
    report.update(loaded)
    return report


def write_agent_tool_use_report(run_path: Path, selected_agents: list[dict[str, Any]]) -> dict[str, Any]:
    spec = load_agent_tool_use_spec()
    ledger_rows = read_ledger(run_path / "tools" / "tool-call-ledger.jsonl")
    graph_tool_results = read_claim_graph_tool_results(run_path / "evidence" / "claim-graph.yaml")
    agent_results = [reconcile_agent(agent, ledger_rows, graph_tool_results) for agent in selected_agents]
    blocking = blocking_issues(agent_results)
    succeeded_tool_calls = sum(len(row["succeeded_tool_result_ids"]) for row in agent_results)
    linked_tool_results = sum(row["tool_results_linked_to_claim_graph"] for row in agent_results)
    overall = round(sum(row["score"] for row in agent_results) / len(agent_results), 1) if agent_results else 0
    report = {
        "version": AGENT_TOOL_USE_VERSION,
        "artifact_type": "agent_tool_use_report",
        "reconciliation_id": spec.get("reconciliation_id"),
        "source_path": spec.get("source_path"),
        "run_id": read_run_id(run_path),
        "overall_score": overall,
        "agent_count": len(agent_results),
        "agents_with_missing_required_tools": sum(1 for row in agent_results if row["missing_required_tools"]),
        "agents_with_forbidden_tool_calls": sum(1 for row in agent_results if row["forbidden_called_tools"]),
        "succeeded_tool_calls": succeeded_tool_calls,
        "linked_tool_results": linked_tool_results,
        "agent_results": agent_results,
        "blocking_issues": blocking,
        "controls": spec.get("controls", []),
        "disclaimer": DISCLAIMER,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    write_yaml(run_path / "harness" / "agent-tool-use.yaml", report)
    return report


def reconcile_agent(agent: dict[str, Any], ledger_rows: list[dict[str, Any]], graph_tool_results: set[str]) -> dict[str, Any]:
    agent_id = agent_id_of(agent)
    policy = load_policy(agent_id)
    allowed = list(policy.get("allowed_tools", []))
    required = list(policy.get("required_tools", []))
    forbidden = set(policy.get("forbidden_tools", [])) | FORBIDDEN_TOOLS
    agent_rows = [row for row in ledger_rows if row.get("agent_id") == agent_id]
    called_tools = sorted({str(row.get("adapter_id")) for row in agent_rows if row.get("adapter_id")})
    succeeded_rows = [row for row in agent_rows if row.get("status") == "succeeded"]
    succeeded_tools = {str(row.get("adapter_id")) for row in succeeded_rows}
    missing_required = [tool for tool in required if tool not in succeeded_tools]
    forbidden_called = sorted({tool for tool in called_tools if tool in forbidden or (allowed and tool not in set(allowed))})
    succeeded_tool_result_ids = [str(row.get("tool_result_id")) for row in succeeded_rows if row.get("tool_result_id")]
    linked_ids = [tool_result_id for tool_result_id in succeeded_tool_result_ids if tool_result_id in graph_tool_results]
    unlinked_ids = [tool_result_id for tool_result_id in succeeded_tool_result_ids if tool_result_id not in graph_tool_results]
    confidence_cap_required = bool(missing_required or forbidden_called or unlinked_ids)
    score = score_agent(required, missing_required, forbidden_called, succeeded_tool_result_ids, linked_ids, confidence_cap_required)
    return {
        "agent_id": agent_id,
        "role": agent.get("role") or policy.get("role"),
        "policy_path": policy.get("source_path"),
        "allowed_tools": allowed,
        "required_tools": required,
        "called_tools": called_tools,
        "missing_required_tools": missing_required,
        "forbidden_called_tools": forbidden_called,
        "succeeded_tool_result_ids": succeeded_tool_result_ids,
        "tool_results_linked_to_claim_graph": len(linked_ids),
        "unlinked_tool_result_ids": unlinked_ids,
        "confidence_cap_required": confidence_cap_required,
        "score": score,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def score_agent(
    required: list[str],
    missing_required: list[str],
    forbidden_called: list[str],
    succeeded_tool_result_ids: list[str],
    linked_ids: list[str],
    confidence_cap_required: bool,
) -> int:
    score = 50
    if required and not missing_required:
        score += 20
    if not forbidden_called:
        score += 10
    if succeeded_tool_result_ids and len(linked_ids) == len(succeeded_tool_result_ids):
        score += 10
    if confidence_cap_required or not missing_required:
        score += 10
    score -= min(48, len(missing_required) * 12)
    score -= min(60, len(forbidden_called) * 30)
    score -= min(32, (len(succeeded_tool_result_ids) - len(linked_ids)) * 8)
    return max(0, min(100, score))


def blocking_issues(agent_results: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    for row in agent_results:
        agent_id = row["agent_id"]
        for tool in row["missing_required_tools"]:
            issues.append(f"missing_required_tool:{agent_id}:{tool}")
        for tool in row["forbidden_called_tools"]:
            issues.append(f"forbidden_tool_call:{agent_id}:{tool}")
        for tool_result_id in row["unlinked_tool_result_ids"]:
            issues.append(f"tool_result_not_in_claim_graph:{agent_id}:{tool_result_id}")
    return issues


def read_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def read_claim_graph_tool_results(path: Path) -> set[str]:
    if not path.exists():
        return set()
    graph = read_yaml(path) or {}
    ids = set()
    for node in graph.get("nodes", []) or []:
        if node.get("kind") == "tool_result" and node.get("tool_result_id"):
            ids.add(str(node.get("tool_result_id")))
    return ids


def load_policy(agent_id: str) -> dict[str, Any]:
    rel = f"specs/agents/tool-policies/{agent_id}.yaml"
    path = REPO_ROOT / rel
    if not path.exists():
        return {"agent_id": agent_id, "allowed_tools": [], "required_tools": [], "forbidden_tools": list(FORBIDDEN_TOOLS), "source_path": rel}
    policy = read_yaml(path) or {}
    policy["source_path"] = rel
    return policy


def agent_id_of(agent: dict[str, Any]) -> str:
    return str(agent.get("agent_id") or agent.get("id"))


def read_run_id(run_path: Path) -> str | None:
    path = run_path / "run.yaml"
    if not path.exists():
        return None
    return (read_yaml(path) or {}).get("run_id")

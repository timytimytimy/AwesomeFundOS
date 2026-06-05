from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.io import REPO_ROOT, read_yaml, write_yaml

TOOL_POLICY_VERSION = "0.1.0"
FORBIDDEN_TOOLS = [
    "broker_api",
    "order_placement",
    "real_trade_execution",
    "account_login",
    "capital_transfer",
    "margin_borrowing",
]
TOOL_USE_RULES = [
    "Only use tools listed in allowed_tools for this agent and task.",
    "Every factual output from a tool must be traceable to a ToolResult ID, Evidence ID, or Claim ID when available.",
    "If a required tool is unavailable or not invoked, report it as missing_tool_calls and cap confidence.",
    "Do not place orders, connect to broker accounts, move capital, or provide brokerage instructions.",
    "Social, KOL, book, course, and historical-case tools may generate hypotheses or checklists only; they cannot produce direct buy/sell signals.",
]
SOURCE_BOUNDARY_RULES = [
    "primary_source_required_for_high_confidence",
    "kol_is_hypothesis_not_trade_signal",
    "book_and_case_are_methodology_only",
    "social_signal_never_direct_buy",
    "real_trade_action_forbidden",
]
HARNESS_CHECKS = [
    "tool_policy_loaded",
    "allowed_tools_declared",
    "forbidden_tools_respected",
    "missing_required_tools_reported",
    "no_real_trade_action",
    "broker_integration_disabled",
]


def tool_family(tool_name: str) -> str:
    name = tool_name.lower()
    if any(key in name for key in ["market_data", "chart", "liquidity"]):
        return "market_data"
    if any(key in name for key in ["announcement", "financial_report", "filing"]):
        return "filing"
    if any(key in name for key in ["news", "web", "policy", "tender"]):
        return "research"
    if any(key in name for key in ["memory", "case"]):
        return "case_library"
    if any(key in name for key in ["risk"]):
        return "risk"
    if any(key in name for key in ["portfolio", "watchlist"]):
        return "portfolio"
    if any(key in name for key in ["harness", "scoring", "auditor", "gap"]):
        return "harness"
    if any(key in name for key in ["writer", "report", "memo"]):
        return "writing"
    if any(key in name for key in ["source_registry", "evolution"]):
        return "evolution"
    if any(key in name for key in ["run_store", "roster", "context_router", "artifact_reader"]):
        return "orchestration"
    if any(key in name for key in ["context_reader", "evidence_pack_reader", "claim"]):
        return "evidence"
    return "analysis"


def required_tools_for(agent: dict[str, Any]) -> list[str]:
    tools = list(agent.get("tools", []))
    role = agent.get("role", "")
    if "Trader" in role:
        return [tool for tool in tools if tool in {"market_data_query", "chart_summary", "liquidity_check", "news_search", "announcement_search", "risk_checklist"}] or tools
    if "Analyst" in role or "Company" in role or "Governance" in role:
        return tools
    if agent["id"] in {"fund_manager", "risk_manager", "bear_debater", "evaluation_harness"}:
        return tools
    return tools[:2] if len(tools) > 2 else tools


def policy_template(agent: dict[str, Any]) -> dict[str, Any]:
    allowed = list(agent.get("tools", []))
    required = required_tools_for(agent)
    return {
        "version": TOOL_POLICY_VERSION,
        "agent_id": agent["id"],
        "role": agent["role"],
        "tool_policy_id": f"{agent['id']}_tool_policy",
        "allowed_tools": allowed,
        "required_tools": required,
        "optional_tools": [tool for tool in allowed if tool not in set(required)],
        "forbidden_tools": FORBIDDEN_TOOLS,
        "tool_categories": {tool: tool_family(tool) for tool in allowed},
        "permission_level": "read_only_analysis",
        "tool_use_rules": TOOL_USE_RULES,
        "source_boundary_rules": SOURCE_BOUNDARY_RULES,
        "harness_checks": HARNESS_CHECKS,
        "missing_tool_reporting": {
            "required": True,
            "confidence_cap_when_missing_required": "low_or_medium",
            "v1_reason": "tool_call_ledger_not_available_v1",
        },
        "real_trade_allowed": False,
        "broker_integration": False,
    }


def load_tool_policy(agent: dict[str, Any]) -> dict[str, Any]:
    agent_id = agent["id"]
    rel = f"specs/agents/tool-policies/{agent_id}.yaml"
    path = REPO_ROOT / rel
    if path.exists():
        loaded = read_yaml(path) or {}
        policy = policy_template(agent)
        policy.update(loaded)
        policy["source_path"] = rel
        policy["available"] = True
        return policy
    policy = policy_template(agent)
    policy["source_path"] = rel
    policy["available"] = False
    return policy


def write_default_tool_policies(root: Path | None = None) -> int:
    base = root or REPO_ROOT
    roster = read_yaml(base / "specs" / "agents" / "default-roster.yaml")
    out_dir = base / "specs" / "agents" / "tool-policies"
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for agent in roster["agents"]:
        path = out_dir / f"{agent['id']}.yaml"
        if not path.exists():
            write_yaml(path, policy_template(agent))
            count += 1
    return count

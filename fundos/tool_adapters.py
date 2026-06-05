from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.io import REPO_ROOT, read_yaml, write_yaml

CONTRACT_REL = "specs/tools/tool-adapter-contracts.yaml"


def load_tool_adapter_contracts() -> dict[str, Any]:
    spec = read_yaml(REPO_ROOT / CONTRACT_REL)
    spec["source_path"] = CONTRACT_REL
    return spec


def adapter_lookup(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for adapter in spec.get("adapters", []):
        lookup[adapter["adapter_id"]] = adapter
        for alias in adapter.get("aliases", []) or []:
            lookup[alias] = adapter
    return lookup


def evaluate_tool_adapter_contracts(roster: dict[str, Any]) -> dict[str, Any]:
    spec = load_tool_adapter_contracts()
    lookup = adapter_lookup(spec)
    forbidden = set(spec.get("forbidden_adapter_categories", []))
    adapters = spec.get("adapters", [])
    unmapped: list[dict[str, str]] = []
    forbidden_mapped: list[dict[str, str]] = []
    mapping: dict[str, dict[str, Any]] = {}
    for agent in roster.get("agents", []):
        required_tools = list(agent.get("tools", []))
        mapped_tools = []
        for tool in required_tools:
            adapter = lookup.get(tool)
            if not adapter:
                unmapped.append({"agent_id": agent.get("id", "unknown"), "tool": tool})
                continue
            if tool in forbidden or adapter.get("category") in forbidden or adapter.get("adapter_id") in forbidden:
                forbidden_mapped.append({"agent_id": agent.get("id", "unknown"), "tool": tool})
                continue
            mapped_tools.append(tool)
        mapping[agent.get("id", "unknown")] = {
            "declared_tools": required_tools,
            "mapped_required_tools": mapped_tools,
            "unmapped_required_tools": [row["tool"] for row in unmapped if row["agent_id"] == agent.get("id")],
        }
    all_read_only = all(adapter.get("permission_level") == "read_only_analysis" for adapter in adapters)
    broker_disabled = all(adapter.get("broker_integration") == "disabled" for adapter in adapters)
    no_real_trade = all(adapter.get("real_trade_allowed") is False for adapter in adapters)
    output_contracts_ok = all(output_contract_valid(adapter) for adapter in adapters)
    blocking = []
    if unmapped:
        blocking.append("unmapped_required_tools")
    if forbidden_mapped:
        blocking.append("forbidden_tool_mapped")
    if not all_read_only:
        blocking.append("adapter_not_read_only")
    if not broker_disabled:
        blocking.append("broker_integration_not_disabled")
    if not no_real_trade:
        blocking.append("real_trade_adapter_enabled")
    if not output_contracts_ok:
        blocking.append("output_contract_missing_required_fields")
    return {
        "artifact_type": "tool_adapter_contract_report",
        "contract_id": spec.get("contract_id"),
        "source_contract_path": spec.get("source_path"),
        "adapter_count": len(adapters),
        "adapter_ids": [adapter["adapter_id"] for adapter in adapters],
        "agent_tool_mapping": mapping,
        "unmapped_required_tools": unmapped,
        "forbidden_mapped_tools": forbidden_mapped,
        "all_agent_required_tools_mapped": not unmapped and not forbidden_mapped,
        "all_adapters_read_only": all_read_only,
        "output_contracts_traceable": output_contracts_ok,
        "broker_integration_disabled": broker_disabled,
        "real_trade_allowed": False if no_real_trade else True,
        "blocking_issues": blocking,
        "controls": spec.get("global_controls", []) + ["read_only_analysis", "no_broker_integration", "no_real_trade_action"],
    }


def output_contract_valid(adapter: dict[str, Any]) -> bool:
    required = set(adapter.get("output_contract", {}).get("required_fields", []))
    return {"tool_result_id", "evidence_items"} <= required


def write_tool_adapter_manifest(root: Path, roster: dict[str, Any]) -> dict[str, Any]:
    report = evaluate_tool_adapter_contracts(roster)
    write_yaml(root / "tools" / "tool-adapter-manifest.yaml", report)
    return report

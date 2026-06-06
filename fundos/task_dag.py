from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fundos.io import DISCLAIMER, REPO_ROOT, read_yaml, write_yaml
from fundos.evidence import enrich_evidence_pack
from fundos.research_tasks import build_next_research_tasks

SPEC_REL = "specs/workflows/research-task-dag.yaml"
TASK_DAG_VERSION = "0.1.0"
PLANNED_NODE_IDS = {"evaluation", "evolution_candidate_generation"}


def load_task_dag_spec() -> dict[str, Any]:
    spec = read_yaml(REPO_ROOT / SPEC_REL)
    spec["source_path"] = SPEC_REL
    return spec


def default_task_dag_harness() -> dict[str, Any]:
    return {
        "artifact_type": "research_task_dag_harness",
        "task_dag_quality_score": 0,
        "node_count": 0,
        "edge_count": 0,
        "blocked_node_count": 0,
        "topological_order_valid": False,
        "missing_artifacts": [],
        "blocking_issues": ["missing_task_dag_harness"],
        "controls": [],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
        "research_gap_count": 0,
        "next_research_tasks": [],
        "agent_reasoning_hypothesis_task_count": 0,
        "agent_reasoning_hypothesis_quality": default_agent_reasoning_hypothesis_quality(),
    }


def load_task_dag_harness(run_path: Path | None) -> dict[str, Any]:
    if not run_path:
        return default_task_dag_harness()
    path = run_path / "harness" / "task-dag-harness.yaml"
    if not path.exists():
        return default_task_dag_harness()
    loaded = read_yaml(path) or {}
    base = default_task_dag_harness()
    base.update(loaded)
    return base


def load_research_gap_task_manifest(run_path: Path) -> dict[str, Any]:
    path = run_path / "workflow" / "research-gap-tasks.yaml"
    if not path.exists():
        return {
            "artifact_type": "research_gap_task_manifest",
            "run_id": read_run_id(run_path),
            "research_gap_count": 0,
            "tasks": [],
            "controls": ["no_real_trade_action", "broker_integration_disabled"],
            "real_trade_allowed": False,
            "broker_integration": "disabled",
        }
    loaded = read_yaml(path) or {}
    loaded.setdefault("tasks", [])
    loaded.setdefault("research_gap_count", len(loaded.get("tasks", [])))
    loaded.setdefault("real_trade_allowed", False)
    loaded.setdefault("broker_integration", "disabled")
    return loaded


def write_research_gap_followup_result(run_path: Path, task_id: str) -> dict[str, Any]:
    manifest = load_research_gap_task_manifest(run_path)
    task = next((row for row in manifest.get("tasks", []) if row.get("task_id") == task_id), None)
    if not task:
        raise KeyError(task_id)
    result = build_research_gap_followup_result(run_path, manifest, task)
    out_dir = run_path / "follow_up" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = safe_filename(task_id.replace(":", "_"))
    result_rel = f"follow_up/results/{stem}.yaml"
    result["result_path"] = result_rel
    write_yaml(run_path / result_rel, result)
    write_research_gap_result_markdown(out_dir / f"{stem}.md", result)
    return result


def reconcile_research_gap_followups(run_path: Path) -> dict[str, Any]:
    manifest_path = run_path / "workflow" / "research-gap-tasks.yaml"
    dag_path = run_path / "workflow" / "task-dag.yaml"
    harness_path = run_path / "harness" / "task-dag-harness.yaml"

    manifest = load_research_gap_task_manifest(run_path)
    results = load_research_gap_followup_results(run_path)
    results_by_task_id = {row.get("task_id"): row for row in results if row.get("task_id")}
    answered_count = 0
    closed_count = 0
    unsafe_blocked_count = 0
    pending_count = 0
    accepted_evidence_count = 0
    reconciled_tasks = []
    for task in manifest.get("tasks", []):
        reconciled = dict(task)
        result = results_by_task_id.get(task.get("task_id"))
        if task.get("closure_status") == "closed_by_accepted_evidence":
            status = "closed_by_accepted_evidence"
            closed_count += 1
            accepted_evidence_count += len(task.get("accepted_evidence_ids", []) or [])
            reconciled["status"] = status
            reconciled["real_trade_allowed"] = False
            reconciled["broker_integration"] = "disabled"
        elif result:
            answered_count += 1
            status = reconciled_status_for_result(result)
            if status == "answered_unsafe_blocked":
                unsafe_blocked_count += 1
            reconciled.update(
                {
                    "status": status,
                    "answer_status": result.get("status"),
                    "result_path": result.get("result_path") or result_path_for_task_id(str(task.get("task_id"))),
                    "result_category": result.get("category"),
                    "result_owner_agent_id": result.get("owner_agent_id"),
                    "real_trade_allowed": False if status != "answered_unsafe_blocked" else bool(result.get("real_trade_allowed")),
                    "broker_integration": "disabled" if status != "answered_unsafe_blocked" else result.get("broker_integration", "violation"),
                }
            )
        else:
            pending_count += 1
        reconciled_tasks.append(reconciled)

    manifest["tasks"] = reconciled_tasks
    manifest["research_gap_count"] = len(reconciled_tasks)
    manifest["answered_count"] = answered_count
    manifest["closed_count"] = closed_count
    manifest["pending_count"] = pending_count
    manifest["unsafe_blocked_count"] = unsafe_blocked_count
    manifest["accepted_evidence_count"] = accepted_evidence_count
    manifest["real_trade_allowed"] = False
    manifest["broker_integration"] = "disabled"
    if manifest_path.exists():
        write_yaml(manifest_path, manifest)
    hypothesis_quality = evaluate_agent_reasoning_hypothesis_tasks(reconciled_tasks)

    if dag_path.exists():
        dag = read_yaml(dag_path) or {}
        task_by_id = {task.get("task_id"): task for task in reconciled_tasks}
        updated_nodes = []
        for node in dag.get("nodes", []):
            updated = dict(node)
            if str(updated.get("node_id", "")).startswith("research_gap:"):
                task = task_by_id.get(updated.get("task_id"))
                if task:
                    updated["status"] = task.get("status", updated.get("status"))
                    for key in ["answer_status", "result_path", "result_category", "result_owner_agent_id", "closure_status", "accepted_evidence_ids", "accepted_claim_ids"]:
                        if key in task:
                            updated[key] = task[key]
                    updated["real_trade_allowed"] = False
                    updated["broker_integration"] = "disabled"
            updated_nodes.append(updated)
        dag["nodes"] = updated_nodes
        dag["research_gap_answered_count"] = answered_count
        dag["research_gap_closed_count"] = closed_count
        dag["research_gap_pending_count"] = pending_count
        dag["research_gap_unsafe_blocked_count"] = unsafe_blocked_count
        dag["research_gap_accepted_evidence_count"] = accepted_evidence_count
        dag["agent_reasoning_hypothesis_task_count"] = hypothesis_quality["routed_count"]
        dag["agent_reasoning_hypothesis_quality"] = hypothesis_quality
        dag["real_trade_allowed"] = False
        dag["broker_integration"] = "disabled"
        write_yaml(dag_path, dag)

    if harness_path.exists():
        harness = read_yaml(harness_path) or {}
        harness["research_gap_answered_count"] = answered_count
        harness["research_gap_closed_count"] = closed_count
        harness["research_gap_pending_count"] = pending_count
        harness["research_gap_unsafe_blocked_count"] = unsafe_blocked_count
        harness["research_gap_accepted_evidence_count"] = accepted_evidence_count
        harness["agent_reasoning_hypothesis_task_count"] = hypothesis_quality["routed_count"]
        harness["agent_reasoning_hypothesis_quality"] = hypothesis_quality
        harness["research_gap_result_paths"] = [task.get("result_path") for task in reconciled_tasks if task.get("result_path")]
        harness["real_trade_allowed"] = False
        harness["broker_integration"] = "disabled"
        if unsafe_blocked_count:
            issues = list(harness.get("blocking_issues", []))
            issues.append("research_gap_followup_unsafe_blocked")
            harness["blocking_issues"] = sorted(set(issues))
        write_yaml(harness_path, harness)

    return {
        "artifact_type": "research_gap_followup_reconciliation",
        "run_id": manifest.get("run_id") or read_run_id(run_path),
        "research_gap_count": len(reconciled_tasks),
        "answered_count": answered_count,
        "closed_count": closed_count,
        "pending_count": pending_count,
        "unsafe_blocked_count": unsafe_blocked_count,
        "accepted_evidence_count": accepted_evidence_count,
        "result_count": len(results),
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def close_research_gap_followup_with_evidence(run_path: Path, task_id: str, accepted_evidence: list[dict[str, Any]]) -> dict[str, Any]:
    manifest = load_research_gap_task_manifest(run_path)
    task = next((row for row in manifest.get("tasks", []) if row.get("task_id") == task_id), None)
    if not task:
        raise KeyError(task_id)
    if not accepted_evidence:
        raise ValueError("accepted_evidence is required to close a research gap")
    category = str(task.get("category") or "")
    safe_items = [normalize_followup_evidence_item(item, category) for item in accepted_evidence]
    validation_errors = validate_followup_evidence_items(safe_items, category)
    if validation_errors:
        raise ValueError("evidence_validation_failed:" + ";".join(validation_errors))
    pack = load_or_empty_evidence_pack(run_path)
    existing = pack.get("evidence_items", [])
    existing_ids = {item.get("id") for item in existing}
    new_items = [item for item in safe_items if item.get("id") not in existing_ids]
    pack["evidence_items"] = existing + new_items
    update_research_plan_coverage_for_closure(pack, category, len(safe_items))
    enrich_evidence_pack(pack)
    write_yaml(run_path / "evidence" / "evidence-pack.yaml", pack)

    updated_tasks = []
    for row in manifest.get("tasks", []):
        updated = dict(row)
        if row.get("task_id") == task_id:
            updated.update(
                {
                    "status": "closed_by_accepted_evidence",
                    "closure_status": "closed_by_accepted_evidence",
                    "accepted_evidence_ids": [item["id"] for item in safe_items],
                    "accepted_claim_ids": [claim.get("claim_id") for item in safe_items for claim in item.get("claims", []) if claim.get("claim_id")],
                    "real_trade_allowed": False,
                    "broker_integration": "disabled",
                }
            )
        updated_tasks.append(updated)
    manifest["tasks"] = updated_tasks
    manifest["real_trade_allowed"] = False
    manifest["broker_integration"] = "disabled"
    write_yaml(run_path / "workflow" / "research-gap-tasks.yaml", manifest)
    reconciliation = reconcile_research_gap_followups(run_path)
    return {
        "artifact_type": "research_gap_followup_evidence_closure",
        "run_id": manifest.get("run_id") or read_run_id(run_path),
        "task_id": task_id,
        "category": category,
        "source": task.get("source"),
        "source_agent_id": task.get("source_agent_id"),
        "source_evidence_id": task.get("source_evidence_id"),
        "source_claim_id": task.get("source_claim_id"),
        "hypothesis": task.get("hypothesis"),
        "validation_required": task.get("validation_required"),
        "accepted_evidence_count": len(safe_items),
        "accepted_evidence_ids": [item["id"] for item in safe_items],
        "closed_count": reconciliation.get("closed_count", 0),
        "pending_count": reconciliation.get("pending_count", 0),
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def load_or_empty_evidence_pack(run_path: Path) -> dict[str, Any]:
    path = run_path / "evidence" / "evidence-pack.yaml"
    if path.exists():
        return read_yaml(path) or {}
    return {
        "run_id": read_run_id(run_path),
        "market": "CN_A_SHARE",
        "query": "",
        "retrieval_plan": [],
        "evidence_items": [],
        "unresolved_gaps": [],
        "research_plan_coverage": {},
    }


def normalize_followup_evidence_item(item: dict[str, Any], category: str) -> dict[str, Any]:
    normalized = dict(item)
    normalized.setdefault("source_id", "accepted_followup_evidence")
    normalized.setdefault("source_type", category)
    normalized.setdefault("source_tier", "tier_1_primary_fact")
    normalized.setdefault("confidence", "high" if normalized.get("source_tier") == "tier_1_primary_fact" else "medium")
    normalized.setdefault("claims", [])
    normalized["research_category"] = category
    normalized["accepted_for_research_gap"] = True
    normalized["real_trade_allowed"] = False
    normalized["broker_integration"] = "disabled"
    return normalized


def validate_followup_evidence_items(items: list[dict[str, Any]], category: str) -> list[str]:
    errors: list[str] = []
    allowed_tiers = {"tier_1_primary_fact", "tier_2_canonical_framework", "tier_3_verified_public_practitioner"}
    category_allowed_source_types = {
        "market_data": {"market_data", "chart_summary"},
        "case_library": {"case", "historical_case"},
        "announcement": {"announcement", "financial_report"},
        "policy": {"policy"},
        "news": {"news", "web"},
        "social_signal": {"social_signal", "web"},
    }
    allowed_source_types = set(category_allowed_source_types.get(category, set())) | {category}
    for index, item in enumerate(items):
        prefix = f"evidence_items[{index}]"
        for field in ["id", "source_type", "source_tier", "summary", "confidence", "claims"]:
            if not item.get(field):
                errors.append(f"{prefix}.{field}_missing")
        source_tier = item.get("source_tier")
        if source_tier not in allowed_tiers:
            errors.append(f"{prefix}.source_tier_not_accepted:{source_tier}")
        source_type = item.get("source_type")
        if source_type not in allowed_source_types:
            errors.append(f"{prefix}.source_type_mismatch:{source_type}!={category}")
        claims = item.get("claims") or []
        if not isinstance(claims, list) or not claims:
            errors.append(f"{prefix}.claims_empty")
            claims = []
        for claim_index, claim in enumerate(claims):
            claim_prefix = f"{prefix}.claims[{claim_index}]"
            for field in ["claim_id", "claim_text", "claim_type", "confidence", "relevant_to", "supports", "contradicts"]:
                if field not in claim or claim.get(field) in (None, ""):
                    errors.append(f"{claim_prefix}.{field}_missing")
            if source_tier == "tier_1_primary_fact" and claim.get("claim_type") not in {"fact", "inference"}:
                errors.append(f"{claim_prefix}.claim_type_not_fact_or_inference")
        if item.get("real_trade_allowed") is not False:
            errors.append(f"{prefix}.real_trade_allowed_must_be_false")
        if item.get("broker_integration") != "disabled":
            errors.append(f"{prefix}.broker_integration_must_be_disabled")
    return errors


def update_research_plan_coverage_for_closure(pack: dict[str, Any], category: str, accepted_count: int) -> None:
    coverage = pack.get("research_plan_coverage") or {}
    missing = [row for row in coverage.get("missing_categories", []) if row != category]
    counts = dict(coverage.get("category_counts", {}))
    counts[category] = counts.get(category, 0) + accepted_count
    coverage["missing_categories"] = missing
    coverage["category_counts"] = counts
    coverage["categories_covered"] = len([value for value in counts.values() if value > 0])
    pack["research_plan_coverage"] = coverage


def load_research_gap_followup_results(run_path: Path) -> list[dict[str, Any]]:
    result_dir = run_path / "follow_up" / "results"
    if not result_dir.exists():
        return []
    results = []
    for path in sorted(result_dir.glob("*.yaml")):
        loaded = read_yaml(path) or {}
        if loaded.get("artifact_type") == "research_gap_followup_result":
            loaded.setdefault("result_path", str(path.relative_to(run_path)))
            results.append(loaded)
    return results


def result_path_for_task_id(task_id: str) -> str:
    return f"follow_up/results/{safe_filename(task_id.replace(':', '_'))}.yaml"


def reconciled_status_for_result(result: dict[str, Any]) -> str:
    if result.get("real_trade_allowed") or result.get("broker_integration") != "disabled":
        return "answered_unsafe_blocked"
    if result.get("status") == "needs_evidence":
        return "answered_needs_evidence"
    return "answered"


def load_research_gap_followup_quality(run_path: Path | None) -> dict[str, Any]:
    if not run_path:
        return default_research_gap_followup_quality()
    manifest = load_research_gap_task_manifest(run_path)
    closed_tasks = [task for task in manifest.get("tasks", []) if task.get("status") == "closed_by_accepted_evidence"]
    closed_categories = sorted({str(task.get("category")) for task in closed_tasks if task.get("category")})
    accepted_evidence_ids = sorted({str(eid) for task in closed_tasks for eid in task.get("accepted_evidence_ids", []) if eid})
    result_dir = run_path / "follow_up" / "results"
    if not result_dir.exists():
        report = default_research_gap_followup_quality()
        report.update(closed_quality_fields(closed_tasks, closed_categories, accepted_evidence_ids))
        if closed_tasks:
            report["research_gap_followup_score"] = 90
        return report
    results = []
    for path in sorted(result_dir.glob("*.yaml")):
        loaded = read_yaml(path) or {}
        if loaded.get("artifact_type") == "research_gap_followup_result":
            results.append(loaded)
    if not results:
        report = default_research_gap_followup_quality()
        report.update(closed_quality_fields(closed_tasks, closed_categories, accepted_evidence_ids))
        if closed_tasks:
            report["research_gap_followup_score"] = 90
        return report
    unsafe = [row for row in results if row.get("real_trade_allowed") or row.get("broker_integration") != "disabled"]
    with_requests = [row for row in results if row.get("evidence_requests")]
    score = 65 + min(20, len(with_requests) * 10)
    if closed_tasks:
        score = max(score, 90 + min(5, len(accepted_evidence_ids)))
    if unsafe:
        score = 0
    report = {
        "artifact_type": "research_gap_followup_quality",
        "result_count": len(results),
        "owner_agent_count": len({row.get("owner_agent_id") for row in results if row.get("owner_agent_id")}),
        "categories": sorted({str(row.get("category")) for row in results if row.get("category")}),
        "results_with_evidence_requests": len(with_requests),
        "all_safe": not unsafe,
        "blocking_issues": [f"unsafe_research_gap_followup:{row.get('task_id')}" for row in unsafe],
        "research_gap_followup_score": score,
        "real_trade_allowed": False if not unsafe else True,
        "broker_integration": "disabled" if not unsafe else "violation",
    }
    report.update(closed_quality_fields(closed_tasks, closed_categories, accepted_evidence_ids))
    return report


def default_research_gap_followup_quality() -> dict[str, Any]:
    return {
        "artifact_type": "research_gap_followup_quality",
        "result_count": 0,
        "owner_agent_count": 0,
        "categories": [],
        "results_with_evidence_requests": 0,
        "closed_count": 0,
        "closed_categories": [],
        "accepted_evidence_count": 0,
        "accepted_evidence_ids": [],
        "all_safe": True,
        "blocking_issues": [],
        "research_gap_followup_score": 0,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def closed_quality_fields(closed_tasks: list[dict[str, Any]], closed_categories: list[str], accepted_evidence_ids: list[str]) -> dict[str, Any]:
    return {
        "closed_count": len(closed_tasks),
        "closed_categories": closed_categories,
        "accepted_evidence_count": len(accepted_evidence_ids),
        "accepted_evidence_ids": accepted_evidence_ids,
    }


def build_research_gap_followup_result(run_path: Path, manifest: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    brief_rel = task.get("brief_path", "")
    brief_path = run_path / brief_rel
    brief_text = brief_path.read_text(encoding="utf-8") if brief_path.exists() else ""
    category = task.get("category")
    owner = task.get("owner_agent_id") or task.get("owner_agent")
    return {
        "artifact_type": "research_gap_followup_result",
        "run_id": manifest.get("run_id"),
        "task_id": task.get("task_id"),
        "category": category,
        "owner_agent_id": owner,
        "source": task.get("source"),
        "source_agent_id": task.get("source_agent_id"),
        "source_evidence_id": task.get("source_evidence_id"),
        "source_claim_id": task.get("source_claim_id"),
        "hypothesis": task.get("hypothesis"),
        "validation_required": task.get("validation_required"),
        "source_brief_path": brief_rel,
        "status": "needs_evidence",
        "agent_position": "Cannot close the research gap until accepted evidence is retrieved and reconciled.",
        "evidence_requests": evidence_requests_for_category(str(category)),
        "source_quality_rules": [
            "prefer tier_1_primary_fact before opinion or social signal",
            "label practitioner/KOL material as methodology or signal unless verified by primary evidence",
            "preserve contradictions and unresolved gaps for context compression",
        ],
        "context_update_request": {
            "target_context_pack": owner,
            "must_preserve": ["evidence_ids", "claim_ids", "missing_evidence", "contradictions", "source_tiers"],
            "reason": task.get("reason"),
        },
        "next_action": "retrieve_evidence_then_rerun_tool_harness_and_evaluation",
        "brief_excerpt": brief_text[:500],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
        "disclaimer": DISCLAIMER,
    }


def evidence_requests_for_category(category: str) -> list[dict[str, str]]:
    templates = {
        "market_data": [
            {"source_type": "market_data", "required_evidence": "price, volume, liquidity, relative strength, and drawdown context"},
            {"source_type": "chart_summary", "required_evidence": "trend phase, trigger, invalidation, and volatility regime"},
        ],
        "case_library": [
            {"source_type": "historical_case", "required_evidence": "comparable market episodes, failure cases, and analogy limits"},
        ],
        "announcement": [
            {"source_type": "announcement", "required_evidence": "issuer filings, exchange disclosures, and financial statement facts"},
        ],
        "policy": [
            {"source_type": "policy", "required_evidence": "official policy text, implementation body, and funding or enforcement mechanism"},
        ],
        "news": [
            {"source_type": "news", "required_evidence": "multi-source current news with event date and affected entities"},
        ],
        "social_signal": [
            {"source_type": "social_signal", "required_evidence": "KOL or crowd signal labeled as low-tier hypothesis, not direct trade evidence"},
        ],
    }
    return templates.get(category, [{"source_type": category, "required_evidence": "accepted evidence for the missing research category"}])


def write_research_gap_result_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [
        f"# Follow-up Result: {result.get('category')}",
        "",
        f"task_id: {result.get('task_id')}",
        f"owner_agent_id: {result.get('owner_agent_id')}",
        f"status: {result.get('status')}",
        "",
        "## Agent Position",
        "",
        str(result.get("agent_position")),
        "",
        "## Evidence Requests",
        "",
    ]
    for item in result.get("evidence_requests", []):
        lines.append(f"- {item.get('source_type')}: {item.get('required_evidence')}")
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- real_trade_allowed: False",
            "- broker_integration: disabled",
            "",
            DISCLAIMER,
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_task_dag(run_path: Path, selected_agents: list[dict[str, str]], evidence_pack: dict[str, Any]) -> dict[str, Any]:
    spec = load_task_dag_spec()
    selected_ids = [row["agent_id"] for row in selected_agents]
    nodes = [build_runtime_node(run_path, node, selected_ids) for node in spec.get("nodes", [])]
    run_id = evidence_pack.get("run_id") or read_run_id(run_path)
    coverage = evidence_pack.get("research_plan_coverage") or {}
    next_research_tasks = build_next_research_tasks(coverage, run_id or "unknown-run")
    next_research_tasks.extend(build_agent_reasoning_hypothesis_tasks(run_path, run_id or "unknown-run"))
    next_research_tasks = merge_existing_research_gap_tasks(run_path, next_research_tasks)
    nodes.extend(build_research_gap_nodes(next_research_tasks))
    edges = build_edges(nodes)
    missing_artifacts = [
        {"node_id": node["node_id"], "artifact": artifact}
        for node in nodes
        for artifact in node.get("missing_artifacts", [])
    ]
    topological_ok = validate_topological_order(nodes)
    blocked = [node for node in nodes if node.get("status") == "waiting_for_artifact"]
    controls = spec.get("controls", [])
    blocking_issues = []
    if not topological_ok:
        blocking_issues.append("task_dag_topological_order_invalid")
    if missing_artifacts:
        blocking_issues.append("task_dag_missing_required_artifacts")
    if not required_controls_present(controls):
        blocking_issues.append("task_dag_missing_safety_controls")
    score = quality_score(nodes, edges, topological_ok, controls)
    hypothesis_quality = evaluate_agent_reasoning_hypothesis_tasks(next_research_tasks)
    dag = {
        "version": TASK_DAG_VERSION,
        "artifact_type": "research_task_dag",
        "workflow_id": spec.get("workflow_id"),
        "source_path": spec.get("source_path"),
        "run_id": run_id,
        "query": evidence_pack.get("query"),
        "market": evidence_pack.get("market", "CN_A_SHARE"),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "blocked_node_count": len(blocked),
        "task_dag_quality_score": score,
        "nodes": nodes,
        "edges": edges,
        "missing_artifacts": missing_artifacts,
        "topological_order_valid": topological_ok,
        "controls": controls,
        "research_plan_coverage": coverage,
        "research_gap_count": len(next_research_tasks),
        "next_research_tasks": next_research_tasks,
        "agent_reasoning_hypothesis_task_count": hypothesis_quality["routed_count"],
        "agent_reasoning_hypothesis_quality": hypothesis_quality,
        "disclaimer": DISCLAIMER,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    harness = {
        "artifact_type": "research_task_dag_harness",
        "workflow_id": spec.get("workflow_id"),
        "run_id": dag["run_id"],
        "task_dag_quality_score": score,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "blocked_node_count": len(blocked),
        "planned_node_count": sum(1 for node in nodes if node.get("status") == "planned"),
        "ready_node_count": sum(1 for node in nodes if node.get("status") == "ready"),
        "topological_order_valid": topological_ok,
        "missing_artifacts": missing_artifacts,
        "blocking_issues": blocking_issues,
        "controls": controls,
        "research_plan_coverage": coverage,
        "research_gap_count": len(next_research_tasks),
        "next_research_tasks": next_research_tasks,
        "agent_reasoning_hypothesis_task_count": hypothesis_quality["routed_count"],
        "agent_reasoning_hypothesis_quality": hypothesis_quality,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    write_yaml(run_path / "workflow" / "task-dag.yaml", dag)
    write_yaml(run_path / "harness" / "task-dag-harness.yaml", harness)
    write_research_gap_task_artifacts(run_path, dag["run_id"], next_research_tasks)
    reconcile_research_gap_followups(run_path)
    return read_yaml(run_path / "workflow" / "task-dag.yaml") or dag


def merge_existing_research_gap_tasks(run_path: Path, next_research_tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing_manifest = load_research_gap_task_manifest(run_path)
    by_task_id = {task.get("task_id"): dict(task) for task in existing_manifest.get("tasks", []) if task.get("task_id")}
    by_category = {task.get("category"): dict(task) for task in existing_manifest.get("tasks", []) if task.get("category")}
    merged: list[dict[str, Any]] = []
    seen_task_ids: set[str] = set()
    for task in next_research_tasks:
        existing = by_task_id.get(task.get("task_id")) or by_category.get(task.get("category"))
        if existing and existing.get("status") in {"closed_by_accepted_evidence", "answered_needs_evidence", "answered_unsafe_blocked", "answered"}:
            combined = dict(task)
            combined.update(existing)
            merged.append(combined)
            seen_task_ids.add(str(combined.get("task_id")))
        else:
            merged.append(task)
            if task.get("task_id"):
                seen_task_ids.add(str(task.get("task_id")))
    for existing in by_task_id.values():
        if existing.get("status") == "closed_by_accepted_evidence" and str(existing.get("task_id")) not in seen_task_ids:
            merged.append(existing)
            seen_task_ids.add(str(existing.get("task_id")))
    return merged


def build_agent_reasoning_hypothesis_tasks(run_path: Path, run_id: str) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for structured_path in sorted((run_path / "agent_work").glob("*.structured.yaml")):
        output = read_yaml(structured_path) or {}
        agent_id = str(output.get("agent_id") or structured_path.stem.replace(".structured", ""))
        reasoning_layers = output.get("reasoning_layers") or {}
        if reasoning_layers.get("real_trade_allowed") or reasoning_layers.get("broker_integration", "disabled") != "disabled":
            continue
        for hypothesis in reasoning_layers.get("hypotheses_to_validate", []) or []:
            if hypothesis.get("layer") != "hypothesis_to_validate":
                continue
            evidence_id = str(hypothesis.get("evidence_id") or "")
            claim_id = str(hypothesis.get("claim_id") or "")
            hypothesis_text = str(hypothesis.get("hypothesis") or hypothesis.get("claim_text") or "")
            validation_required = str(hypothesis.get("validation_required") or "primary_or_cross_validated_evidence_required")
            dedupe_key = (agent_id, evidence_id, claim_id, validation_required if evidence_id or claim_id else hypothesis_text)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            category_suffix = claim_id or evidence_id or stable_short_hash(hypothesis_text or validation_required)
            category = safe_filename(f"agent_hypothesis_validation_{agent_id}_{category_suffix}")
            tasks.append(
                {
                    "task_id": f"{run_id}:research_gap:hypothesis:{len(tasks) + 1:03d}",
                    "category": category,
                    "owner_agent": agent_id,
                    "owner_agent_id": agent_id,
                    "priority": "high" if evidence_id or claim_id else "medium",
                    "reason": f"Agent reasoning hypothesis requires validation before it can influence durable learning or committee conclusions: {hypothesis_text}",
                    "source": "agent_reasoning_layer",
                    "source_agent_id": agent_id,
                    "source_evidence_id": evidence_id or None,
                    "source_claim_id": claim_id or None,
                    "source_type": hypothesis.get("source_type"),
                    "source_tier": hypothesis.get("source_tier"),
                    "hypothesis": hypothesis_text,
                    "validation_required": validation_required,
                    "status": "planned",
                    "real_trade_allowed": False,
                    "broker_integration": "disabled",
                }
            )
    return tasks


def evaluate_agent_reasoning_hypothesis_tasks(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    routed = [task for task in tasks if task.get("source") == "agent_reasoning_layer"]
    if not routed:
        return default_agent_reasoning_hypothesis_quality()
    all_have_validation = all(bool(task.get("validation_required")) for task in routed)
    all_have_source_agent = all(bool(task.get("source_agent_id")) for task in routed)
    all_safe = all(not task.get("real_trade_allowed") and task.get("broker_integration", "disabled") == "disabled" for task in routed)
    score = 100
    if not all_have_validation:
        score -= 30
    if not all_have_source_agent:
        score -= 20
    if not all_safe:
        score = 0
    return {
        "artifact_type": "agent_reasoning_hypothesis_followup_quality",
        "routed_count": len(routed),
        "all_have_validation_required": all_have_validation,
        "all_have_source_agent": all_have_source_agent,
        "all_safe": all_safe,
        "score": max(score, 0),
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def default_agent_reasoning_hypothesis_quality() -> dict[str, Any]:
    return {
        "artifact_type": "agent_reasoning_hypothesis_followup_quality",
        "routed_count": 0,
        "all_have_validation_required": True,
        "all_have_source_agent": True,
        "all_safe": True,
        "score": 0,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def stable_short_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]


def write_research_gap_task_artifacts(run_path: Path, run_id: str | None, next_research_tasks: list[dict[str, Any]]) -> dict[str, Any]:
    tasks = []
    for task in next_research_tasks:
        category = task["category"]
        brief_rel = f"follow_up/research_gap_{safe_filename(category)}.md"
        enriched = dict(task)
        enriched["brief_path"] = brief_rel
        enriched["status"] = task.get("status") or "planned"
        enriched["allowed_output"] = "research_follow_up_brief_only"
        enriched["real_trade_allowed"] = False
        enriched["broker_integration"] = "disabled"
        tasks.append(enriched)
        write_research_gap_brief(run_path / brief_rel, run_id, enriched)
    manifest = {
        "artifact_type": "research_gap_task_manifest",
        "run_id": run_id,
        "research_gap_count": len(tasks),
        "tasks": tasks,
        "controls": [
            "planned_follow_up_research_only",
            "no_real_trade_action",
            "broker_integration_disabled",
            "evidence_hierarchy_required",
        ],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    write_yaml(run_path / "workflow" / "research-gap-tasks.yaml", manifest)
    return manifest


def write_research_gap_brief(path: Path, run_id: str | None, task: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(
        [
            f"# Research Gap Follow-up: {task['category']}",
            "",
            f"run_id: {run_id}",
            f"task_id: {task.get('task_id')}",
            f"owner_agent_id: {task.get('owner_agent_id') or task.get('owner_agent')}",
            f"category: {task['category']}",
            f"priority: {task.get('priority', 'medium')}",
            f"status: {task.get('status', 'planned')}",
            f"source: {task.get('source', 'research_plan_coverage')}",
            f"source_agent_id: {task.get('source_agent_id', '')}",
            f"source_evidence_id: {task.get('source_evidence_id', '')}",
            f"source_claim_id: {task.get('source_claim_id', '')}",
            f"validation_required: {task.get('validation_required', 'accepted_evidence_required')}",
            "",
            "## Reason",
            "",
            str(task.get("reason", "Research plan category had no accepted evidence.")),
            "",
            "## Hypothesis Metadata",
            "",
            f"- hypothesis: {task.get('hypothesis', '')}",
            f"- source_type: {task.get('source_type', '')}",
            f"- source_tier: {task.get('source_tier', '')}",
            "",
            "## Required work",
            "",
            "- Retrieve or request evidence for this missing research-plan category.",
            "- Separate primary facts, practitioner views, social signals, and inference.",
            "- Cite Evidence IDs / Claim IDs when the follow-up is converted into run evidence.",
            "- Preserve contradictions and unresolved gaps for context compression.",
            "",
            "## Allowed output",
            "",
            "- Follow-up research brief.",
            "- Evidence requests and source-quality notes.",
            "- Updated next_research_tasks if the gap remains unresolved.",
            "",
            "## Forbidden output",
            "",
            "- No real trade instruction.",
            "- No broker action or order placement.",
            "- No high-confidence conclusion without accepted evidence.",
            "",
            DISCLAIMER,
            "",
        ]
    )
    path.write_text(text, encoding="utf-8")


def safe_filename(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value)


def build_research_gap_nodes(next_research_tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nodes = []
    for task in next_research_tasks:
        category = task["category"]
        nodes.append(
            {
                "node_id": f"research_gap:{category}",
                "owner_role": task.get("owner_agent_id") or task.get("owner_agent"),
                "owner_agent_id": task.get("owner_agent_id") or task.get("owner_agent"),
                "phase": "follow_up_research",
                "description": task.get("reason"),
                "depends_on": ["evaluation"],
                "expected_artifacts": [],
                "missing_artifacts": [],
                "status": "planned",
                "task_id": task.get("task_id"),
                "category": category,
                "priority": task.get("priority", "medium"),
                "real_trade_allowed": False,
                "broker_integration": "disabled",
            }
        )
    return nodes


def build_runtime_node(run_path: Path, node: dict[str, Any], selected_ids: list[str]) -> dict[str, Any]:
    expected = list(node.get("expected_artifacts", []))
    node_id = node["node_id"]
    missing = missing_artifacts_for(run_path, node_id, expected, selected_ids)
    if node_id in PLANNED_NODE_IDS and missing:
        status = "planned"
    elif missing:
        status = "waiting_for_artifact"
    else:
        status = "ready" if node.get("depends_on") or not missing else "ready"
    runtime = {
        "node_id": node_id,
        "owner_role": node.get("owner_role"),
        "phase": node.get("phase"),
        "description": node.get("description"),
        "depends_on": list(node.get("depends_on", [])),
        "expected_artifacts": expected,
        "missing_artifacts": missing,
        "status": status,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    if node_id == "agent_analysis":
        runtime["assigned_agents"] = selected_ids
    if node_id == "agent_staffing":
        runtime["assigned_agents"] = selected_ids
        runtime["agent_count"] = len(selected_ids)
    return runtime


def missing_artifacts_for(run_path: Path, node_id: str, expected: list[str], selected_ids: list[str]) -> list[str]:
    missing = [artifact for artifact in expected if not (run_path / artifact).exists()]
    if node_id == "task_intake" and (run_path / "run.yaml").exists():
        missing = [artifact for artifact in missing if artifact != "task-brief.md"]
    if node_id == "agent_staffing" and selected_ids:
        missing = [artifact for artifact in missing if artifact != "selected-agents.yaml"]
    if node_id == "context_packaging" and (run_path / "context").exists():
        return []
    return missing


def build_edges(nodes: list[dict[str, Any]]) -> list[dict[str, str]]:
    edges = []
    for node in nodes:
        for upstream in node.get("depends_on", []):
            edges.append({"from": upstream, "to": node["node_id"]})
    return edges


def validate_topological_order(nodes: list[dict[str, Any]]) -> bool:
    seen: set[str] = set()
    node_ids = {node["node_id"] for node in nodes}
    for node in nodes:
        deps = node.get("depends_on", [])
        if any(dep not in node_ids or dep not in seen for dep in deps):
            return False
        seen.add(node["node_id"])
    return True


def required_controls_present(controls: list[str]) -> bool:
    required = {"no_real_trade_action", "broker_integration_disabled", "human_approval_required_for_evolution_apply"}
    return required.issubset(set(controls))


def quality_score(nodes: list[dict[str, Any]], edges: list[dict[str, str]], topological_ok: bool, controls: list[str]) -> int:
    score = 55
    if len(nodes) >= 13:
        score += 15
    if len(edges) >= 12:
        score += 10
    if topological_ok:
        score += 10
    if required_controls_present(controls):
        score += 10
    blocked = sum(1 for node in nodes if node.get("status") == "waiting_for_artifact")
    score -= min(30, blocked * 5)
    return max(0, min(100, score))


def read_run_id(run_path: Path) -> str | None:
    path = run_path / "run.yaml"
    if not path.exists():
        return None
    loaded = read_yaml(path) or {}
    return loaded.get("run_id")

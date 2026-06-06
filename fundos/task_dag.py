from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.io import DISCLAIMER, REPO_ROOT, read_yaml, write_yaml
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


def write_task_dag(run_path: Path, selected_agents: list[dict[str, str]], evidence_pack: dict[str, Any]) -> dict[str, Any]:
    spec = load_task_dag_spec()
    selected_ids = [row["agent_id"] for row in selected_agents]
    nodes = [build_runtime_node(run_path, node, selected_ids) for node in spec.get("nodes", [])]
    run_id = evidence_pack.get("run_id") or read_run_id(run_path)
    coverage = evidence_pack.get("research_plan_coverage") or {}
    next_research_tasks = build_next_research_tasks(coverage, run_id or "unknown-run")
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
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    write_yaml(run_path / "workflow" / "task-dag.yaml", dag)
    write_yaml(run_path / "harness" / "task-dag-harness.yaml", harness)
    write_research_gap_task_artifacts(run_path, dag["run_id"], next_research_tasks)
    return dag


def write_research_gap_task_artifacts(run_path: Path, run_id: str | None, next_research_tasks: list[dict[str, Any]]) -> dict[str, Any]:
    tasks = []
    for task in next_research_tasks:
        category = task["category"]
        brief_rel = f"follow_up/research_gap_{safe_filename(category)}.md"
        enriched = dict(task)
        enriched["brief_path"] = brief_rel
        enriched["status"] = "planned"
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
            "status: planned",
            "",
            "## Reason",
            "",
            str(task.get("reason", "Research plan category had no accepted evidence.")),
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

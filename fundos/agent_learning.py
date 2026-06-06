from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fundos.io import DISCLAIMER, REPO_ROOT, read_yaml, write_yaml
from fundos.research_cache import stable_hash

AGENT_LEARNING_VERSION = "0.1.0"
SPEC_REL = "specs/learning/agent-learning-candidates.yaml"
SAFE_TYPES = {"workflow_update", "principle_update", "checklist_update", "reflection_update", "skill_update"}
SAFE_SCOPES = {"agent_memory", "workflow", "checklist", "principle", "skill"}
FORBIDDEN_TYPES = {"profile_update", "tool_permission_update", "risk_limit_update", "broker_update", "order_execution_update"}
FORBIDDEN_SCOPES = {"core_profile", "tool_permission", "risk_limit", "broker_integration", "real_capital_authority"}
CONTROLS = [
    "no_direct_profile_mutation",
    "no_real_trade_action",
    "requires_evolution_gate",
    "quarantine_before_memory_write",
    "tool_permission_changes_forbidden",
    "risk_limit_changes_forbidden",
    "broker_integration_disabled",
    "paper_portfolio_only",
]
REQUIRED_TESTS = [
    "agent_tool_use_reconciliation",
    "role_drift_check",
    "evidence_quality_check",
    "historical_case_replay",
]


def load_agent_learning_spec() -> dict[str, Any]:
    spec = read_yaml(REPO_ROOT / SPEC_REL)
    spec["source_path"] = SPEC_REL
    return spec


def default_agent_learning_report() -> dict[str, Any]:
    return {
        "version": AGENT_LEARNING_VERSION,
        "artifact_type": "agent_learning_candidate_report",
        "candidate_count": 0,
        "merged_to_evolution": 0,
        "candidates_by_agent": {},
        "route_counts": {},
        "blocking_issues": ["missing_agent_learning_report"],
        "controls": CONTROLS,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def load_agent_learning_report(run_path: Path | None) -> dict[str, Any]:
    if not run_path:
        return default_agent_learning_report()
    path = run_path / "learning" / "agent-learning-report.yaml"
    if not path.exists():
        return default_agent_learning_report()
    report = default_agent_learning_report()
    report.update(read_yaml(path) or {})
    return report


def generate_agent_learning_candidates(run_path: Path) -> dict[str, Any]:
    spec = load_agent_learning_spec()
    run_id = infer_run_id(run_path)
    agent_tool_use = read_optional_yaml(run_path / "harness" / "agent-tool-use.yaml", {})
    failure_report = read_optional_yaml(run_path / "learning" / "failure-patterns.yaml", {})
    agent_harness = read_optional_yaml(run_path / "harness" / "agent-harness.yaml", {})
    skill_benchmark = read_optional_yaml(run_path / "harness" / "skill-benchmark.yaml", {})
    thread_manifest = read_optional_yaml(run_path / "memory" / "agent-thread-manifest.yaml", {})

    candidates: list[dict[str, Any]] = []
    candidates.extend(candidates_from_tool_use(run_id, agent_tool_use))
    candidates.extend(candidates_from_failure_patterns(run_id, failure_report))
    candidates.extend(candidates_from_quality_reports(run_id, agent_harness, skill_benchmark))
    candidates.extend(candidates_from_thread_events(run_path, run_id, thread_manifest))
    candidates = dedupe_candidates([sanitize_candidate(c) for c in candidates])

    learning_path = run_path / "learning" / "agent-learning-candidates.jsonl"
    existing_learning = read_jsonl(learning_path)
    merged_learning = dedupe_candidates(existing_learning + candidates)
    write_jsonl(learning_path, merged_learning)

    evolution_path = run_path / "evolution" / "candidates.jsonl"
    existing_evolution = read_jsonl(evolution_path)
    before = len({row.get("candidate_id") for row in existing_evolution if row.get("candidate_id")})
    merged_evolution = dedupe_candidates(existing_evolution + candidates)
    after = len({row.get("candidate_id") for row in merged_evolution if row.get("candidate_id")})
    write_jsonl(evolution_path, merged_evolution)

    report = {
        "version": AGENT_LEARNING_VERSION,
        "artifact_type": "agent_learning_candidate_report",
        "spec_id": spec.get("spec_id"),
        "source_path": spec.get("source_path"),
        "run_id": run_id,
        "candidate_count": len(merged_learning),
        "new_candidates": len(candidates),
        "merged_to_evolution": after - before,
        "candidates_by_agent": count_by(merged_learning, "target_agent"),
        "candidate_type_counts": count_by(merged_learning, "candidate_type"),
        "target_scope_counts": count_by(merged_learning, "target_scope"),
        "route_counts": count_by(merged_learning, "adoption_route"),
        "candidates": merged_learning,
        "inputs": {
            "agent_tool_use": "harness/agent-tool-use.yaml",
            "failure_patterns": "learning/failure-patterns.yaml",
            "agent_harness": "harness/agent-harness.yaml",
            "skill_benchmark": "harness/skill-benchmark.yaml",
            "agent_thread_manifest": "memory/agent-thread-manifest.yaml",
        },
        "blocking_issues": blocking_issues(merged_learning),
        "controls": spec.get("controls", CONTROLS),
        "disclaimer": DISCLAIMER,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    write_yaml(run_path / "learning" / "agent-learning-report.yaml", report)
    return report


def candidates_from_tool_use(run_id: str, report: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in report.get("agent_results", []) or []:
        agent_id = str(row.get("agent_id") or "unknown_agent")
        missing = [str(tool) for tool in row.get("missing_required_tools", []) if str(tool).strip()]
        forbidden = [str(tool) for tool in row.get("forbidden_called_tools", []) if str(tool).strip()]
        score = int(row.get("score", 100) or 0)
        if missing:
            tools = ", ".join(missing)
            candidates.append(make_candidate(
                run_id=run_id,
                target_agent=agent_id,
                reason_key="missing_required_tools",
                candidate_type="workflow_update",
                target_scope="agent_memory",
                proposal=(
                    f"When required tools are missing ({tools}), {agent_id} must cap confidence, "
                    "record the missing tool chain, and create a follow-up evidence retrieval task before forming a role view. "
                    "This is a checklist/workflow lesson, not a tool-permission change."
                ),
                source_basis=[{
                    "source_id": "agent_tool_use_reconciliation",
                    "evidence_id": "harness/agent-tool-use.yaml",
                    "source_tier": "tier_2_canonical_framework",
                    "rationale": f"Runtime reconciliation found missing required tools: {tools}.",
                }],
                metadata={
                    "missing_required_tools": missing,
                    "called_tools": row.get("called_tools", []),
                    "agent_tool_use_score": score,
                    "confidence_cap_required": bool(row.get("confidence_cap_required")),
                },
            ))
        if forbidden:
            tools = ", ".join(forbidden)
            candidates.append(make_candidate(
                run_id=run_id,
                target_agent=agent_id,
                reason_key="forbidden_tool_calls",
                candidate_type="principle_update",
                target_scope="agent_memory",
                proposal=(
                    f"If forbidden tools are attempted ({tools}), {agent_id} must stop the run segment, downgrade confidence, "
                    "and hand off to EvaluationHarness for boundary review. This cannot grant new permissions."
                ),
                source_basis=[{
                    "source_id": "agent_tool_use_reconciliation",
                    "evidence_id": "harness/agent-tool-use.yaml",
                    "source_tier": "tier_2_canonical_framework",
                    "rationale": f"Runtime reconciliation found forbidden called tools: {tools}.",
                }],
                metadata={"forbidden_called_tools": forbidden, "agent_tool_use_score": score},
            ))
        if score < 60 and not missing and not forbidden:
            candidates.append(make_candidate(
                run_id=run_id,
                target_agent=agent_id,
                reason_key="low_tool_use_score",
                candidate_type="reflection_update",
                target_scope="agent_memory",
                proposal=(
                    f"{agent_id} should add a post-run reflection checklist for low tool-use quality before raising confidence. "
                    "The lesson must preserve evidence IDs, missing context, and confidence caps."
                ),
                source_basis=[{
                    "source_id": "agent_tool_use_reconciliation",
                    "evidence_id": "harness/agent-tool-use.yaml",
                    "source_tier": "tier_2_canonical_framework",
                    "rationale": f"Runtime reconciliation score was low: {score}.",
                }],
                metadata={"agent_tool_use_score": score},
            ))
    return candidates


def candidates_from_thread_events(run_path: Path, run_id: str, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if not manifest or manifest.get("status") == "missing":
        return candidates
    root = infer_runtime_root(run_path)
    for thread in manifest.get("threads", []) or []:
        agent_id = str(thread.get("agent_id") or "")
        event_log_rel = thread.get("event_log_path")
        if not agent_id or not event_log_rel:
            continue
        events = read_jsonl(root / str(event_log_rel))
        for event in events:
            if event.get("run_id") != run_id:
                continue
            if event.get("event_type") == "research_gap_followup_closed":
                payload = event.get("payload", {}) or {}
                task_id = str(payload.get("task_id") or "")
                category = str(payload.get("category") or "unknown_category")
                accepted_evidence_ids = [str(item) for item in payload.get("accepted_evidence_ids", []) or []]
                source = str(payload.get("source") or "")
                source_agent_id = str(payload.get("source_agent_id") or "")
                source_evidence_id = str(payload.get("source_evidence_id") or "")
                source_claim_id = str(payload.get("source_claim_id") or "")
                hypothesis = str(payload.get("hypothesis") or "")
                validation_required = str(payload.get("validation_required") or "")
                if not task_id:
                    continue
                origin_note = ""
                if source == "agent_reasoning_layer":
                    origin_note = (
                        f" The closed gap originated from Agent reasoning hypothesis"
                        f" source_agent={source_agent_id or 'unknown'}"
                        f" evidence_id={source_evidence_id or 'none'}"
                        f" claim_id={source_claim_id or 'none'}"
                        f" validation_required={validation_required or 'unspecified'}"
                        f" hypothesis={hypothesis or 'not recorded'}."
                    )
                candidates.append(make_candidate(
                    run_id=run_id,
                    target_agent=agent_id,
                    reason_key=f"thread_followup_closed_{task_id}_{category}_{source_claim_id}_{','.join(accepted_evidence_ids)}",
                    candidate_type="reflection_update",
                    target_scope="agent_memory",
                    proposal=(
                        f"Record a post-research reflection for closed research gap {category}: the agent first marked "
                        f"task {task_id} as needing evidence and it was later closed with accepted evidence "
                        f"{', '.join(accepted_evidence_ids) or 'none'}.{origin_note} In future similar work, preserve the original evidence gap, "
                        "cite the accepted evidence IDs, and keep confidence capped until the gap is closed."
                    ),
                    source_basis=[{
                        "source_id": "agent_thread_event_log",
                        "evidence_id": str(Path("memory") / "agents" / agent_id / "thread-events.jsonl"),
                        "source_tier": "tier_2_canonical_framework",
                        "rationale": f"Persistent Agent Thread recorded a closed follow-up lifecycle for {category}.",
                    }],
                    metadata={
                        "source_event_type": "research_gap_followup_closed",
                        "task_id": task_id,
                        "category": category,
                        "accepted_evidence_ids": accepted_evidence_ids,
                        "source": source or None,
                        "source_agent_id": source_agent_id or None,
                        "source_evidence_id": source_evidence_id or None,
                        "source_claim_id": source_claim_id or None,
                        "hypothesis": hypothesis or None,
                        "validation_required": validation_required or None,
                        "thread_event_log_path": str(event_log_rel),
                    },
                ))
    return candidates


def candidates_from_failure_patterns(run_id: str, report: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for pattern in report.get("patterns", []) or []:
        agent_id = str(pattern.get("agent_id") or "unknown_agent")
        category = str(pattern.get("category") or "failure_pattern")
        severity = str(pattern.get("severity") or "medium")
        pattern_metadata = pattern.get("metadata", {}) or {}
        if not pattern.get("pattern_id"):
            continue
        candidates.append(make_candidate(
            run_id=run_id,
            target_agent=agent_id,
            reason_key=f"failure_pattern_{category}_{pattern.get('pattern_id')}",
            candidate_type="checklist_update" if severity in {"high", "critical"} else "reflection_update",
            target_scope="agent_memory",
            proposal=(
                f"Add a small review checklist for recurring failure pattern {category}: {pattern.get('description')}. "
                f"Prevention check: {pattern.get('prevention_check')}."
            ),
            source_basis=[{
                "source_id": "failure_pattern_library",
                "evidence_id": "learning/failure-patterns.yaml",
                "source_tier": "tier_2_canonical_framework",
                "rationale": f"Failure pattern {pattern.get('pattern_id')} was extracted from run reflections, evaluation, or harness reports.",
            }],
            metadata={
                "pattern_id": pattern.get("pattern_id"),
                "category": category,
                "severity": severity,
                **pattern_metadata,
            },
        ))
    return candidates


def candidates_from_quality_reports(run_id: str, agent_harness: dict[str, Any], skill_benchmark: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in agent_harness.get("agent_results", []) or []:
        agent_id = str(row.get("agent_id") or "unknown_agent")
        context_quality = row.get("context_management_quality", {}) or {}
        score = int(context_quality.get("score", context_quality.get("overall", 100)) or 100)
        if score < 70:
            candidates.append(make_candidate(
                run_id=run_id,
                target_agent=agent_id,
                reason_key="low_context_management_quality",
                candidate_type="workflow_update",
                target_scope="agent_memory",
                proposal=(
                    f"{agent_id} should tighten vertical context compression: preserve contradictions, source tiers, "
                    "excluded-context reasons, and missing-evidence rows before producing a role view."
                ),
                source_basis=[{
                    "source_id": "agent_harness_context_management",
                    "evidence_id": "harness/agent-harness.yaml",
                    "source_tier": "tier_2_canonical_framework",
                    "rationale": f"Context management score was below threshold: {score}.",
                }],
                metadata={"context_management_score": score},
            ))
    for row in skill_benchmark.get("agent_results", []) or skill_benchmark.get("skill_results", []) or []:
        agent_id = str(row.get("agent_id") or "unknown_agent")
        score = int(row.get("score", row.get("overall_score", 100)) or 100)
        if score < 70:
            candidates.append(make_candidate(
                run_id=run_id,
                target_agent=agent_id,
                reason_key="low_skill_benchmark_score",
                candidate_type="checklist_update",
                target_scope="agent_memory",
                proposal=(
                    f"{agent_id} should add a skill invocation checklist for low benchmark score, including role boundary, "
                    "evidence citations, missing-tool disclosure, and forbidden-output scan."
                ),
                source_basis=[{
                    "source_id": "skill_benchmark",
                    "evidence_id": "harness/skill-benchmark.yaml",
                    "source_tier": "tier_2_canonical_framework",
                    "rationale": f"Skill benchmark score was below threshold: {score}.",
                }],
                metadata={"skill_benchmark_score": score},
            ))
    return candidates


def make_candidate(
    *,
    run_id: str,
    target_agent: str,
    reason_key: str,
    candidate_type: str,
    target_scope: str,
    proposal: str,
    source_basis: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    digest = stable_hash(json.dumps({"run_id": run_id, "target_agent": target_agent, "reason_key": reason_key}, ensure_ascii=False, sort_keys=True))
    return {
        "candidate_id": f"agent_learning_{digest}",
        "run_id": run_id,
        "source_agent": "evaluation_harness",
        "target_agent": target_agent,
        "candidate_type": candidate_type,
        "target_scope": target_scope,
        "proposal": proposal,
        "source_basis": source_basis,
        "required_tests": REQUIRED_TESTS,
        "status": "proposed",
        "origin": "agent_learning_generator_v1",
        "controls": CONTROLS,
        "metadata": metadata,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def sanitize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    candidate_type = candidate.get("candidate_type")
    target_scope = candidate.get("target_scope")
    if candidate_type in FORBIDDEN_TYPES or candidate_type not in SAFE_TYPES:
        candidate["candidate_type"] = "workflow_update"
    if target_scope in FORBIDDEN_SCOPES or target_scope not in SAFE_SCOPES:
        candidate["target_scope"] = "agent_memory"
    candidate["real_trade_allowed"] = False
    candidate["broker_integration"] = "disabled"
    candidate["status"] = "proposed"
    candidate["origin"] = "agent_learning_generator_v1"
    candidate["controls"] = sorted(set(candidate.get("controls", []) + CONTROLS), key=(candidate.get("controls", []) + CONTROLS).index)
    candidate["required_tests"] = sorted(set(candidate.get("required_tests", []) + REQUIRED_TESTS), key=(candidate.get("required_tests", []) + REQUIRED_TESTS).index)
    candidate.update(route_agent_learning_candidate(candidate))
    return candidate


def route_agent_learning_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Classify how a learning candidate may be adopted after EvolutionGate.

    The route is intentionally explicit because different artifacts have
    different safety boundaries: reflections can write controlled memory after
    an accepted EvolutionGate result, workflow/checklist/principle changes are
    managed capability candidates requiring human apply, skill changes patch only
    managed SKILL.md sections after human approval, and protected profile/tool/
    risk mutations are blocked.
    """
    candidate_type = candidate.get("candidate_type")
    target_scope = candidate.get("target_scope", "agent_memory")
    protected = candidate_type in FORBIDDEN_TYPES or target_scope in FORBIDDEN_SCOPES
    if protected:
        return {
            "adoption_route": "forbidden_protected_mutation",
            "memory_write_policy": "blocked",
            "capability_kind": None,
            "human_approval_required": True,
            "protected_mutation_allowed": False,
            "auto_apply_allowed": False,
        }
    if candidate_type == "skill_update" or target_scope == "skill":
        return {
            "adoption_route": "skill_patch_pending_human_apply",
            "memory_write_policy": "no_direct_memory_write",
            "capability_kind": "skill",
            "human_approval_required": True,
            "protected_mutation_allowed": False,
            "auto_apply_allowed": False,
        }
    if target_scope in {"workflow", "checklist", "principle"} or candidate_type in {"workflow_update", "checklist_update", "principle_update"}:
        capability_kind = target_scope if target_scope in {"workflow", "checklist", "principle"} else str(candidate_type).replace("_update", "")
        return {
            "adoption_route": "managed_capability_pending_human_apply",
            "memory_write_policy": "no_direct_memory_write",
            "capability_kind": capability_kind,
            "human_approval_required": True,
            "protected_mutation_allowed": False,
            "auto_apply_allowed": False,
        }
    return {
        "adoption_route": "memory_writeback_after_evolution",
        "memory_write_policy": "auto_after_evolution_accept",
        "capability_kind": None,
        "human_approval_required": False,
        "protected_mutation_allowed": False,
        "auto_apply_allowed": False,
    }


def blocking_issues(candidates: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    for candidate in candidates:
        cid = candidate.get("candidate_id", "unknown")
        if candidate.get("candidate_type") in FORBIDDEN_TYPES:
            issues.append(f"forbidden_candidate_type:{cid}:{candidate.get('candidate_type')}")
        if candidate.get("target_scope") in FORBIDDEN_SCOPES:
            issues.append(f"forbidden_target_scope:{cid}:{candidate.get('target_scope')}")
        if candidate.get("real_trade_allowed"):
            issues.append(f"real_trade_allowed:{cid}")
        if candidate.get("broker_integration") != "disabled":
            issues.append(f"broker_integration_enabled:{cid}")
    return issues


def read_optional_yaml(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return read_yaml(path) or default


def infer_run_id(run_path: Path) -> str:
    run_doc = run_path / "run.yaml"
    if run_doc.exists():
        return (read_yaml(run_doc) or {}).get("run_id", run_path.name)
    return run_path.name


def infer_runtime_root(run_path: Path) -> Path:
    resolved = run_path.resolve()
    if resolved.parent.name == "runs":
        return resolved.parent.parent
    return resolved.parent


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = candidate.get("candidate_id")
        if candidate_id and candidate_id in seen:
            continue
        if candidate_id:
            seen.add(candidate_id)
        unique.append(candidate)
    return unique


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts

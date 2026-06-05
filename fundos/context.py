from __future__ import annotations

import re
from typing import Any

from fundos.io import REPO_ROOT
from fundos.context_policies import load_context_policy
from fundos.memory_policies import load_memory_policy
from fundos.tool_policies import load_tool_policy


def make_context_pack(run_id: str, agent: dict[str, Any], evidence_pack: dict[str, Any]) -> dict[str, Any]:
    role = agent["role"]
    agent_id = agent["id"]
    policy = load_context_policy(agent)
    memory_policy = load_memory_policy(agent)
    tool_policy = load_tool_policy(agent)
    focus = context_focus(agent_id, role, policy)
    candidates = []
    max_items = int(policy.get("max_context_items", 10))
    include_all_claims = policy.get("evidence_selection", {}).get("include_governance_agents_all_claims", False)
    for item in evidence_pack["evidence_items"]:
        claims = item.get("claims", [])
        matched_tags = sorted({tag for c in claims for tag in c.get("relevant_to", []) if tag in set(focus["tags"])})
        allowed = [c["claim_id"] for c in claims if set(c.get("relevant_to", [])) & set(focus["tags"])]
        if allowed or include_all_claims:
            candidates.append(
                {
                    "evidence_id": item["id"],
                    "source_id": item.get("source_id", ""),
                    "source_tier": item.get("source_tier", ""),
                    "source_type": item.get("source_type", ""),
                    "reason": f"matched context policy {policy.get('context_policy_id')} for {role}",
                    "compressed_summary": item["summary"],
                    "allowed_claims": allowed or [c["claim_id"] for c in claims],
                    "policy_matched_tags": matched_tags or focus["tags"],
                }
            )
    included = sorted(candidates, key=context_candidate_rank)[:max_items]
    return {
        "context_pack_id": f"ctx_{agent_id}",
        "run_id": run_id,
        "agent_id": agent_id,
        "role": role,
        "agent_card": load_agent_card(agent_id),
        "skill_contract": load_skill_contract(agent_id),
        "context_policy": policy,
        "memory_policy": memory_policy,
        "tool_policy": tool_policy,
        "task_stage": "specialist_analysis",
        "context_budget_tokens": policy.get("token_budget", 8000),
        "included_evidence": included,
        "contradiction_table": [
            {
                "issue": "方法论来源不能替代一手事实",
                "supporting_claims": ["C004"],
                "opposing_claims": ["C001", "C002"],
            }
        ],
        "missing_evidence": evidence_pack.get("unresolved_gaps", []),
        "excluded_evidence_summary": [
            {"category": "irrelevant noise", "reason": "V1 context router excludes non-role evidence by relevance tags"}
        ],
        "required_focus": focus["required"],
        "forbidden_focus": policy.get("exclusion_rules", []) + ["不要输出真实交易指令", "不要把低等级来源当作一手事实"],
        "context_quality_controls": policy.get("harness_checks", []),
        "memory_quality_controls": memory_policy.get("harness_checks", []),
        "memory_retrieval_contract": memory_policy.get("retrieval_contract", {}),
        "tool_quality_controls": tool_policy.get("harness_checks", []),
        "output_schema": f"{role}Output",
    }


def context_candidate_rank(item: dict[str, Any]) -> tuple[int, int, str]:
    tier_rank = {
        "tier_1_primary_fact": 0,
        "tier_2_canonical_framework": 1,
        "tier_3_verified_public_practitioner": 2,
        "tier_4_expert_opinion": 3,
        "tier_5_social_signal": 4,
        "tier_6_unverified": 5,
    }.get(item.get("source_tier", ""), 6)
    # Run-specific public retrieval should not be starved by static seed patterns;
    # social public results are still low confidence, but must be visible so the
    # agent can label them as sentiment rather than silently dropping them.
    source_rank = 0 if item.get("source_id") == "public_research" else 1
    return (source_rank, tier_rank, item.get("evidence_id", ""))


def load_agent_card(agent_id: str) -> dict[str, Any]:
    rel = f"specs/agents/agent-cards/{agent_id}/agent.md"
    path = REPO_ROOT / rel
    if not path.exists():
        return {"source_path": rel, "available": False, "title": "", "profile_summary": "", "learning_patterns": []}
    text = path.read_text(encoding="utf-8")
    return {
        "source_path": rel,
        "available": True,
        "title": first_heading(text),
        "profile_summary": compact_section(text, "Profile", max_lines=10),
        "decision_principles": bullet_lines(section_body(text, "Decision Principles")),
        "declared_skills": code_or_bullet_values(section_body(text, "Skills")),
        "declared_tools": code_or_bullet_values(section_body(text, "Tools")),
        "learning_patterns": code_or_bullet_values(section_body(text, "Learning Patterns")),
        "capability_boundaries": bullet_lines(section_body(text, "Capability Boundaries")),
        "harness_and_evaluation": bullet_lines(section_body(text, "Harness and Evaluation")),
        "context_management_policy": bullet_lines(section_body(text, "Context Management Policy")),
        "evolution_path": bullet_lines(section_body(text, "Evolution Path")),
        "output_contract": compact_section(text, "Output Contract", max_lines=10),
    }


def load_skill_contract(agent_id: str) -> dict[str, Any]:
    rel = f"specs/skills/{agent_id}/SKILL.md"
    path = REPO_ROOT / rel
    if not path.exists():
        return {"source_path": rel, "available": False, "name": "", "sections": [], "role_checklist": []}
    text = path.read_text(encoding="utf-8")
    frontmatter = parse_frontmatter(text)
    sections = re.findall(r"^##\s+(.+)$", text, flags=re.MULTILINE)
    return {
        "source_path": rel,
        "available": True,
        "name": frontmatter.get("name", ""),
        "description": frontmatter.get("description", ""),
        "sections": sections,
        "when_to_use": compact_section(text, "When to Use This Skill", max_lines=6),
        "inputs": bullet_lines(section_body(text, "Inputs")),
        "operating_workflow": bullet_lines(section_body(text, "Operating Workflow")),
        "evidence_rules": bullet_lines(section_body(text, "Evidence Rules")),
        "context_management": bullet_lines(section_body(text, "Context Management")),
        "output_schema": bullet_lines(section_body(text, "Output Schema")),
        "failure_modes": bullet_lines(section_body(text, "Failure Modes")),
        "learning_patterns": code_or_bullet_values(section_body(text, "Learning Patterns")),
        "role_checklist": bullet_lines(section_body(text, "Role-Specific Checklist")),
        "harness_hooks": bullet_lines(section_body(text, "Harness Hooks")),
        "forbidden_outputs": bullet_lines(section_body(text, "Forbidden Outputs")),
        "boundaries": bullet_lines(section_body(text, "Boundaries")),
        "required_closing": compact_section(text, "Required Closing", max_lines=4),
    }


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    values: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    return values


def first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def section_body(text: str, heading: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"^##\s+", text[start:], flags=re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end].strip()


def bullet_lines(body: str) -> list[str]:
    values = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            values.append(stripped[2:].strip())
    return values


def code_or_bullet_values(body: str) -> list[str]:
    values = []
    for line in bullet_lines(body):
        values.append(line.replace("`", ""))
    return values


def compact_section(text: str, heading: str, max_lines: int) -> str:
    body = section_body(text, heading)
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    return "\n".join(lines[:max_lines])


def context_focus(agent_id: str, role: str, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    if policy:
        return {"tags": policy.get("preferred_context_tags", []), "required": policy.get("required_focus", [])}
    if "Trader" in role:
        return {"tags": ["trading", "risk"], "required": ["量价结构", "买卖触发条件", "仓位纪律"]}
    if "Risk" in role:
        return {"tags": ["risk", "company", "trading"], "required": ["下行风险", "证据等级", "仓位上限"]}
    if "Bear" in role:
        return {"tags": ["bear_case", "risk", "company"], "required": ["攻击核心假设", "替代解释", "证据缺口"]}
    if "Company" in role or "Governance" in role:
        return {"tags": ["company", "risk"], "required": ["财报公告", "产品和订单", "治理风险"]}
    if "Analyst" in role:
        return {"tags": ["industry", "company"], "required": ["产业链", "chokepoint", "需求验证"]}
    return {"tags": ["industry", "company", "trading", "risk", "bear_case"], "required": ["综合判断", "证据追溯", "流程完整性"]}

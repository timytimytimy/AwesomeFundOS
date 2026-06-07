# AwesomeFundOS V1 Implementation & Verification Plan

This file is the current Codex implementation handoff plan for V1. It replaces the earlier scaffold-only plan: the repository now contains a local-first runtime, schemas, tests, audit gates, PRDs, agent cards, skills, memory/evolution flows, and harness artifacts.

## 1. Non-negotiable invariants

- `real_trade_allowed=false` everywhere.
- `broker_integration=disabled` everywhere.
- Outputs are research, watchlist, and Paper Portfolio only.
- No personalized investment advice.
- No automatic order placement.
- KOLs, famous traders, books, courses, Serenity, 里海, and historical cases are methodology or hypothesis sources only, never direct buy/sell evidence.
- Durable learning must pass quarantine, Evaluation, EvolutionGate, regression, and approval controls before capability application.

## 2. Current V1 runtime surface

The local CLI is implemented under `fundos/` and supports these workflows:

Install the editable local console command first when desired:

```bash
python3 -m pip install -e .
fundos --help
```

```bash
python3 -m fundos.cli init
python3 -m fundos.cli run --topic "机器人产业链投资机会"
python3 -m fundos.cli run --topic "机器人产业链投资机会" --research-fixture examples/fixtures/robotics-public-research.json
python3 -m fundos.cli eval --run runs/<run_id>
python3 -m fundos.cli evolve --run runs/<run_id>
python3 -m fundos.cli inspect --run runs/<run_id>
python3 -m fundos.cli report --run runs/<run_id>
python3 -m fundos.cli roster list
python3 -m fundos.cli memory show --agent fund_manager
python3 -m fundos.cli capabilities list
python3 -m fundos.cli capabilities apply <candidate_id> --approver <human>
python3 -m fundos.cli performance show --agent tech_growth_analyst
python3 -m fundos.cli failures summary
python3 -m fundos.cli skills export --out ./skills
python3 -m fundos.cli sources ingest --run runs/<run_id> --fixture <source-candidates.yaml>
python3 -m fundos.cli cases list
python3 -m fundos.cli followups list --run runs/<run_id>
python3 -m fundos.cli threads show --agent fund_manager
python3 -m fundos.cli governance summary --run runs/<run_id>
python3 -m fundos.cli system audit --strict
```

## 3. Implemented module checklist

### 3.1 Repo scaffold and runtime directories

Evidence:

- `fundos/cli.py`
- `specs/agents/default-roster.yaml`
- `tests/test_cli_unittest.py`

Implemented behavior:

- `init` is idempotent.
- Runtime directories are created without overwriting user files.
- Default roster is readable and exposes 19 source-controlled agents.

### 3.2 Core run workspace

Evidence:

- `fundos/cli.py`
- `fundos/os_manifest.py`
- `specs/schemas/run.schema.yaml`
- `tests/test_cli_unittest.py`
- `tests/test_system_audit.py`

Implemented behavior:

- `run` accepts topic, stock, and question inputs.
- Each run writes `run.yaml`, task brief, selected agents, EvidencePack, ContextPacks, agent outputs, committee artifacts, portfolio artifacts, harness reports, memory/thread artifacts, evolution artifacts, and operating-system manifest.
- `run.yaml` writes concrete model records using local file protocol governance records, not placeholder model or tool versions.

### 3.3 Evidence and public research

Evidence:

- `fundos/evidence.py`
- `fundos/public_research.py`
- `fundos/research_cache.py`
- `fundos/tool_runtime.py`
- `specs/schemas/evidence-pack.schema.yaml`
- `specs/schemas/public-research-manifest.schema.yaml`
- `tests/test_public_research.py`
- `tests/test_research_cache.py`
- `tests/test_tool_runtime.py`

Implemented behavior:

- Tool/public-research results become source-tiered EvidenceItems with Claim IDs.
- Runs write `evidence/evidence-pack.yaml` and `evidence/public-research-manifest.yaml`.
- Strict audit checks manifest result counts, source hashes, and research plan coverage.
- If no public result is supplied or retrieved, the system records explicit evidence gaps instead of inventing primary facts.

### 3.4 Context manager

Evidence:

- `fundos/context.py`
- `specs/agents/context-policies/*.yaml`
- `specs/schemas/context-pack.schema.yaml`
- `tests/test_context_policies.py`
- `tests/test_context_management_harness.py`

Implemented behavior:

- Every selected agent receives a role-specific ContextPack.
- ContextPack now exposes `included_evidence`, first-class `included_claims`, first-class `compressed_summaries`, contradiction table, missing evidence, excluded evidence summary, Thread summary, output schema, budget manifest, role context contract, and loss accounting.
- Context compression preserves Evidence IDs, Claim IDs, source tiers, required vertical context dimensions, thread summary boundaries, and no-real-trade safety fields.

### 3.5 Agent cards, skills, and structured outputs

Evidence:

- `specs/agents/agent-cards/*/agent.md`
- `specs/skills/*/SKILL.md`
- `fundos/agent_outputs.py`
- `fundos/agent_harness.py`
- `tests/test_agent_assets.py`
- `tests/test_agent_runtime_integration.py`
- `tests/test_agent_harness.py`

Implemented behavior:

- V1 contains 19 source-controlled independent Agent Cards and 19 matching Skills.
- Each agent has Profile, ContextPolicy, ToolPolicy, MemoryPolicy, ModelPolicy, Thread namespace, Harness hooks, and Evolution path.
- Agent output binds context pack, Skill contract, ToolPolicy, MemoryPolicy, model policy, Evidence IDs, Claim IDs, role checklist, guardrails, reasoning layers, and thread-memory influence.

### 3.6 Debate, risk review, committee memo

Evidence:

- `fundos/committee.py`
- `fundos/decision.py`
- `specs/protocols/debate-protocol.yaml`
- `specs/protocols/investment-committee-protocol.yaml`
- `specs/schemas/decision-memo.schema.yaml`
- `tests/test_committee_protocol.py`

Implemented behavior:

- Bear case, risk review, disagreement tables, and final decision memo are generated.
- Decisions remain watchlist / Paper Portfolio oriented and include risk, trigger, invalidation, evidence, and disclaimer fields.

### 3.7 Harness and evaluation

Evidence:

- `fundos/harness.py`
- `fundos/agent_harness.py`
- `fundos/tool_harness.py`
- `fundos/claim_graph.py`
- `fundos/task_dag.py`
- `specs/schemas/evaluation-report.schema.yaml`
- `tests/test_agent_harness.py`
- `tests/test_tool_harness.py`
- `tests/test_claim_graph.py`
- `tests/test_task_dag.py`

Implemented behavior:

- Runtime evaluation scores evidence, role, context, skill, tool/source boundary, portfolio, outcome, claim graph, task DAG, case replay, performance, and governance signals when relevant artifacts exist.
- Blocking issues cover missing evidence, missing risk review, missing bear case, role drift, unsafe broker leakage, real trade language, unclosed evidence gaps, and low-quality upgrades.
- Agent Harness scores context compression, role-specific context management, thread summary quality, memory lesson traceability, reasoning layer separation, policy contracts, skill invocation, tool policy, memory policy, and role consistency.

### 3.8 Learning, source ingestion, and EvolutionGate

Evidence:

- `fundos/source_ingestion.py`
- `fundos/learning.py`
- `fundos/evolution.py`
- `fundos/memory.py`
- `specs/learning/*`
- `specs/schemas/source-candidate.schema.yaml`
- `specs/schemas/pattern-candidate.schema.yaml`
- `tests/test_source_ingestion.py`
- `tests/test_evolution_gate.py`
- `tests/test_memory_writeback.py`

Implemented behavior:

- Famous investors, KOLs, Serenity/里海, books, courses, and historical cases enter through controlled source candidates and quarantine artifacts.
- Source candidates, quarantine rows, and pattern candidates are schema-validated by strict audit.
- EvolutionGate accepts, rejects, or quarantines candidates and prevents unsafe source-tier promotion, direct trading signals, untestable lessons, and protected mutations.
- Accepted memory is written only through controlled ledgers with reversible metadata and safety boundaries.

### 3.9 Capability regression and human apply

Evidence:

- `fundos/capabilities.py`
- `fundos/capability_regression.py`
- `fundos/capability_apply.py`
- `specs/schemas/capability-*.schema.yaml`
- `tests/test_capability_regression.py`
- `tests/test_capability_apply.py`
- `tests/test_capability_versioning.py`

Implemented behavior:

- Accepted principle, skill, checklist, workflow, and tool-policy candidates enter capability registries.
- Capability regression can block unsafe or unverified candidates.
- Human apply requires explicit `--approver` and writes only controlled runtime artifacts or managed blocks.
- Core source-controlled Agent Cards, Profiles, risk limits, and tool permissions are not silently mutated.

### 3.10 Watchlist, Paper Portfolio, and outcomes

Evidence:

- `fundos/portfolio.py`
- `fundos/outcomes.py`
- `specs/schemas/watchlist.schema.yaml`
- `specs/schemas/paper-portfolio.schema.yaml`
- `specs/schemas/outcome-tracking.schema.yaml`
- `tests/test_portfolio.py`
- `tests/test_outcome_tracking.py`

Implemented behavior:

- Decision memos can produce watchlist and Paper Portfolio artifacts.
- Portfolio review and outcome tracking remain offline/replay based and paper-only.
- Harness exposes portfolio and outcome quality without implying real returns, real orders, or personalized advice.

### 3.11 Failure pattern library

Evidence:

- `fundos/failure_patterns.py`
- `specs/schemas/failure-pattern-report.schema.yaml`
- `tests/test_failure_patterns.py`

Implemented behavior:

- Reflections, Harness blocking issues, Agent Harness findings, and outcome tracking can generate run-level and organization-level failure patterns.
- Failure patterns feed learning candidates as negative examples while preserving paper-only and broker-disabled boundaries.

### 3.12 System governance and audit

Evidence:

- `fundos/system_audit.py`
- `docs/prd/overall-prd.md`
- `docs/prd/modules/*.md`
- `specs/audits/prd-requirement-matrix.yaml`
- `specs/schemas/prd-requirement-matrix.schema.yaml`
- `tests/test_system_audit.py`

Implemented behavior:

- `system audit --strict` validates PRD/module coverage, runtime artifacts, schemas, source ingestion quarantine artifacts, public research manifest integrity, OS manifest, safety invariants, learning/evolution/capability artifacts, and no-placeholder runtime records.
- The PRD acceptance matrix maps all 104 acceptance criteria across 10 module PRDs to concrete evidence paths and verification commands.
- `.github/workflows/ci.yml` runs the same V1 verification gate on push, pull request, and manual dispatch.

## 4. Required verification before claiming V1 readiness

Run these commands from the implementation worktree:

```bash
scripts/verify_v1.sh
```

The script runs:

```bash
python3 -m unittest discover -s tests -q
python3 -m fundos.cli system audit --strict
git diff --check
```

Expected safety fields in audit output:

```text
overall_coverage_score=100.0
failed_requirements=0
real_trade_allowed=False
broker_integration=disabled
```

## 5. Known V1 limits

- V1 is local-first and file-protocol based.
- Public retrieval is fixture/cache/tool-adapter oriented; stable production-grade live data providers remain a V2 integration task.
- Outputs are not financial advice and cannot be used for real trading automation.
- App Server dashboard, full web UI, and multi-market production adapters are outside V1.

## 6. Suggested next hardening tasks

1. Add more fixture-backed public research examples across industries and market regimes.
2. Expand historical case replay coverage for fraud, policy cycles, failed breakouts, and KOL thesis failures.
3. Add benchmark fixtures that compare capability versions before/after human apply.
4. Add richer context stress tests for very dense EvidencePacks and cross-agent handoffs.
5. Keep `.github/workflows/ci.yml` aligned with `scripts/verify_v1.sh` whenever quality gates change.

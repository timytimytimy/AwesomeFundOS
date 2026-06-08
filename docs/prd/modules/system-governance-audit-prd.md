# System Governance Audit PRD

## 1. Module Goal

System Governance Audit proves that a run loaded a coherent Agent Operating System: Profile, Skills, Tools, Memory, Thread, Harness, Evolution, source provenance, context management and safety boundaries. It turns the system from a collection of files into an auditable organization runtime.

## 2. Operating System Manifest

Each run writes:

```text
system/operating-system-manifest.yaml
system/operating-system-manifest.md
```

The manifest links selected agents to source-controlled Agent Cards, SKILL files, ContextPolicy, ToolPolicy, MemoryPolicy, runtime model records, thread manifests, harness artifacts, evolution artifacts, performance / governance summaries, source provenance summaries and context management summaries.

## 3. Strict Audit

`fundos system audit --strict --run <run>` validates:

- required run artifacts exist;
- public research contains primary evidence when high confidence is claimed;
- no unresolved stub blocker remains in fixture-backed valid runs;
- selected agents have ContextPack and outputs;
- model_records contain concrete model / skill / tool policy fields;
- operating-system-manifest matches schema;
- evaluation-report matches schema;
- manifest summaries match source harness artifacts;
- source provenance and context management summaries are not stale;
- safety invariants remain disabled for real trade and broker integration.

## 4. Requirement Coverage Audit

Repository-level audit checks overall PRD, module PRDs, agent assets, policies, harness modules, learning/evolution, case library, tools, governance protocols, safety boundaries and CLI operability.

## 5. System Doctor

`fundos system doctor` is the fast readiness check before handing the repository to Codex for implementation or operation. It verifies console-script packaging, default roster loadability, the 19 source-controlled Agent Cards, the 19 source-controlled Skills, Codex Skill export dry-run, repository strict audit, and the no-real-trade / no-broker safety invariants. It returns non-zero on any failed check and never grants runtime permissions.

## Acceptance Criteria

- Repository audit reports required PRD modules and fails if any module is missing or too weak for implementation.
- Runtime strict audit fails stale OS manifest summaries, schema violations, missing artifacts, unsafe model records or broker / real-trade leakage.
- Audit output includes YAML and Markdown reports with requirement IDs, evidence paths, details and blocking issues.
- Audit itself is evidence-based: each pass must point to concrete files or runtime artifacts.
- `fundos system doctor` returns `doctor_status=pass` only when packaging, Agent assets, Skill exportability, strict audit, and safety invariants pass.
- Safety boundary: `real_trade_allowed=false`, `broker_integration=disabled`, audit never grants permissions.

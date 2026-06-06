# Investment Committee PRD

## 1. Module Goal

Investment Committee coordinates the discretionary-fund style decision process. It turns role-specific research into a debate, risk review and final simulated decision memo. The module exists to make the organization behave like a research committee rather than a single stock-picking prompt.

## 2. Core Actors

- ChiefOfStaff: scopes the question, staffs the run and keeps the workflow complete.
- Industry / Company Analysts: produce thesis, evidence gaps and alternative explanations.
- Traders: evaluate timing, liquidity, price-volume structure and simulated position constraints.
- RiskManager: checks concentration, downside, liquidity, evidence quality and kill criteria.
- BearDebater: attacks the thesis, searches for fraud, bubble, policy and execution risks.
- FundManager: integrates evidence, debate, risk and portfolio context into the final memo.
- ReviewArchivist: archives decision, debate transcript, follow-up tasks and review hooks.

## 3. Workflow

```text
Task brief
  -> Staffing
  -> Agent research outputs
  -> Bear debate issue table
  -> Risk review
  -> FundManager synthesis
  -> Decision memo
  -> Watchlist / Paper Portfolio action
  -> Harness and archive
```

## 4. Artifacts

```text
selected-agents.yaml
agent_work/{agent_id}.structured.yaml
debate/bear-case.yaml
risk/risk-review.yaml
decision/final-decision-memo.yaml
archive/review-archive.yaml
```

Decision memo must include question restatement, conclusion, evidence references, bear/risk impact, conviction, simulated position range, trigger conditions, kill criteria, follow-up research tasks, disclaimer and safety fields.

## 5. Governance Rules

- FundManager cannot ignore unresolved high-severity BearDebater or RiskManager issues without explicit rationale.
- Any high-confidence memo must cite tier_1_primary_fact or accepted cross-validated evidence.
- KOL / book / course / historical case inputs can shape checklist and hypothesis only.
- All decisions are research / watchlist / paper portfolio simulations.

## Acceptance Criteria

- Every run produces debate, risk and decision artifacts when selected agents include those roles.
- Final decision memo validates against `decision-memo.schema.yaml` and links to Evidence ID / Claim ID.
- Bear case and risk review materially influence final memo fields or generate explicit unresolved issues.
- Follow-up research gaps are routed to `workflow/research-gap-tasks.yaml` when evidence is insufficient.
- Safety boundary: `real_trade_allowed=false`, `broker_integration=disabled`, no automatic order placement.

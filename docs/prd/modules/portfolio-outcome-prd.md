# Portfolio Outcome PRD

## 1. Module Goal

Portfolio Outcome tracks watchlist and paper-portfolio consequences of simulated committee decisions. It is a process-quality and learning loop, not a real trading or performance-marketing engine.

## 2. Core Objects

- WatchlistItem: research candidate, trigger, kill criteria, review date and evidence references.
- PaperPortfolioAction: simulated action generated from the decision memo.
- PortfolioReview: review of watchlist / paper decisions, process adherence and risk controls.
- OutcomeTracking: optional offline market replay fixture results for return, drawdown, MFE and MAE.
- AttributionItem: links outcome observations back to evidence, agent outputs, risk review and decision memo.

## 3. Workflow

```text
Decision memo
  -> Watchlist / Paper Portfolio action
  -> Portfolio review
  -> Outcome tracking with offline market replay fixture
  -> Attribution
  -> Review learning candidates
  -> Failure pattern extraction
```

## 4. Artifacts

```text
portfolio/watchlist.yaml
portfolio/paper-portfolio.yaml
portfolio/portfolio-actions.jsonl
portfolio/portfolio-review.yaml
portfolio/attribution.jsonl
portfolio/review-candidates.jsonl
portfolio/outcome-tracking.yaml
portfolio/outcome-attribution.jsonl
```

## 5. Evaluation Signals

Harness evaluates action traceability, review completeness, risk compliance, missing market replay, missed opportunity review, risk control review, evidence linkage and learning candidate quality.

## Acceptance Criteria

- Runs produce watchlist and paper portfolio artifacts from the final decision memo.
- Portfolio review records reviewed actions, attribution items, learning candidates and safety controls.
- Outcome tracking uses only offline market replay fixtures or records missing_market_replay; missing data cannot be treated as success.
- Review candidates must pass EvolutionGate before becoming memory or capability updates.
- Safety boundary: `real_trade_allowed=false`, `broker_integration=disabled`, no broker order, no live position instruction.

# Tooling Data Adapters PRD

## 1. Module Goal

Tooling Data Adapters provide read-only public-data retrieval, normalization, provenance and fixture-backed deterministic testing. They convert raw public results into EvidenceItems without granting trading authority.

## 2. Adapter Types

- public web / news search adapter;
- announcement / exchange disclosure adapter;
- financial report parser adapter;
- market data summary adapter;
- historical case library adapter;
- source registry / learning source adapter;
- memory retrieval adapter;
- custom analysis helper adapter.

## 3. Contracts

Each Tool Adapter contract declares:

- adapter_id and version;
- input schema;
- output schema;
- accepted source types and source tiers;
- provenance fields;
- cache key and source hash;
- error / gap contract;
- safety flags.

## 4. Runtime Behavior

V1 can use deterministic fixtures and local cache. Fixture mode must still produce realistic provenance, source tier counts, source type counts and unresolved gap reporting. Runtime adapters are read-only; they cannot place orders, modify broker state or mutate source-controlled Agent assets.

## 5. Harness

Tool Harness checks adapter coverage, primary-source coverage, low-quality source dominance, KOL methodology boundaries, cache status, source hash presence and blocked unsafe outputs.

## Acceptance Criteria

- `tool-adapter-contracts.yaml` defines read-only adapter contracts and required output fields.
- Runtime can convert fixture or public retrieval results into EvidencePack items with source_type, source_tier, claims and provenance.
- Tool Harness flags missing public research, missing primary evidence, source tier misuse and KOL/social-signal boundary violations.
- Adapter outputs can create research gaps instead of fabricating unavailable facts.
- Safety boundary: `real_trade_allowed=false`, `broker_integration=disabled`, adapters cannot access broker or order APIs.

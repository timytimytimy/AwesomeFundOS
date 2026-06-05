# Examples

This directory stores committed sample outputs that prove the V1 file-level pipeline can run end to end.

## robotics-run

Generated with:

```bash
PYTHONPATH=<repo> python3 -m fundos.cli init
PYTHONPATH=<repo> python3 -m fundos.cli run --topic "机器人产业链投资机会"
```

The sample is intentionally a V1 stub result: it demonstrates Agent staffing, EvidencePack, role-specific ContextPacks, agent work artifacts, a simulated decision memo, evaluation report, reflections, and evolution candidates. It is not investment advice and does not use live market data yet.

## robotics-fixture-run

Generated with a deterministic public-research fixture:

```bash
PYTHONPATH=<repo> python3 -m fundos.cli init
PYTHONPATH=<repo> python3 -m fundos.cli run --topic "机器人产业链投资机会" --research-fixture examples/fixtures/robotics-public-research.json
```

This sample demonstrates fixture-backed EvidencePack ingestion, A-share source classification, role-specific ContextPack routing, and the same simulated committee output flow.

# Examples

This directory stores committed sample outputs that prove the V1 file-level pipeline can run end to end.

## robotics-run

Generated with:

```bash
PYTHONPATH=<repo> python3 -m fundos.cli init
PYTHONPATH=<repo> python3 -m fundos.cli run --topic "机器人产业链投资机会"
```

The sample is a legacy V1 demonstration artifact. Current runtime validation should be performed by generating a fresh run with `python3 -m fundos.cli run ...` and then running `python3 -m fundos.cli system audit --strict`. It is not investment advice and does not imply live trading or broker integration.

## robotics-fixture-run

Generated with a deterministic public-research fixture:

```bash
PYTHONPATH=<repo> python3 -m fundos.cli init
PYTHONPATH=<repo> python3 -m fundos.cli run --topic "机器人产业链投资机会" --research-fixture examples/fixtures/robotics-public-research.json
```

This sample demonstrates fixture-backed EvidencePack ingestion, A-share source classification, role-specific ContextPack routing, and the same simulated committee output flow.

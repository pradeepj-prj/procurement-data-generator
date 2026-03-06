# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Procurement data generator for AMR manufacturing — produces realistic, referentially-intact procurement datasets (29 tables, ~10K rows at 1x scale) for a GenAI demo on SAP HANA Cloud.

## Build & Run

```bash
# Install (editable)
pip install -e .

# Run generator (scale: 1, 3, or 10)
python -m procurement_generator --scale 1

# Run with custom paths
python -m procurement_generator --scale 1 --seeds-dir seeds --output-dir output

# Run tests
pytest tests/
```

Output goes to `output/csv/` and `output/sql/`.

## Architecture

- **Pipeline**: 18-stage orchestrator (`pipeline.py`) runs generators in dependency order, validates after each stage, halts on FATAL errors
- **DataStore**: Central mutable state (`data_store.py`) — all generators write, all validators read
- **Models**: ~20 dataclasses in `models.py` matching SAP-style procurement tables
- **Seeds**: YAML files in `seeds/` anchor 12 demo scenarios with exact attribute values
- **Generators**: `generators/` — seed-first, then bulk fill to scale targets
- **Validators**: `validators/` — structural integrity (FK), business rules, seed verification, statistical distribution
- **Exporters**: `exporters/` — CSV (one per table) and SQL (DDL + batch INSERT, HANA-compatible)

Key generation order: org → categories → materials → legal entities → vendors → contracts → source list → confidentiality propagation → PRs → POs → GRs → invoices → payments → reconciliation.

## Key Files

| File | Purpose |
|------|---------|
| `src/procurement_generator/pipeline.py` | Stage orchestrator |
| `src/procurement_generator/models.py` | All entity dataclasses |
| `src/procurement_generator/data_store.py` | Central data store |
| `src/procurement_generator/config.py` | YAML config + ScaleConfig |
| `seeds/*.yaml` | Seed configuration (8 files) |

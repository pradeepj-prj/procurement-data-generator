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

Output goes to `output/csv/`, `output/sql/`, and `output/postgres/`.

## Architecture

- **Pipeline**: 18-stage orchestrator (`pipeline.py`) runs generators in dependency order, validates after each stage, halts on FATAL errors
- **DataStore**: Central mutable state (`data_store.py`) — all generators write, all validators read
- **Models**: ~20 dataclasses in `models.py` matching SAP-style procurement tables
- **Seeds**: YAML files in `seeds/` anchor 12 demo scenarios with exact attribute values
- **Generators**: `generators/` — seed-first, then bulk fill to scale targets
- **Validators**: `validators/` — structural integrity (FK), business rules, seed verification, statistical distribution
- **Exporters**: `exporters/` — CSV (one per table), SQL (DDL + batch INSERT, HANA-compatible), and Postgres (schema-qualified DDL + INSERT with PKs)

Key generation order: org → categories → materials → legal entities → vendors → contracts → source list → confidentiality propagation → PRs → POs → GRs → invoices → payments → reconciliation.

## Key Files

| File | Purpose |
|------|---------|
| `src/procurement_generator/pipeline.py` | Stage orchestrator |
| `src/procurement_generator/models.py` | All entity dataclasses |
| `src/procurement_generator/data_store.py` | Central data store |
| `src/procurement_generator/config.py` | YAML config + ScaleConfig |
| `seeds/*.yaml` | Seed configuration (8 files) |

## ML Use Cases

### Reference

Full documentation: `docs/ML_USE_CASES.md` — 13 use cases across 3 tiers.

| ID | Name | Tier | Primary Table | Label/Target |
|----|------|------|---------------|-------------|
| UC-01 | Maverick PO Detection | 1 | `po_header` | `maverick_flag` |
| UC-02 | Invoice Three-Way Match | 1 | `invoice_header` | `match_status` |
| UC-03 | Vendor Risk Scoring | 1 | `vendor_master` | `risk_score` |
| UC-04 | Price Anomaly Detection | 1 | `po_line_item` | anomaly score |
| UC-05 | Delivery Delay Prediction | 2 | `po_line_item` | `actual > requested` |
| UC-06 | Contract Renewal Prediction | 2 | `contract_header` | renewal likelihood |
| UC-07 | Payment Timing Optimization | 2 | `payment` | optimal payment date |
| UC-08 | Spend Concentration Risk | 2 | `po_line_item` | concentration index |
| UC-09 | GR Quality Prediction | 3 | `gr_line_item` | `quantity_rejected > 0` |
| UC-10 | PR Priority Scoring | 3 | `pr_header` | priority class |
| UC-11 | Duplicate Invoice Detection | 3 | `invoice_header` | duplicate flag |
| UC-12 | Spend Classification | 3 | `po_line_item` | category prediction |
| UC-13 | Confidentiality Tier Prediction | 3 | `material_master` | `confidentiality_tier` |

### Folder Structure Convention

```
ml/
  common/                     # Shared DB config, feature store, utils
  data_processing/
    sql/                      # Postgres preprocessing scripts
    python/                   # Pandas preprocessing scripts
  uc_XX_<name>/               # Per-use-case folder
    exploration/              # EDA notebooks
    feature_engineering/      # Notebooks + saved .py copies
    training/                 # Pipeline notebook + SAP AI Core container
    inference/                # Serving script + SAP AI Core container
```

### Development Conventions

- **Data ingestion/preprocessing**: Create in both SQL (Postgres) and Python (Pandas), in separate files under `ml/data_processing/`.
- **Data exploration**: Done alongside ingestion/preprocessing. Use seaborn and plotly for graphs. Ensure axis scales match the data distribution (no mismatched scales).
- **Feature engineering**: Separate from preprocessing. Create functions in notebooks first with markdown explanations, then save a copy as a standalone `.py` file for reuse.
- **Training**: Create a training pipeline notebook using the preprocessing and feature engineering functions. Use MLFlow for experiment tracking and Optuna for hyperparameter tuning. The training folder should be deployable on SAP AI Core as a containerized application. Include a visualization/explanation notebook.
- **Inference**: Same containerized pattern as training — deployable on SAP AI Core (CF or Kyma).
- **Monitoring**: TBD
- **Retraining**: TBD

### ML Dependencies

```bash
pip install -e ".[ml]"
```

## Deployment

### EC2 Instance & Postgres Database

Connection details (IP, SSH key, DB credentials) are stored in `.env` (not committed). Copy `.env.example` to `.env` and fill in real values:

```bash
cp .env.example .env
# Edit .env with your EC2 IP, SSH key path, DB password, etc.
```

Default database settings: DB `procurement_demo`, schema `procurement`, user `procurement_user`, port `5432`.

### Data Pipeline

```bash
# 1. Generate data (includes Postgres SQL export)
python -m procurement_generator --scale 1

# 2. Deploy to EC2 (reads connection details from .env)
bash scripts/deploy_to_ec2.sh

# 3. Dry-run (prints commands without executing)
bash scripts/deploy_to_ec2.sh --dry-run
```

Manual deployment:
```bash
scp -i $SSH_KEY -r output/postgres/ $SSH_USER@$EC2_IP:/tmp/procurement_load/
ssh -i $SSH_KEY $SSH_USER@$EC2_IP "cd /tmp/procurement_load && sudo -u postgres psql -d $DB_NAME -f _load_all.sql"
```

### Export Formats

| Format | Output Path | Notes |
|--------|------------|-------|
| CSV | `output/csv/` | One file per table, standard CSV |
| HANA SQL | `output/sql/` | DDL + batch INSERT, SAP HANA compatible |
| Postgres SQL | `output/postgres/` | Schema-qualified DDL with PKs + `_load_all.sql` master script |


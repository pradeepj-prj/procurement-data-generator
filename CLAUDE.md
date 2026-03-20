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

# Install HANA Cloud driver
pip install -e ".[hana]"

# Deploy to HANA Cloud (reads .env)
python scripts/deploy_to_hana.py

# Deploy dry-run
python scripts/deploy_to_hana.py --dry-run

# Deploy knowledge graph (after relational data is loaded)
python scripts/graph/deploy_graph.py

# Graph deploy dry-run
python scripts/graph/deploy_graph.py --dry-run

# Graph deploy SQL-only (no graph workspace, views only)
python scripts/graph/deploy_graph.py --no-graph

# Install ML dependencies
pip install -e ".[ml]"

# Install GraphRAG (NetworkX only, no HANA needed)
pip install -e ".[graphrag]"

# Install GraphRAG + HANA Cloud backend
pip install -e ".[graphrag-hana]"

# MCP Server (NetworkX backend, no DB)
GRAPH_BACKEND=networkx python -m graphrag.mcp_server

# MCP Server (HANA Cloud backend)
GRAPH_BACKEND=hana python -m graphrag.mcp_server

# MCP Server (HTTP transport for SAP GenAI Hub MCP Gateway)
python -m graphrag.mcp_server --transport streamable-http --port 8080

# REST API
python -m graphrag.api

# REST API (dev mode with auto-reload)
uvicorn graphrag.api:app --reload --port 8000

# Train UC-02 model (from CSV data)
cd ml/uc_02_invoice_match/training
python train.py --data-source csv --csv-dir ../../../output/csv --n-trials 50

# Run inference
python -m ml.uc_02_invoice_match.inference.serve --model ml/uc_02_invoice_match/training/best_model.joblib --csv-dir output/csv
```

Output goes to `output/csv/`, `output/sql/`, `output/postgres/`, and `output/hana/`.

## Architecture

- **Pipeline**: 18-stage orchestrator (`pipeline.py`) runs generators in dependency order, validates after each stage, halts on FATAL errors
- **DataStore**: Central mutable state (`data_store.py`) — all generators write, all validators read
- **Models**: ~20 dataclasses in `models.py` matching SAP-style procurement tables
- **Seeds**: YAML files in `seeds/` anchor 12 demo scenarios with exact attribute values
- **Generators**: `generators/` — seed-first, then bulk fill to scale targets
- **Validators**: `validators/` — structural integrity (FK), business rules, seed verification, statistical distribution
- **Exporters**: `exporters/` — CSV (one per table), SQL (DDL + batch INSERT), Postgres (schema-qualified DDL + INSERT with PKs), and HANA Cloud (schema-qualified DDL with safe DROP blocks + monolithic load script)

Key generation order: org → categories → materials → legal entities → vendors → contracts → source list → confidentiality propagation → PRs → POs → GRs → invoices → payments → reconciliation.

## Key Files

| File | Purpose |
|------|---------|
| `src/procurement_generator/pipeline.py` | Stage orchestrator |
| `src/procurement_generator/models.py` | All entity dataclasses |
| `src/procurement_generator/data_store.py` | Central data store |
| `src/procurement_generator/config.py` | YAML config + ScaleConfig |
| `seeds/*.yaml` | Seed configuration (8 files) |
| `ml/common/db_config.py` | Dual CSV/Postgres data loader |
| `ml/common/feature_store.py` | Shared feature computation (vendor profile, performance, invoice behavior, price benchmarks) |
| `ml/data_processing/python/uc02_preprocessing.py` | UC-02 table joins and temporal features |
| `ml/uc_02_invoice_match/feature_engineering/feature_functions.py` | UC-02 feature pipeline with LOO and leakage guards |
| `ml/uc_02_invoice_match/training/train.py` | 4-model training (LR, RF, XGBoost, LightGBM) with Optuna + MLflow |
| `ml/uc_02_invoice_match/inference/serve.py` | Inference predictor with batch scoring and feature explanations |
| `src/procurement_generator/exporters/hana_exporter.py` | HANA Cloud SQL exporter |
| `scripts/deploy_to_hana.py` | HANA Cloud deploy script (hdbcli) |
| `scripts/graph/create_graph_workspace.sql` | Graph workspace DDL (10 vertex views, 14 edge views, GRAPH WORKSPACE) |
| `scripts/graph/deploy_graph.py` | Graph workspace deploy script (`--dry-run`, `--no-graph` fallback) |
| `graphrag/config.py` | GraphRAG config (HANA + NetworkX + GenAI Hub) from `.env` |
| `graphrag/backends/protocol.py` | `GraphBackend` Protocol (16 methods) |
| `graphrag/backends/networkx_backend.py` | NetworkX backend (CSV → MultiDiGraph) |
| `graphrag/backends/hana_backend.py` | HANA Cloud backend (SQL on vertex/edge views) |
| `graphrag/retrieval/context_formatter.py` | Format graph results as structured text for LLM |
| `graphrag/llm/router.py` | Intent classification → graph query → LLM answer |
| `graphrag/mcp_server.py` | MCP server (10 tools, stdio + HTTP transport) |
| `graphrag/api.py` | FastAPI REST endpoint (`POST /chat`) |

## ML Use Cases

### Implementation Status

| ID | Name | Status |
|----|------|--------|
| UC-02 | Invoice Three-Way Match | **Complete** — preprocessing, feature engineering, training (4 models), inference, SAP AI Core Dockerfiles |
| UC-01, UC-03–UC-13 | All others | Not started |

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

### Configuration

Connection details for both HANA Cloud and EC2 Postgres are stored in `.env` (not committed). Copy `.env.example` to `.env` and fill in real values:

```bash
cp .env.example .env
# Edit .env with your connection details
```

**HANA Cloud**: `HANA_HOST`, `HANA_PORT` (443), `HANA_USER` (DBADMIN), `HANA_PASSWORD`, `HANA_SCHEMA` (PROCUREMENT).

**EC2 Postgres**: `EC2_IP`, `SSH_KEY`, `SSH_USER` (ubuntu), `DB_NAME` (procurement_demo), `DB_USER` (procurement_user), `DB_PASSWORD`, `DB_SCHEMA` (procurement), `DB_PORT` (5432).

### Data Pipeline

```bash
# 1. Generate data (all exports: CSV, SQL, Postgres, HANA Cloud)
python -m procurement_generator --scale 1

# 2. Deploy to HANA Cloud
python scripts/deploy_to_hana.py          # real deploy
python scripts/deploy_to_hana.py --dry-run # preview only

# 3. Deploy to EC2 Postgres
bash scripts/deploy_to_ec2.sh             # real deploy
bash scripts/deploy_to_ec2.sh --dry-run   # preview only
```

### Export Formats

| Format | Output Path | Notes |
|--------|------------|-------|
| CSV | `output/csv/` | One file per table, standard CSV |
| HANA SQL (basic) | `output/sql/` | DDL + batch INSERT, no schema prefix |
| HANA Cloud SQL | `output/hana/` | Schema-qualified DDL with PKs, safe DROP blocks, `_load_all_hana.sql` monolithic script |
| Postgres SQL | `output/postgres/` | Schema-qualified DDL with PKs + `_load_all.sql` master script |


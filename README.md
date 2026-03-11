# Procurement Data Generator

Generates realistic, referentially-intact procurement datasets for an AMR (Autonomous Mobile Robots) manufacturing company. Produces 29 interlinked tables (~10K rows at 1x scale) covering the full procure-to-pay cycle, designed for GenAI demos on SAP HANA Cloud.

## What It Does

The generator creates a complete procurement data landscape:

- **Master data** -- company codes, plants, vendors, materials, contracts, category hierarchies
- **Transactional data** -- purchase requisitions, purchase orders, goods receipts, invoices, payments
- **Cross-table integrity** -- all foreign keys are valid, business rules are enforced, and 12 demo scenarios are seeded with exact attribute values

Data is exported in four formats (CSV, basic SQL, HANA Cloud SQL, Postgres SQL) and can be deployed directly to SAP HANA Cloud on BTP or PostgreSQL on EC2.

## Quick Start

```bash
# Install
pip install -e .

# Generate data (scale: 1, 3, or 10)
python -m procurement_generator --scale 1

# Output appears in:
#   output/csv/      -- one CSV per table
#   output/sql/      -- basic HANA-compatible DDL + INSERT
#   output/hana/     -- HANA Cloud DDL with schema, PKs, safe DROP blocks
#   output/postgres/ -- Postgres DDL with schema, PKs, DROP CASCADE
```

## Deploy to SAP HANA Cloud

```bash
# Install HANA driver
pip install -e ".[hana]"

# Configure connection
cp .env.example .env
# Edit .env with your HANA Cloud endpoint, user, and password

# Preview
python scripts/deploy_to_hana.py --dry-run

# Deploy
python scripts/deploy_to_hana.py
```

Requires a HANA Cloud instance on SAP BTP. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for setup instructions.

## Deploy to PostgreSQL

```bash
# Configure connection
cp .env.example .env
# Edit .env with your EC2 IP, SSH key, and DB credentials

# Deploy
bash scripts/deploy_to_ec2.sh
```

## Data Model

29 tables organized in FK-safe dependency order:

```
Org Structure          Master Data              Transactions
─────────────          ───────────              ────────────
company_code      ──>  material_master      ──>  pr_header
purchasing_org         material_plant_ext        pr_line_item
purchasing_group       legal_entity         ──>  po_header
purch_group_category   vendor_master             po_line_item
plant                  vendor_category      ──>  gr_header
storage_location       vendor_address            gr_line_item
cost_center            vendor_contact       ──>  invoice_header
category_hierarchy     source_list               invoice_line_item
                       contract_header      ──>  payment
                       contract_item             payment_invoice_link
                       uom_conversion
```

At 1x scale: ~800 materials, ~120 vendors, ~40 contracts, ~500 PRs, ~400 POs, ~350 GRs, ~320 invoices, ~260 payments (~10,600 total rows).

## Pipeline Architecture

An 18-stage orchestrator runs generators in dependency order, validates after each stage, and halts on fatal errors:

1. Org structure (company, plants, purchasing groups, cost centers)
2. Category hierarchy (3-level, ~80 categories)
3. Materials (~800 with plant extensions)
4. Legal entities
5. Vendors (~120 with addresses, contacts, category mappings)
6. Contracts (~40 with line items)
7. Source list (~2,800 material-vendor-plant entries)
8. Confidentiality propagation
9. Master data validation (FK integrity + business rules)
10. Purchase requisitions
11. Purchase orders (including ~5-8% maverick POs)
12. Goods receipts
13. Invoices (three-way match logic)
14. Payments
15. Reconciliation (contract consumption, delivery dates)
16. Full validation (structural + business + statistical)
17. Seed verification (12 demo scenarios)
18. Export (CSV + SQL + HANA Cloud + Postgres)

## Seed Scenarios

12 pre-configured demo scenarios in `seeds/` ensure specific data patterns exist for demos:

| Seed | Scenario |
|------|----------|
| SEED-001 | Single-source LiDAR with expiring contract |
| SEED-002 | Battery cell supply concentration |
| SEED-003 | Restricted vendor bank account |
| SEED-004 | Mixed confidentiality BMS sources |
| SEED-005 | Off-contract motors |
| SEED-006 | Vendor alias consolidation (Nidec) |
| SEED-007 | SBC sourcing gap at SG01 |
| SEED-008 | Camera long lead time |
| SEED-009 | PG-MECH excluded from ELEC categories |
| SEED-010 | Contract price > standard cost (connector) |
| SEED-011 | Conditional vendor (sheet metal) |
| SEED-012 | Multi-plant sourcing (BLDC Motor) |

## ML Use Cases

The generated data supports 13 ML use cases across three tiers. UC-02 (Invoice Three-Way Match) is fully implemented.

| ID | Use Case | Status |
|----|----------|--------|
| UC-02 | Invoice Three-Way Match | **Complete** -- 4-model pipeline (LR, RF, XGBoost, LightGBM), Optuna tuning, MLflow tracking |
| UC-01 | Maverick PO Detection | Not started |
| UC-03 | Vendor Risk Scoring | Not started |
| UC-04 | Price Anomaly Detection | Not started |
| UC-05--13 | 9 additional use cases | Not started |

See [docs/ML_USE_CASES.md](docs/ML_USE_CASES.md) for the full catalog.

```bash
# Install ML dependencies
pip install -e ".[ml]"

# Train UC-02 model
cd ml/uc_02_invoice_match/training
python train.py --data-source csv --csv-dir ../../../output/csv --n-trials 50

# Run inference
python -m ml.uc_02_invoice_match.inference.serve \
  --model ml/uc_02_invoice_match/training/best_model.joblib \
  --csv-dir output/csv
```

## Project Structure

```
procurement-data-generator/
  src/procurement_generator/
    pipeline.py              # 18-stage orchestrator
    models.py                # ~20 dataclasses (SAP-style tables)
    data_store.py            # Central mutable state
    config.py                # YAML config + ScaleConfig
    generators/              # One generator per entity group
    validators/              # FK integrity, business rules, stats
    exporters/               # CSV, SQL, HANA Cloud, Postgres
  seeds/                     # YAML seed files (12 scenarios)
  scripts/
    deploy_to_hana.py        # HANA Cloud deployment (hdbcli)
    deploy_to_ec2.sh         # EC2 Postgres deployment (SSH)
  ml/
    common/                  # Shared DB config, feature store
    data_processing/         # SQL + Python preprocessing
    uc_02_invoice_match/     # Complete ML pipeline
  tests/
  docs/
    DEPLOYMENT.md            # Deployment guide (HANA + Postgres)
    ML_USE_CASES.md          # 13 use case specifications
    ARCHITECTURE.md          # System architecture
```

## Testing

```bash
pip install -e ".[dev]"
pytest tests/
```

## Requirements

- Python 3.10+
- Core: `pyyaml`, `faker`
- HANA deploy: `hdbcli` (`pip install -e ".[hana]"`)
- ML: `pandas`, `scikit-learn`, `xgboost`, `lightgbm`, `mlflow`, `optuna` (`pip install -e ".[ml]"`)

## License

Internal use -- AMR Manufacturing GenAI Demo.

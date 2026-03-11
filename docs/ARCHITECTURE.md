# Architecture

## Overview

The procurement data generator is a Python application that produces realistic, referentially-intact procurement datasets modeled after SAP procurement structures. The data is used for GenAI demos and ML use case development.

```
                         ┌──────────────┐
                         │  seeds/*.yaml │  (8 YAML files)
                         └──────┬───────┘
                                │
                                v
┌─────────────────────────────────────────────────────────────┐
│                     Pipeline (18 stages)                     │
│                                                              │
│  ┌──────────┐  ┌────────────┐  ┌────────────┐  ┌─────────┐ │
│  │Generators├─>│  DataStore  ├─>│ Validators  ├─>│Exporters│ │
│  └──────────┘  └────────────┘  └────────────┘  └─────────┘ │
│                                                              │
└──────────────────────────────┬───────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              v                v                v
        output/csv/      output/sql/     output/postgres/
                                                │
                                          deploy_to_ec2.sh
                                                │
                                                v
                                    ┌───────────────────┐
                                    │  EC2 / PostgreSQL  │
                                    │  procurement_demo  │
                                    └───────────────────┘
```

## Components

### Pipeline (`pipeline.py`)

The central orchestrator. Runs 18 stages in strict dependency order. Each stage:
1. Calls a generator (or validator/exporter)
2. Returns `ValidationResult` objects
3. Halts on any FATAL failure

**Stage order:**

| # | Stage | Type | Output |
|---|-------|------|--------|
| 1 | Org Structure | Generator | company codes, plants, purchasing orgs/groups, storage locations, cost centers |
| 2 | Category Hierarchy | Generator | 3-level category tree (~79 nodes) |
| 3 | Materials | Generator | material master + plant extensions |
| 4 | Legal Entities | Generator | legal entity records |
| 5 | Vendors | Generator | vendor master + categories, addresses, contacts |
| 6 | Contracts | Generator | contract headers + items + UOM conversions |
| 7 | Source List | Generator | material-vendor-plant sourcing lanes |
| 8 | Confidentiality | Validator | propagate confidentiality tiers to source list |
| 9 | Master Validation | Validator | FK integrity + business rules on master data |
| 10 | Purchase Requisitions | Generator | PR headers + line items |
| 11 | Purchase Orders | Generator | PO headers + line items |
| 12 | Goods Receipts | Generator | GR headers + line items |
| 13 | Invoices | Generator | invoice headers + line items |
| 14 | Payments | Generator | payments + payment-invoice links |
| 15 | Reconciliation | Post-proc | contract consumption + delivery date backfill |
| 16 | Full Validation | Validator | all integrity, business rules, and statistical checks |
| 17 | Seed Verification | Validator | verify all 12 seed scenarios present |
| 18 | Export | Exporter | CSV + HANA SQL + Postgres SQL |

### DataStore (`data_store.py`)

Central mutable state container. Holds 29 typed lists (one per table). All generators write to it; all validators read from it. Provides lookup helpers (`material_by_id`, `vendor_by_id`, etc.) for cross-table references during generation.

### Models (`models.py`)

~20 Python dataclasses defining the schema for all entity types. Each maps to a database table. Fields use `Optional[T]` for nullable columns. The models are grouped into:

- **Organizational**: `CompanyCode`, `PurchasingOrg`, `PurchasingGroup`, `Plant`, `StorageLocation`, `CostCenter`
- **Categorization**: `CategoryHierarchy`, `PurchasingGroupCategory`
- **Materials**: `MaterialMaster`, `MaterialPlantExtension`
- **Vendors**: `LegalEntity`, `VendorMaster`, `VendorCategory`, `VendorAddress`, `VendorContact`
- **Sourcing**: `SourceList`, `ContractHeader`, `ContractItem`, `UOMConversion`
- **Transactional**: `PRHeader`, `PRLineItem`, `POHeader`, `POLineItem`, `GRHeader`, `GRLineItem`, `InvoiceHeader`, `InvoiceLineItem`, `Payment`, `PaymentInvoiceLink`

### Seeds (`seeds/*.yaml`)

8 YAML files that define 12 demo scenarios with exact attribute values. Generators process seeds first, then bulk-fill remaining rows to hit scale targets. Seeds ensure specific scenarios (e.g., a maverick PO, a blocked vendor, a price anomaly) are always present in the generated data.

### Generators (`generators/`)

One module per entity group. Each generator:
1. Reads seed config for pre-defined entities
2. Creates seed entities first
3. Bulk-generates remaining entities to hit the scale target
4. Writes all entities to the DataStore

### Validators (`validators/`)

Four validation modules:
- **`integrity.py`** — Foreign key checks across all tables
- **`business_rules.py`** — Domain-specific rules (e.g., contract dates, vendor status)
- **`seeds.py`** — Verifies all 12 seed scenarios exist with correct attributes
- **`statistical.py`** — Distribution checks (maverick rate 5-8%, on-contract 70-75%, etc.)

### Exporters (`exporters/`)

Three export formats, all generated from the same DataStore:
- **`csv_exporter.py`** — One CSV file per table
- **`sql_exporter.py`** — HANA-compatible DDL + batch INSERT
- **`postgres_exporter.py`** — Postgres DDL with schema qualification, primary keys, `DROP CASCADE`, and a `_load_all.sql` master script

### Config (`config.py`)

- `ScaleConfig` — Scale multiplier (1x, 3x, 10x) with computed targets for each entity type
- YAML loading for seeds and config

### Deployment (`scripts/deploy_to_ec2.sh`)

Shell script that pushes generated Postgres SQL to an EC2 instance. Reads connection details from `.env`. Supports `--dry-run`. See `docs/DEPLOYMENT.md` for details.

## Data Flow

```
Seeds (YAML) ──> Generators ──> DataStore ──> Validators ──> Exporters
                     │              ^              │
                     └──────────────┘              │
                    (write entities)          (read & check)
```

1. **Seed-first generation**: Each generator reads its seed YAML, creates those entities, then generates bulk entities to fill the scale target
2. **Dependency ordering**: Generators run in FK-dependency order (org before materials, materials before vendors, etc.)
3. **Validation gates**: After master data and again after all transactional data, validators check FK integrity, business rules, and statistical distributions
4. **Export**: All three formats are produced from the same DataStore snapshot

## Scale Model

| Entity | 1x | 3x | 10x |
|--------|---:|---:|----:|
| Materials | 800 | 2,400 | 8,000 |
| Vendors | 120 | 360 | 1,200 |
| Contracts | 40 | 120 | 400 |
| Legal Entities | 95 | 285 | 950 |
| Purchase Requisitions | 500 | 1,500 | 5,000 |
| Purchase Orders | 400 | 1,200 | 4,000 |
| Goods Receipts | 350 | 1,050 | 3,500 |
| Invoices | 320 | 960 | 3,200 |
| Payments | 280 | 840 | 2,800 |
| **Total (approx.)** | **~10,600** | **~31,800** | **~106,000** |

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.10+ |
| Data models | Python dataclasses |
| Config | YAML (PyYAML) |
| Synthetic data | Faker |
| SQL (HANA) | Custom DDL generator |
| SQL (Postgres) | Custom DDL generator |
| Database | PostgreSQL 16 on EC2 (Ubuntu) |
| Deployment | Bash + SSH/SCP |
| ML pipeline | pandas, scikit-learn, XGBoost, LightGBM, MLflow, Optuna |
| ML containers | Docker (SAP AI Core compatible) |

## ML Pipeline Architecture

UC-02 (Invoice Three-Way Match) is fully implemented. The remaining 12 use cases follow the same pattern.

```
                    ┌──────────────────────────────────┐
                    │         EC2 / PostgreSQL          │
                    │     procurement_demo.procurement  │
                    └───────────────┬──────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    v               v               v
            ml/data_processing  ml/common     ml/uc_XX_*/
            (SQL + Python)    (feature store)  (per use case)
                    │               │               │
                    v               v               v
              Preprocessing   Feature Eng.    Training / Inference
                                                    │
                                              ┌─────┴─────┐
                                              v           v
                                         SAP AI Core   MLflow
                                        (containers)  (tracking)
```

### ML Module Structure

```
ml/
  common/
    db_config.py              # Dual CSV/Postgres data loader
    feature_store.py          # Shared feature groups (vendor profile, performance, invoice behavior, price benchmarks)
    utils.py                  # Ordinal maps, currency conversion
  data_processing/
    sql/
      uc02_preprocessing.sql  # Postgres-based preprocessing
      feature_store_views.sql # Materialized views for feature store
    python/
      uc02_preprocessing.py   # Pandas-based table joins + temporal features
  uc_02_invoice_match/
    exploration/              # EDA notebook
    feature_engineering/      # Notebook + standalone .py copy
    training/                 # train.py + config.yaml + Dockerfile
    inference/                # serve.py + Dockerfile
```

**Key design decisions:**
- **Leave-one-out (LOO)**: Vendor invoice behavior features exclude the current invoice during training to prevent leakage; full history used at inference
- **Dual preprocessing**: SQL and Python implementations for each use case, either can be used
- **Shared feature store**: `ml/common/feature_store.py` computes vendor profile, historical performance, invoice behavior, and price benchmarks — reusable across use cases
- **Leakage guards**: Explicit `LEAKAGE_COLUMNS` list in feature functions prevents target-correlated fields from entering the feature matrix
- **4-model comparison**: Logistic Regression (baseline), Random Forest, XGBoost + Optuna, LightGBM + Optuna
- **SAP AI Core containers**: Training and inference Dockerfiles follow the SAP AI Core containerization pattern

See `docs/ML_USE_CASES.md` for the 13 use cases and `CLAUDE.md` for ML folder conventions.

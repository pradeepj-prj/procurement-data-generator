# Procurement Data Generator - TODO

## Project Setup
- [x] pyproject.toml with dependencies
- [x] Package structure (src/procurement_generator/)
- [x] CLI entry point (cli.py, __main__.py)

## Models & Infrastructure
- [x] Dataclasses for all ~20 entity types (models.py)
- [x] Central DataStore with typed lists + lookups (data_store.py)
- [x] Config loading + ScaleConfig (config.py)
- [x] Utility functions (utils.py)

## Seed Files
- [x] seeds/config.yaml
- [x] seeds/org_structure.yaml
- [x] seeds/category_hierarchy.yaml
- [x] seeds/seed_materials.yaml
- [x] seeds/seed_vendors.yaml
- [x] seeds/seed_legal_entities.yaml
- [x] seeds/seed_contracts.yaml
- [x] seeds/seed_source_lists.yaml

## Generators (Master Data)
- [x] Org structure generator
- [x] Category hierarchy generator
- [x] Materials generator (seed + bulk, plant extensions)
- [x] Legal entities generator (seed + bulk, alias groups)
- [x] Vendors generator (seed + bulk, categories, addresses, contacts)
- [x] Contracts generator (seed + bulk, items, UOM conversions)
- [x] Source list generator (seed + bulk)

## Generators (Transactional)
- [x] Purchase requisitions generator
- [x] Purchase orders generator (on-contract + maverick + PR-derived)
- [x] Goods receipts generator
- [x] Invoices generator (three-way match)
- [x] Payments generator

## Validators
- [x] Structural integrity (18 FK checks)
- [x] Business rules (criticality, confidentiality, blocked vendors, etc.)
- [x] Scenario seed verification (12 seeds)
- [x] Statistical distribution checks

## Exporters
- [x] CSV exporter
- [x] SQL exporter (DDL + batch INSERT)

## Pipeline
- [x] 18-stage orchestrator with halt-on-FATAL
- [x] Confidentiality propagation stage
- [x] Contract consumption reconciliation
- [x] Full validation pass

## Documentation
- [x] Plan document (plans/2026-03-06/PLAN_1.md)
- [x] TODO checklist (todo/TODO.md)
- [x] Test results (test_results/2026-03-06/TEST_1.md)
- [x] CLAUDE.md with build/run/test commands
- [x] .gitignore

## Verification
- [x] 78/78 FATAL checks pass
- [x] 8/8 WARNING checks pass
- [x] 12/12 scenario seeds verified
- [x] On-contract PO %: 72% (target 70-75%)
- [x] Maverick PO %: 6% (target 5-8%)
- [x] Invoice match rate: 81% (target 80-85%)
- [x] ~10,600 total rows across 29 tables

## ML Infrastructure
- [x] Dual data loader — CSV and Postgres (`ml/common/db_config.py`)
- [x] Shared feature store — vendor profile, performance, invoice behavior, price benchmarks (`ml/common/feature_store.py`)
- [x] Utility maps — ordinal encodings, currency conversion (`ml/common/utils.py`)
- [x] SQL feature store views (`ml/data_processing/sql/feature_store_views.sql`)

## ML UC-02: Invoice Three-Way Match
- [x] SQL preprocessing (`ml/data_processing/sql/uc02_preprocessing.sql`)
- [x] Python preprocessing (`ml/data_processing/python/uc02_preprocessing.py`)
- [x] EDA notebook (`ml/uc_02_invoice_match/exploration/01_eda.ipynb`)
- [x] Feature engineering notebook (`ml/uc_02_invoice_match/feature_engineering/02_feature_engineering.ipynb`)
- [x] Feature functions standalone script (`ml/uc_02_invoice_match/feature_engineering/feature_functions.py`)
- [x] Training pipeline notebook (`ml/uc_02_invoice_match/training/03_training_pipeline.ipynb`)
- [x] Model explanation notebook (`ml/uc_02_invoice_match/training/04_model_explanation.ipynb`)
- [x] Standalone training script (`ml/uc_02_invoice_match/training/train.py`)
- [x] Training config (`ml/uc_02_invoice_match/training/config.yaml`)
- [x] Training Dockerfile (`ml/uc_02_invoice_match/training/Dockerfile`)
- [x] Inference demo notebook (`ml/uc_02_invoice_match/inference/05_inference_demo.ipynb`)
- [x] Inference serving script + Dockerfile (`ml/uc_02_invoice_match/inference/serve.py`)

## ML Remaining
- [ ] UC-01: Maverick PO Detection
- [ ] UC-03: Vendor Risk Scoring
- [ ] UC-04: Price Anomaly Detection
- [ ] UC-05: Delivery Delay Prediction
- [ ] UC-06: Contract Renewal Prediction
- [ ] UC-07: Payment Timing Optimization
- [ ] UC-08: Spend Concentration Risk
- [ ] UC-09: GR Quality Prediction
- [ ] UC-10: PR Priority Scoring
- [ ] UC-11: Duplicate Invoice Detection
- [ ] UC-12: Spend Classification
- [ ] UC-13: Confidentiality Tier Prediction
- [ ] ML monitoring infrastructure
- [ ] ML retraining pipeline

# Plan 3: UC-02 Invoice Three-Way Match — ML Pipeline

## Context

This plan covers the full ML pipeline for UC-02 (Invoice Three-Way Match), building on the configurable ML signal enrichment from Plan 2 (`MLSignalConfig`). UC-02 was chosen as the first use case because it has the highest positive rate (15-20%), a clean multi-class label (`match_status`), and works at 1x scale (320 invoices).

## Relationship to Plan 2

Plan 2 added `MLSignalConfig` to make the generated data ML-realistic (correlated vendor scores, quality-influenced invoice variance). Plan 3 consumes that enriched data to build a complete ML pipeline from preprocessing through inference.

## Files Created

### Shared Infrastructure (`ml/common/`)

| File | Purpose |
|------|---------|
| `db_config.py` | Dual data loader — CSV files (local dev) and Postgres (EC2). Type coercion for booleans, dates, decimals. |
| `feature_store.py` | Shared feature computation groups: vendor composite profile (3.1), vendor historical performance (3.2), vendor invoice behavior with LOO (3.3), price benchmarks (3.5). |
| `utils.py` | Ordinal encoding maps (vendor status, country risk, criticality, confidentiality), currency conversion, common constants. |

### Data Processing (`ml/data_processing/`)

| File | Purpose |
|------|---------|
| `sql/uc02_preprocessing.sql` | Postgres preprocessing — joins invoice → PO → GR → vendor → material. |
| `sql/feature_store_views.sql` | Materialized views for vendor profile, performance, and invoice behavior. |
| `python/uc02_preprocessing.py` | Pandas equivalent — same joins, plus temporal feature extraction (day-of-week, month, quarter). |

### UC-02 Pipeline (`ml/uc_02_invoice_match/`)

| File | Purpose |
|------|---------|
| `exploration/01_eda.ipynb` | Exploratory data analysis — distributions, correlations, class balance. |
| `feature_engineering/02_feature_engineering.ipynb` | Feature development with explanations. |
| `feature_engineering/feature_functions.py` | Standalone `.py` copy for reuse in training/inference. |
| `training/03_training_pipeline.ipynb` | Full training pipeline notebook. |
| `training/04_model_explanation.ipynb` | SHAP, feature importances, confusion matrices. |
| `training/train.py` | Standalone training script (CLI, containerizable). |
| `training/config.yaml` | Training hyperparameters and CV settings. |
| `training/Dockerfile` | SAP AI Core training container. |
| `training/requirements.txt` | Training dependencies. |
| `inference/05_inference_demo.ipynb` | Inference demonstration notebook. |
| `inference/serve.py` | `InvoiceMatchPredictor` class — single and batch scoring with feature explanations. |
| `inference/Dockerfile` | SAP AI Core inference container. |
| `inference/requirements.txt` | Inference dependencies. |

## Design Decisions

### 1. Leave-One-Out (LOO) for Vendor Invoice Behavior

**Problem**: Vendor invoice behavior features (match rate, variance rate) include the current invoice's outcome, creating direct target leakage.

**Solution**: During training, compute vendor stats excluding the current invoice (`compute_vendor_invoice_behavior_loo`). At inference time, use full vendor history (the new invoice hasn't been labeled yet).

Cold-start handling: Vendors with only 1 invoice in training get global average features.

### 2. Dual Preprocessing (SQL + Python)

Both SQL (Postgres) and Python (Pandas) preprocessing scripts produce the same base dataset. This allows:
- SQL for production (faster, runs on the database server)
- Python for local development and notebooks

### 3. Explicit Leakage Guards

`LEAKAGE_COLUMNS` list in `feature_functions.py` enumerates columns that correlate with the target: `price_variance`, `quantity_variance`, `payment_block`, invoice amounts. These are dropped before training regardless of feature selection.

### 4. Four-Model Comparison

| Model | Role |
|-------|------|
| Logistic Regression | Linear baseline (with StandardScaler) |
| Random Forest | Non-linear baseline |
| XGBoost + Optuna | Gradient boosting with 50-trial hyperparameter search |
| LightGBM + Optuna | Alternative gradient boosting with 50-trial search |

Best model selected by cross-validated F1 score (5-fold × 3 repeats). Final model retrained on all data and saved as `.joblib`.

### 5. MLflow Experiment Tracking

All runs logged to local `mlruns/` directory. Each model logs: hyperparameters, CV F1 mean/std, Optuna trial count. Final model artifact registered.

### 6. SAP AI Core Containers

Training and inference Dockerfiles follow SAP AI Core patterns:
- Base image: `python:3.11-slim`
- Dependencies from `requirements.txt`
- Entrypoint: `train.py` (training) or `serve.py` (inference)
- Config via environment variables and mounted volumes

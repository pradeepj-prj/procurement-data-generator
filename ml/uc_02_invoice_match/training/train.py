"""UC-02 Invoice Three-Way Match — Standalone training script.

Usage:
    python train.py --data-source csv --csv-dir ../../../output/csv --target binary --n-trials 50

Containerizable for SAP AI Core deployment.
"""

import argparse
import sys
from pathlib import Path

import joblib
import mlflow
import numpy as np
import optuna
import yaml
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import RepeatedStratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# Add project root to path for imports
_project_root = Path(__file__).resolve().parents[3]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from ml.common.db_config import load_tables
from ml.data_processing.python.uc02_preprocessing import UC02_TABLES
from ml.uc_02_invoice_match.feature_engineering.feature_functions import (
    build_uc02_features,
    prepare_feature_matrix,
)


def load_config(config_path: str = "config.yaml") -> dict:
    """Load training configuration from YAML."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_cv(config: dict) -> RepeatedStratifiedKFold:
    """Create cross-validation splitter from config."""
    cv_cfg = config.get("cv", {})
    return RepeatedStratifiedKFold(
        n_splits=cv_cfg.get("n_splits", 5),
        n_repeats=cv_cfg.get("n_repeats", 3),
        random_state=cv_cfg.get("random_state", 42),
    )


def evaluate_model(model, X, y, cv, metric="f1"):
    """Evaluate model with cross-validation and return mean/std scores."""
    scores = cross_val_score(model, X, y, cv=cv, scoring=metric, n_jobs=-1)
    return scores.mean(), scores.std()


def train_logistic_regression(X, y, cv, config):
    """Train and evaluate Logistic Regression baseline."""
    lr_cfg = config.get("models", {}).get("logistic_regression", {})
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(
            class_weight=lr_cfg.get("class_weight", "balanced"),
            max_iter=lr_cfg.get("max_iter", 1000),
            solver=lr_cfg.get("solver", "lbfgs"),
            random_state=42,
        )),
    ])
    mean_f1, std_f1 = evaluate_model(model, X, y, cv)

    with mlflow.start_run(run_name="logistic_regression"):
        mlflow.log_params(lr_cfg)
        mlflow.log_metric("cv_f1_mean", mean_f1)
        mlflow.log_metric("cv_f1_std", std_f1)

    print(f"  Logistic Regression: F1 = {mean_f1:.4f} (+/- {std_f1:.4f})")
    return model, mean_f1


def train_random_forest(X, y, cv, config):
    """Train and evaluate Random Forest."""
    rf_cfg = config.get("models", {}).get("random_forest", {})
    model = RandomForestClassifier(
        n_estimators=rf_cfg.get("n_estimators", 100),
        class_weight=rf_cfg.get("class_weight", "balanced"),
        random_state=rf_cfg.get("random_state", 42),
    )
    mean_f1, std_f1 = evaluate_model(model, X, y, cv)

    with mlflow.start_run(run_name="random_forest"):
        mlflow.log_params(rf_cfg)
        mlflow.log_metric("cv_f1_mean", mean_f1)
        mlflow.log_metric("cv_f1_std", std_f1)

    print(f"  Random Forest: F1 = {mean_f1:.4f} (+/- {std_f1:.4f})")
    return model, mean_f1


def train_xgboost_optuna(X, y, cv, config):
    """Train XGBoost with Optuna hyperparameter tuning."""
    import xgboost as xgb

    optuna_cfg = config.get("optuna", {})
    n_trials = optuna_cfg.get("n_trials", 50)
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    scale_pos = n_neg / max(n_pos, 1)

    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 50, 300),
            "max_depth": trial.suggest_int("max_depth", 2, 8),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
            "scale_pos_weight": scale_pos,
            "eval_metric": "logloss",
            "random_state": 42,
        }
        model = xgb.XGBClassifier(**params)
        score, _ = evaluate_model(model, X, y, cv)
        return score

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize", study_name="xgboost_uc02")
    study.optimize(objective, n_trials=n_trials, timeout=optuna_cfg.get("timeout", 600))

    best_params = study.best_params
    best_params["scale_pos_weight"] = scale_pos
    best_params["eval_metric"] = "logloss"
    best_params["random_state"] = 42

    model = xgb.XGBClassifier(**best_params)
    mean_f1, std_f1 = evaluate_model(model, X, y, cv)

    with mlflow.start_run(run_name="xgboost_optuna"):
        mlflow.log_params(best_params)
        mlflow.log_metric("cv_f1_mean", mean_f1)
        mlflow.log_metric("cv_f1_std", std_f1)
        mlflow.log_metric("optuna_n_trials", len(study.trials))
        mlflow.log_metric("optuna_best_value", study.best_value)

    print(f"  XGBoost (Optuna): F1 = {mean_f1:.4f} (+/- {std_f1:.4f})")
    return model, mean_f1, best_params


def train_lightgbm_optuna(X, y, cv, config):
    """Train LightGBM with Optuna hyperparameter tuning."""
    import lightgbm as lgb

    optuna_cfg = config.get("optuna", {})
    n_trials = optuna_cfg.get("n_trials", 50)

    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 50, 300),
            "num_leaves": trial.suggest_int("num_leaves", 8, 128),
            "max_depth": trial.suggest_int("max_depth", 2, 8),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 50),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
            "is_unbalance": True,
            "random_state": 42,
            "verbose": -1,
        }
        model = lgb.LGBMClassifier(**params)
        score, _ = evaluate_model(model, X, y, cv)
        return score

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize", study_name="lightgbm_uc02")
    study.optimize(objective, n_trials=n_trials, timeout=optuna_cfg.get("timeout", 600))

    best_params = study.best_params
    best_params["is_unbalance"] = True
    best_params["random_state"] = 42
    best_params["verbose"] = -1

    model = lgb.LGBMClassifier(**best_params)
    mean_f1, std_f1 = evaluate_model(model, X, y, cv)

    with mlflow.start_run(run_name="lightgbm_optuna"):
        mlflow.log_params(best_params)
        mlflow.log_metric("cv_f1_mean", mean_f1)
        mlflow.log_metric("cv_f1_std", std_f1)
        mlflow.log_metric("optuna_n_trials", len(study.trials))
        mlflow.log_metric("optuna_best_value", study.best_value)

    print(f"  LightGBM (Optuna): F1 = {mean_f1:.4f} (+/- {std_f1:.4f})")
    return model, mean_f1, best_params


def main():
    parser = argparse.ArgumentParser(description="UC-02 Invoice Match Training")
    parser.add_argument("--data-source", default="csv", choices=["csv", "postgres"])
    parser.add_argument("--csv-dir", default="../../../output/csv")
    parser.add_argument("--target", default="binary", choices=["binary", "multiclass"])
    parser.add_argument("--n-trials", type=int, default=50)
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--output-model", default="best_model.joblib")
    args = parser.parse_args()

    # Load config
    config_path = Path(__file__).parent / args.config
    config = load_config(config_path) if config_path.exists() else {}
    if args.n_trials:
        config.setdefault("optuna", {})["n_trials"] = args.n_trials

    # Setup MLflow
    experiment_name = config.get("experiment_name", "uc02_invoice_match")
    mlflow.set_tracking_uri("file:./mlruns")
    mlflow.set_experiment(experiment_name)

    # Load data
    print("Loading data...")
    csv_dir = Path(args.csv_dir)
    if not csv_dir.is_absolute():
        csv_dir = Path(__file__).parent / csv_dir
    tables = load_tables(args.data_source, UC02_TABLES, csv_dir=csv_dir)
    print(f"  Loaded {len(tables)} tables")

    # Build features
    print("Building features...")
    feature_df = build_uc02_features(tables, leave_one_out=True)
    X, y = prepare_feature_matrix(feature_df, target=args.target)
    print(f"  Feature matrix: {X.shape[0]} rows, {X.shape[1]} features")
    print(f"  Target distribution: {dict(y.value_counts())}")

    # Check for leakage
    max_corr = X.corrwith(y).abs().max()
    if max_corr > 0.90:
        print(f"  WARNING: Max feature-target correlation = {max_corr:.3f} — possible leakage!")

    # Cross-validation setup
    cv = get_cv(config)
    print(f"\nTraining models (CV: {cv.n_splits}-fold x {cv.n_repeats} repeats)...")

    # Train all models
    results = {}

    lr_model, lr_f1 = train_logistic_regression(X, y, cv, config)
    results["logistic_regression"] = (lr_model, lr_f1)

    rf_model, rf_f1 = train_random_forest(X, y, cv, config)
    results["random_forest"] = (rf_model, rf_f1)

    xgb_model, xgb_f1, xgb_params = train_xgboost_optuna(X, y, cv, config)
    results["xgboost"] = (xgb_model, xgb_f1)

    lgb_model, lgb_f1, lgb_params = train_lightgbm_optuna(X, y, cv, config)
    results["lightgbm"] = (lgb_model, lgb_f1)

    # Select best model
    best_name = max(results, key=lambda k: results[k][1])
    best_model, best_f1 = results[best_name]
    print(f"\nBest model: {best_name} (F1 = {best_f1:.4f})")

    # Train final model on all data
    print("Training final model on all data...")
    best_model.fit(X, y)

    # Save model
    output_path = Path(__file__).parent / args.output_model
    joblib.dump({
        "model": best_model,
        "model_name": best_name,
        "feature_columns": list(X.columns),
        "target": args.target,
        "cv_f1": best_f1,
    }, output_path)
    print(f"Model saved to {output_path}")

    # Register with MLflow
    with mlflow.start_run(run_name=f"final_{best_name}"):
        mlflow.log_metric("final_cv_f1", best_f1)
        mlflow.log_param("best_model", best_name)
        mlflow.log_artifact(str(output_path))

    print("\nDone!")


if __name__ == "__main__":
    main()

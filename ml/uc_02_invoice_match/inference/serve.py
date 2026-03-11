"""UC-02 Invoice Three-Way Match — Inference scoring script.

Provides InvoiceMatchPredictor class for single and batch predictions.
Containerizable for SAP AI Core deployment.
"""

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

# Add project root to path for imports
_project_root = Path(__file__).resolve().parents[3]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from ml.uc_02_invoice_match.feature_engineering.feature_functions import (
    build_uc02_features,
    prepare_feature_matrix,
)


LABEL_MAP_BINARY = {0: "FULL_MATCH", 1: "ANY_VARIANCE"}
LABEL_MAP_MULTICLASS = {
    0: "FULL_MATCH",
    1: "PRICE_VARIANCE",
    2: "QUANTITY_VARIANCE",
    3: "BOTH_VARIANCE",
}


class InvoiceMatchPredictor:
    """Predicts invoice three-way match outcome.

    Loads a trained model and applies the feature pipeline to generate
    predictions with probabilities and explanations.
    """

    def __init__(self, model_path: str | Path):
        """Initialize predictor with a saved model.

        Args:
            model_path: Path to joblib-saved model artifact.
        """
        artifact = joblib.load(model_path)
        self.model = artifact["model"]
        self.feature_columns = artifact["feature_columns"]
        self.target = artifact.get("target", "binary")
        self.model_name = artifact.get("model_name", "unknown")
        self.label_map = LABEL_MAP_BINARY if self.target == "binary" else LABEL_MAP_MULTICLASS

    def predict(
        self,
        invoice_data: dict,
        tables: dict[str, pd.DataFrame],
    ) -> dict:
        """Predict match outcome for a single invoice.

        Args:
            invoice_data: Dictionary with invoice fields.
            tables: Full table dictionary for feature computation.

        Returns:
            Dictionary with predicted_class, probability, confidence, top_features.
        """
        # Build features for all invoices (inference mode: no LOO)
        feature_df = build_uc02_features(tables, leave_one_out=False)

        # Filter to the target invoice
        inv_id = invoice_data.get("invoice_id")
        row = feature_df[feature_df["invoice_id"] == inv_id]
        if row.empty:
            raise ValueError(f"Invoice {inv_id} not found in feature matrix")

        X, _ = prepare_feature_matrix(row, target=self.target)

        # Align columns
        X = self._align_columns(X)

        # Predict
        pred_class = int(self.model.predict(X)[0])
        pred_proba = self.model.predict_proba(X)[0]

        # Top feature contributions (from model feature importances)
        top_features = self._get_top_features(X, n=5)

        return {
            "invoice_id": inv_id,
            "predicted_class": self.label_map.get(pred_class, str(pred_class)),
            "probability": float(pred_proba[pred_class]),
            "confidence": "HIGH" if pred_proba[pred_class] > 0.8 else
                         "MEDIUM" if pred_proba[pred_class] > 0.6 else "LOW",
            "class_probabilities": {
                self.label_map.get(i, str(i)): float(p) for i, p in enumerate(pred_proba)
            },
            "top_features": top_features,
        }

    def predict_batch(
        self,
        tables: dict[str, pd.DataFrame],
        invoice_ids: list[str] | None = None,
    ) -> pd.DataFrame:
        """Score multiple invoices.

        Args:
            tables: Full table dictionary for feature computation.
            invoice_ids: Optional list of invoice IDs to score.
                        If None, scores all invoices.

        Returns:
            DataFrame with invoice_id, predicted_class, probability columns.
        """
        feature_df = build_uc02_features(tables, leave_one_out=False)

        if invoice_ids:
            feature_df = feature_df[feature_df["invoice_id"].isin(invoice_ids)]

        inv_ids = feature_df["invoice_id"].values
        X, _ = prepare_feature_matrix(feature_df, target=self.target)
        X = self._align_columns(X)

        predictions = self.model.predict(X)
        probabilities = self.model.predict_proba(X)

        results = pd.DataFrame({
            "invoice_id": inv_ids,
            "predicted_class": [self.label_map.get(int(p), str(p)) for p in predictions],
            "probability": [float(probabilities[i][int(predictions[i])]) for i in range(len(predictions))],
            "variance_probability": [
                float(probabilities[i][1]) if self.target == "binary" else
                float(1.0 - probabilities[i][0])
                for i in range(len(predictions))
            ],
        })

        return results.sort_values("variance_probability", ascending=False).reset_index(drop=True)

    def _align_columns(self, X: pd.DataFrame) -> pd.DataFrame:
        """Align feature columns to match training order."""
        missing = set(self.feature_columns) - set(X.columns)
        for col in missing:
            X[col] = 0
        return X[self.feature_columns]

    def _get_top_features(self, X: pd.DataFrame, n: int = 5) -> list[dict]:
        """Get top feature contributions for a prediction."""
        if hasattr(self.model, "feature_importances_"):
            importances = self.model.feature_importances_
        elif hasattr(self.model, "named_steps") and hasattr(self.model.named_steps.get("lr", None), "coef_"):
            importances = np.abs(self.model.named_steps["lr"].coef_[0])
        else:
            return []

        feature_names = self.feature_columns
        top_idx = np.argsort(importances)[::-1][:n]

        return [
            {
                "feature": feature_names[i],
                "importance": float(importances[i]),
                "value": float(X.iloc[0, i]) if i < X.shape[1] else None,
            }
            for i in top_idx
        ]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Score invoices for match prediction")
    parser.add_argument("--model", required=True, help="Path to saved model")
    parser.add_argument("--csv-dir", default="output/csv", help="Path to CSV data")
    parser.add_argument("--invoice-id", help="Single invoice ID to score")
    args = parser.parse_args()

    from ml.common.db_config import load_tables
    from ml.data_processing.python.uc02_preprocessing import UC02_TABLES

    predictor = InvoiceMatchPredictor(args.model)
    tables = load_tables("csv", UC02_TABLES, csv_dir=args.csv_dir)

    if args.invoice_id:
        result = predictor.predict({"invoice_id": args.invoice_id}, tables)
        print(f"\nInvoice: {result['invoice_id']}")
        print(f"Prediction: {result['predicted_class']} ({result['probability']:.1%})")
        print(f"Confidence: {result['confidence']}")
    else:
        results = predictor.predict_batch(tables)
        print(f"\nScored {len(results)} invoices")
        print(results.head(10).to_string(index=False))

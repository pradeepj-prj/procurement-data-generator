"""UC-02 Invoice Three-Way Match — Feature engineering functions.

Standalone .py copy of 02_feature_engineering.ipynb for reuse in
training pipelines and inference.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ml.common.db_config import load_tables
from ml.common.feature_store import (
    compute_price_benchmarks,
    compute_vendor_composite_profile,
    compute_vendor_historical_performance,
    compute_vendor_invoice_behavior,
    compute_vendor_invoice_behavior_loo,
)
from ml.common.utils import (
    CONFIDENTIALITY_MAP,
    CRITICALITY_MAP,
    convert_to_usd,
    encode_ordinal,
)
from ml.data_processing.python.uc02_preprocessing import (
    UC02_TABLES,
    build_uc02_base_dataset,
    add_temporal_features,
    load_uc02_raw_data,
)


# Columns that leak the target — must never appear in feature matrix
LEAKAGE_COLUMNS = [
    "price_variance", "quantity_variance", "payment_block", "block_reason",
    "status", "unit_price_invoiced", "quantity_invoiced",
    "total_gross_amount", "tax_amount", "total_net_amount", "net_amount",
]

# ID columns to drop before training
ID_COLUMNS = [
    "invoice_id", "po_id", "vendor_id", "material_id", "gr_id",
    "contract_id", "category_id", "invoice_line_number", "po_line_number",
    "gr_line_number", "contract_item_number", "vendor_invoice_number",
]

# Final feature columns (populated after first run; order matters for inference)
FEATURE_COLUMNS = None  # Set dynamically by prepare_feature_matrix


def compute_uc02_specific_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute UC-02 specific features from the joined base dataset.

    Args:
        df: Base dataset from build_uc02_base_dataset + temporal features.

    Returns:
        DataFrame with UC-02 features added.
    """
    df = df.copy()

    # Contract coverage
    if "contract_id" in df.columns:
        df["uc02_is_contract_po"] = df["contract_id"].notna().astype(int)
    else:
        df["uc02_is_contract_po"] = 0

    # GR quantity vs PO quantity ratio
    if "quantity_received" in df.columns and "quantity" in df.columns:
        df["uc02_gr_qty_vs_po_qty"] = np.where(
            df["quantity"] > 0,
            df["quantity_received"] / df["quantity"],
            np.nan,
        )
    else:
        df["uc02_gr_qty_vs_po_qty"] = np.nan

    # GR has rejection
    if "quantity_rejected" in df.columns:
        df["uc02_gr_has_rejection"] = (
            pd.to_numeric(df["quantity_rejected"], errors="coerce").fillna(0) > 0
        ).astype(int)
    else:
        df["uc02_gr_has_rejection"] = 0

    # Days from GR to invoice
    if "gr_date" in df.columns and "invoice_date" in df.columns:
        gr_dt = pd.to_datetime(df["gr_date"])
        inv_dt = pd.to_datetime(df["invoice_date"])
        df["uc02_days_gr_to_invoice"] = (inv_dt - gr_dt).dt.days
    else:
        df["uc02_days_gr_to_invoice"] = np.nan

    # Maverick PO
    if "maverick_flag" in df.columns:
        df["uc02_is_maverick_po"] = df["maverick_flag"].astype(int)
    else:
        df["uc02_is_maverick_po"] = 0

    # Rush PO
    if "po_type" in df.columns:
        df["uc02_po_type_rush"] = (df["po_type"] == "RUSH").astype(int)
    else:
        df["uc02_po_type_rush"] = 0

    # Price vs standard cost
    if "unit_price" in df.columns and "standard_cost" in df.columns:
        std_cost = pd.to_numeric(df["standard_cost"], errors="coerce")
        unit_price = pd.to_numeric(df["unit_price"], errors="coerce")
        df["uc02_price_vs_standard"] = np.where(
            std_cost > 0, unit_price / std_cost, np.nan,
        )
    else:
        df["uc02_price_vs_standard"] = np.nan

    # Delivery delay days
    if "actual_delivery_date" in df.columns and "requested_delivery_date" in df.columns:
        actual = pd.to_datetime(df["actual_delivery_date"])
        requested = pd.to_datetime(df["requested_delivery_date"])
        df["uc02_delivery_delay_days"] = (actual - requested).dt.days
    else:
        df["uc02_delivery_delay_days"] = np.nan

    # Material criticality ordinal
    if "criticality" in df.columns:
        df["uc02_material_criticality"] = encode_ordinal(df["criticality"], CRITICALITY_MAP)
    else:
        df["uc02_material_criticality"] = 0

    # GR quality hold status
    if "gr_status" in df.columns:
        df["uc02_gr_status_quality_hold"] = (df["gr_status"] == "QUALITY_HOLD").astype(int)
    else:
        df["uc02_gr_status_quality_hold"] = 0

    # PO amount in USD
    if "total_net_value" in df.columns and "currency" in df.columns:
        df["uc02_amount_usd"] = convert_to_usd(
            pd.to_numeric(df["total_net_value"], errors="coerce"),
            df["currency"],
        )
    else:
        df["uc02_amount_usd"] = np.nan

    # Hazmat flag
    if "hazmat_flag" in df.columns:
        df["uc02_hazmat_flag"] = df["hazmat_flag"].astype(int)
    else:
        df["uc02_hazmat_flag"] = 0

    # Confidentiality ordinal
    if "confidentiality_tier" in df.columns:
        df["uc02_confidentiality"] = encode_ordinal(
            df["confidentiality_tier"], CONFIDENTIALITY_MAP
        )

    return df


def _compute_vendor_invoice_seq(df: pd.DataFrame) -> pd.Series:
    """Compute sequential invoice number per vendor ordered by date.

    Args:
        df: Dataset with vendor_id and invoice_date columns.

    Returns:
        Series with sequential invoice count per vendor.
    """
    df_sorted = df.sort_values(["vendor_id", "invoice_date"])
    return df_sorted.groupby("vendor_id").cumcount() + 1


def build_uc02_features(
    tables: dict[str, pd.DataFrame],
    leave_one_out: bool = True,
) -> pd.DataFrame:
    """Master function: build complete UC-02 feature matrix.

    Args:
        tables: Dictionary of table_name -> DataFrame.
        leave_one_out: If True, use LOO for vendor invoice behavior (training).
                       If False, use full history (inference).

    Returns:
        Feature matrix with target columns, indexed by invoice_id.
    """
    # 1. Build base dataset
    df = build_uc02_base_dataset(tables)
    df = add_temporal_features(df)

    # Store invoice_id and match_status before they might get lost
    invoice_ids = df["invoice_id"].copy()
    match_status = df["match_status"].copy()

    # 2. Vendor composite profile
    vendor_profile = compute_vendor_composite_profile(
        tables["vendor_master"],
        tables.get("vendor_category"),
    )
    df = df.merge(vendor_profile, on="vendor_id", how="left")

    # 3. Vendor historical performance
    vendor_perf = compute_vendor_historical_performance(
        tables["po_header"],
        tables["po_line_item"],
        tables.get("gr_header"),
        tables.get("gr_line_item"),
    )
    df = df.merge(vendor_perf, on="vendor_id", how="left")

    # 4. Vendor invoice behavior (LOO or full)
    if leave_one_out:
        vendor_inv_loo = compute_vendor_invoice_behavior_loo(
            tables["invoice_header"],
            tables.get("invoice_line_item"),
        )
        df = df.merge(vendor_inv_loo, on="invoice_id", how="left")
    else:
        vendor_inv = compute_vendor_invoice_behavior(
            tables["invoice_header"],
            tables.get("invoice_line_item"),
        )
        df = df.merge(vendor_inv, on="vendor_id", how="left")
        # Rename to match LOO column names
        rename_map = {
            "v_invoice_match_rate": "v_invoice_match_rate_loo",
            "v_price_variance_rate": "v_price_variance_rate_loo",
            "v_qty_variance_rate": "v_qty_variance_rate_loo",
            "v_avg_price_variance_pct": "v_avg_price_variance_pct_loo",
        }
        df = df.rename(columns=rename_map)

    # 5. Price benchmarks
    price_bench = compute_price_benchmarks(
        tables["po_line_item"],
        tables["material_master"],
        tables.get("contract_item"),
    )
    merge_keys = ["po_id", "po_line_number", "material_id"]
    price_cols = [c for c in price_bench.columns if c.startswith("p_")]
    df = df.merge(
        price_bench[merge_keys + price_cols],
        on=merge_keys,
        how="left",
    )

    # 6. UC-02 specific features
    df = compute_uc02_specific_features(df)

    # 7. Vendor raw scores (from vendor_master directly)
    vendor_scores = tables["vendor_master"][
        ["vendor_id", "quality_score", "risk_score", "on_time_delivery_rate", "esg_score"]
    ].copy()
    vendor_scores = vendor_scores.rename(columns={
        "quality_score": "uc02_vendor_quality_score",
        "risk_score": "uc02_vendor_risk_score",
        "on_time_delivery_rate": "uc02_vendor_otd_rate",
        "esg_score": "uc02_vendor_esg_score",
    })
    df = df.merge(vendor_scores, on="vendor_id", how="left")

    # 8. Vendor invoice sequence
    df["uc02_vendor_invoice_seq"] = _compute_vendor_invoice_seq(df)

    # 9. Label engineering
    df["match_status"] = match_status.values
    df["target_binary"] = (df["match_status"] != "FULL_MATCH").astype(int)
    df["target_multiclass"] = df["match_status"].map({
        "FULL_MATCH": 0,
        "PRICE_VARIANCE": 1,
        "QUANTITY_VARIANCE": 2,
        "BOTH_VARIANCE": 3,
    })

    # Ensure invoice_id is preserved
    df["invoice_id"] = invoice_ids.values

    return df


def prepare_feature_matrix(
    df: pd.DataFrame,
    target: str = "binary",
) -> tuple[pd.DataFrame, pd.Series]:
    """Prepare final feature matrix X and target y.

    Drops ID columns, leakage columns, target columns, and non-numeric columns.
    Fills remaining NaN with 0.

    Args:
        df: Full feature DataFrame from build_uc02_features.
        target: "binary" or "multiclass".

    Returns:
        Tuple of (X, y) where X is the feature matrix and y is the target.
    """
    global FEATURE_COLUMNS

    target_col = "target_binary" if target == "binary" else "target_multiclass"
    y = df[target_col].copy()

    # Columns to drop
    drop_cols = set(ID_COLUMNS + LEAKAGE_COLUMNS + [
        "match_status", "target_binary", "target_multiclass",
        # Date columns (not directly usable as features)
        "invoice_date", "received_date", "po_date", "gr_date",
        "payment_due_date", "requested_delivery_date", "actual_delivery_date",
        "valid_from", "valid_to",
        # Categorical strings (already encoded)
        "po_type", "incoterms", "payment_terms", "material_type",
        "criticality", "make_or_buy", "confidentiality_tier",
        "gr_status", "rejection_reason", "contract_type",
    ])

    feature_cols = [c for c in df.columns if c not in drop_cols]
    X = df[feature_cols].copy()

    # Convert any remaining object columns to numeric or drop
    for col in X.select_dtypes(include=["object", "category"]).columns:
        X[col] = pd.to_numeric(X[col], errors="coerce")

    # Convert boolean columns
    for col in X.select_dtypes(include=["boolean", "bool"]).columns:
        X[col] = X[col].astype(int)

    # Fill NaN
    X = X.fillna(0)

    FEATURE_COLUMNS = list(X.columns)
    return X, y

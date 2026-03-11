"""UC-02 Invoice Three-Way Match — Pandas preprocessing.

Builds the base dataset by joining 10+ tables and dropping leakage columns.
Equivalent to ml/data_processing/sql/uc02_preprocessing.sql.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ml.common.db_config import load_tables
from ml.common.feature_store import compute_vendor_composite_profile

# Tables required for UC-02
UC02_TABLES = [
    "invoice_header",
    "invoice_line_item",
    "po_header",
    "po_line_item",
    "gr_header",
    "gr_line_item",
    "vendor_master",
    "vendor_category",
    "material_master",
    "contract_header",
    "contract_item",
]

# Columns that leak the target variable — MUST be excluded from features
LEAKAGE_COLUMNS = [
    # Direct label / label derivatives
    "price_variance",
    "quantity_variance",
    "payment_block",
    "block_reason",
    "match_status",          # raw label (kept temporarily for target creation)
    # Invoice-originated amounts (not available pre-receipt in Mode A)
    "unit_price_invoiced",
    "quantity_invoiced",
    "total_gross_amount",
    "tax_amount",
    "total_net_amount",
    "net_amount",            # invoice line net_amount
    # Status derived from variance
    "status",                # invoice status (EXCEPTION = variance)
]


def load_uc02_raw_data(
    source: str = "csv",
    csv_dir: str | Path = "output/csv",
    conn=None,
) -> dict[str, pd.DataFrame]:
    """Load all tables needed for UC-02.

    Args:
        source: "csv" or "postgres".
        csv_dir: Path to CSV directory.
        conn: Postgres connection (if source="postgres").

    Returns:
        Dictionary of table_name -> DataFrame.
    """
    return load_tables(source, UC02_TABLES, csv_dir=csv_dir, conn=conn)


def build_uc02_base_dataset(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Build the UC-02 base dataset from multi-table joins.

    Joins: invoice_header → invoice_line_item → po_header → po_line_item
           → gr_header → gr_line_item → material_master → contract tables.

    Drops leakage columns but keeps match_status for target creation.

    Args:
        tables: Dictionary of loaded DataFrames.

    Returns:
        Base dataset with ~320 rows (one per invoice line item).
    """
    inv_h = tables["invoice_header"]
    inv_l = tables["invoice_line_item"]
    po_h = tables["po_header"]
    po_l = tables["po_line_item"]
    gr_h = tables["gr_header"]
    gr_l = tables["gr_line_item"]
    mat = tables["material_master"]
    con_h = tables["contract_header"]
    con_i = tables["contract_item"]

    # Start from invoice line items joined to invoice header
    df = inv_l.merge(
        inv_h[["invoice_id", "invoice_date", "received_date", "vendor_id", "po_id",
               "currency", "match_status", "payment_due_date"]],
        on="invoice_id",
        how="inner",
        suffixes=("", "_header"),
    )

    # Join PO header
    po_h_cols = ["po_id", "po_date", "po_type", "incoterms", "payment_terms",
                 "total_net_value", "maverick_flag"]
    df = df.merge(
        po_h[po_h_cols],
        on="po_id",
        how="inner",
        suffixes=("", "_po"),
    )

    # Join PO line items
    po_l_cols = ["po_id", "po_line_number", "material_id", "quantity", "unit_price",
                 "requested_delivery_date", "actual_delivery_date",
                 "contract_id", "contract_item_number"]
    df = df.merge(
        po_l[po_l_cols],
        on=["po_id", "po_line_number"],
        how="inner",
        suffixes=("", "_po_line"),
    )

    # Join GR header + line items (left join — some invoices may not have GR)
    if "gr_id" in df.columns:
        gr_h_cols = ["gr_id", "gr_date", "status"]
        df = df.merge(
            gr_h[gr_h_cols].rename(columns={"status": "gr_status"}),
            on="gr_id",
            how="left",
        )

        gr_l_cols = ["gr_id", "gr_line_number", "quantity_received",
                     "quantity_accepted", "quantity_rejected", "rejection_reason"]
        df = df.merge(
            gr_l[gr_l_cols],
            on=["gr_id", "gr_line_number"],
            how="left",
        )

    # Join material master
    mat_cols = ["material_id", "material_type", "category_id", "standard_cost",
                "criticality", "hazmat_flag", "default_lead_time_days", "make_or_buy",
                "confidentiality_tier"]
    df = df.merge(
        mat[mat_cols],
        on="material_id",
        how="left",
        suffixes=("", "_mat"),
    )

    # Join contract header (left join — not all POs have contracts)
    if "contract_id" in df.columns:
        con_h_cols = ["contract_id", "contract_type", "valid_from", "valid_to"]
        df = df.merge(
            con_h[con_h_cols],
            on="contract_id",
            how="left",
        )

        # Join contract item for agreed price
        if "contract_item_number" in df.columns:
            con_i_cols = ["contract_id", "item_number", "agreed_price"]
            df = df.merge(
                con_i[con_i_cols].rename(columns={"item_number": "contract_item_number"}),
                on=["contract_id", "contract_item_number"],
                how="left",
            )

    # Drop leakage columns (except match_status — needed for target)
    drop_cols = [c for c in LEAKAGE_COLUMNS if c in df.columns and c != "match_status"]
    df = df.drop(columns=drop_cols, errors="ignore")

    return df


def add_vendor_features(
    df: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Merge vendor composite profile features onto the base dataset.

    Args:
        df: Base dataset with vendor_id column.
        tables: Dictionary of loaded DataFrames (needs vendor_master, vendor_category).

    Returns:
        Dataset with vendor profile columns added.
    """
    vendor_profile = compute_vendor_composite_profile(
        tables["vendor_master"],
        tables.get("vendor_category"),
    )
    return df.merge(vendor_profile, on="vendor_id", how="left")


def add_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add temporal features derived from dates.

    Features:
        - invoice_month, invoice_quarter
        - days_po_to_invoice: business days from PO to invoice
        - days_gr_to_invoice: calendar days from GR to invoice

    Args:
        df: Dataset with date columns.

    Returns:
        Dataset with temporal features added.
    """
    df = df.copy()

    invoice_date = pd.to_datetime(df["invoice_date"])
    df["invoice_month"] = invoice_date.dt.month
    df["invoice_quarter"] = invoice_date.dt.quarter

    if "po_date" in df.columns:
        po_date = pd.to_datetime(df["po_date"])
        df["days_po_to_invoice"] = (invoice_date - po_date).dt.days

    if "gr_date" in df.columns:
        gr_date = pd.to_datetime(df["gr_date"])
        df["days_gr_to_invoice"] = (invoice_date - gr_date).dt.days

    return df

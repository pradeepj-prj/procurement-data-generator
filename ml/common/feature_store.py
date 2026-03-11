"""Shared feature computation groups for ML use cases.

Implements the feature store definitions from docs/ML_USE_CASES.md Section 3:
- Vendor Composite Profile (3.1)
- Vendor Historical Performance (3.2)
- Vendor Invoice Behavior (3.3) — with leave-one-out support
- Price Benchmarks (3.5)
"""

import numpy as np
import pandas as pd

from ml.common.utils import (
    CONFIDENTIALITY_MAP,
    COUNTRY_RISK_MAP,
    CRITICALITY_MAP,
    PAYMENT_TERMS_DAYS,
    VENDOR_STATUS_MAP,
    VENDOR_TYPE_MAP,
    convert_to_usd,
    encode_ordinal,
)


def compute_vendor_composite_profile(
    vendor_master: pd.DataFrame,
    vendor_category: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Compute vendor composite profile features (Feature Store 3.1).

    Args:
        vendor_master: vendor_master table.
        vendor_category: vendor_category table (optional, for category count).

    Returns:
        DataFrame indexed by vendor_id with profile features.
    """
    df = vendor_master[["vendor_id"]].copy()

    # Vendor type one-hot encoding
    for vtype, code in VENDOR_TYPE_MAP.items():
        df[f"v_type_{vtype.lower()}"] = (vendor_master["vendor_type"] == vtype).astype(int)

    df["v_preferred"] = vendor_master["preferred_flag"].astype(int)
    df["v_status_encoded"] = encode_ordinal(vendor_master["status"], VENDOR_STATUS_MAP)
    df["v_country_risk"] = encode_ordinal(vendor_master["country"], COUNTRY_RISK_MAP)
    df["v_payment_terms_days"] = vendor_master["payment_terms"].map(PAYMENT_TERMS_DAYS).fillna(30).astype(int)
    df["v_has_early_discount"] = (vendor_master["payment_terms"] == "2/10NET30").astype(int)
    df["v_confidentiality_ordinal"] = encode_ordinal(
        vendor_master["confidentiality_tier"], CONFIDENTIALITY_MAP
    )

    # Category count from vendor_category table
    if vendor_category is not None and not vendor_category.empty:
        cat_counts = vendor_category.groupby("vendor_id").size().reset_index(name="v_category_count")
        df = df.merge(cat_counts, on="vendor_id", how="left")
        df["v_category_count"] = df["v_category_count"].fillna(0).astype(int)
    else:
        df["v_category_count"] = 1

    return df.set_index("vendor_id")


def compute_vendor_historical_performance(
    po_header: pd.DataFrame,
    po_line_item: pd.DataFrame,
    gr_header: pd.DataFrame | None = None,
    gr_line_item: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Compute vendor historical performance features (Feature Store 3.2).

    Args:
        po_header: po_header table.
        po_line_item: po_line_item table.
        gr_header: gr_header table (optional, for delivery metrics).
        gr_line_item: gr_line_item table (optional, for rejection rate).

    Returns:
        DataFrame indexed by vendor_id with performance features.
    """
    # PO-level aggregations
    po_agg = po_header.groupby("vendor_id").agg(
        v_total_po_count=("po_id", "count"),
        v_total_po_value=("total_net_value", "sum"),
        v_avg_po_value=("total_net_value", "mean"),
    ).reset_index()

    # Distinct materials per vendor
    po_with_lines = po_header[["po_id", "vendor_id"]].merge(
        po_line_item[["po_id", "material_id"]], on="po_id", how="inner"
    )
    mat_counts = po_with_lines.groupby("vendor_id")["material_id"].nunique().reset_index(
        name="v_distinct_materials"
    )
    po_agg = po_agg.merge(mat_counts, on="vendor_id", how="left")
    po_agg["v_distinct_materials"] = po_agg["v_distinct_materials"].fillna(0).astype(int)

    # Delivery performance from PO line items
    delivery_df = po_line_item.dropna(subset=["actual_delivery_date", "requested_delivery_date"]).copy()
    if not delivery_df.empty:
        delivery_df["delay_days"] = (
            pd.to_datetime(delivery_df["actual_delivery_date"])
            - pd.to_datetime(delivery_df["requested_delivery_date"])
        ).dt.days
        delivery_df["on_time"] = (delivery_df["delay_days"] <= 0).astype(int)

        # Join to get vendor_id
        delivery_df = delivery_df.merge(
            po_header[["po_id", "vendor_id"]], on="po_id", how="inner"
        )
        delivery_agg = delivery_df.groupby("vendor_id").agg(
            v_on_time_delivery_actual=("on_time", "mean"),
            v_avg_delivery_delay_days=("delay_days", "mean"),
        ).reset_index()
        po_agg = po_agg.merge(delivery_agg, on="vendor_id", how="left")
    else:
        po_agg["v_on_time_delivery_actual"] = np.nan
        po_agg["v_avg_delivery_delay_days"] = np.nan

    # Rejection rate from GR data
    if gr_line_item is not None and gr_header is not None and not gr_line_item.empty:
        gr_with_vendor = gr_line_item.merge(
            gr_header[["gr_id", "po_id"]], on="gr_id", how="inner"
        ).merge(
            po_header[["po_id", "vendor_id"]], on="po_id", how="inner"
        )
        rej_agg = gr_with_vendor.groupby("vendor_id").agg(
            total_received=("quantity_received", "sum"),
            total_rejected=("quantity_rejected", "sum"),
        ).reset_index()
        rej_agg["v_rejection_rate"] = np.where(
            rej_agg["total_received"] > 0,
            rej_agg["total_rejected"] / rej_agg["total_received"],
            0.0,
        )
        po_agg = po_agg.merge(
            rej_agg[["vendor_id", "v_rejection_rate"]], on="vendor_id", how="left"
        )
    else:
        po_agg["v_rejection_rate"] = np.nan

    po_agg = po_agg.fillna({
        "v_on_time_delivery_actual": 0.5,
        "v_avg_delivery_delay_days": 0.0,
        "v_rejection_rate": 0.0,
    })

    return po_agg.set_index("vendor_id")


def compute_vendor_invoice_behavior(
    invoice_header: pd.DataFrame,
    invoice_line_item: pd.DataFrame | None = None,
    exclude_invoice_ids: set | None = None,
) -> pd.DataFrame:
    """Compute vendor invoice behavior features (Feature Store 3.3).

    Args:
        invoice_header: invoice_header table.
        invoice_line_item: invoice_line_item table (optional, for variance details).
        exclude_invoice_ids: Set of invoice_ids to exclude (for leave-one-out).

    Returns:
        DataFrame indexed by vendor_id with invoice behavior features.
    """
    df = invoice_header.copy()
    if exclude_invoice_ids:
        df = df[~df["invoice_id"].isin(exclude_invoice_ids)]

    if df.empty:
        return pd.DataFrame(columns=[
            "v_invoice_match_rate", "v_price_variance_rate",
            "v_qty_variance_rate", "v_payment_block_rate",
        ]).rename_axis("vendor_id")

    # Per-vendor aggregations
    vendor_groups = df.groupby("vendor_id")

    result = pd.DataFrame()
    result["v_invoice_count"] = vendor_groups["invoice_id"].count()
    result["v_invoice_match_rate"] = vendor_groups["match_status"].apply(
        lambda s: (s == "FULL_MATCH").mean()
    )
    result["v_price_variance_rate"] = vendor_groups["match_status"].apply(
        lambda s: s.isin(["PRICE_VARIANCE", "BOTH_VARIANCE"]).mean()
    )
    result["v_qty_variance_rate"] = vendor_groups["match_status"].apply(
        lambda s: s.isin(["QUANTITY_VARIANCE", "BOTH_VARIANCE"]).mean()
    )
    result["v_payment_block_rate"] = vendor_groups["payment_block"].mean()

    # Average price variance from line items
    if invoice_line_item is not None and not invoice_line_item.empty:
        li = invoice_line_item.copy()
        if exclude_invoice_ids:
            li = li[~li["invoice_id"].isin(exclude_invoice_ids)]

        if not li.empty and "price_variance" in li.columns:
            # Compute percentage variance relative to invoiced price
            li["abs_price_var_pct"] = np.where(
                li["unit_price_invoiced"] > 0,
                np.abs(li["price_variance"]) / li["unit_price_invoiced"],
                0.0,
            )
            li_with_vendor = li.merge(
                invoice_header[["invoice_id", "vendor_id"]], on="invoice_id", how="inner"
            )
            var_agg = li_with_vendor.groupby("vendor_id")["abs_price_var_pct"].mean()
            result["v_avg_price_variance_pct"] = var_agg
        else:
            result["v_avg_price_variance_pct"] = 0.0
    else:
        result["v_avg_price_variance_pct"] = 0.0

    result["v_avg_price_variance_pct"] = result["v_avg_price_variance_pct"].fillna(0.0)

    return result


def compute_vendor_invoice_behavior_loo(
    invoice_header: pd.DataFrame,
    invoice_line_item: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Compute leave-one-out vendor invoice behavior for each invoice.

    For each invoice, computes vendor stats excluding that invoice.
    Vendors with only 1 invoice get global average (cold-start).

    Args:
        invoice_header: invoice_header table.
        invoice_line_item: invoice_line_item table (optional).

    Returns:
        DataFrame indexed by invoice_id with LOO vendor features.
    """
    # Compute global averages for cold-start
    global_stats = compute_vendor_invoice_behavior(invoice_header, invoice_line_item)
    global_avg = {
        "v_invoice_match_rate_loo": global_stats["v_invoice_match_rate"].mean(),
        "v_price_variance_rate_loo": global_stats["v_price_variance_rate"].mean(),
        "v_qty_variance_rate_loo": global_stats["v_qty_variance_rate"].mean(),
        "v_avg_price_variance_pct_loo": global_stats["v_avg_price_variance_pct"].mean(),
    }

    # Compute per-vendor invoice counts
    vendor_inv_counts = invoice_header.groupby("vendor_id")["invoice_id"].count()

    results = []
    for _, row in invoice_header.iterrows():
        inv_id = row["invoice_id"]
        vendor_id = row["vendor_id"]

        if vendor_inv_counts.get(vendor_id, 0) <= 1:
            # Cold-start: use global averages
            rec = {"invoice_id": inv_id, **global_avg}
        else:
            # LOO: exclude this invoice
            loo_stats = compute_vendor_invoice_behavior(
                invoice_header, invoice_line_item,
                exclude_invoice_ids={inv_id},
            )
            if vendor_id in loo_stats.index:
                vendor_row = loo_stats.loc[vendor_id]
                rec = {
                    "invoice_id": inv_id,
                    "v_invoice_match_rate_loo": vendor_row["v_invoice_match_rate"],
                    "v_price_variance_rate_loo": vendor_row["v_price_variance_rate"],
                    "v_qty_variance_rate_loo": vendor_row["v_qty_variance_rate"],
                    "v_avg_price_variance_pct_loo": vendor_row["v_avg_price_variance_pct"],
                }
            else:
                rec = {"invoice_id": inv_id, **global_avg}

        results.append(rec)

    return pd.DataFrame(results).set_index("invoice_id")


def compute_price_benchmarks(
    po_line_item: pd.DataFrame,
    material_master: pd.DataFrame,
    contract_item: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Compute price benchmark features (Feature Store 3.5).

    Args:
        po_line_item: po_line_item table.
        material_master: material_master table.
        contract_item: contract_item table (optional).

    Returns:
        DataFrame indexed by (material_id, po_id, po_line_number) with price features.
    """
    df = po_line_item[["po_id", "po_line_number", "material_id", "unit_price"]].copy()

    # Material-level price statistics
    mat_price_stats = po_line_item.groupby("material_id")["unit_price"].agg(
        p_avg_unit_price="mean",
        p_std_unit_price="std",
        p_min_unit_price="min",
        p_max_unit_price="max",
    ).reset_index()
    mat_price_stats["p_std_unit_price"] = mat_price_stats["p_std_unit_price"].fillna(0.0)

    df = df.merge(mat_price_stats, on="material_id", how="left")

    # Price-to-standard ratio
    std_costs = material_master[["material_id", "standard_cost"]].copy()
    std_costs["standard_cost"] = pd.to_numeric(std_costs["standard_cost"], errors="coerce")
    df = df.merge(std_costs, on="material_id", how="left")
    df["p_price_to_standard_ratio"] = np.where(
        df["standard_cost"] > 0,
        df["unit_price"] / df["standard_cost"],
        np.nan,
    )

    # Contract price
    if contract_item is not None and not contract_item.empty:
        contract_prices = contract_item[["material_id", "agreed_price"]].copy()
        contract_prices["agreed_price"] = pd.to_numeric(contract_prices["agreed_price"], errors="coerce")
        # Take min agreed price per material (best contract price)
        contract_prices = contract_prices.groupby("material_id")["agreed_price"].min().reset_index(
            name="p_contract_price"
        )
        df = df.merge(contract_prices, on="material_id", how="left")
    else:
        df["p_contract_price"] = np.nan

    # Clean up — drop intermediate columns
    df = df.drop(columns=["standard_cost"], errors="ignore")

    return df

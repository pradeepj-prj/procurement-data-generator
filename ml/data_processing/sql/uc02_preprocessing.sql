-- UC-02 Invoice Three-Way Match — Preprocessing Query
-- Joins invoice data with PO, GR, material, vendor, and contract tables.
-- Explicitly excludes leakage columns.
-- Requires feature_store_views.sql to be run first.

WITH base AS (
    SELECT
        -- Invoice identifiers
        ih.invoice_id,
        ih.invoice_date,
        ih.received_date,
        ih.vendor_id,
        ih.po_id,
        ih.currency,
        ih.payment_due_date,
        ih.match_status,                -- kept for target creation only

        -- Invoice line (non-leakage fields only)
        il.invoice_line_number,
        il.po_line_number,
        il.material_id,
        il.gr_id,
        il.gr_line_number,

        -- EXCLUDED (leakage):
        --   il.unit_price_invoiced, il.quantity_invoiced, il.net_amount
        --   il.price_variance, il.quantity_variance
        --   ih.total_gross_amount, ih.tax_amount, ih.total_net_amount
        --   ih.status, ih.payment_block, ih.block_reason

        -- PO header
        ph.po_date,
        ph.po_type,
        ph.incoterms,
        ph.payment_terms,
        ph.total_net_value AS po_total_net_value,
        ph.maverick_flag,

        -- PO line item
        pl.quantity AS po_quantity,
        pl.unit_price AS po_unit_price,
        pl.requested_delivery_date,
        pl.actual_delivery_date,
        pl.contract_id,
        pl.contract_item_number,

        -- GR header
        gh.gr_date,
        gh.status AS gr_status,

        -- GR line item
        gl.quantity_received,
        gl.quantity_accepted,
        gl.quantity_rejected,
        gl.rejection_reason,

        -- Material master
        mm.material_type,
        mm.category_id,
        mm.standard_cost,
        mm.criticality,
        mm.hazmat_flag,
        mm.default_lead_time_days,
        mm.make_or_buy,
        mm.confidentiality_tier AS material_confidentiality,

        -- Contract header
        ch.contract_type,
        ch.valid_from AS contract_valid_from,
        ch.valid_to AS contract_valid_to,

        -- Contract item
        ci.agreed_price AS contract_agreed_price

    FROM procurement.invoice_header ih
    JOIN procurement.invoice_line_item il ON ih.invoice_id = il.invoice_id
    JOIN procurement.po_header ph ON ih.po_id = ph.po_id
    JOIN procurement.po_line_item pl
        ON il.po_id = pl.po_id AND il.po_line_number = pl.po_line_number
    LEFT JOIN procurement.gr_header gh ON il.gr_id = gh.gr_id
    LEFT JOIN procurement.gr_line_item gl
        ON il.gr_id = gl.gr_id AND il.gr_line_number = gl.gr_line_number
    LEFT JOIN procurement.material_master mm ON il.material_id = mm.material_id
    LEFT JOIN procurement.contract_header ch ON pl.contract_id = ch.contract_id
    LEFT JOIN procurement.contract_item ci
        ON pl.contract_id = ci.contract_id
        AND pl.contract_item_number = ci.item_number
),
with_features AS (
    SELECT
        b.*,

        -- Temporal features
        EXTRACT(MONTH FROM b.invoice_date) AS invoice_month,
        EXTRACT(QUARTER FROM b.invoice_date) AS invoice_quarter,
        EXTRACT(DAY FROM b.invoice_date - b.po_date) AS days_po_to_invoice,
        EXTRACT(DAY FROM b.invoice_date - b.gr_date) AS days_gr_to_invoice,

        -- UC-02 specific features
        CASE WHEN b.contract_id IS NOT NULL THEN 1 ELSE 0 END AS uc02_is_contract_po,
        CASE WHEN b.po_quantity > 0
             THEN b.quantity_received / b.po_quantity
             ELSE NULL
        END AS uc02_gr_qty_vs_po_qty,
        CASE WHEN b.quantity_rejected > 0 THEN 1 ELSE 0 END AS uc02_gr_has_rejection,
        CASE WHEN b.maverick_flag THEN 1 ELSE 0 END AS uc02_is_maverick_po,
        CASE WHEN b.po_type = 'RUSH' THEN 1 ELSE 0 END AS uc02_po_type_rush,
        CASE WHEN b.standard_cost > 0
             THEN b.po_unit_price / b.standard_cost
             ELSE NULL
        END AS uc02_price_vs_standard,
        EXTRACT(DAY FROM b.actual_delivery_date - b.requested_delivery_date) AS uc02_delivery_delay_days,
        CASE b.criticality
            WHEN 'LOW' THEN 0 WHEN 'MEDIUM' THEN 1 WHEN 'HIGH' THEN 2
            ELSE -1
        END AS uc02_material_criticality,
        CASE WHEN b.gr_status = 'QUALITY_HOLD' THEN 1 ELSE 0 END AS uc02_gr_status_quality_hold,
        CASE WHEN b.hazmat_flag THEN 1 ELSE 0 END AS uc02_hazmat_flag,

        -- Target variables
        CASE WHEN b.match_status = 'FULL_MATCH' THEN 0 ELSE 1 END AS target_binary,
        CASE b.match_status
            WHEN 'FULL_MATCH' THEN 0
            WHEN 'PRICE_VARIANCE' THEN 1
            WHEN 'QUANTITY_VARIANCE' THEN 2
            WHEN 'BOTH_VARIANCE' THEN 3
        END AS target_multiclass,

        -- Vendor raw scores
        vm.quality_score AS uc02_vendor_quality_score,
        vm.risk_score AS uc02_vendor_risk_score,
        vm.on_time_delivery_rate AS uc02_vendor_otd_rate,
        vm.esg_score AS uc02_vendor_esg_score

    FROM base b
    LEFT JOIN procurement.vendor_master vm ON b.vendor_id = vm.vendor_id
)
SELECT
    wf.*,
    -- Vendor composite profile
    vcp.v_type_oem, vcp.v_type_distributor, vcp.v_type_contract_mfg,
    vcp.v_type_logistics, vcp.v_type_service,
    vcp.v_preferred, vcp.v_status_encoded, vcp.v_country_risk,
    vcp.v_payment_terms_days, vcp.v_has_early_discount,
    vcp.v_confidentiality_ordinal, vcp.v_category_count,
    -- Vendor historical performance
    vhp.v_total_po_count, vhp.v_total_po_value, vhp.v_avg_po_value,
    vhp.v_on_time_delivery_actual, vhp.v_avg_delivery_delay_days,
    vhp.v_rejection_rate, vhp.v_distinct_materials,
    -- Vendor invoice behavior (NOTE: no LOO in SQL — use with caution)
    vib.v_invoice_count, vib.v_invoice_match_rate,
    vib.v_price_variance_rate, vib.v_qty_variance_rate,
    vib.v_payment_block_rate, vib.v_avg_price_variance_pct,
    -- Price benchmarks
    pb.p_avg_unit_price, pb.p_std_unit_price,
    pb.p_price_to_standard_ratio, pb.p_contract_price
FROM with_features wf
LEFT JOIN procurement.mv_vendor_composite_profile vcp ON wf.vendor_id = vcp.vendor_id
LEFT JOIN procurement.mv_vendor_historical_performance vhp ON wf.vendor_id = vhp.vendor_id
LEFT JOIN procurement.mv_vendor_invoice_behavior vib ON wf.vendor_id = vib.vendor_id
LEFT JOIN procurement.mv_price_benchmarks pb
    ON wf.po_id = pb.po_id AND wf.po_line_number = pb.po_line_number
ORDER BY wf.invoice_id;

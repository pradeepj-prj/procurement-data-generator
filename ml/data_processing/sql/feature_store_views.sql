-- Feature Store: Materialized views for shared feature groups
-- Run against procurement schema in Postgres

-- ============================================================
-- 3.1 Vendor Composite Profile
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS procurement.mv_vendor_composite_profile CASCADE;
CREATE MATERIALIZED VIEW procurement.mv_vendor_composite_profile AS
SELECT
    vm.vendor_id,
    -- Vendor type one-hot
    CASE WHEN vm.vendor_type = 'OEM' THEN 1 ELSE 0 END AS v_type_oem,
    CASE WHEN vm.vendor_type = 'DISTRIBUTOR' THEN 1 ELSE 0 END AS v_type_distributor,
    CASE WHEN vm.vendor_type = 'CONTRACT_MFG' THEN 1 ELSE 0 END AS v_type_contract_mfg,
    CASE WHEN vm.vendor_type = 'LOGISTICS' THEN 1 ELSE 0 END AS v_type_logistics,
    CASE WHEN vm.vendor_type = 'SERVICE' THEN 1 ELSE 0 END AS v_type_service,
    -- Preferred flag
    CASE WHEN vm.preferred_flag THEN 1 ELSE 0 END AS v_preferred,
    -- Status ordinal
    CASE vm.status
        WHEN 'ACTIVE' THEN 2
        WHEN 'CONDITIONAL' THEN 1
        WHEN 'BLOCKED' THEN 0
        ELSE -1
    END AS v_status_encoded,
    -- Country risk
    CASE vm.country
        WHEN 'JP' THEN 1 WHEN 'DE' THEN 1 WHEN 'US' THEN 1
        WHEN 'SG' THEN 2 WHEN 'KR' THEN 2
        WHEN 'TH' THEN 3 WHEN 'CN' THEN 3
        WHEN 'VN' THEN 4
        ELSE -1
    END AS v_country_risk,
    -- Payment terms days
    CASE vm.payment_terms
        WHEN 'NET30' THEN 30
        WHEN 'NET60' THEN 60
        WHEN 'NET90' THEN 90
        WHEN '2/10NET30' THEN 30
        WHEN 'IMMEDIATE' THEN 0
        ELSE 30
    END AS v_payment_terms_days,
    -- Early discount flag
    CASE WHEN vm.payment_terms = '2/10NET30' THEN 1 ELSE 0 END AS v_has_early_discount,
    -- Confidentiality ordinal
    CASE vm.confidentiality_tier
        WHEN 'PUBLIC' THEN 0
        WHEN 'INTERNAL' THEN 1
        WHEN 'RESTRICTED' THEN 2
        ELSE -1
    END AS v_confidentiality_ordinal,
    -- Category count
    COALESCE(vc_agg.category_count, 0) AS v_category_count
FROM procurement.vendor_master vm
LEFT JOIN (
    SELECT vendor_id, COUNT(DISTINCT category_id) AS category_count
    FROM procurement.vendor_category
    GROUP BY vendor_id
) vc_agg ON vm.vendor_id = vc_agg.vendor_id;

-- ============================================================
-- 3.2 Vendor Historical Performance
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS procurement.mv_vendor_historical_performance CASCADE;
CREATE MATERIALIZED VIEW procurement.mv_vendor_historical_performance AS
WITH po_agg AS (
    SELECT
        ph.vendor_id,
        COUNT(*) AS v_total_po_count,
        SUM(ph.total_net_value) AS v_total_po_value,
        AVG(ph.total_net_value) AS v_avg_po_value
    FROM procurement.po_header ph
    GROUP BY ph.vendor_id
),
delivery AS (
    SELECT
        ph.vendor_id,
        AVG(CASE WHEN pl.actual_delivery_date <= pl.requested_delivery_date THEN 1.0 ELSE 0.0 END) AS v_on_time_delivery_actual,
        AVG(EXTRACT(DAY FROM pl.actual_delivery_date - pl.requested_delivery_date)) AS v_avg_delivery_delay_days
    FROM procurement.po_line_item pl
    JOIN procurement.po_header ph ON pl.po_id = ph.po_id
    WHERE pl.actual_delivery_date IS NOT NULL
      AND pl.requested_delivery_date IS NOT NULL
    GROUP BY ph.vendor_id
),
rejection AS (
    SELECT
        ph.vendor_id,
        CASE WHEN SUM(gl.quantity_received) > 0
             THEN SUM(gl.quantity_rejected)::FLOAT / SUM(gl.quantity_received)
             ELSE 0.0
        END AS v_rejection_rate
    FROM procurement.gr_line_item gl
    JOIN procurement.gr_header gh ON gl.gr_id = gh.gr_id
    JOIN procurement.po_header ph ON gh.po_id = ph.po_id
    GROUP BY ph.vendor_id
),
materials AS (
    SELECT
        ph.vendor_id,
        COUNT(DISTINCT pl.material_id) AS v_distinct_materials
    FROM procurement.po_line_item pl
    JOIN procurement.po_header ph ON pl.po_id = ph.po_id
    GROUP BY ph.vendor_id
)
SELECT
    pa.vendor_id,
    pa.v_total_po_count,
    pa.v_total_po_value,
    pa.v_avg_po_value,
    COALESCE(d.v_on_time_delivery_actual, 0.5) AS v_on_time_delivery_actual,
    COALESCE(d.v_avg_delivery_delay_days, 0.0) AS v_avg_delivery_delay_days,
    COALESCE(r.v_rejection_rate, 0.0) AS v_rejection_rate,
    COALESCE(m.v_distinct_materials, 0) AS v_distinct_materials
FROM po_agg pa
LEFT JOIN delivery d ON pa.vendor_id = d.vendor_id
LEFT JOIN rejection r ON pa.vendor_id = r.vendor_id
LEFT JOIN materials m ON pa.vendor_id = m.vendor_id;

-- ============================================================
-- 3.3 Vendor Invoice Behavior
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS procurement.mv_vendor_invoice_behavior CASCADE;
CREATE MATERIALIZED VIEW procurement.mv_vendor_invoice_behavior AS
SELECT
    ih.vendor_id,
    COUNT(*) AS v_invoice_count,
    AVG(CASE WHEN ih.match_status = 'FULL_MATCH' THEN 1.0 ELSE 0.0 END) AS v_invoice_match_rate,
    AVG(CASE WHEN ih.match_status IN ('PRICE_VARIANCE', 'BOTH_VARIANCE') THEN 1.0 ELSE 0.0 END) AS v_price_variance_rate,
    AVG(CASE WHEN ih.match_status IN ('QUANTITY_VARIANCE', 'BOTH_VARIANCE') THEN 1.0 ELSE 0.0 END) AS v_qty_variance_rate,
    AVG(CASE WHEN ih.payment_block THEN 1.0 ELSE 0.0 END) AS v_payment_block_rate,
    AVG(CASE WHEN il.unit_price_invoiced > 0
         THEN ABS(il.price_variance) / il.unit_price_invoiced
         ELSE 0.0
    END) AS v_avg_price_variance_pct
FROM procurement.invoice_header ih
JOIN procurement.invoice_line_item il ON ih.invoice_id = il.invoice_id
GROUP BY ih.vendor_id;

-- ============================================================
-- 3.5 Price Benchmarks
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS procurement.mv_price_benchmarks CASCADE;
CREATE MATERIALIZED VIEW procurement.mv_price_benchmarks AS
WITH mat_stats AS (
    SELECT
        material_id,
        AVG(unit_price) AS p_avg_unit_price,
        STDDEV(unit_price) AS p_std_unit_price,
        MIN(unit_price) AS p_min_unit_price,
        MAX(unit_price) AS p_max_unit_price
    FROM procurement.po_line_item
    GROUP BY material_id
),
contract_prices AS (
    SELECT
        material_id,
        MIN(agreed_price) AS p_contract_price
    FROM procurement.contract_item
    GROUP BY material_id
)
SELECT
    pl.po_id,
    pl.po_line_number,
    pl.material_id,
    pl.unit_price,
    ms.p_avg_unit_price,
    COALESCE(ms.p_std_unit_price, 0) AS p_std_unit_price,
    CASE WHEN mm.standard_cost > 0
         THEN pl.unit_price / mm.standard_cost
         ELSE NULL
    END AS p_price_to_standard_ratio,
    cp.p_contract_price
FROM procurement.po_line_item pl
JOIN mat_stats ms ON pl.material_id = ms.material_id
LEFT JOIN procurement.material_master mm ON pl.material_id = mm.material_id
LEFT JOIN contract_prices cp ON pl.material_id = cp.material_id;

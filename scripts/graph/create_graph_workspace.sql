-- ============================================================================
-- PROCUREMENT KNOWLEDGE GRAPH — HANA Cloud Graph Workspace
-- ============================================================================
-- Creates vertex views (10), edge views (14), unified views, and a
-- GRAPH WORKSPACE over the existing 29 procurement tables.
--
-- Prerequisites: relational data already loaded into PROCUREMENT schema.
-- Deploy: python scripts/graph/deploy_graph.py
-- ============================================================================

-- ============================================================================
-- 1. DROP existing objects (reverse dependency order)
-- ============================================================================

-- Drop graph workspace first
DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP GRAPH WORKSPACE "PROCUREMENT"."PROCUREMENT_KG";
END;

-- Drop unified views
DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."E_ALL_EDGES";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."V_ALL_VERTICES";
END;

-- Drop edge views
DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."E_SUPPLIES";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."E_ORDERED_FROM";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."E_CONTAINS_MATERIAL";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."E_UNDER_CONTRACT";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."E_INVOICED_FOR";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."E_RECEIVED_FOR";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."E_PAYS";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."E_BELONGS_TO_CATEGORY";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."E_CATEGORY_PARENT";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."E_LOCATED_AT";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."E_HAS_CONTRACT";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."E_REQUESTED_MATERIAL";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."E_INVOICED_BY_VENDOR";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."E_PAID_TO_VENDOR";
END;

-- Drop vertex views
DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."V_VENDOR";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."V_MATERIAL";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."V_PLANT";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."V_CATEGORY";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."V_PURCHASE_ORDER";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."V_CONTRACT";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."V_INVOICE";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."V_GOODS_RECEIPT";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."V_PAYMENT";
END;

DO BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN END;
  DROP VIEW "PROCUREMENT"."V_PURCHASE_REQ";
END;

-- ============================================================================
-- 2. VERTEX VIEWS
-- ============================================================================

CREATE VIEW "PROCUREMENT"."V_VENDOR" AS
SELECT
    vendor_id       AS vertex_id,
    'VENDOR'        AS vertex_type,
    vendor_name     AS label,
    vendor_type,
    country,
    status,
    quality_score,
    risk_score,
    on_time_delivery_rate
FROM "PROCUREMENT"."vendor_master";

CREATE VIEW "PROCUREMENT"."V_MATERIAL" AS
SELECT
    material_id     AS vertex_id,
    'MATERIAL'      AS vertex_type,
    description     AS label,
    material_type,
    category_id,
    criticality,
    standard_cost,
    base_uom
FROM "PROCUREMENT"."material_master";

CREATE VIEW "PROCUREMENT"."V_PLANT" AS
SELECT
    plant_id        AS vertex_id,
    'PLANT'         AS vertex_type,
    plant_name      AS label,
    country,
    city,
    function
FROM "PROCUREMENT"."plant";

CREATE VIEW "PROCUREMENT"."V_CATEGORY" AS
SELECT
    category_id         AS vertex_id,
    'CATEGORY'          AS vertex_type,
    category_name       AS label,
    level,
    parent_category_id
FROM "PROCUREMENT"."category_hierarchy";

CREATE VIEW "PROCUREMENT"."V_PURCHASE_ORDER" AS
SELECT
    po_id           AS vertex_id,
    'PURCHASE_ORDER' AS vertex_type,
    po_id           AS label,
    po_date,
    vendor_id,
    status,
    total_net_value,
    maverick_flag,
    po_type
FROM "PROCUREMENT"."po_header";

CREATE VIEW "PROCUREMENT"."V_CONTRACT" AS
SELECT
    contract_id     AS vertex_id,
    'CONTRACT'      AS vertex_type,
    contract_id     AS label,
    vendor_id,
    valid_from,
    valid_to,
    status,
    contract_type
FROM "PROCUREMENT"."contract_header";

CREATE VIEW "PROCUREMENT"."V_INVOICE" AS
SELECT
    invoice_id      AS vertex_id,
    'INVOICE'       AS vertex_type,
    invoice_id      AS label,
    invoice_date,
    vendor_id,
    total_net_amount,
    match_status,
    status
FROM "PROCUREMENT"."invoice_header";

CREATE VIEW "PROCUREMENT"."V_GOODS_RECEIPT" AS
SELECT
    gr_id           AS vertex_id,
    'GOODS_RECEIPT' AS vertex_type,
    gr_id           AS label,
    gr_date,
    po_id,
    status
FROM "PROCUREMENT"."gr_header";

CREATE VIEW "PROCUREMENT"."V_PAYMENT" AS
SELECT
    payment_id      AS vertex_id,
    'PAYMENT'       AS vertex_type,
    payment_id      AS label,
    payment_date,
    vendor_id,
    total_amount,
    payment_method,
    status
FROM "PROCUREMENT"."payment";

CREATE VIEW "PROCUREMENT"."V_PURCHASE_REQ" AS
SELECT
    pr_id           AS vertex_id,
    'PURCHASE_REQ'  AS vertex_type,
    pr_id           AS label,
    pr_date,
    status,
    priority,
    pr_type
FROM "PROCUREMENT"."pr_header";

-- ============================================================================
-- 3. UNIFIED VERTEX VIEW
-- ============================================================================

CREATE VIEW "PROCUREMENT"."V_ALL_VERTICES" AS
SELECT vertex_id, vertex_type, label FROM "PROCUREMENT"."V_VENDOR"
UNION ALL
SELECT vertex_id, vertex_type, label FROM "PROCUREMENT"."V_MATERIAL"
UNION ALL
SELECT vertex_id, vertex_type, label FROM "PROCUREMENT"."V_PLANT"
UNION ALL
SELECT vertex_id, vertex_type, label FROM "PROCUREMENT"."V_CATEGORY"
UNION ALL
SELECT vertex_id, vertex_type, label FROM "PROCUREMENT"."V_PURCHASE_ORDER"
UNION ALL
SELECT vertex_id, vertex_type, label FROM "PROCUREMENT"."V_CONTRACT"
UNION ALL
SELECT vertex_id, vertex_type, label FROM "PROCUREMENT"."V_INVOICE"
UNION ALL
SELECT vertex_id, vertex_type, label FROM "PROCUREMENT"."V_GOODS_RECEIPT"
UNION ALL
SELECT vertex_id, vertex_type, label FROM "PROCUREMENT"."V_PAYMENT"
UNION ALL
SELECT vertex_id, vertex_type, label FROM "PROCUREMENT"."V_PURCHASE_REQ";

-- ============================================================================
-- 4. EDGE VIEWS
-- ============================================================================

-- E_SUPPLIES: Vendor → Material (via source_list)
CREATE VIEW "PROCUREMENT"."E_SUPPLIES" AS
SELECT
    ROW_NUMBER() OVER (ORDER BY vendor_id, material_id, plant_id) AS edge_id,
    vendor_id       AS source_vertex,
    material_id     AS target_vertex,
    'SUPPLIES'      AS edge_type,
    plant_id,
    preferred_rank,
    approval_status,
    lane_lead_time_days AS lead_time
FROM "PROCUREMENT"."source_list";

-- E_ORDERED_FROM: PO → Vendor
CREATE VIEW "PROCUREMENT"."E_ORDERED_FROM" AS
SELECT
    ROW_NUMBER() OVER (ORDER BY po_id) AS edge_id,
    po_id           AS source_vertex,
    vendor_id       AS target_vertex,
    'ORDERED_FROM'  AS edge_type,
    po_date,
    total_net_value,
    maverick_flag
FROM "PROCUREMENT"."po_header";

-- E_CONTAINS_MATERIAL: PO → Material (via po_line_item)
CREATE VIEW "PROCUREMENT"."E_CONTAINS_MATERIAL" AS
SELECT
    ROW_NUMBER() OVER (ORDER BY po_id, po_line_number) AS edge_id,
    po_id           AS source_vertex,
    material_id     AS target_vertex,
    'CONTAINS_MATERIAL' AS edge_type,
    quantity,
    unit_price,
    net_value
FROM "PROCUREMENT"."po_line_item";

-- E_UNDER_CONTRACT: PO → Contract (via po_line_item where contract_id is set)
CREATE VIEW "PROCUREMENT"."E_UNDER_CONTRACT" AS
SELECT
    ROW_NUMBER() OVER (ORDER BY po_id, po_line_number) AS edge_id,
    po_id           AS source_vertex,
    contract_id     AS target_vertex,
    'UNDER_CONTRACT' AS edge_type,
    unit_price
FROM "PROCUREMENT"."po_line_item"
WHERE contract_id IS NOT NULL;

-- E_INVOICED_FOR: Invoice → PO
CREATE VIEW "PROCUREMENT"."E_INVOICED_FOR" AS
SELECT
    ROW_NUMBER() OVER (ORDER BY invoice_id) AS edge_id,
    invoice_id      AS source_vertex,
    po_id           AS target_vertex,
    'INVOICED_FOR'  AS edge_type,
    total_net_amount,
    match_status
FROM "PROCUREMENT"."invoice_header";

-- E_RECEIVED_FOR: GR → PO
CREATE VIEW "PROCUREMENT"."E_RECEIVED_FOR" AS
SELECT
    ROW_NUMBER() OVER (ORDER BY gr_id) AS edge_id,
    gr_id           AS source_vertex,
    po_id           AS target_vertex,
    'RECEIVED_FOR'  AS edge_type,
    gr_date,
    status
FROM "PROCUREMENT"."gr_header";

-- E_PAYS: Payment → Invoice (via payment_invoice_link)
CREATE VIEW "PROCUREMENT"."E_PAYS" AS
SELECT
    ROW_NUMBER() OVER (ORDER BY payment_id, invoice_id) AS edge_id,
    payment_id      AS source_vertex,
    invoice_id      AS target_vertex,
    'PAYS'          AS edge_type,
    amount_applied
FROM "PROCUREMENT"."payment_invoice_link";

-- E_BELONGS_TO_CATEGORY: Material → Category
CREATE VIEW "PROCUREMENT"."E_BELONGS_TO_CATEGORY" AS
SELECT
    ROW_NUMBER() OVER (ORDER BY material_id) AS edge_id,
    material_id     AS source_vertex,
    category_id     AS target_vertex,
    'BELONGS_TO_CATEGORY' AS edge_type
FROM "PROCUREMENT"."material_master";

-- E_CATEGORY_PARENT: Category → Parent Category
CREATE VIEW "PROCUREMENT"."E_CATEGORY_PARENT" AS
SELECT
    ROW_NUMBER() OVER (ORDER BY category_id) AS edge_id,
    category_id         AS source_vertex,
    parent_category_id  AS target_vertex,
    'CATEGORY_PARENT'   AS edge_type
FROM "PROCUREMENT"."category_hierarchy"
WHERE parent_category_id IS NOT NULL;

-- E_LOCATED_AT: PO → Plant
CREATE VIEW "PROCUREMENT"."E_LOCATED_AT" AS
SELECT
    ROW_NUMBER() OVER (ORDER BY po_id) AS edge_id,
    po_id           AS source_vertex,
    plant_id        AS target_vertex,
    'LOCATED_AT'    AS edge_type
FROM "PROCUREMENT"."po_header";

-- E_HAS_CONTRACT: Vendor → Contract
CREATE VIEW "PROCUREMENT"."E_HAS_CONTRACT" AS
SELECT
    ROW_NUMBER() OVER (ORDER BY contract_id) AS edge_id,
    vendor_id       AS source_vertex,
    contract_id     AS target_vertex,
    'HAS_CONTRACT'  AS edge_type,
    valid_from,
    valid_to,
    status
FROM "PROCUREMENT"."contract_header";

-- E_REQUESTED_MATERIAL: PR → Material (via pr_line_item)
CREATE VIEW "PROCUREMENT"."E_REQUESTED_MATERIAL" AS
SELECT
    ROW_NUMBER() OVER (ORDER BY pr_id, pr_line_number) AS edge_id,
    pr_id           AS source_vertex,
    material_id     AS target_vertex,
    'REQUESTED_MATERIAL' AS edge_type,
    quantity,
    requested_delivery_date
FROM "PROCUREMENT"."pr_line_item";

-- E_INVOICED_BY_VENDOR: Invoice → Vendor
CREATE VIEW "PROCUREMENT"."E_INVOICED_BY_VENDOR" AS
SELECT
    ROW_NUMBER() OVER (ORDER BY invoice_id) AS edge_id,
    invoice_id      AS source_vertex,
    vendor_id       AS target_vertex,
    'INVOICED_BY_VENDOR' AS edge_type,
    total_net_amount
FROM "PROCUREMENT"."invoice_header";

-- E_PAID_TO_VENDOR: Payment → Vendor
CREATE VIEW "PROCUREMENT"."E_PAID_TO_VENDOR" AS
SELECT
    ROW_NUMBER() OVER (ORDER BY payment_id) AS edge_id,
    payment_id      AS source_vertex,
    vendor_id       AS target_vertex,
    'PAID_TO_VENDOR' AS edge_type,
    total_amount,
    payment_date
FROM "PROCUREMENT"."payment";

-- ============================================================================
-- 5. UNIFIED EDGE VIEW
-- ============================================================================

CREATE VIEW "PROCUREMENT"."E_ALL_EDGES" AS
SELECT  0 * 100000 + edge_id AS edge_id, source_vertex, target_vertex, edge_type FROM "PROCUREMENT"."E_SUPPLIES"
UNION ALL
SELECT  1 * 100000 + edge_id AS edge_id, source_vertex, target_vertex, edge_type FROM "PROCUREMENT"."E_ORDERED_FROM"
UNION ALL
SELECT  2 * 100000 + edge_id AS edge_id, source_vertex, target_vertex, edge_type FROM "PROCUREMENT"."E_CONTAINS_MATERIAL"
UNION ALL
SELECT  3 * 100000 + edge_id AS edge_id, source_vertex, target_vertex, edge_type FROM "PROCUREMENT"."E_UNDER_CONTRACT"
UNION ALL
SELECT  4 * 100000 + edge_id AS edge_id, source_vertex, target_vertex, edge_type FROM "PROCUREMENT"."E_INVOICED_FOR"
UNION ALL
SELECT  5 * 100000 + edge_id AS edge_id, source_vertex, target_vertex, edge_type FROM "PROCUREMENT"."E_RECEIVED_FOR"
UNION ALL
SELECT  6 * 100000 + edge_id AS edge_id, source_vertex, target_vertex, edge_type FROM "PROCUREMENT"."E_PAYS"
UNION ALL
SELECT  7 * 100000 + edge_id AS edge_id, source_vertex, target_vertex, edge_type FROM "PROCUREMENT"."E_BELONGS_TO_CATEGORY"
UNION ALL
SELECT  8 * 100000 + edge_id AS edge_id, source_vertex, target_vertex, edge_type FROM "PROCUREMENT"."E_CATEGORY_PARENT"
UNION ALL
SELECT  9 * 100000 + edge_id AS edge_id, source_vertex, target_vertex, edge_type FROM "PROCUREMENT"."E_LOCATED_AT"
UNION ALL
SELECT 10 * 100000 + edge_id AS edge_id, source_vertex, target_vertex, edge_type FROM "PROCUREMENT"."E_HAS_CONTRACT"
UNION ALL
SELECT 11 * 100000 + edge_id AS edge_id, source_vertex, target_vertex, edge_type FROM "PROCUREMENT"."E_REQUESTED_MATERIAL"
UNION ALL
SELECT 12 * 100000 + edge_id AS edge_id, source_vertex, target_vertex, edge_type FROM "PROCUREMENT"."E_INVOICED_BY_VENDOR"
UNION ALL
SELECT 13 * 100000 + edge_id AS edge_id, source_vertex, target_vertex, edge_type FROM "PROCUREMENT"."E_PAID_TO_VENDOR";

-- ============================================================================
-- 6. GRAPH WORKSPACE
-- ============================================================================

CREATE GRAPH WORKSPACE "PROCUREMENT"."PROCUREMENT_KG"
    EDGE TABLE "PROCUREMENT"."E_ALL_EDGES"
        SOURCE COLUMN "SOURCE_VERTEX"
        TARGET COLUMN "TARGET_VERTEX"
        KEY COLUMN "EDGE_ID"
    VERTEX TABLE "PROCUREMENT"."V_ALL_VERTICES"
        KEY COLUMN "VERTEX_ID";

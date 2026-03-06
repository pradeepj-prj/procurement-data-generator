# ML Use Cases for Procurement Data Generator

## Table of Contents

1. [Introduction](#1-introduction)
2. [Data Context](#2-data-context)
3. [Centralized Feature Store](#3-centralized-feature-store)
4. [Common ML Lifecycle](#4-common-ml-lifecycle)
5. [Tier 1: Demo-Ready Use Cases](#5-tier-1-demo-ready-use-cases)
6. [Tier 2: Feasible with Enrichment](#6-tier-2-feasible-with-enrichment)
7. [Tier 3: Aspirational Use Cases](#7-tier-3-aspirational-use-cases)
8. [Cross-Reference Matrices](#8-cross-reference-matrices)
9. [GenAI Integration Patterns](#9-genai-integration-patterns)
10. [Data Generator Enrichment Roadmap](#10-data-generator-enrichment-roadmap)

---

## 1. Introduction

### Purpose

This document defines 13 machine learning use cases that can be built on top of the procurement dataset produced by this generator. Each use case includes a problem statement, solution approach (both predictive AI and GenAI), detailed feature engineering, and deployment considerations.

### Scope

The use cases cover the full procurement lifecycle -- from purchase requisition through payment -- and are organized into three tiers:

| Tier | Description | Use Cases | Generator Readiness |
|------|-------------|-----------|---------------------|
| **Tier 1** | Demo-ready: strong signals exist in generated data today | UC-01 through UC-04 | High |
| **Tier 2** | Feasible with enrichment: signal exists but needs enhancement | UC-05 through UC-08 | Medium |
| **Tier 3** | Aspirational: requires generator changes or external data | UC-09 through UC-13 | Low |

### Relationship to the Data Generator

The generator produces 29 referentially-intact tables modeled after SAP procurement structures. The dataset includes built-in statistical properties (maverick rate, invoice match rate, vendor quality scores) that serve as ML targets. Section 10 proposes enhancements to make these signals more realistic and challenging for ML models.

### How to Read This Document

Each use case follows a consistent template:

- **Problem Statement** -- What business question we answer and why it matters
- **Data Profile** -- Which tables, joins, labels, and row counts are involved
- **Approach** -- Predictive AI subsection + GenAI subsection
- **Feature Engineering** -- Feature store references + use-case-specific features
- **ML Lifecycle Notes** -- Only deviations from the common lifecycle (Section 4)
- **Demo Scenario** -- 3-5 sentence narrative showing the use case in action

---

## 2. Data Context

### Dataset Overview

The generator produces **29 tables** organized across master data (org structure, materials, vendors, contracts) and transactional data (PRs, POs, GRs, invoices, payments).

### Entity Volumes by Scale

| Entity | 1x | 3x | 10x |
|--------|----:|----:|-----:|
| Materials | 800 | 2,400 | 8,000 |
| Vendors | 120 | 360 | 1,200 |
| Contracts | 40 | 120 | 400 |
| Legal Entities | 95 | 285 | 950 |
| Purchase Requisitions | 500 | 1,500 | 5,000 |
| Purchase Orders | 400 | 1,200 | 4,000 |
| Goods Receipts | 350 | 1,050 | 3,500 |
| Invoices | 320 | 960 | 3,200 |
| Payments | 280 | 840 | 2,800 |
| **Total rows (approx.)** | **~10,600** | **~31,800** | **~106,000** |

### Built-in Statistical Properties

These distribution targets are enforced by the generator's validation layer:

| Property | Target Range | Source |
|----------|-------------|--------|
| Maverick PO rate | 5-8% of PO headers | `statistical.py` validates 2-12% window |
| On-contract PO lines | 70-75% of PO line items | `statistical.py` validates 60-85% window |
| Invoice full-match rate | 80-85% of invoices | `statistical.py` validates 70-95% window |
| Vendor status: ACTIVE | ~90% of vendors | `vendors.py:159-166` status distribution |
| Vendor status: BLOCKED | ~2-3% of vendors | Capped at 3 |
| Vendor status: CONDITIONAL | ~3-5% of vendors | Capped at 5 |
| Material criticality | HIGH/MEDIUM/LOW distribution | Logged in `statistical.py` |
| GR delivery rate | Driven by `vendor.on_time_delivery_rate` | `goods_receipts.py:56-76` |
| Quality rejections | Driven by `vendor.quality_score` | `goods_receipts.py:90-91` |

### Temporal Window

- **Time range**: 2024-04-01 to 2025-09-30 (18 months)
- **Demo reference date**: 2025-09-15
- **Temporal coverage**: POs spread across the full window; GRs follow POs by lead time; invoices follow GRs by 1-5 days; payments follow invoice due dates

### Data Limitations

- **No temporal dynamics**: Vendor scores (`quality_score`, `risk_score`, `on_time_delivery_rate`) are static -- they do not change over time
- **Independent feature generation**: Vendor `risk_score`, `quality_score`, and `esg_score` are drawn independently (`vendors.py:169-172`)
- **Direct label leakage**: `po_header.maverick_flag` and `po_header.notes` directly reveal maverick status; `invoice_header.match_status` directly reveals match outcome
- **Hard-coded thresholds**: Invoice match uses fixed 2%/$0.50 price tolerance and 5% quantity tolerance (`invoices.py:168-172`)
- **No external data**: No market prices, commodity indices, currency rates, or macroeconomic indicators

---

## 3. Centralized Feature Store

### Rationale

Analysis of the 13 use cases reveals that 9 feature groups are shared across 3 or more use cases. Computing these once and storing them in materialized views (or a feature store) eliminates redundant joins and ensures consistency across models.

### Feature Group Inventory

#### 3.1 Vendor Composite Profile

| Attribute | Details |
|-----------|---------|
| **Entity Key** | `vendor_id` |
| **Source Tables** | `vendor_master`, `vendor_category`, `vendor_address` |
| **Used By** | UC-01, UC-02, UC-03, UC-04, UC-05, UC-08, UC-09 |
| **UC Count** | 7 |

**Derived Features:**

| Feature | Source Fields | Computation |
|---------|-------------|-------------|
| `v_type_encoded` | `vendor_master.vendor_type` | One-hot: OEM, DISTRIBUTOR, CONTRACT_MFG, LOGISTICS, SERVICE |
| `v_preferred` | `vendor_master.preferred_flag` | Boolean (0/1) |
| `v_status_encoded` | `vendor_master.status` | Ordinal: ACTIVE=2, CONDITIONAL=1, BLOCKED=0 |
| `v_category_count` | `vendor_category` | COUNT(DISTINCT category_id) per vendor |
| `v_country_risk` | `vendor_master.country` | Mapped ordinal from country ISO code |
| `v_payment_terms_days` | `vendor_master.payment_terms` | NET30->30, NET60->60, NET90->90, 2/10NET30->30 |
| `v_has_early_discount` | `vendor_master.payment_terms` | 1 if 2/10NET30, else 0 |
| `v_confidentiality_ordinal` | `vendor_master.confidentiality_tier` | PUBLIC=0, INTERNAL=1, RESTRICTED=2 |

**Refresh Cadence:** Daily (vendor master changes are infrequent)

**HANA Implementation:** Materialized column view joining `vendor_master` + `vendor_category` with aggregation

#### 3.2 Vendor Historical Performance

| Attribute | Details |
|-----------|---------|
| **Entity Key** | `vendor_id` |
| **Source Tables** | `po_header`, `po_line_item`, `gr_header`, `gr_line_item` |
| **Used By** | UC-02, UC-03, UC-05, UC-09 |
| **UC Count** | 4 |

**Derived Features:**

| Feature | Computation |
|---------|-------------|
| `v_total_po_count` | COUNT(po_header) per vendor |
| `v_total_po_value` | SUM(po_header.total_net_value) per vendor |
| `v_avg_po_value` | AVG(po_header.total_net_value) per vendor |
| `v_on_time_delivery_actual` | COUNT(gr where gr_date <= requested_delivery_date) / COUNT(gr) |
| `v_avg_delivery_delay_days` | AVG(gr_date - requested_delivery_date) where late |
| `v_rejection_rate` | SUM(gr_line.quantity_rejected) / SUM(gr_line.quantity_received) |
| `v_po_frequency_monthly` | COUNT(po) / months_active |
| `v_distinct_materials` | COUNT(DISTINCT material_id) across PO lines |

**Refresh Cadence:** Daily (incremental from new GRs)

#### 3.3 Vendor Invoice Behavior

| Attribute | Details |
|-----------|---------|
| **Entity Key** | `vendor_id` |
| **Source Tables** | `invoice_header`, `invoice_line_item` |
| **Used By** | UC-02, UC-03, UC-07, UC-11 |
| **UC Count** | 4 |

**Derived Features:**

| Feature | Computation |
|---------|-------------|
| `v_invoice_match_rate` | COUNT(FULL_MATCH) / COUNT(*) per vendor |
| `v_price_variance_rate` | COUNT(PRICE_VARIANCE or BOTH_VARIANCE) / COUNT(*) |
| `v_qty_variance_rate` | COUNT(QUANTITY_VARIANCE or BOTH_VARIANCE) / COUNT(*) |
| `v_avg_price_variance_pct` | AVG(ABS(price_variance / unit_price_invoiced)) |
| `v_payment_block_rate` | COUNT(payment_block=True) / COUNT(*) |
| `v_avg_invoice_to_payment_days` | AVG(payment.payment_date - invoice.invoice_date) |

**Refresh Cadence:** Daily

#### 3.4 Material Risk Profile

| Attribute | Details |
|-----------|---------|
| **Entity Key** | `material_id` |
| **Source Tables** | `material_master`, `source_list`, `contract_item` |
| **Used By** | UC-01, UC-04, UC-09, UC-10, UC-12, UC-13 |
| **UC Count** | 6 |

**Derived Features:**

| Feature | Source Fields | Computation |
|---------|-------------|-------------|
| `m_criticality_ordinal` | `material_master.criticality` | LOW=0, MEDIUM=1, HIGH=2 |
| `m_type_encoded` | `material_master.material_type` | One-hot: COMPONENT, RAW, ASSEMBLY, MRO, SERVICE |
| `m_standard_cost` | `material_master.standard_cost` | Numeric (log-transformed for modeling) |
| `m_source_count` | `source_list` | COUNT(DISTINCT vendor_id) per material+plant |
| `m_contract_covered` | `contract_item` | 1 if any active contract covers this material, else 0 |
| `m_hazmat` | `material_master.hazmat_flag` | Boolean |
| `m_lead_time_days` | `material_master.default_lead_time_days` | Numeric |
| `m_confidentiality_ordinal` | `material_master.confidentiality_tier` | PUBLIC=0, INTERNAL=1, RESTRICTED=2 |
| `m_make_or_buy` | `material_master.make_or_buy` | Binary: MAKE=0, BUY=1 |

**Refresh Cadence:** Weekly (material master changes rarely)

#### 3.5 Price Benchmarks

| Attribute | Details |
|-----------|---------|
| **Entity Key** | (`material_id`, `vendor_id`) |
| **Source Tables** | `po_line_item`, `contract_item`, `material_master` |
| **Used By** | UC-01, UC-02, UC-04, UC-07 |
| **UC Count** | 4 |

**Derived Features:**

| Feature | Computation |
|---------|-------------|
| `p_avg_unit_price` | AVG(po_line_item.unit_price) per material+vendor |
| `p_std_unit_price` | STDDEV(po_line_item.unit_price) per material+vendor |
| `p_price_to_standard_ratio` | AVG(unit_price) / material.standard_cost |
| `p_contract_price` | contract_item.agreed_price (NULL if no contract) |
| `p_price_vs_contract` | AVG(unit_price) / contract_item.agreed_price |
| `p_price_trend_slope` | Linear regression slope of unit_price over time |
| `p_min_price_30d` | MIN(unit_price) in last 30 days |
| `p_max_price_30d` | MAX(unit_price) in last 30 days |

**Refresh Cadence:** Daily (new POs change averages)

#### 3.6 Contract Status

| Attribute | Details |
|-----------|---------|
| **Entity Key** | `contract_id` |
| **Source Tables** | `contract_header`, `contract_item` |
| **Used By** | UC-01, UC-04, UC-06, UC-08 |
| **UC Count** | 4 |

**Derived Features:**

| Feature | Computation |
|---------|-------------|
| `c_days_to_expiry` | contract_header.valid_to - CURRENT_DATE |
| `c_is_active` | 1 if status = ACTIVE, else 0 |
| `c_consumption_pct` | consumed_quantity / max_quantity (QUANTITY type) or consumed_value / target_value (VALUE type) |
| `c_remaining_quantity` | max_quantity - consumed_quantity |
| `c_remaining_value` | target_value - consumed_value |
| `c_months_active` | MONTHS_BETWEEN(valid_from, LEAST(CURRENT_DATE, valid_to)) |
| `c_consumption_rate_monthly` | consumption_pct / months_active |

**Refresh Cadence:** Daily

#### 3.7 Category Spend Profile

| Attribute | Details |
|-----------|---------|
| **Entity Key** | `category_id` |
| **Source Tables** | `category_hierarchy`, `material_master`, `po_line_item` |
| **Used By** | UC-04, UC-08, UC-10, UC-12 |
| **UC Count** | 4 |

**Derived Features:**

| Feature | Computation |
|---------|-------------|
| `cat_total_spend` | SUM(po_line_item.net_value) joining through material.category_id |
| `cat_avg_po_value` | AVG(po_line_item.net_value) per category |
| `cat_vendor_count` | COUNT(DISTINCT vendor_id) per category |
| `cat_material_count` | COUNT(DISTINCT material_id) per category |
| `cat_maverick_rate` | COUNT(maverick POs) / COUNT(POs) per category |
| `cat_hierarchy_level` | category_hierarchy.level |
| `cat_parent_id` | category_hierarchy.parent_category_id |

**Refresh Cadence:** Weekly

#### 3.8 Vendor-Material Pair Performance

| Attribute | Details |
|-----------|---------|
| **Entity Key** | (`vendor_id`, `material_id`) |
| **Source Tables** | `po_line_item`, `gr_line_item`, `invoice_line_item` |
| **Used By** | UC-05, UC-09 |
| **UC Count** | 2 |

**Derived Features:**

| Feature | Computation |
|---------|-------------|
| `vm_order_count` | COUNT(po_line_item) per vendor+material |
| `vm_avg_qty_per_order` | AVG(po_line_item.quantity) |
| `vm_rejection_rate` | SUM(qty_rejected) / SUM(qty_received) for this pair |
| `vm_avg_delivery_delay` | AVG(actual_delivery_date - requested_delivery_date) |
| `vm_price_stability` | STDDEV(unit_price) / AVG(unit_price) (coefficient of variation) |
| `vm_last_order_date` | MAX(po_header.po_date) |

**Refresh Cadence:** Daily

#### 3.9 Vendor Geographic Risk

| Attribute | Details |
|-----------|---------|
| **Entity Key** | `vendor_id` |
| **Source Tables** | `vendor_master`, `vendor_address`, `legal_entity` |
| **Used By** | UC-03, UC-05, UC-08 |
| **UC Count** | 3 |

**Derived Features:**

| Feature | Computation |
|---------|-------------|
| `vg_country_code` | vendor_master.country |
| `vg_region` | Mapped from country (APAC, EMEA, AMER) |
| `vg_incorporation_country` | legal_entity.country_of_incorporation |
| `vg_cross_border` | 1 if vendor.country != legal_entity.country_of_incorporation |
| `vg_address_count` | COUNT(vendor_address) per vendor |
| `vg_multi_country` | 1 if addresses span multiple countries |
| `vg_alias_group` | vendor_master.alias_group (for entity resolution) |

**Refresh Cadence:** Weekly

---

## 4. Common ML Lifecycle

This section describes the ML lifecycle steps that are shared across all or most use cases. Individual use case sections only document **deviations** from this common baseline.

### 4.1 Data Preparation

**Join Strategy:** Start from the primary transactional table (e.g., `po_header` for maverick detection) and left-join to dimensional tables. Use the feature store views instead of raw joins where available.

```sql
-- Example: PO-centric dataset
SELECT po.*, pol.*, v.*, m.*
FROM po_header po
JOIN po_line_item pol ON po.po_id = pol.po_id
JOIN vendor_master v ON po.vendor_id = v.vendor_id
JOIN material_master m ON pol.material_id = m.material_id
LEFT JOIN contract_header ch ON pol.contract_id = ch.contract_id
```

**Currency Normalization:** All monetary values should be converted to a single base currency (USD recommended) using a static rate table. Fields affected: `po_line_item.unit_price`, `po_line_item.net_value`, `material_master.standard_cost`, `contract_item.agreed_price`, `invoice_line_item.net_amount`, `payment.total_amount`.

**NULL Handling:**
- `vendor_master.esg_score`: 20% NULL -- impute with category median or use a missing-indicator feature
- `vendor_master.alias_group`: NULL means no alias -- treat as independent vendor
- `source_list.min_order_qty`: NULL means no minimum -- impute with 1
- `po_line_item.contract_id`: NULL means off-contract -- encode as binary feature
- `po_header.notes`: NULL means no notes -- use empty string for text features

### 4.2 Feature Encoding

| Type | Fields | Encoding |
|------|--------|----------|
| **Categorical (nominal)** | `vendor_type`, `material_type`, `po_type`, `incoterms`, `payment_method` | One-hot encoding |
| **Categorical (ordinal)** | `criticality` (LOW/MEDIUM/HIGH), `priority` (LOW/MEDIUM/HIGH/CRITICAL), `confidentiality_tier` (PUBLIC/INTERNAL/RESTRICTED), `status` (ACTIVE/CONDITIONAL/BLOCKED) | Integer ordinal encoding |
| **Numerical** | `standard_cost`, `unit_price`, `quantity`, `quality_score`, `risk_score`, `on_time_delivery_rate` | Standardization (z-score) or min-max; log-transform for skewed costs |
| **Text** | `po_header.notes`, `material_master.description` | TF-IDF or embeddings (GenAI subsections) |
| **Temporal** | `po_date`, `gr_date`, `invoice_date` | Day-of-week, month, quarter, days-since-epoch, cyclical encoding |
| **Boolean** | `preferred_flag`, `hazmat_flag`, `maverick_flag`, `payment_block`, `contract_covered_flag` | Binary 0/1 |

### 4.3 Train/Validation/Test Split

**Recommended: Temporal Split**

Given the 18-month window (2024-04 to 2025-09):

| Set | Period | Purpose |
|-----|--------|---------|
| **Train** | 2024-04 to 2025-03 (12 months) | Model fitting |
| **Validation** | 2025-04 to 2025-06 (3 months) | Hyperparameter tuning |
| **Test** | 2025-07 to 2025-09 (3 months) | Final evaluation |

This prevents data leakage from future transactions informing past predictions. For use cases with very low positive rates (e.g., maverick at 5-8%), consider stratified sampling within each temporal window.

### 4.4 Model Training

**Progression:**

| Stage | Model | When to Use |
|-------|-------|-------------|
| Baseline | Logistic regression (classification) / Linear regression (regression) | Always start here; establishes interpretable floor |
| Intermediate | XGBoost / LightGBM | When baseline plateaus; handles feature interactions natively |
| Advanced | Neural networks / LSTM | Only for temporal patterns or very large datasets (10x scale) |

**Hyperparameter Tuning:** 5-fold time-series cross-validation (expanding window, not random shuffle).

### 4.5 Evaluation Framework

**Classification (UC-01, 02, 03, 09, 11, 13):**

| Metric | Primary For | Notes |
|--------|------------|-------|
| Precision | Low-FP use cases (invoice match, duplicate detection) | Avoid flooding users with false alerts |
| Recall | Low-FN use cases (maverick detection, vendor risk) | Missing a real maverick is costly |
| F1-Score | Balanced use cases | Harmonic mean of precision and recall |
| AUC-ROC | Model comparison | Threshold-independent; preferred for ranking |
| PR-AUC | Imbalanced classes | Better than ROC-AUC when positive class is rare |

**Regression (UC-05, 07, 10):**

| Metric | Notes |
|--------|-------|
| MAE | Mean absolute error; interpretable in original units |
| RMSE | Penalizes large errors more heavily |
| MAPE | Mean absolute percentage error; scale-independent |

**Anomaly Detection (UC-04):**

| Metric | Notes |
|--------|-------|
| Precision@K | Of the top K flagged anomalies, how many are real? |
| Recall@K | Of all real anomalies, how many are in top K? |

### 4.6 Explainability

- **SHAP (SHapley Additive exPlanations):** Global feature importance + per-prediction explanations. Works with tree-based and linear models.
- **LIME (Local Interpretable Model-agnostic Explanations):** Per-prediction surrogate explanations. Useful for complex models.
- **Feature importance (native):** Built-in for XGBoost/LightGBM. Quick sanity check for feature relevance.

For procurement, explainability is critical: users need to know *why* a PO is flagged as maverick or *why* an invoice is predicted to mismatch.

### 4.7 Deployment Patterns

| Pattern | Latency | Use Cases |
|---------|---------|-----------|
| **Batch** | Hours | Vendor risk scoring, spend classification, concentration risk |
| **Near-real-time** | Minutes | Maverick detection (at PO creation), invoice match prediction |
| **On-demand** | Seconds | Price anomaly check, contract expiry alert |

On SAP HANA Cloud, batch scoring uses PAL (Predictive Analysis Library) stored procedures. Near-real-time uses application-layer inference with HANA as feature store.

### 4.8 Monitoring and Drift Detection

- **Prediction drift:** Track prediction distribution weekly. Alert on >10% shift in positive-class rate.
- **Feature drift:** Monitor feature distributions (PSI -- Population Stability Index). Alert on PSI > 0.2.
- **Label drift:** Compare actual outcomes (e.g., actual maverick rate from audits) against predicted rates.
- **Retrain triggers:** Calendar-based (monthly) or drift-triggered (PSI threshold exceeded).

### 4.9 Scale Considerations

| Scale | Rows | ML Viability | Notes |
|-------|------|-------------|-------|
| **1x** | ~10,600 | Prototype | Sufficient for feature engineering validation and model smoke tests. Low event counts for rare classes (mavericks: ~20-32 POs). |
| **3x** | ~31,800 | Viable | Enough for train/val/test splits. Rare class counts become workable (~60-96 mavericks). |
| **10x** | ~106,000 | Production-representative | Supports neural network training. Statistical properties stabilize. Recommended for demo. |

---

## 5. Tier 1: Demo-Ready Use Cases

### UC-01: Maverick Purchase Order Detection

#### Problem Statement

Maverick purchases bypass preferred vendors and contract agreements, leading to higher prices, inconsistent quality, and compliance risk. Detecting maverick POs at creation time allows procurement teams to intervene before orders are placed.

**Business Value:** Organizations typically see 5-15% of spend go through maverick channels. Reducing this by even 2% translates directly to cost savings and supplier relationship improvement.

#### Data Profile

| Attribute | Value |
|-----------|-------|
| **Primary Table** | `po_header` |
| **Join Tables** | `po_line_item`, `vendor_master`, `material_master`, `source_list`, `contract_header`, `contract_item` |
| **Label** | `po_header.maverick_flag` (binary) |
| **Positive Rate** | 5-8% of POs |
| **Row Count (1x)** | ~400 POs, ~20-32 positive |
| **Row Count (10x)** | ~4,000 POs, ~200-320 positive |

#### Approach

**Predictive AI:**

Binary classification. The model predicts whether a PO about to be created would be classified as maverick based on the vendor, material, pricing, and contract context.

- Baseline: Logistic regression on vendor preferred status + contract coverage + price-to-standard ratio
- Target: XGBoost with full feature set including vendor profile, material risk, and contract status features

**GenAI:**

- **Explanation generation:** Given a flagged PO, generate a natural-language explanation: "This PO to vendor NIDEC-JP for MAT-MOT-400W is flagged as maverick because: (1) no active contract covers the 400W variant, (2) unit price of $110 is 29% above standard cost of $85, (3) preferred vendor NIDEC-MY was available on the source list."
- **Policy RAG:** Retrieve relevant procurement policies to contextualize the flag. "Per AMR Procurement Policy 4.2, all motor purchases above $5,000 require contract coverage."
- **Remediation suggestions:** "Consider creating a framework agreement for the 400W variant with NIDEC-JP, or source from contract CTR-00003 which covers 200W motors at $85/unit."

#### Feature Engineering

**From Feature Store:**
- Vendor Composite Profile (3.1): `v_preferred`, `v_status_encoded`, `v_type_encoded`
- Material Risk Profile (3.4): `m_criticality_ordinal`, `m_contract_covered`, `m_standard_cost`
- Price Benchmarks (3.5): `p_price_to_standard_ratio`, `p_contract_price`, `p_price_vs_contract`
- Contract Status (3.6): `c_is_active`, `c_consumption_pct`, `c_days_to_expiry`

**Use-Case-Specific Features:**

| Feature | Computation | Rationale |
|---------|-------------|-----------|
| `uc01_has_source_list_entry` | 1 if source_list exists for (material, plant, vendor) | No source list entry = likely maverick |
| `uc01_source_list_rank` | preferred_rank from source_list, 999 if absent | Higher rank = less preferred |
| `uc01_price_premium_pct` | (unit_price - standard_cost) / standard_cost | Maverick POs have 1.20-1.50x premium (`purchase_orders.py:293`) |
| `uc01_vendor_is_approved` | source_list.approval_status = APPROVED | CONDITIONAL or NOT_APPROVED increases risk |
| `uc01_po_type_rush` | 1 if po_type = RUSH | Maverick POs are 30% more likely to be RUSH (`purchase_orders.py:197`) |
| `uc01_notes_contains_maverick` | 1 if notes contains "Maverick" or "non-preferred" | Direct signal leak in current generator (`purchase_orders.py:300,434`) |

#### ML Lifecycle Notes

- **Class imbalance:** 5-8% positive rate. Use SMOTE or class weights. At 1x scale, only ~20-32 positives -- use 10x for meaningful training.
- **Primary metric:** Recall (missing a real maverick is worse than a false positive). Target: Recall > 0.85, Precision > 0.60.
- **Inference pattern:** Near-real-time -- score at PO creation time.
- **Leakage warning:** `maverick_flag` is the label. Also exclude `po_header.notes` (contains "Maverick purchase" text) from features.

#### Demo Scenario

Procurement analyst Sarah reviews the daily maverick detection dashboard. The system flags PO-000028 to NIDEC-JP for 45 units of MAT-MOT-400W at $110/unit. SHAP analysis shows the top factors: no active contract for 400W motors (impact: +0.35), price 29% above standard cost (impact: +0.28), and preferred vendor NIDEC-MY available on source list (impact: +0.15). Sarah clicks "Explain" and the GenAI module generates a plain-English summary with a recommendation to extend contract CTR-00003 to cover the 400W variant.

---

### UC-02: Invoice Three-Way Match Prediction

#### Problem Statement

Three-way matching (PO price/quantity vs. GR quantity vs. invoice amounts) is a major bottleneck in accounts payable. Predicting which invoices will fail matching allows proactive vendor communication and faster exception resolution.

**Business Value:** Exception handling costs $15-40 per invoice. Predicting mismatches before they occur can cut resolution time by 50% and reduce payment delays.

#### Data Profile

| Attribute | Value |
|-----------|-------|
| **Primary Table** | `invoice_header` |
| **Join Tables** | `invoice_line_item`, `po_header`, `po_line_item`, `gr_header`, `gr_line_item`, `vendor_master` |
| **Label** | `invoice_header.match_status` (multi-class: FULL_MATCH, PRICE_VARIANCE, QUANTITY_VARIANCE, BOTH_VARIANCE) |
| **Positive Rate (mismatch)** | 15-20% of invoices |
| **Row Count (1x)** | ~320 invoices |
| **Row Count (10x)** | ~3,200 invoices |

#### Approach

**Predictive AI:**

Multi-class classification (or binary: FULL_MATCH vs. any variance). Predict the match outcome before the invoice is fully processed.

- Baseline: Logistic regression on vendor match rate history + price variance magnitude
- Target: XGBoost with vendor invoice behavior features + material-specific variance patterns

**GenAI:**

- **Root cause analysis:** "Invoice INV-000001 from MOLEX-SG shows PRICE_VARIANCE: invoiced unit price $5.24 vs. PO price $4.85 (8.0% over). This vendor has a 15% price variance rate across 12 invoices. Recommended action: verify contract terms and request credit note."
- **Auto-resolution suggestions:** For small variances within tolerance, suggest auto-approval. For systematic vendor-specific patterns, suggest vendor scorecard review.

#### Feature Engineering

**From Feature Store:**
- Vendor Composite Profile (3.1): `v_preferred`, `v_status_encoded`
- Vendor Historical Performance (3.2): `v_rejection_rate`, `v_on_time_delivery_actual`
- Vendor Invoice Behavior (3.3): `v_invoice_match_rate`, `v_price_variance_rate`, `v_avg_price_variance_pct`
- Price Benchmarks (3.5): `p_price_to_standard_ratio`, `p_std_unit_price`, `p_contract_price`

**Use-Case-Specific Features:**

| Feature | Computation | Rationale |
|---------|-------------|-----------|
| `uc02_is_contract_po` | 1 if po_line_item.contract_id IS NOT NULL | Contract POs have fixed prices, less variance |
| `uc02_gr_qty_vs_po_qty` | gr_line.quantity_received / po_line.quantity | Partial deliveries create qty variance risk |
| `uc02_gr_has_rejection` | 1 if gr_line.quantity_rejected > 0 | Rejections lead to quantity disputes |
| `uc02_days_gr_to_invoice` | invoice_date - gr_date | Longer gaps increase mismatch risk |
| `uc02_invoice_amount_vs_po` | invoice.total_gross_amount / po.total_net_value | Gross deviation indicator |
| `uc02_vendor_invoice_seq` | Sequential invoice number per vendor | First invoices from a vendor may have higher error rates |

#### ML Lifecycle Notes

- **Multi-class handling:** Can simplify to binary (FULL_MATCH vs. ANY_VARIANCE) for stronger signal. Multi-class (4 categories) may need one-vs-rest at 1x scale.
- **Primary metric:** Precision -- false positives waste AP staff time on invoices that would have matched.
- **Inference pattern:** Near-real-time -- score when invoice is received, before matching begins.

#### Demo Scenario

When invoice INV-000001 arrives from MOLEX-SG, the system predicts PRICE_VARIANCE with 91% confidence before the three-way match runs. AP clerk David sees the prediction alongside the GenAI explanation: "MOLEX-SG's invoices have deviated from PO prices in 3 of their last 8 invoices, averaging 6.2% price overcharge. This invoice is for connectors under contract CTR-00004 at $4.85/unit." David pre-stages the credit note request, cutting resolution time from 5 days to 1 day.

---

### UC-03: Vendor Risk Scoring

#### Problem Statement

Vendor risk encompasses delivery reliability, quality performance, financial stability, and geographic exposure. A composite risk score allows procurement to proactively manage supplier relationships and diversify sources for critical materials.

**Business Value:** Vendor failures in AMR manufacturing can halt production lines. Early risk identification enables contingency planning and reduces supply chain disruptions by 30-50%.

#### Data Profile

| Attribute | Value |
|-----------|-------|
| **Primary Table** | `vendor_master` |
| **Join Tables** | `po_header`, `gr_header`, `gr_line_item`, `invoice_header`, `source_list`, `legal_entity`, `vendor_address` |
| **Label** | Composite risk score (regression) or risk tier (classification: LOW/MEDIUM/HIGH) |
| **Proxy Label** | `vendor_master.risk_score` (currently random 10-85, not correlated with performance) |
| **Row Count (1x)** | ~120 vendors |
| **Row Count (10x)** | ~1,200 vendors |

#### Approach

**Predictive AI:**

Regression (predict continuous risk score 0-100) or classification (LOW/MEDIUM/HIGH tier). Since the current `risk_score` is randomly generated, the practical approach is to derive a target from observable performance metrics.

- **Derived target:** `risk_derived = w1 * (100 - actual_otd_pct) + w2 * (100 - quality_score) + w3 * (rejection_rate * 100) + w4 * invoice_mismatch_rate * 100`
- Baseline: Weighted sum with expert-tuned weights
- Target: XGBoost regression with all vendor features + transaction-derived performance features

**GenAI:**

- **Risk narrative generation:** "Vendor VND-NIDEC-MY has an elevated risk score of 72/100. Key risk factors: (1) on-time delivery rate of 78% is below the 85% fleet average, (2) quality score of 68 puts them in the CONDITIONAL status category, (3) they share legal entity LE-NIDEC with VND-NIDEC-JP (alias group ALIAS-001), creating concentration risk."
- **Mitigation recommendations:** "Consider qualifying an alternative motor supplier. Top candidates from the source list: VND-NIDEC-JP (risk: 35, same entity group) or add a new qualified vendor from the MOTN category."

#### Feature Engineering

**From Feature Store:**
- Vendor Composite Profile (3.1): `v_type_encoded`, `v_preferred`, `v_status_encoded`, `v_country_risk`
- Vendor Historical Performance (3.2): `v_on_time_delivery_actual`, `v_avg_delivery_delay_days`, `v_rejection_rate`
- Vendor Invoice Behavior (3.3): `v_invoice_match_rate`, `v_payment_block_rate`
- Vendor Geographic Risk (3.9): `vg_region`, `vg_cross_border`, `vg_alias_group`

**Use-Case-Specific Features:**

| Feature | Computation | Rationale |
|---------|-------------|-----------|
| `uc03_quality_score_raw` | vendor_master.quality_score | Direct quality indicator |
| `uc03_otd_rate_raw` | vendor_master.on_time_delivery_rate | Delivery reliability |
| `uc03_esg_score` | vendor_master.esg_score (with imputation) | ESG risk factor |
| `uc03_active_contract_count` | COUNT(contract_header where status=ACTIVE) per vendor | More contracts = more established |
| `uc03_material_criticality_max` | MAX(material.criticality) across sourced materials | Supplies critical parts = higher impact if fails |
| `uc03_alias_vendor_count` | COUNT(vendors in same alias_group) | Multi-entity exposure |

#### ML Lifecycle Notes

- **Label engineering:** The current `risk_score` is independently random -- it does not reflect actual transaction performance. Derive a target from GR/invoice outcomes instead.
- **Small N problem:** Only 120 vendors at 1x. Use 10x (1,200) for meaningful models, or apply regularization heavily.
- **Primary metric:** RMSE (regression) or weighted F1 (classification). Weight HIGH-risk misclassification higher.
- **Inference pattern:** Batch -- recalculate scores weekly.

#### Demo Scenario

The weekly vendor risk dashboard updates, and supply chain manager Lisa notices VND-EVE has moved from MEDIUM to HIGH risk. The model's SHAP explanation shows a 15% increase in delivery delays over the past quarter and a spike in price variance on battery cell invoices. The GenAI module suggests: "VND-EVE's risk increase is driven by deteriorating delivery performance (3 of last 5 POs delivered late). VND-CATL, the contracted battery supplier, remains at LOW risk and has capacity under CTR-00002. Recommend shifting 30% of EVE's volume to CATL."

---

### UC-04: Price Anomaly Detection

#### Problem Statement

Anomalous unit prices -- whether too high (overpayment) or too low (quality risk) -- signal procurement issues ranging from contract non-compliance to vendor fraud. Detecting price anomalies across thousands of PO lines requires automated, context-aware analysis.

**Business Value:** Price anomalies typically represent 2-5% of procurement spend. Automated detection recovers overpayments and prevents quality issues from below-market pricing.

#### Data Profile

| Attribute | Value |
|-----------|-------|
| **Primary Table** | `po_line_item` |
| **Join Tables** | `po_header`, `material_master`, `vendor_master`, `contract_item`, `source_list` |
| **Label** | Anomaly score (unsupervised) or binary anomaly flag (semi-supervised) |
| **Proxy Signal** | Price-to-standard-cost ratio; maverick POs use 1.20-1.50x multiplier |
| **Row Count (1x)** | ~400+ PO line items |
| **Row Count (10x)** | ~4,000+ PO line items |

#### Approach

**Predictive AI:**

Anomaly detection, not standard classification (no clean label exists).

- Baseline: Z-score on unit_price per material_id; flag |z| > 2
- Intermediate: Isolation Forest with material, vendor, and contract features
- Target: Autoencoder on the full feature vector; anomaly = high reconstruction error

**GenAI:**

- **Anomaly explanation:** "PO line for MAT-CAM-3D at $241/unit is 14% above the 90-day average of $211 and 2.1% above the recent contract price of $236. This price point was last seen in post-expiry purchases (PO-000039, PO-000040)."
- **Market context (with enrichment):** "Camera module prices have been stable. This price increase may indicate a vendor attempting to renegotiate terms post-contract-expiry."

#### Feature Engineering

**From Feature Store:**
- Material Risk Profile (3.4): `m_standard_cost`, `m_criticality_ordinal`, `m_type_encoded`
- Price Benchmarks (3.5): `p_avg_unit_price`, `p_std_unit_price`, `p_price_to_standard_ratio`, `p_contract_price`
- Contract Status (3.6): `c_is_active`, `c_days_to_expiry`
- Category Spend Profile (3.7): `cat_avg_po_value`

**Use-Case-Specific Features:**

| Feature | Computation | Rationale |
|---------|-------------|-----------|
| `uc04_price_zscore` | (unit_price - AVG(unit_price for material)) / STDDEV | Statistical outlier detection |
| `uc04_price_vs_last_po` | unit_price / LAG(unit_price) per material | Sudden price jumps |
| `uc04_price_vs_contract` | unit_price / contract_item.agreed_price | Over-contract-price indicator |
| `uc04_is_off_contract` | 1 if contract_id IS NULL | Off-contract POs have unconstrained pricing |
| `uc04_vendor_avg_premium` | AVG(unit_price / standard_cost) per vendor | Some vendors consistently overcharge |
| `uc04_qty_weighted_price` | unit_price weighted by quantity | Large quantity at anomalous price is higher risk |

#### ML Lifecycle Notes

- **Unsupervised:** No clean labels. Evaluate using domain expert review of top-K flagged anomalies (Precision@K).
- **Context-dependent thresholds:** What's anomalous for a $0.50 connector is different from a $500 sensor. Train per-material or per-category models.
- **Primary metric:** Precision@50 (of the top 50 flagged anomalies, how many are genuinely anomalous?).
- **Inference pattern:** Batch (nightly scan of new POs) + on-demand (price check at PO creation).

#### Demo Scenario

The nightly price anomaly scan flags 8 PO lines. Procurement analyst James reviews the top-ranked anomaly: a recent camera module PO at $241/unit. The system shows that the historical price range for MAT-CAM-3D is $211-$236, and the anomaly coincides with contract CTR expiry. The GenAI narrative explains the price creep pattern and recommends renegotiating the camera contract before further price escalation.

---

## 6. Tier 2: Feasible with Enrichment

### UC-05: Delivery Delay Prediction

#### Problem Statement

Late deliveries disrupt AMR production schedules. Predicting which POs are at risk of delivery delay enables proactive expediting, alternative sourcing, or production schedule adjustment.

**Business Value:** Each day of production line downtime costs $50,000-200,000. Predicting delays 1-2 weeks ahead allows mitigation before impact.

#### Data Profile

| Attribute | Value |
|-----------|-------|
| **Primary Table** | `gr_header` + `po_line_item` |
| **Join Tables** | `po_header`, `vendor_master`, `material_master`, `source_list` |
| **Label** | Binary: `actual_delivery_date > requested_delivery_date` (derived from `po_line_item` dates) |
| **Positive Rate** | Driven by vendor OTD rates; ~10-25% of deliveries are late |
| **Row Count (1x)** | ~350 GRs |
| **Row Count (10x)** | ~3,500 GRs |

#### Approach

**Predictive AI:**

Binary classification (on-time vs. late) or regression (predicted delay in days).

- Baseline: Logistic regression on `vendor.on_time_delivery_rate` + `material.default_lead_time_days`
- Target: XGBoost with vendor-material pair performance, seasonal features, and order characteristics

**GenAI:**

- **Delay risk narrative:** "PO-000234 to VND-EVE for battery cells has a 73% probability of late delivery. VND-EVE's actual OTD rate is 78%, and this order's quantity (3,000 units) exceeds their typical batch size. Suggested actions: (1) confirm shipment date with vendor, (2) alert production planning of 5-7 day potential delay."
- **Expediting email draft:** Auto-generate vendor communication requesting shipment status update.

#### Feature Engineering

**From Feature Store:**
- Vendor Historical Performance (3.2): `v_on_time_delivery_actual`, `v_avg_delivery_delay_days`
- Vendor-Material Pair Performance (3.8): `vm_avg_delivery_delay`, `vm_order_count`
- Vendor Geographic Risk (3.9): `vg_region`, `vg_cross_border`

**Use-Case-Specific Features:**

| Feature | Computation | Rationale |
|---------|-------------|-----------|
| `uc05_lead_time_ratio` | source_list.lane_lead_time_days / material.default_lead_time_days | Vendor-specific vs. standard lead time |
| `uc05_order_qty_vs_avg` | po_line.quantity / AVG(quantity for this vendor+material) | Large orders may take longer |
| `uc05_vendor_otd_rate` | vendor_master.on_time_delivery_rate | Direct OTD signal |
| `uc05_is_rush_order` | 1 if po_type = RUSH | Rush orders may have tighter deadlines |
| `uc05_month_of_order` | MONTH(po_date) | Seasonal effects (if enriched) |
| `uc05_vendor_current_load` | COUNT(open POs) for vendor at po_date | High load increases delay risk |

#### ML Lifecycle Notes

- **Current limitation:** Delivery delay is a direct Bernoulli draw from `vendor.on_time_delivery_rate` (`goods_receipts.py:57`). A single feature achieves near-perfect prediction. Generator enrichment (Level 2-3) is needed for meaningful ML.
- **Primary metric:** Recall (missing a late delivery is costlier than a false alarm). Target Recall > 0.80.
- **Inference pattern:** Near-real-time -- score at PO creation, update as delivery date approaches.

#### Demo Scenario

Production planner Kenji receives a daily delay risk report. Three POs are flagged as high-risk: all to VND-EVE for battery cells, with predicted delays of 3-7 days. The GenAI module drafts an expediting email to EVE's account manager and suggests re-routing one order to VND-CATL under existing contract CTR-00002. Kenji approves the re-route, preventing a 2-day production line stoppage.

---

### UC-06: Contract Expiry and Renewal Prediction

#### Problem Statement

Contracts expiring without renewal force emergency off-contract purchases at higher prices. Predicting which contracts need renewal attention and when allows strategic renegotiation.

**Business Value:** Unplanned contract lapses increase procurement costs by 15-30% on affected materials. Proactive renewal ensures pricing continuity.

#### Data Profile

| Attribute | Value |
|-----------|-------|
| **Primary Table** | `contract_header` |
| **Join Tables** | `contract_item`, `po_line_item`, `vendor_master`, `material_master` |
| **Label** | Binary: contract needs urgent renewal (valid_to within 60 days + high consumption rate) |
| **Row Count (1x)** | ~40 contracts |
| **Row Count (10x)** | ~400 contracts |

#### Approach

**Predictive AI:**

Classification: will this contract lapse without renewal? Features combine time-to-expiry, consumption rate, and vendor/material importance.

- Baseline: Rule-based: flag contracts expiring within 90 days with >70% consumption
- Target: XGBoost predicting renewal priority score incorporating vendor performance and material criticality

**GenAI:**

- **Renewal brief:** "Contract CTR-00003 with NIDEC-JP for 200W motors expires in 45 days. Current consumption: 420/500 units (84%). At the current order rate of 70 units/month, the contract will be fully consumed 15 days before expiry. Recommended: initiate renewal with 20% volume increase. NIDEC-JP's quality score (88) and OTD (94%) support continued partnership."
- **Negotiation preparation:** Generate a summary of vendor performance during the contract period, benchmark pricing, and alternative vendor options.

#### Feature Engineering

**From Feature Store:**
- Contract Status (3.6): `c_days_to_expiry`, `c_consumption_pct`, `c_remaining_quantity`, `c_consumption_rate_monthly`

**Use-Case-Specific Features:**

| Feature | Computation | Rationale |
|---------|-------------|-----------|
| `uc06_days_to_expiry` | contract_header.valid_to - CURRENT_DATE | Primary urgency signal |
| `uc06_consumption_velocity` | consumed_quantity / months_active | Will contract be consumed before expiry? |
| `uc06_estimated_exhaust_date` | valid_from + (consumed/total * contract_duration) extrapolated | Projected exhaustion |
| `uc06_material_criticality_max` | MAX(material.criticality) across contract items | HIGH criticality = more urgent |
| `uc06_alternative_vendor_count` | COUNT(DISTINCT vendor_id from source_list) for contract materials | Fewer alternatives = higher renewal urgency |
| `uc06_vendor_performance_score` | Weighted average of OTD + quality + match rate | Good vendors warrant renewal |

#### ML Lifecycle Notes

- **Small dataset:** Only 40 contracts at 1x. This is better suited to rule-based systems at low scale. ML becomes viable at 10x (400 contracts).
- **Primary metric:** Recall -- missing a contract that should be renewed is costly.
- **Inference pattern:** Batch -- weekly contract portfolio review.

#### Demo Scenario

Category manager Elena reviews the monthly contract renewal dashboard. CTR-00003 (NIDEC-JP, 200W motors) is highlighted as URGENT: 84% consumed with 45 days remaining. The GenAI module produces a renewal brief comparing NIDEC-JP's performance to market benchmarks, noting their 94% OTD rate exceeds the 88% fleet average. Elena initiates renewal negotiations with a prepared position, securing continuity at a 3% volume discount.

---

### UC-07: Payment Timing Optimization

#### Problem Statement

Optimizing payment timing balances early payment discounts (e.g., 2/10 NET30) against cash flow preservation. Predicting the optimal payment date per invoice maximizes financial efficiency.

**Business Value:** Organizations with 2/10 NET30 terms can earn an annualized 36% return by consistently taking early payment discounts. Conversely, paying too early on non-discount invoices ties up working capital unnecessarily.

#### Data Profile

| Attribute | Value |
|-----------|-------|
| **Primary Table** | `payment` |
| **Join Tables** | `payment_invoice_link`, `invoice_header`, `vendor_master` |
| **Label** | Regression: optimal payment date (days before/after due date) |
| **Alternative Label** | Classification: EARLY (discount), ON_TIME, LATE |
| **Row Count (1x)** | ~280 payments |
| **Row Count (10x)** | ~2,800 payments |

#### Approach

**Predictive AI:**

Classification (early/on-time/late) or regression (days offset from due date).

- Baseline: Rule-based: if payment_terms = "2/10NET30" then pay within 10 days, else pay at due date
- Target: Optimization model balancing discount capture, cash flow, and vendor relationship value

**GenAI:**

- **Payment recommendation:** "Invoice INV-000023 from NIDEC-JP: payment terms 2/10NET30. Discount window closes in 3 days. Discount value: $170. Recommendation: PAY EARLY. NIDEC-JP is a strategic vendor (quality: 88, 3 active contracts)."
- **Cash flow narrative:** "Paying early on 12 discount-eligible invoices this week captures $2,340 in discounts against a 10-day cash advance of $117,000 (annualized return: 36.5%)."

#### Feature Engineering

**From Feature Store:**
- Vendor Invoice Behavior (3.3): `v_avg_invoice_to_payment_days`
- Price Benchmarks (3.5): `p_avg_unit_price` (invoice value context)

**Use-Case-Specific Features:**

| Feature | Computation | Rationale |
|---------|-------------|-----------|
| `uc07_has_early_discount` | 1 if payment_terms starts with discount (e.g., "2/10NET30") | Primary driver of early payment |
| `uc07_discount_pct` | Extract from payment_terms (e.g., 2%) | Discount magnitude |
| `uc07_discount_window_remaining` | discount_days - (CURRENT_DATE - invoice_date) | Urgency of discount capture |
| `uc07_invoice_amount` | invoice_header.total_net_amount | Large invoices = larger discount value |
| `uc07_vendor_strategic_score` | f(preferred_flag, contract_count, quality_score) | Strategic vendors warrant faster payment |
| `uc07_payment_block` | invoice_header.payment_block | Blocked invoices can't be paid regardless |

#### ML Lifecycle Notes

- **Current limitation:** Payment timing is drawn from three hard probability buckets (12% early, 75% on-time, 13% late) with no feature dependence (`payments.py:37-46`). Enrichment needed.
- **Primary metric:** Financial metric: total discount captured + cash flow cost.
- **Inference pattern:** Batch -- daily payment run optimization.

#### Demo Scenario

Treasury manager Akiko reviews the daily payment optimization dashboard. The system recommends paying 8 of 15 eligible invoices early, capturing $3,200 in discounts. For 3 invoices from NIDEC-JP, the GenAI module notes: "These invoices are under 2/10NET30 terms. Paying within the discount window saves $510. NIDEC-JP is a preferred vendor with 3 active contracts -- timely payment strengthens the relationship." Akiko approves the batch with one click.

---

### UC-08: Spend Concentration Risk Assessment

#### Problem Statement

Over-reliance on a single vendor or vendor group for critical materials creates supply chain fragility. Identifying concentration risk across vendors, legal entities, and geographies enables diversification strategies.

**Business Value:** The 2020-2023 supply chain disruptions showed that companies with diversified supplier bases recovered 2-3x faster. Concentration risk assessment is a key resilience metric.

#### Data Profile

| Attribute | Value |
|-----------|-------|
| **Primary Table** | `po_line_item` (aggregated) |
| **Join Tables** | `po_header`, `vendor_master`, `legal_entity`, `material_master`, `category_hierarchy`, `source_list` |
| **Label** | Risk score (regression) or risk tier (LOW/MEDIUM/HIGH/CRITICAL) |
| **Row Count (1x)** | Aggregated to ~120 vendor x category combinations |
| **Row Count (10x)** | ~1,200 combinations |

#### Approach

**Predictive AI:**

Compute Herfindahl-Hirschman Index (HHI) per material/category, then classify concentration risk.

- Baseline: HHI calculation + threshold rules (HHI > 0.25 = concentrated)
- Target: Multi-factor model incorporating HHI + legal entity linkage + geographic concentration + material criticality

**GenAI:**

- **Concentration report:** "Motor category (MOTN) has HIGH concentration risk. HHI = 0.42. VND-NIDEC-JP and VND-NIDEC-MY together account for 78% of motor spend, and both share legal entity LE-NIDEC (alias group ALIAS-001). A disruption at NIDEC would impact 78% of motor supply. Recommendation: qualify an alternative motor supplier from a different legal entity."
- **Scenario analysis:** "If NIDEC operations in Japan are disrupted, the impact covers $450K in annual spend across 3 materials. The Malaysia entity (VND-NIDEC-MY) may also be affected due to shared legal entity."

#### Feature Engineering

**From Feature Store:**
- Vendor Composite Profile (3.1): `v_preferred`, `v_status_encoded`
- Contract Status (3.6): `c_is_active`, `c_days_to_expiry`
- Category Spend Profile (3.7): `cat_total_spend`, `cat_vendor_count`
- Vendor Geographic Risk (3.9): `vg_region`, `vg_alias_group`

**Use-Case-Specific Features:**

| Feature | Computation | Rationale |
|---------|-------------|-----------|
| `uc08_hhi_by_material` | SUM(vendor_share^2) per material | Vendor concentration per material |
| `uc08_hhi_by_category` | SUM(vendor_share^2) per category | Category-level concentration |
| `uc08_hhi_by_legal_entity` | SUM(le_share^2) per material (using legal_entity_id) | True concentration after alias resolution |
| `uc08_top1_vendor_share` | MAX(vendor_spend / total_spend) per material | Single-vendor dependency |
| `uc08_geographic_hhi` | SUM(country_share^2) per material | Geographic concentration |
| `uc08_material_criticality` | material_master.criticality | HIGH criticality + HIGH concentration = CRITICAL risk |
| `uc08_source_list_depth` | COUNT(source_list entries) per material+plant | More sources = more resilience |

#### ML Lifecycle Notes

- **Aggregation level:** This is primarily an analytics/aggregation use case, not row-level prediction. ML adds value by weighting multiple risk dimensions.
- **Entity resolution:** The `alias_group` field links VND-NIDEC-JP and VND-NIDEC-MY to the same legal entity. Models must use `legal_entity_id` for true concentration, not just `vendor_id`.
- **Primary metric:** Coverage of actual high-risk concentrations identified by domain experts.
- **Inference pattern:** Batch -- monthly strategic review.

#### Demo Scenario

Chief Procurement Officer Michael reviews the quarterly concentration risk report. The system highlights MOTN (motors) as CRITICAL: HHI of 0.42 at vendor level, rising to 0.61 at legal entity level after NIDEC alias resolution. The GenAI module generates a diversification roadmap: "Phase 1: Qualify one alternative motor supplier (target: 3 months). Phase 2: Shift 20% of NIDEC volume to new supplier. Phase 3: Establish secondary source list for all HIGH criticality motor materials." The report includes 3 candidate vendors from the MOTN category with their quality and OTD benchmarks.

---

## 7. Tier 3: Aspirational Use Cases

### UC-09: Goods Receipt Quality Prediction

#### Problem Statement

Predicting which incoming shipments are likely to have quality issues (rejections) allows targeted inspection, reducing both quality escapes and unnecessary 100% inspection costs.

**Business Value:** Quality inspections cost $15-50 per GR. Risk-based inspection (inspect high-risk, skip-lot low-risk) can reduce inspection costs by 40% while maintaining quality levels.

#### Data Profile

| Attribute | Value |
|-----------|-------|
| **Primary Table** | `gr_line_item` |
| **Join Tables** | `gr_header`, `po_header`, `po_line_item`, `vendor_master`, `material_master` |
| **Label** | Binary: `quantity_rejected > 0` |
| **Positive Rate** | Derived from vendor quality_score; varies by vendor |
| **Row Count (1x)** | ~350+ GR line items |
| **Row Count (10x)** | ~3,500+ GR line items |

#### Approach

**Predictive AI:**

Binary classification: will this GR have quality rejections?

- Baseline: Logistic regression on `vendor.quality_score`
- Target: XGBoost with vendor-material pair history, material characteristics, and seasonal patterns

**GenAI:**

- **Inspection recommendation:** "GR for PO-000345 from VND-EVE (battery cells): 68% rejection probability. VND-EVE quality score is 65, and their rejection rate for MAT-BAT-CELL is 12%. Recommend: full inspection with focus on EXPIRED and DEFECTIVE categories."
- **Root cause analysis:** "VND-EVE's rejection rate has increased from 5% to 12% over the last quarter, primarily driven by EXPIRED items. This may indicate inventory management issues at the supplier."

#### Feature Engineering

**From Feature Store:**
- Vendor Composite Profile (3.1): `v_status_encoded`
- Vendor Historical Performance (3.2): `v_rejection_rate`
- Material Risk Profile (3.4): `m_criticality_ordinal`, `m_hazmat`, `m_type_encoded`
- Vendor-Material Pair Performance (3.8): `vm_rejection_rate`, `vm_order_count`

**Use-Case-Specific Features:**

| Feature | Computation | Rationale |
|---------|-------------|-----------|
| `uc09_vendor_quality_score` | vendor_master.quality_score | Direct quality indicator |
| `uc09_vendor_quality_tier` | Binned: HIGH(>85), MEDIUM(70-85), LOW(<70) | Non-linear quality effect |
| `uc09_is_hazmat` | material_master.hazmat_flag | Hazmat materials may have stricter quality |
| `uc09_order_qty_vs_lot_size` | po_line.quantity / material_plant.lot_size | Over-lot-size orders may have different quality |
| `uc09_gr_sequence_for_vendor` | Sequential GR number per vendor | Newer vendors may have quality learning curve |
| `uc09_days_since_last_rejection` | Days since vendor's last rejected GR | Recent rejections predict future ones |

#### ML Lifecycle Notes

- **Current limitation:** Rejection probability is `1 - quality_score/100` (`goods_receipts.py:90-91`), a direct function of a single feature. Generator enrichment needed (Level 2: material criticality interaction).
- **Primary metric:** F1-Score -- balance between catching rejections and avoiding unnecessary inspections.
- **Inference pattern:** Near-real-time -- score when PO is about to be delivered.

#### Demo Scenario

Quality manager Tomoko reviews the incoming shipment risk dashboard. A battery cell shipment from VND-EVE is flagged as HIGH risk (78% rejection probability). The system recommends full inspection instead of skip-lot, and the GenAI module explains: "EVE's last 3 shipments had a 15% rejection rate, primarily EXPIRED battery cells. This shipment's quantity (2,500 units) is 25% above their typical batch, which historically correlates with higher defect rates." Tomoko assigns two inspectors instead of one, catching a 10% defective batch before it reaches the production line.

---

### UC-10: Purchase Requisition Priority Scoring

#### Problem Statement

Not all PRs are equally urgent. Automatically scoring PR priority based on material criticality, current inventory signals, and production schedule impact helps purchasing teams focus on the most impactful requisitions first.

**Business Value:** Processing HIGH-priority PRs 2 days faster prevents production stoppages. Automated prioritization ensures critical materials are sourced before routine supplies.

#### Data Profile

| Attribute | Value |
|-----------|-------|
| **Primary Table** | `pr_header` + `pr_line_item` |
| **Join Tables** | `material_master`, `material_plant_extension`, `cost_center` |
| **Label** | `pr_header.priority` (ordinal: LOW/MEDIUM/HIGH/CRITICAL) |
| **Row Count (1x)** | ~500 PRs |
| **Row Count (10x)** | ~5,000 PRs |

#### Approach

**Predictive AI:**

Ordinal classification or learning-to-rank.

- Baseline: Rule-based: HIGH criticality + URGENT type = CRITICAL priority
- Target: Learning-to-rank model considering material criticality, lead time pressure, cost center importance, and PR age

**GenAI:**

- **Priority justification:** "PR-00234 is scored CRITICAL: MAT-LIDAR-2D (HIGH criticality, safety-critical) requested by Production Engineering at plant MY01. Current lead time is 28 days and requested delivery is in 21 days. This PR requires immediate vendor engagement."
- **Workflow routing:** "Route this PR directly to Purchasing Group PG-ELEC for expedited processing. Skip standard 3-day approval queue."

#### Feature Engineering

**From Feature Store:**
- Material Risk Profile (3.4): `m_criticality_ordinal`, `m_lead_time_days`, `m_standard_cost`
- Category Spend Profile (3.7): `cat_material_count`

**Use-Case-Specific Features:**

| Feature | Computation | Rationale |
|---------|-------------|-----------|
| `uc10_pr_type_encoded` | pr_header.pr_type (STANDARD/URGENT/BLANKET) | URGENT PRs get higher priority |
| `uc10_lead_time_gap` | requested_delivery_date - pr_date - default_lead_time_days | Negative = already behind schedule |
| `uc10_material_criticality` | material_master.criticality | HIGH criticality = higher priority |
| `uc10_estimated_value` | pr_line.estimated_price * quantity | Higher value = higher priority |
| `uc10_department` | pr_header.requester_department | Production departments may have higher urgency |
| `uc10_open_po_exists` | 1 if any open PO for same material+plant | Existing coverage reduces urgency |

#### ML Lifecycle Notes

- **Ordinal label:** Use ordinal regression or treat as multi-class with ordinal weighting.
- **Primary metric:** Weighted Kappa (accounts for ordinal misclassification distance).
- **Inference pattern:** Near-real-time -- score at PR creation.

#### Demo Scenario

Buyer Chen opens the PR queue, now sorted by ML-predicted priority instead of FIFO. The top PR is for LiDAR sensors (MAT-LIDAR-2D, CRITICAL priority) from the production engineering team, with a lead time gap of -7 days (already behind). The GenAI module explains the urgency and pre-populates the PO with the preferred vendor (VND-HOKUYO) and contract price from CTR-00001. Chen creates the PO in 2 clicks instead of the usual 15-minute sourcing process.

---

### UC-11: Duplicate Invoice Detection

#### Problem Statement

Duplicate invoices -- whether from vendor error or fraud -- result in overpayment. Detecting duplicates before payment prevents financial loss and strengthens vendor management.

**Business Value:** Industry studies show 0.1-0.5% of invoices are duplicates. At scale, this represents significant overpayment risk.

#### Data Profile

| Attribute | Value |
|-----------|-------|
| **Primary Table** | `invoice_header` |
| **Join Tables** | `invoice_line_item`, `vendor_master` |
| **Label** | Binary: is_duplicate (no labeled duplicates in current data) |
| **Row Count (1x)** | ~320 invoices |
| **Row Count (10x)** | ~3,200 invoices |

#### Approach

**Predictive AI:**

Similarity-based detection: identify invoice pairs that are suspiciously similar.

- Baseline: Exact match on (vendor_id, total_gross_amount, invoice_date) within 7-day window
- Target: Fuzzy matching model using embedding similarity on invoice features; flag pairs above threshold

**GenAI:**

- **Duplicate analysis:** "Invoice INV-000156 and INV-000161 are potential duplicates: same vendor (VND-MOLEX-SG), same amount ($9,700), same PO reference (PO-000038), invoiced 3 days apart. Vendor invoice numbers differ (VIN-MOLEX-0156 vs VIN-MOLEX-0161). Recommend: contact vendor to confirm."
- **Vendor communication:** Auto-draft an email to the vendor requesting clarification on the potential duplicate.

#### Feature Engineering

**From Feature Store:**
- Vendor Invoice Behavior (3.3): `v_avg_invoice_to_payment_days` (duplicate vendors may invoice more frequently)

**Use-Case-Specific Features:**

| Feature | Computation | Rationale |
|---------|-------------|-----------|
| `uc11_same_vendor_same_amount` | COUNT of invoices with matching (vendor_id, total_gross_amount) within 30 days | Core duplicate signal |
| `uc11_same_po_reference` | COUNT of invoices referencing same po_id within 30 days | Same PO invoiced twice |
| `uc11_invoice_number_similarity` | Levenshtein distance on vendor_invoice_number | Typos in re-submitted invoices |
| `uc11_amount_deviation` | ABS(inv1.amount - inv2.amount) / inv1.amount for pairs | Near-duplicate amounts |
| `uc11_date_gap_days` | ABS(inv1.invoice_date - inv2.invoice_date) | Duplicates usually within 1-7 days |
| `uc11_line_item_overlap` | Jaccard similarity of (material_id, quantity) across lines | Same materials = more suspicious |

#### ML Lifecycle Notes

- **No labeled data:** Current generator does not produce duplicate invoices. This is a record-linkage / pairwise comparison problem.
- **Generator enhancement needed:** Inject ~0.5% duplicate invoices (same vendor, similar amounts, close dates) with known labels.
- **Primary metric:** Precision -- false positives waste AP time investigating non-duplicates.
- **Inference pattern:** Batch -- run after daily invoice ingestion.

#### Demo Scenario

The nightly duplicate scan flags 2 invoice pairs. AP supervisor Maya reviews the top pair: two invoices from MOLEX-SG for identical amounts referencing the same PO, invoiced 3 days apart. The GenAI module notes: "This vendor has submitted dual invoices once before (6 months ago). The vendor_invoice_numbers differ by one digit, suggesting a re-submission. Recommend: hold INV-000161 and contact vendor." Maya places a payment block and sends the auto-drafted clarification email.

---

### UC-12: Spend Classification and Categorization

#### Problem Statement

Miscategorized spend obscures procurement analytics. Automatically classifying PO line items into the correct category hierarchy improves spend visibility and enables accurate category management.

**Business Value:** Up to 30% of procurement spend is "tail spend" that may be miscategorized. Correct classification enables better negotiation leverage and contract coverage.

#### Data Profile

| Attribute | Value |
|-----------|-------|
| **Primary Table** | `po_line_item` |
| **Join Tables** | `material_master`, `category_hierarchy` |
| **Label** | `material_master.category_id` (hierarchical: level 1/2/3) |
| **Row Count (1x)** | ~400+ PO lines, ~51 leaf categories |
| **Row Count (10x)** | ~4,000+ PO lines |

#### Approach

**Predictive AI:**

Hierarchical multi-class classification.

- Baseline: Lookup from material_master (already correctly mapped in generated data)
- Target: Text-based classifier using `material_master.description` to predict category_id -- useful for new/unclassified materials

**GenAI:**

- **Classification suggestion:** "New material 'Brushless DC Motor 400W 48V' is most likely in category MOTN > Motors > Servo Motors (confidence: 89%). Alternative: MOTN > Motors > DC Motors (confidence: 78%). Select the correct classification."
- **Category insights:** "The Servo Motors category has 15 materials from 8 vendors. Average spend: $12,000/month. Contract coverage: 65%."

#### Feature Engineering

**From Feature Store:**
- Material Risk Profile (3.4): `m_type_encoded`, `m_criticality_ordinal`
- Category Spend Profile (3.7): `cat_material_count`, `cat_vendor_count`

**Use-Case-Specific Features:**

| Feature | Computation | Rationale |
|---------|-------------|-----------|
| `uc12_description_embedding` | Text embedding of material_master.description | Semantic similarity to category |
| `uc12_material_type` | material_master.material_type | COMPONENT, RAW, etc. correlate with categories |
| `uc12_standard_cost_range` | Binned standard_cost | Cost range varies by category |
| `uc12_uom` | material_master.base_uom | UOM is category-indicative (EA for components, KG for raw) |
| `uc12_vendor_categories` | Mode(vendor_category.category_id) for vendors supplying this material | Vendor's category hints at material category |

#### ML Lifecycle Notes

- **Label quality:** Generated data has perfect categorization (material -> category is deterministic). Useful for model training but doesn't test real-world misclassification.
- **Text model:** Best suited for GenAI / embedding-based models that can generalize to unseen material descriptions.
- **Primary metric:** Top-3 accuracy (correct category in top 3 predictions).
- **Inference pattern:** On-demand -- classify when new material is created.

#### Demo Scenario

A new material request arrives: "Harmonic drive reducer 50:1 ratio for AMR joint actuator." The system classifies it as MOTN > Actuators (92% confidence). The GenAI module adds: "This material is similar to 5 existing harmonic drive materials in the Actuators category. Suggested standard cost range: $180-320 based on similar items. Recommended vendors: 3 vendors currently supply this category with quality scores above 85."

---

### UC-13: Confidentiality Tier Prediction

#### Problem Statement

Assigning the correct confidentiality tier (PUBLIC, INTERNAL, RESTRICTED) to materials, vendors, and source list entries is critical for data governance. Predicting the appropriate tier automates a manual classification process.

**Business Value:** Incorrect confidentiality classification exposes sensitive data (vendor bank accounts, pricing) or over-restricts access to public information, slowing procurement processes.

#### Data Profile

| Attribute | Value |
|-----------|-------|
| **Primary Table** | `material_master` or `source_list` |
| **Join Tables** | `vendor_master`, `contract_header` |
| **Label** | `confidentiality_tier` (ordinal: PUBLIC/INTERNAL/RESTRICTED) |
| **Row Count (1x)** | ~800 materials + ~120 vendors + source list entries |
| **Row Count (10x)** | ~8,000 + ~1,200 |

#### Approach

**Predictive AI:**

Ordinal classification.

- Baseline: Rule-based: hazmat_flag -> RESTRICTED; SERVICE type -> PUBLIC; else INTERNAL
- Target: Multi-class classifier using material attributes, vendor sensitivity, and contract terms

**GenAI:**

- **Classification rationale:** "Material MAT-BAT-CELL is classified RESTRICTED because: (1) it contains lithium (hazmat_flag=True), (2) supplier pricing is competitively sensitive, (3) the material is used in a safety-critical application (criticality=HIGH)."
- **Policy compliance check:** "Source list entry for MAT-LIDAR-2D at plant MY01 is PUBLIC, but the vendor (VND-HOKUYO) is INTERNAL. Per confidentiality propagation rules, the source list entry should inherit INTERNAL. Flag for review."

#### Feature Engineering

**From Feature Store:**
- Material Risk Profile (3.4): `m_criticality_ordinal`, `m_hazmat`, `m_type_encoded`, `m_confidentiality_ordinal`

**Use-Case-Specific Features:**

| Feature | Computation | Rationale |
|---------|-------------|-----------|
| `uc13_is_hazmat` | material_master.hazmat_flag | Hazmat often restricted |
| `uc13_material_type` | material_master.material_type | SERVICE type less sensitive |
| `uc13_vendor_tier` | vendor_master.confidentiality_tier | Vendor tier propagates to source list |
| `uc13_has_bank_info` | 1 if entity has bank_account field | Bank info always RESTRICTED |
| `uc13_criticality` | material_master.criticality | HIGH criticality may need RESTRICTED |
| `uc13_contract_exists` | 1 if active contract for this material | Contract pricing is sensitive |

#### ML Lifecycle Notes

- **Propagation rules:** The generator already propagates confidentiality (Stage 8: `propagate_confidentiality`). ML adds value for initial tier assignment, not propagation.
- **Class distribution:** Heavily skewed toward INTERNAL. Use class weights or focal loss.
- **Primary metric:** Weighted F1 with higher weight on RESTRICTED misclassification.
- **Inference pattern:** On-demand -- classify at entity creation time.

#### Demo Scenario

Master data governance analyst Priya reviews the automated confidentiality tier assignments for 50 new materials. The ML model assigns RESTRICTED to 3 battery-related materials (all hazmat), INTERNAL to 42 standard components, and PUBLIC to 5 MRO items. The GenAI module flags one discrepancy: "MAT-CTRL-PLC is assigned PUBLIC but references a vendor (VND-SIEMENS) with INTERNAL tier. Recommend upgrading to INTERNAL per propagation policy." Priya confirms the upgrade, and the system updates the source list entries automatically.

---

## 8. Cross-Reference Matrices

### 8.1 Feature Store Usage Matrix

| | VP (3.1) | VHP (3.2) | VIB (3.3) | MRP (3.4) | PB (3.5) | CS (3.6) | CSP (3.7) | VMPP (3.8) | VGR (3.9) |
|---|---|---|---|---|---|---|---|---|---|
| **UC-01 Maverick** | X | | | X | X | X | | | |
| **UC-02 Invoice** | X | X | X | | X | | | | |
| **UC-03 Vendor Risk** | X | X | X | | | | | | X |
| **UC-04 Price Anomaly** | | | | X | X | X | X | | |
| **UC-05 Delivery** | | X | | | | | | X | X |
| **UC-06 Contract** | | | | | | X | | | |
| **UC-07 Payment** | | | X | | X | | | | |
| **UC-08 Concentration** | X | | | | | X | X | | X |
| **UC-09 GR Quality** | X | X | | X | | | | X | |
| **UC-10 PR Priority** | | | | X | | | X | | |
| **UC-11 Duplicate Inv** | | | X | | | | | | |
| **UC-12 Spend Class** | | | | X | | | X | | |
| **UC-13 Confidentiality** | | | | X | | | | | |

**Feature Group Legend:** VP=Vendor Profile, VHP=Vendor Historical Perf, VIB=Vendor Invoice Behavior, MRP=Material Risk Profile, PB=Price Benchmarks, CS=Contract Status, CSP=Category Spend Profile, VMPP=Vendor-Material Pair Perf, VGR=Vendor Geographic Risk

### 8.2 Table Dependency Matrix

| Table | UC-01 | UC-02 | UC-03 | UC-04 | UC-05 | UC-06 | UC-07 | UC-08 | UC-09 | UC-10 | UC-11 | UC-12 | UC-13 |
|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|
| `vendor_master` | X | X | X | X | X | X | X | X | X | | X | | X |
| `material_master` | X | | | X | X | X | | X | X | X | | X | X |
| `po_header` | X | X | X | X | X | | | X | X | | | | |
| `po_line_item` | X | X | | X | X | X | | X | X | | | X | |
| `gr_header` | | | X | | X | | | | X | | | | |
| `gr_line_item` | | X | X | | X | | | | X | | | | |
| `invoice_header` | | X | X | | | | X | | | | X | | |
| `invoice_line_item` | | X | | | | | | | | | X | | |
| `contract_header` | X | | | X | | X | | X | | | | | |
| `contract_item` | X | | | X | | X | | | | | | | |
| `source_list` | X | | | | | | | X | | | | | X |
| `payment` | | | | | | | X | | | | | | |
| `legal_entity` | | | X | | | | | X | | | | | |
| `category_hierarchy` | | | | | | | | X | | | | X | |
| `pr_header` | | | | | | | | | | X | | | |
| `pr_line_item` | | | | | | | | | | X | | | |
| `vendor_category` | X | | X | | | | | X | | | | | |
| `vendor_address` | | | X | | | | | | | | | | |

### 8.3 Deployment Pattern Matrix

| Use Case | Batch | Near-Real-Time | On-Demand |
|----------|-------|----------------|-----------|
| UC-01 Maverick Detection | | X | |
| UC-02 Invoice Match | | X | |
| UC-03 Vendor Risk | X | | |
| UC-04 Price Anomaly | X | | X |
| UC-05 Delivery Delay | | X | |
| UC-06 Contract Expiry | X | | |
| UC-07 Payment Timing | X | | |
| UC-08 Concentration Risk | X | | |
| UC-09 GR Quality | | X | |
| UC-10 PR Priority | | X | |
| UC-11 Duplicate Invoice | X | | |
| UC-12 Spend Classification | | | X |
| UC-13 Confidentiality | | | X |

### 8.4 Scale Readiness Matrix

| Use Case | 1x (Prototype) | 3x (Viable) | 10x (Production) | Notes |
|----------|:-:|:-:|:-:|-------|
| UC-01 Maverick | Limited | OK | Best | Only ~20-32 positives at 1x |
| UC-02 Invoice Match | OK | Best | Best | 15-20% positive rate helps |
| UC-03 Vendor Risk | Limited | Limited | OK | Only 120 vendors at 1x |
| UC-04 Price Anomaly | OK | Best | Best | Unsupervised, less data-hungry |
| UC-05 Delivery Delay | OK | Best | Best | Signal exists but is trivial |
| UC-06 Contract Expiry | Limited | Limited | OK | Only 40 contracts at 1x |
| UC-07 Payment Timing | OK | Best | Best | 280 payments at 1x |
| UC-08 Concentration | OK | OK | Best | Aggregation-based, works at any scale |
| UC-09 GR Quality | OK | Best | Best | Signal is trivial without enrichment |
| UC-10 PR Priority | OK | Best | Best | 500 PRs at 1x |
| UC-11 Duplicate Inv | N/A | N/A | N/A | No duplicates in generated data |
| UC-12 Spend Class | OK | Best | Best | 51 categories, enough for hierarchy |
| UC-13 Confidentiality | OK | OK | Best | Few RESTRICTED examples |

---

## 9. GenAI Integration Patterns

### 9.1 RAG Patterns for Procurement Policy Retrieval

**Architecture:** Vector database (HANA Cloud Vector Engine) containing procurement policy documents, contract terms, and approval workflows. Retrieved context is injected into LLM prompts alongside prediction results.

**Application Areas:**

| Pattern | Context Retrieved | Use Cases |
|---------|------------------|-----------|
| **Policy compliance check** | Relevant procurement policies for the transaction type, amount, and category | UC-01 (maverick justification), UC-08 (sourcing requirements) |
| **Contract terms lookup** | Contract clauses for pricing, delivery, and quality obligations | UC-02 (tolerance terms), UC-06 (renewal conditions) |
| **Approval routing** | Approval matrix based on amount thresholds and category | UC-10 (PR routing), UC-01 (escalation rules) |
| **Regulatory compliance** | Hazmat handling regulations, export control rules | UC-13 (confidentiality policy), UC-09 (inspection requirements) |

**Implementation Pattern:**

```
User Query: "Why is PO-000028 flagged as maverick?"
  -> ML Model: maverick_probability = 0.92, SHAP values = {...}
  -> RAG Retrieval: "Policy 4.2: All purchases > $5,000 without contract require VP approval"
  -> RAG Retrieval: "Source List: MAT-MOT-400W has 2 approved vendors"
  -> LLM Generation: Natural language explanation combining ML output + policy context
```

### 9.2 Explanation Generation Patterns

**Template-Augmented Generation:**

For each use case, define a structured template that the LLM fills with prediction details, feature impacts, and contextual data:

```
Template: Maverick Detection Explanation
---
PO {po_id} to {vendor_name} for {material_description} is flagged as {prediction}
with {confidence}% confidence.

Top contributing factors:
{for each top-3 SHAP feature}
- {feature_name}: {feature_value} (impact: {shap_value})
{end for}

Context:
- Contract status: {contract_status}
- Source list alternatives: {alternative_count} vendors available
- Historical pattern: {vendor_maverick_history}

Recommended action: {action_recommendation}
```

**Multi-Modal Explanations:**

Combine text explanations with:
- SHAP waterfall charts (force plots)
- Time-series price trend visualizations
- Vendor scorecard summaries

### 9.3 Conversational Procurement Agent Patterns

**Agent Architecture:**

A multi-tool LLM agent with access to:

| Tool | Description | Example Query |
|------|-------------|---------------|
| `query_vendor_profile` | Retrieve vendor master + performance metrics | "Tell me about NIDEC's delivery performance" |
| `query_material_info` | Retrieve material + sourcing details | "What are the sourcing options for LiDAR sensors?" |
| `query_contract_status` | Retrieve contract consumption and expiry | "How much is left on the HOKUYO contract?" |
| `run_prediction` | Execute ML model for a specific entity | "What's the maverick risk for this PO?" |
| `generate_report` | Create formatted procurement reports | "Generate a vendor risk summary for Q3" |
| `search_policies` | RAG search across procurement policies | "What's our policy on sole-source purchases?" |

**Conversation Flow Examples:**

```
User: "I need to order 200 units of MAT-MOT-400W. What are my options?"

Agent:
1. [query_material_info] -> MAT-MOT-400W: 400W brushless motor, HIGH criticality
2. [query_contract_status] -> No active contract for 400W variant
3. [query_vendor_profile] -> 2 vendors in MOTN category: NIDEC-JP (preferred), NIDEC-MY
4. [run_prediction: maverick_risk] -> 78% maverick risk if ordered without contract
5. [search_policies] -> Policy 4.2: >$5,000 requires contract or VP approval

Response: "MAT-MOT-400W (400W brushless motor) has no active contract.
Two vendors are available: NIDEC-JP and NIDEC-MY. Ordering without a
contract would flag as maverick (78% risk). I recommend either:
(1) Extend CTR-00003 to include the 400W variant, or
(2) Request VP approval for a one-time off-contract purchase.
Would you like me to draft the contract extension request?"
```

### 9.4 Cross-Cutting GenAI Demo Angles

| Demo Angle | Description | Use Cases Enhanced |
|------------|-------------|-------------------|
| **Smart alerts** | Natural-language alerts when ML models detect anomalies | UC-01, UC-02, UC-04, UC-11 |
| **Decision support** | Side-by-side comparison of options with AI analysis | UC-06, UC-07, UC-08 |
| **Report generation** | Automated procurement reports with narrative insights | UC-03, UC-08, UC-12 |
| **Process automation** | End-to-end workflow (detect -> explain -> act) | UC-01 (flag + explain + route), UC-02 (predict + resolve) |
| **Knowledge Q&A** | Free-form questions about procurement data and policies | All use cases |
| **What-if analysis** | "What if we lose this vendor?" scenario modeling | UC-03, UC-05, UC-08 |

---

## 10. Data Generator Enrichment Roadmap

This section analyzes current signal weaknesses and proposes enrichment strategies organized by signal complexity level.

### 10.1 Current Signal Assessment

The current generator produces signals that are **trivially separable** -- a single-feature threshold achieves near-perfect accuracy for most use cases:

| Use Case | Current Signal | Why It's Too Easy |
|----------|---------------|-------------------|
| Maverick detection | `unit_price / standard_cost > 1.15` | Fixed 1.20-1.50x multiplier (`purchase_orders.py:293`), no variance |
| Invoice match | `price_variance > 2%` | Hard-coded threshold at 2% / $0.50 (`invoices.py:168`) |
| Vendor risk | `quality_score < 72` | Static score, CONDITIONAL vendors always 55-72 (`vendors.py:175`) |
| Delivery delay | `vendor.on_time_delivery_rate` | Direct Bernoulli draw from the rate (`goods_receipts.py:57`) |
| GR quality | `vendor.quality_score` | Rejection prob = `1 - quality/100` (`goods_receipts.py:90-91`) |
| Payment timing | Three hard probability buckets | 12%/75%/13% with no feature dependence (`payments.py:37-46`) |

**Root causes:**

1. **Features are generated independently** -- no cross-feature correlations (e.g., `risk_score`, `quality_score`, and `esg_score` are each drawn from independent random distributions at `vendors.py:169-172`)
2. **Label fields are directly observable** -- `po_header.maverick_flag` and `po_header.notes` ("Maverick purchase") directly reveal maverick status; `invoice_header.match_status` directly reveals match outcome
3. **No temporal dynamics** -- vendor scores are static across the 18-month window; no drift, seasonality, or degradation
4. **No interaction effects** -- vendor quality x material criticality x lead time have no joint influence on outcomes
5. **Uniform noise** -- no outliers, no data quality issues, no missing-at-random patterns

### 10.2 Enrichment Strategies by Complexity Level

#### Level 1: Correlated Features (Simple Models Still Work, But Need Feature Engineering)

**Purpose:** Forces ML to combine 2-3 features instead of using one threshold.

**1a. Vendor Score Correlations**

Make `risk_score` inversely correlated with `quality_score` (r ~ -0.7 with noise). ML must learn the joint distribution, not just one score.

- **File:** `generators/vendors.py:169-171`
- **Current:** `risk = random.randint(10, 85)` and `quality = random.randint(60, 98)` drawn independently
- **Proposed:** `risk = max(10, min(85, 100 - quality + random.gauss(0, 10)))`

**1b. Invoice Variance ~ Vendor Quality**

Low-quality vendors produce more price/quantity variance. Variance standard deviation becomes a function of vendor quality.

- **File:** `generators/invoices.py:117-127`
- **Current:** Fixed `random.uniform(0.03, 0.12)` variance for all vendors
- **Proposed:** `variance_std = 0.08 * (1 - vendor.quality_score / 100)` -- high-quality vendors have tight pricing, low-quality have wide variance

**1c. Discount-Driven Payment Timing**

Early payments should correlate with 2/10NET30 terms (currently random).

- **File:** `generators/payments.py:37-46`
- **Current:** 12% early / 75% on-time / 13% late regardless of terms
- **Proposed:** If 2/10NET30: 40% early / 50% on-time / 10% late. Otherwise: 5% early / 80% on-time / 15% late.

#### Level 2: Interaction Effects (Tree Models Needed)

**Purpose:** Creates patterns that require feature interactions (XGBoost/Random Forest territory). Simple logistic regression fails because the decision boundary is non-linear.

**2a. Material Criticality x Vendor Quality -> Rejection Rate**

HIGH criticality materials from low-quality vendors have much higher rejection rates than either factor alone.

- **File:** `generators/goods_receipts.py:90-91`
- **Current:** `has_rejection = random.random() > quality_threshold` (quality only)
- **Proposed:** `rejection_prob = (1 - quality/100) * criticality_multiplier` where HIGH=2.0, MEDIUM=1.0, LOW=0.5

**2b. Material Criticality x Maverick Premium**

Maverick POs on HIGH criticality materials carry larger premiums (1.35-1.65x) vs LOW (1.05-1.25x).

- **File:** `generators/purchase_orders.py:293`
- **Current:** Fixed `random.uniform(1.20, 1.50)` regardless of material
- **Proposed:** HIGH: `uniform(1.35, 1.65)`, MEDIUM: `uniform(1.20, 1.50)`, LOW: `uniform(1.05, 1.25)`

**2c. Vendor Specialization x Material Category -> GR Quality**

Vendors perform better in their primary category. Creates a vendor-material interaction effect.

- **New concept:** Assign each vendor a primary category. When the PO material matches, apply quality bonus (+10 to quality_score for rejection calculation). When mismatched, apply penalty (-10).

**2d. Invoice Age x Payment Failure**

Old unpaid invoices are more likely to have payment failures.

- **File:** `generators/payments.py:63-65`
- **Current:** 3% failure rate, random
- **Proposed:** Failure rate = `0.03 + 0.02 * max(0, (days_since_invoice - 60) / 30)` -- invoices older than 60 days have escalating failure risk

**2e. Contract Proximity x Price Creep**

POs placed within 30 days of contract expiry have higher price variance.

- **File:** `generators/purchase_orders.py`
- **Proposed:** If PO date is within 30 days of contract.valid_to, apply `price * uniform(1.02, 1.08)` instead of exact contract price

#### Level 3: Temporal Dynamics (Sequence Models Needed)

**Purpose:** Patterns that only emerge over time -- rewards RNNs, LSTMs, or temporal feature engineering.

**3a. Vendor Quality Drift**

Vendor OTD and quality scores degrade 0.5-2% per quarter for 30% of vendors. Creates a learning-curve pattern.

- **File:** `generators/goods_receipts.py:56-76`
- **Proposed:** `effective_otd = vendor.otd_rate * (1 - drift_rate * quarters_elapsed)` where drift_rate is vendor-specific (0 for 70%, 0.005-0.02 for 30%)

**3b. Q4 Procurement Surge**

50% higher PO volumes in Oct-Dec. Creates seasonal patterns in maverick rates and delivery delays.

- **File:** `generators/purchase_orders.py`
- **Proposed:** Month-dependent volume multiplier: Q4 = 1.5x, Q1 = 0.8x, Q2-Q3 = 1.0x

**3c. Progressive Vendor Degradation**

First 3 invoices from a vendor are clean, then variance creeps up. Model must learn the vendor "honeymoon period."

- **File:** `generators/invoices.py`
- **Proposed:** Invoice sequence number within vendor drives variance probability. Invoices 1-3: 95% full match. Invoices 4+: standard 82% match rate.

**3d. Contract Expiry Rush**

Last 30 days before contract expiry see 2x volume as buyers rush to consume remaining quantity.

- **File:** `generators/purchase_orders.py`
- **Proposed:** When generating PO dates for contract-linked POs, weight the last 30 days of contract validity 2x higher

#### Level 4: Ambiguous Signals (Deep Learning / Ensemble Territory)

**Purpose:** Creates signal overlap that defeats single-model approaches. Requires sophisticated ensembles or deep architectures.

**4a. Camouflaged Mavericks**

10-15% of on-contract POs use contract pricing but go to non-preferred vendors. Looks legitimate but is policy-violating. Requires combining vendor preference + source list + contract data to detect.

**4b. Legitimate Off-Contract POs**

5% of off-contract POs are legitimate emergency stock purchases (HIGH criticality + URGENT PR). Model must distinguish justified vs. unjustified exceptions.

**4c. Alias Group Masking**

Vendor VND-NIDEC-JP and VND-NIDEC-MY appear as separate vendors but share legal entity LE-NIDEC. Concentration risk models must look beyond `vendor_id` to `legal_entity_id`. Creates an entity resolution challenge.

**4d. Signal Leakage Removal**

Remove `maverick_flag` field and "Maverick purchase" notes text. Models must learn purely from transactional patterns (vendor selection, pricing, contract coverage).

**4e. Soft Tolerance Boundaries**

Replace hard 2%/5% thresholds with fuzzy zones (1-3% = ambiguous). Some invoices in the fuzzy zone ARE legitimate (vendor-agreed price adjustments), some aren't.

#### Level 5: Data Quality Challenges (Robustness Testing)

**Purpose:** Tests model robustness to noisy, messy real-world data.

**5a. Extreme Outliers**

1% of invoices have 50-500% price variance (fat-tailed distribution instead of uniform).

**5b. Missing Values**

5% of `source_list.vendor_material_code` is NULL, 3% of `vendor_master.esg_score` is NULL (already 20% NULL -- increase to 25% and make the missingness correlated with vendor quality).

**5c. Temporal Gaps**

Some vendors have 2-3 month gaps between orders (irregular cadence). Models assuming regular ordering patterns will fail.

**5d. Rejection Reason Alignment**

Map rejection reasons to material types instead of uniform random:

- **File:** `generators/goods_receipts.py:136`
- **Current:** `random.choice(REJECTION_REASONS)` -- uniform across DAMAGED, WRONG_SPEC, DEFECTIVE, EXPIRED
- **Proposed:** Batteries -> EXPIRED (60%), Sensors -> WRONG_SPEC (50%), Structural components -> DAMAGED (50%)

### 10.3 Causal Chain Design

The most impactful enrichment: create end-to-end causal chains across the procurement lifecycle.

**Chain 1: Vendor Quality Cascade**

```
Vendor Quality (root cause)
  -> GR Rejection Rate (higher for low-quality vendors)
    -> Invoice Quantity Variance (follows GR rejection pattern)
      -> Payment Block (triggered by variance)
        -> Payment Delay (blocked invoices paid later)
          -> Vendor Relationship Degradation (late payments -> worse terms)
```

**Chain 2: Material Criticality Flow**

```
Material Criticality (root cause)
  -> Vendor Selection (prefer high-quality for HIGH criticality)
    -> Contract Coverage (HIGH criticality -> more likely contracted)
      -> Maverick Rate (lower for contracted, critical materials)
        -> Price Premium (lower when on-contract)
```

These chains create **multi-hop reasoning** challenges: to predict payment delay, the model must trace back through invoice match, GR quality, vendor quality, and material criticality.

### 10.4 Implementation Priority

| Priority | Enhancement | Effort | Impact on ML Complexity | Files Changed |
|----------|-------------|--------|------------------------|---------------|
| 1 | Vendor score correlations (1a) | Low | High (kills single-feature shortcuts) | `vendors.py` |
| 2 | Invoice variance ~ vendor quality (1b) | Low | High (creates learned thresholds) | `invoices.py` |
| 3 | Material criticality interactions (2a, 2b) | Medium | High (requires interaction terms) | `purchase_orders.py`, `goods_receipts.py` |
| 4 | Temporal vendor drift (3a) | Medium | High (enables time-series models) | `goods_receipts.py`, `invoices.py` |
| 5 | Discount-driven payment timing (1c) | Low | Medium (adds decision logic) | `payments.py` |
| 6 | Q4 seasonality (3b) | Low | Medium (adds temporal signal) | `purchase_orders.py` |
| 7 | Camouflaged mavericks (4a) | Medium | Very High (creates ambiguity) | `purchase_orders.py` |
| 8 | Signal leakage removal (4d) | Low | Very High (forces learning) | `purchase_orders.py`, `models.py` |
| 9 | Soft tolerance boundaries (4e) | Medium | High (creates fuzzy decisions) | `invoices.py` |
| 10 | Extreme outliers + missing values (5a, 5b) | Low | Medium (robustness testing) | Multiple generators |

### 10.5 Model Complexity Progression Table

Shows which model class is needed at each enrichment level:

| Enrichment Level | Model Class | Example | Accuracy Ceiling |
|------------------|-------------|---------|-----------------|
| **Current** (no enrichment) | Single threshold / rule | `if price > 1.15x: maverick` | ~95% |
| **Level 1** (correlations) | Logistic regression | Weighted sum of 3-4 features | ~88% |
| **Level 2** (interactions) | XGBoost / Random Forest | Feature interactions auto-discovered | ~92% |
| **Level 3** (temporal) | LSTM / temporal features | Sequence-aware prediction | ~90% |
| **Level 4** (ambiguity) | Ensemble / deep learning | Multi-model voting | ~85% |
| **Level 5** (data quality) | Robust models + preprocessing | Outlier-aware training | ~83% |

The progression demonstrates that as data becomes more realistic, simpler models plateau and more powerful architectures are justified. The accuracy ceiling *decreases* at higher levels because the task becomes genuinely harder -- this is the desired behavior for an ML demo, as it justifies the use of sophisticated models.

---

## Appendix: Field Reference

Quick reference for key fields used across use cases, mapped to `models.py` dataclass definitions.

### Label Fields

| Use Case | Field | Dataclass | Type |
|----------|-------|-----------|------|
| UC-01 | `maverick_flag` | `POHeader` | bool |
| UC-02 | `match_status` | `InvoiceHeader` | str (FULL_MATCH / PRICE_VARIANCE / QUANTITY_VARIANCE / BOTH_VARIANCE) |
| UC-03 | `risk_score` | `VendorMaster` | int (0-100) |
| UC-05 | derived: `actual_delivery_date > requested_delivery_date` | `POLineItem` | date comparison |
| UC-09 | derived: `quantity_rejected > 0` | `GRLineItem` | Decimal comparison |
| UC-10 | `priority` | `PRHeader` | str (LOW / MEDIUM / HIGH / CRITICAL) |
| UC-13 | `confidentiality_tier` | `MaterialMaster` / `VendorMaster` / `SourceList` | str (PUBLIC / INTERNAL / RESTRICTED) |

### Key Monetary Fields

| Field | Dataclass | Currency Field |
|-------|-----------|---------------|
| `standard_cost` | `MaterialMaster` | `currency` |
| `unit_price` | `POLineItem` | `price_currency` |
| `agreed_price` | `ContractItem` | `ContractHeader.currency` |
| `unit_price_invoiced` | `InvoiceLineItem` | `InvoiceHeader.currency` |
| `total_amount` | `Payment` | `currency` |
| `early_payment_discount` | `Payment` | `currency` |

### Key Variance Fields

| Field | Dataclass | Computation |
|-------|-----------|-------------|
| `price_variance` | `InvoiceLineItem` | `unit_price_invoiced - po_line.unit_price` |
| `quantity_variance` | `InvoiceLineItem` | `quantity_invoiced - gr_line.quantity_accepted` |
| `quantity_rejected` | `GRLineItem` | Count of rejected items |
| `over_delivery_tolerance` | `POLineItem` | Default 10% |
| `under_delivery_tolerance` | `POLineItem` | Default 5% |

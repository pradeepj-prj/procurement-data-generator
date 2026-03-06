# Data Model

## Overview

The procurement database contains **29 tables** organized into 6 domains, modeled after SAP procurement structures. All tables live in the `procurement` schema in PostgreSQL.

At 1x scale the database holds ~10,600 rows. Scale factors of 3x and 10x multiply all transactional and most master data volumes linearly.

## Entity-Relationship Diagram

```
                          ORGANIZATIONAL
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│ company_code │<────│purchasing_org│<────│ purchasing_group  │
└──────┬──────┘     └──────────────┘     └────────┬─────────┘
       │                                          │
       v                                          v
  ┌────────┐     ┌──────────────────┐    ┌────────────────────────┐
  │  plant  │<───│ storage_location │    │purchasing_group_category│
  └────┬───┘     └──────────────────┘    └────────────────────────┘
       │                                          │
       v                                          v
  ┌────────────┐                        ┌──────────────────┐
  │ cost_center │                       │category_hierarchy │ (self-ref)
  └────────────┘                        └────────┬─────────┘
                                                 │
                          MATERIALS              │
                    ┌─────────────────┐          │
                    │ material_master  │<─────────┘
                    └───────┬─────────┘
                            │
                            v
                ┌────────────────────────┐
                │material_plant_extension│
                └────────────────────────┘

                          VENDORS
┌──────────────┐    ┌───────────────┐    ┌─────────────────┐
│ legal_entity │<───│ vendor_master  │───>│ vendor_category │
└──────────────┘    └──┬────────┬───┘    └─────────────────┘
                       │        │
              ┌────────┘        └────────┐
              v                          v
      ┌────────────────┐        ┌────────────────┐
      │ vendor_address  │        │ vendor_contact  │
      └────────────────┘        └────────────────┘

                          SOURCING
┌─────────────┐     ┌──────────────────┐     ┌───────────────┐
│ source_list  │     │ contract_header  │     │ uom_conversion│
│(mat+vnd+plt)│     └────────┬─────────┘     └───────────────┘
└─────────────┘              │
                             v
                      ┌──────────────┐
                      │contract_item │
                      └──────────────┘

                       TRANSACTIONAL
┌───────────┐     ┌───────────┐     ┌────────────┐
│ pr_header  │     │ po_header  │     │  gr_header  │
└─────┬─────┘     └─────┬─────┘     └──────┬─────┘
      │                 │                   │
      v                 v                   v
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ pr_line_item │  │ po_line_item │  │ gr_line_item  │
└──────────────┘  └──────────────┘  └──────────────┘

┌────────────────┐     ┌───────────┐     ┌──────────────────────┐
│ invoice_header  │     │  payment   │     │ payment_invoice_link  │
└───────┬────────┘     └───────────┘     └──────────────────────┘
        │
        v
┌────────────────────┐
│ invoice_line_item   │
└────────────────────┘
```

## Domain Details

### 1. Organizational Structure (7 tables)

These tables define the company's operational hierarchy. They are generated first since nearly all other entities reference them.

#### company_code

The top-level legal/financial entity.

| Column | Type | PK | FK | Description |
|--------|------|:--:|:--:|-------------|
| company_code | VARCHAR(4) | PK | | Company identifier (e.g. `AMR1`) |
| company_name | VARCHAR(100) | | | Full company name |
| country | VARCHAR(2) | | | ISO country code |
| currency | VARCHAR(3) | | | Base currency (e.g. `SGD`) |

**1x scale**: 1 row

#### purchasing_org

Purchasing organization within a company.

| Column | Type | PK | FK | Description |
|--------|------|:--:|:--:|-------------|
| purch_org_id | VARCHAR(4) | PK | | Purchasing org ID |
| purch_org_name | VARCHAR(100) | | | Name |
| company_code | VARCHAR(4) | | FK -> company_code | Parent company |

**1x scale**: 2 rows

#### purchasing_group

Buyer teams responsible for specific categories.

| Column | Type | PK | FK | Description |
|--------|------|:--:|:--:|-------------|
| purch_group_id | VARCHAR(8) | PK | | Group ID (e.g. `PG000001`) |
| purch_group_name | VARCHAR(100) | | | Group name |
| purch_org_id | VARCHAR(4) | | FK -> purchasing_org | Parent org |
| display_code | VARCHAR(30) | | | Human-readable code |

**1x scale**: 6 rows

#### purchasing_group_category

Maps purchasing groups to the categories they manage.

| Column | Type | PK | FK | Description |
|--------|------|:--:|:--:|-------------|
| purch_group_id | VARCHAR(8) | PK | FK -> purchasing_group | |
| category_id | VARCHAR(20) | PK | FK -> category_hierarchy | |

**1x scale**: 7 rows

#### plant

Manufacturing or logistics facility.

| Column | Type | PK | FK | Description |
|--------|------|:--:|:--:|-------------|
| plant_id | VARCHAR(4) | PK | | Plant ID |
| plant_name | VARCHAR(100) | | | Name |
| country | VARCHAR(2) | | | Location country |
| city | VARCHAR(50) | | | Location city |
| function | VARCHAR(50) | | | Plant function (Manufacturing, Warehouse, etc.) |
| company_code | VARCHAR(4) | | FK -> company_code | Parent company |

**1x scale**: 3 rows

#### storage_location

Storage areas within a plant.

| Column | Type | PK | FK | Description |
|--------|------|:--:|:--:|-------------|
| storage_loc_id | VARCHAR(12) | PK | | Storage location ID |
| plant_id | VARCHAR(4) | PK | FK -> plant | Parent plant |
| storage_loc_name | VARCHAR(100) | | | Name |
| storage_type | VARCHAR(30) | | | Type: RAW, WIP, FG, QI, MRO |

**1x scale**: 10 rows

#### cost_center

Cost allocation unit within a plant.

| Column | Type | PK | FK | Description |
|--------|------|:--:|:--:|-------------|
| cost_center_id | VARCHAR(16) | PK | | Cost center ID |
| cost_center_name | VARCHAR(100) | | | Name |
| plant_id | VARCHAR(4) | | FK -> plant | Parent plant |
| department | VARCHAR(50) | | | Department name |

**1x scale**: 19 rows

---

### 2. Category Hierarchy (1 table)

#### category_hierarchy

Three-level procurement taxonomy (Category > Subcategory > Commodity). Self-referencing via `parent_category_id`.

| Column | Type | PK | FK | Nullable | Description |
|--------|------|:--:|:--:|:--------:|-------------|
| category_id | VARCHAR(20) | PK | | | Hierarchical ID (e.g. `ELEC-SEMICOND-ASIC`) |
| category_name | VARCHAR(100) | | | | Display name |
| level | INTEGER | | | | 1=Category, 2=Subcategory, 3=Commodity |
| parent_category_id | VARCHAR(20) | | FK -> category_hierarchy | Yes | NULL for level 1 |
| owner_purch_group_id | VARCHAR(8) | | FK -> purchasing_group | Yes | Responsible buyer group |

**1x scale**: 79 rows (~7 L1, ~22 L2, ~50 L3)

---

### 3. Materials (2 tables)

#### material_master

Central material catalog. Every material belongs to exactly one leaf (level 3) category.

| Column | Type | PK | FK | Nullable | Description |
|--------|------|:--:|:--:|:--------:|-------------|
| material_id | VARCHAR(12) | PK | | | e.g. `MAT-00001` or `MAT-LIDAR-2D` (seed) |
| display_code | VARCHAR(30) | | | | Human-readable code |
| description | VARCHAR(200) | | | | Free-text description |
| material_type | VARCHAR(20) | | | | COMPONENT, RAW, ASSEMBLY, MRO, SERVICE |
| category_id | VARCHAR(20) | | FK -> category_hierarchy | | Leaf category |
| base_uom | VARCHAR(6) | | | | EA, KG, M, L, BOX, SET, HR |
| standard_cost | DECIMAL(12,2) | | | | Reference cost |
| currency | VARCHAR(3) | | | | Cost currency |
| criticality | VARCHAR(10) | | | | HIGH, MEDIUM, LOW |
| criticality_reason_code | VARCHAR(20) | | | Yes | SAFETY, SUPPLY_RISK, LEAD_TIME, REGULATORY |
| hazmat_flag | BOOLEAN | | | | Hazardous material |
| default_lead_time_days | INTEGER | | | | Standard lead time |
| make_or_buy | VARCHAR(4) | | | | MAKE or BUY |
| confidentiality_tier | VARCHAR(12) | | | | PUBLIC, INTERNAL, RESTRICTED |

**1x scale**: 800 rows

#### material_plant_extension

Plant-specific material planning parameters.

| Column | Type | PK | FK | Description |
|--------|------|:--:|:--:|-------------|
| material_id | VARCHAR(12) | PK | FK -> material_master | |
| plant_id | VARCHAR(4) | PK | FK -> plant | |
| reorder_point | INTEGER | | | Stock level trigger |
| lot_size | INTEGER | | | Order quantity increment |
| min_order_qty | INTEGER | | | Minimum order |

**1x scale**: ~1,239 rows (materials x plants where applicable)

---

### 4. Vendors (5 tables)

#### legal_entity

Legal registration of a business entity. Multiple vendors can share the same legal entity (alias groups).

| Column | Type | PK | FK | Description |
|--------|------|:--:|:--:|-------------|
| legal_entity_id | VARCHAR(12) | PK | | |
| legal_name | VARCHAR(200) | | | Registered legal name |
| country_of_incorporation | VARCHAR(2) | | | ISO country |
| registration_id | VARCHAR(30) | | | Tax/registration number |

**1x scale**: 95 rows

#### vendor_master

Core vendor record. Each vendor links to one legal entity.

| Column | Type | PK | FK | Nullable | Description |
|--------|------|:--:|:--:|:--------:|-------------|
| vendor_id | VARCHAR(20) | PK | | | e.g. `VND-SG-00001` |
| display_code | VARCHAR(30) | | | | Human-readable code |
| legal_entity_id | VARCHAR(12) | | FK -> legal_entity | | Owning legal entity |
| vendor_name | VARCHAR(200) | | | | Display name |
| country | VARCHAR(2) | | | | Vendor country |
| vendor_type | VARCHAR(20) | | | | OEM, DISTRIBUTOR, CONTRACT_MFG, LOGISTICS, SERVICE |
| supported_categories | VARCHAR(200) | | | | Comma-separated top-level category IDs |
| preferred_flag | BOOLEAN | | | | Preferred vendor |
| incoterms_default | VARCHAR(3) | | | | FOB, CIF, DDP, EXW, FCA |
| payment_terms | VARCHAR(20) | | | | NET30, NET60, NET90, 2/10NET30 |
| currency | VARCHAR(3) | | | | Default currency |
| lead_time_days_typical | INTEGER | | | | Typical delivery days |
| on_time_delivery_rate | DECIMAL(5,2) | | | | 0-100 percentage |
| quality_score | INTEGER | | | | 1-100 score |
| risk_score | INTEGER | | | | 1-100 score |
| esg_score | INTEGER | | | Yes | 1-100 ESG rating |
| status | VARCHAR(30) | | | | ACTIVE, BLOCKED, CONDITIONAL |
| bank_account | VARCHAR(40) | | | | Bank details (RESTRICTED) |
| confidentiality_tier | VARCHAR(12) | | | | PUBLIC, INTERNAL, RESTRICTED |
| alias_group | VARCHAR(20) | | | Yes | Alias group for duplicate detection |

**1x scale**: 120 rows (~90% ACTIVE, ~3% BLOCKED, ~5% CONDITIONAL)

#### vendor_category

Maps vendors to the categories they can supply.

| Column | Type | PK | FK | Description |
|--------|------|:--:|:--:|-------------|
| vendor_id | VARCHAR(20) | PK | FK -> vendor_master | |
| category_id | VARCHAR(20) | PK | FK -> category_hierarchy | |

**1x scale**: ~364 rows

#### vendor_address

Vendor addresses by type (registered, shipping, billing).

| Column | Type | PK | FK | Description |
|--------|------|:--:|:--:|-------------|
| vendor_id | VARCHAR(20) | PK | FK -> vendor_master | |
| address_type | VARCHAR(20) | PK | | REGISTERED, SHIPPING, BILLING |
| street | VARCHAR(200) | | | |
| city | VARCHAR(50) | | | |
| state_province | VARCHAR(50) | | | |
| country | VARCHAR(2) | | | |
| postal_code | VARCHAR(20) | | | |

**1x scale**: 240 rows (2 per vendor)

#### vendor_contact

Contact persons for each vendor.

| Column | Type | PK | FK | Description |
|--------|------|:--:|:--:|-------------|
| contact_id | VARCHAR(12) | PK | | |
| vendor_id | VARCHAR(20) | | FK -> vendor_master | |
| contact_name | VARCHAR(100) | | | |
| email | VARCHAR(100) | | | |
| phone | VARCHAR(30) | | | |
| role | VARCHAR(50) | | | Account Manager, Sales Rep, etc. |

**1x scale**: ~231 rows

---

### 5. Sourcing (4 tables)

#### source_list

Approved material-vendor-plant sourcing lanes. Central to the procurement process — determines which vendors can supply which materials to which plants.

| Column | Type | PK | FK | Nullable | Description |
|--------|------|:--:|:--:|:--------:|-------------|
| material_id | VARCHAR(12) | PK | FK -> material_master | | |
| plant_id | VARCHAR(4) | PK | FK -> plant | | |
| vendor_id | VARCHAR(20) | PK | FK -> vendor_master | | |
| preferred_rank | INTEGER | | | | 1 = most preferred |
| contract_covered_flag | BOOLEAN | | | | Has active contract |
| approval_status | VARCHAR(20) | | | | APPROVED, CONDITIONAL, NOT_APPROVED |
| lane_lead_time_days | INTEGER | | | | Lead time for this lane |
| vendor_material_code | VARCHAR(30) | | | | Vendor's part number |
| min_order_qty | INTEGER | | | Yes | Lane-specific MOQ |
| confidentiality_tier | VARCHAR(12) | | | | Propagated from material/vendor |
| valid_from | DATE | | | Yes | |
| valid_to | DATE | | | Yes | |

**1x scale**: ~2,814 rows

#### contract_header

Framework agreements with vendors.

| Column | Type | PK | FK | Description |
|--------|------|:--:|:--:|-------------|
| contract_id | VARCHAR(14) | PK | | e.g. `CTR-00001` |
| display_code | VARCHAR(30) | | | |
| vendor_id | VARCHAR(20) | | FK -> vendor_master | |
| valid_from | DATE | | | Contract start |
| valid_to | DATE | | | Contract end |
| contract_type | VARCHAR(10) | | | QUANTITY or VALUE |
| status | VARCHAR(30) | | | ACTIVE, EXPIRED, PENDING |
| currency | VARCHAR(3) | | | |
| incoterms | VARCHAR(3) | | | |
| confidentiality_tier | VARCHAR(12) | | | |

**1x scale**: 40 rows

#### contract_item

Line items within contracts, specifying agreed prices for specific materials.

| Column | Type | PK | FK | Nullable | Description |
|--------|------|:--:|:--:|:--------:|-------------|
| contract_id | VARCHAR(14) | PK | FK -> contract_header | | |
| item_number | INTEGER | PK | | | Line number |
| material_id | VARCHAR(12) | | FK -> material_master | | |
| agreed_price | DECIMAL(12,2) | | | | Contract price |
| price_uom | VARCHAR(6) | | | | Unit of measure for price |
| max_quantity | INTEGER | | | Yes | For QUANTITY contracts |
| target_value | DECIMAL(12,2) | | | Yes | For VALUE contracts |
| consumed_quantity | INTEGER | | | Yes | Reconciled from POs |
| consumed_value | DECIMAL(12,2) | | | Yes | Reconciled from POs |

**1x scale**: 68 rows

#### uom_conversion

Unit of measure conversion factors for materials.

| Column | Type | PK | FK | Description |
|--------|------|:--:|:--:|-------------|
| material_id | VARCHAR(12) | PK | FK -> material_master | |
| from_uom | VARCHAR(6) | PK | | Source unit |
| to_uom | VARCHAR(6) | PK | | Target unit |
| conversion_factor | DECIMAL(10,4) | | | Multiplier |

**1x scale**: 2 rows

---

### 6. Transactional (10 tables)

#### pr_header

Purchase requisitions — internal requests to buy.

| Column | Type | PK | FK | Nullable | Description |
|--------|------|:--:|:--:|:--------:|-------------|
| pr_id | VARCHAR(14) | PK | | | e.g. `PR-000001` |
| pr_date | DATE | | | | Creation date |
| requester_name | VARCHAR(100) | | | | Requesting person |
| requester_department | VARCHAR(50) | | | | Department |
| cost_center_id | VARCHAR(16) | | FK -> cost_center | | Charge-to cost center |
| plant_id | VARCHAR(4) | | FK -> plant | | Requesting plant |
| pr_type | VARCHAR(20) | | | | STANDARD, URGENT, BLANKET |
| status | VARCHAR(30) | | | | OPEN, APPROVED, REJECTED, CONVERTED, CLOSED |
| priority | VARCHAR(10) | | | | LOW, MEDIUM, HIGH, CRITICAL |
| notes | VARCHAR(500) | | | Yes | Free text |

**1x scale**: 500 rows

#### pr_line_item

Individual items requested within a PR.

| Column | Type | PK | FK | Nullable | Description |
|--------|------|:--:|:--:|:--------:|-------------|
| pr_id | VARCHAR(14) | PK | FK -> pr_header | | |
| pr_line_number | INTEGER | PK | | | Line number |
| material_id | VARCHAR(12) | | FK -> material_master | | |
| quantity | DECIMAL(12,2) | | | | Requested quantity |
| uom | VARCHAR(6) | | | | Unit of measure |
| requested_delivery_date | DATE | | | | When needed |
| estimated_price | DECIMAL(12,2) | | | Yes | Budget estimate |
| currency | VARCHAR(3) | | | | |
| status | VARCHAR(30) | | | | OPEN, ASSIGNED, PO_CREATED, CANCELLED |
| assigned_purch_group_id | VARCHAR(8) | | FK -> purchasing_group | Yes | Assigned buyer group |

**1x scale**: ~1,286 rows

#### po_header

Purchase orders — commitments to buy from a vendor.

| Column | Type | PK | FK | Nullable | Description |
|--------|------|:--:|:--:|:--------:|-------------|
| po_id | VARCHAR(14) | PK | | | e.g. `PO-000001` |
| po_date | DATE | | | | Order date |
| vendor_id | VARCHAR(20) | | FK -> vendor_master | | |
| purch_org_id | VARCHAR(4) | | FK -> purchasing_org | | |
| purch_group_id | VARCHAR(8) | | FK -> purchasing_group | | |
| plant_id | VARCHAR(4) | | FK -> plant | | |
| po_type | VARCHAR(20) | | | | STANDARD, FRAMEWORK, RUSH |
| status | VARCHAR(30) | | | | DRAFT, SENT, PARTIALLY_RECEIVED, FULLY_RECEIVED, CLOSED, CANCELLED |
| incoterms | VARCHAR(3) | | | | |
| payment_terms | VARCHAR(20) | | | | |
| currency | VARCHAR(3) | | | | |
| total_net_value | DECIMAL(14,2) | | | | Sum of line item values |
| maverick_flag | BOOLEAN | | | | True if not sourced via approved channel |
| notes | VARCHAR(500) | | | Yes | Free text |

**1x scale**: 400 rows (5-8% maverick)

#### po_line_item

Individual items within a PO. May reference a contract and/or a PR.

| Column | Type | PK | FK | Nullable | Description |
|--------|------|:--:|:--:|:--------:|-------------|
| po_id | VARCHAR(14) | PK | FK -> po_header | | |
| po_line_number | INTEGER | PK | | | |
| material_id | VARCHAR(12) | | FK -> material_master | | |
| quantity | DECIMAL(12,2) | | | | Ordered quantity |
| uom | VARCHAR(6) | | | | |
| unit_price | DECIMAL(12,2) | | | | Price per unit |
| net_value | DECIMAL(14,2) | | | | quantity x unit_price |
| price_currency | VARCHAR(3) | | | | |
| requested_delivery_date | DATE | | | | |
| actual_delivery_date | DATE | | | Yes | Filled after GR |
| contract_id | VARCHAR(14) | | FK -> contract_header | Yes | Source contract |
| contract_item_number | INTEGER | | FK -> contract_item | Yes | Contract line |
| pr_id | VARCHAR(14) | | FK -> pr_header | Yes | Source PR |
| pr_line_number | INTEGER | | | Yes | Source PR line |
| over_delivery_tolerance | DECIMAL(5,2) | | | | Default 10% |
| under_delivery_tolerance | DECIMAL(5,2) | | | | Default 5% |
| gr_status | VARCHAR(10) | | | | OPEN, PARTIAL, COMPLETE |
| invoice_status | VARCHAR(10) | | | | OPEN, PARTIAL, COMPLETE |

**1x scale**: 400 rows (~70-75% on-contract)

#### gr_header

Goods receipts — confirmation of physical delivery.

| Column | Type | PK | FK | Nullable | Description |
|--------|------|:--:|:--:|:--------:|-------------|
| gr_id | VARCHAR(14) | PK | | | e.g. `GR-000001` |
| gr_date | DATE | | | | Receipt date |
| po_id | VARCHAR(14) | | FK -> po_header | | |
| plant_id | VARCHAR(4) | | FK -> plant | | |
| storage_loc_id | VARCHAR(12) | | FK -> storage_location | | |
| received_by | VARCHAR(100) | | | | Receiving clerk |
| status | VARCHAR(30) | | | | POSTED, REVERSED, QUALITY_HOLD |
| notes | VARCHAR(500) | | | Yes | |

**1x scale**: 350 rows

#### gr_line_item

Line-level goods receipt details with quality inspection results.

| Column | Type | PK | FK | Nullable | Description |
|--------|------|:--:|:--:|:--------:|-------------|
| gr_id | VARCHAR(14) | PK | FK -> gr_header | | |
| gr_line_number | INTEGER | PK | | | |
| po_id | VARCHAR(14) | | FK -> po_header | | |
| po_line_number | INTEGER | | FK -> po_line_item | | |
| material_id | VARCHAR(12) | | FK -> material_master | | |
| quantity_received | DECIMAL(12,2) | | | | Total received |
| uom | VARCHAR(6) | | | | |
| quantity_accepted | DECIMAL(12,2) | | | | Passed inspection |
| quantity_rejected | DECIMAL(12,2) | | | | Failed inspection |
| rejection_reason | VARCHAR(100) | | | Yes | DAMAGED, WRONG_SPEC, DEFECTIVE, EXPIRED |
| batch_number | VARCHAR(30) | | | Yes | Lot tracking |

**1x scale**: 350 rows

#### invoice_header

Vendor invoices submitted for payment.

| Column | Type | PK | FK | Description |
|--------|------|:--:|:--:|-------------|
| invoice_id | VARCHAR(14) | PK | | e.g. `INV-000001` |
| vendor_invoice_number | VARCHAR(30) | | | Vendor's invoice ref |
| invoice_date | DATE | | | |
| received_date | DATE | | | When we received it |
| vendor_id | VARCHAR(20) | | FK -> vendor_master | |
| po_id | VARCHAR(14) | | FK -> po_header | |
| currency | VARCHAR(3) | | | |
| total_gross_amount | DECIMAL(14,2) | | | Including tax |
| tax_amount | DECIMAL(12,2) | | | |
| total_net_amount | DECIMAL(14,2) | | | Excluding tax |
| status | VARCHAR(30) | | | RECEIVED, MATCHED, EXCEPTION, APPROVED, PAID, CANCELLED |
| match_status | VARCHAR(20) | | | FULL_MATCH, PRICE_VARIANCE, QUANTITY_VARIANCE, BOTH_VARIANCE, PENDING |
| payment_due_date | DATE | | | |
| payment_block | BOOLEAN | | | Blocked from payment |
| block_reason | VARCHAR(100) | | | PRICE_MISMATCH, QTY_MISMATCH, QUALITY_HOLD, DUPLICATE_SUSPECT |

**1x scale**: 320 rows (80-85% FULL_MATCH)

#### invoice_line_item

Line-level invoice details with variance tracking.

| Column | Type | PK | FK | Nullable | Description |
|--------|------|:--:|:--:|:--------:|-------------|
| invoice_id | VARCHAR(14) | PK | FK -> invoice_header | | |
| invoice_line_number | INTEGER | PK | | | |
| po_id | VARCHAR(14) | | FK -> po_header | | |
| po_line_number | INTEGER | | FK -> po_line_item | | |
| material_id | VARCHAR(12) | | FK -> material_master | | |
| quantity_invoiced | DECIMAL(12,2) | | | | |
| unit_price_invoiced | DECIMAL(12,2) | | | | |
| net_amount | DECIMAL(14,2) | | | | |
| gr_id | VARCHAR(14) | | FK -> gr_header | Yes | Matched GR |
| gr_line_number | INTEGER | | | Yes | |
| price_variance | DECIMAL(12,2) | | | | Invoiced vs PO price |
| quantity_variance | DECIMAL(12,2) | | | | Invoiced vs GR qty |

**1x scale**: 320 rows

#### payment

Payment runs executing approved invoices.

| Column | Type | PK | FK | Description |
|--------|------|:--:|:--:|-------------|
| payment_id | VARCHAR(14) | PK | | e.g. `PAY-000001` |
| payment_date | DATE | | | |
| vendor_id | VARCHAR(20) | | FK -> vendor_master | |
| payment_method | VARCHAR(20) | | | BANK_TRANSFER, CHECK, WIRE |
| currency | VARCHAR(3) | | | |
| total_amount | DECIMAL(14,2) | | | |
| bank_account_ref | VARCHAR(40) | | | Reference (RESTRICTED) |
| payment_terms_applied | VARCHAR(20) | | | |
| early_payment_discount | DECIMAL(12,2) | | | Discount taken |
| status | VARCHAR(30) | | | SCHEDULED, EXECUTED, FAILED, REVERSED |

**1x scale**: ~260 rows

#### payment_invoice_link

Many-to-many link between payments and invoices (a payment can cover multiple invoices).

| Column | Type | PK | FK | Description |
|--------|------|:--:|:--:|-------------|
| payment_id | VARCHAR(14) | PK | FK -> payment | |
| invoice_id | VARCHAR(14) | PK | FK -> invoice_header | |
| amount_applied | DECIMAL(14,2) | | | Amount of this payment applied to this invoice |

**1x scale**: ~260 rows

---

## Foreign Key Summary

All foreign key relationships in the database:

| Child Table | Column(s) | Parent Table | Parent Column(s) |
|-------------|-----------|-------------|-----------------|
| purchasing_org | company_code | company_code | company_code |
| purchasing_group | purch_org_id | purchasing_org | purch_org_id |
| purchasing_group_category | purch_group_id | purchasing_group | purch_group_id |
| purchasing_group_category | category_id | category_hierarchy | category_id |
| plant | company_code | company_code | company_code |
| storage_location | plant_id | plant | plant_id |
| cost_center | plant_id | plant | plant_id |
| category_hierarchy | parent_category_id | category_hierarchy | category_id |
| category_hierarchy | owner_purch_group_id | purchasing_group | purch_group_id |
| material_master | category_id | category_hierarchy | category_id |
| material_plant_extension | material_id | material_master | material_id |
| material_plant_extension | plant_id | plant | plant_id |
| vendor_master | legal_entity_id | legal_entity | legal_entity_id |
| vendor_category | vendor_id | vendor_master | vendor_id |
| vendor_category | category_id | category_hierarchy | category_id |
| vendor_address | vendor_id | vendor_master | vendor_id |
| vendor_contact | vendor_id | vendor_master | vendor_id |
| source_list | material_id | material_master | material_id |
| source_list | plant_id | plant | plant_id |
| source_list | vendor_id | vendor_master | vendor_id |
| contract_header | vendor_id | vendor_master | vendor_id |
| contract_item | contract_id | contract_header | contract_id |
| contract_item | material_id | material_master | material_id |
| pr_header | cost_center_id | cost_center | cost_center_id |
| pr_header | plant_id | plant | plant_id |
| pr_line_item | pr_id | pr_header | pr_id |
| pr_line_item | material_id | material_master | material_id |
| pr_line_item | assigned_purch_group_id | purchasing_group | purch_group_id |
| po_header | vendor_id | vendor_master | vendor_id |
| po_header | purch_org_id | purchasing_org | purch_org_id |
| po_header | purch_group_id | purchasing_group | purch_group_id |
| po_header | plant_id | plant | plant_id |
| po_line_item | po_id | po_header | po_id |
| po_line_item | material_id | material_master | material_id |
| po_line_item | contract_id | contract_header | contract_id |
| po_line_item | pr_id | pr_header | pr_id |
| gr_header | po_id | po_header | po_id |
| gr_header | plant_id | plant | plant_id |
| gr_header | storage_loc_id | storage_location | storage_loc_id |
| gr_line_item | gr_id | gr_header | gr_id |
| gr_line_item | po_id, po_line_number | po_line_item | po_id, po_line_number |
| gr_line_item | material_id | material_master | material_id |
| invoice_header | vendor_id | vendor_master | vendor_id |
| invoice_header | po_id | po_header | po_id |
| invoice_line_item | invoice_id | invoice_header | invoice_id |
| invoice_line_item | po_id, po_line_number | po_line_item | po_id, po_line_number |
| invoice_line_item | material_id | material_master | material_id |
| invoice_line_item | gr_id | gr_header | gr_id |
| payment | vendor_id | vendor_master | vendor_id |
| payment_invoice_link | payment_id | payment | payment_id |
| payment_invoice_link | invoice_id | invoice_header | invoice_id |

---

## Built-in Statistical Properties

The generator enforces these distribution targets, validated by `validators/statistical.py`:

| Property | Target | Validation Window |
|----------|--------|-------------------|
| Maverick PO rate | 5-8% of PO headers | 2-12% |
| On-contract PO lines | 70-75% of PO line items | 60-85% |
| Invoice full-match rate | 80-85% of invoices | 70-95% |
| Vendor status: ACTIVE | ~90% | Majority |
| Vendor status: BLOCKED | ~2-3% | Capped at 3 |
| Material criticality | HIGH/MEDIUM/LOW distribution | Logged |
| GR on-time delivery | Driven by `vendor.on_time_delivery_rate` | Per-vendor |
| Quality rejections | Driven by `vendor.quality_score` | Per-vendor |

## Temporal Window

- **Time range**: 2024-04-01 to 2025-09-30 (18 months)
- **Demo reference date**: 2025-09-15
- **Ordering**: POs spread across the full window; GRs follow POs by lead time; invoices follow GRs by 1-5 days; payments follow invoice due dates

## Confidentiality Model

Three tiers propagate through the data:

| Tier | Meaning | Applies to |
|------|---------|-----------|
| PUBLIC | Unrestricted | Most materials, vendors |
| INTERNAL | Company-internal only | Some materials, vendors, contracts |
| RESTRICTED | Need-to-know basis | Sensitive materials, bank accounts |

Confidentiality propagates from materials and vendors to source list entries (highest tier wins). The `bank_account` and `bank_account_ref` fields are always RESTRICTED.

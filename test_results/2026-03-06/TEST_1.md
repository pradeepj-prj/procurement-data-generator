# Test Results - 2026-03-06

## Run Command

```
python -m procurement_generator --scale 1
```

## Pipeline Result: ALL PASS

- **78 FATAL checks**: 78 passed, 0 failed
- **8 WARNING checks**: 8 passed, 0 warnings

## Row Counts

| Table | Count |
|-------|-------|
| company_code | 1 |
| purchasing_org | 2 |
| purchasing_group | 6 |
| purchasing_group_category | 7 |
| plant | 3 |
| storage_location | 10 |
| cost_center | 19 |
| category_hierarchy | 79 |
| material_master | 800 |
| material_plant_extension | 1,239 |
| legal_entity | 95 |
| vendor_master | 120 |
| vendor_category | 364 |
| vendor_address | 240 |
| vendor_contact | 231 |
| source_list | 2,814 |
| contract_header | 40 |
| contract_item | 68 |
| uom_conversion | 2 |
| pr_header | 500 |
| pr_line_item | 1,315 |
| po_header | 400 |
| po_line_item | 400 |
| gr_header | 350 |
| gr_line_item | 350 |
| invoice_header | 320 |
| invoice_line_item | 320 |
| payment | 260 |
| payment_invoice_link | 260 |
| **TOTAL** | **10,615** |

## Structural Integrity (18 FK Checks) - ALL PASS

- FK: material.category_id -> category_hierarchy
- FK: source_list.material_id -> material_master
- FK: source_list.vendor_id -> vendor_master
- FK: source_list.plant_id -> plant
- FK: contract_item.material_id -> material_master
- FK: contract_header.vendor_id -> vendor_master
- FK: vendor.legal_entity_id -> legal_entity
- FK: pg_category.purch_group_id -> purchasing_group
- FK: pg_category.category_id -> category_hierarchy
- FK: vendor_category.vendor_id -> vendor_master
- FK: material_plant_extension -> material + plant
- FK: pr_line.material_id -> material_master
- FK: pr_header.plant_id -> plant
- FK: po_header.vendor_id -> vendor_master
- FK: gr_header.po_id -> po_header
- FK: invoice_header.po_id -> po_header
- FK: payment.vendor_id -> vendor_master
- FK: payment_invoice_link -> payment + invoice

## Business Rules (7 Checks) - ALL PASS

- HIGH criticality must have reason code
- Confidentiality defaults (no NULL tiers)
- Blocked vendor sourcing
- Alias group integrity
- Confidentiality propagation
- Contract-source alignment
- No POs to BLOCKED vendors

## Statistical Distribution Checks (8 Checks) - ALL PASS

| Check | Actual | Target |
|-------|--------|--------|
| Material count | 800 | 800 |
| Vendor count | 120 | 120 |
| Contract count | 40 | 40 |
| Leaf categories | 50 | ~51 |
| Criticality (H/M/L) | 9%/23%/68% | 10%/20%/70% |
| On-contract PO lines | 72% (290/400) | 70-75% |
| Maverick POs | 6% (23/400) | 5-8% |
| Invoice full-match | 81% (260/320) | 80-85% |

## Scenario Seed Verification (12/12) - ALL PASS

| Seed | Description | Status |
|------|-------------|--------|
| SEED-001 | LiDAR single-source | PASS |
| SEED-002 | Battery concentration | PASS |
| SEED-003 | Restricted bank account | PASS |
| SEED-004 | BMS mixed tiers | PASS |
| SEED-005 | Off-contract motors | PASS |
| SEED-006 | Nidec alias | PASS |
| SEED-007 | SBC sourcing gap | PASS |
| SEED-008 | Camera lead time | PASS |
| SEED-009 | PG-MECH no ELEC | PASS |
| SEED-010 | Connector price variance | PASS |
| SEED-011 | Conditional vendor | PASS |
| SEED-012 | Cross-plant motor sourcing | PASS |

## Export

- CSV: 10,615 rows across 29 tables to `output/csv/`
- SQL: 10,615 rows across 29 tables to `output/sql/`

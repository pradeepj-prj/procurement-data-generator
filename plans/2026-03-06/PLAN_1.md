# Procurement Data Generator - Implementation Plan

## Overview

Python-based data generator producing a realistic, referentially-intact procurement dataset for an AMR (Autonomous Mobile Robot) manufacturing company. Powers a GenAI demo on SAP HANA Cloud.

## Architecture

```
procurement-data-generator/
├── pyproject.toml
├── seeds/                          # YAML seed config files (8 files)
├── src/procurement_generator/
│   ├── cli.py                      # CLI entry point (argparse)
│   ├── config.py                   # YAML config loading, ScaleConfig
│   ├── models.py                   # ~20 dataclasses for all entity types
│   ├── data_store.py               # Central DataStore with typed lists + lookups
│   ├── pipeline.py                 # 18-stage orchestrator
│   ├── utils.py                    # ID generators, date math, Faker setup
│   ├── generators/                 # 13 generator modules
│   │   ├── base.py                 # BaseGenerator ABC
│   │   ├── org_structure.py        # Company, PurchOrg, PurchGroup, Plant, etc.
│   │   ├── categories.py           # 3-level category hierarchy
│   │   ├── materials.py            # 800 materials + plant extensions
│   │   ├── legal_entities.py       # 95 legal entities + alias groups
│   │   ├── vendors.py              # 120 vendors + categories, addresses, contacts
│   │   ├── source_list.py          # ~2800 source list entries
│   │   ├── contracts.py            # 40 contracts + items + UOM conversions
│   │   ├── purchase_reqs.py        # 500 PRs
│   │   ├── purchase_orders.py      # 400 POs (72% on-contract, 6% maverick)
│   │   ├── goods_receipts.py       # 350 GRs
│   │   ├── invoices.py             # 320 invoices (81% full match)
│   │   └── payments.py             # ~260 payments
│   ├── validators/                 # 4 validator modules
│   │   ├── integrity.py            # 18 FK checks
│   │   ├── business_rules.py       # Criticality, confidentiality, blocked vendors
│   │   ├── seeds.py                # 12 scenario seed verifications
│   │   └── statistical.py          # Distribution checks (warnings)
│   └── exporters/
│       ├── csv_exporter.py         # One CSV per table
│       └── sql_exporter.py         # DDL + batch INSERT (HANA-compatible)
└── output/                         # Generated CSV + SQL output
```

## Pipeline Stages

| # | Stage | Type |
|---|-------|------|
| 1 | Org Structure | Master Data |
| 2 | Category Hierarchy | Master Data |
| 3 | Materials | Master Data |
| 4 | Legal Entities | Master Data |
| 5 | Vendors | Master Data |
| 6 | Contracts | Master Data |
| 7 | Source List | Master Data |
| 8 | Confidentiality Propagation | Master Data |
| 9 | Master Data Validation | Validation |
| 10 | Purchase Requisitions | Transactional |
| 11 | Purchase Orders | Transactional |
| 12 | Goods Receipts | Transactional |
| 13 | Invoices | Transactional |
| 14 | Payments | Transactional |
| 15 | Reconciliation | Post-Generation |
| 16 | Full Validation | Post-Generation |
| 17 | Seed Verification | Post-Generation |
| 18 | Export (CSV + SQL) | Post-Generation |

## Key Design Decisions

1. **Seed-first generation**: YAML seeds loaded before bulk generation to anchor demo scenarios
2. **Contracts before source list**: Pipeline reordered so source list can flag contract-covered entries
3. **On-contract PO strategy**: Dedicated on-contract PO block generates ~72% directly from contract items
4. **Dedicated maverick block**: Separate maverick PO generation to hit 5-8% target
5. **Central DataStore**: All generators write to shared store; all validators read from it
6. **Halt-on-FATAL**: Pipeline stops on any FATAL validation failure

## Dependencies

- `pyyaml>=6.0` - seed file loading
- `faker>=20.0` - realistic names, addresses, contacts
- `pytest>=7.0` (dev) - testing

## Scale Targets (1x)

| Entity | Count |
|--------|-------|
| Materials | 800 |
| Vendors | 120 |
| Legal Entities | 95 |
| Source List Entries | ~2800 |
| Contracts | 40 |
| Purchase Requisitions | 500 |
| Purchase Orders | 400 |
| Goods Receipts | 350 |
| Invoices | 320 |
| Payments | ~260 |
| **Total Rows** | **~10,600** |

# Procurement Data Generator - TODO

## Project Setup
- [x] pyproject.toml with dependencies
- [x] Package structure (src/procurement_generator/)
- [x] CLI entry point (cli.py, __main__.py)

## Models & Infrastructure
- [x] Dataclasses for all ~20 entity types (models.py)
- [x] Central DataStore with typed lists + lookups (data_store.py)
- [x] Config loading + ScaleConfig (config.py)
- [x] Utility functions (utils.py)

## Seed Files
- [x] seeds/config.yaml
- [x] seeds/org_structure.yaml
- [x] seeds/category_hierarchy.yaml
- [x] seeds/seed_materials.yaml
- [x] seeds/seed_vendors.yaml
- [x] seeds/seed_legal_entities.yaml
- [x] seeds/seed_contracts.yaml
- [x] seeds/seed_source_lists.yaml

## Generators (Master Data)
- [x] Org structure generator
- [x] Category hierarchy generator
- [x] Materials generator (seed + bulk, plant extensions)
- [x] Legal entities generator (seed + bulk, alias groups)
- [x] Vendors generator (seed + bulk, categories, addresses, contacts)
- [x] Contracts generator (seed + bulk, items, UOM conversions)
- [x] Source list generator (seed + bulk)

## Generators (Transactional)
- [x] Purchase requisitions generator
- [x] Purchase orders generator (on-contract + maverick + PR-derived)
- [x] Goods receipts generator
- [x] Invoices generator (three-way match)
- [x] Payments generator

## Validators
- [x] Structural integrity (18 FK checks)
- [x] Business rules (criticality, confidentiality, blocked vendors, etc.)
- [x] Scenario seed verification (12 seeds)
- [x] Statistical distribution checks

## Exporters
- [x] CSV exporter
- [x] SQL exporter (DDL + batch INSERT)

## Pipeline
- [x] 18-stage orchestrator with halt-on-FATAL
- [x] Confidentiality propagation stage
- [x] Contract consumption reconciliation
- [x] Full validation pass

## Documentation
- [x] Plan document (plans/2026-03-06/PLAN_1.md)
- [x] TODO checklist (todo/TODO.md)
- [x] Test results (test_results/2026-03-06/TEST_1.md)
- [x] CLAUDE.md with build/run/test commands
- [x] .gitignore

## Verification
- [x] 78/78 FATAL checks pass
- [x] 8/8 WARNING checks pass
- [x] 12/12 scenario seeds verified
- [x] On-contract PO %: 72% (target 70-75%)
- [x] Maverick PO %: 6% (target 5-8%)
- [x] Invoice match rate: 81% (target 80-85%)
- [x] ~10,600 total rows across 29 tables

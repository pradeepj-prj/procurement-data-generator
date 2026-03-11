# Plan: Deploy Procurement Data to SAP HANA Cloud on BTP

## Status: IMPLEMENTED

## Summary

Added HANA Cloud exporter + Python deploy script to deploy procurement data to SAP HANA Cloud on BTP.

## Changes Made

1. **Moved shared constants** (`PRIMARY_KEYS`, `TABLE_ORDER`) from `postgres_exporter.py` to `sql_exporter.py`
2. **Created `hana_exporter.py`** — HANA Cloud SQL export with:
   - Schema-qualified tables: `"PROCUREMENT"."table_name"`
   - Safe DROP via anonymous blocks (error code 259)
   - PRIMARY KEY constraints
   - Monolithic `_load_all_hana.sql` (HANA has no `\i` include)
3. **Integrated into pipeline** — Stage 18 now exports to `output/hana/`
4. **Created `scripts/deploy_to_hana.py`** — Python deploy script using `hdbcli`:
   - Loads config from `.env`
   - Creates schema (handles error code 386)
   - Loads tables in FK-safe order
   - Verifies via `M_TABLES`
   - Supports `--dry-run`, `--sql-dir`, `--schema` flags
5. **Added `hana` optional dependency** in `pyproject.toml`
6. **Added HANA variables** to `.env.example`
7. **Created 18 unit tests** in `tests/test_hana_exporter.py`
8. **Updated documentation** — `DEPLOYMENT.md` and `CLAUDE.md`

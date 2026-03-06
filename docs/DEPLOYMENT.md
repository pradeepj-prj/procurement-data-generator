# Deployment Guide

## Overview

This document covers deploying the generated procurement data to a Postgres instance on EC2. It includes setup instructions, the automated deployment script, and lessons learned from the initial deployment.

## Prerequisites

- Python 3.10+ with the project installed (`pip install -e .`)
- SSH access to the EC2 instance (key file configured in `.env`)
- PostgreSQL 16+ running on the EC2 instance
- Generated data in `output/postgres/` (run `python -m procurement_generator --scale 1`)

## Configuration

All connection details are stored in `.env` (gitignored). Copy the template and fill in real values:

```bash
cp .env.example .env
```

`.env` variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `EC2_IP` | *(required)* | EC2 instance public IP |
| `SSH_KEY` | *(required)* | Path to SSH private key (e.g. `~/.ssh/kp-2.pem`) |
| `SSH_USER` | `ubuntu` | SSH username |
| `DB_NAME` | `procurement_demo` | Postgres database name |
| `DB_USER` | `procurement_user` | Postgres role for the application |
| `DB_PASSWORD` | *(required)* | Password for the Postgres role |
| `DB_SCHEMA` | `procurement` | Schema within the database |
| `DB_PORT` | `5432` | Postgres port |

## Deployment Steps

### Automated (recommended)

```bash
# 1. Generate data
python -m procurement_generator --scale 1

# 2. Preview what will happen
bash scripts/deploy_to_ec2.sh --dry-run

# 3. Deploy
bash scripts/deploy_to_ec2.sh
```

The script performs 4 steps:
1. **Upload** — `scp` all SQL files from `output/postgres/` to `/tmp/procurement_load/` on EC2
2. **Setup** — Idempotently create the Postgres role and database (via `sudo -u postgres`)
3. **Load** — Execute `_load_all.sql` which creates the schema and loads all 29 tables in FK-safe order
4. **Verify** — Query row counts for every table in the schema and print a summary
5. **Cleanup** — Remove the temporary files from EC2

### Manual

```bash
# Upload
scp -i $SSH_KEY -r output/postgres/ $SSH_USER@$EC2_IP:/tmp/procurement_load/

# Create DB (if first time)
ssh -i $SSH_KEY $SSH_USER@$EC2_IP \
  "sudo -u postgres createdb procurement_demo"

# Load
ssh -i $SSH_KEY $SSH_USER@$EC2_IP \
  "cd /tmp/procurement_load && sudo -u postgres psql -d procurement_demo -f _load_all.sql"
```

## Export Formats

The generator produces three export formats in every run:

| Format | Output Path | Target | Notes |
|--------|------------|--------|-------|
| CSV | `output/csv/` | Any system | One file per table, standard RFC 4180 CSV |
| HANA SQL | `output/sql/` | SAP HANA Cloud | DDL + batch INSERT, no schema prefix |
| Postgres SQL | `output/postgres/` | PostgreSQL 14+ | Schema-qualified DDL with PKs, `DROP CASCADE`, `_load_all.sql` master script |

## Postgres SQL Details

Each table file in `output/postgres/` contains:
- `DROP TABLE IF EXISTS procurement.<table> CASCADE;` — idempotent, safe for re-runs
- `CREATE TABLE procurement.<table> (...)` — with column types, NOT NULL constraints, and a `PRIMARY KEY` clause
- `INSERT INTO` statements in batches of 100 rows

The `_load_all.sql` master script:
- Creates the `procurement` schema if it doesn't exist
- Sets `search_path` to the schema
- `\i`-includes each table file in FK-safe order (org structure first, payment links last)

## Verifying the Deployment

```bash
# Connect to the database
ssh -i $SSH_KEY $SSH_USER@$EC2_IP \
  "sudo -u postgres psql -d procurement_demo"

# Inside psql:
SET search_path TO procurement;
\dt                              -- list all tables
SELECT count(*) FROM po_header;  -- spot-check a table

-- Row counts for all tables:
SELECT table_name,
       (xpath('/row/cnt/text()',
              query_to_xml('SELECT count(*) AS cnt FROM procurement.' || table_name,
                           false, true, '')))[1]::text::int AS row_count
FROM information_schema.tables
WHERE table_schema = 'procurement'
ORDER BY table_name;
```

Expected totals at 1x scale: ~10,600 rows across 29 tables.

## Redeployment

The deployment is fully idempotent. Running `deploy_to_ec2.sh` again will:
- Skip role/database creation (already exists)
- `DROP CASCADE` and recreate every table (the SQL files handle this)
- Reload all data from scratch

There is no incremental update — each deployment is a full refresh.

---

## Lessons Learned

These issues were encountered during the initial EC2 deployment and have since been fixed.

### 1. VARCHAR Column Sizes Too Small

**Symptom**: Postgres rejected INSERT statements with `ERROR: value too long for type character varying(N)`.

**Root cause**: The `FIELD_TYPES` mapping in `sql_exporter.py` defined VARCHAR widths based on SAP field conventions, but the generator produced longer values. For example, `vendor_id` was `VARCHAR(12)` but generated IDs like `VND-SG-00010` (14 chars), and `category_id` was `VARCHAR(12)` but hierarchical IDs like `ELEC-SEMICOND-ASIC` reached 17 chars.

**Fix**: Widened the affected fields:

| Field | Before | After | Reason |
|-------|--------|-------|--------|
| `category_id` | `VARCHAR(12)` | `VARCHAR(20)` | Hierarchical IDs like `ELEC-SEMICOND-ASIC` |
| `parent_category_id` | `VARCHAR(12)` | `VARCHAR(20)` | Same IDs as `category_id` |
| `vendor_id` | `VARCHAR(12)` | `VARCHAR(20)` | Country-prefixed IDs like `VND-SG-00010` |
| `cost_center_id` | `VARCHAR(10)` | `VARCHAR(16)` | IDs like `CC-PLT001-07` |
| `storage_loc_id` | `VARCHAR(8)` | `VARCHAR(12)` | IDs like `SL-PLT001-1` |
| `phone` | `VARCHAR(20)` | `VARCHAR(30)` | International formats with extensions |
| `status` | `VARCHAR(20)` | `VARCHAR(30)` | Values like `PARTIALLY_RECEIVED` |

**Lesson**: When generating synthetic data, always validate max field lengths against DDL constraints before export. The HANA exporter didn't surface this because HANA is more lenient with VARCHAR overflow in some modes. A validation step that checks `max(len(field)) <= VARCHAR(N)` per column would catch this automatically.

### 2. NOT NULL Constraint on Optional Fields

**Symptom**: Postgres rejected INSERTs with `ERROR: null value in column "pr_id" of relation "po_line_item" violates not-null constraint`.

**Root cause**: The nullable detection logic checked for `"typing.Optional"` in the string representation of field types. With `from __future__ import annotations` (PEP 563 deferred evaluation), Python represents the type as `"Optional[str]"` — without the `typing.` prefix. The check failed silently, and fields like `pr_id`, `contract_id`, and `parent_category_id` (all `Optional[str]` in the model) were incorrectly marked `NOT NULL`.

**Affected tables**: `po_line_item` (5 nullable fields), `category_hierarchy` (`parent_category_id`), and several others.

**Fix**: Changed the check from `"typing.Optional" in str(ef.type)` to `"Optional" in str(ef.type)` in both `sql_exporter.py` and `postgres_exporter.py`.

**Lesson**: String-based type introspection is fragile across Python versions and `__future__` imports. A more robust approach would use `typing.get_type_hints()` with `include_extras=True`, but the simple string fix is sufficient here since the project consistently uses `from __future__ import annotations`.

### 3. Shell Escaping in Deploy Script

**Symptom**: The initial deploy script used a `\gexec`-based SQL block to idempotently create the database. The dollar-quoting (`$$`) and psql meta-commands (`\gexec`) got mangled through multiple layers of shell escaping (bash -> ssh -> psql), so the DB creation silently failed while the script continued.

**Root cause**: Embedding complex SQL with dollar-quoting inside a shell variable, inside an SSH command, requires triple-escaping that is error-prone and unreadable.

**Fix**: Replaced the monolithic SQL block with three separate, simple SSH commands:
1. Check if role exists (`psql -tAc "SELECT 1 FROM pg_roles WHERE..."`) then create if not
2. Check if database exists then `createdb` if not
3. `GRANT ALL PRIVILEGES`

**Lesson**: For deployment scripts that run SQL over SSH, prefer simple single-statement commands over complex multi-statement blocks. Each command can be tested independently and fails clearly. Avoid `\gexec` and dollar-quoting in SSH contexts entirely.

### 4. HANA vs Postgres SQL Compatibility

The existing HANA SQL exporter (`sql_exporter.py`) was not directly usable for Postgres. Key differences:

| Feature | HANA SQL | Postgres SQL |
|---------|----------|-------------|
| Schema prefix | None (default schema) | `procurement.<table>` |
| Drop before create | Not included | `DROP TABLE IF EXISTS ... CASCADE` |
| Primary keys | Not included | `PRIMARY KEY (...)` constraint |
| Load ordering | Not managed | `_load_all.sql` with `\i` in FK order |
| Boolean literals | `TRUE`/`FALSE` | `TRUE`/`FALSE` (compatible) |
| VARCHAR overflow | Silently truncated | Strict error |

The Postgres exporter (`postgres_exporter.py`) was created as a separate module that reuses the type mapping and value formatting from the HANA exporter but adds Postgres-specific DDL generation.

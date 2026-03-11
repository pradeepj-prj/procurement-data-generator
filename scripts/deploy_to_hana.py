#!/usr/bin/env python3
"""Deploy procurement data to SAP HANA Cloud on BTP.

Usage:
    python scripts/deploy_to_hana.py [--dry-run] [--sql-dir output/hana] [--schema PROCUREMENT]

Prerequisites:
    - pip install hdbcli
    - HANA Cloud instance provisioned on BTP
    - Connection details in .env (see .env.example)
    - Generated HANA SQL in output/hana/ (run: python -m procurement_generator --scale 1)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add project root to path for TABLE_ORDER import
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from procurement_generator.exporters.sql_exporter import TABLE_ORDER


def load_env() -> None:
    """Load .env file into os.environ."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def get_config(args: argparse.Namespace) -> dict:
    """Build config from .env and CLI args."""
    load_env()
    return {
        "host": os.environ.get("HANA_HOST", ""),
        "port": int(os.environ.get("HANA_PORT", "443")),
        "user": os.environ.get("HANA_USER", "DBADMIN"),
        "password": os.environ.get("HANA_PASSWORD", ""),
        "schema": args.schema or os.environ.get("HANA_SCHEMA", "PROCUREMENT"),
        "sql_dir": Path(args.sql_dir),
        "dry_run": args.dry_run,
    }


def validate_sql_dir(sql_dir: Path) -> list[str]:
    """Check that SQL files exist. Returns list of table files found."""
    if not sql_dir.exists():
        print(f"ERROR: {sql_dir} not found. Run 'python -m procurement_generator --scale 1' first.")
        sys.exit(1)

    master = sql_dir / "_load_all_hana.sql"
    if not master.exists():
        print(f"ERROR: {master} not found.")
        sys.exit(1)

    table_files = []
    for table_name in TABLE_ORDER:
        table_file = sql_dir / f"{table_name}.sql"
        if table_file.exists():
            table_files.append(table_name)
    return table_files


def split_statements(sql_text: str) -> list[str]:
    """Split SQL text into individual statements.

    Handles DO BEGIN...END blocks and regular semicolon-delimited statements.
    """
    statements = []
    current = []
    in_do_block = False

    for line in sql_text.splitlines():
        stripped = line.strip()

        # Skip comments and empty lines outside statements
        if not current and (stripped.startswith("--") or not stripped):
            continue

        if stripped.upper() == "DO BEGIN":
            in_do_block = True
            current.append(line)
            continue

        if in_do_block:
            current.append(line)
            if stripped.upper().startswith("END;"):
                statements.append("\n".join(current))
                current = []
                in_do_block = False
            continue

        # Regular statement accumulation
        current.append(line)
        if stripped.endswith(";"):
            stmt = "\n".join(current).strip()
            if stmt and not stmt.startswith("--"):
                # Remove trailing semicolon for hdbcli execute
                statements.append(stmt.rstrip(";"))
            current = []

    # Flush any remaining
    if current:
        stmt = "\n".join(current).strip()
        if stmt and not stmt.startswith("--"):
            statements.append(stmt.rstrip(";"))

    return statements


def deploy(config: dict) -> None:
    """Deploy SQL files to HANA Cloud."""
    sql_dir = config["sql_dir"]
    schema = config["schema"]
    dry_run = config["dry_run"]

    table_files = validate_sql_dir(sql_dir)

    print("=== HANA Cloud Deployment ===")
    print(f"  Host:    {config['host']}")
    print(f"  Port:    {config['port']}")
    print(f"  User:    {config['user']}")
    print(f"  Schema:  {schema}")
    print(f"  SQL dir: {sql_dir}")
    print(f"  Tables:  {len(table_files)}")
    if dry_run:
        print("  [DRY RUN] No connection will be made.")
    print()

    if dry_run:
        print("--- Step 1: Create schema ---")
        print(f'  [CMD] CREATE SCHEMA "{schema}"')
        print()
        print("--- Step 2: Load tables ---")
        for table_name in table_files:
            table_file = sql_dir / f"{table_name}.sql"
            stmts = split_statements(table_file.read_text(encoding="utf-8"))
            print(f"  [CMD] {table_name}: {len(stmts)} statements")
        print()
        print("--- Step 3: Verify ---")
        print(f'  [CMD] SELECT TABLE_NAME, RECORD_COUNT FROM M_TABLES WHERE SCHEMA_NAME = \'{schema}\'')
        print()
        print("=== Dry run complete ===")
        return

    # Real deployment
    if not config["host"]:
        print("ERROR: HANA_HOST not set. Copy .env.example to .env and fill in values.")
        sys.exit(1)
    if not config["password"]:
        print("ERROR: HANA_PASSWORD not set.")
        sys.exit(1)

    try:
        from hdbcli import dbapi
    except ImportError:
        print("ERROR: hdbcli not installed. Run: pip install hdbcli")
        sys.exit(1)

    print("--- Step 1: Connecting ---")
    conn = dbapi.connect(
        address=config["host"],
        port=config["port"],
        user=config["user"],
        password=config["password"],
        encrypt=True,
    )
    cursor = conn.cursor()
    print("  Connected.")

    # Create schema
    print()
    print("--- Step 2: Create schema ---")
    try:
        cursor.execute(f'CREATE SCHEMA "{schema}"')
        print(f'  Created schema "{schema}".')
    except dbapi.Error as e:
        if "386" in str(e):  # schema already exists
            print(f'  Schema "{schema}" already exists.')
        else:
            raise

    # Load tables
    print()
    print("--- Step 3: Load tables ---")
    for table_name in table_files:
        table_file = sql_dir / f"{table_name}.sql"
        stmts = split_statements(table_file.read_text(encoding="utf-8"))
        for stmt in stmts:
            cursor.execute(stmt)
        conn.commit()
        print(f"  {table_name}: {len(stmts)} statements executed")

    # Verify
    print()
    print("--- Step 4: Verification ---")
    cursor.execute(
        "SELECT TABLE_NAME, RECORD_COUNT FROM M_TABLES "
        f"WHERE SCHEMA_NAME = '{schema}' ORDER BY TABLE_NAME"
    )
    rows = cursor.fetchall()
    total = 0
    for table_name, count in rows:
        print(f"  {table_name:35s} {count:>8,}")
        total += count
    print(f"  {'TOTAL':35s} {total:>8,}")

    cursor.close()
    conn.close()
    print()
    print("=== Deployment complete ===")
    print(f"Connect: hdbsql -n {config['host']}:{config['port']} -u {config['user']} -d SYSTEMDB")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy procurement data to SAP HANA Cloud")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without connecting")
    parser.add_argument("--sql-dir", default="output/hana", help="Path to HANA SQL files")
    parser.add_argument("--schema", default=None, help="HANA schema name (default: PROCUREMENT)")
    args = parser.parse_args()

    config = get_config(args)
    deploy(config)


if __name__ == "__main__":
    main()

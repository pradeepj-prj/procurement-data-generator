#!/usr/bin/env python3
"""Deploy procurement knowledge graph to SAP HANA Cloud.

Creates vertex views, edge views, and a GRAPH WORKSPACE over the
existing 29 procurement tables.

Usage:
    python scripts/graph/deploy_graph.py [--dry-run] [--no-graph] [--sql-file PATH] [--schema SCHEMA]

Prerequisites:
    - pip install hdbcli
    - Relational data already loaded (run deploy_to_hana.py first)
    - Connection details in .env (see .env.example)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add project root to path for TABLE_ORDER import
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from procurement_generator.exporters.sql_exporter import TABLE_ORDER

DEFAULT_SQL_FILE = Path(__file__).resolve().parent / "create_graph_workspace.sql"


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
        "sql_file": Path(args.sql_file),
        "dry_run": args.dry_run,
        "no_graph": args.no_graph,
    }


def split_statements(sql_text: str) -> list[str]:
    """Split SQL text into individual statements.

    Handles DO BEGIN...END blocks and regular semicolon-delimited statements.
    """
    statements = []
    current: list[str] = []
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


def classify_statement(stmt: str) -> str:
    """Classify a SQL statement for filtering and reporting."""
    upper = stmt.upper()
    if "CREATE GRAPH WORKSPACE" in upper:
        return "create_graph"
    if "CREATE" in upper and "VIEW" in upper:
        view_name = ""
        for token in stmt.split('"'):
            if token.startswith("V_") or token.startswith("E_"):
                view_name = token
                break
        return f"create_view:{view_name}"
    return "other"


def deploy(config: dict) -> None:
    """Deploy graph workspace SQL to HANA Cloud."""
    sql_file = config["sql_file"]
    schema = config["schema"]
    dry_run = config["dry_run"]
    no_graph = config["no_graph"]

    if not sql_file.exists():
        print(f"ERROR: SQL file not found: {sql_file}")
        sys.exit(1)

    sql_text = sql_file.read_text(encoding="utf-8")
    # Replace hardcoded schema with configured schema
    if schema != "PROCUREMENT":
        sql_text = sql_text.replace('"PROCUREMENT"', f'"{schema}"')

    statements = split_statements(sql_text)

    # Filter out graph workspace statements if --no-graph
    if no_graph:
        statements = [
            s for s in statements
            if classify_statement(s) not in ("drop_graph", "create_graph")
        ]

    print("=== Graph Workspace Deployment ===")
    print(f"  Host:     {config['host']}")
    print(f"  Port:     {config['port']}")
    print(f"  User:     {config['user']}")
    print(f"  Schema:   {schema}")
    print(f"  SQL file: {sql_file}")
    print(f"  Mode:     {'SQL-only (no graph workspace)' if no_graph else 'Full graph workspace'}")
    if dry_run:
        print("  [DRY RUN] No connection will be made.")
    print()

    if dry_run:
        print(f"--- Statements to execute: {len(statements)} ---")
        for i, stmt in enumerate(statements, 1):
            cls = classify_statement(stmt)
            # Show a concise summary per statement
            first_line = stmt.strip().splitlines()[0][:100]
            print(f"  [{i:2d}] ({cls}) {first_line}")
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

    # Step 1: Connect
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

    # Step 2: Pre-check — verify base tables exist
    print()
    print("--- Step 2: Pre-check base tables ---")
    cursor.execute(
        "SELECT COUNT(*) FROM M_TABLES WHERE SCHEMA_NAME = ?",
        (schema,),
    )
    table_count = cursor.fetchone()[0]
    expected = len(TABLE_ORDER)
    if table_count < expected:
        print(f"  WARNING: Found {table_count} tables, expected {expected}.")
        print("  Run deploy_to_hana.py first to load relational data.")
    else:
        print(f"  Found {table_count} tables in schema \"{schema}\" (expected {expected}).")

    # Step 3: Drop existing graph workspace (must be done before replacing views)
    if not no_graph:
        print()
        print("--- Step 3: Drop existing graph workspace ---")
        try:
            cursor.execute(f'DROP GRAPH WORKSPACE "{schema}"."PROCUREMENT_KG"')
            conn.commit()
            print("  Dropped existing PROCUREMENT_KG.")
        except Exception:
            print("  No existing PROCUREMENT_KG (OK).")

    # Step 4: Execute SQL statements
    print()
    print("--- Step 4: Execute graph DDL ---")
    for i, stmt in enumerate(statements, 1):
        cls = classify_statement(stmt)
        try:
            cursor.execute(stmt)
            conn.commit()
            print(f"  [{i:2d}] OK  ({cls})")
        except Exception as e:
            print(f"  [{i:2d}] ERR ({cls}): {e}")
            cursor.close()
            conn.close()
            print()
            print("=== Deployment FAILED ===")
            sys.exit(1)

    # Step 5: Verification
    print()
    print("--- Step 5: Verification ---")

    # Vertex counts by type
    try:
        cursor.execute(
            f'SELECT vertex_type, COUNT(*) FROM "{schema}"."V_ALL_VERTICES" '
            "GROUP BY vertex_type ORDER BY vertex_type"
        )
        vertex_rows = cursor.fetchall()
        total_vertices = sum(r[1] for r in vertex_rows)
        print(f"  Vertices: {total_vertices:,} ({len(vertex_rows)} types)")
        for vtype, cnt in vertex_rows:
            print(f"    {vtype:20s} {cnt:>8,}")
    except Exception as e:
        print(f"  Could not query vertices: {e}")

    print()

    # Edge counts by type
    try:
        cursor.execute(
            f'SELECT edge_type, COUNT(*) FROM "{schema}"."E_ALL_EDGES" '
            "GROUP BY edge_type ORDER BY COUNT(*) DESC"
        )
        edge_rows = cursor.fetchall()
        total_edges = sum(r[1] for r in edge_rows)
        print(f"  Edges:    {total_edges:,} ({len(edge_rows)} types)")
        for etype, cnt in edge_rows:
            print(f"    {etype:25s} {cnt:>8,}")
    except Exception as e:
        print(f"  Could not query edges: {e}")

    print()

    # Graph workspace check
    if not no_graph:
        try:
            cursor.execute(
                "SELECT WORKSPACE_NAME FROM GRAPH_WORKSPACES "
                f"WHERE SCHEMA_NAME = '{schema}' AND WORKSPACE_NAME = 'PROCUREMENT_KG'"
            )
            ws_row = cursor.fetchone()
            if ws_row:
                print(f"  Workspace: {ws_row[0]} [CREATED]")
            else:
                print("  Workspace: PROCUREMENT_KG [NOT FOUND]")
        except Exception as e:
            print(f"  Could not verify workspace: {e}")
    else:
        print("  Workspace: skipped (--no-graph mode)")

    cursor.close()
    conn.close()
    print()
    print("=== Deployment complete ===")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deploy procurement knowledge graph to SAP HANA Cloud"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print statements without connecting"
    )
    parser.add_argument(
        "--sql-file", default=str(DEFAULT_SQL_FILE),
        help="Path to graph SQL file (default: scripts/graph/create_graph_workspace.sql)"
    )
    parser.add_argument(
        "--schema", default=None,
        help="HANA schema name (default: PROCUREMENT from .env)"
    )
    parser.add_argument(
        "--no-graph", action="store_true",
        help="SQL fallback: create vertex/edge views only, skip GRAPH WORKSPACE"
    )
    args = parser.parse_args()

    config = get_config(args)
    deploy(config)


if __name__ == "__main__":
    main()

"""SAP HANA Cloud SQL export: DDL + INSERT statements per table."""
from __future__ import annotations

from dataclasses import fields
from pathlib import Path

from .sql_exporter import _sql_value, _get_sql_type, PRIMARY_KEYS, TABLE_ORDER


def export_hana_cloud(store, output_dir: Path, schema: str = "PROCUREMENT") -> dict[str, int]:
    """Export all tables to HANA Cloud SQL files. Returns table -> row count."""
    output_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    all_tables = store.get_all_tables()

    for table_name in TABLE_ORDER:
        entities = all_tables.get(table_name, [])
        if not entities:
            counts[table_name] = 0
            continue

        filepath = output_dir / f"{table_name}.sql"
        entity_fields = fields(entities[0])
        field_names = [f.name for f in entity_fields]

        with open(filepath, "w", encoding="utf-8") as f:
            qualified = f'"{schema}"."{table_name}"'

            # Safe DROP using anonymous block (error code 259 = table not found)
            f.write(f"-- Table: {qualified}\n")
            f.write(f"-- Generated rows: {len(entities)}\n\n")
            f.write("DO BEGIN\n")
            f.write("  DECLARE EXIT HANDLER FOR SQL_ERROR_CODE 259 BEGIN END;\n")
            f.write(f"  DROP TABLE {qualified} CASCADE;\n")
            f.write("END;\n\n")

            # CREATE TABLE
            f.write(f"CREATE TABLE {qualified} (\n")

            col_defs = []
            for ef in entity_fields:
                sql_type = _get_sql_type(ef.name, str(ef.type))
                nullable = "Optional" in str(ef.type) or ef.name.endswith("_id") is False
                null_str = "" if nullable else " NOT NULL"
                col_defs.append(f"    {ef.name} {sql_type}{null_str}")

            # Add primary key constraint
            pk_cols = PRIMARY_KEYS.get(table_name)
            if pk_cols:
                col_defs.append(f"    PRIMARY KEY ({', '.join(pk_cols)})")

            f.write(",\n".join(col_defs))
            f.write("\n);\n\n")

            # INSERT statements — one per row (HANA does not support multi-row VALUES)
            cols = ", ".join(field_names)
            for entity in entities:
                vals = [_sql_value(getattr(entity, fn)) for fn in field_names]
                f.write(f"INSERT INTO {qualified} ({cols}) VALUES ({', '.join(vals)});\n")
            f.write("\n")

        counts[table_name] = len(entities)

    # Generate monolithic master load script
    _write_load_script(output_dir, schema, counts, all_tables)

    return counts


def _write_load_script(
    output_dir: Path, schema: str, counts: dict[str, int], all_tables: dict
) -> None:
    """Write _load_all_hana.sql — monolithic script (HANA has no \\i include)."""
    filepath = output_dir / "_load_all_hana.sql"
    with open(filepath, "w", encoding="utf-8") as f:
        active_tables = [t for t in TABLE_ORDER if counts.get(t, 0) > 0]
        f.write("-- Master load script for procurement data (SAP HANA Cloud)\n")
        f.write(f"-- Tables: {len(active_tables)}\n")
        f.write(f"-- Total rows: {sum(counts.values())}\n\n")

        # Create schema (error code 386 = schema already exists)
        f.write("DO BEGIN\n")
        f.write("  DECLARE EXIT HANDLER FOR SQL_ERROR_CODE 386 BEGIN END;\n")
        f.write(f'  CREATE SCHEMA "{schema}";\n')
        f.write("END;\n\n")

        # Concatenate each table file's content
        for table_name in active_tables:
            table_file = output_dir / f"{table_name}.sql"
            f.write(f"-- {'=' * 60}\n")
            f.write(f"-- {table_name}\n")
            f.write(f"-- {'=' * 60}\n")
            f.write(table_file.read_text(encoding="utf-8"))
            f.write("\n")

        f.write("-- Done.\n")

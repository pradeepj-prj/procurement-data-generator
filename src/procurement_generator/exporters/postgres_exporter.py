"""Postgres-compatible SQL export: DDL + INSERT statements per table."""
from __future__ import annotations

from dataclasses import fields
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from .sql_exporter import FIELD_TYPES, _sql_value, _get_sql_type

# Primary key definitions for each table
PRIMARY_KEYS = {
    "company_code": ["company_code"],
    "purchasing_org": ["purch_org_id"],
    "purchasing_group": ["purch_group_id"],
    "purchasing_group_category": ["purch_group_id", "category_id"],
    "plant": ["plant_id"],
    "storage_location": ["plant_id", "storage_loc_id"],
    "cost_center": ["cost_center_id"],
    "category_hierarchy": ["category_id"],
    "material_master": ["material_id"],
    "material_plant_extension": ["material_id", "plant_id"],
    "legal_entity": ["legal_entity_id"],
    "vendor_master": ["vendor_id"],
    "vendor_category": ["vendor_id", "category_id"],
    "vendor_address": ["vendor_id", "address_type"],
    "vendor_contact": ["contact_id"],
    "source_list": ["material_id", "vendor_id", "plant_id"],
    "contract_header": ["contract_id"],
    "contract_item": ["contract_id", "item_number"],
    "uom_conversion": ["material_id", "from_uom", "to_uom"],
    "pr_header": ["pr_id"],
    "pr_line_item": ["pr_id", "pr_line_number"],
    "po_header": ["po_id"],
    "po_line_item": ["po_id", "po_line_number"],
    "gr_header": ["gr_id"],
    "gr_line_item": ["gr_id", "gr_line_number"],
    "invoice_header": ["invoice_id"],
    "invoice_line_item": ["invoice_id", "invoice_line_number"],
    "payment": ["payment_id"],
    "payment_invoice_link": ["payment_id", "invoice_id"],
}

# FK-safe table ordering (matches pipeline generation order)
TABLE_ORDER = [
    "company_code",
    "purchasing_org",
    "purchasing_group",
    "purchasing_group_category",
    "plant",
    "storage_location",
    "cost_center",
    "category_hierarchy",
    "material_master",
    "material_plant_extension",
    "legal_entity",
    "vendor_master",
    "vendor_category",
    "vendor_address",
    "vendor_contact",
    "source_list",
    "contract_header",
    "contract_item",
    "uom_conversion",
    "pr_header",
    "pr_line_item",
    "po_header",
    "po_line_item",
    "gr_header",
    "gr_line_item",
    "invoice_header",
    "invoice_line_item",
    "payment",
    "payment_invoice_link",
]

# Postgres type overrides (where HANA types differ)
PG_TYPE_MAP = {
    "BOOLEAN": "BOOLEAN",
}


def _pg_type(sql_type: str) -> str:
    """Convert a HANA SQL type to Postgres-compatible type."""
    return PG_TYPE_MAP.get(sql_type, sql_type)


def export_postgres(store, output_dir: Path, schema: str = "procurement") -> dict[str, int]:
    """Export all tables to Postgres-compatible SQL files. Returns table -> row count."""
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
            qualified = f"{schema}.{table_name}"

            # DDL
            f.write(f"-- Table: {qualified}\n")
            f.write(f"-- Generated rows: {len(entities)}\n\n")
            f.write(f"DROP TABLE IF EXISTS {qualified} CASCADE;\n\n")
            f.write(f"CREATE TABLE {qualified} (\n")

            col_defs = []
            for ef in entity_fields:
                sql_type = _pg_type(_get_sql_type(ef.name, str(ef.type)))
                nullable = "Optional" in str(ef.type) or ef.name.endswith("_id") is False
                null_str = "" if nullable else " NOT NULL"
                col_defs.append(f"    {ef.name} {sql_type}{null_str}")

            # Add primary key constraint
            pk_cols = PRIMARY_KEYS.get(table_name)
            if pk_cols:
                col_defs.append(f"    PRIMARY KEY ({', '.join(pk_cols)})")

            f.write(",\n".join(col_defs))
            f.write("\n);\n\n")

            # INSERT statements in batches of 100
            batch_size = 100
            for batch_start in range(0, len(entities), batch_size):
                batch = entities[batch_start:batch_start + batch_size]
                cols = ", ".join(field_names)
                f.write(f"INSERT INTO {qualified} ({cols}) VALUES\n")

                rows = []
                for entity in batch:
                    vals = [_sql_value(getattr(entity, fn)) for fn in field_names]
                    rows.append(f"    ({', '.join(vals)})")

                f.write(",\n".join(rows))
                f.write(";\n\n")

        counts[table_name] = len(entities)

    # Generate master load script
    _write_load_script(output_dir, schema, counts)

    return counts


def _write_load_script(output_dir: Path, schema: str, counts: dict[str, int]) -> None:
    """Write _load_all.sql master script."""
    filepath = output_dir / "_load_all.sql"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("-- Master load script for procurement data (Postgres)\n")
        f.write(f"-- Tables: {len([c for c in counts.values() if c > 0])}\n")
        f.write(f"-- Total rows: {sum(counts.values())}\n\n")
        f.write(f"CREATE SCHEMA IF NOT EXISTS {schema};\n")
        f.write(f"SET search_path TO {schema};\n\n")

        for table_name in TABLE_ORDER:
            if counts.get(table_name, 0) > 0:
                f.write(f"\\i {table_name}.sql\n")

        f.write("\n-- Done.\n")

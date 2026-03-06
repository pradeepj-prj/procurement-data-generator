"""SQL export: DDL + INSERT statements per table, HANA-compatible."""
from __future__ import annotations

from dataclasses import fields
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

# SQL type mapping from Python types
TYPE_MAP = {
    "str": "VARCHAR(200)",
    "int": "INTEGER",
    "float": "DECIMAL(14,2)",
    "Decimal": "DECIMAL(14,2)",
    "bool": "BOOLEAN",
    "date": "DATE",
}

# Override specific field widths
FIELD_TYPES = {
    "company_code": "VARCHAR(4)",
    "company_name": "VARCHAR(100)",
    "country": "VARCHAR(2)",
    "currency": "VARCHAR(3)",
    "purch_org_id": "VARCHAR(4)",
    "purch_org_name": "VARCHAR(100)",
    "purch_group_id": "VARCHAR(8)",
    "purch_group_name": "VARCHAR(100)",
    "display_code": "VARCHAR(30)",
    "plant_id": "VARCHAR(4)",
    "plant_name": "VARCHAR(100)",
    "city": "VARCHAR(50)",
    "function": "VARCHAR(50)",
    "storage_loc_id": "VARCHAR(12)",
    "storage_loc_name": "VARCHAR(100)",
    "storage_type": "VARCHAR(30)",
    "cost_center_id": "VARCHAR(16)",
    "cost_center_name": "VARCHAR(100)",
    "department": "VARCHAR(50)",
    "category_id": "VARCHAR(20)",
    "category_name": "VARCHAR(100)",
    "level": "INTEGER",
    "parent_category_id": "VARCHAR(20)",
    "owner_purch_group_id": "VARCHAR(8)",
    "material_id": "VARCHAR(12)",
    "description": "VARCHAR(200)",
    "material_type": "VARCHAR(20)",
    "base_uom": "VARCHAR(6)",
    "standard_cost": "DECIMAL(12,2)",
    "criticality": "VARCHAR(10)",
    "criticality_reason_code": "VARCHAR(20)",
    "hazmat_flag": "BOOLEAN",
    "default_lead_time_days": "INTEGER",
    "make_or_buy": "VARCHAR(4)",
    "confidentiality_tier": "VARCHAR(12)",
    "reorder_point": "INTEGER",
    "lot_size": "INTEGER",
    "min_order_qty": "INTEGER",
    "legal_entity_id": "VARCHAR(12)",
    "legal_name": "VARCHAR(200)",
    "country_of_incorporation": "VARCHAR(2)",
    "registration_id": "VARCHAR(30)",
    "vendor_id": "VARCHAR(20)",
    "vendor_name": "VARCHAR(200)",
    "vendor_type": "VARCHAR(20)",
    "supported_categories": "VARCHAR(200)",
    "preferred_flag": "BOOLEAN",
    "incoterms_default": "VARCHAR(3)",
    "payment_terms": "VARCHAR(20)",
    "lead_time_days_typical": "INTEGER",
    "on_time_delivery_rate": "DECIMAL(5,2)",
    "quality_score": "INTEGER",
    "risk_score": "INTEGER",
    "esg_score": "INTEGER",
    "status": "VARCHAR(30)",
    "bank_account": "VARCHAR(40)",
    "alias_group": "VARCHAR(20)",
    "address_type": "VARCHAR(20)",
    "street": "VARCHAR(200)",
    "state_province": "VARCHAR(50)",
    "postal_code": "VARCHAR(20)",
    "contact_id": "VARCHAR(12)",
    "contact_name": "VARCHAR(100)",
    "email": "VARCHAR(100)",
    "phone": "VARCHAR(30)",
    "role": "VARCHAR(50)",
    "preferred_rank": "INTEGER",
    "contract_covered_flag": "BOOLEAN",
    "approval_status": "VARCHAR(20)",
    "lane_lead_time_days": "INTEGER",
    "vendor_material_code": "VARCHAR(30)",
    "valid_from": "DATE",
    "valid_to": "DATE",
    "contract_id": "VARCHAR(14)",
    "item_number": "INTEGER",
    "agreed_price": "DECIMAL(12,2)",
    "price_uom": "VARCHAR(6)",
    "max_quantity": "INTEGER",
    "target_value": "DECIMAL(12,2)",
    "consumed_quantity": "INTEGER",
    "consumed_value": "DECIMAL(12,2)",
    "from_uom": "VARCHAR(6)",
    "to_uom": "VARCHAR(6)",
    "conversion_factor": "DECIMAL(10,4)",
    "contract_type": "VARCHAR(10)",
    "incoterms": "VARCHAR(3)",
    # Transactional
    "pr_id": "VARCHAR(14)",
    "pr_date": "DATE",
    "requester_name": "VARCHAR(100)",
    "requester_department": "VARCHAR(50)",
    "pr_type": "VARCHAR(20)",
    "priority": "VARCHAR(10)",
    "notes": "VARCHAR(500)",
    "pr_line_number": "INTEGER",
    "quantity": "DECIMAL(12,2)",
    "uom": "VARCHAR(6)",
    "requested_delivery_date": "DATE",
    "estimated_price": "DECIMAL(12,2)",
    "assigned_purch_group_id": "VARCHAR(8)",
    "po_id": "VARCHAR(14)",
    "po_date": "DATE",
    "po_type": "VARCHAR(20)",
    "total_net_value": "DECIMAL(14,2)",
    "maverick_flag": "BOOLEAN",
    "po_line_number": "INTEGER",
    "unit_price": "DECIMAL(12,2)",
    "net_value": "DECIMAL(14,2)",
    "price_currency": "VARCHAR(3)",
    "actual_delivery_date": "DATE",
    "contract_item_number": "INTEGER",
    "over_delivery_tolerance": "DECIMAL(5,2)",
    "under_delivery_tolerance": "DECIMAL(5,2)",
    "gr_status": "VARCHAR(10)",
    "invoice_status": "VARCHAR(10)",
    "gr_id": "VARCHAR(14)",
    "gr_date": "DATE",
    "received_by": "VARCHAR(100)",
    "gr_line_number": "INTEGER",
    "quantity_received": "DECIMAL(12,2)",
    "quantity_accepted": "DECIMAL(12,2)",
    "quantity_rejected": "DECIMAL(12,2)",
    "rejection_reason": "VARCHAR(100)",
    "batch_number": "VARCHAR(30)",
    "invoice_id": "VARCHAR(14)",
    "vendor_invoice_number": "VARCHAR(30)",
    "invoice_date": "DATE",
    "received_date": "DATE",
    "total_gross_amount": "DECIMAL(14,2)",
    "tax_amount": "DECIMAL(12,2)",
    "total_net_amount": "DECIMAL(14,2)",
    "match_status": "VARCHAR(20)",
    "payment_due_date": "DATE",
    "payment_block": "BOOLEAN",
    "block_reason": "VARCHAR(100)",
    "invoice_line_number": "INTEGER",
    "quantity_invoiced": "DECIMAL(12,2)",
    "unit_price_invoiced": "DECIMAL(12,2)",
    "net_amount": "DECIMAL(14,2)",
    "price_variance": "DECIMAL(12,2)",
    "quantity_variance": "DECIMAL(12,2)",
    "payment_id": "VARCHAR(14)",
    "payment_date": "DATE",
    "payment_method": "VARCHAR(20)",
    "total_amount": "DECIMAL(14,2)",
    "bank_account_ref": "VARCHAR(40)",
    "payment_terms_applied": "VARCHAR(20)",
    "early_payment_discount": "DECIMAL(12,2)",
    "amount_applied": "DECIMAL(14,2)",
    "storage_loc_id": "VARCHAR(12)",
}


def _sql_value(val: Any) -> str:
    """Convert a Python value to a SQL literal."""
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, date):
        return f"'{val.isoformat()}'"
    if isinstance(val, (int, float, Decimal)):
        return str(val)
    # String - escape single quotes
    s = str(val).replace("'", "''")
    return f"'{s}'"


def _get_sql_type(field_name: str, field_type_str: str) -> str:
    """Get SQL type for a field."""
    if field_name in FIELD_TYPES:
        return FIELD_TYPES[field_name]
    # Clean up type string
    clean = field_type_str.replace("typing.Optional[", "").replace("]", "")
    clean = clean.replace("<class '", "").replace("'>", "")
    if "Decimal" in clean:
        return "DECIMAL(14,2)"
    if "int" in clean:
        return "INTEGER"
    if "bool" in clean:
        return "BOOLEAN"
    if "date" in clean:
        return "DATE"
    return "VARCHAR(200)"


def export_sql(store, output_dir: Path) -> dict[str, int]:
    """Export all tables to SQL files with DDL + INSERT. Returns table -> row count."""
    output_dir.mkdir(parents=True, exist_ok=True)
    counts = {}

    for table_name, entities in store.get_all_tables().items():
        if not entities:
            counts[table_name] = 0
            continue

        filepath = output_dir / f"{table_name}.sql"
        entity_fields = fields(entities[0])
        field_names = [f.name for f in entity_fields]

        with open(filepath, "w", encoding="utf-8") as f:
            # DDL
            f.write(f"-- Table: {table_name}\n")
            f.write(f"-- Generated rows: {len(entities)}\n\n")
            f.write(f"CREATE TABLE {table_name} (\n")
            col_defs = []
            for ef in entity_fields:
                sql_type = _get_sql_type(ef.name, str(ef.type))
                nullable = "Optional" in str(ef.type) or ef.name.endswith("_id") is False
                null_str = "" if nullable else " NOT NULL"
                col_defs.append(f"    {ef.name} {sql_type}{null_str}")
            f.write(",\n".join(col_defs))
            f.write("\n);\n\n")

            # INSERT statements in batches of 100
            batch_size = 100
            for batch_start in range(0, len(entities), batch_size):
                batch = entities[batch_start:batch_start + batch_size]
                cols = ", ".join(field_names)
                f.write(f"INSERT INTO {table_name} ({cols}) VALUES\n")

                rows = []
                for entity in batch:
                    vals = [_sql_value(getattr(entity, fn)) for fn in field_names]
                    rows.append(f"    ({', '.join(vals)})")

                f.write(",\n".join(rows))
                f.write(";\n\n")

        counts[table_name] = len(entities)

    return counts

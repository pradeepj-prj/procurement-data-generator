"""CSV export: one file per table."""
from __future__ import annotations

import csv
from dataclasses import fields, asdict
from datetime import date
from decimal import Decimal
from pathlib import Path


def export_csv(store, output_dir: Path) -> dict[str, int]:
    """Export all tables to CSV files. Returns dict of table_name -> row_count."""
    output_dir.mkdir(parents=True, exist_ok=True)
    counts = {}

    for table_name, entities in store.get_all_tables().items():
        if not entities:
            counts[table_name] = 0
            continue

        filepath = output_dir / f"{table_name}.csv"
        field_names = [f.name for f in fields(entities[0])]

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(field_names)

            for entity in entities:
                row = []
                for fname in field_names:
                    val = getattr(entity, fname)
                    if val is None:
                        row.append("")
                    elif isinstance(val, bool):
                        row.append("TRUE" if val else "FALSE")
                    elif isinstance(val, date):
                        row.append(val.isoformat())
                    elif isinstance(val, Decimal):
                        row.append(str(val))
                    else:
                        row.append(str(val))
                writer.writerow(row)

        counts[table_name] = len(entities)

    return counts

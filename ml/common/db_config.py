"""Dual data loader: CSV files and Postgres database.

Provides a unified interface to load procurement tables from either
local CSV exports or a Postgres database.
"""

import os
from decimal import Decimal
from pathlib import Path

import pandas as pd


# Boolean columns across tables (CSV uses TRUE/FALSE strings)
_BOOL_COLUMNS = {
    "preferred_flag", "maverick_flag", "payment_block", "hazmat_flag",
}

# Date columns (ISO format strings → Timestamp)
_DATE_COLUMNS = {
    "po_date", "pr_date", "gr_date", "invoice_date", "received_date",
    "payment_due_date", "payment_date", "valid_from", "valid_to",
    "requested_delivery_date", "actual_delivery_date", "creation_date",
    "time_window_start", "time_window_end", "demo_reference_date",
}

# Decimal / numeric columns to coerce to float64
_DECIMAL_COLUMNS = {
    "total_net_value", "total_gross_amount", "tax_amount", "total_net_amount",
    "net_value", "net_amount", "unit_price", "unit_price_invoiced",
    "standard_cost", "agreed_price", "quantity", "quantity_invoiced",
    "quantity_received", "quantity_accepted", "quantity_rejected",
    "price_variance", "quantity_variance", "over_delivery_tolerance",
    "under_delivery_tolerance", "on_time_delivery_rate", "quality_score",
    "risk_score", "esg_score", "payment_amount", "discount_amount",
    "consumed_quantity", "consumed_value", "max_quantity", "target_value",
    "lead_time_days_typical", "default_lead_time_days",
}


def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce CSV string values to appropriate Python/pandas types."""
    df = df.copy()

    for col in df.columns:
        if col in _BOOL_COLUMNS:
            df[col] = df[col].map({"TRUE": True, "FALSE": False, "": None, True: True, False: False})
        elif col in _DATE_COLUMNS:
            df[col] = pd.to_datetime(df[col], errors="coerce")
        elif col in _DECIMAL_COLUMNS:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def load_table_csv(csv_dir: str | Path, table_name: str) -> pd.DataFrame:
    """Load a single table from CSV with type coercion.

    Args:
        csv_dir: Path to directory containing CSV files.
        table_name: Name of the table (without .csv extension).

    Returns:
        DataFrame with coerced types.
    """
    filepath = Path(csv_dir) / f"{table_name}.csv"
    if not filepath.exists():
        raise FileNotFoundError(f"CSV file not found: {filepath}")

    df = pd.read_csv(filepath, dtype=str, keep_default_na=False)
    # Replace empty strings with NaN for proper null handling
    df = df.replace("", pd.NA)
    df = _coerce_types(df)
    return df


def load_table_pg(conn, table_name: str, schema: str = "procurement") -> pd.DataFrame:
    """Load a single table from Postgres.

    Args:
        conn: psycopg2 or SQLAlchemy connection.
        table_name: Name of the table.
        schema: Database schema (default: procurement).

    Returns:
        DataFrame with table data.
    """
    query = f'SELECT * FROM "{schema}"."{table_name}"'
    return pd.read_sql(query, conn)


def load_tables(
    source: str,
    tables: list[str],
    csv_dir: str | Path | None = None,
    conn=None,
) -> dict[str, pd.DataFrame]:
    """Load multiple tables from the specified source.

    Args:
        source: Either "csv" or "postgres".
        tables: List of table names to load.
        csv_dir: Path to CSV directory (required if source="csv").
        conn: Database connection (required if source="postgres").

    Returns:
        Dictionary mapping table_name -> DataFrame.
    """
    result = {}
    for table in tables:
        if source == "csv":
            if csv_dir is None:
                raise ValueError("csv_dir required when source='csv'")
            result[table] = load_table_csv(csv_dir, table)
        elif source == "postgres":
            if conn is None:
                raise ValueError("conn required when source='postgres'")
            result[table] = load_table_pg(conn, table)
        else:
            raise ValueError(f"Unknown source: {source}. Use 'csv' or 'postgres'.")
    return result


def get_pg_connection(env_path: str | Path = ".env"):
    """Create a Postgres connection using credentials from .env file.

    Expected .env variables: EC2_IP, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT.

    Returns:
        psycopg2 connection object.
    """
    import psycopg2

    env_vars = {}
    env_file = Path(env_path)
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    env_vars[key.strip()] = value.strip().strip('"').strip("'")

    return psycopg2.connect(
        host=env_vars.get("EC2_IP", os.getenv("EC2_IP", "localhost")),
        dbname=env_vars.get("DB_NAME", os.getenv("DB_NAME", "procurement_demo")),
        user=env_vars.get("DB_USER", os.getenv("DB_USER", "procurement_user")),
        password=env_vars.get("DB_PASSWORD", os.getenv("DB_PASSWORD", "")),
        port=int(env_vars.get("DB_PORT", os.getenv("DB_PORT", "5432"))),
    )

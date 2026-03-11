"""Tests for the HANA Cloud exporter."""
from __future__ import annotations

import re
from dataclasses import dataclass, fields
from decimal import Decimal
from pathlib import Path
from typing import Optional

import pytest

from procurement_generator.exporters.hana_exporter import export_hana_cloud
from procurement_generator.exporters.sql_exporter import PRIMARY_KEYS, TABLE_ORDER


# --- Minimal mock entities ---


@dataclass
class MockCompanyCode:
    company_code: str
    company_name: str
    country: str
    currency: str


@dataclass
class MockVendorMaster:
    vendor_id: str
    vendor_name: str
    status: str
    risk_score: Optional[int] = None


# --- Mock DataStore ---


class MockDataStore:
    """Minimal DataStore mock with a few tables."""

    def __init__(self):
        self.company_codes = [
            MockCompanyCode("1000", "AMR Corp", "US", "USD"),
            MockCompanyCode("2000", "AMR Europe", "DE", "EUR"),
        ]
        self.vendors = [
            MockVendorMaster("VND-US-00001", "Acme Supply", "ACTIVE", 25),
            MockVendorMaster("VND-DE-00002", "O'Reilly Parts", "ACTIVE", None),
        ]

    def get_all_tables(self) -> dict:
        return {
            "company_code": self.company_codes,
            "vendor_master": self.vendors,
        }


# --- Tests ---


class TestHanaExporterDDL:
    """Test DDL generation for HANA Cloud."""

    def test_creates_output_directory(self, tmp_path):
        store = MockDataStore()
        output_dir = tmp_path / "hana"
        export_hana_cloud(store, output_dir)
        assert output_dir.exists()

    def test_generates_table_files(self, tmp_path):
        store = MockDataStore()
        counts = export_hana_cloud(store, tmp_path)
        assert (tmp_path / "company_code.sql").exists()
        assert (tmp_path / "vendor_master.sql").exists()
        assert counts["company_code"] == 2
        assert counts["vendor_master"] == 2

    def test_generates_master_script(self, tmp_path):
        store = MockDataStore()
        export_hana_cloud(store, tmp_path)
        master = tmp_path / "_load_all_hana.sql"
        assert master.exists()
        content = master.read_text()
        assert "SAP HANA Cloud" in content
        assert "PROCUREMENT" in content

    def test_schema_qualification(self, tmp_path):
        store = MockDataStore()
        export_hana_cloud(store, tmp_path)
        sql = (tmp_path / "company_code.sql").read_text()
        assert '"PROCUREMENT"."company_code"' in sql

    def test_custom_schema(self, tmp_path):
        store = MockDataStore()
        export_hana_cloud(store, tmp_path, schema="MY_SCHEMA")
        sql = (tmp_path / "company_code.sql").read_text()
        assert '"MY_SCHEMA"."company_code"' in sql

    def test_drop_block_syntax(self, tmp_path):
        store = MockDataStore()
        export_hana_cloud(store, tmp_path)
        sql = (tmp_path / "company_code.sql").read_text()
        assert "DO BEGIN" in sql
        assert "SQL_ERROR_CODE 259" in sql
        assert "DROP TABLE" in sql
        assert "CASCADE" in sql

    def test_primary_key_constraint(self, tmp_path):
        store = MockDataStore()
        export_hana_cloud(store, tmp_path)
        sql = (tmp_path / "company_code.sql").read_text()
        assert "PRIMARY KEY (company_code)" in sql

    def test_insert_values(self, tmp_path):
        store = MockDataStore()
        export_hana_cloud(store, tmp_path)
        sql = (tmp_path / "company_code.sql").read_text()
        assert "'AMR Corp'" in sql
        assert "'1000'" in sql
        assert "'USD'" in sql

    def test_single_quote_escaping(self, tmp_path):
        store = MockDataStore()
        export_hana_cloud(store, tmp_path)
        sql = (tmp_path / "vendor_master.sql").read_text()
        # O'Reilly should be escaped as O''Reilly
        assert "O''Reilly" in sql

    def test_null_values(self, tmp_path):
        store = MockDataStore()
        export_hana_cloud(store, tmp_path)
        sql = (tmp_path / "vendor_master.sql").read_text()
        # Second vendor has risk_score=None
        assert "NULL" in sql

    def test_empty_tables_get_zero_count(self, tmp_path):
        store = MockDataStore()
        counts = export_hana_cloud(store, tmp_path)
        # Tables not in mock store should have 0 count
        assert counts.get("plant", 0) == 0

    def test_no_file_for_empty_table(self, tmp_path):
        store = MockDataStore()
        export_hana_cloud(store, tmp_path)
        # plant has no data, so no file should be created
        assert not (tmp_path / "plant.sql").exists()


class TestHanaMasterScript:
    """Test the monolithic _load_all_hana.sql master script."""

    def test_contains_schema_creation(self, tmp_path):
        store = MockDataStore()
        export_hana_cloud(store, tmp_path)
        master = (tmp_path / "_load_all_hana.sql").read_text()
        assert 'CREATE SCHEMA "PROCUREMENT"' in master
        assert "SQL_ERROR_CODE 386" in master

    def test_contains_all_table_sql(self, tmp_path):
        store = MockDataStore()
        export_hana_cloud(store, tmp_path)
        master = (tmp_path / "_load_all_hana.sql").read_text()
        # Should contain actual DDL+INSERT, not \i references
        assert "CREATE TABLE" in master
        assert "INSERT INTO" in master
        assert "\\i" not in master

    def test_fk_safe_ordering(self, tmp_path):
        store = MockDataStore()
        export_hana_cloud(store, tmp_path)
        master = (tmp_path / "_load_all_hana.sql").read_text()
        # company_code should appear before vendor_master
        cc_pos = master.index("company_code")
        vm_pos = master.index("vendor_master")
        assert cc_pos < vm_pos


class TestSharedConstants:
    """Verify PRIMARY_KEYS and TABLE_ORDER are properly shared."""

    def test_table_order_has_29_tables(self):
        assert len(TABLE_ORDER) == 29

    def test_primary_keys_cover_all_tables(self):
        assert set(PRIMARY_KEYS.keys()) == set(TABLE_ORDER)

    def test_postgres_imports_from_sql_exporter(self):
        """Verify postgres_exporter imports shared constants."""
        from procurement_generator.exporters.postgres_exporter import PRIMARY_KEYS as PG_PK
        from procurement_generator.exporters.postgres_exporter import TABLE_ORDER as PG_TO
        assert PG_PK is PRIMARY_KEYS
        assert PG_TO is TABLE_ORDER

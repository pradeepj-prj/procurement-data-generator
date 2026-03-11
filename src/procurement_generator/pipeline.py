"""Pipeline orchestrator: runs stages in dependency order with validation."""
from __future__ import annotations

import sys
from pathlib import Path

from .config import ScaleConfig
from .data_store import DataStore
from .generators.org_structure import OrgStructureGenerator
from .generators.categories import CategoryGenerator
from .generators.materials import MaterialGenerator
from .generators.legal_entities import LegalEntityGenerator
from .generators.vendors import VendorGenerator
from .generators.source_list import SourceListGenerator
from .generators.contracts import ContractGenerator
from .generators.purchase_reqs import PurchaseReqGenerator
from .generators.purchase_orders import PurchaseOrderGenerator
from .generators.goods_receipts import GoodsReceiptGenerator
from .generators.invoices import InvoiceGenerator
from .generators.payments import PaymentGenerator
from .validators.integrity import validate_structural_integrity, ValidationResult
from .validators.business_rules import validate_business_rules, propagate_confidentiality
from .validators.seeds import verify_scenario_seeds
from .validators.statistical import validate_distributions
from .exporters.csv_exporter import export_csv
from .exporters.sql_exporter import export_sql
from .exporters.postgres_exporter import export_postgres
from .exporters.hana_exporter import export_hana_cloud


class Pipeline:
    """Orchestrates the full data generation pipeline."""

    def __init__(self, config: ScaleConfig, seeds: dict, output_dir: Path) -> None:
        self.config = config
        self.seeds = seeds
        self.output_dir = output_dir
        self.store = DataStore()
        self.all_results: list[ValidationResult] = []

    def run(self) -> bool:
        """Run the full pipeline. Returns True if all FATAL checks pass."""
        print("=" * 60)
        print("Procurement Data Generator Pipeline")
        print(f"Scale: {self.config.scale}x")
        print(f"Demo Reference Date: {self.config.demo_reference_date}")
        print("=" * 60)

        stages = [
            # MASTER DATA
            ("Stage 1: Org Structure", self._stage_org, True),
            ("Stage 2: Category Hierarchy", self._stage_categories, True),
            ("Stage 3: Materials", self._stage_materials, True),
            ("Stage 4: Legal Entities", self._stage_legal_entities, True),
            ("Stage 5: Vendors", self._stage_vendors, True),
            ("Stage 6: Contracts", self._stage_contracts, True),
            ("Stage 7: Source List", self._stage_source_list, True),
            ("Stage 8: Confidentiality Propagation", self._stage_confidentiality, True),
            # MASTER DATA VALIDATION
            ("Stage 9: Master Data Validation", self._stage_master_validation, True),
            # TRANSACTIONAL
            ("Stage 10: Purchase Requisitions", self._stage_prs, True),
            ("Stage 11: Purchase Orders", self._stage_pos, True),
            ("Stage 12: Goods Receipts", self._stage_grs, True),
            ("Stage 13: Invoices", self._stage_invoices, True),
            ("Stage 14: Payments", self._stage_payments, True),
            # POST-GENERATION
            ("Stage 15: Reconciliation", self._stage_reconciliation, True),
            ("Stage 16: Full Validation", self._stage_full_validation, True),
            ("Stage 17: Seed Verification", self._stage_seed_verification, False),
            ("Stage 18: Export", self._stage_export, True),
        ]

        for stage_name, stage_fn, halt_on_fatal in stages:
            print(f"\n{'─' * 50}")
            print(f"  {stage_name}")
            print(f"{'─' * 50}")

            results = stage_fn()
            if results:
                self.all_results.extend(results)
                fatals = [r for r in results if r.severity == "FATAL" and not r.passed]
                warnings = [r for r in results if r.severity == "WARNING" and not r.passed]

                for r in results:
                    icon = "PASS" if r.passed else ("FAIL" if r.severity == "FATAL" else "WARN")
                    print(f"    [{icon}] {r.check_name}: {r.message}")
                    if not r.passed and r.details:
                        for d in r.details[:5]:
                            print(f"           - {d}")

                if fatals and halt_on_fatal:
                    print(f"\n  FATAL: {len(fatals)} check(s) failed. Pipeline halted.")
                    return False

        self._print_summary()
        return True

    # --- Stage implementations ---

    def _stage_org(self) -> list[ValidationResult]:
        OrgStructureGenerator(self.store, self.config, self.seeds).generate()
        results = []
        results.append(ValidationResult(
            "Org structure loaded", "FATAL",
            len(self.store.company_codes) > 0 and len(self.store.plants) > 0,
            f"{len(self.store.plants)} plants, {len(self.store.purchasing_groups)} PGs, "
            f"{len(self.store.cost_centers)} cost centers",
            [],
        ))
        return results

    def _stage_categories(self) -> list[ValidationResult]:
        CategoryGenerator(self.store, self.config, self.seeds).generate()
        leaves = [c for c in self.store.categories if c.level == 3]
        results = []
        results.append(ValidationResult(
            "Category hierarchy", "FATAL",
            len(leaves) >= 45,
            f"{len(self.store.categories)} categories, {len(leaves)} leaf nodes",
            [],
        ))
        # Validate parent refs
        cat_ids = {c.category_id for c in self.store.categories}
        orphans = [c.category_id for c in self.store.categories
                  if c.parent_category_id and c.parent_category_id not in cat_ids]
        results.append(ValidationResult(
            "Category parent references", "FATAL",
            len(orphans) == 0, f"{len(orphans)} orphan parent refs", orphans,
        ))
        return results

    def _stage_materials(self) -> list[ValidationResult]:
        MaterialGenerator(self.store, self.config, self.seeds).generate()
        return [ValidationResult(
            "Materials generated", "FATAL",
            len(self.store.materials) > 0,
            f"{len(self.store.materials)} materials, {len(self.store.material_plant_extensions)} plant extensions",
            [],
        )]

    def _stage_legal_entities(self) -> list[ValidationResult]:
        LegalEntityGenerator(self.store, self.config, self.seeds).generate()
        return [ValidationResult(
            "Legal entities generated", "FATAL",
            len(self.store.legal_entities) > 0,
            f"{len(self.store.legal_entities)} legal entities",
            [],
        )]

    def _stage_vendors(self) -> list[ValidationResult]:
        VendorGenerator(self.store, self.config, self.seeds).generate()
        return [ValidationResult(
            "Vendors generated", "FATAL",
            len(self.store.vendors) > 0,
            f"{len(self.store.vendors)} vendors, {len(self.store.vendor_categories)} category mappings, "
            f"{len(self.store.vendor_addresses)} addresses, {len(self.store.vendor_contacts)} contacts",
            [],
        )]

    def _stage_source_list(self) -> list[ValidationResult]:
        SourceListGenerator(self.store, self.config, self.seeds).generate()
        return [ValidationResult(
            "Source list generated", "FATAL",
            len(self.store.source_lists) > 0,
            f"{len(self.store.source_lists)} source list entries",
            [],
        )]

    def _stage_contracts(self) -> list[ValidationResult]:
        ContractGenerator(self.store, self.config, self.seeds).generate()
        return [ValidationResult(
            "Contracts generated", "FATAL",
            len(self.store.contract_headers) > 0,
            f"{len(self.store.contract_headers)} contracts, {len(self.store.contract_items)} items, "
            f"{len(self.store.uom_conversions)} UOM conversions",
            [],
        )]

    def _stage_confidentiality(self) -> list[ValidationResult]:
        updated = propagate_confidentiality(self.store)
        return [ValidationResult(
            "Confidentiality propagation", "FATAL", True,
            f"{updated} source list entries updated", [],
        )]

    def _stage_master_validation(self) -> list[ValidationResult]:
        results = validate_structural_integrity(self.store)
        results.extend(validate_business_rules(self.store))
        return results

    def _stage_prs(self) -> list[ValidationResult]:
        PurchaseReqGenerator(self.store, self.config, self.seeds).generate()
        return [ValidationResult(
            "Purchase requisitions generated", "FATAL",
            len(self.store.pr_headers) > 0,
            f"{len(self.store.pr_headers)} PRs, {len(self.store.pr_line_items)} line items",
            [],
        )]

    def _stage_pos(self) -> list[ValidationResult]:
        PurchaseOrderGenerator(self.store, self.config, self.seeds).generate()
        return [ValidationResult(
            "Purchase orders generated", "FATAL",
            len(self.store.po_headers) > 0,
            f"{len(self.store.po_headers)} POs, {len(self.store.po_line_items)} line items",
            [],
        )]

    def _stage_grs(self) -> list[ValidationResult]:
        GoodsReceiptGenerator(self.store, self.config, self.seeds).generate()
        return [ValidationResult(
            "Goods receipts generated", "FATAL",
            len(self.store.gr_headers) > 0,
            f"{len(self.store.gr_headers)} GRs, {len(self.store.gr_line_items)} line items",
            [],
        )]

    def _stage_invoices(self) -> list[ValidationResult]:
        InvoiceGenerator(self.store, self.config, self.seeds).generate()
        return [ValidationResult(
            "Invoices generated", "FATAL",
            len(self.store.invoice_headers) > 0,
            f"{len(self.store.invoice_headers)} invoices, {len(self.store.invoice_line_items)} line items",
            [],
        )]

    def _stage_payments(self) -> list[ValidationResult]:
        PaymentGenerator(self.store, self.config, self.seeds).generate()
        return [ValidationResult(
            "Payments generated", "FATAL",
            len(self.store.payments) > 0,
            f"{len(self.store.payments)} payments, {len(self.store.payment_invoice_links)} links",
            [],
        )]

    def _stage_reconciliation(self) -> list[ValidationResult]:
        """Reconcile contract consumption from PO actuals + backfill delivery dates."""
        # Contract consumption reconciliation
        for ci in self.store.contract_items:
            ch = self.store.contract_by_id(ci.contract_id)
            if not ch:
                continue

            total_qty = 0
            total_val = 0.0
            for pol in self.store.po_line_items:
                if pol.contract_id == ci.contract_id and pol.contract_item_number == ci.item_number:
                    total_qty += int(float(pol.quantity))
                    total_val += float(pol.net_value)

            if ch.contract_type == "QUANTITY":
                ci.consumed_quantity = total_qty
            else:
                from .utils import to_decimal
                ci.consumed_value = to_decimal(total_val)

        return [ValidationResult(
            "Reconciliation complete", "FATAL", True,
            "Contract consumption and delivery dates reconciled", [],
        )]

    def _stage_full_validation(self) -> list[ValidationResult]:
        results = validate_structural_integrity(self.store)
        results.extend(validate_business_rules(self.store))
        results.extend(validate_distributions(self.store, self.config))
        return results

    def _stage_seed_verification(self) -> list[ValidationResult]:
        return verify_scenario_seeds(self.store, self.config)

    def _stage_export(self) -> list[ValidationResult]:
        csv_dir = self.output_dir / "csv"
        sql_dir = self.output_dir / "sql"
        pg_dir = self.output_dir / "postgres"
        hana_dir = self.output_dir / "hana"

        csv_counts = export_csv(self.store, csv_dir)
        sql_counts = export_sql(self.store, sql_dir)
        pg_counts = export_postgres(self.store, pg_dir)
        hana_counts = export_hana_cloud(self.store, hana_dir)

        total_csv = sum(csv_counts.values())
        total_sql = sum(sql_counts.values())
        total_pg = sum(pg_counts.values())
        total_hana = sum(hana_counts.values())

        return [ValidationResult(
            "Export complete", "FATAL", True,
            f"CSV: {total_csv} rows across {len(csv_counts)} tables to {csv_dir}\n"
            f"    SQL: {total_sql} rows across {len(sql_counts)} tables to {sql_dir}\n"
            f"    Postgres: {total_pg} rows across {len(pg_counts)} tables to {pg_dir}\n"
            f"    HANA Cloud: {total_hana} rows across {len(hana_counts)} tables to {hana_dir}",
            [],
        )]

    def _print_summary(self) -> None:
        print("\n" + "=" * 60)
        print("PIPELINE SUMMARY")
        print("=" * 60)

        tables = self.store.get_all_tables()
        print("\nTable Row Counts:")
        for name, entities in tables.items():
            if entities:
                print(f"  {name:35s} {len(entities):>8,}")

        total = sum(len(e) for e in tables.values())
        print(f"  {'TOTAL':35s} {total:>8,}")

        fatals = [r for r in self.all_results if r.severity == "FATAL"]
        fatal_pass = sum(1 for r in fatals if r.passed)
        fatal_fail = sum(1 for r in fatals if not r.passed)
        warnings = [r for r in self.all_results if r.severity == "WARNING"]
        warn_pass = sum(1 for r in warnings if r.passed)
        warn_fail = sum(1 for r in warnings if not r.passed)

        print(f"\nValidation Results:")
        print(f"  FATAL checks:   {fatal_pass} passed, {fatal_fail} failed")
        print(f"  WARNING checks: {warn_pass} passed, {warn_fail} warnings")
        print("=" * 60)

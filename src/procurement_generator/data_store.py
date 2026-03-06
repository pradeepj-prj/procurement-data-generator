"""Central data store holding all generated entities."""
from __future__ import annotations

from dataclasses import fields
from typing import Any

from .models import (
    CompanyCode, PurchasingOrg, PurchasingGroup, PurchasingGroupCategory,
    Plant, StorageLocation, CostCenter, CategoryHierarchy,
    MaterialMaster, MaterialPlantExtension,
    LegalEntity, VendorMaster, VendorCategory, VendorAddress, VendorContact,
    SourceList, ContractHeader, ContractItem, UOMConversion,
    PRHeader, PRLineItem, POHeader, POLineItem,
    GRHeader, GRLineItem, InvoiceHeader, InvoiceLineItem,
    Payment, PaymentInvoiceLink,
)


class DataStore:
    """Holds all generated entities as typed lists."""

    def __init__(self) -> None:
        self.company_codes: list[CompanyCode] = []
        self.purchasing_orgs: list[PurchasingOrg] = []
        self.purchasing_groups: list[PurchasingGroup] = []
        self.pg_category_mappings: list[PurchasingGroupCategory] = []
        self.plants: list[Plant] = []
        self.storage_locations: list[StorageLocation] = []
        self.cost_centers: list[CostCenter] = []
        self.categories: list[CategoryHierarchy] = []
        self.materials: list[MaterialMaster] = []
        self.material_plant_extensions: list[MaterialPlantExtension] = []
        self.legal_entities: list[LegalEntity] = []
        self.vendors: list[VendorMaster] = []
        self.vendor_categories: list[VendorCategory] = []
        self.vendor_addresses: list[VendorAddress] = []
        self.vendor_contacts: list[VendorContact] = []
        self.source_lists: list[SourceList] = []
        self.contract_headers: list[ContractHeader] = []
        self.contract_items: list[ContractItem] = []
        self.uom_conversions: list[UOMConversion] = []
        self.pr_headers: list[PRHeader] = []
        self.pr_line_items: list[PRLineItem] = []
        self.po_headers: list[POHeader] = []
        self.po_line_items: list[POLineItem] = []
        self.gr_headers: list[GRHeader] = []
        self.gr_line_items: list[GRLineItem] = []
        self.invoice_headers: list[InvoiceHeader] = []
        self.invoice_line_items: list[InvoiceLineItem] = []
        self.payments: list[Payment] = []
        self.payment_invoice_links: list[PaymentInvoiceLink] = []

    # --- Lookup helpers ---

    def material_by_id(self, material_id: str) -> MaterialMaster | None:
        for m in self.materials:
            if m.material_id == material_id:
                return m
        return None

    def vendor_by_id(self, vendor_id: str) -> VendorMaster | None:
        for v in self.vendors:
            if v.vendor_id == vendor_id:
                return v
        return None

    def contract_by_id(self, contract_id: str) -> ContractHeader | None:
        for c in self.contract_headers:
            if c.contract_id == contract_id:
                return c
        return None

    def plant_by_id(self, plant_id: str) -> Plant | None:
        for p in self.plants:
            if p.plant_id == plant_id:
                return p
        return None

    def category_by_id(self, category_id: str) -> CategoryHierarchy | None:
        for c in self.categories:
            if c.category_id == category_id:
                return c
        return None

    def material_ids(self) -> set[str]:
        return {m.material_id for m in self.materials}

    def vendor_ids(self) -> set[str]:
        return {v.vendor_id for v in self.vendors}

    def plant_ids(self) -> set[str]:
        return {p.plant_id for p in self.plants}

    def category_ids(self) -> set[str]:
        return {c.category_id for c in self.categories}

    def leaf_category_ids(self) -> set[str]:
        return {c.category_id for c in self.categories if c.level == 3}

    def purch_group_ids(self) -> set[str]:
        return {pg.purch_group_id for pg in self.purchasing_groups}

    def legal_entity_ids(self) -> set[str]:
        return {le.legal_entity_id for le in self.legal_entities}

    def cost_center_ids(self) -> set[str]:
        return {cc.cost_center_id for cc in self.cost_centers}

    def storage_locs_for_plant(self, plant_id: str) -> list[StorageLocation]:
        return [sl for sl in self.storage_locations if sl.plant_id == plant_id]

    def cost_centers_for_plant(self, plant_id: str) -> list[CostCenter]:
        return [cc for cc in self.cost_centers if cc.plant_id == plant_id]

    def contract_items_for_contract(self, contract_id: str) -> list[ContractItem]:
        return [ci for ci in self.contract_items if ci.contract_id == contract_id]

    def source_lists_for_material_plant(self, material_id: str, plant_id: str) -> list[SourceList]:
        return [sl for sl in self.source_lists
                if sl.material_id == material_id and sl.plant_id == plant_id]

    def plant_extensions_for_material(self, material_id: str) -> list[MaterialPlantExtension]:
        return [mpe for mpe in self.material_plant_extensions
                if mpe.material_id == material_id]

    def category_top_level(self, category_id: str) -> str | None:
        """Walk up the hierarchy to find the top-level category."""
        cat = self.category_by_id(category_id)
        while cat and cat.parent_category_id:
            cat = self.category_by_id(cat.parent_category_id)
        return cat.category_id if cat else None

    def purch_group_for_category(self, category_id: str) -> str | None:
        """Find the purchasing group responsible for a category (walks up hierarchy)."""
        cat = self.category_by_id(category_id)
        while cat:
            if cat.owner_purch_group_id:
                return cat.owner_purch_group_id
            if cat.parent_category_id:
                cat = self.category_by_id(cat.parent_category_id)
            else:
                break
        return None

    def get_all_tables(self) -> dict[str, list]:
        """Return all entity lists as a dict keyed by table name."""
        return {
            "company_code": self.company_codes,
            "purchasing_org": self.purchasing_orgs,
            "purchasing_group": self.purchasing_groups,
            "purchasing_group_category": self.pg_category_mappings,
            "plant": self.plants,
            "storage_location": self.storage_locations,
            "cost_center": self.cost_centers,
            "category_hierarchy": self.categories,
            "material_master": self.materials,
            "material_plant_extension": self.material_plant_extensions,
            "legal_entity": self.legal_entities,
            "vendor_master": self.vendors,
            "vendor_category": self.vendor_categories,
            "vendor_address": self.vendor_addresses,
            "vendor_contact": self.vendor_contacts,
            "source_list": self.source_lists,
            "contract_header": self.contract_headers,
            "contract_item": self.contract_items,
            "uom_conversion": self.uom_conversions,
            "pr_header": self.pr_headers,
            "pr_line_item": self.pr_line_items,
            "po_header": self.po_headers,
            "po_line_item": self.po_line_items,
            "gr_header": self.gr_headers,
            "gr_line_item": self.gr_line_items,
            "invoice_header": self.invoice_headers,
            "invoice_line_item": self.invoice_line_items,
            "payment": self.payments,
            "payment_invoice_link": self.payment_invoice_links,
        }

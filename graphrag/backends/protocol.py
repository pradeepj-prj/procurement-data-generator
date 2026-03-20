"""GraphBackend protocol — shared interface for HANA Cloud and NetworkX backends."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class GraphBackend(Protocol):
    """Abstract interface that both HANA and NetworkX backends implement."""

    def get_entity_by_id(self, entity_id: str) -> dict:
        """Look up any entity by its ID. Returns entity attributes."""
        ...

    def get_vendor_profile(self, vendor_id: str) -> dict:
        """Complete vendor dossier — vendor + materials supplied + contracts."""
        ...

    def get_vendor_materials(self, vendor_id: str) -> list[dict]:
        """Materials a vendor supplies (via source_list)."""
        ...

    def get_material_vendors(self, material_id: str) -> list[dict]:
        """Vendors supplying a given material."""
        ...

    def get_po_details(self, po_id: str) -> dict:
        """PO header + vendor + line items with materials."""
        ...

    def get_p2p_chain(self, po_id: str) -> dict:
        """Full procure-to-pay chain: PO → Vendor → Materials → GRs → Invoices → Payments."""
        ...

    def get_contract_pos(self, contract_id: str) -> list[dict]:
        """POs linked to a contract."""
        ...

    def get_vendor_contracts(self, vendor_id: str) -> list[dict]:
        """Contracts for a vendor."""
        ...

    def get_invoices_with_issues(self) -> list[dict]:
        """Invoices with match_status != FULL_MATCH."""
        ...

    def get_invoice_context(self, invoice_id: str) -> dict:
        """Three-way match context: invoice + PO + GR details."""
        ...

    def get_plant_materials(self, plant_id: str) -> list[dict]:
        """Materials sourced at a plant (via source_list)."""
        ...

    def get_vendor_pos(self, vendor_id: str) -> list[dict]:
        """Purchase orders for a vendor."""
        ...

    def get_category_tree(self, category_id: str) -> dict:
        """Category hierarchy + materials in the category."""
        ...

    def get_vendor_plant_contracts(self, plant_id: str) -> list[dict]:
        """Multi-hop: plant → vendors (via source_list) → their contracts."""
        ...

    def search_entities(self, query: str, entity_type: str | None = None) -> list[dict]:
        """Search entities by name/description. Optional type filter."""
        ...

    def get_summary(self) -> dict:
        """Vertex/edge counts by type."""
        ...

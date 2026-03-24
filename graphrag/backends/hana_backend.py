"""HANA Cloud graph backend — queries vertex/edge views via hdbcli."""

from __future__ import annotations

from typing import Any

from graphrag.config import GraphRAGConfig


class HanaConnection:
    """Thin wrapper around hdbcli connection."""

    def __init__(self, config: GraphRAGConfig) -> None:
        from hdbcli import dbapi

        self._conn = dbapi.connect(
            address=config.hana_host,
            port=config.hana_port,
            user=config.hana_user,
            password=config.hana_password,
            encrypt=True,
            sslValidateCertificate=False,
        )
        self._schema = config.hana_schema

    def execute(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute SQL and return rows as list of dicts."""
        cursor = self._conn.cursor()
        try:
            cursor.execute(sql, params)
            if cursor.description is None:
                return []
            columns = [desc[0].lower() for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            cursor.close()

    @property
    def schema(self) -> str:
        return self._schema

    def close(self) -> None:
        self._conn.close()


class HanaGraphBackend:
    """HANA Cloud backend — SQL queries on graph vertex/edge views."""

    def __init__(self, config: GraphRAGConfig) -> None:
        self._conn = HanaConnection(config)
        self._s = self._conn.schema  # schema shorthand

    def _q(self, sql: str, params: tuple = ()) -> list[dict]:
        return self._conn.execute(sql, params)

    def _one(self, sql: str, params: tuple = ()) -> dict:
        rows = self._q(sql, params)
        return rows[0] if rows else {}

    # ── Protocol implementation ──────────────────────────────────────────────

    def get_entity_by_id(self, entity_id: str) -> dict:
        # Try each typed view in order
        for view, id_col in _TYPED_VIEWS:
            row = self._one(
                f'SELECT * FROM "{self._s}"."{view}" WHERE "{id_col}" = ?',
                (entity_id,),
            )
            if row:
                row["id"] = entity_id
                return row
        return {}

    def get_vendor_profile(self, vendor_id: str) -> dict:
        vendor = self._one(
            f'SELECT * FROM "{self._s}"."V_VENDOR" WHERE vertex_id = ?',
            (vendor_id,),
        )
        if not vendor:
            return {}
        vendor["id"] = vendor_id
        vendor["materials"] = self.get_vendor_materials(vendor_id)
        vendor["contracts"] = self.get_vendor_contracts(vendor_id)
        vendor["po_count"] = len(self.get_vendor_pos(vendor_id))
        return vendor

    def get_vendor_materials(self, vendor_id: str) -> list[dict]:
        return self._q(
            f'''SELECT m.*, e.plant_id, e.preferred_rank, e.lead_time
                FROM "{self._s}"."E_SUPPLIES" e
                JOIN "{self._s}"."V_MATERIAL" m ON m.vertex_id = e.target_vertex
                WHERE e.source_vertex = ?''',
            (vendor_id,),
        )

    def get_material_vendors(self, material_id: str) -> list[dict]:
        return self._q(
            f'''SELECT v.*, e.plant_id, e.preferred_rank, e.lead_time
                FROM "{self._s}"."E_SUPPLIES" e
                JOIN "{self._s}"."V_VENDOR" v ON v.vertex_id = e.source_vertex
                WHERE e.target_vertex = ?''',
            (material_id,),
        )

    def get_po_details(self, po_id: str) -> dict:
        po = self._one(
            f'SELECT * FROM "{self._s}"."V_PURCHASE_ORDER" WHERE vertex_id = ?',
            (po_id,),
        )
        if not po:
            return {}
        po["id"] = po_id

        # Vendor
        vendor_row = self._one(
            f'''SELECT v.* FROM "{self._s}"."E_ORDERED_FROM" e
                JOIN "{self._s}"."V_VENDOR" v ON v.vertex_id = e.target_vertex
                WHERE e.source_vertex = ?''',
            (po_id,),
        )
        if vendor_row:
            po["vendor"] = vendor_row

        # Materials (line items)
        po["materials"] = self._q(
            f'''SELECT m.*, e.quantity, e.unit_price, e.net_value
                FROM "{self._s}"."E_CONTAINS_MATERIAL" e
                JOIN "{self._s}"."V_MATERIAL" m ON m.vertex_id = e.target_vertex
                WHERE e.source_vertex = ?''',
            (po_id,),
        )

        # Contract
        contract_row = self._one(
            f'''SELECT c.* FROM "{self._s}"."E_UNDER_CONTRACT" e
                JOIN "{self._s}"."V_CONTRACT" c ON c.vertex_id = e.target_vertex
                WHERE e.source_vertex = ?''',
            (po_id,),
        )
        if contract_row:
            po["contract"] = contract_row

        return po

    def get_p2p_chain(self, po_id: str) -> dict:
        po = self.get_po_details(po_id)
        if not po:
            return {}

        # Goods receipts
        po["goods_receipts"] = self._q(
            f'''SELECT g.* FROM "{self._s}"."E_RECEIVED_FOR" e
                JOIN "{self._s}"."V_GOODS_RECEIPT" g ON g.vertex_id = e.source_vertex
                WHERE e.target_vertex = ?''',
            (po_id,),
        )

        # Invoices + payments
        invoices = self._q(
            f'''SELECT i.*, e.match_status AS edge_match_status
                FROM "{self._s}"."E_INVOICED_FOR" e
                JOIN "{self._s}"."V_INVOICE" i ON i.vertex_id = e.source_vertex
                WHERE e.target_vertex = ?''',
            (po_id,),
        )
        for inv in invoices:
            inv_id = inv.get("vertex_id", "")
            inv["payments"] = self._q(
                f'''SELECT p.*, e.amount_applied
                    FROM "{self._s}"."E_PAYS" e
                    JOIN "{self._s}"."V_PAYMENT" p ON p.vertex_id = e.source_vertex
                    WHERE e.target_vertex = ?''',
                (inv_id,),
            )
        po["invoices"] = invoices

        return po

    def get_contract_pos(self, contract_id: str) -> list[dict]:
        return self._q(
            f'''SELECT DISTINCT p.* FROM "{self._s}"."E_UNDER_CONTRACT" e
                JOIN "{self._s}"."V_PURCHASE_ORDER" p ON p.vertex_id = e.source_vertex
                WHERE e.target_vertex = ?''',
            (contract_id,),
        )

    def get_vendor_contracts(self, vendor_id: str) -> list[dict]:
        return self._q(
            f'''SELECT c.*, e.valid_from AS e_valid_from, e.valid_to AS e_valid_to
                FROM "{self._s}"."E_HAS_CONTRACT" e
                JOIN "{self._s}"."V_CONTRACT" c ON c.vertex_id = e.target_vertex
                WHERE e.source_vertex = ?''',
            (vendor_id,),
        )

    def get_invoices_with_issues(self) -> list[dict]:
        return self._q(
            f'''SELECT * FROM "{self._s}"."V_INVOICE"
                WHERE match_status IS NOT NULL AND match_status != 'FULL_MATCH'
                ORDER BY invoice_date DESC''',
        )

    def get_invoice_context(self, invoice_id: str) -> dict:
        inv = self._one(
            f'SELECT * FROM "{self._s}"."V_INVOICE" WHERE vertex_id = ?',
            (invoice_id,),
        )
        if not inv:
            return {}
        inv["id"] = invoice_id

        # PO
        po_row = self._one(
            f'''SELECT p.* FROM "{self._s}"."E_INVOICED_FOR" e
                JOIN "{self._s}"."V_PURCHASE_ORDER" p ON p.vertex_id = e.target_vertex
                WHERE e.source_vertex = ?''',
            (invoice_id,),
        )
        if po_row:
            inv["po"] = self.get_po_details(po_row.get("vertex_id", ""))
            # GRs for the PO
            inv["goods_receipts"] = self._q(
                f'''SELECT g.* FROM "{self._s}"."E_RECEIVED_FOR" e
                    JOIN "{self._s}"."V_GOODS_RECEIPT" g ON g.vertex_id = e.source_vertex
                    WHERE e.target_vertex = ?''',
                (po_row.get("vertex_id", ""),),
            )

        # Vendor
        vendor_row = self._one(
            f'''SELECT v.* FROM "{self._s}"."E_INVOICED_BY_VENDOR" e
                JOIN "{self._s}"."V_VENDOR" v ON v.vertex_id = e.target_vertex
                WHERE e.source_vertex = ?''',
            (invoice_id,),
        )
        if vendor_row:
            inv["vendor"] = vendor_row

        # Payments
        inv["payments"] = self._q(
            f'''SELECT p.*, e.amount_applied
                FROM "{self._s}"."E_PAYS" e
                JOIN "{self._s}"."V_PAYMENT" p ON p.vertex_id = e.source_vertex
                WHERE e.target_vertex = ?''',
            (invoice_id,),
        )

        return inv

    def get_plant_materials(self, plant_id: str) -> list[dict]:
        return self._q(
            f'''SELECT DISTINCT m.*, e.source_vertex AS vendor_id
                FROM "{self._s}"."E_SUPPLIES" e
                JOIN "{self._s}"."V_MATERIAL" m ON m.vertex_id = e.target_vertex
                WHERE e.plant_id = ?''',
            (plant_id,),
        )

    def get_vendor_pos(self, vendor_id: str) -> list[dict]:
        return self._q(
            f'''SELECT p.* FROM "{self._s}"."E_ORDERED_FROM" e
                JOIN "{self._s}"."V_PURCHASE_ORDER" p ON p.vertex_id = e.source_vertex
                WHERE e.target_vertex = ?''',
            (vendor_id,),
        )

    def get_category_tree(self, category_id: str) -> dict:
        cat = self._one(
            f'SELECT * FROM "{self._s}"."V_CATEGORY" WHERE vertex_id = ?',
            (category_id,),
        )
        if not cat:
            return {}
        cat["id"] = category_id

        # Children
        cat["children"] = self._q(
            f'''SELECT c.* FROM "{self._s}"."E_CATEGORY_PARENT" e
                JOIN "{self._s}"."V_CATEGORY" c ON c.vertex_id = e.source_vertex
                WHERE e.target_vertex = ?''',
            (category_id,),
        )

        # Materials in this category and children
        child_ids = [c.get("vertex_id", "") for c in cat["children"]]
        all_cat_ids = [category_id] + child_ids
        placeholders = ",".join("?" for _ in all_cat_ids)
        cat["materials"] = self._q(
            f'''SELECT m.* FROM "{self._s}"."E_BELONGS_TO_CATEGORY" e
                JOIN "{self._s}"."V_MATERIAL" m ON m.vertex_id = e.source_vertex
                WHERE e.target_vertex IN ({placeholders})''',
            tuple(all_cat_ids),
        )

        return cat

    def get_vendor_plant_contracts(self, plant_id: str) -> list[dict]:
        rows = self._q(
            f'''SELECT DISTINCT v.*, c.vertex_id AS contract_vertex_id,
                       c.contract_type, c.valid_from, c.valid_to, c.status AS contract_status
                FROM "{self._s}"."E_SUPPLIES" e
                JOIN "{self._s}"."V_VENDOR" v ON v.vertex_id = e.source_vertex
                JOIN "{self._s}"."E_HAS_CONTRACT" hc ON hc.source_vertex = v.vertex_id
                JOIN "{self._s}"."V_CONTRACT" c ON c.vertex_id = hc.target_vertex
                WHERE e.plant_id = ?''',
            (plant_id,),
        )
        # Group by vendor
        vendors: dict[str, dict] = {}
        for row in rows:
            vid = row.get("vertex_id", "")
            if vid not in vendors:
                vendors[vid] = {
                    "vendor": {k: v for k, v in row.items()
                               if k not in ("contract_vertex_id", "contract_type",
                                            "valid_from", "valid_to", "contract_status")},
                    "contracts": [],
                }
            vendors[vid]["contracts"].append({
                "contract_id": row.get("contract_vertex_id"),
                "contract_type": row.get("contract_type"),
                "valid_from": row.get("valid_from"),
                "valid_to": row.get("valid_to"),
                "status": row.get("contract_status"),
            })
        return list(vendors.values())

    def search_entities(self, query: str, entity_type: str | None = None) -> list[dict]:
        like_pattern = f"%{query}%"
        if entity_type:
            return self._q(
                f'''SELECT vertex_id AS id, vertex_type, label
                    FROM "{self._s}"."V_ALL_VERTICES"
                    WHERE vertex_type = ? AND (LOWER(label) LIKE LOWER(?) OR LOWER(vertex_id) LIKE LOWER(?))
                    ORDER BY vertex_id LIMIT 20''',
                (entity_type.upper(), like_pattern, like_pattern),
            )
        return self._q(
            f'''SELECT vertex_id AS id, vertex_type, label
                FROM "{self._s}"."V_ALL_VERTICES"
                WHERE LOWER(label) LIKE LOWER(?) OR LOWER(vertex_id) LIKE LOWER(?)
                ORDER BY vertex_id LIMIT 20''',
            (like_pattern, like_pattern),
        )

    def get_summary(self) -> dict:
        vertex_counts_rows = self._q(
            f'''SELECT vertex_type, COUNT(*) AS cnt
                FROM "{self._s}"."V_ALL_VERTICES"
                GROUP BY vertex_type ORDER BY vertex_type''',
        )
        edge_counts_rows = self._q(
            f'''SELECT edge_type, COUNT(*) AS cnt
                FROM "{self._s}"."E_ALL_EDGES"
                GROUP BY edge_type ORDER BY edge_type''',
        )
        vertex_counts = {r["vertex_type"]: r["cnt"] for r in vertex_counts_rows}
        edge_counts = {r["edge_type"]: r["cnt"] for r in edge_counts_rows}
        return {
            "total_vertices": sum(vertex_counts.values()),
            "total_edges": sum(edge_counts.values()),
            "vertex_counts": vertex_counts,
            "edge_counts": edge_counts,
        }


# View name → primary key column for entity lookup
_TYPED_VIEWS: list[tuple[str, str]] = [
    ("V_VENDOR", "vertex_id"),
    ("V_MATERIAL", "vertex_id"),
    ("V_PLANT", "vertex_id"),
    ("V_CATEGORY", "vertex_id"),
    ("V_PURCHASE_ORDER", "vertex_id"),
    ("V_CONTRACT", "vertex_id"),
    ("V_INVOICE", "vertex_id"),
    ("V_GOODS_RECEIPT", "vertex_id"),
    ("V_PAYMENT", "vertex_id"),
    ("V_PURCHASE_REQ", "vertex_id"),
]

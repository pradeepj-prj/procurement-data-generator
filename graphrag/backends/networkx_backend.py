"""NetworkX graph backend — builds an in-memory DiGraph from CSV files."""

from __future__ import annotations

import pickle
from datetime import date
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd

from graphrag.config import GraphRAGConfig

# Tables needed for relational queries (loaded with default dtype inference)
_RELATIONAL_TABLES = [
    "vendor_master", "po_header", "po_line_item", "invoice_header",
    "payment", "payment_invoice_link", "material_master", "category_hierarchy",
]

# ── CSV → Node mappings ─────────────────────────────────────────────────────
# Each entry: (csv_file, id_column, vertex_type, label_column, extra_columns)
_NODE_SOURCES: list[tuple[str, str, str, str, list[str]]] = [
    ("vendor_master", "vendor_id", "VENDOR", "vendor_name",
     ["vendor_type", "country", "status", "quality_score", "risk_score",
      "on_time_delivery_rate", "esg_score", "preferred_flag", "payment_terms",
      "currency", "lead_time_days_typical"]),
    ("material_master", "material_id", "MATERIAL", "description",
     ["material_type", "category_id", "criticality", "standard_cost",
      "base_uom", "hazmat_flag", "default_lead_time_days"]),
    ("plant", "plant_id", "PLANT", "plant_name",
     ["country", "city", "function"]),
    ("category_hierarchy", "category_id", "CATEGORY", "category_name",
     ["level", "parent_category_id"]),
    ("po_header", "po_id", "PURCHASE_ORDER", "po_id",
     ["po_date", "vendor_id", "status", "total_net_value", "maverick_flag",
      "po_type", "plant_id", "currency", "payment_terms"]),
    ("contract_header", "contract_id", "CONTRACT", "contract_id",
     ["vendor_id", "valid_from", "valid_to", "status", "contract_type",
      "currency"]),
    ("invoice_header", "invoice_id", "INVOICE", "invoice_id",
     ["invoice_date", "vendor_id", "po_id", "total_net_amount",
      "match_status", "status", "payment_due_date", "payment_block",
      "block_reason", "total_gross_amount", "tax_amount"]),
    ("gr_header", "gr_id", "GOODS_RECEIPT", "gr_id",
     ["gr_date", "po_id", "status", "plant_id"]),
    ("payment", "payment_id", "PAYMENT", "payment_id",
     ["payment_date", "vendor_id", "total_amount", "payment_method",
      "status", "currency"]),
    ("pr_header", "pr_id", "PURCHASE_REQ", "pr_id",
     ["pr_date", "status", "priority", "pr_type", "plant_id",
      "requester_name", "requester_department"]),
]

# ── CSV → Edge mappings ──────────────────────────────────────────────────────
# Each entry: (csv_file, source_col, target_col, edge_type, extra_cols, filter_fn)
_EDGE_SOURCES: list[tuple[str, str, str, str, list[str], Any]] = [
    # E_SUPPLIES: Vendor → Material (via source_list)
    ("source_list", "vendor_id", "material_id", "SUPPLIES",
     ["plant_id", "preferred_rank", "approval_status", "lane_lead_time_days"], None),
    # E_ORDERED_FROM: PO → Vendor
    ("po_header", "po_id", "vendor_id", "ORDERED_FROM",
     ["po_date", "total_net_value", "maverick_flag"], None),
    # E_CONTAINS_MATERIAL: PO → Material (via po_line_item)
    ("po_line_item", "po_id", "material_id", "CONTAINS_MATERIAL",
     ["quantity", "unit_price", "net_value", "po_line_number"], None),
    # E_UNDER_CONTRACT: PO → Contract (via po_line_item, where contract_id is set)
    ("po_line_item", "po_id", "contract_id", "UNDER_CONTRACT",
     ["unit_price"], lambda df: df[df["contract_id"].notna() & (df["contract_id"] != "")]),
    # E_INVOICED_FOR: Invoice → PO
    ("invoice_header", "invoice_id", "po_id", "INVOICED_FOR",
     ["total_net_amount", "match_status"], None),
    # E_RECEIVED_FOR: GR → PO
    ("gr_header", "gr_id", "po_id", "RECEIVED_FOR",
     ["gr_date", "status"], None),
    # E_PAYS: Payment → Invoice (via payment_invoice_link)
    ("payment_invoice_link", "payment_id", "invoice_id", "PAYS",
     ["amount_applied"], None),
    # E_BELONGS_TO_CATEGORY: Material → Category
    ("material_master", "material_id", "category_id", "BELONGS_TO_CATEGORY",
     [], None),
    # E_CATEGORY_PARENT: Category → Parent Category
    ("category_hierarchy", "category_id", "parent_category_id", "CATEGORY_PARENT",
     [], lambda df: df[df["parent_category_id"].notna() & (df["parent_category_id"] != "")]),
    # E_LOCATED_AT: PO → Plant
    ("po_header", "po_id", "plant_id", "LOCATED_AT",
     [], None),
    # E_HAS_CONTRACT: Vendor → Contract
    ("contract_header", "vendor_id", "contract_id", "HAS_CONTRACT",
     ["valid_from", "valid_to", "status"], None),
    # E_REQUESTED_MATERIAL: PR → Material (via pr_line_item)
    ("pr_line_item", "pr_id", "material_id", "REQUESTED_MATERIAL",
     ["quantity", "requested_delivery_date"], None),
    # E_INVOICED_BY_VENDOR: Invoice → Vendor
    ("invoice_header", "invoice_id", "vendor_id", "INVOICED_BY_VENDOR",
     ["total_net_amount"], None),
    # E_PAID_TO_VENDOR: Payment → Vendor
    ("payment", "payment_id", "vendor_id", "PAID_TO_VENDOR",
     ["total_amount", "payment_date"], None),
]


class NetworkXGraphBackend:
    """In-memory graph backend using NetworkX MultiDiGraph, built from CSV files."""

    def __init__(self, config: GraphRAGConfig) -> None:
        self._config = config
        self._csv_dir = Path(config.csv_dir)
        self._pickle_path = Path(config.graph_pickle)
        self._graph: nx.MultiDiGraph = self._load_or_build()
        self._tables: dict[str, pd.DataFrame] = self._load_tables()

    # ── Graph construction ───────────────────────────────────────────────────

    def _load_or_build(self) -> nx.MultiDiGraph:
        """Load from pickle if available and newer than CSVs, else build from CSV."""
        if self._pickle_path and str(self._pickle_path) and self._pickle_path.is_file():
            csv_mtime = max(
                f.stat().st_mtime
                for f in self._csv_dir.glob("*.csv")
            ) if self._csv_dir.exists() else 0
            if self._pickle_path.stat().st_mtime > csv_mtime:
                return self.load(self._pickle_path)
        return self._build_from_csv()

    def _build_from_csv(self) -> nx.MultiDiGraph:
        """Build MultiDiGraph from CSV files."""
        G = nx.MultiDiGraph()

        # Load nodes
        for csv_name, id_col, vtype, label_col, extra_cols in _NODE_SOURCES:
            csv_path = self._csv_dir / f"{csv_name}.csv"
            if not csv_path.exists():
                continue
            df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
            for _, row in df.iterrows():
                node_id = row[id_col]
                attrs = {
                    "vertex_type": vtype,
                    "label": row.get(label_col, node_id),
                }
                for col in extra_cols:
                    if col in row.index:
                        val = row[col]
                        attrs[col] = _coerce_value(val)
                G.add_node(node_id, **attrs)

        # Load edges
        for csv_name, src_col, tgt_col, etype, extra_cols, filter_fn in _EDGE_SOURCES:
            csv_path = self._csv_dir / f"{csv_name}.csv"
            if not csv_path.exists():
                continue
            df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
            if filter_fn is not None:
                df = filter_fn(df)
            for _, row in df.iterrows():
                src = row[src_col]
                tgt = row[tgt_col]
                if not src or not tgt:
                    continue
                attrs: dict[str, Any] = {}
                for col in extra_cols:
                    if col in row.index:
                        attrs[col] = _coerce_value(row[col])
                G.add_edge(src, tgt, key=etype, edge_type=etype, **attrs)

        return G

    def save(self, path: Path | str | None = None) -> None:
        """Pickle the graph for fast reload."""
        path = Path(path) if path else self._pickle_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self._graph, f, protocol=pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def load(path: Path | str) -> nx.MultiDiGraph:
        """Load a pickled graph."""
        with open(path, "rb") as f:
            return pickle.load(f)  # noqa: S301

    def _load_tables(self) -> dict[str, pd.DataFrame]:
        """Load CSV tables with default dtype inference for relational queries."""
        tables: dict[str, pd.DataFrame] = {}
        for name in _RELATIONAL_TABLES:
            csv_path = self._csv_dir / f"{name}.csv"
            if csv_path.exists():
                tables[name] = pd.read_csv(csv_path)
        return tables

    def _get_table(self, name: str) -> pd.DataFrame:
        """Get a loaded table, returning empty DataFrame if not found."""
        return self._tables.get(name, pd.DataFrame())

    # ── Protocol implementation ──────────────────────────────────────────────

    def get_entity_by_id(self, entity_id: str) -> dict:
        if entity_id not in self._graph:
            return {}
        return {"id": entity_id, **self._graph.nodes[entity_id]}

    def get_vendor_profile(self, vendor_id: str) -> dict:
        if vendor_id not in self._graph:
            return {}
        vendor = {"id": vendor_id, **self._graph.nodes[vendor_id]}
        vendor["materials"] = self.get_vendor_materials(vendor_id)
        vendor["contracts"] = self.get_vendor_contracts(vendor_id)
        vendor["po_count"] = len(self.get_vendor_pos(vendor_id))
        return vendor

    def get_vendor_materials(self, vendor_id: str) -> list[dict]:
        results = []
        for _, tgt, data in self._graph.out_edges(vendor_id, data=True):
            if data.get("edge_type") == "SUPPLIES":
                mat = self.get_entity_by_id(tgt)
                if mat:
                    mat["plant_id"] = data.get("plant_id")
                    mat["preferred_rank"] = data.get("preferred_rank")
                    mat["lead_time"] = data.get("lane_lead_time_days")
                    results.append(mat)
        return results

    def get_material_vendors(self, material_id: str) -> list[dict]:
        results = []
        for src, _, data in self._graph.in_edges(material_id, data=True):
            if data.get("edge_type") == "SUPPLIES":
                vendor = self.get_entity_by_id(src)
                if vendor:
                    vendor["plant_id"] = data.get("plant_id")
                    vendor["preferred_rank"] = data.get("preferred_rank")
                    vendor["lead_time"] = data.get("lane_lead_time_days")
                    results.append(vendor)
        return results

    def get_po_details(self, po_id: str) -> dict:
        if po_id not in self._graph:
            return {}
        po = {"id": po_id, **self._graph.nodes[po_id]}

        # Vendor
        for _, tgt, data in self._graph.out_edges(po_id, data=True):
            if data.get("edge_type") == "ORDERED_FROM":
                po["vendor"] = self.get_entity_by_id(tgt)
                break

        # Line items (materials)
        materials = []
        for _, tgt, data in self._graph.out_edges(po_id, data=True):
            if data.get("edge_type") == "CONTAINS_MATERIAL":
                mat = self.get_entity_by_id(tgt)
                if mat:
                    mat["quantity"] = data.get("quantity")
                    mat["unit_price"] = data.get("unit_price")
                    mat["net_value"] = data.get("net_value")
                    materials.append(mat)
        po["materials"] = materials

        # Contract
        for _, tgt, data in self._graph.out_edges(po_id, data=True):
            if data.get("edge_type") == "UNDER_CONTRACT":
                po["contract"] = self.get_entity_by_id(tgt)
                break

        return po

    def get_p2p_chain(self, po_id: str) -> dict:
        po = self.get_po_details(po_id)
        if not po:
            return {}

        # GRs for this PO
        grs = []
        for src, _, data in self._graph.in_edges(po_id, data=True):
            if data.get("edge_type") == "RECEIVED_FOR":
                grs.append(self.get_entity_by_id(src))
        po["goods_receipts"] = grs

        # Invoices for this PO
        invoices = []
        for src, _, data in self._graph.in_edges(po_id, data=True):
            if data.get("edge_type") == "INVOICED_FOR":
                inv = self.get_entity_by_id(src)
                if inv:
                    inv["match_status"] = data.get("match_status")
                    # Payments for this invoice
                    payments = []
                    for pay_src, _, pay_data in self._graph.in_edges(src, data=True):
                        if pay_data.get("edge_type") == "PAYS":
                            pay = self.get_entity_by_id(pay_src)
                            if pay:
                                pay["amount_applied"] = pay_data.get("amount_applied")
                                payments.append(pay)
                    inv["payments"] = payments
                    invoices.append(inv)
        po["invoices"] = invoices

        return po

    def get_contract_pos(self, contract_id: str) -> list[dict]:
        results = []
        for src, _, data in self._graph.in_edges(contract_id, data=True):
            if data.get("edge_type") == "UNDER_CONTRACT":
                po = self.get_entity_by_id(src)
                if po:
                    results.append(po)
        return results

    def get_vendor_contracts(self, vendor_id: str) -> list[dict]:
        results = []
        for _, tgt, data in self._graph.out_edges(vendor_id, data=True):
            if data.get("edge_type") == "HAS_CONTRACT":
                contract = self.get_entity_by_id(tgt)
                if contract:
                    contract["valid_from"] = data.get("valid_from")
                    contract["valid_to"] = data.get("valid_to")
                    results.append(contract)
        return results

    def get_invoices_with_issues(self) -> list[dict]:
        results = []
        for node_id, attrs in self._graph.nodes(data=True):
            if (
                attrs.get("vertex_type") == "INVOICE"
                and attrs.get("match_status")
                and attrs.get("match_status") != "FULL_MATCH"
            ):
                results.append({"id": node_id, **attrs})
        return results

    def get_invoice_context(self, invoice_id: str) -> dict:
        if invoice_id not in self._graph:
            return {}
        inv = {"id": invoice_id, **self._graph.nodes[invoice_id]}

        # PO linked to this invoice
        for _, tgt, data in self._graph.out_edges(invoice_id, data=True):
            if data.get("edge_type") == "INVOICED_FOR":
                inv["po"] = self.get_po_details(tgt)
                # GRs for the PO
                grs = []
                for src, _, gr_data in self._graph.in_edges(tgt, data=True):
                    if gr_data.get("edge_type") == "RECEIVED_FOR":
                        grs.append(self.get_entity_by_id(src))
                inv["goods_receipts"] = grs
                break

        # Vendor
        for _, tgt, data in self._graph.out_edges(invoice_id, data=True):
            if data.get("edge_type") == "INVOICED_BY_VENDOR":
                inv["vendor"] = self.get_entity_by_id(tgt)
                break

        # Payments
        payments = []
        for src, _, data in self._graph.in_edges(invoice_id, data=True):
            if data.get("edge_type") == "PAYS":
                pay = self.get_entity_by_id(src)
                if pay:
                    pay["amount_applied"] = data.get("amount_applied")
                    payments.append(pay)
        inv["payments"] = payments

        return inv

    def get_plant_materials(self, plant_id: str) -> list[dict]:
        results = []
        seen = set()
        for src, tgt, data in self._graph.edges(data=True):
            if data.get("edge_type") == "SUPPLIES" and data.get("plant_id") == plant_id:
                if tgt not in seen:
                    mat = self.get_entity_by_id(tgt)
                    if mat:
                        mat["vendor_id"] = src
                        results.append(mat)
                        seen.add(tgt)
        return results

    def get_vendor_pos(self, vendor_id: str) -> list[dict]:
        results = []
        for src, _, data in self._graph.in_edges(vendor_id, data=True):
            if data.get("edge_type") == "ORDERED_FROM":
                po = self.get_entity_by_id(src)
                if po:
                    results.append(po)
        return results

    def get_category_tree(self, category_id: str) -> dict:
        if category_id not in self._graph:
            return {}
        cat = {"id": category_id, **self._graph.nodes[category_id]}

        # Child categories
        children = []
        for src, _, data in self._graph.in_edges(category_id, data=True):
            if data.get("edge_type") == "CATEGORY_PARENT":
                child = self.get_entity_by_id(src)
                if child:
                    children.append(child)
        cat["children"] = children

        # Materials in this category (and children)
        cat_ids = {category_id} | {c["id"] for c in children}
        materials = []
        for src, tgt, data in self._graph.edges(data=True):
            if data.get("edge_type") == "BELONGS_TO_CATEGORY" and tgt in cat_ids:
                mat = self.get_entity_by_id(src)
                if mat:
                    materials.append(mat)
        cat["materials"] = materials

        return cat

    def get_vendor_plant_contracts(self, plant_id: str) -> list[dict]:
        """Multi-hop: plant → vendors (via SUPPLIES where plant matches) → contracts."""
        results = []
        vendor_ids = set()
        for src, tgt, data in self._graph.edges(data=True):
            if data.get("edge_type") == "SUPPLIES" and data.get("plant_id") == plant_id:
                vendor_ids.add(src)

        for vid in vendor_ids:
            vendor = self.get_entity_by_id(vid)
            if not vendor:
                continue
            contracts = self.get_vendor_contracts(vid)
            if contracts:
                results.append({
                    "vendor": vendor,
                    "contracts": contracts,
                })
        return results

    def search_entities(self, query: str, entity_type: str | None = None) -> list[dict]:
        query_lower = query.lower()
        results = []
        for node_id, attrs in self._graph.nodes(data=True):
            if entity_type and attrs.get("vertex_type") != entity_type.upper():
                continue
            label = str(attrs.get("label", "")).lower()
            node_lower = node_id.lower()
            if query_lower in label or query_lower in node_lower:
                results.append({"id": node_id, **attrs})
                if len(results) >= 20:
                    break
        return results

    def get_summary(self) -> dict:
        vertex_counts: dict[str, int] = {}
        for _, attrs in self._graph.nodes(data=True):
            vtype = attrs.get("vertex_type", "UNKNOWN")
            vertex_counts[vtype] = vertex_counts.get(vtype, 0) + 1

        edge_counts: dict[str, int] = {}
        for _, _, attrs in self._graph.edges(data=True):
            etype = attrs.get("edge_type", "UNKNOWN")
            edge_counts[etype] = edge_counts.get(etype, 0) + 1

        return {
            "total_vertices": self._graph.number_of_nodes(),
            "total_edges": self._graph.number_of_edges(),
            "vertex_counts": vertex_counts,
            "edge_counts": edge_counts,
        }

    # ── Relational queries ────────────────────────────────────────────────

    def get_spend_by_vendor(self, top_n: int = 10) -> list[dict]:
        po = self._get_table("po_header")
        vm = self._get_table("vendor_master")
        if po.empty or vm.empty:
            return []
        merged = po.merge(vm[["vendor_id", "vendor_name"]], on="vendor_id", how="left")
        grouped = (
            merged.groupby(["vendor_id", "vendor_name"])
            .agg(total_spend=("total_net_value", "sum"), po_count=("po_id", "count"))
            .reset_index()
            .sort_values("total_spend", ascending=False)
            .head(top_n)
        )
        return grouped.to_dict("records")

    def get_spend_by_category(self, top_n: int = 10) -> list[dict]:
        pli = self._get_table("po_line_item")
        mm = self._get_table("material_master")
        ch = self._get_table("category_hierarchy")
        if pli.empty or mm.empty or ch.empty:
            return []
        merged = pli.merge(mm[["material_id", "category_id"]], on="material_id", how="left")
        merged = merged.merge(ch[["category_id", "category_name"]], on="category_id", how="left")
        grouped = (
            merged.groupby(["category_id", "category_name"])
            .agg(total_spend=("net_value", "sum"), item_count=("po_line_number", "count"))
            .reset_index()
            .sort_values("total_spend", ascending=False)
            .head(top_n)
        )
        return grouped.to_dict("records")

    def get_pos_by_filter(
        self,
        status: str | None = None,
        maverick: bool | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
        limit: int = 20,
    ) -> list[dict]:
        po = self._get_table("po_header")
        vm = self._get_table("vendor_master")
        if po.empty:
            return []
        df = po.copy()
        if status:
            df = df[df["status"].str.upper() == status.upper()]
        if maverick is not None:
            df = df[df["maverick_flag"] == maverick]
        if min_value is not None:
            df = df[df["total_net_value"] >= min_value]
        if max_value is not None:
            df = df[df["total_net_value"] <= max_value]
        df = df.sort_values("total_net_value", ascending=False).head(limit)
        if not vm.empty:
            df = df.merge(vm[["vendor_id", "vendor_name"]], on="vendor_id", how="left")
        return df.to_dict("records")

    def get_invoice_aging(self) -> list[dict]:
        inv = self._get_table("invoice_header")
        if inv.empty:
            return []
        grouped = (
            inv.groupby("match_status")
            .agg(count=("invoice_id", "count"), total_amount=("total_net_amount", "sum"))
            .reset_index()
            .sort_values("count", ascending=False)
        )
        return grouped.to_dict("records")

    def get_overdue_invoices(self, limit: int = 20) -> list[dict]:
        inv = self._get_table("invoice_header")
        vm = self._get_table("vendor_master")
        if inv.empty:
            return []
        df = inv.copy()
        df["payment_due_date"] = pd.to_datetime(df["payment_due_date"], errors="coerce")
        today = pd.Timestamp(date.today())
        df = df[
            (df["payment_due_date"] < today)
            & (df["status"].str.upper() != "PAID")
        ]
        df = df.sort_values("payment_due_date").head(limit)
        if not vm.empty:
            df = df.merge(vm[["vendor_id", "vendor_name"]], on="vendor_id", how="left")
        return df.to_dict("records")

    def get_vendor_risk_summary(self, threshold: float = 3.0) -> list[dict]:
        vm = self._get_table("vendor_master")
        if vm.empty:
            return []
        df = vm[vm["risk_score"] > threshold].copy()
        df = df.sort_values("risk_score", ascending=False)
        cols = [
            c for c in [
                "vendor_id", "vendor_name", "risk_score", "quality_score",
                "on_time_delivery_rate", "esg_score", "status", "country",
            ] if c in df.columns
        ]
        return df[cols].to_dict("records")


def _coerce_value(val: str) -> str | int | float | bool | None:
    """Best-effort coercion of CSV string values."""
    if val == "":
        return None
    if val == "TRUE":
        return True
    if val == "FALSE":
        return False
    try:
        if "." in val:
            return float(val)
        return int(val)
    except (ValueError, TypeError):
        return val

"""MCP server — 16 tools exposing the procurement knowledge graph."""

from __future__ import annotations

import argparse
import sys

from mcp.server.fastmcp import FastMCP

from graphrag.config import GraphRAGConfig, get_backend
from graphrag.retrieval import context_formatter as fmt

mcp = FastMCP(
    "Procurement Knowledge Graph",
    description="Query procurement knowledge graph — vendors, materials, POs, contracts, invoices, and more.",
)

# Lazy-initialized backend (set in main or on first tool call)
_backend = None


def _get_backend():
    global _backend
    if _backend is None:
        config = GraphRAGConfig.from_env()
        _backend = get_backend(config)
    return _backend


# ── MCP Tools ────────────────────────────────────────────────────────────────


@mcp.tool()
def get_entity(entity_id: str) -> str:
    """Look up any entity by ID (vendor, material, PO, contract, invoice, GR, payment, PR, plant, category)."""
    data = _get_backend().get_entity_by_id(entity_id)
    return fmt.format_entity(data)


@mcp.tool()
def get_vendor_profile(vendor_id: str) -> str:
    """Get a complete vendor dossier — performance scores, materials supplied, contracts, and PO count."""
    data = _get_backend().get_vendor_profile(vendor_id)
    return fmt.format_vendor_profile(data)


@mcp.tool()
def get_procure_to_pay_chain(po_id: str) -> str:
    """Get the full procure-to-pay chain for a PO: vendor, materials, goods receipts, invoices, and payments."""
    data = _get_backend().get_p2p_chain(po_id)
    return fmt.format_p2p_chain(data)


@mcp.tool()
def get_invoice_context(invoice_id: str) -> str:
    """Get three-way match context for an invoice — linked PO, goods receipts, vendor, and payments."""
    data = _get_backend().get_invoice_context(invoice_id)
    return fmt.format_invoice_context(data)


@mcp.tool()
def find_invoice_issues() -> str:
    """Find all invoices with match problems (match_status != FULL_MATCH)."""
    items = _get_backend().get_invoices_with_issues()
    return fmt.format_list(items, "Invoices with Issues")


@mcp.tool()
def search_entities(query: str, entity_type: str | None = None) -> str:
    """Search for entities by name or description. Optional entity_type filter (VENDOR, MATERIAL, PURCHASE_ORDER, etc.)."""
    items = _get_backend().search_entities(query, entity_type)
    return fmt.format_search_results(items)


@mcp.tool()
def get_materials_for_vendor(vendor_id: str) -> str:
    """Get all materials a vendor supplies, with plant and ranking info."""
    items = _get_backend().get_vendor_materials(vendor_id)
    return fmt.format_list(items, "Vendor Materials")


@mcp.tool()
def get_vendors_for_material(material_id: str) -> str:
    """Get all vendors supplying a specific material."""
    items = _get_backend().get_material_vendors(material_id)
    return fmt.format_list(items, "Material Vendors")


@mcp.tool()
def get_vendors_for_plant_with_contracts(plant_id: str) -> str:
    """Multi-hop query: find all vendors supplying materials at a plant, along with their contracts."""
    items = _get_backend().get_vendor_plant_contracts(plant_id)
    return fmt.format_vendor_plant_contracts(items)


@mcp.tool()
def get_graph_summary() -> str:
    """Get an overview of the knowledge graph — vertex and edge counts by type."""
    data = _get_backend().get_summary()
    lines = [
        "## Knowledge Graph Summary",
        f"  Total Vertices: {data.get('total_vertices', 0)}",
        f"  Total Edges: {data.get('total_edges', 0)}",
        "",
        "### Vertex Counts",
    ]
    for vtype, count in sorted(data.get("vertex_counts", {}).items()):
        lines.append(f"  {vtype}: {count}")
    lines.append("\n### Edge Counts")
    for etype, count in sorted(data.get("edge_counts", {}).items()):
        lines.append(f"  {etype}: {count}")
    return "\n".join(lines)


# ── Relational tools ─────────────────────────────────────────────────────────


@mcp.tool()
def get_top_vendors_by_spend(top_n: int = 10) -> str:
    """Get the top vendors ranked by total PO spend."""
    items = _get_backend().get_spend_by_vendor(top_n)
    return fmt.format_spend_table(items, "Top Vendors by Spend")


@mcp.tool()
def get_spend_by_category(top_n: int = 10) -> str:
    """Get spend breakdown aggregated by material category."""
    items = _get_backend().get_spend_by_category(top_n)
    return fmt.format_spend_table(items, "Spend by Category")


@mcp.tool()
def filter_purchase_orders(
    status: str | None = None,
    maverick_only: bool = False,
    min_value: float | None = None,
    max_value: float | None = None,
) -> str:
    """Filter purchase orders by status, maverick flag, and/or value range."""
    items = _get_backend().get_pos_by_filter(
        status=status,
        maverick=True if maverick_only else None,
        min_value=min_value,
        max_value=max_value,
    )
    return fmt.format_po_list(items)


@mcp.tool()
def get_invoice_aging_summary() -> str:
    """Get invoice aging summary — counts and totals grouped by match status."""
    items = _get_backend().get_invoice_aging()
    return fmt.format_invoice_aging(items)


@mcp.tool()
def get_overdue_invoices() -> str:
    """Get invoices that are past their payment due date and not yet paid."""
    items = _get_backend().get_overdue_invoices()
    return fmt.format_po_list(items)


@mcp.tool()
def get_high_risk_vendors(risk_threshold: float = 3.0) -> str:
    """Get vendors with risk scores above a threshold, with quality and delivery metrics."""
    items = _get_backend().get_vendor_risk_summary(risk_threshold)
    return fmt.format_vendor_risk(items)


# ── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Procurement KG MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for HTTP transport (default: 8080)",
    )
    args = parser.parse_args()

    # Pre-initialize backend to fail fast
    global _backend
    config = GraphRAGConfig.from_env()
    _backend = get_backend(config)
    backend_name = config.graph_backend
    vertex_count = _backend.get_summary().get("total_vertices", 0)
    print(f"Backend: {backend_name} ({vertex_count} vertices)", file=sys.stderr)

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http", port=args.port)


if __name__ == "__main__":
    main()

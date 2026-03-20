"""Format graph query results as structured text for LLM consumption."""

from __future__ import annotations

from typing import Any


def format_vendor_profile(data: dict) -> str:
    """Format a vendor profile with materials and contracts."""
    if not data:
        return "No vendor found."

    lines = [
        f"## Vendor: {data.get('label', data.get('id', 'Unknown'))}",
        f"  ID: {data.get('id', 'N/A')}",
        f"  Type: {data.get('vendor_type', 'N/A')}",
        f"  Country: {data.get('country', 'N/A')}",
        f"  Status: {data.get('status', 'N/A')}",
        f"  Quality Score: {_fmt(data.get('quality_score'))}",
        f"  Risk Score: {_fmt(data.get('risk_score'))}",
        f"  On-Time Delivery: {_fmt(data.get('on_time_delivery_rate'))}%",
        f"  ESG Score: {_fmt(data.get('esg_score'))}",
        f"  PO Count: {data.get('po_count', 'N/A')}",
    ]

    materials = data.get("materials", [])
    if materials:
        lines.append(f"\n### Materials Supplied ({len(materials)})")
        for m in materials[:10]:
            lines.append(f"  - {m.get('label', m.get('id', '?'))} ({m.get('id', '?')})")
            lines.append(f"    Plant: {m.get('plant_id', '?')}, Rank: {m.get('preferred_rank', '?')}")
        if len(materials) > 10:
            lines.append(f"  ... and {len(materials) - 10} more")

    contracts = data.get("contracts", [])
    if contracts:
        lines.append(f"\n### Contracts ({len(contracts)})")
        for c in contracts:
            lines.append(f"  - {c.get('id', c.get('vertex_id', '?'))}")
            lines.append(f"    Type: {c.get('contract_type', '?')}, Status: {c.get('status', '?')}")
            lines.append(f"    Valid: {c.get('valid_from', '?')} → {c.get('valid_to', '?')}")

    return "\n".join(lines)


def format_p2p_chain(data: dict) -> str:
    """Format the full procure-to-pay chain for a PO."""
    if not data:
        return "No PO found."

    lines = [
        f"## Procure-to-Pay Chain: {data.get('id', 'Unknown')}",
        "",
        "### Purchase Order",
        f"  PO ID: {data.get('id', 'N/A')}",
        f"  Date: {_fmt(data.get('po_date'))}",
        f"  Status: {data.get('status', 'N/A')}",
        f"  Total Value: {_fmt(data.get('total_net_value'))} {data.get('currency', '')}",
        f"  Type: {data.get('po_type', 'N/A')}",
        f"  Maverick: {data.get('maverick_flag', 'N/A')}",
    ]

    vendor = data.get("vendor")
    if vendor:
        lines.extend([
            "",
            "### Vendor",
            f"  {vendor.get('label', vendor.get('id', '?'))} ({vendor.get('id', vendor.get('vertex_id', '?'))})",
            f"  Quality: {_fmt(vendor.get('quality_score'))}, Risk: {_fmt(vendor.get('risk_score'))}",
        ])

    materials = data.get("materials", [])
    if materials:
        lines.append(f"\n### Materials ({len(materials)})")
        for m in materials:
            lines.append(f"  - {m.get('label', m.get('id', '?'))}")
            lines.append(f"    Qty: {_fmt(m.get('quantity'))}, Price: {_fmt(m.get('unit_price'))}")

    contract = data.get("contract")
    if contract:
        lines.extend([
            "",
            "### Contract",
            f"  {contract.get('id', contract.get('vertex_id', '?'))} ({contract.get('contract_type', '?')})",
        ])

    grs = data.get("goods_receipts", [])
    if grs:
        lines.append(f"\n### Goods Receipts ({len(grs)})")
        for gr in grs:
            lines.append(f"  - {gr.get('id', gr.get('vertex_id', '?'))} — {_fmt(gr.get('gr_date'))} [{gr.get('status', '?')}]")

    invoices = data.get("invoices", [])
    if invoices:
        lines.append(f"\n### Invoices ({len(invoices)})")
        for inv in invoices:
            lines.append(f"  - {inv.get('id', inv.get('vertex_id', '?'))}")
            lines.append(f"    Match: {inv.get('match_status', '?')}, Amount: {_fmt(inv.get('total_net_amount'))}")
            payments = inv.get("payments", [])
            for pay in payments:
                lines.append(f"    → Payment: {pay.get('id', pay.get('vertex_id', '?'))} ({_fmt(pay.get('amount_applied'))})")

    return "\n".join(lines)


def format_invoice_context(data: dict) -> str:
    """Format three-way match context for an invoice."""
    if not data:
        return "No invoice found."

    lines = [
        f"## Invoice: {data.get('id', 'Unknown')}",
        f"  Date: {_fmt(data.get('invoice_date'))}",
        f"  Status: {data.get('status', 'N/A')}",
        f"  Match Status: {data.get('match_status', 'N/A')}",
        f"  Gross Amount: {_fmt(data.get('total_gross_amount'))}",
        f"  Tax: {_fmt(data.get('tax_amount'))}",
        f"  Net Amount: {_fmt(data.get('total_net_amount'))}",
        f"  Payment Due: {_fmt(data.get('payment_due_date'))}",
        f"  Payment Block: {data.get('payment_block', 'N/A')}",
    ]
    if data.get("block_reason"):
        lines.append(f"  Block Reason: {data['block_reason']}")

    vendor = data.get("vendor")
    if vendor:
        lines.extend([
            "",
            "### Vendor",
            f"  {vendor.get('label', vendor.get('id', '?'))} ({vendor.get('id', vendor.get('vertex_id', '?'))})",
        ])

    po = data.get("po")
    if po:
        lines.extend([
            "",
            "### Linked PO",
            f"  {po.get('id', '?')} — Value: {_fmt(po.get('total_net_value'))}",
        ])
        po_materials = po.get("materials", [])
        for m in po_materials:
            lines.append(f"  Material: {m.get('label', m.get('id', '?'))} — Qty: {_fmt(m.get('quantity'))}, Price: {_fmt(m.get('unit_price'))}")

    grs = data.get("goods_receipts", [])
    if grs:
        lines.append(f"\n### Goods Receipts ({len(grs)})")
        for gr in grs:
            lines.append(f"  - {gr.get('id', gr.get('vertex_id', '?'))} — {_fmt(gr.get('gr_date'))} [{gr.get('status', '?')}]")

    payments = data.get("payments", [])
    if payments:
        lines.append(f"\n### Payments ({len(payments)})")
        for pay in payments:
            lines.append(f"  - {pay.get('id', pay.get('vertex_id', '?'))} — {_fmt(pay.get('amount_applied'))}")

    return "\n".join(lines)


def format_entity(data: dict) -> str:
    """Format a single entity."""
    if not data:
        return "No entity found."
    lines = [f"## {data.get('vertex_type', 'Entity')}: {data.get('label', data.get('id', 'Unknown'))}"]
    for key, val in data.items():
        if key in ("vertex_type", "label"):
            continue
        lines.append(f"  {key}: {_fmt(val)}")
    return "\n".join(lines)


def format_search_results(results: list[dict]) -> str:
    """Format a list of search results."""
    if not results:
        return "No results found."
    lines = [f"## Search Results ({len(results)} found)"]
    for r in results[:15]:
        vtype = r.get("vertex_type", "?")
        label = r.get("label", r.get("id", "?"))
        rid = r.get("id", "?")
        lines.append(f"  - [{vtype}] {label} ({rid})")
    if len(results) > 15:
        lines.append(f"  ... and {len(results) - 15} more")
    return "\n".join(lines)


def format_list(items: list[dict], title: str = "Results") -> str:
    """Format a generic list of dicts."""
    if not items:
        return f"No {title.lower()} found."
    lines = [f"## {title} ({len(items)})"]
    for item in items[:15]:
        label = item.get("label", item.get("id", item.get("vertex_id", "?")))
        rid = item.get("id", item.get("vertex_id", "?"))
        vtype = item.get("vertex_type", "")
        prefix = f"[{vtype}] " if vtype else ""
        lines.append(f"  - {prefix}{label} ({rid})")
        # Show key attributes
        for key in ("status", "match_status", "quality_score", "contract_type", "po_date"):
            if key in item and item[key] is not None:
                lines.append(f"    {key}: {_fmt(item[key])}")
    if len(items) > 15:
        lines.append(f"  ... and {len(items) - 15} more")
    return "\n".join(lines)


def format_category_tree(data: dict) -> str:
    """Format a category tree with children and materials."""
    if not data:
        return "No category found."
    lines = [
        f"## Category: {data.get('label', data.get('id', 'Unknown'))}",
        f"  ID: {data.get('id', 'N/A')}",
        f"  Level: {_fmt(data.get('level'))}",
    ]
    children = data.get("children", [])
    if children:
        lines.append(f"\n### Subcategories ({len(children)})")
        for c in children:
            lines.append(f"  - {c.get('label', c.get('id', '?'))} ({c.get('id', c.get('vertex_id', '?'))})")

    materials = data.get("materials", [])
    if materials:
        lines.append(f"\n### Materials ({len(materials)})")
        for m in materials[:15]:
            lines.append(f"  - {m.get('label', m.get('id', m.get('vertex_id', '?')))} ({m.get('id', m.get('vertex_id', '?'))})")
        if len(materials) > 15:
            lines.append(f"  ... and {len(materials) - 15} more")
    return "\n".join(lines)


def format_vendor_plant_contracts(items: list[dict]) -> str:
    """Format multi-hop vendor → contract results for a plant."""
    if not items:
        return "No vendors with contracts found for this plant."
    lines = [f"## Vendors with Contracts at Plant ({len(items)} vendors)"]
    for entry in items:
        vendor = entry.get("vendor", {})
        lines.append(f"\n### {vendor.get('label', vendor.get('id', '?'))}")
        for c in entry.get("contracts", []):
            cid = c.get("contract_id", c.get("id", c.get("vertex_id", "?")))
            lines.append(f"  - {cid} ({c.get('contract_type', '?')}) [{c.get('status', '?')}]")
            lines.append(f"    Valid: {c.get('valid_from', '?')} → {c.get('valid_to', '?')}")
    return "\n".join(lines)


def _fmt(val: Any) -> str:
    """Format a value for display, handling None."""
    if val is None:
        return "N/A"
    return str(val)

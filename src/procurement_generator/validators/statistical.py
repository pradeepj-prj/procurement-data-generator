"""Statistical distribution checks (warnings only)."""
from __future__ import annotations

from .integrity import ValidationResult


def validate_distributions(store, config) -> list[ValidationResult]:
    """Check data distribution targets. All WARNING severity."""
    results = []

    # Material count
    mat_count = len(store.materials)
    target = config.target_materials
    results.append(ValidationResult(
        f"Material count ({mat_count} vs target {target})", "WARNING",
        abs(mat_count - target) / target < 0.15,
        f"{mat_count} materials generated", [],
    ))

    # Vendor count
    vnd_count = len(store.vendors)
    target = config.target_vendors
    results.append(ValidationResult(
        f"Vendor count ({vnd_count} vs target {target})", "WARNING",
        abs(vnd_count - target) / target < 0.15,
        f"{vnd_count} vendors generated", [],
    ))

    # Contract count
    ctr_count = len(store.contract_headers)
    target = config.target_contracts
    results.append(ValidationResult(
        f"Contract count ({ctr_count} vs target {target})", "WARNING",
        abs(ctr_count - target) / target < 0.20,
        f"{ctr_count} contracts generated", [],
    ))

    # Leaf category count
    leaves = [c for c in store.categories if c.level == 3]
    results.append(ValidationResult(
        f"Leaf category count ({len(leaves)} vs ~51)", "WARNING",
        45 <= len(leaves) <= 55,
        f"{len(leaves)} leaf categories", [],
    ))

    # Criticality distribution
    total = len(store.materials)
    if total > 0:
        high = sum(1 for m in store.materials if m.criticality == "HIGH")
        med = sum(1 for m in store.materials if m.criticality == "MEDIUM")
        low = sum(1 for m in store.materials if m.criticality == "LOW")
        results.append(ValidationResult(
            f"Criticality distribution (H:{high/total:.0%} M:{med/total:.0%} L:{low/total:.0%})",
            "WARNING", True,
            f"HIGH={high}, MEDIUM={med}, LOW={low}", [],
        ))

    # On-contract PO percentage
    if store.po_headers:
        on_contract = sum(1 for pol in store.po_line_items if pol.contract_id)
        total_lines = len(store.po_line_items)
        pct = on_contract / total_lines if total_lines else 0
        results.append(ValidationResult(
            f"On-contract PO line %: {pct:.0%} (target 70-75%)", "WARNING",
            0.60 <= pct <= 0.85,
            f"{on_contract}/{total_lines} PO lines on contract", [],
        ))

    # Maverick PO percentage
    if store.po_headers:
        mav = sum(1 for po in store.po_headers if po.maverick_flag)
        total_po = len(store.po_headers)
        pct = mav / total_po if total_po else 0
        results.append(ValidationResult(
            f"Maverick PO %: {pct:.0%} (target 5-8%)", "WARNING",
            0.02 <= pct <= 0.12,
            f"{mav}/{total_po} maverick POs", [],
        ))

    # Invoice match rates
    if store.invoice_headers:
        full_match = sum(1 for inv in store.invoice_headers if inv.match_status == "FULL_MATCH")
        total_inv = len(store.invoice_headers)
        pct = full_match / total_inv if total_inv else 0
        results.append(ValidationResult(
            f"Invoice full-match rate: {pct:.0%} (target 80-85%)", "WARNING",
            0.70 <= pct <= 0.95,
            f"{full_match}/{total_inv} invoices fully matched", [],
        ))

    return results

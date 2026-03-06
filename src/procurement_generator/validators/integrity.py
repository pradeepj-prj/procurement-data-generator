"""Structural integrity validation checks (FK checks, B10.1 + D5.1)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValidationResult:
    check_name: str
    severity: str  # FATAL | WARNING
    passed: bool
    message: str
    details: list[str]


def validate_structural_integrity(store) -> list[ValidationResult]:
    """Run all structural FK and integrity checks."""
    results = []
    mat_ids = store.material_ids()
    vnd_ids = store.vendor_ids()
    plt_ids = store.plant_ids()
    cat_ids = store.category_ids()
    pg_ids = store.purch_group_ids()
    le_ids = store.legal_entity_ids()
    cc_ids = store.cost_center_ids()

    # Material category FK
    orphans = [m.material_id for m in store.materials if m.category_id not in cat_ids]
    results.append(ValidationResult(
        "FK: material.category_id → category_hierarchy", "FATAL",
        len(orphans) == 0, f"{len(orphans)} orphan material categories", orphans[:10],
    ))

    # Source list material FK
    orphans = [f"{sl.material_id}@{sl.plant_id}" for sl in store.source_lists
               if sl.material_id not in mat_ids]
    results.append(ValidationResult(
        "FK: source_list.material_id → material_master", "FATAL",
        len(orphans) == 0, f"{len(orphans)} orphan source list materials", orphans[:10],
    ))

    # Source list vendor FK
    orphans = [f"{sl.vendor_id}@{sl.material_id}" for sl in store.source_lists
               if sl.vendor_id not in vnd_ids]
    results.append(ValidationResult(
        "FK: source_list.vendor_id → vendor_master", "FATAL",
        len(orphans) == 0, f"{len(orphans)} orphan source list vendors", orphans[:10],
    ))

    # Source list plant FK
    orphans = [f"{sl.plant_id}@{sl.material_id}" for sl in store.source_lists
               if sl.plant_id not in plt_ids]
    results.append(ValidationResult(
        "FK: source_list.plant_id → plant", "FATAL",
        len(orphans) == 0, f"{len(orphans)} orphan source list plants", orphans[:10],
    ))

    # Contract item material FK
    orphans = [f"{ci.contract_id}:{ci.material_id}" for ci in store.contract_items
               if ci.material_id not in mat_ids]
    results.append(ValidationResult(
        "FK: contract_item.material_id → material_master", "FATAL",
        len(orphans) == 0, f"{len(orphans)} orphan contract item materials", orphans[:10],
    ))

    # Contract header vendor FK
    orphans = [c.contract_id for c in store.contract_headers if c.vendor_id not in vnd_ids]
    results.append(ValidationResult(
        "FK: contract_header.vendor_id → vendor_master", "FATAL",
        len(orphans) == 0, f"{len(orphans)} orphan contract vendors", orphans[:10],
    ))

    # Vendor legal_entity FK
    orphans = [v.vendor_id for v in store.vendors if v.legal_entity_id not in le_ids]
    results.append(ValidationResult(
        "FK: vendor.legal_entity_id → legal_entity", "FATAL",
        len(orphans) == 0, f"{len(orphans)} orphan vendor legal entities", orphans[:10],
    ))

    # PG-category mapping FKs
    orphans = [f"{pgc.purch_group_id}" for pgc in store.pg_category_mappings
               if pgc.purch_group_id not in pg_ids]
    results.append(ValidationResult(
        "FK: pg_category.purch_group_id → purchasing_group", "FATAL",
        len(orphans) == 0, f"{len(orphans)} orphan PG-category PG refs", orphans[:10],
    ))

    orphans = [f"{pgc.category_id}" for pgc in store.pg_category_mappings
               if pgc.category_id not in cat_ids]
    results.append(ValidationResult(
        "FK: pg_category.category_id → category_hierarchy", "FATAL",
        len(orphans) == 0, f"{len(orphans)} orphan PG-category cat refs", orphans[:10],
    ))

    # Vendor category FKs
    orphans = [f"{vc.vendor_id}" for vc in store.vendor_categories if vc.vendor_id not in vnd_ids]
    results.append(ValidationResult(
        "FK: vendor_category.vendor_id → vendor_master", "FATAL",
        len(orphans) == 0, f"{len(orphans)} orphan vendor_category vendor refs", orphans[:10],
    ))

    # Material-plant extension FKs
    orphans = [f"{mpe.material_id}@{mpe.plant_id}" for mpe in store.material_plant_extensions
               if mpe.material_id not in mat_ids or mpe.plant_id not in plt_ids]
    results.append(ValidationResult(
        "FK: material_plant_extension → material + plant", "FATAL",
        len(orphans) == 0, f"{len(orphans)} invalid material-plant extensions", orphans[:10],
    ))

    # --- Transactional FKs ---

    # PR material FK
    orphans = [f"{prl.pr_id}:{prl.material_id}" for prl in store.pr_line_items
               if prl.material_id not in mat_ids]
    results.append(ValidationResult(
        "FK: pr_line.material_id → material_master", "FATAL",
        len(orphans) == 0, f"{len(orphans)} orphan PR line materials", orphans[:10],
    ))

    # PR plant FK
    pr_plant_orphans = [pr.pr_id for pr in store.pr_headers if pr.plant_id not in plt_ids]
    results.append(ValidationResult(
        "FK: pr_header.plant_id → plant", "FATAL",
        len(pr_plant_orphans) == 0, f"{len(pr_plant_orphans)} orphan PR plants", pr_plant_orphans[:10],
    ))

    # PO vendor FK
    orphans = [po.po_id for po in store.po_headers if po.vendor_id not in vnd_ids]
    results.append(ValidationResult(
        "FK: po_header.vendor_id → vendor_master", "FATAL",
        len(orphans) == 0, f"{len(orphans)} orphan PO vendors", orphans[:10],
    ))

    # GR PO FK
    po_ids = {po.po_id for po in store.po_headers}
    orphans = [gr.gr_id for gr in store.gr_headers if gr.po_id not in po_ids]
    results.append(ValidationResult(
        "FK: gr_header.po_id → po_header", "FATAL",
        len(orphans) == 0, f"{len(orphans)} orphan GR PO refs", orphans[:10],
    ))

    # Invoice PO FK
    orphans = [inv.invoice_id for inv in store.invoice_headers if inv.po_id not in po_ids]
    results.append(ValidationResult(
        "FK: invoice_header.po_id → po_header", "FATAL",
        len(orphans) == 0, f"{len(orphans)} orphan invoice PO refs", orphans[:10],
    ))

    # Payment vendor FK
    orphans = [p.payment_id for p in store.payments if p.vendor_id not in vnd_ids]
    results.append(ValidationResult(
        "FK: payment.vendor_id → vendor_master", "FATAL",
        len(orphans) == 0, f"{len(orphans)} orphan payment vendor refs", orphans[:10],
    ))

    # Payment-invoice link FKs
    pay_ids = {p.payment_id for p in store.payments}
    inv_ids = {inv.invoice_id for inv in store.invoice_headers}
    orphans = [f"{pil.payment_id}-{pil.invoice_id}" for pil in store.payment_invoice_links
               if pil.payment_id not in pay_ids or pil.invoice_id not in inv_ids]
    results.append(ValidationResult(
        "FK: payment_invoice_link → payment + invoice", "FATAL",
        len(orphans) == 0, f"{len(orphans)} orphan payment-invoice links", orphans[:10],
    ))

    return results

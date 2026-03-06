"""Business rule validation checks."""
from __future__ import annotations

from .integrity import ValidationResult
from ..utils import tier_value, max_tier


def validate_business_rules(store) -> list[ValidationResult]:
    """Run all business rule checks."""
    results = []

    # HIGH criticality must have reason code
    missing = [m.material_id for m in store.materials
               if m.criticality == "HIGH" and not m.criticality_reason_code]
    results.append(ValidationResult(
        "HIGH criticality must have reason code", "FATAL",
        len(missing) == 0, f"{len(missing)} HIGH materials missing reason code", missing[:10],
    ))

    # Confidentiality defaults: NULL tier -> INTERNAL
    null_tiers = [m.material_id for m in store.materials if not m.confidentiality_tier]
    null_tiers += [v.vendor_id for v in store.vendors if not v.confidentiality_tier]
    results.append(ValidationResult(
        "Confidentiality defaults (no NULL tiers)", "FATAL",
        len(null_tiers) == 0, f"{len(null_tiers)} entities with NULL tier", null_tiers[:10],
    ))

    # Blocked vendors must not have APPROVED source list entries
    blocked_ids = {v.vendor_id for v in store.vendors if v.status == "BLOCKED"}
    violations = [f"{sl.vendor_id}@{sl.material_id}" for sl in store.source_lists
                  if sl.vendor_id in blocked_ids and sl.approval_status == "APPROVED"]
    results.append(ValidationResult(
        "Blocked vendor sourcing", "FATAL",
        len(violations) == 0, f"{len(violations)} APPROVED entries for BLOCKED vendors", violations[:10],
    ))

    # Alias group integrity: same legal_entity_id
    alias_groups: dict[str, set] = {}
    for v in store.vendors:
        if v.alias_group:
            alias_groups.setdefault(v.alias_group, set()).add(v.legal_entity_id)
    violations = [ag for ag, les in alias_groups.items() if len(les) > 1]
    results.append(ValidationResult(
        "Alias group integrity", "FATAL",
        len(violations) == 0,
        f"{len(violations)} alias groups with inconsistent legal_entity_id", violations,
    ))

    # Confidentiality propagation on source list
    violations = []
    for sl in store.source_lists:
        vendor = store.vendor_by_id(sl.vendor_id)
        mat = store.material_by_id(sl.material_id)
        if not vendor or not mat:
            continue

        # Check contract tier if contract covered
        contract_tier = "PUBLIC"
        if sl.contract_covered_flag:
            for ci in store.contract_items:
                ch = store.contract_by_id(ci.contract_id)
                if (ch and ch.vendor_id == sl.vendor_id
                        and ci.material_id == sl.material_id
                        and ch.status == "ACTIVE"):
                    contract_tier = ch.confidentiality_tier
                    break

        required = max_tier(vendor.confidentiality_tier, mat.confidentiality_tier, contract_tier)
        if tier_value(sl.confidentiality_tier) < tier_value(required):
            violations.append(f"{sl.material_id}@{sl.plant_id}:{sl.vendor_id}")

    results.append(ValidationResult(
        "Confidentiality propagation", "FATAL",
        len(violations) == 0,
        f"{len(violations)} source list entries below required tier", violations[:10],
    ))

    # Contract-source alignment
    violations = []
    for sl in store.source_lists:
        if not sl.contract_covered_flag:
            continue
        found = False
        for ci in store.contract_items:
            ch = store.contract_by_id(ci.contract_id)
            if (ch and ch.vendor_id == sl.vendor_id
                    and ci.material_id == sl.material_id
                    and ch.status == "ACTIVE"):
                found = True
                break
        if not found:
            violations.append(f"{sl.material_id}@{sl.plant_id}:{sl.vendor_id}")
    results.append(ValidationResult(
        "Contract-source alignment", "FATAL",
        len(violations) == 0,
        f"{len(violations)} contract_covered entries without matching contract", violations[:10],
    ))

    # No POs to BLOCKED vendors
    blocked_pos = [po.po_id for po in store.po_headers if po.vendor_id in blocked_ids]
    results.append(ValidationResult(
        "No POs to BLOCKED vendors", "FATAL",
        len(blocked_pos) == 0, f"{len(blocked_pos)} POs to blocked vendors", blocked_pos[:10],
    ))

    return results


def propagate_confidentiality(store) -> int:
    """Post-generation: enforce confidentiality propagation on source list.
    Returns count of entries updated."""
    updated = 0
    for sl in store.source_lists:
        vendor = store.vendor_by_id(sl.vendor_id)
        mat = store.material_by_id(sl.material_id)
        if not vendor or not mat:
            continue

        contract_tier = "PUBLIC"
        if sl.contract_covered_flag:
            for ci in store.contract_items:
                ch = store.contract_by_id(ci.contract_id)
                if (ch and ch.vendor_id == sl.vendor_id
                        and ci.material_id == sl.material_id
                        and ch.status == "ACTIVE"):
                    contract_tier = ch.confidentiality_tier
                    break

        required = max_tier(vendor.confidentiality_tier, mat.confidentiality_tier, contract_tier)
        if tier_value(sl.confidentiality_tier) < tier_value(required):
            sl.confidentiality_tier = required
            updated += 1
    return updated

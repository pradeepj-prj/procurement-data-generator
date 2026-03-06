"""Scenario seed verification."""
from __future__ import annotations

from .integrity import ValidationResult


def verify_scenario_seeds(store, config) -> list[ValidationResult]:
    """Verify all 12 master data + 5 transactional scenario seeds."""
    results = []
    ref = config.demo_reference_date

    # SEED-001: Single-source LiDAR with expiring contract
    mat = store.material_by_id("MAT-LIDAR-2D")
    if mat:
        checks = []
        if mat.criticality != "HIGH":
            checks.append("criticality not HIGH")
        if mat.criticality_reason_code != "SAFETY":
            checks.append("reason not SAFETY")

        # Check single source
        for plant_id in ["SG01", "MY01"]:
            sls = store.source_lists_for_material_plant("MAT-LIDAR-2D", plant_id)
            if len(sls) != 1:
                checks.append(f"not single-source at {plant_id} (has {len(sls)})")

        # Vendor risk
        vendor = store.vendor_by_id("VND-HOKUYO")
        if vendor and vendor.risk_score <= 70:
            checks.append(f"vendor risk_score {vendor.risk_score} not > 70")

        # Contract expiry
        ctr = store.contract_by_id("CTR-00001")
        if ctr:
            days_to_expiry = (ctr.valid_to - ref).days
            if days_to_expiry > 60:
                checks.append(f"contract expires in {days_to_expiry} days, not within 60")

        results.append(ValidationResult(
            "SEED-001: LiDAR single-source", "FATAL",
            len(checks) == 0, "SEED-001 verification", checks,
        ))
    else:
        results.append(ValidationResult("SEED-001", "FATAL", False, "Material MAT-LIDAR-2D not found", []))

    # SEED-002: Battery cell supply concentration
    mat = store.material_by_id("MAT-BAT-CELL")
    if mat:
        checks = []
        catl = store.vendor_by_id("VND-CATL")
        eve = store.vendor_by_id("VND-EVE")
        if catl and catl.country != "CN":
            checks.append("CATL not CN")
        if eve and eve.country != "CN":
            checks.append("EVE not CN")
        if catl and eve and catl.quality_score == eve.quality_score:
            checks.append("quality scores identical")

        results.append(ValidationResult(
            "SEED-002: Battery concentration", "FATAL",
            len(checks) == 0, "SEED-002 verification", checks,
        ))

    # SEED-003: Restricted vendor bank account
    checks = []
    nidec = store.vendor_by_id("VND-NIDEC-JP")
    if nidec:
        if nidec.confidentiality_tier == "PUBLIC":
            checks.append("Nidec tier is PUBLIC, needs at least INTERNAL")
        if not nidec.bank_account:
            checks.append("bank_account not populated")
    results.append(ValidationResult(
        "SEED-003: Restricted bank account", "FATAL",
        len(checks) == 0, "SEED-003 verification", checks,
    ))

    # SEED-004: Mixed confidentiality BMS sources
    checks = []
    bms_sls = store.source_lists_for_material_plant("MAT-BMS", "MY01")
    tiers = set(sl.confidentiality_tier for sl in bms_sls)
    if len(tiers) < 2:
        checks.append(f"BMS source list has {len(tiers)} distinct tiers, need 2")
    results.append(ValidationResult(
        "SEED-004: BMS mixed tiers", "FATAL",
        len(checks) == 0, "SEED-004 verification", checks,
    ))

    # SEED-005: Off-contract motors
    checks = []
    motor_ids = ["MAT-MOT-200W", "MAT-MOT-400W", "MAT-MOT-INTG"]
    covered = 0
    for mid in motor_ids:
        for sl in store.source_lists:
            if sl.material_id == mid and sl.contract_covered_flag:
                covered += 1
                break
    if covered != 1:
        checks.append(f"{covered} motor materials with contract coverage, expected 1")
    results.append(ValidationResult(
        "SEED-005: Off-contract motors", "FATAL",
        len(checks) == 0, "SEED-005 verification", checks,
    ))

    # SEED-006: Vendor alias consolidation
    checks = []
    nj = store.vendor_by_id("VND-NIDEC-JP")
    nm = store.vendor_by_id("VND-NIDEC-MY")
    if nj and nm:
        if nj.legal_entity_id != nm.legal_entity_id:
            checks.append("Nidec vendors don't share legal_entity_id")
        if nj.alias_group != nm.alias_group:
            checks.append("Nidec vendors not in same alias group")
    else:
        checks.append("Nidec vendor records not found")
    results.append(ValidationResult(
        "SEED-006: Nidec alias", "FATAL",
        len(checks) == 0, "SEED-006 verification", checks,
    ))

    # SEED-007: SBC sourcing gap at SG01
    checks = []
    sbc_sg01 = store.source_lists_for_material_plant("MAT-SBC-IND", "SG01")
    sbc_my01 = store.source_lists_for_material_plant("MAT-SBC-IND", "MY01")
    if len(sbc_sg01) > 0:
        checks.append("SBC has source at SG01 (should have gap)")
    if len(sbc_my01) == 0:
        checks.append("SBC has no source at MY01")
    # Also check plant extension
    sbc_exts = store.plant_extensions_for_material("MAT-SBC-IND")
    sg01_ext = any(e.plant_id == "SG01" for e in sbc_exts)
    if sg01_ext:
        checks.append("SBC has plant extension at SG01 (should not)")
    results.append(ValidationResult(
        "SEED-007: SBC sourcing gap", "FATAL",
        len(checks) == 0, "SEED-007 verification", checks,
    ))

    # SEED-008: Camera long lead time
    checks = []
    cam_sls = store.source_lists_for_material_plant("MAT-CAM-3D", "MY01")
    if cam_sls:
        lt = cam_sls[0].lane_lead_time_days
        if lt < 60:
            checks.append(f"Camera lead time {lt} days, expected > 60")
    else:
        checks.append("No source list for camera at MY01")
    results.append(ValidationResult(
        "SEED-008: Camera lead time", "FATAL",
        len(checks) == 0, "SEED-008 verification", checks,
    ))

    # SEED-009: PG-MECH does not have ELEC categories
    checks = []
    mech_cats = {pgc.category_id for pgc in store.pg_category_mappings
                 if pgc.purch_group_id == "PG000004"}
    if "ELEC" in mech_cats or any(c.startswith("ELEC") for c in mech_cats):
        checks.append("PG-MECH has ELEC categories")
    results.append(ValidationResult(
        "SEED-009: PG-MECH no ELEC", "FATAL",
        len(checks) == 0, "SEED-009 verification", checks,
    ))

    # SEED-010: Contract price > 1.2x standard cost for connector
    checks = []
    mat_con = store.material_by_id("MAT-CON-24P")
    if mat_con:
        for ci in store.contract_items:
            if ci.material_id == "MAT-CON-24P":
                ratio = float(ci.agreed_price) / float(mat_con.standard_cost)
                if ratio <= 1.2:
                    checks.append(f"Contract/std ratio {ratio:.2f}, expected > 1.2")
                break
    results.append(ValidationResult(
        "SEED-010: Connector price variance", "FATAL",
        len(checks) == 0, "SEED-010 verification", checks,
    ))

    # SEED-011: Conditional vendor with quality < 70
    checks = []
    sp = store.vendor_by_id("VND-SHEETPRO")
    if sp:
        if sp.status != "CONDITIONAL":
            checks.append(f"SheetPro status {sp.status}, expected CONDITIONAL")
        if sp.quality_score >= 70:
            checks.append(f"SheetPro quality {sp.quality_score}, expected < 70")
    results.append(ValidationResult(
        "SEED-011: Conditional vendor", "FATAL",
        len(checks) == 0, "SEED-011 verification", checks,
    ))

    # SEED-012: Cross-plant motor sourcing
    checks = []
    my01_sls = store.source_lists_for_material_plant("MAT-MOT-200W", "MY01")
    vn01_sls = store.source_lists_for_material_plant("MAT-MOT-200W", "VN01")
    if not my01_sls:
        checks.append("No motor source at MY01")
    if not vn01_sls:
        checks.append("No motor source at VN01")
    if my01_sls and vn01_sls:
        if my01_sls[0].lane_lead_time_days == vn01_sls[0].lane_lead_time_days:
            checks.append("Same lead time at both plants")
    results.append(ValidationResult(
        "SEED-012: Cross-plant motor sourcing", "FATAL",
        len(checks) == 0, "SEED-012 verification", checks,
    ))

    return results

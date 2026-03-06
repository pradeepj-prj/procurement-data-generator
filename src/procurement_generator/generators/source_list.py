"""Generator for source list entries."""
from __future__ import annotations

import random
from datetime import date

from ..models import SourceList
from ..utils import vendor_material_code, to_decimal
from .base import BaseGenerator


class SourceListGenerator(BaseGenerator):
    """Generates seed + bulk source list entries."""

    def generate(self) -> None:
        self._load_seed_source_lists()
        self._generate_bulk_source_lists()

    def _load_seed_source_lists(self) -> None:
        seed_sl = self.seeds.get("seed_source_lists", {}).get("source_lists", [])
        for sl in seed_sl:
            self.store.source_lists.append(SourceList(
                material_id=sl["material_id"],
                plant_id=sl["plant_id"],
                vendor_id=sl["vendor_id"],
                preferred_rank=sl["preferred_rank"],
                contract_covered_flag=sl.get("contract_covered_flag", False),
                approval_status=sl.get("approval_status", "APPROVED"),
                lane_lead_time_days=sl.get("lane_lead_time_days", 14),
                vendor_material_code=sl.get("vendor_material_code", ""),
                min_order_qty=sl.get("min_order_qty"),
                confidentiality_tier=sl.get("confidentiality_tier", "INTERNAL"),
                valid_from=None,
                valid_to=None,
            ))

    def _generate_bulk_source_lists(self) -> None:
        """Generate source list for materials not yet covered by seeds."""
        # Build set of (material_id, plant_id) already in source list
        existing = {(sl.material_id, sl.plant_id) for sl in self.store.source_lists}

        # Build vendor lookup by supported subcategories
        vendor_by_subcat: dict[str, list] = {}
        for vc in self.store.vendor_categories:
            vendor_by_subcat.setdefault(vc.category_id, []).append(vc.vendor_id)

        # Also build by top-level category
        vendor_by_topcat: dict[str, list] = {}
        for v in self.store.vendors:
            for cat in v.supported_categories.split(","):
                cat = cat.strip()
                vendor_by_topcat.setdefault(cat, []).append(v.vendor_id)

        # Contract lookup: (vendor_id, material_id) -> contract exists
        contract_coverage = set()
        for ci in self.store.contract_items:
            ch = self.store.contract_by_id(ci.contract_id)
            if ch and ch.status == "ACTIVE":
                contract_coverage.add((ch.vendor_id, ci.material_id))

        # For each material-plant extension not yet covered
        for mpe in self.store.material_plant_extensions:
            key = (mpe.material_id, mpe.plant_id)
            if key in existing:
                continue

            mat = self.store.material_by_id(mpe.material_id)
            if not mat:
                continue

            # Find eligible vendors
            top_cat = self.store.category_top_level(mat.category_id)
            # Try subcategory match first
            parent_cat = None
            cat = self.store.category_by_id(mat.category_id)
            if cat and cat.parent_category_id:
                parent_cat = cat.parent_category_id

            eligible_vendors = set()
            if parent_cat and parent_cat in vendor_by_subcat:
                eligible_vendors.update(vendor_by_subcat[parent_cat])
            if top_cat and top_cat in vendor_by_topcat:
                eligible_vendors.update(vendor_by_topcat[top_cat])

            # Filter out blocked vendors
            active_vendors = [v_id for v_id in eligible_vendors
                              if (v := self.store.vendor_by_id(v_id)) and v.status != "BLOCKED"]

            if not active_vendors:
                # Assign a random active vendor
                all_active = [v.vendor_id for v in self.store.vendors if v.status == "ACTIVE"]
                if all_active:
                    active_vendors = [random.choice(all_active)]
                else:
                    continue

            # 2-3 source entries per material-plant
            num_entries = min(len(active_vendors), random.randint(2, 3))
            selected = random.sample(active_vendors, min(num_entries, len(active_vendors)))

            for rank, vid in enumerate(selected, 1):
                vendor = self.store.vendor_by_id(vid)
                if not vendor:
                    continue

                has_contract = (vid, mpe.material_id) in contract_coverage
                if vendor.status == "CONDITIONAL":
                    approval = "CONDITIONAL"
                else:
                    approval = "APPROVED"

                # Lane lead time: vendor typical +/- variation for distance
                base_lt = vendor.lead_time_days_typical
                lt_var = random.randint(-3, 7)
                lane_lt = max(1, base_lt + lt_var)

                self.store.source_lists.append(SourceList(
                    material_id=mpe.material_id,
                    plant_id=mpe.plant_id,
                    vendor_id=vid,
                    preferred_rank=rank,
                    contract_covered_flag=has_contract,
                    approval_status=approval,
                    lane_lead_time_days=lane_lt,
                    vendor_material_code=vendor_material_code(mat.display_code),
                    min_order_qty=mpe.min_order_qty,
                    confidentiality_tier="INTERNAL",
                    valid_from=None,
                    valid_to=None,
                ))

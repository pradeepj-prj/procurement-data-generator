"""Generator for contract headers and items."""
from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal

from ..models import ContractHeader, ContractItem, UOMConversion
from ..utils import to_decimal, random_date
from .base import BaseGenerator


class ContractGenerator(BaseGenerator):
    """Generates seed + bulk contracts with items and UOM conversions."""

    def generate(self) -> None:
        self._load_seed_contracts()
        self._generate_bulk_contracts()
        self._generate_uom_conversions()

    def _load_seed_contracts(self) -> None:
        seed_ctrs = self.seeds.get("seed_contracts", {}).get("contracts", [])
        for sc in seed_ctrs:
            vf = sc["valid_from"]
            vt = sc["valid_to"]
            if isinstance(vf, str):
                vf = date.fromisoformat(vf)
            if isinstance(vt, str):
                vt = date.fromisoformat(vt)

            self.store.contract_headers.append(ContractHeader(
                contract_id=sc["contract_id"],
                display_code=sc["display_code"],
                vendor_id=sc["vendor_id"],
                valid_from=vf,
                valid_to=vt,
                contract_type=sc["contract_type"],
                status=sc["status"],
                currency=sc.get("currency", "USD"),
                incoterms=sc.get("incoterms", "FOB"),
                confidentiality_tier=sc.get("confidentiality_tier", "INTERNAL"),
            ))

            for item in sc.get("items", []):
                self.store.contract_items.append(ContractItem(
                    contract_id=sc["contract_id"],
                    item_number=item["item_number"],
                    material_id=item["material_id"],
                    agreed_price=to_decimal(item["agreed_price"]),
                    price_uom=item["price_uom"],
                    max_quantity=item.get("max_quantity"),
                    target_value=to_decimal(item["target_value"]) if item.get("target_value") else None,
                    consumed_quantity=item.get("consumed_quantity"),
                    consumed_value=to_decimal(item["consumed_value"]) if item.get("consumed_value") else None,
                ))

    def _generate_bulk_contracts(self) -> None:
        target = self.config.target_contracts
        existing = len(self.store.contract_headers)
        remaining = target - existing

        used_ids = {c.contract_id for c in self.store.contract_headers}
        # Vendors already with contracts
        contracted_vendors = {c.vendor_id for c in self.store.contract_headers}

        # Find vendors eligible for contracts (ACTIVE, not already at max)
        eligible_vendors = [v for v in self.store.vendors
                           if v.status == "ACTIVE" and v.vendor_id not in contracted_vendors]
        random.shuffle(eligible_vendors)

        ref_date = self.config.demo_reference_date
        seq = len(used_ids) + 1

        # Distribution targets
        expiring_soon = 0
        high_consumed = 0
        expired = 0
        restricted = 0

        for i in range(remaining):
            if not eligible_vendors:
                # Re-use vendors that already have contracts
                eligible_vendors = [v for v in self.store.vendors if v.status == "ACTIVE"]
                random.shuffle(eligible_vendors)

            vendor = eligible_vendors.pop(0) if eligible_vendors else random.choice(
                [v for v in self.store.vendors if v.status == "ACTIVE"]
            )

            ctr_id = f"CTR-{seq:05d}"
            while ctr_id in used_ids:
                seq += 1
                ctr_id = f"CTR-{seq:05d}"
            used_ids.add(ctr_id)
            seq += 1

            # Display code
            v_short = vendor.display_code.split("-")[0] if "-" in vendor.display_code else vendor.display_code[:6]
            year = ref_date.year
            dc = f"CTR-{v_short}-{year}-{seq % 100:02d}"

            # Contract type
            ctr_type = random.choice(["QUANTITY", "VALUE"])

            # Determine validity and status
            if expired < 3 and random.random() < 0.08:
                # Expired contract
                valid_from = ref_date - timedelta(days=random.randint(365, 540))
                valid_to = ref_date - timedelta(days=random.randint(10, 90))
                status = "EXPIRED"
                expired += 1
            elif expiring_soon < 5 and random.random() < 0.15:
                # Expiring within 60 days
                valid_from = ref_date - timedelta(days=random.randint(180, 365))
                valid_to = ref_date + timedelta(days=random.randint(5, 55))
                status = "ACTIVE"
                expiring_soon += 1
            else:
                # Normal active
                valid_from = ref_date - timedelta(days=random.randint(60, 365))
                valid_to = ref_date + timedelta(days=random.randint(90, 540))
                status = "ACTIVE"

            # Tier
            if restricted < 6 and random.random() < 0.18:
                tier = "RESTRICTED"
                restricted += 1
            else:
                tier = "INTERNAL"

            self.store.contract_headers.append(ContractHeader(
                contract_id=ctr_id,
                display_code=dc,
                vendor_id=vendor.vendor_id,
                valid_from=valid_from,
                valid_to=valid_to,
                contract_type=ctr_type,
                status=status,
                currency=vendor.currency,
                incoterms=vendor.incoterms_default,
                confidentiality_tier=tier,
            ))

            # Generate 1-3 contract items
            # Find materials this vendor could supply via source list
            vendor_mats = set()
            for sl in self.store.source_lists:
                if sl.vendor_id == vendor.vendor_id:
                    vendor_mats.add(sl.material_id)

            # If no source list yet, find materials by category
            if not vendor_mats:
                for vc in self.store.vendor_categories:
                    if vc.vendor_id == vendor.vendor_id:
                        for m in self.store.materials:
                            top = self.store.category_top_level(m.category_id)
                            parent = self.store.category_by_id(m.category_id)
                            if parent and parent.parent_category_id == vc.category_id:
                                vendor_mats.add(m.material_id)
                            elif top == vc.category_id:
                                vendor_mats.add(m.material_id)

            if not vendor_mats:
                # Pick random materials
                vendor_mats = {m.material_id for m in random.sample(
                    self.store.materials, min(3, len(self.store.materials))
                )}

            num_items = min(len(vendor_mats), random.randint(1, 3))
            selected_mats = random.sample(list(vendor_mats), num_items)

            for item_seq, mat_id in enumerate(selected_mats):
                mat = self.store.material_by_id(mat_id)
                if not mat:
                    continue

                # Price near standard cost
                price_mult = random.uniform(0.85, 1.20)
                agreed_price = to_decimal(float(mat.standard_cost) * price_mult)

                if ctr_type == "QUANTITY":
                    max_qty = random.randint(100, 5000)
                    target_val = None
                    # Consumption
                    if high_consumed < 4 and random.random() < 0.12:
                        consumed_pct = random.uniform(0.80, 0.95)
                        high_consumed += 1
                    else:
                        consumed_pct = random.uniform(0.10, 0.70)
                    consumed_qty = int(max_qty * consumed_pct)
                    consumed_val = None
                else:
                    max_qty = None
                    target_val = to_decimal(random.uniform(10000, 500000))
                    consumed_qty = None
                    if high_consumed < 4 and random.random() < 0.12:
                        consumed_pct = random.uniform(0.80, 0.95)
                        high_consumed += 1
                    else:
                        consumed_pct = random.uniform(0.10, 0.70)
                    consumed_val = to_decimal(float(target_val) * consumed_pct)

                self.store.contract_items.append(ContractItem(
                    contract_id=ctr_id,
                    item_number=(item_seq + 1) * 10,
                    material_id=mat_id,
                    agreed_price=agreed_price,
                    price_uom=mat.base_uom,
                    max_quantity=max_qty,
                    target_value=target_val,
                    consumed_quantity=consumed_qty,
                    consumed_value=consumed_val,
                ))

    def _generate_uom_conversions(self) -> None:
        """Generate UOM conversion table for intentional mismatches."""
        # From spec: BATCELL-21700 EA->BOX and CONN-24P-MOLEX EA->REEL
        conversions = [
            ("MAT-BAT-CELL", "EA", "BOX", "0.01"),
            ("MAT-CON-24P", "EA", "REEL", "0.002"),
        ]
        for mat_id, from_uom, to_uom, factor in conversions:
            if self.store.material_by_id(mat_id):
                self.store.uom_conversions.append(UOMConversion(
                    material_id=mat_id,
                    from_uom=from_uom,
                    to_uom=to_uom,
                    conversion_factor=to_decimal(factor, 4),
                ))

"""Generator for purchase orders."""
from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal

from ..models import POHeader, POLineItem
from ..utils import random_date, to_decimal
from .base import BaseGenerator


class PurchaseOrderGenerator(BaseGenerator):
    """Generates purchase orders from PRs and seed scenarios."""

    def generate(self) -> None:
        self._generate_seed_pos()
        self._generate_bulk_pos()

    def _generate_seed_pos(self) -> None:
        """Generate POs required by scenario seed extensions."""
        ref = self.config.demo_reference_date
        start = self.config.time_window_start

        # SEED-001 ext: 6-8 POs against CTR-HOKUYO-2025-01
        self._gen_seed_contract_pos(
            "CTR-00001", "VND-HOKUYO", "MAT-LIDAR-2D", "MY01",
            num_pos=7, start_date=start + timedelta(days=30),
            end_date=ref - timedelta(days=15), qty_per_po_range=(50, 75),
            po_start_seq=1,
        )

        # SEED-002 ext: CATL POs (8-10 on contract) + EVE POs (3-5 off contract)
        self._gen_seed_contract_pos(
            "CTR-00002", "VND-CATL", "MAT-BAT-CELL", "MY01",
            num_pos=9, start_date=start + timedelta(days=60),
            end_date=ref - timedelta(days=30), qty_per_po_range=(2000, 4000),
            po_start_seq=8,
        )
        # EVE off-contract POs
        for i in range(4):
            po_date = random_date(start + timedelta(days=120), ref - timedelta(days=60))
            self._create_po(
                po_seq=17 + i, vendor_id="VND-EVE", plant_id="MY01",
                po_date=po_date, maverick=False,
                lines=[(
                    "MAT-BAT-CELL", random.randint(1000, 3000),
                    to_decimal(random.uniform(5.0, 5.8)), None, None,
                )],
            )

        # SEED-005 ext: On-contract motor POs + maverick POs
        self._gen_seed_contract_pos(
            "CTR-00003", "VND-NIDEC-JP", "MAT-MOT-200W", "MY01",
            num_pos=6, start_date=start + timedelta(days=90),
            end_date=ref - timedelta(days=20), qty_per_po_range=(50, 100),
            po_start_seq=21,
        )
        # Maverick 400W motor POs
        for i in range(3):
            po_date = random_date(start + timedelta(days=150), ref - timedelta(days=30))
            price = to_decimal(random.uniform(102, 118))
            self._create_po(
                po_seq=27 + i, vendor_id="VND-NIDEC-JP", plant_id="MY01",
                po_date=po_date, maverick=True,
                lines=[(
                    "MAT-MOT-400W", random.randint(20, 60),
                    price, None, None,
                )],
                notes="Off-contract purchase - no framework agreement for 400W variant",
            )

        # SEED-006 ext: Split POs across Nidec entities
        for i in range(4):
            po_date = random_date(start + timedelta(days=60), ref - timedelta(days=30))
            self._create_po(
                po_seq=30 + i, vendor_id="VND-NIDEC-JP", plant_id="MY01",
                po_date=po_date, maverick=False,
                lines=[("MAT-MOT-200W", random.randint(30, 80), to_decimal(85), "CTR-00003", 10)],
            )
        for i in range(3):
            po_date = random_date(start + timedelta(days=60), ref - timedelta(days=30))
            self._create_po(
                po_seq=34 + i, vendor_id="VND-NIDEC-MY", plant_id="VN01",
                po_date=po_date, maverick=False,
                lines=[("MAT-MOT-200W", random.randint(20, 50), to_decimal(random.uniform(88, 95)), None, None)],
            )

        # SEED-008 ext: Recent camera PO + historical
        self._create_po(
            po_seq=37, vendor_id="VND-INTEL", plant_id="MY01",
            po_date=ref - timedelta(days=15), maverick=False,
            lines=[("MAT-CAM-3D", 40, to_decimal(236), None, None)],
        )

        # SEED-T01: Connector PO for invoice mismatch
        self._create_po(
            po_seq=38, vendor_id="VND-MOLEX-SG", plant_id="VN01",
            po_date=ref - timedelta(days=60), maverick=False,
            lines=[("MAT-CON-24P", 2000, to_decimal(4.85), "CTR-00004", 10)],
        )

        # SEED-T04: Post-expiry camera POs at higher price
        for i, price in enumerate([236, 241]):
            po_date = random_date(
                max(start, ref - timedelta(days=200)),
                ref - timedelta(days=30),
            )
            self._create_po(
                po_seq=39 + i, vendor_id="VND-INTEL", plant_id="MY01",
                po_date=po_date, maverick=False,
                lines=[("MAT-CAM-3D", random.randint(20, 40), to_decimal(price), None, None)],
            )

    def _gen_seed_contract_pos(
        self, contract_id: str, vendor_id: str, material_id: str, plant_id: str,
        num_pos: int, start_date, end_date, qty_per_po_range: tuple, po_start_seq: int,
    ) -> None:
        """Generate POs against a specific contract."""
        contract = self.store.contract_by_id(contract_id)
        if not contract:
            return
        items = self.store.contract_items_for_contract(contract_id)
        if not items:
            return
        item = items[0]

        interval = max(1, (end_date - start_date).days // num_pos)
        for i in range(num_pos):
            po_date = start_date + timedelta(days=interval * i + random.randint(0, 5))
            if po_date > end_date:
                po_date = end_date
            qty = random.randint(*qty_per_po_range)
            self._create_po(
                po_seq=po_start_seq + i, vendor_id=vendor_id, plant_id=plant_id,
                po_date=po_date, maverick=False,
                lines=[(material_id, qty, item.agreed_price, contract_id, item.item_number)],
            )

    def _create_po(
        self, po_seq: int, vendor_id: str, plant_id: str,
        po_date, maverick: bool, lines: list[tuple],
        notes: str | None = None,
    ) -> None:
        po_id = f"PO-{po_seq:06d}"

        # Check if this PO already exists
        if any(po.po_id == po_id for po in self.store.po_headers):
            return

        vendor = self.store.vendor_by_id(vendor_id)
        if not vendor:
            return

        pg = None
        if lines:
            mat = self.store.material_by_id(lines[0][0])
            if mat:
                pg = self.store.purch_group_for_category(mat.category_id)

        total = Decimal("0")
        po_lines = []
        for i, (mat_id, qty, price, ctr_id, ctr_item) in enumerate(lines):
            mat = self.store.material_by_id(mat_id)
            if not mat:
                continue
            net = to_decimal(float(price) * qty)
            total += net

            # Find source list for lead time
            sls = self.store.source_lists_for_material_plant(mat_id, plant_id)
            lt = 14
            for sl in sls:
                if sl.vendor_id == vendor_id:
                    lt = sl.lane_lead_time_days
                    break

            delivery_date = po_date + timedelta(days=lt + random.randint(0, 5))

            po_lines.append(POLineItem(
                po_id=po_id,
                po_line_number=(i + 1) * 10,
                material_id=mat_id,
                quantity=to_decimal(qty),
                uom=mat.base_uom,
                unit_price=price,
                net_value=net,
                price_currency=vendor.currency,
                requested_delivery_date=delivery_date,
                actual_delivery_date=None,
                contract_id=ctr_id,
                contract_item_number=ctr_item,
                pr_id=None,
                pr_line_number=None,
            ))

        po_type = "RUSH" if maverick and random.random() < 0.3 else "STANDARD"

        self.store.po_headers.append(POHeader(
            po_id=po_id,
            po_date=po_date,
            vendor_id=vendor_id,
            purch_org_id="PO01",
            purch_group_id=pg or "PG000001",
            plant_id=plant_id,
            po_type=po_type,
            status="SENT",
            incoterms=vendor.incoterms_default,
            payment_terms=vendor.payment_terms,
            currency=vendor.currency,
            total_net_value=total,
            maverick_flag=maverick,
            notes=notes,
        ))
        self.store.po_line_items.extend(po_lines)

    def _generate_bulk_pos(self) -> None:
        """Generate bulk POs from converted PRs + direct contract POs."""
        target = self.config.target_pos
        existing = len(self.store.po_headers)
        remaining = target - existing
        if remaining <= 0:
            return

        # Build contract material index for on-contract PO generation
        contract_mats: list[tuple] = []  # (contract_id, item_number, material_id, vendor_id, price)
        for ci in self.store.contract_items:
            ch = self.store.contract_by_id(ci.contract_id)
            if ch and ch.status == "ACTIVE":
                contract_mats.append((ci.contract_id, ci.item_number, ci.material_id,
                                      ch.vendor_id, ci.agreed_price))

        # Budget: ~72% on-contract, ~6% maverick, rest PR-derived
        on_contract_target = int(remaining * 0.72)
        maverick_target = int(remaining * 0.065)
        po_seq = existing + 100

        # On-contract POs
        for _ in range(on_contract_target):
            if not contract_mats:
                break
            cm = random.choice(contract_mats)
            ctr_id, item_num, mat_id, vendor_id, price = cm

            mat = self.store.material_by_id(mat_id)
            vendor = self.store.vendor_by_id(vendor_id)
            if not mat or not vendor:
                continue

            # Pick a plant where this material is available
            exts = self.store.plant_extensions_for_material(mat_id)
            if not exts:
                continue
            plant_id = random.choice(exts).plant_id

            po_date = random_date(
                self.config.time_window_start + timedelta(days=30),
                self.config.time_window_end - timedelta(days=30),
            )

            # Check contract validity dates
            ch = self.store.contract_by_id(ctr_id)
            if ch and (po_date < ch.valid_from or po_date > ch.valid_to):
                po_date = random_date(ch.valid_from, min(ch.valid_to, self.config.time_window_end - timedelta(days=10)))

            qty = random.randint(10, 200) if mat.standard_cost > Decimal("50") else random.randint(50, 2000)

            po_seq += 1
            self._create_po(
                po_seq=po_seq, vendor_id=vendor_id, plant_id=plant_id,
                po_date=po_date, maverick=False,
                lines=[(mat_id, qty, price, ctr_id, item_num)],
            )

        # Dedicated maverick PO generation
        maverick_count = sum(1 for po in self.store.po_headers if po.maverick_flag)
        active_vendors = [v for v in self.store.vendors if v.status == "ACTIVE"]
        all_mats = [m for m in self.store.materials if m.material_type != "SERVICE"]

        while maverick_count < maverick_target and len(self.store.po_headers) < target and active_vendors and all_mats:
            mat = random.choice(all_mats)
            vendor = random.choice(active_vendors)
            exts = self.store.plant_extensions_for_material(mat.material_id)
            if not exts:
                continue
            plant_id = random.choice(exts).plant_id

            po_date = random_date(
                self.config.time_window_start + timedelta(days=30),
                self.config.time_window_end - timedelta(days=30),
            )
            qty = random.randint(5, 100) if mat.standard_cost > Decimal("50") else random.randint(20, 500)
            price = to_decimal(float(mat.standard_cost) * random.uniform(1.20, 1.50))

            po_seq += 1
            self._create_po(
                po_seq=po_seq, vendor_id=vendor.vendor_id, plant_id=plant_id,
                po_date=po_date, maverick=True,
                lines=[(mat.material_id, qty, price, None, None)],
                notes="Maverick purchase - non-preferred vendor",
            )
            maverick_count += 1

        # Find converted PR line items not yet linked to POs
        used_pr_lines = {(pol.pr_id, pol.pr_line_number)
                        for pol in self.store.po_line_items
                        if pol.pr_id}

        available_pr_lines = [
            prl for prl in self.store.pr_line_items
            if prl.status == "PO_CREATED"
            and (prl.pr_id, prl.pr_line_number) not in used_pr_lines
        ]
        random.shuffle(available_pr_lines)

        i = 0
        while len(self.store.po_headers) < target and i < len(available_pr_lines):
            prl = available_pr_lines[i]
            i += 1

            pr = None
            for prh in self.store.pr_headers:
                if prh.pr_id == prl.pr_id:
                    pr = prh
                    break
            if not pr:
                continue

            mat = self.store.material_by_id(prl.material_id)
            if not mat:
                continue

            # Find a vendor from source list
            sls = self.store.source_lists_for_material_plant(prl.material_id, pr.plant_id)

            is_maverick = (
                maverick_count < maverick_target
                and random.random() < 0.07
            )

            if is_maverick or not sls:
                # Maverick: pick any active vendor
                active_vendors = [v for v in self.store.vendors if v.status == "ACTIVE"]
                if not active_vendors:
                    continue
                vendor = random.choice(active_vendors)
                price_mult = random.uniform(1.20, 1.50)
                contract_id = None
                contract_item = None
                maverick_count += 1
                lt = vendor.lead_time_days_typical
            else:
                # Normal: use preferred vendor
                sl = sls[0]  # preferred rank 1
                vendor = self.store.vendor_by_id(sl.vendor_id)
                if not vendor:
                    continue

                # Check contract coverage - search all source entries and contracts
                contract_id = None
                contract_item = None
                # Try each source list entry for contract coverage
                for sl_entry in sls:
                    v = self.store.vendor_by_id(sl_entry.vendor_id)
                    if not v or v.status == "BLOCKED":
                        continue
                    for ci in self.store.contract_items:
                        ch = self.store.contract_by_id(ci.contract_id)
                        if (ch and ch.vendor_id == sl_entry.vendor_id
                                and ci.material_id == prl.material_id
                                and ch.status == "ACTIVE"):
                            contract_id = ci.contract_id
                            contract_item = ci.item_number
                            vendor = v  # Use the contracted vendor
                            sl = sl_entry
                            break
                    if contract_id:
                        break

                # If no direct contract, also check for any active contract for this material
                if not contract_id and random.random() < 0.70:
                    for ci in self.store.contract_items:
                        ch = self.store.contract_by_id(ci.contract_id)
                        if (ch and ci.material_id == prl.material_id
                                and ch.status == "ACTIVE"):
                            # Check if this vendor has source list entry
                            v = self.store.vendor_by_id(ch.vendor_id)
                            if v and v.status != "BLOCKED":
                                contract_id = ci.contract_id
                                contract_item = ci.item_number
                                vendor = v
                                break

                if contract_id:
                    price_mult = 1.0  # Use contract price
                else:
                    price_mult = random.uniform(1.05, 1.15)

                lt = sl.lane_lead_time_days

            if contract_id:
                ci_item = None
                for ci in self.store.contract_items:
                    if ci.contract_id == contract_id and ci.item_number == contract_item:
                        ci_item = ci
                        break
                price = ci_item.agreed_price if ci_item else to_decimal(float(mat.standard_cost) * price_mult)
            else:
                price = to_decimal(float(mat.standard_cost) * price_mult)

            po_seq += 1
            po_id = f"PO-{po_seq:06d}"
            po_date = pr.pr_date + timedelta(days=random.randint(1, 7))

            net = to_decimal(float(price) * float(prl.quantity))
            delivery_date = po_date + timedelta(days=lt + random.randint(0, 5))

            pg = self.store.purch_group_for_category(mat.category_id) or "PG000001"

            self.store.po_headers.append(POHeader(
                po_id=po_id,
                po_date=po_date,
                vendor_id=vendor.vendor_id,
                purch_org_id="PO01",
                purch_group_id=pg,
                plant_id=pr.plant_id,
                po_type="RUSH" if pr.pr_type == "URGENT" else "STANDARD",
                status="SENT",
                incoterms=vendor.incoterms_default,
                payment_terms=vendor.payment_terms,
                currency=vendor.currency,
                total_net_value=net,
                maverick_flag=is_maverick,
                notes="Maverick purchase - non-preferred vendor" if is_maverick else None,
            ))

            self.store.po_line_items.append(POLineItem(
                po_id=po_id,
                po_line_number=10,
                material_id=prl.material_id,
                quantity=prl.quantity,
                uom=prl.uom,
                unit_price=price,
                net_value=net,
                price_currency=vendor.currency,
                requested_delivery_date=delivery_date,
                actual_delivery_date=None,
                contract_id=contract_id,
                contract_item_number=contract_item,
                pr_id=prl.pr_id,
                pr_line_number=prl.pr_line_number,
            ))

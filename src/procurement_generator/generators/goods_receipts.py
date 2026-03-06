"""Generator for goods receipts."""
from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal

from ..models import GRHeader, GRLineItem
from ..utils import to_decimal, fake, random_date
from .base import BaseGenerator

REJECTION_REASONS = ["DAMAGED", "WRONG_SPEC", "DEFECTIVE", "EXPIRED"]


class GoodsReceiptGenerator(BaseGenerator):
    """Generates goods receipts for POs."""

    def generate(self) -> None:
        target = self.config.target_grs
        ref = self.config.demo_reference_date
        gr_seq = 1

        # Process each PO that should have a GR
        # ~92% of POs get a GR, ~8% still open
        po_headers = list(self.store.po_headers)
        random.shuffle(po_headers)

        for po in po_headers:
            if gr_seq > target:
                break

            # Skip ~8% as still open/in-transit
            if random.random() < 0.08:
                continue

            vendor = self.store.vendor_by_id(po.vendor_id)
            if not vendor:
                continue

            # Get PO lines for this PO
            po_lines = [pol for pol in self.store.po_line_items if pol.po_id == po.po_id]
            if not po_lines:
                continue

            # Pick a storage location at the plant
            storage_locs = self.store.storage_locs_for_plant(po.plant_id)
            # Prefer RAW storage
            raw_locs = [sl for sl in storage_locs if sl.storage_type == "RAW"]
            storage_loc = random.choice(raw_locs) if raw_locs else (
                random.choice(storage_locs) if storage_locs else None
            )
            if not storage_loc:
                continue

            # Delivery timing based on vendor OTD
            otd_rate = float(vendor.on_time_delivery_rate) / 100.0
            is_on_time = random.random() < otd_rate

            # Calculate GR date from PO date + lead time
            pol = po_lines[0]
            if is_on_time:
                # On-time or early
                if random.random() < 0.7:
                    # On-time
                    gr_date = pol.requested_delivery_date + timedelta(days=random.randint(-3, 0))
                else:
                    # Early
                    gr_date = pol.requested_delivery_date - timedelta(days=random.randint(4, 7))
            else:
                # Late
                if random.random() < 0.7:
                    # Minor late
                    gr_date = pol.requested_delivery_date + timedelta(days=random.randint(1, 7))
                else:
                    # Significant late
                    gr_date = pol.requested_delivery_date + timedelta(days=random.randint(8, 30))

            # Ensure GR date is after PO date and before ref date
            if gr_date <= po.po_date:
                gr_date = po.po_date + timedelta(days=1)
            if gr_date > ref:
                gr_date = ref - timedelta(days=random.randint(1, 10))
            if gr_date <= po.po_date:
                gr_date = po.po_date + timedelta(days=1)

            gr_id = f"GR-{gr_seq:06d}"
            gr_seq += 1

            # Quality rejection based on vendor quality score
            quality_threshold = vendor.quality_score / 100.0
            has_rejection = random.random() > quality_threshold

            status = "POSTED"
            if has_rejection and random.random() < 0.3:
                status = "QUALITY_HOLD"

            self.store.gr_headers.append(GRHeader(
                gr_id=gr_id,
                gr_date=gr_date,
                po_id=po.po_id,
                plant_id=po.plant_id,
                storage_loc_id=storage_loc.storage_loc_id,
                received_by=fake.name(),
                status=status,
                notes=None,
            ))

            # Generate GR line items
            for line_idx, pol in enumerate(po_lines):
                mat = self.store.material_by_id(pol.material_id)
                if not mat:
                    continue

                ordered_qty = float(pol.quantity)

                # Quantity received distribution
                r = random.random()
                if r < 0.92:
                    # Full delivery
                    qty_received = ordered_qty
                elif r < 0.95:
                    # Partial delivery
                    qty_received = ordered_qty * random.uniform(0.6, 0.95)
                else:
                    # Over-delivery (within tolerance)
                    qty_received = ordered_qty * random.uniform(1.01, 1.10)

                qty_received = max(1, round(qty_received))

                # Quality rejections
                qty_rejected = 0
                rejection_reason = None
                if has_rejection and random.random() < 0.3:
                    reject_pct = random.uniform(0.02, 0.15)
                    qty_rejected = max(1, round(qty_received * reject_pct))
                    rejection_reason = random.choice(REJECTION_REASONS)

                qty_accepted = qty_received - qty_rejected

                batch = f"B{gr_date.strftime('%y%m')}-{random.randint(1000, 9999)}" if random.random() < 0.5 else None

                self.store.gr_line_items.append(GRLineItem(
                    gr_id=gr_id,
                    gr_line_number=(line_idx + 1) * 10,
                    po_id=po.po_id,
                    po_line_number=pol.po_line_number,
                    material_id=pol.material_id,
                    quantity_received=to_decimal(qty_received),
                    uom=pol.uom,
                    quantity_accepted=to_decimal(qty_accepted),
                    quantity_rejected=to_decimal(qty_rejected),
                    rejection_reason=rejection_reason,
                    batch_number=batch,
                ))

            # Update PO status
            po.status = "FULLY_RECEIVED"
            for pol in po_lines:
                pol.gr_status = "COMPLETE"
                pol.actual_delivery_date = gr_date

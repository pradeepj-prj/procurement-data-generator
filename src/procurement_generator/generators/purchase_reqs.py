"""Generator for purchase requisitions."""
from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal

from ..models import PRHeader, PRLineItem
from ..utils import random_date, to_decimal, fake
from .base import BaseGenerator

DEPARTMENTS = ["Engineering", "Production", "Quality", "Logistics", "R&D", "Admin"]
PR_TYPES = ["STANDARD"] * 85 + ["URGENT"] * 10 + ["BLANKET"] * 5
PRIORITIES = ["LOW"] * 30 + ["MEDIUM"] * 45 + ["HIGH"] * 20 + ["CRITICAL"] * 5


class PurchaseReqGenerator(BaseGenerator):
    """Generates purchase requisitions with line items."""

    def generate(self) -> None:
        target = self.config.target_prs
        start = self.config.time_window_start
        end = self.config.time_window_end

        # Get materials that have plant extensions
        mat_plant_pairs = []
        for mpe in self.store.material_plant_extensions:
            mat = self.store.material_by_id(mpe.material_id)
            if mat:
                mat_plant_pairs.append((mat, mpe.plant_id))

        if not mat_plant_pairs:
            return

        pr_seq = 1
        line_seq = 0
        generated = 0

        while generated < target:
            pr_id = f"PR-{pr_seq:06d}"
            pr_seq += 1

            pr_date = random_date(start, end - timedelta(days=30))
            plant_id = random.choice(list(self.store.plant_ids()))

            # Cost center at this plant
            ccs = self.store.cost_centers_for_plant(plant_id)
            cc = random.choice(ccs) if ccs else None
            if not cc:
                continue

            pr_type = random.choice(PR_TYPES)
            priority = random.choice(PRIORITIES)

            # If URGENT, skew toward HIGH criticality materials
            if pr_type == "URGENT":
                priority = random.choice(["HIGH", "CRITICAL"])

            # Status distribution: 85% CONVERTED, 5% CANCELLED, 10% OPEN
            r = random.random()
            if r < 0.85:
                status = "CONVERTED"
            elif r < 0.90:
                status = "OPEN"
            elif r < 0.95:
                status = "APPROVED"
            else:
                status = "CANCELLED" if random.random() < 0.5 else "REJECTED"

            dept = random.choice(DEPARTMENTS)
            requester = fake.name()

            self.store.pr_headers.append(PRHeader(
                pr_id=pr_id,
                pr_date=pr_date,
                requester_name=requester,
                requester_department=dept,
                cost_center_id=cc.cost_center_id,
                plant_id=plant_id,
                pr_type=pr_type,
                status=status,
                priority=priority,
                notes=f"Auto-generated PR for {dept}" if random.random() < 0.2 else None,
            ))

            # Generate 1-4 line items per PR
            num_lines = random.randint(1, 4)
            # Filter materials available at this plant
            plant_mats = [(m, p) for m, p in mat_plant_pairs if p == plant_id]
            if not plant_mats:
                plant_mats = mat_plant_pairs

            selected = random.sample(plant_mats, min(num_lines, len(plant_mats)))

            for i, (mat, _) in enumerate(selected):
                line_num = (i + 1) * 10

                # Quantity
                if mat.standard_cost > Decimal("100"):
                    qty = random.randint(1, 50)
                elif mat.standard_cost > Decimal("10"):
                    qty = random.randint(10, 200)
                else:
                    qty = random.randint(50, 5000)

                delivery_date = pr_date + timedelta(days=mat.default_lead_time_days + random.randint(5, 30))
                if delivery_date > end:
                    delivery_date = end

                # Line status follows header
                if status == "CONVERTED":
                    line_status = "PO_CREATED"
                elif status == "CANCELLED" or status == "REJECTED":
                    line_status = "CANCELLED"
                elif status == "APPROVED":
                    line_status = "ASSIGNED"
                else:
                    line_status = "OPEN"

                # Purchasing group assignment
                pg = self.store.purch_group_for_category(mat.category_id)

                self.store.pr_line_items.append(PRLineItem(
                    pr_id=pr_id,
                    pr_line_number=line_num,
                    material_id=mat.material_id,
                    quantity=to_decimal(qty),
                    uom=mat.base_uom,
                    requested_delivery_date=delivery_date,
                    estimated_price=mat.standard_cost,
                    currency=mat.currency,
                    status=line_status,
                    assigned_purch_group_id=pg,
                ))

            generated += 1

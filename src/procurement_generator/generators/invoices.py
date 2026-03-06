"""Generator for invoices."""
from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal

from ..models import InvoiceHeader, InvoiceLineItem
from ..utils import to_decimal, payment_terms_to_days
from .base import BaseGenerator


class InvoiceGenerator(BaseGenerator):
    """Generates invoices with three-way match logic."""

    def generate(self) -> None:
        self._generate_seed_invoices()
        self._generate_bulk_invoices()

    def _generate_seed_invoices(self) -> None:
        """Generate invoices for scenario seeds."""
        ref = self.config.demo_reference_date

        # SEED-T01: Blocked Molex invoice with price variance
        # Find the PO for connector
        for po in self.store.po_headers:
            if po.vendor_id == "VND-MOLEX-SG":
                po_lines = [pol for pol in self.store.po_line_items
                           if pol.po_id == po.po_id and pol.material_id == "MAT-CON-24P"]
                if po_lines:
                    pol = po_lines[0]
                    gr = self._find_gr_for_po(po.po_id)
                    gr_line = self._find_gr_line(gr.gr_id if gr else None, po.po_id, pol.po_line_number) if gr else None

                    inv_date = (gr.gr_date if gr else po.po_date) + timedelta(days=random.randint(1, 5))
                    price_invoiced = to_decimal(5.24)  # 8% above PO price of 4.85
                    qty_invoiced = pol.quantity

                    self._create_invoice(
                        inv_seq=1, po=po, vendor_id=po.vendor_id,
                        inv_date=inv_date,
                        lines=[(pol, price_invoiced, qty_invoiced, gr, gr_line)],
                        force_match="PRICE_VARIANCE",
                    )
                    break

        # SEED-T02: Nidec invoices approaching payment due
        nidec_pos = [po for po in self.store.po_headers if po.vendor_id == "VND-NIDEC-JP"]
        inv_seq = 2
        count = 0
        for po in nidec_pos:
            if count >= 3:
                break
            po_lines = [pol for pol in self.store.po_line_items if pol.po_id == po.po_id]
            if not po_lines:
                continue
            gr = self._find_gr_for_po(po.po_id)
            if not gr:
                continue

            # Invoice date such that payment_due_date is within 5 days of ref date
            # payment_terms for Nidec is 2/10NET30, so due = inv_date + 30
            inv_date = ref - timedelta(days=random.randint(25, 28))

            all_lines = []
            for pol in po_lines:
                gr_line = self._find_gr_line(gr.gr_id, po.po_id, pol.po_line_number)
                all_lines.append((pol, pol.unit_price, pol.quantity, gr, gr_line))

            self._create_invoice(inv_seq, po, po.vendor_id, inv_date, all_lines, "FULL_MATCH")
            inv_seq += 1
            count += 1

    def _generate_bulk_invoices(self) -> None:
        """Generate invoices for GRs not yet invoiced."""
        target = self.config.target_invoices
        existing = len(self.store.invoice_headers)
        remaining = target - existing

        # Find POs with GRs that don't have invoices yet
        invoiced_pos = {inv.po_id for inv in self.store.invoice_headers}
        gr_po_ids = {gr.po_id for gr in self.store.gr_headers}
        eligible = [po for po in self.store.po_headers
                   if po.po_id in gr_po_ids and po.po_id not in invoiced_pos]
        random.shuffle(eligible)

        inv_seq = existing + 10
        for po in eligible:
            if len(self.store.invoice_headers) >= target:
                break

            po_lines = [pol for pol in self.store.po_line_items if pol.po_id == po.po_id]
            if not po_lines:
                continue

            gr = self._find_gr_for_po(po.po_id)
            if not gr:
                continue

            inv_date = gr.gr_date + timedelta(days=random.randint(1, 5))

            # Match status distribution
            r = random.random()
            if r < 0.82:
                match_type = "FULL_MATCH"
            elif r < 0.92:
                match_type = "PRICE_VARIANCE"
            elif r < 0.97:
                match_type = "QUANTITY_VARIANCE"
            else:
                match_type = "BOTH_VARIANCE"

            all_lines = []
            for pol in po_lines:
                gr_line = self._find_gr_line(gr.gr_id, po.po_id, pol.po_line_number)

                if match_type == "PRICE_VARIANCE" or match_type == "BOTH_VARIANCE":
                    price_var = random.uniform(0.03, 0.12) * (1 if random.random() > 0.3 else -1)
                    price_invoiced = to_decimal(float(pol.unit_price) * (1 + price_var))
                else:
                    price_invoiced = pol.unit_price

                if match_type == "QUANTITY_VARIANCE" or match_type == "BOTH_VARIANCE":
                    if gr_line:
                        qty_invoiced = gr_line.quantity_accepted * to_decimal(random.uniform(0.92, 1.08))
                    else:
                        qty_invoiced = pol.quantity * to_decimal(random.uniform(0.92, 1.08))
                else:
                    qty_invoiced = gr_line.quantity_accepted if gr_line else pol.quantity

                all_lines.append((pol, price_invoiced, qty_invoiced, gr, gr_line))

            self._create_invoice(inv_seq, po, po.vendor_id, inv_date, all_lines, match_type)
            inv_seq += 1

    def _create_invoice(
        self, inv_seq: int, po, vendor_id: str,
        inv_date, lines: list, force_match: str | None = None,
    ) -> None:
        inv_id = f"INV-{inv_seq:06d}"
        if any(inv.invoice_id == inv_id for inv in self.store.invoice_headers):
            return

        vendor = self.store.vendor_by_id(vendor_id)
        if not vendor:
            return

        received_date = inv_date + timedelta(days=random.randint(0, 5))
        pt_days = payment_terms_to_days(vendor.payment_terms)
        payment_due = inv_date + timedelta(days=pt_days)

        total_gross = Decimal("0")
        inv_lines = []
        has_price_var = False
        has_qty_var = False

        for i, (pol, price_inv, qty_inv, gr, gr_line) in enumerate(lines):
            net = to_decimal(float(price_inv) * float(qty_inv))
            total_gross += net

            price_variance = to_decimal(float(price_inv) - float(pol.unit_price))
            qty_variance = Decimal("0")
            if gr_line:
                qty_variance = to_decimal(float(qty_inv) - float(gr_line.quantity_accepted))

            # Check tolerance
            price_pct = abs(float(price_variance) / float(pol.unit_price)) if pol.unit_price else 0
            if price_pct > 0.02 or abs(float(price_variance)) > 0.50:
                has_price_var = True

            qty_pct = abs(float(qty_variance) / float(pol.quantity)) if pol.quantity else 0
            if qty_pct > 0.05:
                has_qty_var = True

            inv_lines.append(InvoiceLineItem(
                invoice_id=inv_id,
                invoice_line_number=(i + 1) * 10,
                po_id=po.po_id,
                po_line_number=pol.po_line_number,
                material_id=pol.material_id,
                quantity_invoiced=qty_inv,
                unit_price_invoiced=price_inv,
                net_amount=net,
                gr_id=gr.gr_id if gr else None,
                gr_line_number=gr_line.gr_line_number if gr_line else None,
                price_variance=price_variance,
                quantity_variance=qty_variance,
            ))

        # Determine match status
        if force_match:
            match_status = force_match
        elif has_price_var and has_qty_var:
            match_status = "BOTH_VARIANCE"
        elif has_price_var:
            match_status = "PRICE_VARIANCE"
        elif has_qty_var:
            match_status = "QUANTITY_VARIANCE"
        else:
            match_status = "FULL_MATCH"

        payment_block = match_status != "FULL_MATCH"
        block_reason = None
        if has_price_var:
            block_reason = "PRICE_MISMATCH"
        elif has_qty_var:
            block_reason = "QTY_MISMATCH"

        tax = to_decimal(float(total_gross) * 0.07)  # 7% GST
        total_net = total_gross + tax

        status = "MATCHED" if not payment_block else "EXCEPTION"

        vendor_inv_num = f"VIN-{vendor.display_code[:6]}-{inv_seq:04d}"

        self.store.invoice_headers.append(InvoiceHeader(
            invoice_id=inv_id,
            vendor_invoice_number=vendor_inv_num,
            invoice_date=inv_date,
            received_date=received_date,
            vendor_id=vendor_id,
            po_id=po.po_id,
            currency=po.currency,
            total_gross_amount=total_gross,
            tax_amount=tax,
            total_net_amount=total_net,
            status=status,
            match_status=match_status,
            payment_due_date=payment_due,
            payment_block=payment_block,
            block_reason=block_reason,
        ))
        self.store.invoice_line_items.extend(inv_lines)

        # Update PO line invoice status
        for pol_data in lines:
            pol = pol_data[0]
            pol.invoice_status = "COMPLETE"

    def _find_gr_for_po(self, po_id: str) -> GRHeader | None:
        from ..models import GRHeader
        for gr in self.store.gr_headers:
            if gr.po_id == po_id:
                return gr
        return None

    def _find_gr_line(self, gr_id: str | None, po_id: str, po_line_number: int):
        if not gr_id:
            return None
        for grl in self.store.gr_line_items:
            if grl.gr_id == gr_id and grl.po_id == po_id and grl.po_line_number == po_line_number:
                return grl
        return None

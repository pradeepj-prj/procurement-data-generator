"""Generator for payments."""
from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal

from ..models import Payment, PaymentInvoiceLink
from ..utils import to_decimal, has_early_discount
from .base import BaseGenerator


class PaymentGenerator(BaseGenerator):
    """Generates payments from approved invoices."""

    def generate(self) -> None:
        target = self.config.target_payments
        ref = self.config.demo_reference_date

        # Find invoices eligible for payment (matched, not blocked)
        eligible = [inv for inv in self.store.invoice_headers
                   if not inv.payment_block and inv.status in ("MATCHED", "APPROVED")]
        random.shuffle(eligible)

        pay_seq = 1
        failed_count = 0

        for inv in eligible:
            if pay_seq > target:
                break

            vendor = self.store.vendor_by_id(inv.vendor_id)
            if not vendor:
                continue

            # Payment timing distribution
            r = random.random()
            if r < 0.12:
                # Early payment
                days_offset = random.randint(-15, -5)
            elif r < 0.87:
                # On-time
                days_offset = random.randint(-3, 3)
            else:
                # Late
                days_offset = random.randint(5, 20)

            pay_date = inv.payment_due_date + timedelta(days=days_offset)
            if pay_date > ref:
                pay_date = ref - timedelta(days=random.randint(0, 5))
            if pay_date < inv.received_date:
                pay_date = inv.received_date + timedelta(days=1)

            # Early payment discount
            discount = Decimal("0")
            has_disc, disc_pct, disc_days = has_early_discount(vendor.payment_terms)
            if has_disc and (pay_date - inv.invoice_date).days <= disc_days:
                discount = to_decimal(float(inv.total_net_amount) * disc_pct / 100)

            amount = inv.total_net_amount - discount

            # Status
            if failed_count < 3 and random.random() < 0.03:
                status = random.choice(["FAILED", "REVERSED"])
                failed_count += 1
            else:
                status = "EXECUTED"

            pay_id = f"PAY-{pay_seq:06d}"
            pay_seq += 1

            self.store.payments.append(Payment(
                payment_id=pay_id,
                payment_date=pay_date,
                vendor_id=inv.vendor_id,
                payment_method=random.choice(["BANK_TRANSFER", "WIRE"]),
                currency=inv.currency,
                total_amount=amount,
                bank_account_ref=vendor.bank_account,
                payment_terms_applied=vendor.payment_terms,
                early_payment_discount=discount,
                status=status,
            ))

            self.store.payment_invoice_links.append(PaymentInvoiceLink(
                payment_id=pay_id,
                invoice_id=inv.invoice_id,
                amount_applied=amount,
            ))

            # Update invoice status
            if status == "EXECUTED":
                inv.status = "PAID"

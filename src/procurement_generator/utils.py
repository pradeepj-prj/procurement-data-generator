"""Utility functions: ID generators, date math, tier comparison, Faker setup."""
from __future__ import annotations

import random
import string
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from faker import Faker

# Seeded Faker instance
fake = Faker()

# Tier ordinal encoding for comparison
TIER_ORDER = {"PUBLIC": 1, "INTERNAL": 2, "RESTRICTED": 3}


def set_random_seed(seed: int) -> None:
    """Set random seed for reproducibility."""
    random.seed(seed)
    Faker.seed(seed)


# --- ID Generators ---

_counters: dict[str, int] = {}


def reset_counters() -> None:
    _counters.clear()


def next_id(prefix: str, width: int = 5) -> str:
    """Generate sequential ID like MAT-00001, VND-00002."""
    _counters[prefix] = _counters.get(prefix, 0) + 1
    return f"{prefix}-{_counters[prefix]:0{width}d}"


# --- Date Math ---

def add_business_days(start: date, days: int) -> date:
    """Add business days (Mon-Fri) to a date."""
    current = start
    added = 0
    step = 1 if days >= 0 else -1
    target = abs(days)
    while added < target:
        current += timedelta(days=step)
        if current.weekday() < 5:
            added += 1
    return current


def random_date(start: date, end: date) -> date:
    """Return a random date between start and end inclusive."""
    delta = (end - start).days
    if delta <= 0:
        return start
    return start + timedelta(days=random.randint(0, delta))


def days_between(d1: date, d2: date) -> int:
    return (d2 - d1).days


# --- Tier Comparison ---

def tier_value(tier: str | None) -> int:
    """Return ordinal value of confidentiality tier. NULL defaults to INTERNAL."""
    if tier is None:
        return TIER_ORDER["INTERNAL"]
    return TIER_ORDER.get(tier, TIER_ORDER["INTERNAL"])


def max_tier(*tiers: str | None) -> str:
    """Return the most restrictive tier."""
    mapping = {1: "PUBLIC", 2: "INTERNAL", 3: "RESTRICTED"}
    max_val = max(tier_value(t) for t in tiers)
    return mapping[max_val]


# --- Decimal Helpers ---

def to_decimal(value: float | int | str, places: int = 2) -> Decimal:
    """Convert to Decimal with specified precision."""
    q = Decimal(10) ** -places
    return Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP)


def random_decimal(low: float, high: float, places: int = 2) -> Decimal:
    """Random decimal in range."""
    return to_decimal(random.uniform(low, high), places)


# --- String Helpers ---

def generate_iban(country: str) -> str:
    """Generate a fake IBAN-like string."""
    digits = ''.join(random.choices(string.digits, k=18))
    return f"{country}{random.randint(10,99)}{digits}"


def generate_registration_id(country: str) -> str:
    """Generate a fake business registration number."""
    return f"{country}-{''.join(random.choices(string.digits, k=9))}"


def payment_terms_to_days(terms: str) -> int:
    """Convert payment terms string to number of days."""
    mapping = {"NET30": 30, "NET60": 60, "NET90": 90, "2/10NET30": 30}
    return mapping.get(terms, 30)


def has_early_discount(terms: str) -> tuple[bool, float, int]:
    """Return (has_discount, discount_pct, discount_days) from payment terms."""
    if terms == "2/10NET30":
        return True, 2.0, 10
    return False, 0.0, 0


def vendor_material_code(display_code: str) -> str:
    """Generate a vendor-side part number from display code."""
    parts = display_code.split("-")
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
    short = parts[0][:4] if parts else display_code[:4]
    return f"{short}-{suffix}"

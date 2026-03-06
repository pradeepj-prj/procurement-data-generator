"""Generator for vendor master, vendor categories, addresses, and contacts."""
from __future__ import annotations

import random
from decimal import Decimal

from ..models import VendorMaster, VendorCategory, VendorAddress, VendorContact
from ..utils import to_decimal, generate_iban, fake, next_id
from .base import BaseGenerator

VENDOR_TYPE_WEIGHTS = [
    ("OEM", 40), ("DISTRIBUTOR", 25), ("CONTRACT_MFG", 15),
    ("LOGISTICS", 10), ("SERVICE", 10),
]

COUNTRIES = ["JP", "CN", "KR", "TW", "SG", "MY", "VN", "DE", "US", "TH"]
COUNTRY_WEIGHTS = [15, 25, 8, 10, 12, 10, 5, 5, 5, 5]  # APAC-heavy

INCOTERMS = ["FOB", "CIF", "DDP", "EXW", "FCA"]
PAYMENT_TERMS = ["NET30", "NET60", "NET90", "2/10NET30"]
CURRENCIES = {
    "JP": "JPY", "CN": "CNY", "KR": "KRW", "TW": "TWD",
    "SG": "SGD", "MY": "MYR", "VN": "VND", "DE": "EUR",
    "US": "USD", "TH": "THB",
}

# Map vendor types to likely supported category top-levels
TYPE_CATEGORIES = {
    "OEM": ["ELEC", "MOTN", "POWR"],
    "DISTRIBUTOR": ["ELEC", "MECH", "MOTN"],
    "CONTRACT_MFG": ["MECH", "ELEC"],
    "LOGISTICS": ["SRVC"],
    "SERVICE": ["SRVC", "MRO"],
}

CONTACT_ROLES = ["Account Manager", "Sales Representative", "Quality Contact", "Logistics Contact"]


class VendorGenerator(BaseGenerator):
    """Generates seed + bulk vendors with categories, addresses, and contacts."""

    def generate(self) -> None:
        self._load_seed_vendors()
        self._generate_bulk_vendors()
        self._generate_vendor_categories()
        self._generate_addresses()
        self._generate_contacts()

    def _load_seed_vendors(self) -> None:
        seed_le = self.seeds.get("seed_legal_entities", {})
        alias_groups = {ag["alias_group_id"]: ag for ag in seed_le.get("alias_groups", [])}

        seed_vnds = self.seeds.get("seed_vendors", {}).get("vendors", [])
        for sv in seed_vnds:
            # Find matching legal entity
            le_id = None
            for le in self.store.legal_entities:
                if sv["vendor_id"] in [v_id for ag in seed_le.get("alias_groups", [])
                                        for v_id in ag.get("vendor_ids", [])
                                        if ag["legal_entity_id"] == le.legal_entity_id]:
                    le_id = le.legal_entity_id
                    break
            if le_id is None:
                # Try direct LE match
                for le_data in seed_le.get("legal_entities", []):
                    if sv["vendor_id"] in le_data.get("vendor_ids", []):
                        le_id = le_data["legal_entity_id"]
                        break
            if le_id is None:
                le_id = self.store.legal_entities[0].legal_entity_id if self.store.legal_entities else "LE-00001"

            self.store.vendors.append(VendorMaster(
                vendor_id=sv["vendor_id"],
                display_code=sv["display_code"],
                legal_entity_id=le_id,
                vendor_name=sv["vendor_name"],
                country=sv["country"],
                vendor_type=sv["vendor_type"],
                supported_categories=sv["supported_categories"],
                preferred_flag=sv.get("preferred_flag", False),
                incoterms_default=sv.get("incoterms_default", "FOB"),
                payment_terms=sv.get("payment_terms", "NET30"),
                currency=sv.get("currency", "USD"),
                lead_time_days_typical=sv.get("lead_time_days_typical", 21),
                on_time_delivery_rate=to_decimal(sv.get("on_time_delivery_rate", 90)),
                quality_score=sv.get("quality_score", 80),
                risk_score=sv.get("risk_score", 50),
                esg_score=sv.get("esg_score"),
                status=sv.get("status", "ACTIVE"),
                bank_account=generate_iban(sv["country"]),
                confidentiality_tier=sv.get("confidentiality_tier", "INTERNAL"),
                alias_group=sv.get("alias_group"),
            ))

    def _generate_bulk_vendors(self) -> None:
        target = self.config.target_vendors
        existing = len(self.store.vendors)
        remaining = target - existing

        used_ids = {v.vendor_id for v in self.store.vendors}
        used_display = {v.display_code for v in self.store.vendors}
        le_list = list(self.store.legal_entities)
        seed_le_ids = {v.legal_entity_id for v in self.store.vendors}

        # Track counts for distribution
        blocked_count = sum(1 for v in self.store.vendors if v.status == "BLOCKED")
        conditional_count = sum(1 for v in self.store.vendors if v.status == "CONDITIONAL")

        seq = 100

        for i in range(remaining):
            seq += 1
            vnd_id = f"VND-{seq:05d}"
            while vnd_id in used_ids:
                seq += 1
                vnd_id = f"VND-{seq:05d}"
            used_ids.add(vnd_id)

            # Vendor type
            vtype = random.choices(
                [t[0] for t in VENDOR_TYPE_WEIGHTS],
                [t[1] for t in VENDOR_TYPE_WEIGHTS],
            )[0]

            # Country
            country = random.choices(COUNTRIES, COUNTRY_WEIGHTS)[0]

            # Company name
            name = fake.company()
            display = f"{name.split()[0].upper()[:8]}-{country}"
            while display in used_display:
                name = fake.company()
                display = f"{name.split()[0].upper()[:8]}-{country}"
            used_display.add(display)

            # Find or assign a legal entity
            unused_les = [le for le in le_list
                          if le.legal_entity_id not in seed_le_ids
                          and le.country_of_incorporation == country]
            if unused_les:
                le = unused_les[0]
                seed_le_ids.add(le.legal_entity_id)
            else:
                # Use any unassigned LE
                unused_les = [le for le in le_list if le.legal_entity_id not in seed_le_ids]
                if unused_les:
                    le = unused_les[0]
                    seed_le_ids.add(le.legal_entity_id)
                else:
                    le = random.choice(le_list)

            # Supported categories
            cat_options = TYPE_CATEGORIES.get(vtype, ["ELEC"])
            num_cats = random.randint(1, min(3, len(cat_options)))
            cats = random.sample(cat_options, num_cats)
            supported = ",".join(cats)

            # Status distribution
            if blocked_count < 3 and random.random() < 0.03:
                status = "BLOCKED"
                blocked_count += 1
            elif conditional_count < 5 and random.random() < 0.05:
                status = "CONDITIONAL"
                conditional_count += 1
            else:
                status = "ACTIVE"

            # Scores
            quality = random.randint(60, 98)
            otd = to_decimal(random.uniform(75.0, 99.0))
            esg = random.randint(40, 95) if random.random() > 0.2 else None

            ml = self.config.ml_signal
            if ml.enabled:
                corr = ml.vendor_score_correlation
                noise_std = ml.vendor_score_noise_std
                correlated_risk = 100 - quality + random.gauss(0, noise_std)
                independent_risk = random.randint(10, 85)
                risk = int(max(10, min(85, corr * correlated_risk + (1 - corr) * independent_risk)))
            else:
                risk = random.randint(10, 85)

            if status == "CONDITIONAL":
                quality = random.randint(55, 72)
                otd = to_decimal(random.uniform(70.0, 82.0))

            if status == "BLOCKED":
                quality = random.randint(40, 60)

            tier = "INTERNAL"
            if random.random() < 0.08:
                tier = "RESTRICTED"
            elif random.random() < 0.15:
                tier = "PUBLIC"

            self.store.vendors.append(VendorMaster(
                vendor_id=vnd_id,
                display_code=display,
                legal_entity_id=le.legal_entity_id,
                vendor_name=name,
                country=country,
                vendor_type=vtype,
                supported_categories=supported,
                preferred_flag=random.random() < 0.4,
                incoterms_default=random.choice(INCOTERMS),
                payment_terms=random.choice(PAYMENT_TERMS),
                currency=CURRENCIES.get(country, "USD"),
                lead_time_days_typical=random.randint(5, 60),
                on_time_delivery_rate=otd,
                quality_score=quality,
                risk_score=risk,
                esg_score=esg,
                status=status,
                bank_account=generate_iban(country),
                confidentiality_tier=tier,
                alias_group=None,
            ))

    def _generate_vendor_categories(self) -> None:
        """Create vendor_category junction table entries."""
        # Get category hierarchy for mapping
        cat_map: dict[str, list[str]] = {}  # top-level -> list of subcategory IDs
        for cat in self.store.categories:
            if cat.level == 2:
                top = cat.parent_category_id
                cat_map.setdefault(top, []).append(cat.category_id)

        for vendor in self.store.vendors:
            # Check if seed vendor has explicit categories
            seed_vnds = self.seeds.get("seed_vendors", {}).get("vendors", [])
            seed_cats = None
            for sv in seed_vnds:
                if sv["vendor_id"] == vendor.vendor_id:
                    seed_cats = sv.get("vendor_categories", [])
                    break

            if seed_cats:
                for cat_id in seed_cats:
                    self.store.vendor_categories.append(VendorCategory(
                        vendor_id=vendor.vendor_id,
                        category_id=cat_id,
                    ))
            else:
                # Map from supported_categories (top-level IDs)
                for top_cat in vendor.supported_categories.split(","):
                    top_cat = top_cat.strip()
                    subcats = cat_map.get(top_cat, [])
                    if subcats:
                        # Map to 1-3 subcategories
                        n = min(len(subcats), random.randint(1, 3))
                        for sc in random.sample(subcats, n):
                            self.store.vendor_categories.append(VendorCategory(
                                vendor_id=vendor.vendor_id,
                                category_id=sc,
                            ))
                    else:
                        # Map to top-level itself
                        self.store.vendor_categories.append(VendorCategory(
                            vendor_id=vendor.vendor_id,
                            category_id=top_cat,
                        ))

    def _generate_addresses(self) -> None:
        """Generate 1-2 addresses per vendor using Faker."""
        for vendor in self.store.vendors:
            for addr_type in ["REGISTERED", "SHIPPING"]:
                self.store.vendor_addresses.append(VendorAddress(
                    vendor_id=vendor.vendor_id,
                    address_type=addr_type,
                    street=fake.street_address(),
                    city=fake.city(),
                    state_province=fake.state() if vendor.country == "US" else fake.city(),
                    country=vendor.country,
                    postal_code=fake.postcode(),
                ))

    def _generate_contacts(self) -> None:
        """Generate 1-3 contacts per vendor."""
        contact_seq = 1
        for vendor in self.store.vendors:
            num_contacts = random.randint(1, 3)
            for _ in range(num_contacts):
                self.store.vendor_contacts.append(VendorContact(
                    contact_id=f"CON-{contact_seq:05d}",
                    vendor_id=vendor.vendor_id,
                    contact_name=fake.name(),
                    email=fake.email(),
                    phone=fake.phone_number(),
                    role=random.choice(CONTACT_ROLES),
                ))
                contact_seq += 1

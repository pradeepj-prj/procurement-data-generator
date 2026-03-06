"""Generator for legal entities."""
from __future__ import annotations

import random

from ..models import LegalEntity
from ..utils import generate_registration_id, fake
from .base import BaseGenerator

COUNTRIES = ["JP", "CN", "KR", "TW", "SG", "MY", "VN", "DE", "US", "TH"]


class LegalEntityGenerator(BaseGenerator):
    """Generates seed + bulk legal entities."""

    def generate(self) -> None:
        self._load_seed_entities()
        self._generate_bulk_entities()

    def _load_seed_entities(self) -> None:
        seed_le = self.seeds.get("seed_legal_entities", {})
        for le in seed_le.get("legal_entities", []):
            self.store.legal_entities.append(LegalEntity(
                legal_entity_id=le["legal_entity_id"],
                legal_name=le["legal_name"],
                country_of_incorporation=le["country_of_incorporation"],
                registration_id=le["registration_id"],
            ))

    def _generate_bulk_entities(self) -> None:
        target = self.config.target_legal_entities
        existing = len(self.store.legal_entities)
        remaining = target - existing

        used_ids = {le.legal_entity_id for le in self.store.legal_entities}
        seq = len(used_ids) + 1

        for i in range(remaining):
            le_id = f"LE-{seq + i:05d}"
            while le_id in used_ids:
                i += 1
                le_id = f"LE-{seq + i:05d}"
            used_ids.add(le_id)

            country = random.choice(COUNTRIES)
            name = fake.company()
            # Add country-appropriate suffix
            suffixes = {
                "JP": "Co., Ltd.", "CN": "Co., Ltd.", "KR": "Co., Ltd.",
                "TW": "Corporation", "SG": "Pte Ltd", "MY": "Sdn Bhd",
                "VN": "JSC", "DE": "GmbH", "US": "Inc.", "TH": "Co., Ltd."
            }
            suffix = suffixes.get(country, "Ltd.")
            if not name.endswith(suffix):
                name = f"{name} {suffix}"

            self.store.legal_entities.append(LegalEntity(
                legal_entity_id=le_id,
                legal_name=name,
                country_of_incorporation=country,
                registration_id=generate_registration_id(country),
            ))

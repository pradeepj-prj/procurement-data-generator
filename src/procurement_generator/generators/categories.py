"""Generator for category hierarchy."""
from __future__ import annotations

from ..models import CategoryHierarchy
from .base import BaseGenerator


class CategoryGenerator(BaseGenerator):
    """Loads the full category hierarchy from seed YAML."""

    def generate(self) -> None:
        cat_data = self.seeds.get("category_hierarchy", {})
        for cat in cat_data.get("categories", []):
            self.store.categories.append(CategoryHierarchy(
                category_id=cat["category_id"],
                category_name=cat["category_name"],
                level=cat["level"],
                parent_category_id=cat.get("parent_category_id"),
                owner_purch_group_id=cat.get("owner_purch_group_id"),
            ))

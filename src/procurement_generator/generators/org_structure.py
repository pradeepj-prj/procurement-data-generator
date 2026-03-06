"""Generator for organizational structure entities."""
from __future__ import annotations

from ..models import (
    CompanyCode, PurchasingOrg, PurchasingGroup, PurchasingGroupCategory,
    Plant, StorageLocation, CostCenter,
)
from .base import BaseGenerator


class OrgStructureGenerator(BaseGenerator):
    """Loads org structure from seed YAML (all authored, not generated)."""

    def generate(self) -> None:
        org = self.seeds.get("org_structure", {})

        # Company code
        cc = org.get("company", {})
        self.store.company_codes.append(CompanyCode(
            company_code=cc["company_code"],
            company_name=cc["company_name"],
            country=cc["country"],
            currency=cc["currency"],
        ))

        # Purchasing orgs
        for po in org.get("purchasing_orgs", []):
            self.store.purchasing_orgs.append(PurchasingOrg(
                purch_org_id=po["purch_org_id"],
                purch_org_name=po["purch_org_name"],
                company_code=po["company_code"],
            ))

        # Purchasing groups
        for pg in org.get("purchasing_groups", []):
            self.store.purchasing_groups.append(PurchasingGroup(
                purch_group_id=pg["purch_group_id"],
                purch_group_name=pg["purch_group_name"],
                purch_org_id=pg["purch_org_id"],
                display_code=pg["display_code"],
            ))

        # Plants
        for p in org.get("plants", []):
            self.store.plants.append(Plant(
                plant_id=p["plant_id"],
                plant_name=p["plant_name"],
                country=p["country"],
                city=p["city"],
                function=p["function"],
                company_code=p["company_code"],
            ))

        # Storage locations
        for sl in org.get("storage_locations", []):
            self.store.storage_locations.append(StorageLocation(
                storage_loc_id=sl["storage_loc_id"],
                plant_id=sl["plant_id"],
                storage_loc_name=sl["storage_loc_name"],
                storage_type=sl["storage_type"],
            ))

        # Cost centers
        for cc_data in org.get("cost_centers", []):
            self.store.cost_centers.append(CostCenter(
                cost_center_id=cc_data["cost_center_id"],
                cost_center_name=cc_data["cost_center_name"],
                plant_id=cc_data["plant_id"],
                department=cc_data["department"],
            ))

        # PG-Category mapping
        for pgc in org.get("pg_category_mapping", []):
            self.store.pg_category_mappings.append(PurchasingGroupCategory(
                purch_group_id=pgc["purch_group_id"],
                category_id=pgc["category_id"],
            ))

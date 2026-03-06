"""Generator for material master and plant extensions."""
from __future__ import annotations

import random
from decimal import Decimal

from ..models import MaterialMaster, MaterialPlantExtension
from ..utils import next_id, to_decimal, fake
from .base import BaseGenerator

# Category distribution targets (A7) as fractions
CATEGORY_DISTRIBUTION = {
    "ELEC": 0.30,
    "MOTN": 0.20,
    "POWR": 0.15,
    "MECH": 0.10,
    "PACK": 0.10,
    "SRVC": 0.10,
    "MRO": 0.05,
}

# Material type weights per top-level category
TYPE_BY_CATEGORY = {
    "ELEC": ["COMPONENT"] * 8 + ["ASSEMBLY"] * 2,
    "MOTN": ["COMPONENT"] * 7 + ["ASSEMBLY"] * 3,
    "POWR": ["COMPONENT"] * 6 + ["ASSEMBLY"] * 4,
    "MECH": ["RAW"] * 5 + ["COMPONENT"] * 5,
    "PACK": ["RAW"] * 8 + ["COMPONENT"] * 2,
    "SRVC": ["SERVICE"] * 10,
    "MRO": ["MRO"] * 10,
}

# Criticality distribution: 70% LOW, 20% MEDIUM, 10% HIGH
CRITICALITY_WEIGHTS = [("LOW", 70), ("MEDIUM", 20), ("HIGH", 10)]

# Reason codes for HIGH criticality
HIGH_REASON_CODES = ["SAFETY", "SUPPLY_RISK", "LEAD_TIME", "REGULATORY"]

# UOM by category/type
UOM_MAP = {
    "SERVICE": "HR",
    "RAW": random.choice(["EA", "KG", "M"]),
}

# Plant affinity rules (A6) - which top-level categories go to which plants
PLANT_AFFINITY = {
    "ELEC-SENS-LIDAR2D": ["SG01", "MY01"],
    "ELEC-SENS-CAM3D": ["SG01", "MY01"],
    "ELEC-COMP-SBC": ["SG01", "MY01"],
    "ELEC-COMP-FPGA": ["SG01", "MY01"],
    "POWR-BAT-CELL": ["MY01"],
    "POWR-BAT-PACK": ["MY01"],
    "POWR-BAT-BMS": ["MY01"],
    "MECH-STR-SHEET": ["MY01", "VN01"],
    "MECH-STR-EXTR": ["MY01", "VN01"],
    "MECH-STR-BRACKET": ["MY01", "VN01"],
    "PACK-PRI-CARTON": ["MY01", "VN01"],
    "PACK-PRI-FOAM": ["MY01", "VN01"],
    "PACK-SEC-PALLET": ["MY01", "VN01"],
    "PACK-LBL-PRODUCT": ["MY01", "VN01"],
    "PACK-LBL-SHIP": ["MY01", "VN01"],
    "SRVC-TECH-CALIB": ["SG01"],
    "SRVC-LOG-FREIGHT": ["SG01", "MY01", "VN01"],
    "SRVC-LOG-CUSTOMS": ["SG01", "MY01", "VN01"],
    "SRVC-SW-LICENSE": ["SG01", "MY01"],
    "SRVC-TECH-TEST": ["SG01", "MY01"],
}

# Default plant affinity by top-level category
DEFAULT_AFFINITY = {
    "ELEC": {"SG01": 0.25, "MY01": 0.80, "VN01": 0.10},
    "MOTN": {"SG01": 0.15, "MY01": 0.80, "VN01": 0.30},
    "POWR": {"SG01": 0.15, "MY01": 0.80, "VN01": 0.05},
    "MECH": {"SG01": 0.10, "MY01": 0.70, "VN01": 0.50},
    "PACK": {"SG01": 0.05, "MY01": 0.80, "VN01": 0.60},
    "SRVC": {"SG01": 0.30, "MY01": 0.50, "VN01": 0.20},
    "MRO": {"SG01": 0.30, "MY01": 0.50, "VN01": 0.30},
}

# Descriptive templates for bulk material names per commodity
MATERIAL_TEMPLATES = {
    "ELEC-COMP-MCU": ["Microcontroller {}", "MCU {} Series", "ARM Cortex-M {} Controller"],
    "ELEC-COMP-SBC": ["Single Board Computer {}", "Embedded SBC Module {}"],
    "ELEC-COMP-FPGA": ["FPGA Module {}", "Programmable Logic Module {}"],
    "ELEC-PCB-BARE": ["Bare PCB {} Layer", "PCB Blank {} Series"],
    "ELEC-PCB-PCBA": ["PCBA Assembly {}", "PCB Assembly Module {}"],
    "ELEC-SENS-LIDAR2D": ["2D LiDAR Sensor {}", "Laser Range Finder {}"],
    "ELEC-SENS-CAM3D": ["3D Depth Camera {}", "Stereo Vision Camera {}"],
    "ELEC-SENS-IMU": ["IMU {} Axis", "Inertial Measurement Unit {}"],
    "ELEC-SENS-ENCODER": ["Rotary Encoder {} PPR", "Wheel Encoder {}"],
    "ELEC-SENS-ULTRA": ["Ultrasonic Sensor {}", "Proximity Sensor {}"],
    "ELEC-SENS-SAFETY": ["Safety Sensor {}", "Emergency Stop Sensor {}"],
    "ELEC-CONN-WIFI": ["WiFi Module {}", "BT/WiFi Combo Module {}"],
    "ELEC-CONN-ETH": ["Ethernet Module {}", "Industrial Ethernet {}"],
    "ELEC-CONN-IO": ["IO Module {}", "Digital IO Expander {}"],
    "MOTN-MOT-BLDC": ["BLDC Motor {}W", "Brushless DC Motor {}"],
    "MOTN-MOT-STEP": ["Stepper Motor {} NEMA", "Step Motor {}"],
    "MOTN-DRV-GBOX": ["Planetary Gearbox {}:1", "Gearbox Reducer {}"],
    "MOTN-DRV-WHEEL": ["Drive Wheel {} mm", "Traction Wheel {}"],
    "MOTN-DRV-CASTER": ["Caster Wheel {} mm", "Swivel Caster {}"],
    "MOTN-DRV-BEARING": ["Ball Bearing {} mm", "Precision Bearing {}"],
    "MOTN-ACT-LINEAR": ["Linear Actuator {} mm", "Electric Cylinder {}"],
    "MOTN-ACT-GRIP": ["Gripper Assembly {}", "Pneumatic Gripper {}"],
    "MOTN-TRN-BELT": ["Timing Belt {} mm", "Drive Belt {}"],
    "POWR-BAT-CELL": ["Battery Cell {} mAh", "Li-ion Cell {}"],
    "POWR-BAT-PACK": ["Battery Pack {}V", "Li-ion Pack {}"],
    "POWR-BAT-BMS": ["BMS Module {}", "Battery Management Board {}"],
    "POWR-CHG-UNIT": ["Charger Unit {}A", "Intelligent Charger {}"],
    "POWR-CHG-CONTACT": ["Charging Contact Set {}", "Charge Pad Connector {}"],
    "POWR-CNV-DCDC": ["DC-DC Converter {}", "Voltage Regulator {}"],
    "POWR-CNV-PDU": ["Power Distribution Unit {}", "PDU Module {}"],
    "MECH-STR-SHEET": ["Sheet Metal Part {}", "Steel Plate {} mm"],
    "MECH-STR-EXTR": ["Aluminum Extrusion {} mm", "T-Slot Profile {}"],
    "MECH-STR-BRACKET": ["Mounting Bracket {}", "L-Bracket {}"],
    "MECH-FST-SCREW": ["M{} Socket Head Screw", "Machine Screw M{}"],
    "MECH-FST-NUT": ["M{} Hex Nut", "Flange Nut M{}"],
    "MECH-WIR-CABLE": ["Cable Assembly {}", "Wire Harness {} pin"],
    "PACK-PRI-CARTON": ["Carton Box {} mm", "Shipping Box {}"],
    "PACK-PRI-FOAM": ["Foam Insert {}", "PE Foam Sheet {}"],
    "PACK-SEC-PALLET": ["Pallet {} mm", "Stretch Wrap Roll {}"],
    "PACK-LBL-PRODUCT": ["Product Label {}", "Barcode Label {}"],
    "PACK-LBL-SHIP": ["Shipping Label {}", "Address Label {}"],
    "SRVC-TECH-CALIB": ["Calibration Service {}", "Sensor Calibration {}"],
    "SRVC-TECH-TEST": ["Testing Service {}", "Certification Service {}"],
    "SRVC-LOG-FREIGHT": ["Freight Service {}", "Shipping Service {}"],
    "SRVC-LOG-CUSTOMS": ["Customs Brokerage {}", "Import Clearance {}"],
    "SRVC-SW-LICENSE": ["Software License {}", "Annual Subscription {}"],
    "MRO-FAC-CLEAN": ["Cleaning Agent {}", "Industrial Cleaner {}"],
    "MRO-FAC-SAFETY": ["Safety Glasses {}", "Work Gloves {}"],
    "MRO-TOOL-HAND": ["Hand Tool Set {}", "Screwdriver Set {}"],
    "MRO-TOOL-POWER": ["Power Drill {}", "Impact Wrench {}"],
}

# Standard cost ranges per commodity
COST_RANGES = {
    "ELEC-COMP-MCU": (3, 25), "ELEC-COMP-SBC": (100, 800), "ELEC-COMP-FPGA": (50, 400),
    "ELEC-PCB-BARE": (2, 15), "ELEC-PCB-PCBA": (20, 200),
    "ELEC-SENS-LIDAR2D": (80, 300), "ELEC-SENS-CAM3D": (100, 500),
    "ELEC-SENS-IMU": (5, 30), "ELEC-SENS-ENCODER": (3, 20),
    "ELEC-SENS-ULTRA": (2, 15), "ELEC-SENS-SAFETY": (15, 80),
    "ELEC-CONN-WIFI": (5, 25), "ELEC-CONN-ETH": (8, 35), "ELEC-CONN-IO": (10, 40),
    "MOTN-MOT-BLDC": (40, 250), "MOTN-MOT-STEP": (15, 80),
    "MOTN-DRV-GBOX": (30, 150), "MOTN-DRV-WHEEL": (10, 60),
    "MOTN-DRV-CASTER": (5, 30), "MOTN-DRV-BEARING": (2, 20),
    "MOTN-ACT-LINEAR": (30, 150), "MOTN-ACT-GRIP": (50, 300),
    "MOTN-TRN-BELT": (3, 20),
    "POWR-BAT-CELL": (2, 10), "POWR-BAT-PACK": (200, 1200), "POWR-BAT-BMS": (50, 200),
    "POWR-CHG-UNIT": (40, 200), "POWR-CHG-CONTACT": (5, 25),
    "POWR-CNV-DCDC": (10, 60), "POWR-CNV-PDU": (30, 120),
    "MECH-STR-SHEET": (5, 40), "MECH-STR-EXTR": (3, 25), "MECH-STR-BRACKET": (1, 10),
    "MECH-FST-SCREW": (0.02, 0.50), "MECH-FST-NUT": (0.01, 0.30),
    "MECH-WIR-CABLE": (1, 15),
    "PACK-PRI-CARTON": (0.50, 5), "PACK-PRI-FOAM": (0.30, 4),
    "PACK-SEC-PALLET": (5, 20), "PACK-LBL-PRODUCT": (0.02, 0.20), "PACK-LBL-SHIP": (0.03, 0.25),
    "SRVC-TECH-CALIB": (80, 300), "SRVC-TECH-TEST": (100, 500),
    "SRVC-LOG-FREIGHT": (50, 500), "SRVC-LOG-CUSTOMS": (100, 400),
    "SRVC-SW-LICENSE": (200, 5000),
    "MRO-FAC-CLEAN": (5, 30), "MRO-FAC-SAFETY": (3, 50),
    "MRO-TOOL-HAND": (10, 80), "MRO-TOOL-POWER": (50, 300),
}

# Confidentiality tier mapping (A4.4)
def _material_tier(category_id: str, hazmat: bool, criticality: str) -> str:
    if hazmat:
        return "RESTRICTED"
    top = category_id.split("-")[0]
    if top in ("SRVC", "PACK"):
        return "PUBLIC"
    if top == "MRO":
        return "PUBLIC"
    if criticality == "HIGH":
        return "INTERNAL"
    return "INTERNAL"


class MaterialGenerator(BaseGenerator):
    """Generates seed and bulk materials with plant extensions."""

    def generate(self) -> None:
        self._load_seed_materials()
        self._generate_bulk_materials()
        self._generate_plant_extensions()

    def _load_seed_materials(self) -> None:
        seed_mats = self.seeds.get("seed_materials", {}).get("materials", [])
        for sm in seed_mats:
            mat = MaterialMaster(
                material_id=sm["material_id"],
                display_code=sm["display_code"],
                description=sm["description"],
                material_type=sm["material_type"],
                category_id=sm["category_id"],
                base_uom=sm["base_uom"],
                standard_cost=to_decimal(sm["standard_cost"]),
                currency=sm.get("currency", "USD"),
                criticality=sm["criticality"],
                criticality_reason_code=sm.get("criticality_reason_code"),
                hazmat_flag=sm.get("hazmat_flag", False),
                default_lead_time_days=sm.get("default_lead_time_days", 14),
                make_or_buy=sm.get("make_or_buy", "BUY"),
                confidentiality_tier=sm.get("confidentiality_tier", "INTERNAL"),
            )
            self.store.materials.append(mat)

    def _generate_bulk_materials(self) -> None:
        target = self.config.target_materials
        existing = len(self.store.materials)
        remaining = target - existing

        # Get leaf categories grouped by top-level
        cat_to_top = {}
        for cat in self.store.categories:
            if cat.level == 3:
                top = self.store.category_top_level(cat.category_id)
                cat_to_top[cat.category_id] = top

        # Group leaf categories by top-level
        top_to_leaves: dict[str, list[str]] = {}
        for leaf_id, top_id in cat_to_top.items():
            top_to_leaves.setdefault(top_id, []).append(leaf_id)

        # Calculate how many materials per top-level category
        existing_per_top: dict[str, int] = {}
        for m in self.store.materials:
            top = self.store.category_top_level(m.category_id)
            existing_per_top[top] = existing_per_top.get(top, 0) + 1

        # Track generated display codes to ensure uniqueness
        used_display_codes = {m.display_code for m in self.store.materials}
        used_ids = {m.material_id for m in self.store.materials}
        seq = 100  # Start bulk IDs from MAT-00100

        for top_cat, fraction in CATEGORY_DISTRIBUTION.items():
            target_for_top = int(target * fraction)
            already = existing_per_top.get(top_cat, 0)
            to_generate = max(0, target_for_top - already)

            leaves = top_to_leaves.get(top_cat, [])
            if not leaves:
                continue

            for i in range(to_generate):
                leaf = random.choice(leaves)
                seq += 1
                mat_id = f"MAT-{seq:05d}"
                while mat_id in used_ids:
                    seq += 1
                    mat_id = f"MAT-{seq:05d}"
                used_ids.add(mat_id)

                # Generate display code
                templates = MATERIAL_TEMPLATES.get(leaf, ["Part {}"])
                template = random.choice(templates)
                variant = random.randint(1, 999)
                display = template.format(variant)
                # Make display code from it
                dc = display.upper().replace(" ", "-").replace("/", "-")[:25] + f"-{seq % 1000:03d}"
                while dc in used_display_codes:
                    variant += 1
                    dc = template.format(variant).upper().replace(" ", "-").replace("/", "-")[:25] + f"-{seq % 1000:03d}"
                used_display_codes.add(dc)

                # Material type
                type_options = TYPE_BY_CATEGORY.get(top_cat, ["COMPONENT"])
                mat_type = random.choice(type_options)

                # Criticality
                crit = random.choices(
                    [c[0] for c in CRITICALITY_WEIGHTS],
                    [c[1] for c in CRITICALITY_WEIGHTS],
                )[0]
                reason = None
                if crit == "HIGH":
                    reason = random.choice(HIGH_REASON_CODES)

                # Cost
                cost_range = COST_RANGES.get(leaf, (5, 100))
                cost = to_decimal(random.uniform(*cost_range))

                # UOM
                if mat_type == "SERVICE":
                    uom = "HR"
                elif leaf.startswith("MECH-FST") or leaf.startswith("PACK-LBL"):
                    uom = random.choice(["EA", "BOX"])
                elif leaf.startswith("MECH-STR"):
                    uom = random.choice(["EA", "KG"])
                else:
                    uom = "EA"

                # Hazmat
                hazmat = leaf in ("POWR-BAT-CELL", "POWR-BAT-PACK") and random.random() < 0.7

                # Lead time
                if mat_type == "SERVICE":
                    lt = random.randint(1, 10)
                elif top_cat == "ELEC":
                    lt = random.randint(10, 60)
                elif top_cat in ("PACK", "MRO"):
                    lt = random.randint(3, 14)
                else:
                    lt = random.randint(7, 35)

                tier = _material_tier(leaf, hazmat, crit)

                mat = MaterialMaster(
                    material_id=mat_id,
                    display_code=dc,
                    description=display,
                    material_type=mat_type,
                    category_id=leaf,
                    base_uom=uom,
                    standard_cost=cost,
                    currency="USD",
                    criticality=crit,
                    criticality_reason_code=reason,
                    hazmat_flag=hazmat,
                    default_lead_time_days=lt,
                    make_or_buy="BUY",
                    confidentiality_tier=tier,
                )
                self.store.materials.append(mat)

    def _generate_plant_extensions(self) -> None:
        """Create material-plant extensions respecting affinity rules (A6)."""
        # First handle seed materials with explicit plant assignments
        seed_mats = self.seeds.get("seed_materials", {}).get("materials", [])
        seed_plant_map: dict[str, list[str]] = {}
        for sm in seed_mats:
            seed_plant_map[sm["material_id"]] = sm.get("plants", ["MY01"])

        for mat in self.store.materials:
            if mat.material_id in seed_plant_map:
                plants = seed_plant_map[mat.material_id]
            else:
                plants = self._determine_plants(mat)

            for plant_id in plants:
                # Determine realistic reorder/lot/min values
                if mat.material_type == "SERVICE":
                    rop, lot, moq = 0, 1, 1
                elif mat.standard_cost > Decimal("100"):
                    rop = random.randint(5, 30)
                    lot = random.randint(10, 50)
                    moq = random.randint(5, 20)
                elif mat.standard_cost > Decimal("10"):
                    rop = random.randint(20, 100)
                    lot = random.randint(25, 200)
                    moq = random.randint(10, 50)
                else:
                    rop = random.randint(100, 1000)
                    lot = random.randint(100, 5000)
                    moq = random.randint(50, 500)

                self.store.material_plant_extensions.append(MaterialPlantExtension(
                    material_id=mat.material_id,
                    plant_id=plant_id,
                    reorder_point=rop,
                    lot_size=lot,
                    min_order_qty=moq,
                ))

    def _determine_plants(self, mat: MaterialMaster) -> list[str]:
        """Determine which plants a material should be extended to per A6 rules."""
        # Check specific commodity affinity first
        if mat.category_id in PLANT_AFFINITY:
            return PLANT_AFFINITY[mat.category_id]

        # Fall back to top-level category probabilities
        top = self.store.category_top_level(mat.category_id)
        probs = DEFAULT_AFFINITY.get(top, {"SG01": 0.25, "MY01": 0.80, "VN01": 0.30})

        plants = []
        for plant_id, prob in probs.items():
            if random.random() < prob:
                plants.append(plant_id)

        # Ensure at least one plant
        if not plants:
            plants = ["MY01"]

        return plants

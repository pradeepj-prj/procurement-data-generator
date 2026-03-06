"""Load YAML configuration and seed files."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml


@dataclass
class MLSignalConfig:
    enabled: bool = False
    # 1a: Vendor score correlations
    vendor_score_correlation: float = 0.7
    vendor_score_noise_std: float = 10.0
    # 1b: Invoice variance ~ vendor quality
    invoice_quality_influence: float = 0.5
    invoice_base_match_rate: float = 0.82
    invoice_variance_scale: float = 0.08


@dataclass
class ScaleConfig:
    scale: int = 1
    demo_reference_date: date = date(2025, 9, 15)
    time_window_start: date = date(2024, 4, 1)
    time_window_end: date = date(2025, 9, 30)
    random_seed: int = 42
    ml_signal: MLSignalConfig = field(default_factory=MLSignalConfig)

    # Scaled targets
    @property
    def target_materials(self) -> int:
        return 800 * self.scale

    @property
    def target_vendors(self) -> int:
        return 120 * self.scale

    @property
    def target_contracts(self) -> int:
        return 40 * self.scale

    @property
    def target_legal_entities(self) -> int:
        return 95 * self.scale  # midpoint of 80-110

    @property
    def target_prs(self) -> int:
        return 500 * self.scale

    @property
    def target_pos(self) -> int:
        return 400 * self.scale

    @property
    def target_grs(self) -> int:
        return 350 * self.scale

    @property
    def target_invoices(self) -> int:
        return 320 * self.scale

    @property
    def target_payments(self) -> int:
        return 280 * self.scale


def load_yaml(filepath: Path) -> dict[str, Any]:
    """Load a YAML file and return its contents."""
    with open(filepath, "r") as f:
        return yaml.safe_load(f) or {}


def load_config(seeds_dir: Path) -> ScaleConfig:
    """Load config.yaml and return a ScaleConfig."""
    data = load_yaml(seeds_dir / "config.yaml")
    cfg = ScaleConfig()
    cfg.scale = data.get("scale", 1)
    cfg.random_seed = data.get("random_seed", 42)

    ref = data.get("demo_reference_date")
    if isinstance(ref, str):
        cfg.demo_reference_date = datetime.strptime(ref, "%Y-%m-%d").date()
    elif isinstance(ref, date):
        cfg.demo_reference_date = ref

    start = data.get("time_window_start")
    if isinstance(start, str):
        cfg.time_window_start = datetime.strptime(start, "%Y-%m-%d").date()
    elif isinstance(start, date):
        cfg.time_window_start = start

    end = data.get("time_window_end")
    if isinstance(end, str):
        cfg.time_window_end = datetime.strptime(end, "%Y-%m-%d").date()
    elif isinstance(end, date):
        cfg.time_window_end = end

    ml = data.get("ml_signal", {})
    if ml:
        cfg.ml_signal = MLSignalConfig(
            enabled=ml.get("enabled", False),
            vendor_score_correlation=ml.get("vendor_score_correlation", 0.7),
            vendor_score_noise_std=ml.get("vendor_score_noise_std", 10.0),
            invoice_quality_influence=ml.get("invoice_quality_influence", 0.5),
            invoice_base_match_rate=ml.get("invoice_base_match_rate", 0.82),
            invoice_variance_scale=ml.get("invoice_variance_scale", 0.08),
        )

    return cfg


def load_all_seeds(seeds_dir: Path) -> dict[str, Any]:
    """Load all seed YAML files into a single dict."""
    seeds = {}
    seed_files = [
        "org_structure", "category_hierarchy", "seed_materials",
        "seed_vendors", "seed_legal_entities", "seed_contracts",
        "seed_source_lists",
    ]
    for name in seed_files:
        filepath = seeds_dir / f"{name}.yaml"
        if filepath.exists():
            seeds[name] = load_yaml(filepath)
    return seeds

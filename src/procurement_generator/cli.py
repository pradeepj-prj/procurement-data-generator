"""CLI entry point for procurement data generator."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_config, load_all_seeds
from .pipeline import Pipeline
from .utils import set_random_seed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate procurement dataset for AMR manufacturing demo"
    )
    parser.add_argument(
        "--scale", type=int, default=None,
        help="Scale multiplier (1, 3, or 10). Overrides config.yaml."
    )
    parser.add_argument(
        "--seeds-dir", type=str, default="seeds",
        help="Path to seeds directory (default: seeds/)"
    )
    parser.add_argument(
        "--output-dir", type=str, default="output",
        help="Path to output directory (default: output/)"
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for reproducibility. Overrides config.yaml."
    )

    args = parser.parse_args()

    seeds_dir = Path(args.seeds_dir)
    output_dir = Path(args.output_dir)

    if not seeds_dir.exists():
        print(f"Error: Seeds directory '{seeds_dir}' not found.")
        sys.exit(1)

    # Load config
    config = load_config(seeds_dir)
    if args.scale is not None:
        config.scale = args.scale
    if args.seed is not None:
        config.random_seed = args.seed

    # Set random seed
    set_random_seed(config.random_seed)

    # Load seed files
    seeds = load_all_seeds(seeds_dir)

    # Run pipeline
    pipeline = Pipeline(config, seeds, output_dir)
    success = pipeline.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

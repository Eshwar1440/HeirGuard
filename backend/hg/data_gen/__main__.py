"""CLI: python -m hg.data_gen --out data/packets"""

import argparse
from pathlib import Path

from hg.config import get_settings
from hg.data_gen.packets import generate_all


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate hypothetical estate packets.")
    parser.add_argument("--out", type=Path, default=get_settings().data_dir / "packets")
    args = parser.parse_args()

    for truth in generate_all(args.out):
        errors = ", ".join(truth.planted_errors) or "none"
        print(f"{truth.packet_id}: {len(truth.documents)} documents, planted errors: {errors}")
    print(f"Wrote packets to {args.out.resolve()}")


if __name__ == "__main__":
    main()

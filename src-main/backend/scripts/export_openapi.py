"""Write or verify the repository's canonical OpenAPI contract.

Run from ``backend``. The output is deterministic so CI can reject route/schema drift.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.main import create_app

DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "contracts" / "openapi.json"


def rendered_contract() -> str:
    return (
        json.dumps(
            create_app().openapi(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail instead of updating")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    expected = rendered_contract()

    if args.check:
        try:
            actual = args.output.read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"OpenAPI contract is missing: {args.output}")
            return 1
        if actual != expected:
            print(
                "OpenAPI contract drift detected. Run "
                "'uv run --frozen python scripts/export_openapi.py' and review the diff."
            )
            return 1
        print(f"OpenAPI contract is current: {args.output}")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8", newline="\n")
    print(f"Wrote OpenAPI contract: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

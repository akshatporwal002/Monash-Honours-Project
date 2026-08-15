"""Write or verify the repository's canonical OpenAPI contract.

Run from ``backend``. The output is deterministic so CI can reject route/schema drift.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import TypeAdapter

from app.main import create_app
from app.schemas.assessment import ASSESSMENT_CONTRACT_TYPES

DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "contracts" / "openapi.json"


def assessment_contract_schemas() -> dict[str, object]:
    """Build OpenAPI components for route-independent frozen contracts."""
    schemas: dict[str, object] = {}
    for contract_type in ASSESSMENT_CONTRACT_TYPES:
        schema = TypeAdapter(contract_type).json_schema(ref_template="#/components/schemas/{model}")
        definitions = schema.pop("$defs", {})
        for name, definition in definitions.items():
            _add_schema(schemas, name, definition)
        _add_schema(schemas, contract_type.__name__, schema)
    return schemas


def _add_schema(schemas: dict[str, object], name: str, schema: object) -> None:
    existing = schemas.get(name)
    if existing is not None and existing != schema:
        raise ValueError(f"conflicting OpenAPI schema definition: {name}")
    schemas[name] = schema


def openapi_document() -> dict[str, object]:
    """Return the route contract plus frozen cross-person contract schemas."""
    document = create_app().openapi()
    components = document.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    for name, schema in assessment_contract_schemas().items():
        _add_schema(schemas, name, schema)
    return document


def rendered_contract() -> str:
    return (
        json.dumps(
            openapi_document(),
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

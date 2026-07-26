"""Generate deterministic TypeScript API contracts from the committed OpenAPI document."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "contracts" / "openapi.json"
DEFAULT_OUTPUT = ROOT / "frontend" / "src" / "api" / "generated.ts"
HEADER = """// Generated from contracts/openapi.json. Do not edit by hand.
// Run: uv run --frozen python scripts/generate_frontend_contracts.py

"""


class UnsupportedSchemaError(ValueError):
    """Raised instead of silently weakening an unfamiliar OpenAPI schema."""


def _literal(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str | int | float):
        return json.dumps(value, ensure_ascii=False)
    raise UnsupportedSchemaError(f"unsupported literal: {type(value).__name__}")


def _reference_name(reference: str) -> str:
    prefix = "#/components/schemas/"
    if not reference.startswith(prefix):
        raise UnsupportedSchemaError(f"unsupported reference: {reference}")
    return reference.removeprefix(prefix)


def _type_expression(schema: dict[str, Any], indent: int = 0) -> str:
    if set(schema).issubset({"title", "description", "default", "examples"}):
        return "unknown"
    if "$ref" in schema:
        return f"ApiSchemas[{json.dumps(_reference_name(schema['$ref']))}]"
    if "const" in schema:
        return _literal(schema["const"])
    if "enum" in schema:
        values = schema["enum"]
        if not isinstance(values, list) or not values:
            raise UnsupportedSchemaError("enum must contain at least one value")
        return " | ".join(_literal(value) for value in values)
    for union_key in ("anyOf", "oneOf"):
        if union_key in schema:
            variants = schema[union_key]
            if not isinstance(variants, list) or not variants:
                raise UnsupportedSchemaError(f"{union_key} must contain variants")
            return " | ".join(f"({_type_expression(variant, indent)})" for variant in variants)

    schema_type = schema.get("type")
    if schema_type == "null":
        return "null"
    if schema_type == "string":
        return "string"
    if schema_type in {"integer", "number"}:
        return "number"
    if schema_type == "boolean":
        return "boolean"
    if schema_type == "array":
        items = schema.get("items")
        if not isinstance(items, dict):
            raise UnsupportedSchemaError("array schema is missing items")
        return f"Array<{_type_expression(items, indent)}>"
    if schema_type == "object" or "properties" in schema or "additionalProperties" in schema:
        return _object_expression(schema, indent)
    raise UnsupportedSchemaError(f"unsupported schema shape: {json.dumps(schema, sort_keys=True)}")


def _object_expression(schema: dict[str, Any], indent: int) -> str:
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    if not isinstance(properties, dict):
        raise UnsupportedSchemaError("object properties must be a mapping")

    additional = schema.get("additionalProperties")
    property_names = schema.get("propertyNames")
    record_expression: str | None = None
    if isinstance(additional, dict):
        key_expression = "string"
        if isinstance(property_names, dict):
            key_expression = _type_expression(property_names, indent)
        record_expression = (
            f"Partial<Record<{key_expression}, {_type_expression(additional, indent)}>>"
        )
    elif additional is True:
        record_expression = "Record<string, unknown>"
    elif additional not in (False, None):
        raise UnsupportedSchemaError("unsupported additionalProperties value")

    if not properties:
        return record_expression or "Record<string, never>"

    spacing = " " * indent
    child_spacing = " " * (indent + 2)
    lines = ["{"]
    for name in sorted(properties):
        property_schema = properties[name]
        if not isinstance(property_schema, dict):
            raise UnsupportedSchemaError(f"property {name} has an invalid schema")
        optional = "" if name in required else "?"
        lines.append(
            f"{child_spacing}{json.dumps(name, ensure_ascii=False)}{optional}: "
            f"{_type_expression(property_schema, indent + 2)}"
        )
    lines.append(f"{spacing}}}")
    object_expression = "\n".join(lines)
    if record_expression is not None:
        return f"({object_expression} & {record_expression})"
    return object_expression


def render_contract(openapi: dict[str, Any]) -> str:
    schemas = openapi.get("components", {}).get("schemas")
    if not isinstance(schemas, dict) or not schemas:
        raise UnsupportedSchemaError("OpenAPI document has no component schemas")
    lines = [HEADER.rstrip(), "", "export type ApiSchemas = {"]
    for name in sorted(schemas):
        schema = schemas[name]
        if not isinstance(schema, dict):
            raise UnsupportedSchemaError(f"schema {name} is not an object")
        expression = _type_expression(schema, 2)
        lines.append(f"  {json.dumps(name, ensure_ascii=False)}: {expression}")
    lines.extend(["}", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail instead of updating")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    expected = render_contract(json.loads(args.input.read_text(encoding="utf-8")))

    if args.check:
        try:
            actual = args.output.read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"Generated frontend contracts are missing: {args.output}")
            return 1
        if actual != expected:
            print(
                "Frontend API contract drift detected. Run "
                "'uv run --frozen python scripts/generate_frontend_contracts.py'."
            )
            return 1
        print(f"Frontend API contracts are current: {args.output}")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8", newline="\n")
    print(f"Wrote frontend API contracts: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

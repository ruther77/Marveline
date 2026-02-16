#!/usr/bin/env python3
"""Export OpenAPI schema from FastAPI app and generate API_CONTRACT.md.

Usage:
    python scripts/export_openapi.py
    # or in Docker:
    docker compose run --rm --no-deps --entrypoint "" api python scripts/export_openapi.py

Outputs:
    docs/openapi.json       — OpenAPI 3.x JSON schema
    docs/API_CONTRACT.md    — Human-readable API contract
    frontend/openapi.json   — Copy for frontend type generation
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Force DEBUG=true to skip production secret validation
os.environ.setdefault("DEBUG", "true")

# Ensure project root is in path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.main import app  # noqa: E402


def export_openapi_json(output_dir: Path) -> dict:
    """Extract OpenAPI schema and write to JSON file."""
    schema = app.openapi()
    output_dir.mkdir(parents=True, exist_ok=True)

    openapi_path = output_dir / "openapi.json"
    with open(openapi_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    print(f"  openapi.json -> {openapi_path}")
    return schema


def generate_api_contract(schema: dict, output_dir: Path) -> None:
    """Generate human-readable API_CONTRACT.md from OpenAPI schema."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# API Contract — {schema.get('info', {}).get('title', 'CaroCorp')}",
        "",
        f"> Auto-generated on {now} by `scripts/export_openapi.py`",
        f"> Version: {schema.get('info', {}).get('version', '?')}",
        "> **NE PAS MODIFIER MANUELLEMENT** — relancer `make sync-api-types`",
        "",
    ]

    # --- Endpoints ---
    lines.append("## Endpoints")
    lines.append("")

    paths = schema.get("paths", {})
    # Group by tag
    tag_groups: dict[str, list[tuple[str, str, dict]]] = {}
    for path, methods in sorted(paths.items()):
        for method, details in methods.items():
            if method in ("get", "post", "put", "patch", "delete"):
                tags = details.get("tags", ["Other"])
                tag = tags[0] if tags else "Other"
                tag_groups.setdefault(tag, []).append((method.upper(), path, details))

    for tag, endpoints in sorted(tag_groups.items()):
        lines.append(f"### {tag}")
        lines.append("")
        lines.append("| Method | Path | Summary |")
        lines.append("|--------|------|---------|")
        for method, path, details in endpoints:
            summary = details.get("summary", "-")
            lines.append(f"| `{method}` | `{path}` | {summary} |")
        lines.append("")

    # --- Schemas ---
    lines.append("## Schemas (Pydantic Models)")
    lines.append("")

    components = schema.get("components", {})
    schemas = components.get("schemas", {})

    for name, sch in sorted(schemas.items()):
        # Skip internal/validation schemas
        if name.startswith("HTTPValidationError") or name.startswith("ValidationError"):
            continue

        lines.append(f"### `{name}`")
        lines.append("")

        description = sch.get("description", "")
        if description:
            lines.append(f"_{description}_")
            lines.append("")

        properties = sch.get("properties", {})
        required_fields = set(sch.get("required", []))

        if properties:
            lines.append("| Field | Type | Required | Default |")
            lines.append("|-------|------|----------|---------|")

            for field_name, field_info in properties.items():
                field_type = _resolve_type(field_info)
                is_required = field_name in required_fields
                req_marker = "Yes" if is_required else "No"
                default = field_info.get("default")
                default_str = f"`{default}`" if default is not None else "-"
                lines.append(
                    f"| `{field_name}` | `{field_type}` | {req_marker} | {default_str} |"
                )
            lines.append("")

        # Enum values
        if "enum" in sch:
            lines.append(f"**Values:** `{'`, `'.join(str(v) for v in sch['enum'])}`")
            lines.append("")

    # --- Write file ---
    output_dir.mkdir(parents=True, exist_ok=True)
    contract_path = output_dir / "API_CONTRACT.md"
    with open(contract_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"  API_CONTRACT.md -> {contract_path}")


def _resolve_type(field_info: dict) -> str:
    """Resolve OpenAPI type to readable string."""
    if "$ref" in field_info:
        return field_info["$ref"].split("/")[-1]

    if "allOf" in field_info:
        refs = [_resolve_type(item) for item in field_info["allOf"]]
        return " & ".join(refs)

    if "anyOf" in field_info:
        types = [_resolve_type(item) for item in field_info["anyOf"]]
        non_null = [t for t in types if t != "null"]
        if len(non_null) == 1 and len(types) > 1:
            return f"{non_null[0]} | null"
        return " | ".join(types)

    field_type = field_info.get("type", "any")

    if field_type == "array":
        items = field_info.get("items", {})
        item_type = _resolve_type(items)
        return f"{item_type}[]"

    if field_type == "object":
        additional = field_info.get("additionalProperties")
        if additional and isinstance(additional, dict):
            val_type = _resolve_type(additional)
            return f"Record<string, {val_type}>"
        return "object"

    if field_type == "string":
        fmt = field_info.get("format", "")
        if fmt == "date-time":
            return "datetime"
        if fmt == "email":
            return "email"
        if fmt == "uuid":
            return "uuid"
        return "string"

    if field_type == "null":
        return "null"

    return field_type


def main():
    print("Exporting OpenAPI schema...")

    docs_dir = project_root / "docs"
    frontend_dir = project_root / "frontend"

    # 1. Export OpenAPI JSON
    schema = export_openapi_json(docs_dir)

    # 2. Copy to frontend for openapi-typescript
    frontend_openapi = frontend_dir / "openapi.json"
    with open(frontend_openapi, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
    print(f"  openapi.json -> {frontend_openapi}")

    # 3. Generate human-readable contract
    generate_api_contract(schema, docs_dir)

    # Summary
    paths_count = len(schema.get("paths", {}))
    schemas_count = len(schema.get("components", {}).get("schemas", {}))
    print(f"\nDone: {paths_count} paths, {schemas_count} schemas exported.")


if __name__ == "__main__":
    main()

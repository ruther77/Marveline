#!/usr/bin/env python3
"""Generate a per-file Python scope map (functions, states, key variables)."""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET_DIRS = ("app", "alembic/versions", "scripts")
OUTPUT_JSON = PROJECT_ROOT / "docs" / "PYTHON_FILE_SCOPE_MAP.json"
OUTPUT_MD = PROJECT_ROOT / "docs" / "PYTHON_FILE_SCOPE_MAP.md"


@dataclass
class ClassInfo:
    name: str
    bases: list[str]
    attributes: list[str]
    methods: list[str]


@dataclass
class FileInfo:
    path: str
    module_doc: str | None
    imports: list[str]
    classes: list[ClassInfo]
    functions: list[str]
    key_variables: list[str]
    state_indicators: list[str]


def node_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = node_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Subscript):
        return node_name(node.value)
    if isinstance(node, ast.Call):
        return node_name(node.func)
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Tuple):
        return ", ".join(node_name(e) for e in node.elts)
    return ""


def extract_assigned_names(target: ast.AST) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        names: list[str] = []
        for elt in target.elts:
            names.extend(extract_assigned_names(elt))
        return names
    return []


def is_state_name(name: str) -> bool:
    upper = name.upper()
    return (
        "STATUS" in upper
        or "STATE" in upper
        or "TRANSITION" in upper
        or "PHASE" in upper
        or "STEP" in upper
        or upper in {"ACTIVE", "INACTIVE", "ENABLED", "DISABLED"}
    )


def parse_file(path: Path) -> FileInfo | None:
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return None

    imports: list[str] = []
    classes: list[ClassInfo] = []
    functions: list[str] = []
    key_vars: list[str] = []
    states: list[str] = []

    module_doc = ast.get_docstring(tree)
    if module_doc:
        module_doc = " ".join(module_doc.strip().split())

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = ", ".join(alias.name for alias in node.names)
            imports.append(f"{module}: {names}" if module else names)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for name in extract_assigned_names(target):
                    if name.startswith("_"):
                        continue
                    key_vars.append(name)
                    if is_state_name(name):
                        states.append(name)
        elif isinstance(node, ast.FunctionDef):
            functions.append(node.name)
        elif isinstance(node, ast.AsyncFunctionDef):
            functions.append(f"{node.name} [async]")
        elif isinstance(node, ast.ClassDef):
            base_names = [node_name(base) for base in node.bases if node_name(base)]
            methods: list[str] = []
            attributes: list[str] = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    methods.append(item.name)
                elif isinstance(item, ast.AsyncFunctionDef):
                    methods.append(f"{item.name} [async]")
                elif isinstance(item, (ast.Assign, ast.AnnAssign)):
                    assign_targets = item.targets if isinstance(item, ast.Assign) else [item.target]
                    for assign_target in assign_targets:
                        for name in extract_assigned_names(assign_target):
                            if name and not name.startswith("_"):
                                attributes.append(name)
                                key_vars.append(f"{node.name}.{name}")
                            if is_state_name(name):
                                states.append(f"{node.name}.{name}")

            if any("Enum" in b for b in base_names):
                enum_values: list[str] = []
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for t in item.targets:
                            for n in extract_assigned_names(t):
                                if n.isupper():
                                    enum_values.append(n)
                if enum_values:
                    states.append(f"{node.name}: {', '.join(enum_values)}")

            classes.append(
                ClassInfo(
                    name=node.name,
                    bases=base_names,
                    attributes=sorted(dict.fromkeys(attributes)),
                    methods=methods,
                )
            )

            if is_state_name(node.name):
                states.append(node.name)

    dedupe = lambda seq: sorted(dict.fromkeys(seq))

    return FileInfo(
        path=str(path.relative_to(PROJECT_ROOT)),
        module_doc=module_doc,
        imports=dedupe(imports),
        classes=sorted(classes, key=lambda c: c.name),
        functions=dedupe(functions),
        key_variables=dedupe(key_vars),
        state_indicators=dedupe(states),
    )


def render_markdown(files: list[FileInfo]) -> str:
    def group_key(path: str) -> str:
        parts = path.split("/")
        if parts[0] == "app" and len(parts) >= 2:
            return "/".join(parts[:2])
        if parts[0] == "alembic" and len(parts) >= 2:
            return "/".join(parts[:2])
        if parts[0] == "scripts":
            return "scripts"
        if len(parts) >= 2:
            return "/".join(parts[:2])
        return parts[0]

    module_counts: dict[str, int] = {}
    for f in files:
        k = group_key(f.path)
        module_counts[k] = module_counts.get(k, 0) + 1

    top_functions = sorted(
        ((f.path, len(f.functions)) for f in files if f.functions),
        key=lambda x: x[1],
        reverse=True,
    )[:20]

    top_states = sorted(
        ((f.path, len(f.state_indicators)) for f in files if f.state_indicators),
        key=lambda x: x[1],
        reverse=True,
    )[:20]

    lines: list[str] = []
    lines.append("# Python File Scope Map")
    lines.append("")
    lines.append(f"- Files documented: {len(files)}")
    lines.append("- Scope: `app/**/*.py`, `alembic/versions/*.py`, `scripts/*.py`")
    lines.append("- Generated by: `scripts/generate_python_file_scope.py`")
    lines.append("")
    lines.append("## Quick Orientation")
    lines.append("")
    lines.append("### Files by module prefix")
    lines.append("")
    for k, count in sorted(module_counts.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- `{k}`: {count}")
    lines.append("")
    lines.append("### Top files by function count")
    lines.append("")
    for path, count in top_functions:
        lines.append(f"- `{path}`: {count}")
    lines.append("")
    lines.append("### Top files by state indicators")
    lines.append("")
    for path, count in top_states:
        lines.append(f"- `{path}`: {count}")
    lines.append("")
    lines.append("## Global Index")
    lines.append("")
    for f in files:
        lines.append(f"- `{f.path}`")
    lines.append("")

    for f in files:
        lines.append(f"## `{f.path}`")
        lines.append("")
        if f.module_doc:
            lines.append(f"- Module doc: {f.module_doc}")
        else:
            lines.append("- Module doc: (none)")

        if f.functions:
            lines.append(f"- Functions ({len(f.functions)}): {', '.join(f.functions)}")
        else:
            lines.append("- Functions (0): (none)")

        if f.classes:
            lines.append(f"- Classes ({len(f.classes)}):")
            for c in f.classes:
                bases = f" [{', '.join(c.bases)}]" if c.bases else ""
                attrs = ", ".join(c.attributes) if c.attributes else "(none)"
                methods = ", ".join(c.methods) if c.methods else "(none)"
                lines.append(f"  - `{c.name}`{bases} -> attrs: {attrs} | methods: {methods}")
        else:
            lines.append("- Classes (0): (none)")

        if f.state_indicators:
            lines.append(f"- State indicators ({len(f.state_indicators)}): {', '.join(f.state_indicators)}")
        else:
            lines.append("- State indicators (0): (none)")

        if f.key_variables:
            lines.append(f"- Key variables ({len(f.key_variables)}): {', '.join(f.key_variables)}")
        else:
            lines.append("- Key variables (0): (none)")

        if f.imports:
            lines.append(f"- Imports ({len(f.imports)}): {', '.join(f.imports)}")
        else:
            lines.append("- Imports (0): (none)")

        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    files: list[FileInfo] = []
    for root in TARGET_DIRS:
        base = PROJECT_ROOT / root
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            info = parse_file(path)
            if info is None:
                continue
            files.append(info)

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps([asdict(f) for f in files], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    OUTPUT_MD.write_text(render_markdown(files), encoding="utf-8")

    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {OUTPUT_MD}")
    print(f"Files: {len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

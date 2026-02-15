#!/usr/bin/env python3
"""
CaroCorp Context Engine — MCP Server
Exposes: bootstrap(), prepare(), explore(), checkpoint(), search()
Maintains in-memory dependency graph and session state.
Persists to .context/ directory.
"""

import ast
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", os.getcwd()))
CONTEXT_DIR = PROJECT_ROOT / ".context"
APP_DIR = PROJECT_ROOT / "app"

mcp = FastMCP(
    "carocorp-context",
    instructions=(
        "CaroCorp codebase context server. "
        "ALWAYS call bootstrap() at the start of each session. "
        "ALWAYS call prepare(file_path) before editing any file. "
        "Use explore(module) to understand a module. "
        "Use search(query) to find symbols. "
        "Use checkpoint(notes) to save session progress."
    ),
)

# ---------------------------------------------------------------------------
# Session state (persists across tool calls via stdio process lifetime)
# ---------------------------------------------------------------------------

session: dict[str, Any] = {
    "bootstrapped": False,
    "prepared_files": {},       # {path: {deps, dependents, structure, prepared_at}}
    "dependency_graph": {},     # {rel_path: [dep_rel_paths]}
    "reverse_graph": {},        # {rel_path: [dependent_rel_paths]}
    "file_index": {},           # {rel_path: {classes, functions, lines, import_count}}
    "symbol_index": {},         # {symbol_name: [{file, kind, line}]}
    "checkpoints": [],
    "started_at": None,
}


# ---------------------------------------------------------------------------
# AST Helpers
# ---------------------------------------------------------------------------

def _resolve_import(module_name: str) -> str | None:
    """Resolve a dotted import to a relative file path within the project."""
    parts = module_name.replace(".", "/")
    candidates = [
        PROJECT_ROOT / f"{parts}.py",
        PROJECT_ROOT / parts / "__init__.py",
    ]
    for c in candidates:
        if c.exists():
            return str(c.relative_to(PROJECT_ROOT))
    return None


def _parse_file(file_path: Path) -> dict[str, Any]:
    """Parse a Python file with ast and extract structural metadata."""
    result: dict[str, Any] = {
        "imports": [],
        "from_imports": [],
        "classes": [],
        "functions": [],
        "lines": 0,
        "errors": [],
    }
    try:
        source = file_path.read_text(encoding="utf-8")
        result["lines"] = len(source.splitlines())
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        result["errors"].append(f"SyntaxError: {e}")
        return result
    except Exception as e:
        result["errors"].append(str(e))
        return result

    # Track class nodes to distinguish methods from top-level functions
    class_bodies: set[int] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append(alias.name)

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                result["from_imports"].append({
                    "module": node.module,
                    "names": [a.name for a in node.names],
                    "line": node.lineno,
                })

        elif isinstance(node, ast.ClassDef):
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(item.name)
                    class_bodies.add(id(item))
            bases = []
            for b in node.bases:
                try:
                    bases.append(ast.unparse(b))
                except Exception:
                    bases.append("?")
            result["classes"].append({
                "name": node.name,
                "bases": bases,
                "methods": methods,
                "line": node.lineno,
            })

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if id(node) not in class_bodies:
                args = []
                for a in node.args.args:
                    arg_str = a.arg
                    if a.annotation:
                        try:
                            arg_str += f": {ast.unparse(a.annotation)}"
                        except Exception:
                            pass
                    args.append(arg_str)
                ret = None
                if node.returns:
                    try:
                        ret = ast.unparse(node.returns)
                    except Exception:
                        pass
                decorators = []
                for dec in node.decorator_list:
                    try:
                        decorators.append(ast.unparse(dec))
                    except Exception:
                        decorators.append("?")
                result["functions"].append({
                    "name": node.name,
                    "args": args,
                    "return_type": ret,
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                    "decorators": decorators,
                    "line": node.lineno,
                })

    return result


def _build_deps(parsed: dict) -> list[str]:
    """Resolve parsed imports to project-internal file paths."""
    deps: set[str] = set()
    for imp in parsed["imports"]:
        resolved = _resolve_import(imp)
        if resolved:
            deps.add(resolved)
    for from_imp in parsed["from_imports"]:
        resolved = _resolve_import(from_imp["module"])
        if resolved:
            deps.add(resolved)
    return sorted(deps)


def _ensure_context_dir() -> None:
    CONTEXT_DIR.mkdir(exist_ok=True)


def _get_transitive_deps(file_path: str, depth: int = 2) -> dict[int, list[str]]:
    """Get dependencies at each depth level (1=direct, 2=deps of deps)."""
    result: dict[int, list[str]] = {}
    seen = {file_path}
    current_level_deps = session["dependency_graph"].get(file_path, [])

    for level in range(1, depth + 1):
        new_deps = []
        for dep in current_level_deps:
            if dep not in seen:
                new_deps.append(dep)
                seen.add(dep)
        result[level] = sorted(new_deps)
        # Compute next level
        next_deps = []
        for dep in new_deps:
            for sub_dep in session["dependency_graph"].get(dep, []):
                if sub_dep not in seen:
                    next_deps.append(sub_dep)
        current_level_deps = next_deps

    return result


def _find_related_tests(file_path: str) -> list[str]:
    """Find test files related to a source file by stem matching."""
    stem = Path(file_path).stem
    if stem == "__init__":
        stem = Path(file_path).parent.name

    tests_dir = PROJECT_ROOT / "tests"
    if not tests_dir.exists():
        return []

    matches = []
    for test_file in tests_dir.rglob("test_*.py"):
        if stem in test_file.stem:
            matches.append(str(test_file.relative_to(PROJECT_ROOT)))
    return sorted(matches)


def _find_siblings(file_path: str) -> list[str]:
    """Find other Python files in the same directory."""
    parent = (PROJECT_ROOT / file_path).parent
    if not parent.exists():
        return []
    return sorted(
        str(f.relative_to(PROJECT_ROOT))
        for f in parent.glob("*.py")
        if str(f.relative_to(PROJECT_ROOT)) != file_path
    )


def _find_related_schemas(file_path: str) -> list[str]:
    """Find related schema/service/model files by cross-layer matching."""
    stem = Path(file_path).stem
    if stem == "__init__":
        return []

    parts = file_path.split("/")
    related: set[str] = set()

    # Layer cross-references: service↔schema, model↔schema, endpoint↔service/schema, repo↔model/service
    layer_map = {
        "services": ["schemas", "models"],
        "schemas": ["services", "models"],
        "models": ["schemas", "repositories"],
        "repositories": ["models", "services"],
        "endpoints": ["services", "schemas"],
    }

    source_layer = None
    for layer in layer_map:
        if layer in parts:
            source_layer = layer
            break

    if source_layer:
        for target_layer in layer_map[source_layer]:
            for f in session["file_index"]:
                if target_layer in f.split("/") and stem in Path(f).stem:
                    related.add(f)

    return sorted(related - {file_path})


def _build_symbol_index() -> None:
    """Build a flat symbol->file lookup from the file_index."""
    idx: dict[str, list[dict]] = {}
    for rel_path, info in session["file_index"].items():
        for cls_name in info.get("classes", []):
            idx.setdefault(cls_name, []).append({
                "file": rel_path, "kind": "class",
            })
        for func_name in info.get("functions", []):
            idx.setdefault(func_name, []).append({
                "file": rel_path, "kind": "function",
            })
    session["symbol_index"] = idx


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def bootstrap() -> str:
    """
    Initialize session: scan all Python files, build dependency graph and symbol index.
    Call this ONCE at the start of every session.
    Returns a project structure summary.
    """
    try:
        _ensure_context_dir()

        session["started_at"] = datetime.now(timezone.utc).isoformat()
        session["dependency_graph"] = {}
        session["reverse_graph"] = {}
        session["file_index"] = {}
        session["prepared_files"] = {}
        session["checkpoints"] = []

        # Scan app/ Python files
        python_files = sorted(APP_DIR.rglob("*.py"))

        for pf in python_files:
            rel = str(pf.relative_to(PROJECT_ROOT))
            parsed = _parse_file(pf)
            deps = _build_deps(parsed)

            session["file_index"][rel] = {
                "classes": [c["name"] for c in parsed["classes"]],
                "functions": [f["name"] for f in parsed["functions"]],
                "lines": parsed["lines"],
                "import_count": len(parsed["imports"]) + len(parsed["from_imports"]),
            }
            session["dependency_graph"][rel] = deps

        # Reverse graph
        for src, deps in session["dependency_graph"].items():
            for dep in deps:
                session["reverse_graph"].setdefault(dep, []).append(src)

        # Include migrations and scripts in file_index (metadata only)
        for extra_dir in ["alembic/versions", "scripts"]:
            extra_path = PROJECT_ROOT / extra_dir
            if extra_path.exists():
                for pf in extra_path.rglob("*.py"):
                    rel = str(pf.relative_to(PROJECT_ROOT))
                    if rel not in session["file_index"]:
                        try:
                            lines = len(pf.read_text(encoding="utf-8").splitlines())
                        except Exception:
                            lines = 0
                        session["file_index"][rel] = {
                            "classes": [], "functions": [],
                            "lines": lines, "import_count": 0,
                        }

        # Symbol index
        _build_symbol_index()

        session["bootstrapped"] = True

        # Persist graph
        graph_path = CONTEXT_DIR / "dependency_graph.json"
        graph_path.write_text(
            json.dumps(session["dependency_graph"], indent=2),
            encoding="utf-8",
        )

        # Summary
        total_files = len(session["file_index"])
        total_lines = sum(f["lines"] for f in session["file_index"].values())
        total_classes = sum(len(f["classes"]) for f in session["file_index"].values())
        total_functions = sum(len(f["functions"]) for f in session["file_index"].values())

        modules: dict[str, list[str]] = {}
        for rel in session["file_index"]:
            parts = rel.split("/")
            if len(parts) >= 2 and parts[0] == "app":
                modules.setdefault(parts[1], []).append(rel)
            elif parts[0] not in ("app",):
                modules.setdefault(parts[0], []).append(rel)

        module_summary = "\n".join(
            f"  {mod}: {len(files)} files"
            for mod, files in sorted(modules.items(), key=lambda x: -len(x[1]))
        )

        return (
            f"Bootstrapped OK.\n\n"
            f"{total_files} files | {total_lines} lines | "
            f"{total_classes} classes | {total_functions} functions | "
            f"{len(session['symbol_index'])} symbols\n\n"
            f"Modules:\n{module_summary}\n\n"
            f"Graph persisted to .context/dependency_graph.json"
        )

    except Exception as e:
        return f"BOOTSTRAP ERROR: {e}"


@mcp.tool()
def prepare(file_path: str) -> str:
    """
    Prepare a file for editing: returns its structure, dependencies, and dependents.
    MUST be called before editing any file.

    Args:
        file_path: Relative path from project root (e.g. "app/services/audit.py")
    """
    try:
        if not session["bootstrapped"]:
            return "ERROR: Call bootstrap() first."

        full_path = PROJECT_ROOT / file_path
        if not full_path.exists():
            return f"ERROR: File not found: {file_path}"

        parsed = _parse_file(full_path)

        # Transitive deps (2 levels)
        transitive = _get_transitive_deps(file_path, depth=2)
        deps_l1 = transitive.get(1, [])
        deps_l2 = transitive.get(2, [])

        dependents = session["reverse_graph"].get(file_path, [])

        # Related tests, siblings, cross-layer schemas
        related_tests = _find_related_tests(file_path)
        siblings = _find_siblings(file_path)
        related_schemas = _find_related_schemas(file_path)

        session["prepared_files"][file_path] = {
            "prepared_at": datetime.now(timezone.utc).isoformat(),
            "deps": deps_l1,
            "deps_l2": deps_l2,
            "dependents": dependents,
            "tests": related_tests,
            "siblings": siblings,
            "related": related_schemas,
        }

        # Persist prepared list
        _ensure_context_dir()
        prepared_path = CONTEXT_DIR / "prepared_files.json"
        prepared_path.write_text(
            json.dumps(
                {k: v["prepared_at"] for k, v in session["prepared_files"].items()},
                indent=2,
            ),
            encoding="utf-8",
        )

        # Format classes
        classes_lines = []
        for c in parsed["classes"]:
            bases = ", ".join(c["bases"]) if c["bases"] else ""
            methods_str = ", ".join(c["methods"][:10])
            if len(c["methods"]) > 10:
                methods_str += f"... (+{len(c['methods']) - 10})"
            classes_lines.append(
                f"  class {c['name']}({bases}) [{len(c['methods'])} methods: {methods_str}] L{c['line']}"
            )

        # Format functions
        func_lines = []
        for f in parsed["functions"]:
            prefix = "async " if f["is_async"] else ""
            args_str = ", ".join(f["args"])
            ret = f" -> {f['return_type']}" if f.get("return_type") else ""
            decs = ""
            if f["decorators"]:
                decs = f" @{f['decorators'][0]}"
                if len(f["decorators"]) > 1:
                    decs += f" (+{len(f['decorators']) - 1})"
            func_lines.append(
                f"  {prefix}def {f['name']}({args_str}){ret}{decs} L{f['line']}"
            )

        # Format imports
        import_lines = []
        for fi in parsed["from_imports"]:
            names = ", ".join(fi["names"][:5])
            if len(fi["names"]) > 5:
                names += f"... (+{len(fi['names']) - 5})"
            import_lines.append(f"  from {fi['module']} import {names}")
        for imp in parsed["imports"]:
            import_lines.append(f"  import {imp}")

        deps_l1_str = "\n".join(f"  {d}" for d in deps_l1) or "  (none)"
        deps_l2_str = "\n".join(f"  {d}" for d in deps_l2) or "  (none)"
        dependents_str = "\n".join(f"  {d}" for d in dependents) or "  (none)"
        classes_str = "\n".join(classes_lines) or "  (none)"
        funcs_str = "\n".join(func_lines) or "  (none)"
        imports_str = "\n".join(import_lines) or "  (none)"
        tests_str = "\n".join(f"  {t}" for t in related_tests) or "  (none found)"
        siblings_str = "\n".join(f"  {s}" for s in siblings) or "  (none)"
        related_str = "\n".join(f"  {r}" for r in related_schemas) or "  (none)"

        errors_str = ""
        if parsed["errors"]:
            errors_str = "\n\nPARSE ERRORS:\n" + "\n".join(f"  {e}" for e in parsed["errors"])

        return (
            f"=== {file_path} ({parsed['lines']} lines) ===\n\n"
            f"Classes:\n{classes_str}\n\n"
            f"Functions:\n{funcs_str}\n\n"
            f"Imports:\n{imports_str}\n\n"
            f"Dependencies L1 (direct imports):\n{deps_l1_str}\n\n"
            f"Dependencies L2 (transitive):\n{deps_l2_str}\n\n"
            f"Dependents (imported by):\n{dependents_str}\n\n"
            f"Related tests:\n{tests_str}\n\n"
            f"Related schemas/services:\n{related_str}\n\n"
            f"Siblings (same dir):\n{siblings_str}\n\n"
            f"[Prepared: {len(session['prepared_files'])} files this session]"
            f"{errors_str}"
        )

    except Exception as e:
        return f"PREPARE ERROR: {e}"


@mcp.tool()
def explore(module: str) -> str:
    """
    Explore a module: returns all files, their structure, and inter-dependencies.

    Args:
        module: Module path under app/ (e.g. "services", "models", "api/v1/endpoints")
    """
    try:
        if not session["bootstrapped"]:
            return "ERROR: Call bootstrap() first."

        module_path = f"app/{module}"
        matching = {
            k: v for k, v in session["file_index"].items()
            if k.startswith(module_path + "/") or k == module_path + ".py"
        }

        if not matching:
            available = sorted({
                k.split("/")[1] for k in session["file_index"]
                if k.startswith("app/") and len(k.split("/")) > 2
            })
            return f"ERROR: No files for '{module}'. Available: {', '.join(available)}"

        # File details
        file_lines = []
        for fpath, info in sorted(matching.items()):
            cls = ", ".join(info["classes"][:3]) or "-"
            fns = ", ".join(info["functions"][:3]) or "-"
            if len(info["classes"]) > 3:
                cls += "..."
            if len(info["functions"]) > 3:
                fns += "..."
            file_lines.append(
                f"  {fpath}: {info['lines']}L | classes: [{cls}] | funcs: [{fns}]"
            )

        # Internal and external deps
        internal: list[str] = []
        external: list[str] = []
        for fpath in matching:
            for dep in session["dependency_graph"].get(fpath, []):
                if dep.startswith(module_path):
                    internal.append(f"  {fpath} -> {dep}")
                else:
                    external.append(f"  {fpath} -> {dep}")

        total_lines = sum(f["lines"] for f in matching.values())

        return (
            f"=== Module: {module} ===\n"
            f"{len(matching)} files | {total_lines} lines\n\n"
            f"Files:\n" + "\n".join(file_lines) + "\n\n"
            f"Internal deps:\n" + ("\n".join(sorted(set(internal))) or "  (none)") + "\n\n"
            f"External deps:\n" + ("\n".join(sorted(set(external))) or "  (none)")
        )

    except Exception as e:
        return f"EXPLORE ERROR: {e}"


@mcp.tool()
def search(query: str) -> str:
    """
    Search for symbols (classes, functions) across the codebase.

    Args:
        query: Symbol name or substring to search for (case-insensitive)
    """
    try:
        if not session["bootstrapped"]:
            return "ERROR: Call bootstrap() first."

        query_lower = query.lower()
        results: list[str] = []

        for symbol, locations in session["symbol_index"].items():
            if query_lower in symbol.lower():
                for loc in locations:
                    results.append(f"  {loc['kind']:8s} {symbol} -> {loc['file']}")

        if not results:
            return f"No symbols matching '{query}' found."

        # Limit output
        total = len(results)
        if total > 50:
            results = results[:50]
            results.append(f"  ... and {total - 50} more matches")

        return f"Symbols matching '{query}' ({total} results):\n" + "\n".join(results)

    except Exception as e:
        return f"SEARCH ERROR: {e}"


@mcp.tool()
def checkpoint(notes: str) -> str:
    """
    Save session checkpoint with notes. Writes to .context/ for recovery.

    Args:
        notes: Description of current progress and decisions made.
    """
    try:
        _ensure_context_dir()

        cp = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "notes": notes,
            "prepared_count": len(session["prepared_files"]),
            "prepared_files": list(session["prepared_files"].keys()),
        }
        session["checkpoints"].append(cp)

        # Persist
        CONTEXT_DIR.joinpath("checkpoints.json").write_text(
            json.dumps(session["checkpoints"], indent=2),
            encoding="utf-8",
        )

        # Session log (human-readable)
        log_lines = [f"# Session Log\n\nStarted: {session['started_at']}\n"]
        for i, c in enumerate(session["checkpoints"], 1):
            log_lines.append(
                f"\n## Checkpoint {i} — {c['timestamp']}\n\n"
                f"Prepared: {c['prepared_count']} files\n\n"
                f"{c['notes']}\n"
            )
        CONTEXT_DIR.joinpath("session_log.md").write_text(
            "\n".join(log_lines), encoding="utf-8",
        )

        return (
            f"Checkpoint #{len(session['checkpoints'])} saved.\n"
            f"Files prepared: {len(session['prepared_files'])}\n"
            f"Persisted to .context/checkpoints.json"
        )

    except Exception as e:
        return f"CHECKPOINT ERROR: {e}"


# ---------------------------------------------------------------------------
# MCP Resources
# ---------------------------------------------------------------------------

@mcp.resource("context://status")
def get_status() -> str:
    """Current session status."""
    return json.dumps({
        "bootstrapped": session["bootstrapped"],
        "started_at": session["started_at"],
        "prepared_count": len(session["prepared_files"]),
        "prepared_files": list(session["prepared_files"].keys()),
        "indexed_files": len(session["file_index"]),
        "symbols": len(session["symbol_index"]),
        "checkpoints": len(session["checkpoints"]),
    }, indent=2)


@mcp.resource("context://graph")
def get_graph() -> str:
    """Full dependency graph as JSON."""
    return json.dumps(session["dependency_graph"], indent=2)


@mcp.resource("context://symbols")
def get_symbols() -> str:
    """Symbol index summary (top 100 by reference count)."""
    sorted_symbols = sorted(
        session["symbol_index"].items(),
        key=lambda x: -len(x[1]),
    )[:100]
    return json.dumps(
        {s: locs for s, locs in sorted_symbols},
        indent=2,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()

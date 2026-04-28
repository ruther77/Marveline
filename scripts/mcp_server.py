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
from fnmatch import fnmatch
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", os.getcwd()))
CONTEXT_DIR = PROJECT_ROOT / ".context"

DEFAULT_CONTEXT_CONFIG: dict[str, Any] = {
    "scan_dirs": ["app"],
    "extra_dirs": ["alembic/versions", "scripts"],
    "tests_dir": "tests",
    "ignore_dirs": [
        ".git",
        ".venv",
        ".venv-mcp",
        ".pytest_cache",
        "__pycache__",
        "node_modules",
    ],
    "ignore_globs": [
        "*.pyc",
        "*.pyo",
        "*/__pycache__/*",
    ],
    "layer_map": {
        "services": ["schemas", "models"],
        "schemas": ["services", "models"],
        "models": ["schemas", "repositories"],
        "repositories": ["models", "services"],
        "endpoints": ["services", "schemas"],
    },
}


def _as_str_list(value: Any) -> list[str]:
    """Return a cleaned string list from unknown JSON data."""
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item.strip()]


def _as_layer_map(value: Any) -> dict[str, list[str]]:
    """Validate layer map shape from JSON."""
    if not isinstance(value, dict):
        return {}
    result: dict[str, list[str]] = {}
    for k, v in value.items():
        if not isinstance(k, str):
            continue
        cleaned = _as_str_list(v)
        if cleaned:
            result[k] = cleaned
    return result


def _default_context_config() -> dict[str, Any]:
    """Return an isolated default context config."""
    return {
        "scan_dirs": list(DEFAULT_CONTEXT_CONFIG["scan_dirs"]),
        "extra_dirs": list(DEFAULT_CONTEXT_CONFIG["extra_dirs"]),
        "tests_dir": DEFAULT_CONTEXT_CONFIG["tests_dir"],
        "ignore_dirs": list(DEFAULT_CONTEXT_CONFIG["ignore_dirs"]),
        "ignore_globs": list(DEFAULT_CONTEXT_CONFIG["ignore_globs"]),
        "layer_map": {
            k: list(v) for k, v in DEFAULT_CONTEXT_CONFIG["layer_map"].items()
        },
    }


def _load_context_config() -> dict[str, Any]:
    """Load optional .context.json with safe fallbacks."""
    config = _default_context_config()
    cfg_path = PROJECT_ROOT / ".context.json"
    if not cfg_path.exists():
        return config

    try:
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return config

    scan_dirs = _as_str_list(raw.get("scan_dirs"))
    if scan_dirs:
        config["scan_dirs"] = scan_dirs

    extra_dirs = _as_str_list(raw.get("extra_dirs"))
    if extra_dirs:
        config["extra_dirs"] = extra_dirs

    tests_dir = raw.get("tests_dir")
    if isinstance(tests_dir, str) and tests_dir.strip():
        config["tests_dir"] = tests_dir

    ignore_dirs = _as_str_list(raw.get("ignore_dirs"))
    if ignore_dirs:
        config["ignore_dirs"] = ignore_dirs

    ignore_globs = _as_str_list(raw.get("ignore_globs"))
    if ignore_globs:
        config["ignore_globs"] = ignore_globs

    layer_map = _as_layer_map(raw.get("layer_map"))
    if layer_map:
        config["layer_map"] = layer_map

    return config


CONTEXT_CONFIG = _load_context_config()

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
    "parse_cache": {},          # {rel_path: {signature: "mtime:size", parsed: {...}}}
    "checkpoints": [],
    "started_at": None,
}


# ---------------------------------------------------------------------------
# AST Helpers
# ---------------------------------------------------------------------------

def _normalize_project_rel_path(file_path: str) -> str | None:
    """Normalize a user-provided path and ensure it stays inside project root."""
    candidate = Path(file_path)
    if candidate.is_absolute():
        resolved = candidate.resolve(strict=False)
    else:
        resolved = (PROJECT_ROOT / candidate).resolve(strict=False)
    try:
        rel = resolved.relative_to(PROJECT_ROOT.resolve(strict=False))
    except ValueError:
        return None
    return str(rel).replace("\\", "/")


def _to_rel_path(file_path: Path) -> str:
    """Convert an absolute project file path to normalized relative path."""
    return str(file_path.relative_to(PROJECT_ROOT)).replace("\\", "/")


def _path_signature(file_path: Path) -> str | None:
    """Return a stable file signature based on mtime and size."""
    try:
        stat = file_path.stat()
    except OSError:
        return None
    return f"{stat.st_mtime_ns}:{stat.st_size}"


def _is_ignored_rel_path(rel_path: str) -> bool:
    """Check whether a relative path is ignored by config."""
    path = Path(rel_path)
    ignore_dirs = set(CONTEXT_CONFIG.get("ignore_dirs", []))
    if any(part in ignore_dirs for part in path.parts):
        return True

    ignore_globs = CONTEXT_CONFIG.get("ignore_globs", [])
    for pattern in ignore_globs:
        if fnmatch(rel_path, pattern):
            return True
    return False


def _iter_python_files(root_dir: Path) -> list[Path]:
    """List Python files under root_dir while pruning ignored directories."""
    if not root_dir.exists() or not root_dir.is_dir():
        return []

    results: list[Path] = []
    ignore_dirs = set(CONTEXT_CONFIG.get("ignore_dirs", []))

    for walk_root, dirs, files in os.walk(root_dir):
        # Prune ignored subdirectories early for performance.
        dirs[:] = [d for d in dirs if d not in ignore_dirs]

        walk_root_path = Path(walk_root)
        for file_name in files:
            if not file_name.endswith(".py"):
                continue
            file_path = walk_root_path / file_name
            rel_path = _to_rel_path(file_path)
            if _is_ignored_rel_path(rel_path):
                continue
            results.append(file_path)
    return results


def _resolve_import(
    module_name: str,
    *,
    current_file: str | None = None,
    level: int = 0,
) -> str | None:
    """
    Resolve import to a project-relative Python file.

    Supports absolute and relative imports.
    """
    if level > 0:
        if not current_file:
            return None
        anchor = Path(current_file).parent
        for _ in range(level - 1):
            anchor = anchor.parent
        base = PROJECT_ROOT / anchor
    else:
        base = PROJECT_ROOT

    module_parts = [p for p in module_name.split(".") if p]
    candidate_root = base.joinpath(*module_parts) if module_parts else base

    candidates = [
        candidate_root.with_suffix(".py"),
        candidate_root / "__init__.py",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
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
            result["from_imports"].append({
                "module": node.module or "",
                "names": [a.name for a in node.names],
                "level": node.level,
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


def _parse_file_cached(file_path: Path, rel_path: str) -> dict[str, Any]:
    """Parse file with cache invalidation based on stat signature."""
    signature = _path_signature(file_path)
    cache = session.get("parse_cache", {})
    cached = cache.get(rel_path) if isinstance(cache, dict) else None

    if (
        signature
        and isinstance(cached, dict)
        and cached.get("signature") == signature
        and isinstance(cached.get("parsed"), dict)
    ):
        return cached["parsed"]

    parsed = _parse_file(file_path)
    if signature and isinstance(cache, dict):
        cache[rel_path] = {"signature": signature, "parsed": parsed}
    return parsed


def _build_deps(parsed: dict, *, current_file: str) -> list[str]:
    """Resolve parsed imports to project-internal file paths."""
    deps: set[str] = set()

    for imp in parsed["imports"]:
        resolved = _resolve_import(imp, current_file=current_file, level=0)
        if resolved:
            deps.add(resolved)

    for from_imp in parsed["from_imports"]:
        module = from_imp.get("module", "")
        level = int(from_imp.get("level", 0) or 0)

        # Dependency on imported module/package itself.
        if module:
            resolved = _resolve_import(module, current_file=current_file, level=level)
            if resolved:
                deps.add(resolved)

        # Resolve "from X import Y" where Y might be a submodule.
        for imported_name in from_imp.get("names", []):
            if imported_name == "*":
                continue
            candidate_module = f"{module}.{imported_name}" if module else imported_name
            resolved_member = _resolve_import(
                candidate_module,
                current_file=current_file,
                level=level,
            )
            if resolved_member:
                deps.add(resolved_member)

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

    tests_dir = PROJECT_ROOT / CONTEXT_CONFIG["tests_dir"]
    if not tests_dir.exists():
        return []

    matches = []
    for test_file in tests_dir.rglob("test_*.py"):
        rel_test = _to_rel_path(test_file)
        if _is_ignored_rel_path(rel_test):
            continue
        if stem in test_file.stem:
            matches.append(rel_test)
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

    # Layer cross-references are configurable via .context.json.
    layer_map: dict[str, list[str]] = CONTEXT_CONFIG["layer_map"]

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


def _load_persisted_checkpoints() -> list[dict[str, Any]]:
    """Load previous checkpoints from .context/checkpoints.json if available."""
    path = CONTEXT_DIR / "checkpoints.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    valid: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict):
            valid.append(item)
    return valid


def _load_persisted_prepared_files() -> dict[str, dict[str, Any]]:
    """Load previous prepared files from .context/prepared_files.json if available."""
    path = CONTEXT_DIR / "prepared_files.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}

    prepared: dict[str, dict[str, Any]] = {}
    for file_path, prepared_at in data.items():
        if not isinstance(file_path, str):
            continue
        if not isinstance(prepared_at, str):
            prepared_at = ""
        prepared[file_path] = {
            "prepared_at": prepared_at,
            "deps": [],
            "deps_l2": [],
            "dependents": [],
            "tests": [],
            "siblings": [],
            "related": [],
        }
    return prepared


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
        global CONTEXT_CONFIG

        _ensure_context_dir()
        CONTEXT_CONFIG = _load_context_config()

        session["started_at"] = datetime.now(timezone.utc).isoformat()
        session["dependency_graph"] = {}
        session["reverse_graph"] = {}
        session["file_index"] = {}
        session["prepared_files"] = _load_persisted_prepared_files()
        session["checkpoints"] = _load_persisted_checkpoints()

        # Scan configured source directories for Python files.
        python_files: dict[str, Path] = {}
        for scan_dir in CONTEXT_CONFIG["scan_dirs"]:
            scan_path = PROJECT_ROOT / scan_dir
            for pf in _iter_python_files(scan_path):
                python_files[_to_rel_path(pf)] = pf

        for rel, pf in sorted(python_files.items()):
            parsed = _parse_file_cached(pf, rel)
            deps = _build_deps(parsed, current_file=rel)

            session["file_index"][rel] = {
                "classes": [c["name"] for c in parsed["classes"]],
                "functions": [f["name"] for f in parsed["functions"]],
                "lines": parsed["lines"],
                "import_count": len(parsed["imports"]) + len(parsed["from_imports"]),
            }
            session["dependency_graph"][rel] = deps

        # Include optional extra directories in index and graph.
        for extra_dir in CONTEXT_CONFIG["extra_dirs"]:
            extra_path = PROJECT_ROOT / extra_dir
            for pf in _iter_python_files(extra_path):
                rel = _to_rel_path(pf)
                if rel in session["file_index"]:
                    continue
                parsed = _parse_file_cached(pf, rel)
                session["file_index"][rel] = {
                    "classes": [c["name"] for c in parsed["classes"]],
                    "functions": [f["name"] for f in parsed["functions"]],
                    "lines": parsed["lines"],
                    "import_count": len(parsed["imports"]) + len(parsed["from_imports"]),
                }
                session["dependency_graph"][rel] = _build_deps(parsed, current_file=rel)

        # Reverse graph
        for src, deps in session["dependency_graph"].items():
            for dep in deps:
                session["reverse_graph"].setdefault(dep, []).append(src)
        for dep in session["reverse_graph"]:
            session["reverse_graph"][dep] = sorted(set(session["reverse_graph"][dep]))

        # Keep parse cache bounded to current indexed files.
        parse_cache = session.get("parse_cache", {})
        if isinstance(parse_cache, dict):
            valid_paths = set(session["file_index"].keys())
            stale_paths = [p for p in parse_cache if p not in valid_paths]
            for stale_path in stale_paths:
                del parse_cache[stale_path]

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

        scan_dirs_roots = {
            Path(scan_dir).parts[0] for scan_dir in CONTEXT_CONFIG["scan_dirs"] if scan_dir
        }
        modules: dict[str, list[str]] = {}
        for rel in session["file_index"]:
            parts = rel.split("/")
            if len(parts) >= 2 and parts[0] in scan_dirs_roots:
                modules.setdefault(parts[1], []).append(rel)
            elif parts[0] not in scan_dirs_roots:
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
            f"Scan dirs: {', '.join(CONTEXT_CONFIG['scan_dirs'])}\n"
            f"Extra dirs: {', '.join(CONTEXT_CONFIG['extra_dirs'])}\n\n"
            f"Ignored dirs: {', '.join(CONTEXT_CONFIG['ignore_dirs'])}\n\n"
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

        normalized_path = _normalize_project_rel_path(file_path)
        if not normalized_path:
            return f"ERROR: Path outside project root: {file_path}"
        file_path = normalized_path

        full_path = PROJECT_ROOT / file_path
        if not full_path.exists() or not full_path.is_file():
            return f"ERROR: File not found: {file_path}"

        parsed = _parse_file_cached(full_path, file_path)

        # Keep graph/index fresh for this file (covers late-added files).
        deps_now = _build_deps(parsed, current_file=file_path)
        deps_prev = set(session["dependency_graph"].get(file_path, []))
        deps_now_set = set(deps_now)
        session["dependency_graph"][file_path] = deps_now
        session["file_index"][file_path] = {
            "classes": [c["name"] for c in parsed["classes"]],
            "functions": [f["name"] for f in parsed["functions"]],
            "lines": parsed["lines"],
            "import_count": len(parsed["imports"]) + len(parsed["from_imports"]),
        }

        for dep in deps_prev - deps_now_set:
            existing = session["reverse_graph"].get(dep, [])
            session["reverse_graph"][dep] = [src for src in existing if src != file_path]
            if not session["reverse_graph"][dep]:
                del session["reverse_graph"][dep]
        for dep in deps_now:
            sources = session["reverse_graph"].setdefault(dep, [])
            if file_path not in sources:
                sources.append(file_path)

        # Transitive deps (2 levels)
        transitive = _get_transitive_deps(file_path, depth=2)
        deps_l1 = transitive.get(1, [])
        deps_l2 = transitive.get(2, [])

        dependents = sorted(set(session["reverse_graph"].get(file_path, [])))

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
            dots = "." * int(fi.get("level", 0) or 0)
            module_label = fi.get("module", "") or ""
            import_lines.append(f"  from {dots}{module_label} import {names}")
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
        module: Module path under configured scan dirs
                (e.g. "services", "models", "api/v1/endpoints")
    """
    try:
        if not session["bootstrapped"]:
            return "ERROR: Call bootstrap() first."

        matching: dict[str, Any] = {}
        for scan_dir in CONTEXT_CONFIG["scan_dirs"]:
            module_path = f"{scan_dir}/{module}"
            for rel_path, info in session["file_index"].items():
                if rel_path.startswith(module_path + "/") or rel_path == module_path + ".py":
                    matching[rel_path] = info

        if not matching:
            scan_roots = {
                Path(scan_dir).parts[0] for scan_dir in CONTEXT_CONFIG["scan_dirs"] if scan_dir
            }
            available = sorted({
                k.split("/")[1] for k in session["file_index"]
                if len(k.split("/")) > 2 and k.split("/")[0] in scan_roots
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
        module_prefixes = [
            f"{scan_dir}/{module}" for scan_dir in CONTEXT_CONFIG["scan_dirs"]
        ]
        for fpath in matching:
            for dep in session["dependency_graph"].get(fpath, []):
                is_internal = any(
                    dep.startswith(prefix + "/") or dep == prefix + ".py"
                    for prefix in module_prefixes
                )
                if is_internal:
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
        if not session["bootstrapped"]:
            return "ERROR: Call bootstrap() first."

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
        "scan_dirs": CONTEXT_CONFIG["scan_dirs"],
        "extra_dirs": CONTEXT_CONFIG["extra_dirs"],
        "tests_dir": CONTEXT_CONFIG["tests_dir"],
        "ignore_dirs": CONTEXT_CONFIG["ignore_dirs"],
        "ignore_globs": CONTEXT_CONFIG["ignore_globs"],
        "parse_cache_entries": len(session.get("parse_cache", {})),
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

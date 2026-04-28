# 54 — CI Invariants Scripts

> Scripts Python lancés par GitHub Actions à chaque PR. **Une PR ne peut pas merger si un invariant échoue.**
> Localisation : `tools/check_*.py`. Tests d'invariant ≠ tests fonctionnels.
> **Convention** : chaque script imprime `[INVARIANT_OK]` ou `[INVARIANT_FAIL]` + message lisible. Exit code 0 = OK, 1 = FAIL.

## Sommaire

| # | Script | Invariant garanti | CI step |
|---|---|---|---|
| 1 | `check_endpoint_scopes.py` | Tout endpoint a `require_scope()` (sauf whitelist) | invariants |
| 2 | `check_celery_queues.py` | Toute queue déclarée est consommée par un worker | invariants |
| 3 | `check_no_finance_legacy.py` | Aucun import depuis `app/models/finance/` (drop Bloc 3) | invariants |
| 4 | `check_mapped_datetime.py` | `Mapped[datetime]` couplé `DateTime(timezone=True)` (pas `Mapped[str]`) | invariants |
| 5 | `check_scope_catalog.py` | Tout `Scope.X` utilisé est dans l'enum + `auth_vertical_scopes` | invariants |
| 6 | `check_no_brand_code.py` | Aucun `brand_code` sur Product/Category/Bundle/Collection (Bloc 7) | invariants |
| 7 | `check_audit_action_decorator.py` | Tout service de mutation a `@audit_action` ou `audit_service.log_*` | invariants |
| 8 | `verify_audit_chain.py` | Chaîne HMAC audit_logs intacte (chronologique) | nightly job |
| 9 | `check_ledger_immutable_triggers.py` | Triggers DB `BEFORE UPDATE/DELETE` présents sur ledger tables | invariants |
| 10 | `check_celery_tenant_arg.py` | Toute `@celery_app.task` qui touche table tenant-scoped a `tenant_id` arg | invariants |
| 11 | `check_no_userpcompat.py` | Aucun import `UserCompat` (supprimé Bloc 1) | invariants |
| 12 | `check_no_sync_db_in_async_handler.py` | Aucun handler async qui utilise sync session | invariants |
| 13 | `check_rls_enabled_on_tenant_tables.py` | Toute table avec colonne `tenant_id` a RLS enabled | invariants |
| 14 | `check_fsm_transitions_present.py` | Toute table FSM a sa matrice dans `fsm_transitions` | invariants |
| 15 | `check_alembic_downgrade_implemented.py` | Toute migration Alembic a `downgrade()` non-vide | invariants |
| 16 | `check_tr_coverage.py` | Tout TR-yy déclaré architecture-cible.md a un mapping en RACI §8 + sprint cité existe | invariants (Vague 2) |
| 17 | `check_schema_constants_coherence.py` | Tout default value Pydantic schema lié à `MFAConfig.X`/`SecurityConfig.X` est bind dynamique (pas hardcoded) | invariants (Vague 4 — B2.S4) |
| 18 | `check_metrics_path_patterns.py` | Tout label `path` exporté en métrique Prometheus est dans la whitelist cardinality `'other'` fallback | invariants (B6.S6.T4) |

## Pipeline GitHub Actions intégration

```yaml
# .github/workflows/ci.yml
jobs:
  invariants:
    runs-on: ubuntu-latest
    needs: [test:integ]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -r requirements.txt
      - run: |
          python tools/check_endpoint_scopes.py
          python tools/check_celery_queues.py
          python tools/check_no_finance_legacy.py
          python tools/check_mapped_datetime.py
          python tools/check_scope_catalog.py
          python tools/check_no_brand_code.py
          python tools/check_audit_action_decorator.py
          python tools/check_ledger_immutable_triggers.py
          python tools/check_celery_tenant_arg.py
          python tools/check_no_userpcompat.py
          python tools/check_no_sync_db_in_async_handler.py
          python tools/check_rls_enabled_on_tenant_tables.py
          python tools/check_fsm_transitions_present.py
          python tools/check_alembic_downgrade_implemented.py
          python tools/check_tr_coverage.py
          python tools/check_schema_constants_coherence.py
          python tools/check_metrics_path_patterns.py
```

---

## 1. `check_endpoint_scopes.py`

### But

Garantir que **tous** les endpoints `@router.{get,post,put,patch,delete}` ont un `Depends(require_scope(...))` (sauf whitelist explicite).

### Failure mode

Sans cet invariant, friction F486 (Bloc 4) reproduit : 5 endpoints `GET /products` sans scope check passent en prod silencieusement → user `customers:read` accède au catalogue.

### Implémentation

```python
# tools/check_endpoint_scopes.py
"""CI invariant : tout endpoint FastAPI doit avoir require_scope().

Whitelist exceptions documentées :
  - /health/live, /health/ready, /health/status (publics, mTLS Prometheus)
  - /metrics (Prometheus mTLS, Bloc 6 §6.2.15)
  - /docs, /openapi.json (non-prod)
  - /auth/v2/login, /auth/v2/refresh (auth flow lui-même)
  - /auth/v2/forgot-password, /auth/v2/reset-password (anonymous flow)
  - /webauthn/registration/options (pre-auth WebAuthn)

Friction prévenue : F486 (Bloc 4 §4.2.6).
"""
import ast
import re
import sys
from pathlib import Path

ENDPOINTS_DIR = Path("app/api/v1/endpoints")

WHITELIST_PATHS = {
    "/health", "/health/live", "/health/ready", "/health/status",
    "/metrics",
    "/docs", "/openapi.json", "/redoc",
    "/auth/v2/login", "/auth/v2/refresh", "/auth/v2/forgot-password",
    "/auth/v2/reset-password", "/auth/v2/verify-reset-token",
    "/webauthn/registration/options",
}

ROUTER_DECORATOR_RE = re.compile(r"@router\.(get|post|put|patch|delete)\(")


def check_function(file_path: Path, fn_node: ast.FunctionDef) -> list[str]:
    """Vérifie qu'une fonction décorée @router.* a require_scope() dans son Depends().
    
    Returns list of violations.
    """
    violations = []
    
    # Récupère le path du décorateur (premier arg)
    router_decorator = None
    for dec in fn_node.decorator_list:
        if (isinstance(dec, ast.Call)
            and isinstance(dec.func, ast.Attribute)
            and isinstance(dec.func.value, ast.Name)
            and dec.func.value.id == "router"
            and dec.func.attr in ("get", "post", "put", "patch", "delete")):
            router_decorator = dec
            break
    
    if router_decorator is None:
        return []  # pas un endpoint
    
    # Path du décorateur
    if not router_decorator.args:
        return [f"{file_path}:{fn_node.lineno} {fn_node.name}: @router decorator without path"]
    
    path_arg = router_decorator.args[0]
    if not isinstance(path_arg, ast.Constant):
        return []  # path dynamique, skip
    
    path = path_arg.value
    if path in WHITELIST_PATHS or any(path.startswith(w) for w in WHITELIST_PATHS):
        return []
    
    # Cherche require_scope() dans les Depends() des params
    has_require_scope = False
    for arg in fn_node.args.args + fn_node.args.kwonlyargs:
        # Cherche un Depends(require_scope(...)) dans l'annotation par défaut
        for default in fn_node.args.defaults + fn_node.args.kw_defaults:
            if default is None:
                continue
            for node in ast.walk(default):
                if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "require_scope"):
                    has_require_scope = True
                    break
                if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "require_scope"):
                    has_require_scope = True
                    break
    
    # Vérifier aussi `dependencies=[Depends(require_scope(...))]` sur le décorateur
    for kw in router_decorator.keywords:
        if kw.arg == "dependencies":
            for node in ast.walk(kw.value):
                if (isinstance(node, ast.Call)
                    and (
                        (isinstance(node.func, ast.Name) and node.func.id == "require_scope")
                        or (isinstance(node.func, ast.Attribute) and node.func.attr == "require_scope")
                    )):
                    has_require_scope = True
                    break
    
    if not has_require_scope:
        violations.append(
            f"{file_path}:{fn_node.lineno} {fn_node.name} (path={path}): missing require_scope()"
        )
    
    return violations


def main():
    if not ENDPOINTS_DIR.exists():
        print(f"[INVARIANT_FAIL] {ENDPOINTS_DIR} not found")
        return 1
    
    all_violations = []
    
    for py_file in ENDPOINTS_DIR.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError as e:
            print(f"[INVARIANT_FAIL] {py_file}: SyntaxError {e}")
            return 1
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                violations = check_function(py_file, node)
                all_violations.extend(violations)
    
    if all_violations:
        print(f"[INVARIANT_FAIL] {len(all_violations)} endpoint(s) without require_scope():")
        for v in all_violations:
            print(f"  - {v}")
        print("\nFix: add `Depends(require_scope(Scope.<DOMAIN>_<ACTION>))` to function params,")
        print("OR add `dependencies=[Depends(require_scope(...))]` to @router decorator.")
        print("Whitelist exceptions documented in tools/check_endpoint_scopes.py:WHITELIST_PATHS.")
        return 1
    
    print(f"[INVARIANT_OK] All endpoints have require_scope() (whitelist excepted)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

## 2. `check_celery_queues.py`

### But

Garantir que **toutes les queues déclarées dans `task_routes`** sont effectivement consommées par au moins un worker dans `docker-compose.yml` (ou Kubernetes manifest).

### Failure mode

Sans cet invariant, friction F1053 (Bloc 6) : queue `loyalty` déclarée par decorator `@celery_app.task(queue='loyalty')` mais jamais routée → tasks empilées indéfiniment dans Redis.

### Implémentation

```python
# tools/check_celery_queues.py
"""CI invariant : toute queue déclarée dans task_routes ou via @celery_app.task(queue=...)
doit être consommée par au moins un worker dans docker-compose.yml.

Friction prévenue : F1053 (Bloc 6 §6.2.11).
"""
import ast
import re
import sys
from pathlib import Path

import yaml

CELERY_APP_FILE = Path("app/tasks/celery_app.py")
TASKS_DIR = Path("app/tasks")
DOCKER_COMPOSE = Path("docker-compose.yml")


def extract_routed_queues_from_celery_app() -> set[str]:
    """Parse celery_app.py task_routes dict."""
    tree = ast.parse(CELERY_APP_FILE.read_text())
    queues = set()
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (isinstance(target, ast.Attribute)
                    and target.attr == "task_routes"):
                    if isinstance(node.value, ast.Dict):
                        for v in node.value.values:
                            if isinstance(v, ast.Dict):
                                for k, val in zip(v.keys, v.values):
                                    if (isinstance(k, ast.Constant) and k.value == "queue"
                                        and isinstance(val, ast.Constant)):
                                        queues.add(val.value)
    return queues


def extract_decorator_queues_from_tasks() -> set[str]:
    """Parse all @celery_app.task(queue='X') decorators in app/tasks/."""
    queues = set()
    for py_file in TASKS_DIR.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    if (isinstance(dec, ast.Call)
                        and isinstance(dec.func, ast.Attribute)
                        and dec.func.attr == "task"):
                        for kw in dec.keywords:
                            if kw.arg == "queue" and isinstance(kw.value, ast.Constant):
                                queues.add(kw.value.value)
    return queues


def extract_consumed_queues_from_compose() -> set[str]:
    """Parse docker-compose.yml services.celery-worker-*.command for -Q <queue>."""
    if not DOCKER_COMPOSE.exists():
        # Fallback : K8s manifest
        return set()  # à implémenter pour K8s
    
    compose = yaml.safe_load(DOCKER_COMPOSE.read_text())
    consumed = set()
    
    for service_name, service_def in compose.get("services", {}).items():
        if "celery" not in service_name and "worker" not in service_name:
            continue
        cmd = service_def.get("command", "")
        if isinstance(cmd, list):
            cmd = " ".join(cmd)
        # Match -Q queue1,queue2 ou --queues=q1,q2
        m = re.search(r"(-Q|--queues[= ])([\w,]+)", cmd)
        if m:
            for q in m.group(2).split(","):
                consumed.add(q.strip())
        else:
            # Worker sans -Q consume default
            consumed.add("default")
    
    return consumed


def main():
    declared = extract_routed_queues_from_celery_app() | extract_decorator_queues_from_tasks()
    declared.add("default")  # Celery default queue
    
    consumed = extract_consumed_queues_from_compose()
    
    missing = declared - consumed
    
    if missing:
        print(f"[INVARIANT_FAIL] Queues declared but not consumed by any worker: {sorted(missing)}")
        print("\nFix: add -Q queue1,queue2 to docker-compose.yml worker command.")
        print(f"Declared queues: {sorted(declared)}")
        print(f"Consumed queues: {sorted(consumed)}")
        return 1
    
    extra = consumed - declared
    if extra:
        print(f"[INVARIANT_WARNING] Workers consume queues never declared (will be empty): {sorted(extra)}")
        # Warning, pas fail
    
    print(f"[INVARIANT_OK] All declared queues consumed: {sorted(declared)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

## 3. `check_no_finance_legacy.py`

### But

Aucun import depuis `app/models/finance/` (duplicates supprimés Bloc 3 §3.2.9).

### Failure mode

Sans, F715 (duplicates Invoice models) reproduit silencieusement.

### Implémentation

```python
# tools/check_no_finance_legacy.py
"""CI invariant : aucun import depuis app.models.finance.* (drop Bloc 3 §3.2.9).

Friction prévenue : F715.
"""
import re
import sys
from pathlib import Path

LEGACY_PATTERN = re.compile(r"from\s+app\.models\.finance(\.|\s|$)|import\s+app\.models\.finance(\.|\s|$)")


def main():
    violations = []
    for py_file in Path("app").rglob("*.py"):
        if "models/finance/" in str(py_file):
            continue  # le dossier lui-même, on s'attend à ce qu'il disparaisse
        for i, line in enumerate(py_file.read_text().splitlines(), 1):
            if LEGACY_PATTERN.search(line):
                violations.append(f"{py_file}:{i}: {line.strip()}")
    
    if violations:
        print(f"[INVARIANT_FAIL] {len(violations)} legacy `app.models.finance` imports:")
        for v in violations:
            print(f"  - {v}")
        print("\nFix: import from app.models.invoice instead. See architecture-cible.md §3.2.9.")
        return 1
    
    # Vérifier que le dossier finance/ a été supprimé
    finance_dir = Path("app/models/finance")
    if finance_dir.exists() and any(finance_dir.iterdir()):
        print(f"[INVARIANT_WARNING] {finance_dir} still exists with files. Should be removed (Bloc 3 §3.2.9).")
    
    print("[INVARIANT_OK] No legacy app.models.finance imports")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

## 4. `check_mapped_datetime.py`

### But

Détecter les `Mapped[str]` couplés à `DateTime(...)` (TR-25 Bloc 4, frictions F648, F649, F771).

### Failure mode

Bug typing récurrent. mypy/IDE crash sur `scheduled_date.date()`.

### Implémentation

```python
# tools/check_mapped_datetime.py
"""CI invariant : Mapped[X] couplé DateTime(...) doit avoir X = datetime, jamais str.

Friction prévenue : F648, F649, F771 (TR-25 Bloc 4).
"""
import re
import sys
from pathlib import Path

# Pattern :
#   <name>: Mapped[<type>] = mapped_column(<...>DateTime<...>)
# On veut <type> != "str"
PATTERN = re.compile(
    r"(\w+)\s*:\s*Mapped\[(\w+(?:\s*\|\s*\w+)?(?:\s*\|\s*None)?)\]\s*=\s*mapped_column\([^)]*DateTime[^)]*\)",
    re.MULTILINE
)


def main():
    violations = []
    for py_file in Path("app/models").rglob("*.py"):
        content = py_file.read_text()
        for m in PATTERN.finditer(content):
            field_name = m.group(1)
            type_annotation = m.group(2)
            if "str" in type_annotation:
                # Trouver le numéro de ligne
                line_no = content[:m.start()].count("\n") + 1
                violations.append(f"{py_file}:{line_no}: {field_name}: Mapped[{type_annotation}] = ... DateTime(...)")
    
    if violations:
        print(f"[INVARIANT_FAIL] {len(violations)} Mapped[str] coupled with DateTime():")
        for v in violations:
            print(f"  - {v}")
        print("\nFix: change Mapped[str] -> Mapped[datetime] (or Mapped[datetime | None] if nullable).")
        return 1
    
    print("[INVARIANT_OK] All Mapped[X] with DateTime(...) use proper datetime typing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

## 5. `check_scope_catalog.py`

### But

Tout `Scope.X` utilisé dans le code doit être :
1. Défini dans l'enum `app/permissions/scope.py`
2. Présent dans la table `auth_vertical_scopes` (au moins un vertical)

### Failure mode

Drift entre code et DB → user a un scope dans son JWT mais pas en DB → 403 silencieux.

### Implémentation

```python
# tools/check_scope_catalog.py
"""CI invariant : tout Scope.X utilisé dans le code est défini en enum + en DB.

Friction prévenue : R-8 (architecture-cible.md §6.2.6).
"""
import ast
import re
import sys
from pathlib import Path

SCOPE_ENUM_FILE = Path("app/permissions/scope.py")


def extract_enum_values() -> set[str]:
    """Parse Scope enum and return set of scope strings."""
    tree = ast.parse(SCOPE_ENUM_FILE.read_text())
    values = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Scope":
            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name) and isinstance(stmt.value, ast.Constant):
                            values.add(stmt.value.value)
    return values


def extract_used_scopes() -> set[str]:
    """Parse all `Scope.X` references in app/."""
    used = set()
    pattern = re.compile(r"Scope\.([A-Z][A-Z0-9_]+)")
    for py_file in Path("app").rglob("*.py"):
        content = py_file.read_text()
        for m in pattern.finditer(content):
            used.add(m.group(1))
    return used


def main():
    enum_value_keys = extract_enum_values()  # ex: {"customers:read", "products:write", ...}
    
    # Re-parse pour récupérer les noms d'enum (CUSTOMERS_READ) → string ("customers:read")
    tree = ast.parse(SCOPE_ENUM_FILE.read_text())
    enum_name_to_str = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Scope":
            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name) and isinstance(stmt.value, ast.Constant):
                            enum_name_to_str[target.id] = stmt.value.value
    
    used_names = extract_used_scopes()
    missing = used_names - set(enum_name_to_str.keys())
    
    if missing:
        print(f"[INVARIANT_FAIL] {len(missing)} Scope.X references without enum definition:")
        for s in sorted(missing):
            print(f"  - Scope.{s}")
        print("\nFix: add to app/permissions/scope.py:Scope enum.")
        return 1
    
    # Optionnel : check DB consistency (nécessite connexion DB en CI integration)
    # SELECT DISTINCT scope_name FROM auth_vertical_scopes
    # vs enum_value_keys
    # (skip dans ce script — fait par check_db_scopes_match.py séparément si besoin)
    
    print(f"[INVARIANT_OK] All {len(used_names)} Scope.X references have enum definition")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

## 6. `check_no_brand_code.py`

### But

Aucune occurrence de `brand_code` sur les modèles Catalogue (drop Bloc 7 §7.6 / Q43=B).

### Implémentation

```python
# tools/check_no_brand_code.py
"""CI invariant : aucun brand_code sur Product/Category/Bundle/ProductCollection (Bloc 7 Q43=B).

Friction prévenue : R-5 + Bloc 7 §7.6.
"""
import re
import sys
from pathlib import Path

CATALOGUE_MODELS = [
    "app/models/product.py",
    "app/models/category.py",
    "app/models/bundle.py",
    "app/models/product_collection.py",
]

PATTERNS = [
    re.compile(r"brand_code\s*:\s*Mapped"),
    re.compile(r"X-Brand-Code"),
    re.compile(r"is_multi_brand\s*:\s*Mapped"),
]


def main():
    violations = []
    
    # 1. Models catalogue : pas de brand_code colonne
    for model_path in CATALOGUE_MODELS:
        path = Path(model_path)
        if not path.exists():
            continue
        content = path.read_text()
        for i, line in enumerate(content.splitlines(), 1):
            for pat in PATTERNS:
                if pat.search(line):
                    violations.append(f"{path}:{i}: {line.strip()}")
    
    # 2. Repositories : pas de WHERE brand_code (Catalogue layers)
    for repo_path in [
        "app/repositories/product.py",
        "app/repositories/category.py",
        "app/repositories/bundle.py",
    ]:
        path = Path(repo_path)
        if not path.exists():
            continue
        content = path.read_text()
        for i, line in enumerate(content.splitlines(), 1):
            if "brand_code" in line and not line.strip().startswith("#"):
                violations.append(f"{path}:{i}: {line.strip()}")
    
    # 3. Schemas : pas de brand_code
    for schema_path in [
        "app/schemas/product.py",
        "app/schemas/category.py",
        "app/schemas/bundle.py",
    ]:
        path = Path(schema_path)
        if not path.exists():
            continue
        content = path.read_text()
        for i, line in enumerate(content.splitlines(), 1):
            if "brand_code" in line and not line.strip().startswith("#"):
                violations.append(f"{path}:{i}: {line.strip()}")
    
    # 4. Endpoints : pas de header X-Brand-Code lu
    for ep_file in Path("app/api/v1/endpoints").rglob("*.py"):
        content = ep_file.read_text()
        for i, line in enumerate(content.splitlines(), 1):
            if "X-Brand-Code" in line:
                violations.append(f"{ep_file}:{i}: {line.strip()}")
    
    if violations:
        print(f"[INVARIANT_FAIL] {len(violations)} brand_code/is_multi_brand/X-Brand-Code occurrences:")
        for v in violations:
            print(f"  - {v}")
        print("\nFix: drop these references. Bloc 7 Q43=B verrouille catalogue strictement per-tenant.")
        return 1
    
    print("[INVARIANT_OK] No brand_code/is_multi_brand/X-Brand-Code in catalogue layers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

## 7. `check_audit_action_decorator.py`

### But

Tout service de mutation (`async def update`, `delete`, `create`) a soit `@audit_action(...)` soit un appel explicite `audit_service.log_*` dans le corps.

### Implémentation

```python
# tools/check_audit_action_decorator.py
"""CI invariant : services de mutation auditent leurs actions.

Friction prévenue : F456, F522, F541, F774, F835 (TR-36 Bloc 4) + AuditMiddleware drop Bloc 6.
"""
import ast
import sys
from pathlib import Path

SERVICES_DIR = Path("app/services")

MUTATION_FN_PREFIXES = ("create_", "update_", "delete_", "cancel_", "transit_", "approve_", "reject_", "fulfill_", "encaisser", "annuler", "payer", "valider")

WHITELIST_FUNCTIONS = {
    # Helpers internes qui ne sont pas des mutations métier audits
    "_compute_total", "_calculate_tva", "_internal_helper",
    "create_session_id", "create_test_db",
}


def function_has_audit(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True si la fonction a @audit_action OR appelle audit_service.log_* dans son corps."""
    # 1. Décorateur
    for dec in node.decorator_list:
        if (isinstance(dec, ast.Call)
            and isinstance(dec.func, ast.Name)
            and dec.func.id == "audit_action"):
            return True
        if (isinstance(dec, ast.Call)
            and isinstance(dec.func, ast.Attribute)
            and dec.func.attr == "audit_action"):
            return True
    
    # 2. Appel audit_service.log_* dans le corps
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute):
            if "audit" in sub.attr.lower() and sub.attr.startswith("log_"):
                return True
        if isinstance(sub, ast.Call):
            if isinstance(sub.func, ast.Attribute) and sub.func.attr.startswith("log_"):
                # ex: audit_service.log_action(...)
                if isinstance(sub.func.value, ast.Name) and "audit" in sub.func.value.id.lower():
                    return True
    
    return False


def main():
    violations = []
    for py_file in SERVICES_DIR.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_name = node.name
                if fn_name in WHITELIST_FUNCTIONS or fn_name.startswith("_"):
                    continue
                if any(fn_name.startswith(p) for p in MUTATION_FN_PREFIXES):
                    if not function_has_audit(node):
                        violations.append(f"{py_file}:{node.lineno} {fn_name}: no @audit_action nor audit_service.log_*()")
    
    if violations:
        print(f"[INVARIANT_FAIL] {len(violations)} service mutation functions without audit:")
        for v in violations[:30]:
            print(f"  - {v}")
        if len(violations) > 30:
            print(f"  ... and {len(violations) - 30} more")
        print("\nFix: add @audit_action(entity_type='X') decorator OR explicit audit_service.log_*() call.")
        return 1
    
    print(f"[INVARIANT_OK] All service mutation functions have audit instrumentation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

## 8. `verify_audit_chain.py`

### But

Vérifie l'intégrité de la chaîne HMAC `audit_logs.prev_hmac` (blockchain audit).

### Failure mode

Si chaîne rompue → tampering détecté → alerte AlertManager.

### Différence avec autres scripts

**Pas un check CI sur PR**, mais **job nightly** déclenché par Celery beat.

### Implémentation

```python
# tools/verify_audit_chain.py
"""Job nightly : vérifie intégrité chaîne HMAC audit_logs.

Bloc 6 §6.2.4 (blockchain audit). Détecte tampering.
"""
import asyncio
import hashlib
import hmac
import json
import os
import sys

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.environ["DATABASE_URL"]
HMAC_KEY = os.environ["AUDIT_HMAC_KEY"].encode()


def compute_expected_hmac(prev_hmac: str | None, row: dict, key: bytes) -> str:
    """Reproduit le HMAC qui aurait dû être inséré."""
    canonical = {
        "action": row["action"],
        "entity_type": row["entity_type"],
        "entity_id": row["entity_id"],
        "tenant_id": row["tenant_id"],
        "account_id": row["account_id"],
        "api_key_id": row["api_key_id"],
        "request_id": row["request_id"],
        "changes": row.get("changes_encrypted"),  # bytes ou None
        "description": row.get("description_encrypted"),
        "created_at": row["created_at"].isoformat(),
    }
    msg = (prev_hmac or "") + json.dumps(canonical, sort_keys=True, default=str)
    return hmac.new(key, msg.encode(), hashlib.sha256).hexdigest()


async def main():
    engine = create_async_engine(DATABASE_URL)
    
    async with engine.connect() as conn:
        # Pour chaque tenant_id, lire les rows en ordre chronologique et vérifier la chaîne
        tenants = await conn.execute(text("SELECT DISTINCT tenant_id FROM audit_logs ORDER BY tenant_id"))
        tenant_ids = [r[0] for r in tenants]
        
        breaks = []
        
        for tid in tenant_ids:
            result = await conn.execute(text("""
                SELECT id, tenant_id, action, entity_type, entity_id, account_id, api_key_id,
                       request_id, changes_encrypted, description_encrypted, created_at,
                       prev_hmac, hmac_signature
                FROM audit_logs
                WHERE tenant_id = :tid
                ORDER BY id
            """), {"tid": tid})
            
            previous_hmac = None
            for row in result.mappings():
                expected = compute_expected_hmac(previous_hmac, dict(row), HMAC_KEY)
                if row["hmac_signature"] != expected:
                    breaks.append({
                        "tenant_id": tid,
                        "audit_id": row["id"],
                        "expected_hmac": expected,
                        "actual_hmac": row["hmac_signature"],
                        "previous_hmac_used": previous_hmac,
                    })
                
                # Vérifier prev_hmac aussi
                if row["prev_hmac"] != previous_hmac:
                    breaks.append({
                        "tenant_id": tid,
                        "audit_id": row["id"],
                        "issue": "prev_hmac mismatch with last row",
                        "expected_prev": previous_hmac,
                        "actual_prev": row["prev_hmac"],
                    })
                
                previous_hmac = row["hmac_signature"]
    
    if breaks:
        print(f"[INVARIANT_FAIL] Audit chain integrity broken: {len(breaks)} issue(s):")
        for b in breaks[:10]:
            print(f"  - {b}")
        if len(breaks) > 10:
            print(f"  ... and {len(breaks) - 10} more")
        # Send alert AlertManager / Slack
        # (à intégrer avec ops alerting)
        return 1
    
    print(f"[INVARIANT_OK] Audit chain intact across {len(tenant_ids)} tenants")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

---

## 9. `check_ledger_immutable_triggers.py`

### But

Vérifie que les triggers DB `BEFORE UPDATE/DELETE → RAISE EXCEPTION` existent sur les tables ledger.

### Failure mode

Un dev oublie d'ajouter le trigger dans une migration → table ledger devient mutable silencieusement.

### Implémentation

```python
# tools/check_ledger_immutable_triggers.py
"""CI invariant : triggers immutability présents sur tables ledger.

Friction prévenue : TR-7 Bloc 3 (DB triggers ledger immutability).
"""
import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.environ.get("DATABASE_URL_TEST", os.environ["DATABASE_URL"])

REQUIRED_LEDGER_TRIGGERS = [
    ("points_ledger", "trg_points_ledger_immutable"),
    ("revenue_ledger", "trg_revenue_ledger_immutable"),
    ("payment_ledger", "trg_payment_ledger_immutable"),
    ("audit_logs", "trg_audit_logs_immutable"),
    ("epicerie_stock_movements", "trg_epicerie_stock_movements_immutable"),
    ("mouvements_stock_restaurant", "trg_mouvements_stock_restaurant_immutable"),
    ("inventory_movements", "trg_inventory_movements_immutable"),
]


async def main():
    engine = create_async_engine(DATABASE_URL)
    
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT event_object_table, trigger_name
            FROM information_schema.triggers
            WHERE trigger_schema = 'public'
              AND event_manipulation IN ('UPDATE', 'DELETE')
        """))
        existing = {(r[0], r[1]) for r in result}
    
    missing = []
    for table, trigger in REQUIRED_LEDGER_TRIGGERS:
        # Le trigger fire sur UPDATE et DELETE (ou il y a 2 entrées en information_schema)
        if (table, trigger) not in existing:
            missing.append((table, trigger))
    
    if missing:
        print(f"[INVARIANT_FAIL] {len(missing)} ledger immutability triggers missing:")
        for t, tr in missing:
            print(f"  - {t}: {tr}")
        print("\nFix: see 50-sql-schema.md §14.1 + 51-alembic-migrations.md.")
        return 1
    
    print(f"[INVARIANT_OK] All ledger immutability triggers present")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

---

## 10. `check_celery_tenant_arg.py`

### But

Toute `@celery_app.task` qui touche une table tenant-scoped (TenantMixin) DOIT avoir un argument `tenant_id`.

### Failure mode

Friction F960 : ETL Celery sans `tenant_id` arg → forge possible cross-tenant.

### Implémentation

```python
# tools/check_celery_tenant_arg.py
"""CI invariant : Celery task qui touche TenantMixin tables doit avoir tenant_id arg.

Friction prévenue : F960 (Bloc 5 §5.2.8).
"""
import ast
import re
import sys
from pathlib import Path

TASKS_DIR = Path("app/tasks")
MODELS_DIR = Path("app/models")

# Whitelist tasks qui n'ont pas de tenant_id (global infra)
WHITELIST = {
    "debug_task",
    "outbox_dispatcher_task",
    "verify_audit_chain_task",
    "purge_audit_logs_older_than_7y_task",
    "beat_heartbeat_task",
    "refresh_rfm_view_task",
    "refresh_stock_view_task",
}


def get_tenant_scoped_models() -> set[str]:
    """Identifie les models avec TenantMixin."""
    models = set()
    for py_file in MODELS_DIR.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "TenantMixin":
                        models.add(node.name)
                    elif isinstance(base, ast.Attribute) and base.attr == "TenantMixin":
                        models.add(node.name)
    return models


def task_function_uses_tenant_models(node: ast.FunctionDef, tenant_models: set[str]) -> bool:
    """Heuristique : la fonction référence-t-elle un model tenant-scoped ?"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in tenant_models:
            return True
        if isinstance(sub, ast.Attribute) and sub.attr in tenant_models:
            return True
    return False


def task_has_tenant_id_arg(node: ast.FunctionDef) -> bool:
    """Vérifie que la fonction a un arg 'tenant_id'."""
    args = [a.arg for a in node.args.args + node.args.kwonlyargs]
    return "tenant_id" in args


def main():
    tenant_models = get_tenant_scoped_models()
    if not tenant_models:
        print("[INVARIANT_WARNING] No tenant-scoped models found — skipping check")
        return 0
    
    violations = []
    for py_file in TASKS_DIR.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            
            # Doit être décoré @celery_app.task
            is_task = False
            for dec in node.decorator_list:
                if (isinstance(dec, ast.Call)
                    and isinstance(dec.func, ast.Attribute)
                    and dec.func.attr == "task"):
                    is_task = True
                    break
            if not is_task:
                continue
            
            if node.name in WHITELIST:
                continue
            
            if task_function_uses_tenant_models(node, tenant_models):
                if not task_has_tenant_id_arg(node):
                    violations.append(f"{py_file}:{node.lineno} {node.name}: touches tenant-scoped models but no tenant_id arg")
    
    if violations:
        print(f"[INVARIANT_FAIL] {len(violations)} Celery tasks without tenant_id arg:")
        for v in violations:
            print(f"  - {v}")
        print("\nFix: add `tenant_id: int` arg + assert against entity.tenant_id.")
        print("Whitelist tasks (global infra) documented in tools/check_celery_tenant_arg.py:WHITELIST.")
        return 1
    
    print(f"[INVARIANT_OK] All Celery tasks touching tenant-scoped models have tenant_id arg")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

## 11-15. Scripts complémentaires (squelettes)

### 11. `check_no_userpcompat.py`

```python
"""CI invariant : aucun import UserCompat (supprimé Bloc 1 §1.2.1)."""
import re, sys
from pathlib import Path

PATTERN = re.compile(r"\bUserCompat\b")

def main():
    violations = []
    for py_file in Path("app").rglob("*.py"):
        for i, line in enumerate(py_file.read_text().splitlines(), 1):
            if PATTERN.search(line) and not line.strip().startswith("#"):
                violations.append(f"{py_file}:{i}: {line.strip()}")
    if violations:
        print(f"[INVARIANT_FAIL] {len(violations)} UserCompat references:")
        for v in violations: print(f"  - {v}")
        print("\nFix: replace with Account or Principal Protocol.")
        return 1
    print("[INVARIANT_OK] No UserCompat references")
    return 0

if __name__ == "__main__": sys.exit(main())
```

### 12. `check_no_sync_db_in_async_handler.py`

```python
"""CI invariant : pas de sync session DB dans handlers async."""
import ast, sys
from pathlib import Path

# Heuristique : async def + appel à get_db() sync ou .query() ORM 1.x
# Implémentation similaire AST-walk
```

### 13. `check_rls_enabled_on_tenant_tables.py`

```python
"""CI invariant : toute table avec colonne tenant_id a RLS enabled.

Query :
  SELECT t.tablename, c.relrowsecurity
  FROM information_schema.columns col
  JOIN pg_class c ON c.relname = col.table_name
  JOIN pg_tables t ON t.tablename = col.table_name
  WHERE col.column_name = 'tenant_id'
    AND col.table_schema = 'public';

Failed if any tenant_id column on table without rowsecurity=true.
"""
```

### 14. `check_fsm_transitions_present.py`

```python
"""CI invariant : toute table FSM-aware a sa matrice dans fsm_transitions.

Liste tables FSM-aware codée en dur :
  - devis, reservations, deposits, invoices, ventes, relances
  - epicerie_ventes, restaurant_commandes, lignes_commande_restaurant
  - etl_imports, etl_conflicts, internal_transfers, transfer_requests
  - stock_items
  - feature_flags (no FSM mais audit existant)

Pour chaque, query :
  SELECT COUNT(*) FROM fsm_transitions WHERE table_name = '<x>'
  
Si count = 0 → fail.
"""
```

### 15. `check_alembic_downgrade_implemented.py`

```python
"""CI invariant : toute migration Alembic a downgrade() non-vide.

Parse alembic/versions/*.py
Pour chaque, vérifier :
  - def downgrade() existe
  - corps n'est pas juste `pass` ou `# ...`
  - sinon : violation

Friction prévenue : convention 02-conventions.md §1.4.
"""
import ast, sys
from pathlib import Path

VERSIONS = Path("alembic/versions")

def main():
    violations = []
    for py_file in VERSIONS.glob("*.py"):
        if py_file.name == "__init__.py": continue
        tree = ast.parse(py_file.read_text())
        downgrade_fn = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "downgrade":
                downgrade_fn = node
                break
        if downgrade_fn is None:
            violations.append(f"{py_file}: no downgrade() function")
            continue
        # Vérifier corps non-trivial
        body_meaningful = False
        for stmt in downgrade_fn.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                continue  # docstring
            if isinstance(stmt, ast.Pass):
                continue
            body_meaningful = True
            break
        if not body_meaningful:
            violations.append(f"{py_file}: downgrade() is empty/pass-only")
    
    if violations:
        print(f"[INVARIANT_FAIL] {len(violations)} migrations with empty downgrade():")
        for v in violations: print(f"  - {v}")
        print("\nFix: implement downgrade() reverse logic. If irreversible, document explicitly with TODO + raise NotImplementedError + comment.")
        return 1
    print("[INVARIANT_OK] All migrations have non-empty downgrade()")
    return 0

if __name__ == "__main__": sys.exit(main())
```

### 16. `check_middleware_order.py` (F111 — vague 3)

```python
"""CI invariant : RequestContextMiddleware doit être appliqué avant
les middlewares qui consomment request.state (RateLimit, AppEnforcement,
SecurityHeaders, CSRFProtection, Metrics).

Rappel FastAPI : add_middleware() est LIFO. Le DERNIER ajouté s'exécute
EN PREMIER (outermost). Donc RequestContextMiddleware doit être ajouté
APRÈS les middlewares qui en dépendent dans le code main.py.

Friction prévenue : F111 (cf. 04-middleware.md §2.1) — RequestContextMiddleware
en pos 12 → request.state.tenant_id / api_key_id non peuplés pour 10
middlewares amont → rate-limit identity inopérant.
"""
import ast, sys
from pathlib import Path

CONSUMERS_OF_REQUEST_STATE = {
    "RateLimitMiddleware",
    "AppEnforcementMiddleware",
    "SecurityHeadersMiddleware",
    "CSRFProtectionMiddleware",
    "MetricsMiddleware",
}

def main():
    main_py = Path("app/main.py")
    if not main_py.exists():
        print("[INVARIANT_SKIP] app/main.py not found")
        return 0

    tree = ast.parse(main_py.read_text())
    add_middleware_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "add_middleware" and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Name):
                    add_middleware_calls.append((node.lineno, arg.id))

    # Position de RequestContextMiddleware vs ses consommateurs
    # LIFO : RequestContextMiddleware doit être ajouté APRÈS (lineno > consumers)
    rc_line = next(
        (line for line, name in add_middleware_calls if name == "RequestContextMiddleware"),
        None
    )
    if rc_line is None:
        print("[INVARIANT_FAIL] RequestContextMiddleware not registered in main.py")
        return 1

    violations = []
    for line, name in add_middleware_calls:
        if name in CONSUMERS_OF_REQUEST_STATE and line > rc_line:
            # consumer ajouté APRÈS RequestContext = consumer s'exécute AVANT (LIFO) → request.state vide
            violations.append((name, line, rc_line))

    if violations:
        print("[INVARIANT_FAIL] Middlewares consumming request.state are added AFTER RequestContextMiddleware (LIFO order = they run BEFORE):")
        for name, consumer_line, rc_line in violations:
            print(f"  - {name} (main.py:{consumer_line}) added after RequestContextMiddleware (main.py:{rc_line})")
        print("\nFix: Move app.add_middleware(RequestContextMiddleware, ...) to be AFTER all consumers in code (LIFO = first to run).")
        return 1

    print(f"[INVARIANT_OK] RequestContextMiddleware (line {rc_line}) ordered before {len(CONSUMERS_OF_REQUEST_STATE)} consumers (LIFO).")
    return 0

if __name__ == "__main__": sys.exit(main())
```

### 17. `check_audit_entity_types.py` (F1004 — vague 3)

```python
"""CI invariant : tout `@audit_action(entity_type='X', ...)` utilise
une valeur de l'enum EntityType (catalogue centralisé).

Friction prévenue : F1004 (cf. 31-audit-log.md §F1004) — `_singularize_entity_type`
heuristique → entity_type drift dans audit (ex: 'Vente' vs 'VenteEpicerie').
Audit RGPD Art.15 (export) ne peut pas filtrer correctement.

Préalable : `app/constants/audit.py` exporte `class EntityType(StrEnum)` avec
toutes les entités auditables (~40 valeurs).
"""
import ast, sys
from pathlib import Path

def load_entity_type_enum():
    """Lit la définition de EntityType depuis app/constants/audit.py."""
    audit_constants = Path("app/constants/audit.py")
    if not audit_constants.exists():
        return None
    tree = ast.parse(audit_constants.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "EntityType":
            return {
                stmt.targets[0].id
                for stmt in node.body
                if isinstance(stmt, ast.Assign) and isinstance(stmt.targets[0], ast.Name)
            }
    return None

def find_audit_action_calls(directory: Path):
    """Trouve tous les @audit_action(entity_type=...) dans le code."""
    for py_file in directory.rglob("*.py"):
        if "/tests/" in str(py_file) or "/migrations/" in str(py_file):
            continue
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "audit_action":
                for kw in node.keywords:
                    if kw.arg == "entity_type" and isinstance(kw.value, ast.Constant):
                        yield (py_file, node.lineno, kw.value.value)

def main():
    valid_types = load_entity_type_enum()
    if valid_types is None:
        print("[INVARIANT_FAIL] app/constants/audit.py:EntityType enum not found. Define it before enabling this check.")
        return 1

    violations = []
    for py_file, line, value in find_audit_action_calls(Path("app/services")):
        if value not in valid_types:
            violations.append((py_file, line, value))

    if violations:
        print(f"[INVARIANT_FAIL] {len(violations)} @audit_action calls with entity_type not in EntityType enum:")
        for py_file, line, value in violations:
            print(f"  - {py_file}:{line} entity_type='{value}'")
        print(f"\nValid values: {sorted(valid_types)}")
        print("\nFix: Either add the value to EntityType enum or correct the @audit_action call.")
        return 1

    print("[INVARIANT_OK] All @audit_action calls use valid EntityType enum values")
    return 0

if __name__ == "__main__": sys.exit(main())
```

### 18. `check_no_unawaited_async.py` (F255, F05 — vague 3)

```python
"""CI invariant : pas d'appel à fonction async sans await dans handler async.

Détecte les patterns du type :
    async def handler(...):
        result = some_async_method(...)   # ⚠️ coroutine perdue
        return result

Friction prévenue : F255 (provisioning.py:140,159,179,180 — redis_sec.* sans await),
F05 (cache_invalidate appelle async sans await — décorateur sync wrappant async).

Heuristique : pour chaque `async def`, walker l'AST et détecter les appels
à des callables connus comme async (whitelist : redis_sec.*, cache.*, db.execute,
service.* qui sont async). Si le résultat n'est pas wrappé dans `await`,
`asyncio.create_task()`, `asyncio.ensure_future()` → violation.

Approche pragmatique : whitelist d'objets async-only (redis_sec, redis_cache,
audit_service, etc.) + check que tous les appels sur ces objets dans un
async def sont précédés de `await` ou wrappés.
"""
import ast, sys
from pathlib import Path

# Objets connus comme exposant uniquement des méthodes async
ASYNC_ONLY_OBJECTS = {
    "redis_sec",
    "redis_cache",
    "redis_general",
    "audit_service",
    "outbox_service",
    "kms_client",
    "email_gateway",
}

class UnawaitedAsyncDetector(ast.NodeVisitor):
    def __init__(self):
        self.violations = []
        self.in_async_func = False
        self.current_file = None

    def visit_AsyncFunctionDef(self, node):
        prev = self.in_async_func
        self.in_async_func = True
        self.generic_visit(node)
        self.in_async_func = prev

    def visit_FunctionDef(self, node):
        prev = self.in_async_func
        self.in_async_func = False
        self.generic_visit(node)
        self.in_async_func = prev

    def visit_Expr(self, node):
        # Expression statement (call non-awaited utilisé comme statement)
        if self.in_async_func and isinstance(node.value, ast.Call):
            self._check_call(node.value, node.lineno, awaited=False)
        self.generic_visit(node)

    def visit_Assign(self, node):
        # x = some_async_call() — sans await → on récupère une coroutine
        if self.in_async_func and isinstance(node.value, ast.Call):
            self._check_call(node.value, node.lineno, awaited=False)
        self.generic_visit(node)

    def visit_Await(self, node):
        # Marque les appels awaitedés comme OK (pas besoin de descendre dans .value)
        return  # skip — l'appel sous-jacent est awaité

    def _check_call(self, call_node, lineno, awaited):
        if awaited:
            return
        # Pattern : redis_sec.method(...)
        if isinstance(call_node.func, ast.Attribute):
            obj = call_node.func.value
            if isinstance(obj, ast.Name) and obj.id in ASYNC_ONLY_OBJECTS:
                self.violations.append((self.current_file, lineno, f"{obj.id}.{call_node.func.attr}"))


def main():
    detector = UnawaitedAsyncDetector()
    for py_file in Path("app").rglob("*.py"):
        if "/migrations/" in str(py_file) or "/tests/" in str(py_file):
            continue
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        detector.current_file = py_file
        detector.visit(tree)

    if detector.violations:
        print(f"[INVARIANT_FAIL] {len(detector.violations)} async calls without await in async handlers:")
        for f, line, call in detector.violations:
            print(f"  - {f}:{line} → {call}() (likely missing `await`)")
        print("\nFix: prefix with `await` or wrap in asyncio.create_task() if fire-and-forget.")
        return 1

    print(f"[INVARIANT_OK] No unawaited async calls in {len(ASYNC_ONLY_OBJECTS)} known async objects.")
    return 0

if __name__ == "__main__": sys.exit(main())
```

### 19. `check_token_creator_passes_db.py` (F329 — vague 4)

```python
"""CI invariant : tout call-site de `get_role_scopes(role, db)` doit passer `db != None`.

Friction prévenue : F329 — `app/services/token.py:49` appelait `get_role_scopes(role, None)`
→ branche fallback ROLE_SCOPES_FALLBACK hardcodée systématiquement → la table
auth_role_scopes n'était JAMAIS lue → Sprint B2.S3 livrable sans effet (placebo).

Sans ce check : risque que B2.S3 soit déclaré done alors que le RBAC reste hardcodé.
"""
import ast, sys
from pathlib import Path


def find_get_role_scopes_calls(directory: Path):
    """Trouve tous les `get_role_scopes(...)` dans le code service."""
    for py_file in directory.rglob("*.py"):
        if "/tests/" in str(py_file):
            continue
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute)):
                func_name = (
                    node.func.id if isinstance(node.func, ast.Name)
                    else node.func.attr
                )
                if func_name == "get_role_scopes":
                    yield (py_file, node.lineno, node)


def main():
    violations = []
    for py_file, line, call in find_get_role_scopes_calls(Path("app")):
        # Vérifier que le 2ème argument (db) n'est pas None constant
        db_arg = None
        if len(call.args) >= 2:
            db_arg = call.args[1]
        else:
            for kw in call.keywords:
                if kw.arg == "db":
                    db_arg = kw.value
                    break

        if db_arg is None:
            violations.append(f"{py_file}:{line} → get_role_scopes(...) sans argument `db` explicite")
        elif isinstance(db_arg, ast.Constant) and db_arg.value is None:
            violations.append(f"{py_file}:{line} → get_role_scopes(..., db=None) — fallback permanent F329")

    if violations:
        print(f"[INVARIANT_FAIL] {len(violations)} call-sites get_role_scopes avec db=None (F329) :")
        for v in violations:
            print(f"  - {v}")
        print("\nFix : passer la session AsyncSession active. Sprint B2.S3 dépend de ce fix.")
        return 1

    print("[INVARIANT_OK] All get_role_scopes() calls pass non-None db argument")
    return 0


if __name__ == "__main__": sys.exit(main())
```

### 20. `check_no_mfa_bypass_oauth.py` (F404 — vague 5)

```python
"""CI invariant : OAuth callbacks doivent appeler mfa_service.is_enrolled() avant émission tokens.

Friction prévenue : F404 — `oauth.py:296` `mfa_verified=False` hardcodé permettait
à un user MFA-enrôlé de bypass MFA via login Google/Microsoft.

Heuristique : pour chaque fonction async dans `app/api/v1/endpoints/oauth*.py` ou
`app/services/oauth*.py` qui retourne TokenOut/MFARequiredResponse, vérifier qu'il y a
un appel `mfa_service.is_enrolled` ou équivalent dans le call-graph.
"""
import ast, sys
from pathlib import Path


OAUTH_FILES = [
    "app/api/v1/endpoints/oauth.py",
    "app/services/oauth_v2.py",
]

# Fonctions qui doivent contenir un check MFA gate avant émission tokens
TOKEN_EMITTING_FUNCTIONS = {
    "_issue_oauth_tokens",
    "_open_session_and_issue",
}

REQUIRED_CHECK_PATTERNS = {
    "mfa_service.is_enrolled",
    "mfa_service.is_mfa_enabled",
    "is_mfa_required_for_account",
}


class MFAGateChecker(ast.NodeVisitor):
    def __init__(self):
        self.violations = []
        self.current_file = None

    def visit_AsyncFunctionDef(self, node):
        if node.name in TOKEN_EMITTING_FUNCTIONS:
            # Walker les appels dans le corps
            calls_made = set()
            for sub_node in ast.walk(node):
                if isinstance(sub_node, ast.Call) and isinstance(sub_node.func, ast.Attribute):
                    # Construire le chemin attribute (ex: mfa_service.is_enrolled)
                    if isinstance(sub_node.func.value, ast.Name):
                        path = f"{sub_node.func.value.id}.{sub_node.func.attr}"
                        calls_made.add(path)

            if not (calls_made & REQUIRED_CHECK_PATTERNS):
                self.violations.append(
                    f"{self.current_file}:{node.lineno} {node.name}() émet tokens sans vérifier MFA enrôlement"
                )
        self.generic_visit(node)


def main():
    checker = MFAGateChecker()
    for filepath in OAUTH_FILES:
        path = Path(filepath)
        if not path.exists():
            continue
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        checker.current_file = filepath
        checker.visit(tree)

    if checker.violations:
        print(f"[INVARIANT_FAIL] {len(checker.violations)} OAuth flows sans MFA gate (F404) :")
        for v in checker.violations:
            print(f"  - {v}")
        print("\nFix : avant TokenOut, appeler `await mfa_service.is_enrolled(account_id)`."
              "\nSi True → retourner MFARequiredResponse au lieu des tokens.")
        return 1

    print("[INVARIANT_OK] All OAuth token-emitting functions check MFA enrollment")
    return 0


if __name__ == "__main__": sys.exit(main())
```

### 21. `check_pii_columns_encrypted.py` (V5-P0-01 — vague 5)

```python
"""CI invariant : toute colonne sémantiquement PII a son pendant `_encrypted` BYTEA.

Friction prévenue : V5-P0-01 — B4.S5 chiffrait `notes` seul. Le périmètre PII Customer
inclut phone, address, first_name, last_name (commerciaux y stockent typiquement
numéro perso, anniversaire, allergies = données de santé RGPD Art.9).

Liste des paires (table, column_pii) — à étendre lors de l'ajout de nouveaux modèles.
"""
import sys
import psycopg2
import os


PII_COLUMNS = [
    ("customers", "phone"),
    ("customers", "address"),
    ("customers", "first_name"),
    ("customers", "last_name"),
    ("customers", "notes"),
    ("accounts", "email"),  # Possiblement pseudonyme — à confirmer DPO
    # Ajouter d'autres modèles : EventIncident.notes, etc.
]


def main():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    violations = []
    for table, col in PII_COLUMNS:
        # Vérifie présence colonne plain text
        cur.execute("""
            SELECT data_type FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s
        """, (table, col))
        plain_text = cur.fetchone()

        # Vérifie présence pendant `_encrypted`
        cur.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s
        """, (table, f"{col}_encrypted"))
        encrypted_exists = cur.fetchone() is not None

        if plain_text and not encrypted_exists:
            # Colonne plain text sans pendant encrypted → violation
            violations.append(f"{table}.{col} ({plain_text[0]}) sans {col}_encrypted")

    cur.close()
    conn.close()

    if violations:
        print(f"[INVARIANT_FAIL] {len(violations)} colonnes PII sans chiffrement (RGPD Art.25) :")
        for v in violations:
            print(f"  - {v}")
        print("\nFix : étendre Sprint B4.S5 pour chiffrer ces colonnes (cf. 50-sql-schema.md §4).")
        return 1

    print(f"[INVARIANT_OK] Toutes les {len(PII_COLUMNS)} colonnes PII répertoriées ont leur pendant chiffré.")
    return 0


if __name__ == "__main__": sys.exit(main())
```

### 22. `check_no_sync_httpx_in_async.py` (F1091 — vague 6)

```python
"""CI invariant : pas de httpx.Client (sync) dans handlers async.

Friction prévenue : F1091 — `app/services/wireguard_client.py:66,107` utilisait
`with httpx.Client(...)` synchrone. Les handlers VPN sync exécutaient dans
threadpool uvicorn → 1 thread bloqué par appel × timeout 10s → exhaustion pool
sous charge.
"""
import ast, sys
from pathlib import Path


class SyncHttpxDetector(ast.NodeVisitor):
    def __init__(self):
        self.violations = []
        self.current_file = None

    def visit_With(self, node):
        # Pattern : with httpx.Client(...) as client:
        for item in node.items:
            ctx = item.context_expr
            if isinstance(ctx, ast.Call) and isinstance(ctx.func, ast.Attribute):
                if (isinstance(ctx.func.value, ast.Name) and ctx.func.value.id == "httpx"
                    and ctx.func.attr == "Client"):
                    self.violations.append(
                        f"{self.current_file}:{node.lineno} `with httpx.Client(...)` sync — utiliser AsyncClient"
                    )
        self.generic_visit(node)


def main():
    detector = SyncHttpxDetector()
    for py_file in Path("app").rglob("*.py"):
        if "/tests/" in str(py_file) or "/migrations/" in str(py_file):
            continue
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        detector.current_file = py_file
        detector.visit(tree)

    if detector.violations:
        print(f"[INVARIANT_FAIL] {len(detector.violations)} httpx.Client sync (F1091) :")
        for v in detector.violations:
            print(f"  - {v}")
        print("\nFix : remplacer par `httpx.AsyncClient` + `async with` + handler `async def`.")
        return 1

    print("[INVARIANT_OK] No sync httpx.Client found in app/")
    return 0


if __name__ == "__main__": sys.exit(main())
```

### 23. `check_metrics_tenant_label.py` (F83/F84/F1128 — vagues 5+)

```python
"""CI invariant : tous les Counter/Histogram HTTP exposent un label `app_code`.

Friction prévenue : F83/F84/F1128 — métriques Prometheus sans label tenant
→ impossible de répondre 'combien de req/s pour Marveline ?' + rate-limit
cross-tenant collision.
"""
import ast, sys
from pathlib import Path


METRICS_CLASSES = {"Counter", "Histogram", "Gauge", "Summary"}

REQUIRED_LABEL = "app_code"


def find_metrics_definitions(directory: Path):
    for py_file in directory.rglob("*.py"):
        if "/tests/" in str(py_file):
            continue
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in METRICS_CLASSES:
                    # Extraire le kwarg `labelnames=[...]`
                    labelnames = None
                    for kw in node.keywords:
                        if kw.arg == "labelnames" and isinstance(kw.value, ast.List):
                            labelnames = [
                                e.value for e in kw.value.elts
                                if isinstance(e, ast.Constant)
                            ]
                    yield (py_file, node.lineno, node.func.id, labelnames)


# Whitelist : métriques qui n'ont pas vocation à être tenant-scopées (ex: infra globale)
WHITELIST_PATTERNS = {
    "celery_workers_active",       # global broker
    "db_pool_connections",         # global pool
    "process_resident_memory",     # OS-level
    "python_gc_objects",           # runtime
}


def main():
    violations = []
    for py_file, line, cls_name, labelnames in find_metrics_definitions(Path("app")):
        if labelnames is None:
            # Métrique sans labelnames du tout — probablement infra globale, OK
            continue
        # Heuristique : nom de variable / contexte HTTP
        # Pour l'instant, on flague si la métrique a au moins 1 label mais pas app_code
        # ET si le fichier contient "http" ou "request"
        file_str = str(py_file).lower()
        is_http_metric = "http" in file_str or "metrics.py" in file_str or "request" in file_str
        if is_http_metric and REQUIRED_LABEL not in labelnames:
            violations.append(
                f"{py_file}:{line} {cls_name}(labelnames={labelnames}) — manque '{REQUIRED_LABEL}'"
            )

    if violations:
        print(f"[INVARIANT_FAIL] {len(violations)} métriques HTTP sans label tenant (F83/F84) :")
        for v in violations:
            print(f"  - {v}")
        print("\nFix : ajouter 'app_code' à labelnames + populer depuis request.state.app_code.")
        return 1

    print("[INVARIANT_OK] All HTTP metrics expose 'app_code' label")
    return 0


if __name__ == "__main__": sys.exit(main())
```

---

## Stratégie d'introduction graduelle

**Sprint 1 (PROD FIRE-DRILL)** : aucun script CI nouveau (focus prod).

**Bloc 1 (Foundations)** : intro `check_no_userpcompat.py` + `check_alembic_downgrade_implemented.py` + `check_mapped_datetime.py` + **`check_middleware_order.py`** (F111) + **`check_no_unawaited_async.py`** (F255, F05) + **`check_no_sync_httpx_in_async.py`** (F1091) + **`check_token_creator_passes_db.py`** (F329 — pré-requis B2.S3 — refuser merge si call-site `get_role_scopes(role, None)`).

**Bloc 2 (Identity)** : intro `check_endpoint_scopes.py` + `check_scope_catalog.py` + `check_no_sync_db_in_async_handler.py` + **`check_no_mfa_bypass_oauth.py`** (F404 — refuser merge si OAuth flow émet token sans appel `mfa_service.is_enrolled`).

**Bloc 3 (Money)** : intro `check_no_finance_legacy.py` + `check_ledger_immutable_triggers.py` + `check_audit_action_decorator.py`.

**Bloc 4 (Catalogue)** : intro **`check_pii_columns_encrypted.py`** (V5-P0-01 — refuser merge si nouvelle colonne PII Customer sans pendant `_encrypted`).

**Bloc 5 (Multi-app)** : intro `check_celery_tenant_arg.py` + `check_celery_queues.py`.

**Bloc 6 (Cross-cutting)** : intro `verify_audit_chain.py` (job nightly) + `check_rls_enabled_on_tenant_tables.py` + **`check_audit_entity_types.py`** (F1004 — préalable : EntityType enum dans `app/constants/audit.py`) + **`check_metrics_tenant_label.py`** (F83/F84/F1128 — refuser métriques HTTP sans label `app_code`).

**Bloc 7 (Sémantique DEVUP)** : intro `check_no_brand_code.py` + `check_fsm_transitions_present.py`.

**Approche graduelle** : à chaque sprint, le script CI passe sur le périmètre de ce sprint (sans bloquer le reste). Activation globale en fin de bloc.

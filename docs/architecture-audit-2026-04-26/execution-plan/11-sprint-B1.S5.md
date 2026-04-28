# Sprint B1.S5 — Constants éclatées + observability/

> **STATUT** : ⏳ À démarrer après B1.S4
> **DURÉE MAX** : 2 semaines
> **OWNER** : Dev1
> **BLOQUE** : B6.S6 (observability mTLS — dépend de constants/observability/)
> **DÉPEND DE** : B1.S4 (`SENSITIVE_FIELDS` étendu)
> **OBJECTIF** : Éclater le module monolithique `app/constants/__init__.py` en sous-modules par domaine. Créer `app/observability/` pour métriques/tracing/logging structuré.

## Vue d'ensemble

| Story | Description | Estimation | Bloque |
|---|---|---|---|
| **B1.S5.T1** | Éclater `constants/` (business, errors, http, limits, security) | 1 j | T2-T3 |
| **B1.S5.T2** | Créer `observability/metrics.py` avec labels `app_code` (F83/F84) | 1.5 j | B6.S6 |
| **B1.S5.T3** | BaseSchema + ErrorResponse aligné middleware (F232/F233 vague 6) | 1 j | aucun |
| **B1.S5.T4** | Linter CI BaseSchema (`check_basemodel_field_strict.py`) | 0.5 j | aucun |

**Total effort** : 4 jours-homme.

---

# Story B1.S5.T1 — Éclater `app/constants/`

## Contexte

**Convention** : `02-conventions.md` + CLAUDE.md "Constantes : `app/constants/` (jamais de strings hardcodées)"

### Description

Aujourd'hui : `app/constants/__init__.py` monolithique ~800 lignes. Convention cible : 1 fichier par domaine.

## Solution

```
app/constants/
├── __init__.py           # Re-export selectif pour rétro-compat
├── business.py           # JWT_AUDIENCES, RateLimitScope, AuthEndpoints
├── errors.py             # codes erreur métier (DEVUP_*, RESA_*, etc.)
├── http.py               # HTTPMethods, HTTPStatusReasons, PATH_NORMALIZATION_PATTERNS
├── limits.py             # RATE_LIMIT_*, MAX_REQUEST_SIZE, GZIP_MIN_SIZE
├── security.py           # MFAConfig, JWT_*, ARGON2_*, MAX_LOGIN_ATTEMPTS
├── audit.py              # NEW (B6.S2) : EntityType enum (F1004)
├── loyalty.py            # MAX_LOYALTY_MULTIPLIER, LOYALTY_DAILY_EARN_CAP
└── tenants.py            # DEFAULT_DEPOSIT_PCT, DEVIS_DEFAULT_EXPIRY_DAYS
```

## Definition of Done

- [ ] Fichiers créés, re-exports `__init__.py` opérationnels
- [ ] 0 régression import (tests CI verts)
- [ ] Documentation `02-conventions.md` mise à jour avec liste domaines

---

# Story B1.S5.T2 — `observability/metrics.py` avec labels app_code

## Contexte

**Friction** : F83 (vague 5) — `http_requests_total{method, path, status}` sans label tenant

### Description

Centraliser les définitions Prometheus dans `app/observability/metrics.py` avec convention systematic du label `app_code`.

## Solution

```python
# app/observability/metrics.py
from prometheus_client import Counter, Histogram

# F83 fix : label app_code obligatoire sur métriques HTTP
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    labelnames=["method", "path", "status", "app_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    labelnames=["method", "path", "app_code"],
    buckets=(0.01, 0.05, 0.1, 0.2, 0.5, 1, 2, 5),
)

# Métriques rate-limit (par tenant_bucket pour limiter cardinalité)
rate_limit_exceeded_total = Counter(
    "rate_limit_exceeded_total",
    "Rate limit exceeded events",
    labelnames=["scope", "tenant_bucket"],  # bucket : "marveline" | "splendid" | ... | "other"
)
```

```python
# app/middleware/metrics.py (refacto)
class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        path = self._normalize_path(request.url.path)
        # F83 fix : populer app_code depuis request.state (B1.S1.T4 fix)
        app_code = getattr(request.state, "app_code", "unknown")

        http_requests_total.labels(
            method=request.method,
            path=path,
            status=str(response.status_code),
            app_code=app_code,
        ).inc()
        http_request_duration_seconds.labels(
            method=request.method,
            path=path,
            app_code=app_code,
        ).observe(duration)

        return response
```

## Definition of Done

- [ ] `app/observability/metrics.py` centralisé
- [ ] Label `app_code` sur toutes métriques HTTP
- [ ] CI invariant `check_metrics_tenant_label.py` (54 §23) vert
- [ ] Dashboards Grafana mis à jour avec filtre `app_code`

---

# Story B1.S5.T3 — BaseSchema + ErrorResponse (F232/F233)

## Contexte

**Frictions** : F232 (Decimal→float perte précision), F233 (ErrorResponse divergent middleware vs schema)

### Description

```python
# app/schemas/base.py (refacto)
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base Pydantic 2 — config commune DEVUP."""
    model_config = ConfigDict(
        # F232 fix : Decimal préservé (pas converti en float)
        json_encoders={Decimal: str},
        # Strict types
        strict=True,
        # Reject extra fields by default
        extra="forbid",
        # ORM mode
        from_attributes=True,
    )


class ErrorResponse(BaseSchema):
    """F233 fix : aligné avec middleware.exception_handler output exact.

    Middleware produit {"success": False, "error", "message", "detail",
                        "details", "errors", "request_id"}
    """
    success: bool = False
    error: str  # Code erreur machine-readable (ex: "RESA_NOT_FOUND")
    message: str  # Message human-readable (FR)
    detail: Optional[str] = None  # Compat FastAPI (alias message)
    details: Optional[dict] = None  # Détails structurés optionnels
    errors: Optional[list[dict]] = None  # Validation errors (Pydantic)
    request_id: str  # X-Request-ID
```

## Definition of Done

- [ ] `BaseSchema` opérationnel + Decimal préservé (test E2E `montant_centimes` Numeric correctement sérialisé)
- [ ] `ErrorResponse` schéma matche exactement le format middleware (F233)
- [ ] OpenAPI doc à jour (`52-api-contracts.openapi.yml` reflète ErrorResponse)

---

# Story B1.S5.T4 — Linter CI BaseSchema

## Contexte

**Convention** : tous les schemas Pydantic doivent hériter `BaseSchema` (pas `BaseModel` directement)

## Solution

```python
# tools/check_basemodel_field_strict.py
"""CI invariant : tous les schemas dans app/schemas/ héritent BaseSchema (pas BaseModel)."""
import ast, sys
from pathlib import Path


def main():
    violations = []
    for py_file in Path("app/schemas").rglob("*.py"):
        if py_file.name == "base.py":
            continue
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = [b.id if isinstance(b, ast.Name) else None for b in node.bases]
                if "BaseModel" in bases and "BaseSchema" not in bases:
                    violations.append(f"{py_file}:{node.lineno} class {node.name} hérite BaseModel directement (utiliser BaseSchema)")

    if violations:
        for v in violations:
            print(f"  - {v}")
        return 1
    return 0
```

## Definition of Done

- [ ] Script CI `check_basemodel_field_strict.py` créé
- [ ] Intégré au pipeline GitHub Actions
- [ ] 0 violation actuelle (audit + correction si besoin)

---

## Critères de succès Sprint B1.S5

- [ ] `app/constants/` éclaté en 8 sous-modules
- [ ] `app/observability/metrics.py` centralisé avec label `app_code`
- [ ] `BaseSchema` + `ErrorResponse` aligné middleware
- [ ] Linter CI BaseSchema actif

## Bloc 1 — bilan

À l'issue de B1.S5, **Bloc 1 Foundations livré**. Tous les fondamentaux core sont consolidés :
- Sécurité : RLS active, KMS opérationnel, Outbox transactionnel
- Performance : middleware chain optimisée, rate-limiter atomique, Redis splitté
- Observabilité : labels tenant-scoped, redaction logs étendue
- Conventions : constants éclatés, BaseSchema strict

**Suite** : Bloc 2 Identity (B2.S1 → B2.S5) peut démarrer en parallèle de Bloc 3+.

---

**Fin du document — 11-sprint-B1.S5.md**

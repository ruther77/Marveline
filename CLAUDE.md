# CLAUDE.md — CaroCorp (Marveline)

## Context Engine (OBLIGATOIRE)

Au demarrage de chaque session, appeler `mcp__context-engine__bootstrap()`.
Avant d'editer un fichier Python, appeler `mcp__context-engine__prepare(file_path="chemin/relatif")`.
Le hook PreToolUse bloquera toute edition non preparee.

## Projet

CaroCorp est une application SaaS multi-tenant de gestion de location de vaisselle et accessoires pour evenements.
Le backend expose une API REST versionnee (`/api/v1/`), le frontend est une SPA React/TypeScript.

## Stack technique

| Couche | Technologie |
|---|---|
| Backend API | FastAPI (Python 3.11+) |
| ORM | SQLAlchemy 2.0 (mapped_column, DeclarativeBase) |
| Validation | Pydantic 2.x (pydantic-settings) |
| Base de donnees | PostgreSQL 16 |
| Migrations | Alembic (expand/contract, jamais destructive) |
| Cache / Rate-limit | Redis 7 |
| Taches async | Celery (queues: default, reservations, invoicing, notifications) |
| Auth | JWT (python-jose) + Argon2id + CSRF tokens |
| MFA | TOTP via pyotp |
| Metrics | Prometheus (prometheus-client) |
| Frontend | React + TypeScript + Vite |
| Infra | Docker Compose (db, api, redis, frontend, celery-worker) |

## Architecture du code

```
app/
  api/v1/endpoints/   # Routers FastAPI (auth, products, customers, reservations,
                       #   invoices, categories, bundles, users, mfa, sessions,
                       #   audit, health)
  core/               # Infrastructure transversale
    config.py          # Settings (pydantic-settings, .env)
    database.py        # Engine + SessionLocal + get_db
    deps.py            # Dependencies FastAPI (get_current_user, etc.)
    exceptions.py      # Hierarchie AppException -> HTTP (NotFound, etc.)
    security.py        # JWT, Argon2id, bcrypt, password hashing
    permissions.py     # RBAC (UserRole: admin, manager, staff)
    password_policy.py # Validation force mot de passe
    validators.py      # Validateurs metier
    redis.py           # Client Redis singleton
    rate_limiter.py    # Rate limiter Redis-backed
    health.py          # Health check helpers (Postgres, Redis)
    metrics.py         # Prometheus counters/gauges
    crypto.py          # AES-256 encryption (MFA secrets)
    logging.py         # Structured logging JSON
  models/              # Modeles SQLAlchemy
    base.py            # Base, TimestampMixin, TenantMixin, SoftDeleteMixin
    user.py, product.py, customer.py, reservation.py, invoice.py,
    category.py, bundle.py, mfa.py, audit_log.py
  schemas/             # DTOs Pydantic (request/response)
    base.py            # BaseSchema, EntityResponseSchema
    auth.py, product.py, customer.py, reservation.py, invoice.py,
    category.py, bundle.py, mfa.py, session.py, audit.py, user.py
  repositories/        # Data Access Layer (generic BaseRepository<T>)
    base.py            # CRUD generique + tenant isolation + cache Redis
    product.py, customer.py, reservation.py, invoice.py, category.py, bundle.py
  services/            # Business logic layer
    auth.py, user.py, product.py, session.py, token.py, mfa.py,
    bruteforce.py, cache.py, audit.py, bundle.py, category.py, reservation.py
  middleware/          # Middlewares (ordre LIFO dans main.py)
    security.py        # CSRF, SecurityHeaders, RateLimit
    audit.py           # Audit trail
    request_context.py # X-Request-ID, JWT claims -> ContextVars
    timing.py          # X-Response-Time header
    metrics.py         # Prometheus request metrics
    exception_handler.py # AppException -> JSONResponse
  constants/           # Toutes les constantes (JAMAIS de strings magiques)
    business.py        # Enums (ProductCategory, ReservationStatus, UserRole, etc.)
    errors.py          # Messages d'erreur
    security.py        # Headers, Redis keys, Argon2 params, RBAC
    http.py            # Endpoints publics, methodes HTTP
    limits.py          # Limites (pagination, token expiry, etc.)
    metrics.py         # Patterns normalisation URLs
  tasks/               # Celery tasks
    celery_app.py      # Configuration Celery
  utils/               # Utilitaires (slug generation, etc.)

frontend/
  src/
    api/               # Clients API TypeScript (auth, products, customers, etc.)
    components/        # Composants React (layout, ui, auth, agenda, errors)
    pages/             # Pages (admin, auth, dashboard, events, inventory, products, profile)
    stores/            # State management (authStore, uiStore)
    types/             # Types TypeScript
    hooks/             # Custom React hooks
    styles/            # CSS

tests/
  conftest.py          # Fixtures principales (test_db, client, auth fixtures)
  unit/                # Tests unitaires (~35 fichiers)
  integration/         # Tests integration API (~20 fichiers)
  security/            # Tests securite (CSRF, RBAC, tenant isolation, rate limiting, timing attacks)
  e2e/                 # Tests end-to-end (workflows complets, audit, cache)
  load/                # Tests charge k6 (cache, multi-tenant, invalidation)
```

## Conventions critiques

### Multi-tenant (P0 — violation = incident critique)
- `tenant_id NOT NULL` sur TOUTE table metier via `TenantMixin`
- Index composite `(tenant_id, id)` sur chaque table
- `BaseRepository` applique le filtre `tenant_id` automatiquement sur TOUTES les queries
- Cross-tenant access retourne `None` (pas 404 — evite info leakage)
- Tester l'isolation avec les fixtures `test_user_tenant2`, `auth_headers_tenant2`

### Modeles SQLAlchemy
- Heriter de `Base` (DeclarativeBase) dans `app/models/base.py`
- Mixins obligatoires pour tables metier: `TimestampMixin`, `TenantMixin`, `SoftDeleteMixin`
- Montants monetaires: `BigInteger` centimes (250 = 2,50 EUR). JAMAIS de float.
- Methodes `to_dict()` / `from_dict()` sur Base pour serialisation cache Redis

### Schemas Pydantic
- Heriter de `BaseSchema` (from_attributes=True, strip whitespace, validate assignment)
- Schemas response: utiliser `EntityResponseSchema` (ID + timestamps + tenant + soft delete)
- Schemas dans `app/schemas/`, un fichier par domaine

### Repository pattern
- `BaseRepository[T]` generique avec CRUD, pagination, filtres, cache Redis
- Cache Redis transparent (TTL par entite: Product 5min, Customer 10min, Reservation 1min)
- Invalidation cache automatique sur update/delete (write-through)
- `flush()` sans `commit()` — le commit est gere par le service layer

### Exceptions
- Utiliser `from app.core.exceptions import NotFound, InvalidCredentials, ...`
- ATTENTION: c'est `NotFound` (pas `NotFoundError`)
- Hierarchie: `AppException` -> exceptions specifiques avec `status_code`, `error_code`, `message`
- Le middleware `exception_handler.py` convertit automatiquement en JSONResponse

### Constantes
- TOUTES les constantes dans `app/constants/` (business.py, errors.py, security.py, http.py, limits.py)
- Import: `from app.constants import ProductCategory, ErrorMessages, UserRole`
- JAMAIS de strings magiques hardcodees pour concepts metier

### Securite
- Pas de secret hardcode (validator dans Settings bloque en production)
- Pas d'endpoint sans auth (sauf health, CSRF token, login, register, docs)
- Hashing: Argon2id (OWASP 2024+), migration transparente depuis bcrypt
- CSRF: token dans header `X-CSRF-Token` pour methodes mutantes
- Rate limiting: Redis-backed, fail-open strategy (disponibilite > securite)
- RBAC: roles `admin`, `manager`, `staff` via `app/core/permissions.py`

### Migrations Alembic
- Pattern expand/contract uniquement, JAMAIS de migration destructive directe
- Commande: `alembic revision --autogenerate -m "description"`
- Appliquer: `alembic upgrade head` (automatique au demarrage Docker)

## Commandes

### Tests
```bash
# Via Docker (recommande)
docker compose run --rm --entrypoint "" api python -m pytest tests/ -v

# Tests unitaires seuls
docker compose run --rm --entrypoint "" api python -m pytest tests/unit/ -v

# Tests integration
docker compose run --rm --entrypoint "" api python -m pytest tests/integration/ -v

# Tests securite
docker compose run --rm --entrypoint "" api python -m pytest tests/security/ -v

# Avec couverture
docker compose run --rm --entrypoint "" api python -m pytest tests/ -v --cov=app --cov-report=term-missing
```

pytest-asyncio mode strict: `@pytest.mark.asyncio` obligatoire sur tests async.
Minimum de mocks, implementations reelles preferees.

### Linting / Formatting
```bash
black app/ tests/        # Formatting
ruff check app/ tests/   # Linting rapide
flake8 app/ tests/       # Linting
mypy app/                # Type checking
bandit -r app/           # Security audit
```

### Docker
```bash
docker compose up -d           # Demarrer tous les services
docker compose down            # Arreter
docker compose logs api -f     # Logs API
docker compose exec api bash   # Shell dans le container API
```

### Services Docker
| Service | Port | Description |
|---|---|---|
| api | 8001:8000 | API FastAPI |
| db | 5433:5432 | PostgreSQL 16 |
| redis | 6380:6379 | Redis 7 |
| frontend | 3002:80 | React SPA |
| celery-worker | — | Worker Celery |

## Test fixtures cles (tests/conftest.py)

- `test_db`: Session SQLAlchemy avec SAVEPOINT rollback (isolation par test)
- `client`: TestClient FastAPI avec DB de test
- `test_user` / `test_admin`: Utilisateurs tenant_id=1
- `test_user_tenant2` / `test_admin_tenant2`: Utilisateurs tenant_id=2
- `auth_headers_real` / `auth_headers_admin`: Headers JWT + CSRF valides
- `auth_headers_tenant2`: Headers pour tests cross-tenant
- `cleanup_redis_between_tests`: Nettoyage automatique Redis entre tests

## Workflow middleware (ordre d'execution requete)

```
Request ->
  MetricsMiddleware          (outermost — capture tout)
  TimingMiddleware           (mesure duree)
  TrustedHostMiddleware      (bloque hosts non autorises)
  CORSMiddleware             (preflight CORS)
  CSRFProtectionMiddleware   (validation CSRF)
  SecurityHeadersMiddleware  (headers securite)
  RateLimitMiddleware        (rate limiting Redis)
  GZipMiddleware             (compression)
  RequestContextMiddleware   (X-Request-ID, JWT claims, ContextVars)
  AuditMiddleware            (innermost — audit trail)
  -> Exception Handlers -> Routes
```

## Regles globales

Les regles completes (securite, CI/CD, RGPD, observabilite, workflow Git) sont dans `~/.claude/CLAUDE.md`.

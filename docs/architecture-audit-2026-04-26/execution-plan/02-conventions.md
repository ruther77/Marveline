# Conventions DEVUP — Code, Tests, Git, PR

> **Source de vérité** pour conventions. Toute déviation = rejet en review. Si une règle ne convient pas, ouvrir une RFC, ne pas contourner silencieusement.

## 1. Conventions de nommage

### 1.1 Tables PostgreSQL

| Pattern | Exemple | Anti-pattern |
|---|---|---|
| `snake_case` pluriel | `customers`, `audit_logs`, `feature_flags` | ❌ `Customer`, `auditLog`, `FeatureFlag` |
| Préfixe domaine pour tables vertical-spécifiques | `restaurant_commandes`, `epicerie_ventes`, `loyalty_members` | ❌ `commandes` (ambigu) |
| Tables M:N avec préfixe ou nom explicite | `auth_role_scopes`, `feature_flag_tenants`, `tenant_memberships` | ❌ `users_roles` (ambigu sens) |
| Tables `_history` pour append-only audit | `feature_flag_history`, `catalogue_produit_price_history` | ❌ `feature_flags_changes` |

### 1.2 Colonnes

| Pattern | Exemple |
|---|---|
| `snake_case` | `created_at`, `tenant_id`, `is_active` |
| Boolean : préfixe `is_` ou `has_` ou `requires_` | `is_active`, `has_variants`, `requires_deposit` |
| FK : `<table_singulier>_id` | `tenant_id`, `account_id`, `category_id` |
| Cents (BigInteger) | `total_ttc_cents`, `prix_unitaire_cents`, `cleaning_fee_cents` |
| Timestamps : `created_at`, `updated_at`, `_at` suffix pour autres | `confirmed_at`, `cancelled_at`, `last_login_at` |
| ENUM : valeurs lower_snake | `'pending', 'confirmed', 'cancelled'` (jamais `'PENDING'`) |
| Snapshots : suffix `_snapshot` | `tva_rate_snapshot`, `prix_unitaire_snapshot` |
| Encrypted : marquer dans le commentaire SQLAlchemy `EncryptedField` | PII chiffré KMS |

### 1.3 Modèles SQLAlchemy

```python
# CORRECT
class Customer(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="t")
    
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_customers_tenant_email"),
        Index("idx_customers_search", "tenant_id", "first_name", "last_name"),
    )
```

**Anti-patterns** :
- Classes Python en lower-case (`class customer`) — toujours PascalCase.
- Classe modèle qui n'hérite pas de `Base` — incohérent avec ORM.
- Modèle tenant-scoped sans `TenantMixin`.
- Type `Integer` pour primary key (préférer `BigInteger`, tables peuvent dépasser 2.1B rows).
- Style legacy `id = Column(...)` — utiliser `Mapped[type] = mapped_column(...)`.

### 1.4 Migrations Alembic

**Naming** : `<timestamp>_<short_description>.py` (ex: `2026_04_28_1430_add_tenant_vertical_column.py`)

**Convention de revision_id** : 12 caractères hex (ex: `a1b2c3d4e5f6`).

**Obligations** :
1. **Toujours** implémenter `downgrade()`. Pas de `pass` silencieux. Si downgrade impossible (ex: drop column avec data perdue), commenter explicitement et soulever en review.
2. **Toujours** tester upgrade + downgrade en local sur une copie de prod (ou fixture représentative).
3. **Pas de SELECT bloquant en prod** : `op.execute("UPDATE customers SET ... WHERE id IN (...)")` sur 50k rows = lock table → INTERDIT en migration. Utiliser script Celery batché.
4. **Migrations data séparées des migrations schema** : 1 migration = soit schema, soit data, jamais les deux mélangés.
5. **Backward-compatible step-by-step** :
   - Step 1 : ajouter nouvelle colonne nullable
   - Step 2 : backfill via Celery (pas migration directe)
   - Step 3 : ALTER COLUMN NOT NULL
   - Step 4 : drop ancienne colonne
   - Chaque step déployé séparément. Pas de big bang.

### 1.5 Variables et fonctions Python

| Pattern | Exemple |
|---|---|
| Variables locales et fonctions : `snake_case` | `customer_id`, `def get_active_rules()` |
| Constants : `UPPER_SNAKE_CASE` | `MAX_LOYALTY_MULTIPLIER = 3.0` |
| Classes : `PascalCase` | `class PricingEngine`, `class FSM` |
| Privées : préfixe `_` | `_compute_tva_total`, `_internal_helper` |
| Type aliases : `PascalCase` | `type TenantId = int`, `type Principal = Account \| ApiKeyClient` |

## 2. Structure des fichiers

### 2.1 Layers (cf. `architecture-cible.md` §1.2.1)

```
app/
├── api/v1/endpoints/      # Routers FastAPI — fines, délèguent au service
├── core/                  # Foundations transverses (auth, db, redis, observability)
├── constants/             # Defaults globaux (per-tenant → tenant_settings DB)
├── models/                # SQLAlchemy 2.0 Mapped[...]
├── repositories/          # Async only (Q5=A)
├── schemas/               # Pydantic 2.x (request/response)
├── services/              # Logique métier — JAMAIS dans endpoints/repositories
├── tasks/                 # Celery tasks (queue per domain)
└── middleware/            # Chain : RequestContext → Tenant → Auth → RateLimit → Audit
```

**Règle d'or** : un endpoint **ne contient pas** de logique métier. Il :
1. Valide le payload Pydantic
2. Appelle un service
3. Map la réponse en schema Pydantic

Aucune query SQLAlchemy directement dans un endpoint. Aucun calcul métier. Si tu en mets, refactor en service avant de PR.

### 2.2 Services — pattern canonique

```python
# app/services/customer.py
class CustomerService:
    def __init__(
        self,
        db: AsyncSession,
        repo: CustomerRepository,
        audit_service: AuditService,
        notification_service: NotificationService = None,
    ):
        self._db = db
        self._repo = repo
        self._audit = audit_service
        self._notif = notification_service

    @audit_action(entity_type="Customer")
    async def update(self, customer_id: int, payload: CustomerUpdate, actor: Principal) -> Customer:
        async with self._db.begin():
            customer = await self._repo.get_by_id_for_update(customer_id, actor.active_tenant_id)
            if customer is None:
                raise NotFound("Customer", customer_id)
            
            before = customer.to_audit_dict()
            
            for field, value in payload.model_dump(exclude_unset=True).items():
                setattr(customer, field, value)
            
            return customer
```

### 2.3 Repositories — pattern canonique

```python
# app/repositories/customer.py
class CustomerRepository(BaseRepository[Customer]):
    """Tous les query SQLAlchemy ICI. Service ne touche pas .execute() directement."""
    
    async def get_by_id_for_update(self, customer_id: int, tenant_id: int) -> Customer | None:
        return await self._db.scalar(
            select(Customer)
            .where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
            .with_for_update()
        )
    
    async def email_exists(self, email: str, tenant_id: int) -> bool:
        """Cohérent avec UNIQUE strict DB (pas de filtre is_active — F447)."""
        return await self._db.scalar(
            select(exists().where(
                Customer.email == email.lower(),
                Customer.tenant_id == tenant_id,
            ))
        )
```

## 3. Tests

### 3.1 Pyramide

| Niveau | % du total | Rapidité cible | Localisation |
|---|---|---|---|
| **Unit** | ~70% | <5s par fichier | `tests/unit/` |
| **Integration** | ~25% | <30s par fichier | `tests/integration/` (DB réelle, Redis réel, pas mock) |
| **E2E** | ~5% | <2min par scénario | `tests/e2e/` (HTTP via TestClient) |

### 3.2 Conventions tests

- **Fichier** : `tests/<layer>/test_<module>.py` (ex: `tests/unit/test_pricing_engine.py`)
- **Test name** : `test_<scenario>_<expected_outcome>` (ex: `test_credit_points_concurrent_returns_correct_balance`)
- **Anti-mock DB** : les integration tests utilisent **Postgres réel** (cf. memory `bug-infra-testdb`). Mock uniquement les services externes (Postmark API, KMS, WG service).
- **Pas de `assert True`** ou `time.sleep()` dans tests. Bare `except:` interdit dans les tests aussi.
- **Tests d'invariant CI** dans `tests/invariants/` (ex: `test_invariant_engine_eq_simulate.py`)

### 3.3 Coverage cible

| Module | Coverage minimum |
|---|---|
| `app/services/` | 90% (logique métier critique) |
| `app/repositories/` | 80% |
| `app/core/auth/` | 95% (sécurité) |
| `app/core/permissions/` | 95% (RBAC) |
| `app/api/v1/endpoints/` | 70% (E2E couvre le reste) |
| `app/middleware/` | 85% |
| `app/tasks/` | 80% (Celery fixtures) |

CI bloque si la couverture descend sous le seuil par module.

### 3.4 Fixtures

- `conftest.py` racine : fixtures session + DB schema setup
- `conftest.py` par dossier : fixtures spécifiques au domaine
- **Pas de fixture autouse=True qui touche la DB** sans raison explicite (cf. `bug-infra-testdb` — fixture teardown casse run batch)
- `factory_boy` ou équivalent pour générer des données réalistes

## 4. Git workflow

### 4.1 Branches

| Branche | Pattern | Durée de vie |
|---|---|---|
| `main` | Trunk, prod-ready après CI vert | ∞ |
| Feature : `feat/B<bloc>.S<sprint>-<short>` | `feat/B5.S1-marmite-fix` | <5 jours |
| Hotfix : `hotfix/F<friction>-<short>` | `hotfix/F906-quantite-par-batch` | <1 jour |
| Refactor : `refactor/B<bloc>.S<sprint>-<short>` | `refactor/B4.S3-category-fk` | <5 jours |
| Spike : `spike/<short>` | `spike/rabbitmq-poc` | <3 jours, pas mergeable |

**Pas de** `dev`, `staging`, `release/*` longue durée. Trunk-based development. Feature flags pour découpler déploiement et release.

### 4.2 Commits

**Conventional Commits** :
```
<type>(<scope>): <subject>

<body>

<footer>
```

| `<type>` | Quand |
|---|---|
| `feat` | Nouvelle fonctionnalité |
| `fix` | Bug fix (toujours référencer FXXX dans le subject ou body) |
| `refactor` | Refonte sans changement comportement |
| `test` | Ajout/modif tests |
| `docs` | Doc seule |
| `chore` | Build, CI, deps |
| `perf` | Optimisation perf mesurable |
| `security` | Fix sécurité (CVE, RGPD, audit) |
| `migration` | Migration Alembic ou data |

**`<scope>`** : `B<bloc>.S<sprint>` ou domaine (`auth`, `pricing`, `etl`, etc.)

**Exemples** :
```
fix(B5.S1): F906 marmite — quantite_par_portion → quantite_par_batch + formule

Le service _verifier_et_consommer_recette accédait à
ligne.quantite_par_portion qui n'existe pas dans le model
RecetteTypePreparation. Corrige en quantite_par_batch et applique
la formule batch→portions correcte.

Tests E2E POST /instances avec recette pass.
Closes F906, MARMITE-QPP-01.
```

**Anti-patterns** :
- ❌ `fix bug`
- ❌ `wip` (jamais en main)
- ❌ `merge branch ...` (rebase, pas merge)
- ❌ Commit sans référence FXXX pour les fix audit

### 4.3 Pull Request

**Title** : même format que conventional commit subject.

**Body template** :
```markdown
## Contexte
Lien architecture-cible.md §X.Y.Z + audit module XX

## Changes
- liste des modifications
- 1 puce = 1 changement atomique

## Tests
- [ ] Tests unitaires écrits (couverture >X%)
- [ ] Tests integration (si touche DB)
- [ ] Tests E2E (si touche endpoint)
- [ ] Tests régression : 1782 tests existants passent

## Migrations
- [ ] Migration Alembic upgrade testée
- [ ] Migration Alembic downgrade testée
- [ ] Backfill data testé sur copie prod (si applicable)

## Risques & rollback
- Risque P/I : ...
- Plan rollback : ...

## Checklist senior
- [ ] Pas de stub `NotImplementedError` non documenté
- [ ] Pas de `bare except:` ni `except Exception: pass`
- [ ] Pas de query directe dans endpoint (passe par service)
- [ ] Audit log via `@audit_action` ou `audit_service.log_*` explicite
- [ ] Tenant_id filtrage présent (si tenant-scoped)
- [ ] Pas de `print()` ou `logger.debug` en prod paths
- [ ] Type hints sur toutes les fonctions publiques
- [ ] Docstring sur les services complexes

Closes FXXX, FYYY.
```

### 4.4 PR review process

1. **Author** : self-review + checklist remplie + tous les tests verts CI.
2. **Reviewer 1** (peer) : focus correctness + lisibilité + tests.
3. **Reviewer 2** (senior) : focus architecture + sécurité + perf.
4. **Owner du sprint** (cf. RACI) : approve final.
5. **Merge** : squash-merge sur main (1 PR = 1 commit en main, message = PR title + body).

**SLA review** : 24h ouvrées max. Au-delà, escalation au lead.

## 5. CI/CD

### 5.1 Pipeline GitHub Actions

```yaml
ci:
  - lint:        ruff check + ruff format --check + mypy --strict
  - test:unit:   pytest tests/unit -n auto --cov=app --cov-fail-under=80
  - test:integ:  pytest tests/integration (DB + Redis docker)
  - test:e2e:    pytest tests/e2e (full app + DB + Redis + RabbitMQ)
  - invariants:  python tools/check_*.py (cf. 54-ci-invariants.md)
  - migrations:  alembic upgrade head + downgrade base + upgrade head (idempotence)
  - security:    bandit + safety + trivy (Docker image scan)
  - build:       docker build + push registry (si main)
  - deploy:      manuel via /deploy slash command (gate)
```

### 5.2 Branch protection main

- Requires : CI vert + 1 review approved + à jour avec main (rebase)
- No direct push (même les leads passent par PR)
- No force push
- Tags signés pour les releases

## 6. Observabilité standards

### 6.1 Logs

- **Format** : JSON structuré (pas de string `f"user {x} did Y"`)
- **Champs obligatoires** : `timestamp`, `level`, `message`, `tenant_id` (si applicable), `account_id` (si applicable), `request_id`, `trace_id` (OpenTelemetry)
- **Pas de PII** dans les logs (cf. `SENSITIVE_FIELDS` étendu Bloc 1)
- **Levels** :
  - `DEBUG` : dev local, jamais en prod paths
  - `INFO` : événements business notables (ex: "Vente encaissée")
  - `WARNING` : situation anormale mais récupérable
  - `ERROR` : exception capturée, opération échouée
  - `CRITICAL` : action requise immédiate (degraded mode, kill-switch)

### 6.2 Métriques Prometheus

- **Naming** : `<domain>_<measure>_<unit>` (ex: `http_request_duration_seconds`, `celery_task_duration_seconds`)
- **Labels obligatoires** : `tenant_id` (cap top 100, sinon `'other'` — cf. F1126)
- **Labels low cardinality** : pas d'IDs uniques (`customer_123` interdit)
- **Histogramme buckets adaptés** : pas de `(0.005, 0.01, 0.025, ..., 5.0)` générique pour ETL tasks (qui prennent minutes — F1137)

### 6.3 Traces OpenTelemetry

- Activé Sprint B6.S6 (Q37=A)
- Span propagation : `traceparent` header api → Celery → WG service → Postmark
- `trace_id` dans tous les logs structurés (corrélation Loki ↔ Tempo/Jaeger)

## 7. Sécurité — règles non négociables

1. **Aucun secret en clair dans le code, dans les logs, dans Git.** Secrets via env + KMS + chiffrés au repos.
2. **Validation entrée à TOUTES les frontières externes** (HTTP body via Pydantic, JWT decode, input ETL).
3. **Pas de SQL string formatting**. Toujours bind params via SQLAlchemy.
4. **Pas d'exécution shell sans sanitization** : éviter `subprocess` avec `shell=True`. Préférer `subprocess.run(["cmd", "arg"])` avec list argv.
5. **Pas de désérialisation arbitraire** sur input externe : interdire les formats non-safe (formats binaires natifs Python sur input réseau, `yaml.load()` sans `SafeLoader`, etc.).
6. **Pas de `bare except:`** ni `except Exception: pass`. Logger.exception minimum.
7. **Aucun endpoint sans `require_scope()`** sauf whitelist explicite (`/health/live`, `/metrics` mTLS, `/docs` non-prod).
8. **Tenant filtering** : tout repository query DOIT filtrer `tenant_id` (sauf tables global infra : `verticals`, `apps`, `audit_chain_master_keys`).
9. **PII chiffrée** au repos pour `Customer.notes`, `Supplier.notes`, audit `changes`/`description`, etc.
10. **Audit obligatoire** sur toute mutation entité tenant-scoped + sur toute lecture PII (READ_SENSITIVE).

## 8. Convention de gestion des erreurs

### 8.1 Hiérarchie

```python
# app/core/exceptions.py
class DomainException(Exception):
    """Toutes les erreurs business héritent."""
    status_code: int = 400
    error_code: str

class NotFound(DomainException):
    status_code = 404

class Conflict(DomainException):
    status_code = 409

class IllegalTransition(DomainException):
    status_code = 409
    error_code = "ILLEGAL_FSM_TRANSITION"

class TenantMismatch(DomainException):
    status_code = 403
    error_code = "TENANT_MISMATCH"
```

### 8.2 ExceptionHandler middleware

```python
# app/middleware/exception_handler.py
@app.exception_handler(DomainException)
async def handle_domain(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": exc.error_code, "detail": str(exc)},
    )

@app.exception_handler(Exception)
async def handle_unexpected(request, exc):
    logger.exception("unexpected error")
    # JAMAIS exposer str(exc) au client (F460)
    return JSONResponse(
        status_code=500,
        content={"error_code": "INTERNAL_ERROR", "detail": "Internal server error"},
    )
```

**Anti-pattern** :
```python
# INTERDIT (F460)
except Exception as e:
    raise HTTPException(500, detail=f"Error: {str(e)}")  # FUITE schema DB
```

## 9. Code review : red flags

Le reviewer doit refuser une PR avec :

| Red flag | Raison |
|---|---|
| `time.sleep()` dans code prod | Polling au lieu de event-driven |
| `requests.get()` synchrone dans handler async | Threadpool exhausted (cf. F1091) |
| Query SQLAlchemy avec `tenant_id` manquant | Leak cross-tenant probable |
| `# TODO` sans ticket FXXX référencé | Dette tech invisible |
| `raise NotImplementedError` non documenté | Stub silencieux (V1 violation) |
| Migration Alembic sans `downgrade()` | Pas de rollback |
| Ajout colonne nullable sans plan NOT NULL | Backfill jamais fait |
| String hardcoded `"marveline"` / `"epicerie"` | Devrait être constante ou settings |
| `print()` au lieu de `logger.X()` | Pas de structured log |
| `assert` dans code prod (pas test) | Désactivé avec `python -O` |
| Schema Pydantic sans validators | Validation faible |
| Mock `db` dans integration test | Cf. règle anti-mock DB |
| Commit message sans `B<bloc>.S<sprint>` ni FXXX | Traçabilité cassée |

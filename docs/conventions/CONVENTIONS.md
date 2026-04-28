# Marveline — Conventions de Code (Référence Officielle)

> Version : 2.0 — 2026-02-20
> Niveau de sévérité : **Scalabilité maximale**. En cas de doute, choisir l'option la plus rigoureuse.
> Ce document fait autorité sur tout autre source. Toute dérogation = commentaire explicite + ticket.

---

## Sommaire

### Conventions core (1–11)
1. [Modèles SQLAlchemy](#1-modèles-sqlalchemy)
2. [Schémas Pydantic](#2-schémas-pydantic)
3. [Repositories](#3-repositories)
4. [Services](#4-services)
5. [Endpoints FastAPI](#5-endpoints-fastapi)
6. [Tests](#6-tests)
7. [Frontend TypeScript](#7-frontend-typescript)
8. [Constantes et Enums](#8-constantes-et-enums)
9. [Migrations Alembic](#9-migrations-alembic)
10. [Points transverses](#10-points-transverses)
11. [Décisions architecturales tranchées (T1–T10)](#11-décisions-architecturales-tranchées)

### Patterns avancés — Scaling & Résilience (12)
12. [Outbox Pattern](#121-outbox-pattern) · [Unit of Work](#122-unit-of-work) · [Circuit Breaker](#123-circuit-breaker) · [Advisory Locks](#124-advisory-locks-postgresql) · [Idempotency Keys](#125-idempotency-keys) · [Optimistic Locking](#126-optimistic-locking) · [Saga + Compensation](#127-saga--compensation) · [SSRF Prevention](#128-ssrf-prevention) · [Field Encryption](#129-field-level-encryption) · [ReDoS Protection](#1210-redos-protection) · [Retry + Jitter](#1211-retry-exponential-backoff--full-jitter) · [Bulkhead](#1212-bulkhead-pattern) · [Timeout Strategy](#1213-timeout-strategy) · [Rate Limiting](#1214-rate-limiting-par-tenant) · [CQRS Light](#1215-cqrs-light) · [Specification Pattern](#1216-specification-pattern) · [Cursor Pagination](#1217-cursor-based-pagination) · [ETag](#1218-etag--if-none-match) · [Sparse Fieldsets](#1219-sparse-fieldsets-fields) · [Materialized Views](#1220-materialized-views-postgresql) · [Partial Indexes](#1221-partial-indexes) · [Domain Events](#1222-domain-events--eventbus) · [Re-auth Sensitive](#1223-re-auth-pour-actions-sensibles) · [Bulk Operations](#1224-bulk-operations)

### Patterns infra/ops (13–17)
13. [Celery DLQ + Flower](#13-celery--tâches-asynchrones) · 14. [Observabilité](#14-observabilité-ops) · 15. [RGPD & Conformité](#15-rgpd--conformité) · 16. [Frontend avancé](#16-frontend-avancé) · 17. [Décisions de déploiement](#17-déploiement--infrastructure)

### Architecture distribuée (18–24)
18. [Zod + MSW](#18-frontend--validation--mocking) · 19. [useTransition + URL State](#19-react-18--performance) · 20. [TestContainers + Visual Regression](#20-tests-avancés) · 21. [Pre-commit + ADR](#21-qualité-du-code) · 22. [SLO + Error Budgets](#22-slo--error-budgets) · 23. [Data Anonymisation](#23-data-anonymisation-staging) · 24. [Backup/Restore](#24-backuprestore-runbook)

### Patterns expert (25–45)
25. [Docker multi-stage](#25-docker--containers) · 26. [Secrets Vault](#26-secrets-management) · 27. [DB SSL](#27-database-sécurité) · 28. [Blue/Green Canary](#28-déploiement-bluegreen--canary) · 29. [React.memo + Zustand Immer](#29-react-performance) · 30. [Design Tokens + Storybook](#30-design-system) · 31. [OpenTelemetry](#31-observabilité-distribuée) · 32. [Slow Query](#32-slow-query-detection) · 33. [Cache Tags](#33-cache-invalidation-par-tag) · 34. [Optimistic UI](#34-optimistic-ui--rollback) · 35. [Infinite Scroll + Form Dirty State](#35-ux-patterns) · 36. [Event Sourcing](#36-event-sourcing) · 37. [CSP Nonce](#37-csp-nonce-dynamique) · 38. [mTLS + Chaos](#38-sécurité-avancée) · 39. [Command Pattern](#39-command-pattern-réversible) · 40. [gRPC](#40-grpc-inter-services) · 41. [Sliding Window + Token Bucket](#41-rate-limiting-avancé) · 42. [Sparse Fieldsets](#42-sparse-fieldsets-api) · 43. [Contract-First API](#43-contract-first-api-design) · 44. [API Versioning](#44-api-versioning) · 45. [Accessibility + Performance](#45-accessibility--performance-ci)

---

## 1. Modèles SQLAlchemy

### 1.1 Nommage

| Élément | Convention | Exemple |
|---------|-----------|---------|
| Fichier | `snake_case.py` | `invoice_charge.py` |
| Classe | `PascalCase` | `InvoiceCharge` |
| Table | `snake_case` pluriel | `invoice_charges` |
| Colonne | `snake_case` | `total_amount_cents` |
| Index | `ix_{table}_{cols}` | `ix_invoices_tenant_number` |
| Contrainte unique | `uq_{table}_{cols}` | `uq_invoices_tenant_number` |
| Check constraint | `check_{table}_{rule}` | `check_invoice_total_positive` |
| FK constraint | `fk_{table}_{col}` | `fk_invoice_charges_invoice_id` |

### 1.2 Structure obligatoire

```python
class Invoice(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Description courte du modèle.

    Business rules:
        - Règle 1
        - Règle 2
    """

    __tablename__ = "invoices"

    # ── Clé primaire ──────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # ── Colonnes métier ───────────────────────────────────────────────────────
    invoice_number: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    total_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Clés étrangères ───────────────────────────────────────────────────────
    reservation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("reservations.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # ── Relations ─────────────────────────────────────────────────────────────
    reservation: Mapped["Reservation"] = relationship(
        "Reservation",
        back_populates="invoice",
        lazy="select",          # EXPLICITE TOUJOURS
    )
    charges: Mapped[list["InvoiceCharge"]] = relationship(
        "InvoiceCharge",
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="select",          # EXPLICITE TOUJOURS
    )

    # ── Contraintes table ─────────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_invoices_tenant_number", "tenant_id", "invoice_number", unique=True),
        CheckConstraint("total_amount_cents >= 0", name="check_invoice_total_positive"),
        # ⚠️ DRY : générer la contrainte depuis l'enum Python pour éviter désynchronisation
        # from app.constants.business import InvoiceStatus
        # CheckConstraint(f"status IN {tuple(s.value for s in InvoiceStatus)}", name="check_invoice_status_valid")
        CheckConstraint(
            "status IN ('draft', 'sent', 'paid', 'overdue', 'cancelled')",
            name="check_invoice_status_valid",
        ),
    )

    def __repr__(self) -> str:
        return f"<Invoice(id={self.id}, number='{self.invoice_number}', status='{self.status}')>"
```

### 1.3 Règles absolues

**R-MOD-1 — Types de colonnes**

| Concept | Type SQL | Interdit |
|---------|----------|---------|
| Montant | `BigInteger` (centimes) | `Float`, `Numeric`, `Decimal` |
| Quantité | `Integer` | `Float` |
| Statut/Enum | `String(20)` + `CheckConstraint` | `Enum` natif SQL |
| Description courte | `String(N)` avec N explicite | `String()` sans longueur |
| Texte libre | `Text` (justifié) | `String` pour contenu long |
| Timestamp | `DateTime(timezone=True)` | `DateTime()` sans timezone |
| Date seule | `Date` | `String` |

**R-MOD-2 — Mixins obligatoires**

| Mixin | Tables concernées |
|-------|------------------|
| `TimestampMixin` | Toutes les tables sans exception |
| `TenantMixin` | Toutes les tables métier (hors auth/config système) |
| `SoftDeleteMixin` | Entités principales : `Product`, `Customer`, `User`, `Bundle` |

**R-MOD-3 — Contraintes**
- Tout `CheckConstraint` doit avoir `name=` explicite. Sans nom : blocage Alembic.
- **DRY sur les enums** : les `CheckConstraint` sur les statuts doivent être générés depuis les enums Python (`app/constants/`) pour éviter désynchronisation. Pattern : `f"status IN {tuple(s.value for s in MyStatus)}"`.
- Toute FK doit déclarer `ondelete=` (`"CASCADE"` ou `"RESTRICT"` — jamais implicite).
- Index composite `(tenant_id, id)` obligatoire sur toute table avec `TenantMixin`.

**R-MOD-4 — Relations**
- `lazy=` toujours explicite. Valeurs autorisées : `"select"` (défaut explicite) ou `"joined"` (si toujours chargé ensemble).
- `lazy="dynamic"` interdit (déprécié SQLAlchemy 2.0).
- `lazy="subquery"` interdit (imprévisible sur listes larges).

**R-MOD-5 — Type hints**
- `Mapped[Optional[str]]` — ordre correct (pas `Optional[Mapped[str]]`).
- Nullable = `Mapped[Optional[T]]` + `nullable=True` dans `mapped_column()`.
- Non-nullable = `Mapped[T]` + `nullable=False` dans `mapped_column()`.

---

## 2. Schémas Pydantic

### 2.1 Hiérarchie obligatoire

```
BaseSchema                          ← model_config avec extra="forbid"
    │
    ├── EntityBase                  ← champs partagés + @model_validator métier
    │       ├── EntityCreate        ← POST (champs requis, extra="forbid" hérité)
    │       └── EntityUpdate        ← PATCH (tous Optional[T] = None)
    │
    └── EntityResponseSchema        ← model_config avec from_attributes=True
            ├── EntityList          ← réponse liste (champs essentiels)
            └── EntityResponse      ← réponse détail (étend List + relations)
```

### 2.2 Pattern complet

```python
# ── Base de toutes les classes input ──────────────────────────────────────────
class BaseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")   # Rejette tout champ inconnu


# ── Base de toutes les classes réponse ───────────────────────────────────────
class EntityResponseSchema(BaseModel):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Input schemas ─────────────────────────────────────────────────────────────
class InvoiceBase(BaseSchema):
    """Champs partagés entre Create et Update. Validateurs métier ici."""

    issue_date: date = Field(..., description="Date d'émission")
    due_date: date = Field(..., description="Date d'échéance")

    @model_validator(mode="after")
    def validate_dates_coherence(self) -> "InvoiceBase":
        if self.due_date < self.issue_date:
            raise ValueError("due_date doit être >= issue_date")
        return self


class InvoiceCreate(InvoiceBase):
    """Payload POST /invoices — id/tenant_id/timestamps rejetés (extra=forbid hérité)."""

    reservation_id: int = Field(..., gt=0)


class InvoiceUpdate(BaseSchema):
    """Payload PATCH /invoices/{id} — tous champs optionnels."""

    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "InvoiceUpdate":
        if not any([self.issue_date, self.due_date, self.notes]):
            raise ValueError("Au moins un champ doit être fourni")
        return self


# ── Response schemas ──────────────────────────────────────────────────────────
class InvoiceList(EntityResponseSchema):
    """Réponse liste — champs essentiels uniquement. Pas de computed euros ici."""

    invoice_number: str
    status: str
    total_amount_cents: int
    paid_amount_cents: int
    is_overdue: bool


class InvoiceResponse(InvoiceList):
    """Réponse détail — étend List sans redéfinir de champs existants.

    Rule: Response EXTENDS List. NEVER redefines an existing field with a different type.
    """

    reservation_id: int
    notes: Optional[str] = None
    charges: list["InvoiceChargeRead"] = []
    payments: list["PaymentRead"] = []

    # computed_field UNIQUEMENT sur Response (détail), jamais sur List (perf)
    @computed_field
    @property
    def total_amount_euros(self) -> float:
        return round(self.total_amount_cents / 100, 2)

    @computed_field
    @property
    def paid_amount_euros(self) -> float:
        return round(self.paid_amount_cents / 100, 2)

    @computed_field
    @property
    def remaining_amount_cents(self) -> int:
        return max(0, self.total_amount_cents - self.paid_amount_cents)
```

### 2.3 Règles absolues

**R-SCH-1** — `extra="forbid"` sur tous les schemas input. `from_attributes=True` sur tous les schemas réponse. Ces deux configs ne se mélangent pas.

**R-SCH-2** — `@computed_field` euros uniquement sur `EntityResponse` (jamais sur `EntityList`).

**R-SCH-3** — `EntityResponse` ne redéfinit jamais un champ de `EntityList` avec un type différent.

**R-SCH-4** — Tout champ montant porte le suffixe `_cents` (type `int`). Les champs `_euros` sont uniquement des `@computed_field`.

**R-SCH-5** — Les validateurs métier complexes vont dans `EntityBase`, pas dans `EntityCreate` (pour être hérités par les deux).

---

## 3. Repositories

### 3.1 Structure

```python
class InvoiceRepository(BaseRepository[Invoice]):
    """Repository factures — isolation tenant stricte.

    Never:
        - db.query() (SQLAlchemy 1.x — interdit)
        - db.commit() (responsabilité endpoint)
        - Requête sans tenant_id filter
    """

    # ── Lecture ───────────────────────────────────────────────────────────────
    def get_by_id(self, id: int, tenant_id: int) -> Optional[Invoice]:
        query = (
            select(Invoice)
            .options(joinedload(Invoice.charges), joinedload(Invoice.reservation))
            .where(Invoice.id == id)
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        return self.db.execute(query).unique().scalar_one_or_none()

    def list_with_count(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
    ) -> tuple[list[Invoice], int]:
        """Retourne toujours (items, total) — jamais list[T] seul."""
        base = select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.is_active.is_(True))
        if status:
            base = base.where(Invoice.status == status)

        total = self.db.scalar(select(func.count()).select_from(base.subquery()))
        items = (
            self.db.execute(
                base.options(joinedload(Invoice.reservation))
                .order_by(Invoice.id.desc())
                .offset(skip)
                .limit(limit)
            )
            .unique()
            .scalars()
            .all()
        )
        return list(items), total or 0

    # ── Écriture ──────────────────────────────────────────────────────────────
    def create(self, entity: Invoice) -> Invoice:
        """Flush + refresh. Jamais commit."""
        self.db.add(entity)
        self.db.flush()
        self.db.refresh(entity)
        return entity

    def update(self, entity: Invoice) -> Invoice:
        """Flush + refresh. Jamais commit."""
        self.db.flush()
        self.db.refresh(entity)
        return entity
```

### 3.2 Nommage des méthodes

| Action | Nom canonique | Alias interdits |
|--------|--------------|----------------|
| Lire un par ID | `get_by_id(id, tenant_id)` | `find_by_id`, `fetch`, `get` |
| Lire un par champ | `get_by_{field}(value, tenant_id)` | `find_by_*`, `fetch_by_*` |
| Lire plusieurs | `list_with_count(tenant_id, ...)` | `get_all`, `fetch_all`, `list` seul |
| Compter | `count_by_{filter}(tenant_id)` | `get_count`, `count` seul |
| Créer | `create(entity)` | `save`, `add`, `insert`, `persist` |
| Mettre à jour | `update(entity)` | `save`, `modify`, `patch` |
| Supprimer (soft) | `delete(id, tenant_id)` | `remove`, `destroy`, `deactivate` |

### 3.3 Règles absolues

**R-REPO-1** — `db.query()` interdit partout. Uniquement `select()` + `db.execute()`.

**R-REPO-2** — Tout `select()` sans `_apply_tenant_filter()` = violation P0.

**R-REPO-3** — `list_*` retourne toujours `tuple[list[T], int]`.

**R-REPO-4** — `flush()` dans `create()`/`update()`. Jamais `commit()`.

**R-REPO-5** — Les repositories n'instancient jamais d'autres repositories. L'orchestration appartient aux services.

**R-REPO-6** — `joinedload()` pour les relations attendues systématiquement. `selectinload()` pour les listes larges (> 100 éléments prévisibles).

---

## 4. Services

### 4.1 Structure

```python
class InvoiceService:
    """Service factures — logique métier et orchestration.

    Responsibilities:
        - Validation métier (règles CGV, états autorisés)
        - Orchestration multi-repository
        - Génération de données calculées (numéros, totaux)
        - Notifications async (best-effort)

    Invariants:
        - Jamais de db.execute() direct — uniquement self.repo.*
        - Jamais de db.commit() — responsabilité de l'endpoint
        - Toute exception métier = HTTPException (convention projet)
        - Notifications Celery = try/except sans raise
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = InvoiceRepository(db)
        self.reservation_repo = ReservationRepository(db)

    # ── Lecture ───────────────────────────────────────────────────────────────
    def get_invoice_or_404(self, invoice_id: int, tenant_id: int) -> Invoice:
        invoice = self.repo.get_by_id(invoice_id, tenant_id)
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.INVOICE_NOT_FOUND,
            )
        return invoice

    def list_invoices(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        status_filter: Optional[str] = None,
    ) -> tuple[list[Invoice], int]:
        return self.repo.list_with_count(tenant_id, skip, limit, status_filter)

    # ── Écriture ──────────────────────────────────────────────────────────────
    def create_invoice(self, data: InvoiceCreate, tenant_id: int) -> Invoice:
        """Crée une facture depuis une réservation.

        Raises:
            HTTPException 404: Réservation introuvable
            HTTPException 409: Facture déjà existante pour cette réservation
        """
        self._validate_reservation_invoiceable(data.reservation_id, tenant_id)
        invoice = Invoice(
            tenant_id=tenant_id,
            invoice_number=self._generate_invoice_number(tenant_id),
            reservation_id=data.reservation_id,
            issue_date=data.issue_date,
            due_date=data.due_date,
            status="draft",
            total_amount_cents=0,
            paid_amount_cents=0,
        )
        invoice = self.repo.create(invoice)
        self._notify_invoice_created(invoice)
        return invoice

    # ── Méthodes privées ──────────────────────────────────────────────────────
    def _validate_reservation_invoiceable(self, reservation_id: int, tenant_id: int) -> None:
        """Validation métier — lève HTTPException si règle violée."""
        reservation = self.reservation_repo.get_by_id(reservation_id, tenant_id)
        if not reservation:
            raise HTTPException(status_code=404, detail=ErrorMessages.RESERVATION_NOT_FOUND)
        if reservation.invoice:
            raise HTTPException(status_code=409, detail=ErrorMessages.INVOICE_ALREADY_EXISTS)

    def _generate_invoice_number(self, tenant_id: int) -> str:
        """Génère numéro unique via séquence Redis INCR (thread-safe)."""
        # Voir R-SVC-1 — Redis INCR obligatoire
        from app.core.redis import get_redis_client
        redis = get_redis_client()
        year = date.today().year
        seq = redis.incr(f"invoice_seq:{tenant_id}:{year}")
        return f"INV-{year}-{seq:04d}"

    def _notify_invoice_created(self, invoice: Invoice) -> None:
        """Notification async best-effort — ne bloque jamais le flux principal."""
        try:
            from app.tasks.notifications import send_invoice_created_email
            send_invoice_created_email.delay(invoice_id=invoice.id)
        except Exception:
            logger.exception("Notification failed for invoice %s", invoice.id)
```

### 4.2 Règles absolues

**R-SVC-1 — Génération de références séquentielles** : Redis `INCR` obligatoire. Interdit : `set[str]` classe-level (non thread-safe multi-worker), `random`, `uuid` pour des références lisibles.

**R-SVC-2 — Exceptions** : uniquement `HTTPException`. Interdits comme exceptions remontant : `ValueError`, `RuntimeError`, `Exception` brute. Ces types doivent être catchés et convertis en `HTTPException` avant de remonter.

**R-SVC-3 — Accès DB** : uniquement via `self.repo.*`. Interdit : `self.db.execute()`, `self.db.query()` directement dans un service.

**R-SVC-4 — Longueur des méthodes** : 40 lignes max. Au-delà, extraire en `_validate_*`, `_compute_*`, `_build_*`, `_notify_*`.

**R-SVC-5 — Notifications Celery** : toujours dans `try/except Exception` sans `raise`. Le failure d'une notification ne doit jamais rollback une opération métier réussie.

**R-SVC-6 — Commit** : jamais dans un service. Le service crée/modifie, l'endpoint committe.

---

## 5. Endpoints FastAPI

### 5.1 Pattern de base

```python
import logging
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invoices", tags=["Invoices"])   # prefix/tags ICI, pas dans __init__


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice(
    # 1. Path params (aucun ici)
    # 2. Query params (aucun ici)
    invoice_data: InvoiceCreate,                                    # 3. Body
    # 4. Dépendances génériques (aucune ici)
    db: Session = Depends(get_db),                                  # 5. DB
    current_user: User = Depends(get_current_user),                 # 6. Auth
) -> InvoiceResponse:
    """Crée une nouvelle facture depuis une réservation confirmée.

    Returns:
        InvoiceResponse: La facture créée avec son numéro généré.

    Raises:
        404: Réservation introuvable ou appartenant à un autre tenant.
        409: Une facture existe déjà pour cette réservation.
    """
    service = InvoiceService(db)
    try:
        invoice = service.create_invoice(invoice_data, current_user.tenant_id)
        db.commit()
        db.refresh(invoice)                # OBLIGATOIRE après commit sur création
        return InvoiceResponse.model_validate(invoice)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in create_invoice for tenant %s", current_user.tenant_id)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Une erreur interne est survenue",
        )


@router.get("", response_model=PaginatedResponse[InvoiceList])
def list_invoices(
    status_filter: Optional[str] = Query(None, description="Filtrer par statut"),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[InvoiceList]:
    """Liste les factures du tenant courant avec pagination."""
    service = InvoiceService(db)
    invoices, total = service.list_invoices(
        tenant_id=current_user.tenant_id,
        skip=pagination.skip,
        limit=pagination.limit,
        status_filter=status_filter,
    )
    return PaginatedResponse(
        items=[InvoiceList.model_validate(i) for i in invoices],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )
```

### 5.2 Ordre des paramètres (standard universel)

```python
def endpoint_name(
    path_param_1: int,                              # 1. Path params
    path_param_2: str,
    query_param: Optional[str] = Query(None),       # 2. Query params
    body: CreateSchema = Body(...),                 # 3. Body
    pagination: PaginationParams = Depends(),       # 4. Dépendances génériques
    db: Session = Depends(get_db),                  # 5. DB
    current_user: User = Depends(get_current_user), # 6. Auth (toujours en dernier)
) -> ResponseSchema:
```

### 5.3 Règles absolues

**R-END-1** — `response_model=` obligatoire sur chaque route sans exception.

**R-END-2** — `status_code=` explicite sur `POST` (`201`) et `DELETE` (`204`). `GET`/`PATCH`/`PUT` sont `200` par défaut.

**R-END-3** — Envelope de réponse : **objet direct** uniquement (pas de `{ "data": ... }` wrapper). Pydantic `response_model` suffit.

**R-END-4** — `logger = logging.getLogger(__name__)` en haut de chaque fichier endpoint.

**R-END-5** — Pattern try/except obligatoire sur tout endpoint mutant (`POST`, `PATCH`, `DELETE`) :
```python
try:
    result = service.operation(...)
    db.commit()
    db.refresh(result)   # sur création
    return Schema.model_validate(result)
except HTTPException:
    raise
except Exception:
    logger.exception("...")
    db.rollback()
    raise HTTPException(status_code=500, detail="Erreur interne")
```

**R-END-6** — `prefix=` et `tags=[]` dans le fichier endpoint, jamais dans `__init__.py`.

**R-END-7** — `db.refresh()` après `db.commit()` : obligatoire sur création, optionnel sur update si l'entité est déjà fraîche en mémoire.

---

## 6. Tests

### 6.1 Structure des fichiers

```
tests/
├── conftest.py                     ← fixtures communes (test_db, client, admin_token)
├── integration/
│   └── test_{feature}.py          ← endpoint + workflow complet
└── unit/
    └── test_{module}.py            ← service ou repo isolé, sans HTTP
```

### 6.2 Nommage

```python
# Convention : test_{action}_{contexte}_{résultat_attendu}
def test_create_invoice_valid_reservation_returns_201(): ...
def test_create_invoice_reservation_not_found_returns_404(): ...
def test_create_invoice_already_invoiced_returns_409(): ...
def test_list_invoices_cross_tenant_returns_empty(): ...
def test_add_payment_invoice_paid_returns_400(): ...
```

### 6.3 Pattern de test d'intégration

```python
@pytest.fixture
def invoice_inv(test_db, customer_inv, reservation_inv):
    """Préfixe _inv pour éviter collision avec autres modules."""
    invoice = Invoice(
        tenant_id=1,
        invoice_number="INV-2026-0001",
        reservation_id=reservation_inv.id,
        status="draft",
        total_amount_cents=10000,
        paid_amount_cents=0,
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=30),
    )
    test_db.add(invoice)
    test_db.flush()        # JAMAIS commit() dans une fixture
    test_db.refresh(invoice)
    return invoice


def test_add_payment_happy_path(test_db, client, admin_token, invoice_inv):
    """Happy path : paiement partiel accepté."""
    response = client.post(
        f"/api/v1/invoices/{invoice_inv.id}/add-payment",
        json={"amount_cents": 5000, "payment_method": "cash", "payment_date": "2026-02-20"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["paid_amount_cents"] == 5000


def test_add_payment_cross_tenant_returns_404(test_db, client, other_tenant_token, invoice_inv):
    """Isolation tenant : un autre tenant ne voit pas cette facture."""
    response = client.post(
        f"/api/v1/invoices/{invoice_inv.id}/add-payment",
        json={"amount_cents": 5000, "payment_method": "cash", "payment_date": "2026-02-20"},
        headers={"Authorization": f"Bearer {other_tenant_token}"},
    )
    assert response.status_code == 404   # Pas 403 — évite info leakage
```

### 6.4 Matrice de couverture minimale par fichier d'intégration

| Test | HTTP attendu | Obligatoire |
|------|-------------|------------|
| Happy path création | 201 | ✅ |
| Happy path lecture | 200 | ✅ |
| Ressource introuvable | 404 | ✅ |
| Cross-tenant isolation | 404 | ✅ **P0** |
| Payload invalide | 422 | ✅ |
| Règle métier violée | 400 ou 409 | ✅ si applicable |
| Non authentifié | 401 | ✅ |

### 6.5 Règles absolues

**R-TEST-1** — `flush()` dans les fixtures, jamais `commit()`. La transaction reste ouverte pour rollback entre tests.

**R-TEST-2** — Fixtures préfixées par module (`_inv`, `_dep`, `_pay`, etc.).

**R-TEST-3** — `time.sleep()` interdit. Si nécessaire, c'est un design smell à corriger.

**R-TEST-4** — `@pytest.mark.asyncio` obligatoire sur toutes les fonctions `async def`.

**R-TEST-5** — Test cross-tenant obligatoire sur tout endpoint métier (P0).

**R-TEST-6** — Nom de test en anglais, format `test_{action}_{context}_{expected}`.

**R-TEST-7** — Mocks minimum. Préférer les implémentations réelles. Exception : services externes (email, Celery tasks).

---

## 7. Frontend TypeScript

### 7.1 Types (`src/types/`)

```typescript
// ─ Fichiers : snake_case.ts ─────────────────────────────────────────────────

// ─ Union types pour statuts ──────────────────────────────────────────────────
export type InvoiceStatus = 'draft' | 'sent' | 'paid' | 'overdue' | 'cancelled'
export type PaymentMethod = 'cash' | 'card' | 'transfer' | 'check'

// ─ Interface liste (champs essentiels) ───────────────────────────────────────
export interface InvoiceListItem {
  id: number
  invoice_number: string
  status: InvoiceStatus
  total_amount_cents: number      // _cents : entier brut
  paid_amount_cents: number
  is_overdue: boolean
  created_at: string              // ISO 8601
}

// ─ Interface détail (étend List) ─────────────────────────────────────────────
export interface InvoiceDetail extends InvoiceListItem {
  reservation_id: number
  notes: string | null            // null explicite (pas undefined)
  charges: InvoiceCharge[]
  payments: PaymentRecord[]
  total_amount_euros: number      // _euros : computed_field backend
  paid_amount_euros: number
  remaining_amount_cents: number
}

// ─ Requests ──────────────────────────────────────────────────────────────────
export interface InvoiceCreateRequest {
  reservation_id: number
  issue_date: string              // ISO 8601
  due_date: string
}

export interface AddPaymentRequest {
  amount_cents: number
  payment_method: PaymentMethod
  payment_date: string
}
```

**Règles types :**

| Règle | Convention | Interdit |
|-------|-----------|---------|
| Montants bruts | `_cents` (number) | `_amount` sans suffixe |
| Montants calculés | `_euros` (number) | `float`, `decimal` |
| Dates | `string` (ISO 8601) | `Date`, `Moment` |
| Nullable | `T \| null` | `T \| undefined`, `T?` pour champs présents |
| Types génériques | `unknown` + guard | `any` — **interdit** |
| Statuts | `type X = 'a' \| 'b'` | `enum X` (TS enum) |

### 7.2 API Calls (`src/api/`)

```typescript
// src/api/invoices.ts
import apiClient from './client'
import { getAPIError } from '@/lib/api-error'           // centralisé
import type { InvoiceListItem, InvoiceDetail, InvoiceCreateRequest } from '@/types/invoice'

export const invoicesApi = {

  getInvoices: async (params?: {
    page?: number
    page_size?: number
    status?: InvoiceStatus
  }): Promise<{ items: InvoiceListItem[]; total: number }> => {
    const skip = ((params?.page ?? 1) - 1) * (params?.page_size ?? 20)
    const { data } = await apiClient.get('/invoices', {
      params: { skip, limit: params?.page_size ?? 20, ...(params?.status && { status_filter: params.status }) },
    })
    return { items: data.items ?? [], total: data.total ?? 0 }
  },

  getInvoice: async (id: number): Promise<InvoiceDetail> => {
    const { data } = await apiClient.get(`/invoices/${id}`)
    return data
  },

  createInvoice: async (payload: InvoiceCreateRequest): Promise<InvoiceDetail> => {
    const { data } = await apiClient.post('/invoices', payload)
    return data
  },

  addPayment: async (id: number, payload: AddPaymentRequest): Promise<InvoiceDetail> => {
    const { data } = await apiClient.post(`/invoices/${id}/add-payment`, payload)
    return data
  },
}
```

### 7.3 Gestion des erreurs centralisée (obligatoire)

```typescript
// src/lib/api-error.ts
export type APIError = {
  response?: {
    data?: {
      detail?: string
    }
  }
}

export const getAPIError = (err: unknown, fallback = 'Une erreur est survenue'): string =>
  (err as APIError)?.response?.data?.detail ?? fallback
```

Usage **unique et obligatoire** dans tous les `onError` :
```typescript
onError: (err) => {
  setError(getAPIError(err))
},
```

### 7.4 React Query

```typescript
// ─ queryKey : [entité, ...discriminants] ─────────────────────────────────────
queryKey: ['invoices']                          // liste
queryKey: ['invoices', id]                      // détail
queryKey: ['invoices', { status, page }]        // liste filtrée
queryKey: ['customers', id, 'history']          // sub-resource

// ─ Pattern page complète ─────────────────────────────────────────────────────
const { data, isLoading, error } = useQuery({
  queryKey: ['invoices', { page, statusFilter }],
  queryFn: () => invoicesApi.getInvoices({ page, status: statusFilter || undefined }),
})

const createMutation = useMutation({
  mutationFn: (payload: InvoiceCreateRequest) => invoicesApi.createInvoice(payload),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['invoices'] })
    onClose()
  },
  onError: (err) => {
    setError(getAPIError(err))
  },
})
```

### 7.5 Règles absolues frontend

**R-FE-1** — `getAPIError()` depuis `@/lib/api-error`. Pattern inline interdit.

**R-FE-2** — Appels API uniquement via `{entity}Api`. Interdit : `apiClient.get(...)` dans un composant ou une page.

**R-FE-3** — `any` interdit. Utiliser `unknown` + type guard ou type explicite.

**R-FE-4** — `onSuccess` doit toujours invalider les queries parentes puis fermer le modal.

**R-FE-5** — `queryKey` commence toujours par le nom de l'entité (string littérale).

**R-FE-6** — Nullable = `T | null` (pas `T | undefined`). Un champ présent dans la réponse backend est soit typé soit `null`.

**R-FE-7** — Les `_euros` et champs calculés viennent du backend (`@computed_field`). Ne pas les recalculer côté frontend. Ne pas stocker de doublons.

---

## 8. Constantes et Enums

### 8.1 Backend (`app/constants/`)

```python
# app/constants/business.py

class InvoiceStatus(str, Enum):
    """Statuts possibles d'une facture.

    Transitions autorisées :
        draft → sent → paid
        sent → overdue (automatique)
        draft|sent → cancelled
    """
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class PaymentMethod(str, Enum):
    CASH = "cash"
    CARD = "card"
    TRANSFER = "transfer"
    CHECK = "check"


# Constantes métier — avec annotation de type et docstring
DEPOSIT_RATE: float = 3.0
"""Caution = 3× montant facture (CGV art. 4)."""

INVOICE_NUMBER_PREFIX: str = "INV"
INVOICE_NUMBER_YEAR_FORMAT: str = "%Y"
INVOICE_NUMBER_SEQ_PADDING: int = 4          # INV-2026-0001
```

**Règles :**
- Toute string magique liée à un concept métier → constante dans `app/constants/`.
- Tout entier magique (taux, seuil, padding) → constante nommée avec docstring.
- Les `str(Enum)` sont préférés aux `IntEnum` pour la lisibilité en DB et en JSON.

### 8.2 Frontend

```typescript
// src/constants/invoice.ts
export const INVOICE_STATUS_LABELS: Record<InvoiceStatus, string> = {
  draft: 'Brouillon',
  sent: 'Envoyée',
  paid: 'Payée',
  overdue: 'En retard',
  cancelled: 'Annulée',
}

export const INVOICE_STATUS_COLORS: Record<InvoiceStatus, string> = {
  draft: 'gray',
  sent: 'blue',
  paid: 'green',
  overdue: 'red',
  cancelled: 'gray',
}
```

---

## 9. Migrations Alembic

### 9.1 Nommage

- Fichier : `{revision_id}_{snake_case_description}.py`
- `revision` : 12 caractères hex lowercase (ex: `f2g3h4i5j6k7`)
- Description : verbe à l'infinitif + sujet (`add_payments_table`, `add_status_to_reservations`)

### 9.2 Pattern obligatoire

```python
"""Add payments table.

Revision ID: f2g3h4i5j6k7
Revises: e1f2a3b4c5d6
Create Date: 2026-02-18 10:00:00

Strategy: expand only (new table, no column removal)
Rollback: drop table — safe, no data loss risk
"""

from typing import Union
import sqlalchemy as sa
from alembic import op

revision: str = 'f2g3h4i5j6k7'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        'payments',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('invoice_id', sa.BigInteger(), nullable=False),
        sa.Column('amount_cents', sa.BigInteger(), nullable=False),
        sa.Column('payment_method', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], name='fk_payments_invoice_id', ondelete='RESTRICT'),
        sa.CheckConstraint('amount_cents > 0', name='check_payment_amount_positive'),
        sa.CheckConstraint(
            "payment_method IN ('cash', 'card', 'transfer', 'check')",
            name='check_payment_method_valid',
        ),
    )
    op.create_index('ix_payments_tenant_invoice', 'payments', ['tenant_id', 'invoice_id'])


def downgrade() -> None:
    op.drop_index('ix_payments_tenant_invoice', table_name='payments')
    op.drop_table('payments')
```

### 9.3 Règles absolues

**R-MIG-1** — Stratégie expand/contract uniquement. Toute suppression de colonne existante = migration en 2 phases minimum.

**R-MIG-2** — Tout `CheckConstraint` dans la migration doit avoir `name=` explicite.

**R-MIG-3** — Tout `ForeignKeyConstraint` doit avoir `name=` et `ondelete=`.

**R-MIG-4** — `downgrade()` toujours implémenté et testé. Jamais `pass`.

**R-MIG-5** — Commentaire de migration : stratégie (expand/contract), risque rollback.

**R-MIG-6** — `DateTime` toujours avec `timezone=True`.

---

## 10. Points transverses

### 10.1 Logging

```python
# En haut de chaque fichier service ET endpoint
import logging
logger = logging.getLogger(__name__)

# Niveaux :
logger.debug("...")     # Détail technique (désactivé en prod)
logger.info("...")      # Événement métier normal (ex: "Invoice INV-2026-001 created")
logger.warning("...")   # Situation anormale non bloquante
logger.exception("...")  # Exception catchée — inclut stacktrace automatiquement
```

**Règle** : tout `except Exception` doit contenir un `logger.exception(...)`. Catch silencieux interdit.

### 10.2 Sécurité

- Tout endpoint authentifié via `Depends(get_current_user)`.
- RBAC vérifié côté backend via `Depends(require_role(...))`. Jamais côté frontend uniquement.
- `tenant_id` extrait du token, jamais du body de la requête.
- Rate limiting sur les endpoints auth (déjà en place via Redis).

### 10.3 Performance

- N+1 interdit : tout `relationship()` en `lazy="select"` doit être pré-chargé via `joinedload()` ou `selectinload()` dans le repository.
- Pagination obligatoire sur toute route listant des entités (max `page_size=1000`).
- `COUNT(*)` via subquery dans `list_with_count()` — une seule requête COUNT par appel.

---

## 11. Décisions architecturales tranchées

Ces décisions sont **définitives**. Toute dérogation nécessite un ticket + validation senior.

### T1 — Génération de références séquentielles

**Décision : Redis INCR**

```python
def _generate_reference(self, prefix: str, tenant_id: int) -> str:
    year = date.today().year
    seq = redis_client.incr(f"{prefix}_seq:{tenant_id}:{year}")
    return f"{prefix}-{year}-{seq:04d}"
```

- **Interdit** : `set[str]` au niveau classe (non thread-safe multi-worker)
- **Interdit** : `uuid4()` pour des références lisibles par humain
- **Fallback** : séquence DB Alembic si Redis indisponible (à implémenter)

---

### T2 — Exceptions dans les services

**Décision : HTTPException universelle**

Les services lèvent uniquement `HTTPException`. Aucune `ValueError`, `RuntimeError` ou exception custom ne doit remonter jusqu'à l'endpoint sans être convertie.

```python
# ✅ Autorisé
raise HTTPException(status_code=400, detail=ErrorMessages.INVOICE_PAID_NO_MODIFY)

# ❌ Interdit (remonterait en 500 non documenté)
raise ValueError("Invoice already paid")
```

---

### T3 — Envelope de réponse backend

**Décision : objet direct (pas de wrapper `{ data: ... }`)**

Tous les endpoints retournent l'objet directement. `response_model=` Pydantic gère la sérialisation.

```python
# ✅
return InvoiceResponse.model_validate(invoice)

# ❌ Éliminé
return {"data": invoice, "status": "ok"}
```

Côté frontend : plus de fallback `data.data || data`. Uniquement `data`.

---

### T4 — `lazy=` sur les relationships

**Décision : `lazy=` toujours explicite**

```python
# ✅ Obligatoire
charges: Mapped[list["InvoiceCharge"]] = relationship(
    "InvoiceCharge",
    lazy="select",          # explicite
)

# ❌ Interdit
charges: Mapped[list["InvoiceCharge"]] = relationship("InvoiceCharge")
```

Valeurs autorisées : `"select"` ou `"joined"`. Tout autre mode nécessite justification.

---

### T5 — Gestion d'erreur Axios frontend

**Décision : `getAPIError()` centralisé obligatoire**

```typescript
// src/lib/api-error.ts — fichier à créer (Session S)
export type APIError = { response?: { data?: { detail?: string } } }
export const getAPIError = (err: unknown, fallback = 'Une erreur est survenue'): string =>
  (err as APIError)?.response?.data?.detail ?? fallback
```

Le pattern inline est **interdit** dans tous les composants après harmonisation.

---

### T6 — `flush()` vs `commit()` dans les fixtures

**Décision : `flush()` uniquement dans les fixtures**

```python
# ✅
test_db.add(entity)
test_db.flush()
test_db.refresh(entity)
return entity

# ❌ Interdit dans une fixture
test_db.commit()
```

Raison : `commit()` dans une fixture sort de la transaction de test, empêche le rollback automatique entre tests et peut contaminer l'état de tests suivants.

---

### T7 — Style SQLAlchemy

**Décision : `select()` + `db.execute()` exclusivement pour tout nouveau code**

```python
# ✅ Nouveau code — toujours
result = db.execute(select(Invoice).where(Invoice.id == id)).scalar_one_or_none()

# ❌ Interdit pour tout nouveau code (SQLAlchemy 1.x legacy)
result = db.query(Invoice).filter(Invoice.id == id).first()
```

> **Scope** : s'applique à tout code *nouveau ou modifié*. Pour le code legacy existant non touché, voir T10 (migration progressive). Ne jamais écrire de nouveau `db.query()`.

---

### T8 — `model_config` sur les schemas

**Décision : héritage strict, pas de répétition**

- `extra="forbid"` sur `BaseSchema` (hérité par tous les inputs)
- `from_attributes=True` sur `EntityResponseSchema` (hérité par tous les outputs)
- Ne jamais redéfinir `model_config` sur une sous-classe sauf exception justifiée

---

### T9 — `@computed_field` euros

**Décision : uniquement sur `EntityResponse` (détail)**

Les `EntityList` n'exposent que les `_cents`. Les conversions euros sont calculées une fois sur le détail. Raison : éviter N calculs Python sur des listes de 100+ entités.

---

### T10 — `db.query()` legacy

**Décision : migration progressive obligatoire**

Tout fichier touché dans une PR doit convertir ses `db.query()` en `select()`. La coexistence est tolérée uniquement pour le code legacy *non touché par la PR* ; aucun nouveau `db.query()` n'est jamais accepté.

> **Relation avec T7** : T7 est la règle générale (nouveau code). T10 est la règle de migration (code legacy existant). Les deux sont complémentaires et non contradictoires.

---

## Checklist de revue de PR

Avant tout merge, vérifier :

### Backend
- [ ] Tout fichier Python édité avait `prepare()` appelé
- [ ] Aucun `db.query()` ajouté
- [ ] Aucun `db.commit()` dans un service ou repository
- [ ] `tenant_id` filtré sur toute requête (isolation)
- [ ] `response_model=` présent sur chaque route
- [ ] `lazy=` explicite sur toute nouvelle `relationship()`
- [ ] `CheckConstraint` avec `name=` explicite
- [ ] Test cross-tenant présent
- [ ] `logger.exception()` dans tout `except Exception`

### Frontend
- [ ] `getAPIError()` utilisé (pas de pattern inline)
- [ ] Aucun `any` ajouté
- [ ] `queryKey` commence par le nom de l'entité
- [ ] `invalidateQueries()` dans `onSuccess`
- [ ] Appels API via `{entity}Api` uniquement

### Tests
- [ ] `flush()` dans les fixtures (pas `commit()`)
- [ ] Nom de test : `test_{action}_{context}_{expected}`
- [ ] Happy path + 404 + cross-tenant + 422 couverts

### Migrations
- [ ] `downgrade()` implémenté
- [ ] Tous les `CheckConstraint` avec `name=`
- [ ] Commentaire stratégie expand/contract

---

## 12. Patterns avancés — Scaling & Résilience

> Ces patterns s'appliquent dès que le volume dépasse les seuils indiqués.
> Implémentation progressive : P0 immédiat, P1 prochain sprint, P2+ roadmap.

---

### 12.1 Idempotency Keys — POST/PUT critiques (P0)

**Seuil** : tout endpoint créant une transaction financière (paiement, facture, caution).

**Problème** : réseau flaky → client retry → double débit.

```python
# app/core/idempotency.py
import json, hashlib
from fastapi import Header
from app.core.redis import get_redis_client

IDEMPOTENCY_TTL = 86400  # 24h

def idempotency_key_guard(
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """Dépendance FastAPI — à injecter sur tout endpoint financier."""
    return idempotency_key


def check_or_store_idempotency(
    key: str,
    tenant_id: int,
    execute_fn,            # callable → résultat sérialisable
):
    """
    Si key déjà vu → retourne réponse mémorisée.
    Sinon → exécute fn, stocke résultat, retourne résultat.
    Pattern : exactly-once semantics côté serveur.
    """
    redis = get_redis_client()
    redis_key = f"idempotency:{tenant_id}:{key}"

    cached = redis.get(redis_key)
    if cached:
        return json.loads(cached), True  # (résultat, was_cached)

    result = execute_fn()
    redis.setex(redis_key, IDEMPOTENCY_TTL, json.dumps(result))
    return result, False


# Usage dans endpoint
@router.post("/invoices/{id}/add-payment", response_model=InvoiceResponse, status_code=200)
def add_payment(
    id: int,
    payload: AddPaymentRequest,
    idempotency_key: str | None = Depends(idempotency_key_guard),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InvoiceResponse:
    service = InvoiceService(db)

    def execute():
        payment = service.add_payment(id, payload, current_user.tenant_id)
        db.commit()
        db.refresh(payment)
        return InvoiceResponse.model_validate(payment).model_dump(mode="json")

    if idempotency_key:
        result, was_cached = check_or_store_idempotency(
            idempotency_key, current_user.tenant_id, execute
        )
        return result
    return execute()
```

**Frontend** : générer un UUID par soumission de formulaire, pas par session.

```typescript
// src/lib/idempotency.ts
import { v4 as uuidv4 } from 'uuid'

export const generateIdempotencyKey = (): string => uuidv4()

// Usage dans mutation
const mutation = useMutation({
  mutationFn: (payload: AddPaymentRequest) => {
    const key = generateIdempotencyKey()   // Nouveau à chaque tentative user
    return invoicesApi.addPayment(invoiceId, payload, key)
  },
})
```

---

### 12.2 Optimistic Locking — Version Column (P1)

**Seuil** : toute entité modifiable par plusieurs agents simultanément (Reservation, Invoice).

**Problème** : deux agents modifient le même statut → last-write-wins → perte silencieuse.

```python
# Dans le modèle
class Reservation(Base, TimestampMixin, TenantMixin):
    ...
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

# Dans le schéma de mise à jour
class ReservationUpdate(BaseSchema):
    ...
    version: int = Field(..., description="Version actuelle — protection concurrence")

# Dans le repository
def update_with_lock(self, entity_id: int, tenant_id: int, version: int, data: dict) -> Reservation:
    """Lève 409 si version ne correspond pas (concurrent edit détecté)."""
    stmt = (
        select(Reservation)
        .where(
            Reservation.id == entity_id,
            Reservation.tenant_id == tenant_id,
            Reservation.version == version,      # Filtre clé
        )
        .with_for_update()                        # Lock row pendant transaction
    )
    entity = self.db.execute(stmt).scalar_one_or_none()
    if not entity:
        raise HTTPException(
            status_code=409,
            detail="Modification concurrente détectée. Rechargez et réessayez.",
        )
    for k, v in data.items():
        setattr(entity, k, v)
    entity.version += 1                          # Incrément obligatoire
    self.db.flush()
    self.db.refresh(entity)
    return entity
```

**Frontend** : toujours inclure `version` dans les PATCH body, afficher message d'erreur 409.

```typescript
// Si 409 → proposer reload
onError: (err) => {
  if ((err as APIError).response?.status === 409) {
    setError('Un autre utilisateur a modifié cet enregistrement. Rechargez la page.')
    queryClient.invalidateQueries({ queryKey: ['reservations', id] })
  } else {
    setError(getAPIError(err))
  }
}
```

---

### 12.3 Circuit Breaker — Redis & Services externes (P1)

**Seuil** : tout appel réseau vers Redis, Celery, services tiers.

**Problème** : Redis down → chaque requête attend timeout 30s → cascade de threads bloqués.

```python
# app/core/circuit_breaker.py
import time, threading
from enum import Enum
from dataclasses import dataclass, field

class CircuitState(Enum):
    CLOSED = "closed"        # Normal — calls passent
    OPEN = "open"            # Fail fast — no calls
    HALF_OPEN = "half_open"  # Test — 1 call probe

@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failures: int = field(default=0, init=False)
    _opened_at: float | None = field(default=None, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def call(self, fn, *args, fallback=None, **kwargs):
        """Exécute fn avec circuit breaker. Retourne fallback si OPEN."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._opened_at > self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    logger.info("Circuit %s → HALF_OPEN (probing)", self.name)
                else:
                    return fallback   # Fast fail

        try:
            result = fn(*args, **kwargs)
            with self._lock:
                if self._state == CircuitState.HALF_OPEN:
                    self._state = CircuitState.CLOSED
                    self._failures = 0
                    logger.info("Circuit %s → CLOSED (recovered)", self.name)
            return result
        except Exception as e:
            with self._lock:
                self._failures += 1
                if self._failures >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    self._opened_at = time.monotonic()
                    logger.error("Circuit %s → OPEN after %d failures", self.name, self._failures)
            return fallback

# Singletons partagés (init dans app/main.py lifespan)
redis_circuit = CircuitBreaker(name="redis", failure_threshold=5, recovery_timeout=30.0)
celery_circuit = CircuitBreaker(name="celery", failure_threshold=3, recovery_timeout=60.0)

# Usage dans cache
def get_cached(key: str) -> Any | None:
    return redis_circuit.call(redis_client.get, key, fallback=None)
```

---

### 12.4 Unit of Work — Transactions explicites (P1)

**Problème actuel** : plusieurs services dans un même endpoint font chacun `flush()` → difficile de rollback atomiquement si l'un échoue à mi-chemin.

```python
# app/core/unit_of_work.py
from contextlib import contextmanager
from sqlalchemy.orm import Session

class UnitOfWork:
    """Gestionnaire de transaction explicite pour workflows multi-services."""

    def __init__(self, db: Session):
        self.db = db
        self.invoice_repo = InvoiceRepository(db)
        self.reservation_repo = ReservationRepository(db)
        self.stock_repo = StockItemRepository(db)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.db.rollback()
        else:
            self.db.commit()

# Usage dans endpoint complexe (ex: confirm + facturer + déduire stock)
@router.post("/reservations/{id}/confirm", response_model=ReservationResponse)
def confirm_reservation(id: int, db: Session = Depends(get_db), current_user = Depends(...)):
    with UnitOfWork(db) as uow:
        reservation = uow.reservation_repo.get_by_id(id, current_user.tenant_id)
        # 1. Confirmer réservation
        reservation.status = "confirmed"
        uow.reservation_repo.update(reservation)
        # 2. Générer facture
        invoice = Invoice(reservation_id=id, ...)
        uow.invoice_repo.create(invoice)
        # 3. Déduire stock
        uow.stock_repo.reserve_units(reservation.lines)
        # → commit automatique en sortie de with (ou rollback si exception)
    db.refresh(reservation)
    return ReservationResponse.model_validate(reservation)
```

---

### 12.5 Domain Events — Découplage inter-services (P1)

**Problème** : `reservation_service.confirm()` appelle directement `invoice_service`, `stock_service`, `notification_service` → couplage fort, testabilité réduite.

```python
# app/core/events.py
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict
from typing import Callable

@dataclass
class DomainEvent:
    occurred_at: datetime
    tenant_id: int

@dataclass
class ReservationConfirmed(DomainEvent):
    reservation_id: int
    customer_id: int

@dataclass
class InvoicePaid(DomainEvent):
    invoice_id: int
    amount_cents: int

class EventBus:
    """Bus d'événements in-process (sync). Celery pour l'async."""
    _handlers: dict[type, list[Callable]] = defaultdict(list)

    @classmethod
    def subscribe(cls, event_type: type, handler: Callable):
        cls._handlers[event_type].append(handler)

    @classmethod
    def publish(cls, event: DomainEvent):
        for handler in cls._handlers[type(event)]:
            try:
                handler(event)
            except Exception:
                logger.exception("Handler %s failed for event %s", handler, event)
                # Ne bloque jamais le flux principal

# Abonnements (dans app/main.py lifespan ou app/events/handlers.py)
EventBus.subscribe(ReservationConfirmed, on_reservation_confirmed_create_invoice)
EventBus.subscribe(ReservationConfirmed, on_reservation_confirmed_reserve_stock)
EventBus.subscribe(InvoicePaid, on_invoice_paid_release_deposit)

# Dans le service — émet l'événement, ne connaît pas les handlers
class ReservationService:
    def confirm_reservation(self, reservation_id: int, tenant_id: int) -> Reservation:
        res = self._validate_and_confirm(reservation_id, tenant_id)
        EventBus.publish(ReservationConfirmed(
            occurred_at=utcnow(),
            tenant_id=tenant_id,
            reservation_id=res.id,
            customer_id=res.customer_id,
        ))
        return res
```

---

### 12.6 ETag / Conditional Requests (P2)

**Seuil** : endpoints GET sur ressources volumineuses appelés > 100/min.

```python
# app/core/etag.py
import hashlib, json
from fastapi import Request, Response

def compute_etag(data: dict | list) -> str:
    content = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(content.encode()).hexdigest()[:16]

def etag_response(request: Request, data: dict, response: Response) -> dict | Response:
    """Retourne 304 si ETag identique, sinon data + header ETag."""
    etag = f'"{compute_etag(data)}"'
    if request.headers.get("If-None-Match") == etag:
        return Response(status_code=304)
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
    return data

# Usage endpoint
@router.get("/products/{id}", response_model=ProductResponse)
def get_product(id: int, request: Request, response: Response, ...):
    product = service.get_product(id, tenant_id)
    data = ProductResponse.model_validate(product).model_dump(mode="json")
    return etag_response(request, data, response)
```

---

### 12.7 Cursor Pagination — Grands datasets (P2)

**Seuil** : tables > 100k lignes ou export/scroll infini.

```python
# app/schemas/pagination.py
class CursorPage(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None    # None = dernière page
    has_more: bool

# app/core/cursor.py
import base64, json
from datetime import datetime

def encode_cursor(created_at: datetime, id: int) -> str:
    payload = {"ca": created_at.isoformat(), "id": id}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()

def decode_cursor(cursor: str) -> tuple[datetime, int]:
    payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
    return datetime.fromisoformat(payload["ca"]), payload["id"]

# Dans repository
def list_cursor(self, tenant_id: int, cursor: str | None, limit: int = 50) -> CursorPage:
    query = (
        select(self.model)
        .where(self.model.tenant_id == tenant_id, self.model.is_active.is_(True))
        .order_by(self.model.created_at.desc(), self.model.id.desc())
    )
    if cursor:
        ca, cid = decode_cursor(cursor)
        query = query.where(
            or_(
                self.model.created_at < ca,
                and_(self.model.created_at == ca, self.model.id < cid),
            )
        )
    rows = self.db.execute(query.limit(limit + 1)).scalars().all()
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if has_more else None
    return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)
```

---

### 12.8 Factory / Builder Pattern — Test Data (P1)

**Problème** : fixtures répétées dans chaque fichier de test (CustomerFactory, ReservationFactory).

```python
# tests/factories.py
from datetime import date, timedelta
from app.models import Customer, Reservation, Invoice, Product

class CustomerFactory:
    """Builder fluide pour données de test — valeurs par défaut valides."""
    _defaults = {
        "tenant_id": 1,
        "customer_type": "individual",
        "first_name": "Jean",
        "last_name": "Test",
        "email": "jean.test@example.com",
        "is_active": True,
    }

    @classmethod
    def build(cls, **overrides) -> Customer:
        """Crée instance sans persister."""
        return Customer(**{**cls._defaults, **overrides})

    @classmethod
    def create(cls, db, **overrides) -> Customer:
        """Crée et persiste (flush, pas commit)."""
        obj = cls.build(**overrides)
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

class ReservationFactory:
    @classmethod
    def create(cls, db, customer_id: int, **overrides) -> Reservation:
        defaults = {
            "tenant_id": 1,
            "customer_id": customer_id,
            "reference": f"TEST-{customer_id:04d}",
            "status": "draft",
            "start_date": date.today(),
            "end_date": date.today() + timedelta(days=2),
        }
        obj = Reservation(**{**defaults, **overrides})
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

# Usage dans tests — remplace 30 lignes de fixture par 3
def test_invoice_creation(test_db, client, admin_token):
    customer = CustomerFactory.create(test_db, email="alice@test.com")
    reservation = ReservationFactory.create(test_db, customer_id=customer.id, status="confirmed")
    # ... test ...
```

---

### 12.9 Property-Based Testing — Hypothesis (P2)

**Seuil** : toute fonction pure avec règles métier (calculs de prix, validateurs, générateurs).

```python
# tests/unit/test_business_rules_hypothesis.py
from hypothesis import given, strategies as st, settings
from app.services.invoice import compute_remaining_amount

@given(
    total=st.integers(min_value=0, max_value=10_000_000),
    paid=st.integers(min_value=0, max_value=10_000_000),
)
@settings(max_examples=500)
def test_remaining_amount_never_negative(total: int, paid: int):
    """remaining_amount est TOUJOURS >= 0, quelle que soit la combinaison."""
    remaining = compute_remaining_amount(total_cents=total, paid_cents=paid)
    assert remaining >= 0

@given(
    amount=st.integers(min_value=1, max_value=100_000_000),
    rate=st.floats(min_value=0.1, max_value=10.0),
)
def test_deposit_always_positive(amount: int, rate: float):
    from app.services.deposit import compute_deposit_amount
    deposit = compute_deposit_amount(amount_cents=amount, rate=rate)
    assert deposit > 0
    assert isinstance(deposit, int)   # Toujours entier (centimes)
```

---

### 12.10 Distributed Tracing — OpenTelemetry (P2)

**Seuil** : > 3 services (API + Celery + Redis + DB) — debugging de latence impossible sans traces.

```python
# app/core/tracing.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

def setup_tracing(app, engine):
    provider = TracerProvider()
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint="http://otel-collector:4317"))
    )
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine)
    RedisInstrumentor().instrument()

# Spans manuels pour opérations critiques
tracer = trace.get_tracer(__name__)

class InvoiceService:
    def create_invoice(self, data, tenant_id):
        with tracer.start_as_current_span("invoice.create") as span:
            span.set_attribute("tenant_id", tenant_id)
            span.set_attribute("reservation_id", data.reservation_id)
            invoice = self._do_create(data, tenant_id)
            span.set_attribute("invoice_id", invoice.id)
            return invoice
```

---

### 12.11 Structured Query Logging — Slow Query Detection (P2)

```python
# app/core/database.py — à ajouter au engine config
from sqlalchemy import event
import time

SLOW_QUERY_THRESHOLD_MS = 200

@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.monotonic()

@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    elapsed_ms = (time.monotonic() - context._query_start_time) * 1000
    if elapsed_ms > SLOW_QUERY_THRESHOLD_MS:
        logger.warning(
            "SLOW_QUERY",
            extra={
                "duration_ms": round(elapsed_ms, 2),
                "statement": statement[:500],   # Tronqué pour PII
            },
        )
```

---

### 12.12 Graceful Shutdown — Celery & FastAPI (P1)

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up Marveline API")
    setup_tracing(app, engine)
    EventBus.subscribe(ReservationConfirmed, on_reservation_confirmed)
    yield
    # Shutdown — ordre important
    logger.info("Shutting down — draining connections")
    await asyncio.sleep(2)       # Laisser requêtes en cours terminer
    engine.dispose()             # Fermer pool DB proprement
    logger.info("Shutdown complete")

app = FastAPI(lifespan=lifespan)
```

```python
# app/tasks/celery_app.py — à vérifier
celery_app = Celery(...)
celery_app.conf.update(
    task_acks_late=True,             # Ack après exécution (pas avant)
    task_reject_on_worker_lost=True, # Rejeu si worker crash pendant exécution
    worker_prefetch_multiplier=1,    # 1 tâche à la fois (fairness)
)
```

---

### 12.13 Materialized Views — Dashboard Analytics (P2)

```python
# alembic/versions/XXX_add_dashboard_materialized_views.py
def upgrade():
    op.execute("""
        CREATE MATERIALIZED VIEW mv_finances_monthly AS
        SELECT
            tenant_id,
            DATE_TRUNC('month', issue_date)::date AS month,
            COUNT(*)                               AS invoice_count,
            SUM(total_amount_cents)                AS total_cents,
            SUM(paid_amount_cents)                 AS paid_cents,
            COUNT(*) FILTER (WHERE status = 'paid')    AS paid_count,
            COUNT(*) FILTER (WHERE status = 'overdue') AS overdue_count
        FROM invoices
        WHERE is_active = true
        GROUP BY tenant_id, DATE_TRUNC('month', issue_date)
        WITH DATA;

        CREATE UNIQUE INDEX ON mv_finances_monthly (tenant_id, month);
    """)

def downgrade():
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_finances_monthly")

# Refresh via Celery (toutes les heures)
@celery_app.task(name="refresh_dashboard_views")
def refresh_dashboard_views():
    with get_db_context() as db:
        db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_finances_monthly"))
        db.commit()
    logger.info("Materialized views refreshed")
```

---

### 12.14 Partial Indexes — Perf soft-delete (P1)

```python
# Dans les migrations — à ajouter sur toutes tables avec is_active
def upgrade():
    # Index partiel : ne couvre que les lignes actives (50-90% du volume)
    op.execute("""
        CREATE INDEX ix_products_active_tenant_sku
        ON products (tenant_id, sku)
        WHERE is_active = true;

        CREATE INDEX ix_reservations_active_status
        ON reservations (tenant_id, status, start_date)
        WHERE is_active = true AND status NOT IN ('cancelled', 'completed');

        CREATE INDEX ix_invoices_active_overdue
        ON invoices (tenant_id, due_date)
        WHERE is_active = true AND status = 'sent';
    """)
```

---

### 12.15 React Error Boundary (P1)

```typescript
// frontend/src/components/ui/ErrorBoundary.tsx
import React, { ReactNode, ErrorInfo } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Envoyer à Sentry si configuré
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div className="p-8 text-center">
          <h2 className="text-xl font-semibold text-red-600 mb-2">Une erreur est survenue</h2>
          <p className="text-gray-500 text-sm mb-4">{this.state.error?.message}</p>
          <button
            className="px-4 py-2 bg-primary text-white rounded"
            onClick={() => this.setState({ hasError: false, error: null })}
          >
            Réessayer
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

// Usage dans App.tsx — wrapper par route
<ErrorBoundary>
  <Suspense fallback={<PageLoader />}>
    <InvoicesPage />
  </Suspense>
</ErrorBoundary>
```

---

### 12.16 Code Splitting / Lazy Loading — Bundle (P1)

```typescript
// frontend/src/App.tsx — remplacer tous imports statiques
import { lazy, Suspense } from 'react'
import { PageLoader } from '@/components/ui/PageLoader'

// Chunking par domaine métier (pas par page)
const ProductsBundle = lazy(() => import('@/pages/products/bundle'))
const InvoicesBundle = lazy(() => import('@/pages/invoices/bundle'))
const InventoryBundle = lazy(() => import('@/pages/inventory/bundle'))
const AdminBundle    = lazy(() => import('@/pages/admin/bundle'))

// frontend/src/pages/invoices/bundle.ts — barrel export du domaine
export { default as InvoicesPage } from './InvoicesPage'
export { default as InvoiceDetailPage } from './InvoiceDetailPage'
```

```typescript
// vite.config.ts — configuration chunks optimisée
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react':  ['react', 'react-dom', 'react-router-dom'],
          'vendor-query':  ['@tanstack/react-query'],
          'vendor-charts': ['recharts'],
          'vendor-ui':     ['@radix-ui/react-dialog', '@radix-ui/react-dropdown-menu'],
        },
      },
    },
    chunkSizeWarningLimit: 400,   // Warn si chunk > 400KB
  },
})
```

---

### 12.17 Optimistic Updates — React Query (P2)

**Seuil** : actions fréquentes (toggle statut, reorder) où 200ms de latence est visible.

```typescript
const cancelMutation = useMutation({
  mutationFn: (id: number) => invoicesApi.cancelInvoice(id),

  // 1. Mise à jour immédiate du cache (avant réponse serveur)
  onMutate: async (id) => {
    await queryClient.cancelQueries({ queryKey: ['invoices'] })
    const previous = queryClient.getQueryData<InvoiceListResponse>(['invoices'])

    queryClient.setQueryData(['invoices'], (old: InvoiceListResponse) => ({
      ...old,
      items: old.items.map(inv =>
        inv.id === id ? { ...inv, status: 'cancelled' as InvoiceStatus } : inv
      ),
    }))

    return { previous }   // Contexte pour rollback
  },

  // 2. Rollback si erreur serveur
  onError: (err, id, context) => {
    queryClient.setQueryData(['invoices'], context?.previous)
    setError(getAPIError(err))
  },

  // 3. Re-sync avec serveur après succès
  onSettled: () => {
    queryClient.invalidateQueries({ queryKey: ['invoices'] })
  },
})
```

---

### 12.18 Virtual Scrolling — Listes larges (P2)

**Seuil** : listes > 500 éléments rendus simultanément (ex: catalogue produits).

```typescript
// npm install @tanstack/react-virtual
import { useVirtualizer } from '@tanstack/react-virtual'
import { useRef } from 'react'

function ProductList({ products }: { products: Product[] }) {
  const parentRef = useRef<HTMLDivElement>(null)

  const virtualizer = useVirtualizer({
    count: products.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 64,   // Hauteur estimée d'une ligne en px
    overscan: 10,             // Pré-rendre 10 items au-delà du viewport
  })

  return (
    <div ref={parentRef} style={{ height: '600px', overflow: 'auto' }}>
      <div style={{ height: `${virtualizer.getTotalSize()}px`, position: 'relative' }}>
        {virtualizer.getVirtualItems().map((virtualRow) => (
          <div
            key={virtualRow.index}
            style={{
              position: 'absolute',
              top: 0,
              transform: `translateY(${virtualRow.start}px)`,
              width: '100%',
              height: `${virtualRow.size}px`,
            }}
          >
            <ProductRow product={products[virtualRow.index]} />
          </div>
        ))}
      </div>
    </div>
  )
}
```

---

### 12.19 Contract Testing — API Pact (P2)

**Problème** : frontend et backend évoluent indépendamment → régression silencieuse de contrat.

```typescript
// frontend/tests/contract/invoices.pact.spec.ts
import { Pact } from '@pact-foundation/pact'
import { invoicesApi } from '@/api/invoices'

const provider = new Pact({
  consumer: 'marveline-frontend',
  provider: 'marveline-api',
  port: 1234,
})

describe('InvoicesApi contract', () => {
  beforeAll(() => provider.setup())
  afterAll(() => provider.finalize())

  it('GET /invoices/{id} returns InvoiceDetail shape', async () => {
    await provider.addInteraction({
      state: 'invoice 1 exists',
      uponReceiving: 'GET /invoices/1',
      withRequest: { method: 'GET', path: '/api/v1/invoices/1' },
      willRespondWith: {
        status: 200,
        body: {
          id: 1,
          invoice_number: like('INV-2026-0001'),
          status: like('draft'),
          total_amount_cents: like(10000),
          paid_amount_cents: like(0),
          charges: eachLike({ amount_cents: like(500) }),
        },
      },
    })

    const invoice = await invoicesApi.getInvoice(1)
    expect(invoice.id).toBe(1)
    expect(invoice.total_amount_cents).toBeTypeOf('number')
  })
})
```

---

### 12.20 Webhook Outbound — Intégrations tierces (P3)

```python
# app/models/webhook_endpoint.py
class WebhookEndpoint(Base, TimestampMixin, TenantMixin):
    __tablename__ = "webhook_endpoints"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    secret: Mapped[str] = mapped_column(String(64), nullable=False)   # HMAC signing
    events: Mapped[list[str]] = mapped_column(ARRAY(String(50)), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

# app/tasks/webhooks.py
import hmac, hashlib

@celery_app.task(bind=True, max_retries=5, default_retry_delay=60)
def deliver_webhook(self, endpoint_id: int, event_type: str, payload: dict):
    """Livraison avec retry exponentiel + signature HMAC."""
    with get_db_context() as db:
        endpoint = db.get(WebhookEndpoint, endpoint_id)
        if not endpoint or not endpoint.is_active:
            return

        body = json.dumps(payload)
        signature = hmac.new(
            endpoint.secret.encode(),
            body.encode(),
            hashlib.sha256,
        ).hexdigest()

        try:
            resp = httpx.post(
                endpoint.url,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Marveline-Signature": f"sha256={signature}",
                    "X-Marveline-Event": event_type,
                },
                timeout=10,
            )
            resp.raise_for_status()
        except Exception as exc:
            raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)
```

---

### 12.21 Accessibility (a11y) — Standards WCAG 2.1 AA (P2)

```typescript
// Règles à appliquer sur tous les composants

// 1. Boutons sans texte → aria-label obligatoire
<button aria-label="Fermer le modal" onClick={onClose}>
  <XIcon className="h-5 w-5" />
</button>

// 2. Modals → focus trap + role=dialog
<div
  role="dialog"
  aria-modal="true"
  aria-labelledby="modal-title"
  aria-describedby="modal-description"
>
  <h2 id="modal-title">Créer une facture</h2>

// 3. Formulaires → label explicitement lié
<label htmlFor="invoice-amount">Montant (€)</label>
<input
  id="invoice-amount"
  type="number"
  aria-required="true"
  aria-invalid={!!errors.amount}
  aria-describedby={errors.amount ? "amount-error" : undefined}
/>
{errors.amount && <span id="amount-error" role="alert">{errors.amount}</span>}

// 4. Tables → headers sémantiques
<th scope="col">Référence</th>
<th scope="col">Montant</th>

// 5. Statuts colorés → pas uniquement par couleur
<span className="text-green-600" aria-label="Statut : Payée">
  <CheckIcon aria-hidden="true" /> Payée
</span>

// 6. Navigation clavier → skip link
<a href="#main-content" className="sr-only focus:not-sr-only">
  Aller au contenu principal
</a>
```

---

### 12.22 i18n — Internationalisation (P3)

**Préparer l'infrastructure même si déploiement mono-langue pour l'instant.**

```typescript
// frontend/src/i18n/index.ts
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

i18n.use(initReactI18next).init({
  lng: 'fr',
  fallbackLng: 'fr',
  resources: {
    fr: { translation: () => import('./locales/fr.json') },
    en: { translation: () => import('./locales/en.json') },
  },
  interpolation: { escapeValue: false },
})

// Règle : AUCUNE chaîne UI hardcodée dans les composants
// ❌ <button>Créer une facture</button>
// ✅ <button>{t('invoice.create.button')}</button>

// Formatage monétaire via Intl (pas de string manuelle)
const formatCents = (cents: number): string =>
  new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' })
    .format(cents / 100)
// → "50,00 €"
```

---

### 12.23 Secret Management — Vault ou Env tiered (P1)

```python
# app/core/config.py — hiérarchie de sources

class Settings(BaseSettings):
    # Secrets : env vars > AWS Secrets Manager > fichier .env (dev only)
    DATABASE_URL: str
    REDIS_URL: str
    JWT_SECRET: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # En prod : les env vars Docker/K8s écrasent .env
    )

    @model_validator(mode="after")
    def validate_prod_secrets(self) -> "Settings":
        import os
        if os.getenv("ENV") == "production":
            if "dev" in self.JWT_SECRET.lower() or len(self.JWT_SECRET) < 32:
                raise ValueError("JWT_SECRET insuffisant pour production")
        return self

# Règles :
# - .env → développement local uniquement (gitignored)
# - Staging/Prod → secrets injectés via Docker secrets ou K8s secrets
# - Jamais de secret dans docker-compose.yml en clair (utiliser ${VAR})
# - Rotation via Vault ou AWS Secrets Manager en production
```

---

### 12.24 Read Replica Routing — Lecture/Écriture (P3)

**Seuil** : > 500 req/s ou > 70% queries en lecture.

```python
# app/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

write_engine = create_engine(settings.DATABASE_URL, pool_size=10)
read_engine  = create_engine(settings.DATABASE_READ_URL, pool_size=20)

WriteSession = sessionmaker(bind=write_engine)
ReadSession  = sessionmaker(bind=read_engine)

# Dépendances FastAPI séparées
def get_db():             yield from _get_session(WriteSession)
def get_read_db():        yield from _get_session(ReadSession)

# Usage dans endpoints
@router.get("/products", response_model=...)
def list_products(db: Session = Depends(get_read_db)):   # Lecture seule
    ...

@router.post("/products", response_model=...)
def create_product(db: Session = Depends(get_db)):       # Écriture
    ...
```

---

## 13. Matrice de priorité — Patterns avancés

| # | Pattern | Fichier principal | Priorité | Effort | Impact |
|---|---------|-----------------|---------|--------|--------|
| 12.1 | Idempotency Keys | `app/core/idempotency.py` | **P0** | 2j | Intégrité financière |
| 12.2 | Optimistic Locking | `app/models/*.py` | **P1** | 3j | Cohérence concurrence |
| 12.3 | Circuit Breaker | `app/core/circuit_breaker.py` | **P1** | 2j | Résilience cascade |
| 12.4 | Unit of Work | `app/core/unit_of_work.py` | **P1** | 1j | Transactions atomiques |
| 12.5 | Domain Events | `app/core/events.py` | **P1** | 2j | Découplage services |
| 12.8 | Test Factories | `tests/factories.py` | **P1** | 1j | Maintenabilité tests |
| 12.12 | Graceful Shutdown | `app/main.py` | **P1** | 0.5j | Zéro perte requêtes |
| 12.14 | Partial Indexes | migrations | **P1** | 0.5j | Perf queries actives |
| 12.15 | Error Boundary | `frontend/src/components/ui/` | **P1** | 0.5j | UX crash recovery |
| 12.16 | Code Splitting | `frontend/src/App.tsx` | **P1** | 1j | -60% bundle initial |
| 12.23 | Secret Management | `app/core/config.py` | **P1** | 0.5j | Sécurité prod |
| 12.6 | ETag | `app/core/etag.py` | **P2** | 1j | -80% bandwidth GET |
| 12.7 | Cursor Pagination | `app/core/cursor.py` | **P2** | 1.5j | Scale > 100k rows |
| 12.9 | Property-Based Tests | `tests/unit/` | **P2** | 0.5j | Confiance règles |
| 12.10 | OpenTelemetry | `app/core/tracing.py` | **P2** | 2j | Debug latence |
| 12.11 | Slow Query Log | `app/core/database.py` | **P2** | 0.5j | Détection N+1 prod |
| 12.17 | Optimistic Updates | pages/modals | **P2** | 1j | UX snappy |
| 12.18 | Virtual Scrolling | `InventoryPage.tsx` | **P2** | 0.5j | Perf > 500 lignes |
| 12.19 | Contract Testing | `tests/contract/` | **P2** | 2j | Évite régression API |
| 12.21 | Accessibility a11y | tous composants | **P2** | 3j | WCAG 2.1 AA |
| 12.13 | Materialized Views | migrations | **P2** | 1.5j | Dashboard < 50ms |
| 12.20 | Webhook Outbound | `app/tasks/webhooks.py` | **P3** | 3j | Intégrations tierces |
| 12.22 | i18n | `frontend/src/i18n/` | **P3** | 2j | Multi-marché |
| 12.24 | Read Replica | `app/core/database.py` | **P3** | 2j | Scale > 500 req/s |

---

## 14. Patterns avancés — Infrastructure, Ops & Qualité

> Tier suivant : observabilité, sécurité défensive, résilience Celery, qualité code.

---

### 14.1 pgBouncer — Connection Pooling PostgreSQL (P1)

**Problème** : FastAPI async + SQLAlchemy sync → chaque worker maintient une connexion DB ouverte.
À 50 workers, PostgreSQL reçoit 50 connexions permanentes → OOM sur instance small.

```
# docker-compose.yml — ajouter devant PostgreSQL
pgbouncer:
  image: edoburu/pgbouncer:1.22.0
  environment:
    DB_HOST: postgres
    DB_PORT: 5432
    DB_USER: ${POSTGRES_USER}
    DB_PASSWORD: ${POSTGRES_PASSWORD}
    DB_NAME: ${POSTGRES_DB}
    POOL_MODE: transaction          # transaction pooling (optimal FastAPI)
    MAX_CLIENT_CONN: 500
    DEFAULT_POOL_SIZE: 25           # 25 connexions physiques max vers PG
    RESERVE_POOL_SIZE: 5
    SERVER_IDLE_TIMEOUT: 600
  ports:
    - "6432:5432"
  depends_on: [postgres]
```

```python
# app/core/config.py — pointer sur pgBouncer en prod
# DATABASE_URL = "postgresql://user:pass@pgbouncer:6432/db"

# app/core/database.py — désactiver prepared statements (incompatibles pgBouncer transaction mode)
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=5,                # Pool SQLAlchemy minimal (pgBouncer gère le vrai pool)
    max_overflow=0,
    connect_args={"options": "-c statement_timeout=30000"},
    execution_options={"no_parameters": True},   # Désactive prepared statements
)
```

**Règle** : en production, `DATABASE_URL` pointe sur pgBouncer, jamais directement PostgreSQL.

---

### 14.2 Health Checks — Liveness & Readiness Probes (P0)

```python
# app/api/v1/endpoints/health.py
from fastapi import APIRouter, Response
from sqlalchemy import text
from app.core.database import get_db_context
from app.core.redis import get_redis_client

router = APIRouter(tags=["health"])

@router.get("/health/live", include_in_schema=False)
def liveness():
    """Kubernetes liveness probe — juste vérifier que le process répond."""
    return {"status": "alive"}

@router.get("/health/ready", include_in_schema=False)
def readiness(response: Response):
    """
    Kubernetes readiness probe — vérifier DB + Redis accessibles.
    Retourne 503 si une dépendance est KO (pod retiré du load balancer).
    """
    checks = {}

    # Check PostgreSQL
    try:
        with get_db_context() as db:
            db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "error"

    # Check Redis
    try:
        redis = get_redis_client()
        redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    if not all_ok:
        response.status_code = 503

    return {"status": "ready" if all_ok else "degraded", "checks": checks}

@router.get("/health/startup", include_in_schema=False)
def startup():
    """Kubernetes startup probe — vérifier migrations appliquées."""
    try:
        with get_db_context() as db:
            result = db.execute(text(
                "SELECT version_num FROM alembic_version LIMIT 1"
            )).scalar()
        return {"status": "started", "migration": result}
    except Exception as e:
        return Response(
            content=f'{{"status":"error","detail":"{e}"}}',
            status_code=503,
            media_type="application/json",
        )
```

```yaml
# docker-compose.yml — probes pour api
api:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health/ready"]
    interval: 30s
    timeout: 5s
    retries: 3
    start_period: 40s
```

---

### 14.3 Advisory Locks — Sections critiques distribuées (P1)

**Problème** : plusieurs workers Celery peuvent traiter la même réservation simultanément.
`SELECT FOR UPDATE` ne protège que dans une transaction. Advisory lock = global pour un `lock_id`.

```python
# app/core/advisory_lock.py
from contextlib import contextmanager
from sqlalchemy import text
from app.core.database import get_db_context

@contextmanager
def advisory_lock(lock_id: int):
    """
    Lock PostgreSQL au niveau session — bloque tous les workers concurrents.
    Idéal pour : confirm_reservation, generate_invoice_number, apply_deposit.
    """
    with get_db_context() as db:
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
        yield db
        # Lock libéré automatiquement à la fin de la transaction

def reservation_lock_id(reservation_id: int) -> int:
    """Déterministe : même réservation → même lock_id."""
    return hash(f"reservation:{reservation_id}") % (2**31)

# Usage dans service
class ReservationService:
    def confirm_reservation(self, reservation_id: int, tenant_id: int) -> Reservation:
        lock_id = reservation_lock_id(reservation_id)
        with advisory_lock(lock_id) as db:
            reservation = self.repo.get_by_id(reservation_id, tenant_id, db)
            if reservation.status != "draft":
                raise HTTPException(status_code=409, detail="Already confirmed")
            reservation.status = "confirmed"
            db.flush()
            return reservation
```

---

### 14.4 Celery — DLQ + Déduplication + Monitoring Flower (P1)

**Dead Letter Queue** : tâches qui échouent toutes les retries → file d'attente séparée pour inspection.

```python
# app/tasks/celery_app.py
from celery import Celery
from kombu import Queue, Exchange

dead_letter_exchange = Exchange("dlx", type="direct")

celery_app = Celery("marveline")
celery_app.conf.update(
    # DLQ : tâche échouée → republier sur marveline.dlq
    task_queues=(
        Queue("default", routing_key="default"),
        Queue(
            "marveline.dlq",
            exchange=dead_letter_exchange,
            routing_key="dlq",
        ),
    ),
    task_default_queue="default",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,

    # Résultats : expiration après 24h
    result_expires=86400,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    on_failure=lambda self, exc, task_id, args, kwargs, einfo: (
        logger.error("TASK_FAILED", extra={"task_id": task_id, "exc": str(exc)})
    ),
)
def send_invoice_email(self, invoice_id: int, tenant_id: int):
    ...
```

```python
# app/core/task_dedup.py — Déduplication Redis
import hashlib
from app.core.redis import get_redis_client

DEDUP_TTL = 3600  # 1h

def deduplicated_task(task_fn, *args, dedup_key: str | None = None, **kwargs):
    """
    Évite double-enqueue de la même tâche (ex: webhook retry storm).
    Si dedup_key déjà en vol → skip silencieux.
    """
    redis = get_redis_client()
    key = f"task_dedup:{dedup_key or hashlib.md5(str((task_fn.name, args, kwargs)).encode()).hexdigest()}"

    if redis.set(key, "1", nx=True, ex=DEDUP_TTL):
        task_fn.delay(*args, **kwargs)
        return True
    return False  # Déjà en file

# Usage
deduplicated_task(send_invoice_email, invoice_id=42, tenant_id=1, dedup_key=f"invoice_email:{42}")
```

```yaml
# docker-compose.yml — Flower pour monitoring Celery
flower:
  image: mher/flower:2.0
  command: celery --broker=redis://redis:6379/0 flower --port=5555
  ports:
    - "5555:5555"
  environment:
    CELERY_BROKER_URL: redis://redis:6379/0
    FLOWER_BASIC_AUTH: admin:${FLOWER_PASSWORD}
  depends_on: [redis, worker]
```

---

### 14.5 Sentry — Error Tracking avec contexte enrichi (P1)

```python
# app/main.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

def setup_sentry():
    if not settings.SENTRY_DSN:
        return
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENV,
        traces_sample_rate=0.1,       # 10% des traces envoyées
        profiles_sample_rate=0.05,    # 5% des requêtes profilées
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            CeleryIntegration(monitor_beat_tasks=True),
        ],
        before_send=_scrub_sensitive_data,
    )

def _scrub_sensitive_data(event, hint):
    """Retirer PII avant envoi Sentry."""
    if "request" in event:
        req = event["request"]
        # Scrub headers sensibles
        headers = req.get("headers", {})
        for h in ("authorization", "x-csrf-token", "cookie", "x-api-key"):
            headers.pop(h, None)
        # Scrub request body (peut contenir mots de passe, tokens)
        if "data" in req:
            body = req["data"]
            if isinstance(body, dict):
                for field in ("password", "token", "secret", "api_key", "card_number"):
                    if field in body:
                        body[field] = "[Filtered]"
            else:
                req["data"] = "[Filtered]"
    return event

# Middleware — enrichir contexte par requête
@app.middleware("http")
async def sentry_tenant_context(request: Request, call_next):
    with sentry_sdk.configure_scope() as scope:
        if hasattr(request.state, "tenant_id"):
            scope.set_tag("tenant_id", request.state.tenant_id)
        if hasattr(request.state, "user_id"):
            scope.set_user({"id": request.state.user_id})
    return await call_next(request)
```

```typescript
// frontend/src/lib/sentry.ts
import * as Sentry from '@sentry/react'

export function setupSentry() {
  if (!import.meta.env.VITE_SENTRY_DSN) return
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.MODE,
    tracesSampleRate: 0.1,
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration({ maskAllInputs: true }),  // PII masqué
    ],
    // Ignorer erreurs réseau normales (offline user)
    ignoreErrors: ['Network Error', 'Request aborted', 'ResizeObserver loop'],
  })
}

// Dans ErrorBoundary.componentDidCatch
componentDidCatch(error: Error, info: ErrorInfo) {
  Sentry.captureException(error, { extra: { componentStack: info.componentStack } })
}
```

---

### 14.6 RGPD — Droit à l'effacement & Rétention des données (P1)

```python
# app/services/gdpr.py
from datetime import date, timedelta
from sqlalchemy import update, delete
from app.models import Customer, Invoice, AuditLog

class GDPRService:
    """
    Implémente les articles 17 (effacement) et 5(1)(e) (limitation stockage) du RGPD.
    """

    def erase_customer(self, customer_id: int, tenant_id: int, db) -> dict:
        """
        Droit à l'effacement : anonymiser les données personnelles.
        NE PAS supprimer : les enregistrements comptables sont légalement requis 10 ans.
        Stratégie : pseudonymisation (pas suppression).
        """
        customer = self.customer_repo.get_by_id(customer_id, tenant_id, db)
        if not customer:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Customer not found")

        # Anonymiser PII sur le client
        anonymized_email = f"deleted_{customer_id}@anonymized.invalid"
        db.execute(
            update(Customer)
            .where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
            .values(
                first_name="[Supprimé]",
                last_name="[Supprimé]",
                email=anonymized_email,
                phone=None,
                address=None,
                city=None,
                postal_code=None,
                is_active=False,
                erased_at=date.today(),       # Nouvelle colonne : preuve effacement
            )
        )
        db.commit()  # ← atomicité obligatoire : commit ici car appelé depuis endpoint dédié

        # Logger l'action d'effacement (preuve de conformité)
        logger.info(
            "GDPR_ERASURE",
            extra={"customer_id": customer_id, "tenant_id": tenant_id, "date": str(date.today())}
        )

        return {"status": "erased", "customer_id": customer_id}

    def apply_retention_policy(self, tenant_id: int, db) -> dict:
        """
        Suppression données > 7 ans (politique de rétention légale).
        À appeler via tâche Celery mensuelle.
        Audit logs : 5 ans (RGPD recommandation CNIL).
        """
        cutoff_invoices = date.today() - timedelta(days=365 * 7)
        cutoff_audit    = date.today() - timedelta(days=365 * 5)

        # Soft delete des factures anciennes anonymisées
        invoices_deleted = db.execute(
            update(Invoice)
            .where(
                Invoice.tenant_id == tenant_id,
                Invoice.issue_date < cutoff_invoices,
                Invoice.is_active == True,
            )
            .values(is_active=False)
        ).rowcount

        # Purge physique audit logs anciens (pas de soft delete requis)
        audit_deleted = db.execute(
            delete(AuditLog)
            .where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.created_at < cutoff_audit,
            )
        ).rowcount

        return {
            "invoices_archived": invoices_deleted,
            "audit_logs_purged": audit_deleted,
        }
```

```python
# Tâche Celery mensuelle
@celery_app.task(name="apply_retention_policies")
def apply_retention_policies():
    """Déclencher le 1er de chaque mois via Celery Beat."""
    with get_db_context() as db:
        tenants = db.execute(select(Tenant.id).where(Tenant.is_active == True)).scalars().all()
        for tenant_id in tenants:
            gdpr_service.apply_retention_policy(tenant_id, db)
        db.commit()
```

---

### 14.7 API Deprecation — Headers Sunset & Deprecation (P2)

**Standard RFC 8594** : informer les clients d'une future suppression d'endpoint.

```python
# app/core/deprecation.py
from datetime import date
from fastapi import Response
from functools import wraps

def deprecated(sunset_date: date, replacement: str | None = None):
    """
    Décorateur pour marquer un endpoint comme déprécié.
    Ajoute les headers RFC 8594 : Deprecation + Sunset.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, response: Response, **kwargs):
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = sunset_date.strftime("%a, %d %b %Y 00:00:00 GMT")
            if replacement:
                response.headers["Link"] = f'<{replacement}>; rel="successor-version"'
            return fn(*args, response=response, **kwargs)
        return wrapper
    return decorator

# Usage
@router.get("/v1/products/all", response_model=list[ProductResponse])
@deprecated(
    sunset_date=date(2026, 6, 1),
    replacement="/api/v1/products?limit=1000"
)
def list_all_products_legacy(response: Response, db: Session = Depends(get_db)):
    """⚠️ DÉPRÉCIÉ — utiliser GET /products avec pagination."""
    ...
```

```python
# Log des appels à endpoints dépréciés → alerte sur volume
@app.middleware("http")
async def log_deprecated_usage(request: Request, call_next):
    response = await call_next(request)
    if response.headers.get("Deprecation") == "true":
        logger.warning(
            "DEPRECATED_ENDPOINT_CALLED",
            extra={"path": request.url.path, "client": request.client.host if request.client else None}
        )
    return response
```

---

### 14.8 Specification Pattern — Requêtes complexes (P2)

**Problème** : les repositories accumulent des méthodes `get_by_status_and_date_and_customer()`.
Specification pattern → requêtes composables sans explosion combinatoire.

```python
# app/repositories/specifications.py
from abc import ABC, abstractmethod
from sqlalchemy import ColumnElement, and_, or_
from datetime import date

class Specification(ABC):
    """Prédicat SQLAlchemy composable."""

    @abstractmethod
    def to_expression(self) -> ColumnElement:
        ...

    def __and__(self, other: "Specification") -> "AndSpec":
        return AndSpec(self, other)

    def __or__(self, other: "Specification") -> "OrSpec":
        return OrSpec(self, other)

class AndSpec(Specification):
    def __init__(self, *specs: Specification):
        self.specs = specs
    def to_expression(self):
        return and_(*[s.to_expression() for s in self.specs])

class OrSpec(Specification):
    def __init__(self, *specs: Specification):
        self.specs = specs
    def to_expression(self):
        return or_(*[s.to_expression() for s in self.specs])

# Spécifications métier
class ReservationByStatus(Specification):
    def __init__(self, status: str):
        self.status = status
    def to_expression(self):
        return Reservation.status == self.status

class ReservationByDateRange(Specification):
    def __init__(self, start: date, end: date):
        self.start, self.end = start, end
    def to_expression(self):
        return and_(Reservation.start_date >= self.start, Reservation.end_date <= self.end)

class ReservationByCustomer(Specification):
    def __init__(self, customer_id: int):
        self.customer_id = customer_id
    def to_expression(self):
        return Reservation.customer_id == self.customer_id

# Usage dans repository
class ReservationRepository:
    def find(self, tenant_id: int, spec: Specification | None = None) -> list[Reservation]:
        stmt = (
            select(Reservation)
            .where(Reservation.tenant_id == tenant_id, Reservation.is_archived == False)
        )
        if spec:
            stmt = stmt.where(spec.to_expression())
        return self.db.execute(stmt).scalars().all()

# Composition côté service
spec = (
    ReservationByStatus("confirmed")
    & ReservationByDateRange(date(2026, 1, 1), date(2026, 12, 31))
    & ReservationByCustomer(customer_id=42)
)
reservations = reservation_repo.find(tenant_id=1, spec=spec)
```

---

### 14.9 CQRS Light — Séparation Command/Query (P2)

**Problème** : services avec `get_*` et `create_*` dans la même classe → coupling lecture/écriture.
CQRS light : séparation sans event store complet.

```python
# app/services/reservation_queries.py — READ side
class ReservationQueryService:
    """Lecture seule — peut utiliser read replica, cache, vues matérialisées."""

    def get_calendar_view(self, tenant_id: int, month: date) -> list[CalendarEvent]:
        """Optimisé pour affichage calendrier — pas de logique métier."""
        stmt = text("""
            SELECT r.id, r.reference, r.start_date, r.end_date,
                   c.first_name || ' ' || c.last_name AS customer_name,
                   r.status
            FROM reservations r
            JOIN customers c ON c.id = r.customer_id
            WHERE r.tenant_id = :tenant_id
              AND r.start_date >= :start
              AND r.end_date   <= :end
              AND r.is_active  = true
            ORDER BY r.start_date
        """)
        rows = self.read_db.execute(stmt, {
            "tenant_id": tenant_id,
            "start": month.replace(day=1),
            "end": (month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1),
        }).mappings().all()
        return [CalendarEvent(**r) for r in rows]

# app/services/reservation_commands.py — WRITE side
class ReservationCommandService:
    """Écriture — logique métier, validations, events."""

    def confirm(self, reservation_id: int, tenant_id: int) -> Reservation:
        with advisory_lock(reservation_lock_id(reservation_id)) as db:
            reservation = self._get_or_404(reservation_id, tenant_id, db)
            self._validate_stock_available(reservation, db)
            reservation.status = "confirmed"
            db.flush()
            EventBus.publish(ReservationConfirmed(reservation_id=reservation.id))
            return reservation
```

---

### 14.10 Rate Limiting par Tenant (P1)

**Problème** : rate limit global par IP → un tenant abuse ralentit tous les autres.
Solution : bucket Redis par `(tenant_id, endpoint)`.

```python
# app/core/rate_limit.py
from fastapi import Request, HTTPException
from app.core.redis import get_redis_client

def tenant_rate_limit(requests_per_minute: int = 60, burst: int = 10):
    """
    Dépendance FastAPI — à injecter sur endpoints potentiellement abusés.
    Algorithme : Token Bucket par tenant.
    """
    def dependency(request: Request):
        # Récupérer tenant depuis le token JWT déjà décodé
        tenant_id = getattr(request.state, "tenant_id", None)
        if not tenant_id:
            return  # Pas authentifié → autre middleware gère

        redis = get_redis_client()
        endpoint = request.url.path.replace("/", "_")
        key = f"ratelimit:tenant:{tenant_id}:{endpoint}"

        # Sliding window counter
        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, 60)
        count, _ = pipe.execute()

        limit = requests_per_minute + burst
        if count > limit:
            raise HTTPException(
                status_code=429,
                detail="Trop de requêtes — réessayez dans 60 secondes",
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": "60",
                },
            )

    return dependency

# Usage
@router.post("/invoices", dependencies=[Depends(tenant_rate_limit(requests_per_minute=30))])
def create_invoice(...):
    ...
```

---

### 14.11 Mutation Testing — Mutmut (P3)

**Problème** : 90% de coverage mais les tests ne vérifient pas vraiment les conditions.
Mutation testing : introduire des bugs → un bon test les détecte.

```bash
# Installation
pip install mutmut

# Cibler les services métier critiques (pas toute la codebase)
mutmut run \
  --paths-to-mutate="app/services/invoice.py,app/services/reservation.py" \
  --runner="python -m pytest tests/unit/ -x -q"

# Rapport
mutmut results
# Survived mutations → tests à renforcer

# Exemple : mutation ">" → ">=" dans compute_remaining_amount
# Si le test ne détecte pas → coverage menteur sur cette ligne
```

```python
# Règle : Mutmut score > 80% sur les services financiers (invoice, payment, deposit).
# Intégrer dans CI monthly (pas à chaque PR — trop lent) :
# .github/workflows/mutation.yml — schedule: cron "0 2 * * 1" (lundi 2h)
```

---

### 14.12 Load Testing — Locust / k6 (P2)

```python
# tests/load/locustfile.py
from locust import HttpUser, task, between
import random

class MarvelineUser(HttpUser):
    """Simule un utilisateur admin typique."""
    wait_time = between(1, 3)
    host = "http://localhost:8000"
    token: str = ""

    def on_start(self):
        resp = self.client.post("/api/v1/auth/login", data={
            "username": "admin@test.com",
            "password": "TestPassword123!",
        })
        self.token = resp.json().get("access_token", "")

    @task(5)   # Poids : opération la plus fréquente
    def list_reservations(self):
        self.client.get(
            "/api/v1/reservations?page=1&limit=20",
            headers={"Authorization": f"Bearer {self.token}"},
            name="/reservations [list]",
        )

    @task(2)
    def list_invoices(self):
        self.client.get(
            "/api/v1/invoices?page=1&limit=20",
            headers={"Authorization": f"Bearer {self.token}"},
            name="/invoices [list]",
        )

    @task(1)
    def dashboard(self):
        self.client.get(
            "/api/v1/dashboard/",
            headers={"Authorization": f"Bearer {self.token}"},
            name="/dashboard",
        )

# Seuils d'acceptation :
# P50 < 100ms, P95 < 300ms, P99 < 1000ms
# Taux erreur < 0.1% à 100 users concurrents
# Commande : locust -f tests/load/locustfile.py --users 100 --spawn-rate 10 --headless --run-time 5m
```

---

### 14.13 Web Vitals & Bundle Analysis (P2)

```typescript
// frontend/src/lib/web-vitals.ts
import { onCLS, onFID, onLCP, onFCP, onTTFB, type Metric } from 'web-vitals'

function sendToAnalytics(metric: Metric) {
  // Envoyer à endpoint interne (pas tiers) pour éviter RGPD
  fetch('/api/v1/metrics/web-vitals', {
    method: 'POST',
    body: JSON.stringify({
      name: metric.name,
      value: Math.round(metric.value),
      rating: metric.rating,   // 'good' | 'needs-improvement' | 'poor'
      id: metric.id,
    }),
    keepalive: true,
  })
}

export function initWebVitals() {
  onCLS(sendToAnalytics)   // Cumulative Layout Shift  → cible < 0.1
  onFID(sendToAnalytics)   // First Input Delay         → cible < 100ms
  onLCP(sendToAnalytics)   // Largest Contentful Paint  → cible < 2.5s
  onFCP(sendToAnalytics)   // First Contentful Paint    → cible < 1.8s
  onTTFB(sendToAnalytics)  // Time to First Byte        → cible < 800ms
}
```

```typescript
// vite.config.ts — Bundle Visualizer (analyse taille chunks)
import { visualizer } from 'rollup-plugin-visualizer'

plugins: [
  react(),
  visualizer({
    filename: 'dist/bundle-stats.html',
    open: false,          // Générer sans ouvrir auto
    gzipSize: true,
    brotliSize: true,
    template: 'treemap',  // 'treemap' | 'sunburst' | 'network'
  }),
]

// Règle : `npm run build` → ouvrir bundle-stats.html si build > 500KB gzip.
// Cible : chunk initial < 200KB gzip. Recharts séparé en chunk vendor-charts.
```

---

### 14.14 Dependency Vulnerability Scanning (P1)

```yaml
# .github/workflows/security.yml — Scan automatisé à chaque PR
name: Security Scan

on: [push, pull_request]

jobs:
  python-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install pip-audit safety
      # pip-audit : CVE dans les dépendances directes et transitives
      - run: pip-audit --requirement requirements.txt --format json --output audit.json
      # safety : check contre base Snyk
      - run: safety check --full-report

  node-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: cd frontend && npm audit --audit-level=high

  docker-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aquasecurity/trivy-action@master
        with:
          image-ref: marveline-api:latest
          format: table
          exit-code: 1          # CI rouge si vulnérabilité HIGH+
          severity: HIGH,CRITICAL
```

```python
# Makefile — cible locale
security-audit:
	pip-audit --requirement requirements.txt
	cd frontend && npm audit --audit-level=moderate
	@echo "✅ Security audit complete"
```

---

### 14.15 OWASP Top 10 — Checklist par endpoint (P0)

```python
# app/core/security_headers.py — Headers de sécurité universels
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.update({
            # A05 — Security Misconfiguration
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "0",         # Désactiver l'ancien XSS filter (dangereux)
            "Referrer-Policy": "strict-origin-when-cross-origin",
            # A02 — Cryptographic Failures
            "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
            # A03 — Injection : CSP
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "connect-src 'self'; "
                "frame-ancestors 'none';"
            ),
            # A04 — Permissions Policy
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        })
        # Ne pas exposer la stack technique
        response.headers.pop("server", None)
        response.headers.pop("x-powered-by", None)
        return response

app.add_middleware(SecurityHeadersMiddleware)
```

```python
# Checklist OWASP par endpoint (à valider en PR review)
#
# A01 Broken Access Control  → tenant_id filtré + RBAC vérifié
# A02 Cryptographic Failures → HTTPS only + JWT HS256+ 32 octets minimum
# A03 Injection             → SQLAlchemy ORM (pas de f-string dans requêtes)
# A04 Insecure Design       → Rate limit + advisory lock sur mutations critiques
# A05 Security Misconfig    → SecurityHeadersMiddleware sur toutes réponses
# A06 Vulnerable Components → pip-audit + npm audit dans CI (14.14)
# A07 Auth Failures         → login brute force: 5 req/min Redis + lockout
# A08 Integrity Failures    → Idempotency keys (12.1) + HMAC webhooks (12.20)
# A09 Logging Failures      → structured logging + audit_logs table (Section 10)
# A10 SSRF                  → whitelist URLs sortantes, pas de fetch user-controlled
```

---

### 14.16 PostgreSQL LISTEN/NOTIFY — Temps réel sans polling (P3)

**Alternative légère à Redis Pub/Sub ou WebSocket** pour notifier le frontend d'événements DB.

```python
# app/api/v1/endpoints/sse.py — Server-Sent Events via LISTEN/NOTIFY
import asyncio
import psycopg2
import select
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.core.config import settings

router = APIRouter()

async def _listen_postgres(tenant_id: int):
    """Générateur SSE — écoute NOTIFY depuis PostgreSQL."""
    conn = psycopg2.connect(settings.DATABASE_URL)
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute(f"LISTEN reservation_events_{tenant_id};")

    try:
        while True:
            # Polling non-bloquant toutes 100ms
            if select.select([conn], [], [], 0.1)[0]:
                conn.poll()
                while conn.notifies:
                    notify = conn.notifies.pop(0)
                    yield f"data: {notify.payload}\n\n"
            else:
                yield ": heartbeat\n\n"   # Keepalive toutes les 100ms
            await asyncio.sleep(0.1)
    finally:
        conn.close()

@router.get("/events/stream")
def reservation_stream(current_user: User = Depends(get_current_user)):
    return StreamingResponse(
        _listen_postgres(current_user.tenant_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

# Émettre depuis service
class ReservationService:
    def confirm_reservation(self, reservation_id, tenant_id, db):
        ...
        db.execute(text(
            "SELECT pg_notify(:channel, :payload)"
        ), {
            "channel": f"reservation_events_{tenant_id}",
            "payload": json.dumps({"event": "confirmed", "id": reservation_id}),
        })
```

```typescript
// frontend/src/hooks/useReservationStream.ts
export function useReservationStream(onEvent: (event: unknown) => void) {
  useEffect(() => {
    const es = new EventSource('/api/v1/events/stream')
    es.onmessage = (e) => {
      if (e.data.startsWith(':')) return   // Heartbeat
      onEvent(JSON.parse(e.data))
    }
    return () => es.close()
  }, [onEvent])
}
```

---

### 14.17 Zero-Downtime Migration — Stratégie Expand/Contract (P0)

**Règle** : toute migration qui modifie une colonne existante doit suivre le cycle en 3 phases.

```
Phase 1 — EXPAND (déployable sans downtime)
  ✅ Ajouter une nouvelle colonne nullable
  ✅ Ajouter un index CONCURRENTLY
  ✅ Ajouter une table
  ✅ Ajouter une FK nullable

Phase 2 — MIGRATE (script de backfill, peut durer longtemps)
  ✅ Remplir la nouvelle colonne depuis l'ancienne
  ✅ Backfill en batches (jamais UPDATE sans WHERE LIMIT)
  ✅ Valider la cohérence avant Phase 3

Phase 3 — CONTRACT (après validation)
  ✅ Rendre la nouvelle colonne NOT NULL (si données complètes)
  ✅ Supprimer l'ancienne colonne
  ✅ Supprimer l'ancien index
```

```python
# INTERDIT en migration directe
def upgrade_WRONG():
    op.alter_column("invoices", "amount", new_column_name="total_amount_cents")  # 🚫 Downtime

# CORRECT — Phase 1 (expand)
def upgrade_phase1():
    op.add_column("invoices", sa.Column("total_amount_cents", sa.BigInteger, nullable=True))
    # Commentaire obligatoire : "Phase 1/3 — sera NOT NULL après backfill"

# Script backfill indépendant
def backfill_total_amount_cents(db):
    db.execute(text("""
        UPDATE invoices
        SET total_amount_cents = amount * 100
        WHERE total_amount_cents IS NULL
        LIMIT 1000
    """))  # À exécuter en boucle jusqu'à rowcount == 0

# CORRECT — Phase 3 (contract) — après validation complète
def upgrade_phase3():
    op.alter_column("invoices", "total_amount_cents", nullable=False)
    op.drop_column("invoices", "amount")
```

```python
# Index CONCURRENTLY — jamais d'index bloquant en prod
def upgrade():
    # op.create_index("ix_...", ...) → lock table entière 🚫
    # Utiliser raw SQL avec CONCURRENTLY :
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_invoices_tenant_status "
        "ON invoices (tenant_id, status) WHERE is_active = true"
    )
    # Note : CONCURRENTLY nécessite autocommit → ne pas wrapper dans transaction Alembic
```

---

## 15. Matrice globale — Priorités complémentaires (Section 14)

| # | Pattern | Priorité | Effort | Impact |
|---|---------|---------|--------|--------|
| 14.2 | Health Checks liveness/readiness | **P0** | 0.5j | Kubernetes ready |
| 14.4 | Celery DLQ + Flower | **P1** | 1j | Observabilité tâches |
| 14.5 | Sentry contexte enrichi | **P1** | 1j | Debug prod |
| 14.6 | RGPD effacement + rétention | **P1** | 2j | Conformité légale |
| 14.10 | Rate limit par tenant | **P1** | 1j | Isolation abus |
| 14.14 | Vulnerability scanning CI | **P1** | 0.5j | Sécurité supply chain |
| 14.15 | OWASP headers + checklist | **P0** | 0.5j | Sécurité de base |
| 14.17 | Zero-downtime expand/contract | **P0** | 0j | Règle process |
| 14.1 | pgBouncer connection pooling | **P1** | 0.5j | Scalabilité connexions |
| 14.3 | Advisory locks PostgreSQL | **P1** | 0.5j | Concurrence distribuée |
| 14.7 | API Deprecation headers | **P2** | 0.5j | Évolution propre |
| 14.8 | Specification pattern | **P2** | 1j | Requêtes composables |
| 14.9 | CQRS Light | **P2** | 2j | Séparation R/W |
| 14.12 | Load Testing Locust | **P2** | 1j | Validation perf |
| 14.13 | Web Vitals + Bundle analyzer | **P2** | 0.5j | UX mesurable |
| 14.11 | Mutation Testing Mutmut | **P3** | 1j | Qualité tests |
| 14.16 | LISTEN/NOTIFY temps réel | **P3** | 2j | Real-time léger |

---

## 16. Patterns avancés — API Design & Opérations de masse

> Patterns identifiés lors de l'audit complet du codebase — complètent les sections 12 et 14.

---

### 16.1 Bulk Operations — Insertions/Mises à jour de masse (P2)

**Problème** : import 1000 produits CSV = 1000 INSERT séquentiels (~10s). `bulk_insert_mappings` → 1 query (~50ms).

```python
# app/repositories/product.py
class ProductRepository:
    def bulk_create(self, tenant_id: int, products: list[dict]) -> int:
        """
        Crée N produits en 1–2 queries (au lieu de N).
        Règle : jamais de boucle db.add() sans bulk si N > 50.
        """
        now = utcnow()
        data = [
            {
                **p,
                "tenant_id": tenant_id,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
            for p in products
        ]
        self.db.bulk_insert_mappings(Product, data)
        self.db.flush()
        return len(data)

    def bulk_update_status(
        self, tenant_id: int, ids: list[int], new_status: str
    ) -> int:
        """Mise à jour de masse via UPDATE WHERE IN (1 query)."""
        result = self.db.execute(
            update(Product)
            .where(Product.tenant_id == tenant_id, Product.id.in_(ids))
            .values(status=new_status, updated_at=utcnow())
        )
        self.db.flush()
        return result.rowcount

# app/api/v1/endpoints/products.py — endpoint d'import
class ProductBulkCreate(BaseModel):
    products: list[ProductCreate]
    model_config = ConfigDict(strict=True)

    @field_validator("products")
    @classmethod
    def max_bulk_size(cls, v: list) -> list:
        if len(v) > 500:
            raise ValueError("Maximum 500 produits par import")
        return v

@router.post("/products/bulk", response_model=BulkCreateResponse, status_code=201)
def bulk_create_products(
    payload: ProductBulkCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    count = product_repo.bulk_create(current_user.tenant_id, [p.model_dump() for p in payload.products])
    return {"created": count}
```

---

### 16.2 Form State — Zustand pour formulaires complexes (P2)

**Problème** : `useState` local pour 10+ champs = 10 re-renders/field. Zustand store = 1 store, re-renders selectifs.

```typescript
// frontend/src/stores/formStore.ts
// Pattern général : un store par domaine métier (pas un store global)
import { create } from 'zustand'

interface FieldState<T> {
  value: T
  error: string | null
  touched: boolean
}

interface ProductFormStore {
  fields: {
    name: FieldState<string>
    sku: FieldState<string>
    price_cents: FieldState<number>
    description: FieldState<string>
  }
  isSubmitting: boolean

  setField: <K extends keyof ProductFormStore['fields']>(
    key: K,
    value: ProductFormStore['fields'][K]['value']
  ) => void
  setError: (key: keyof ProductFormStore['fields'], error: string) => void
  markTouched: (key: keyof ProductFormStore['fields']) => void
  reset: () => void
}

const initialFields = {
  name:         { value: '', error: null, touched: false },
  sku:          { value: '', error: null, touched: false },
  price_cents:  { value: 0, error: null, touched: false },
  description:  { value: '', error: null, touched: false },
}

export const useProductFormStore = create<ProductFormStore>((set) => ({
  fields: initialFields,
  isSubmitting: false,

  setField: (key, value) =>
    set((s) => ({
      fields: { ...s.fields, [key]: { ...s.fields[key], value, error: null } },
    })),

  setError: (key, error) =>
    set((s) => ({
      fields: { ...s.fields, [key]: { ...s.fields[key], error } },
    })),

  markTouched: (key) =>
    set((s) => ({
      fields: { ...s.fields, [key]: { ...s.fields[key], touched: true } },
    })),

  reset: () => set({ fields: initialFields, isSubmitting: false }),
}))

// Usage dans ProductFormModal — 1 selector = 1 re-render ciblé
function ProductFormModal() {
  const name       = useProductFormStore((s) => s.fields.name)
  const setField   = useProductFormStore((s) => s.setField)
  const markTouched = useProductFormStore((s) => s.markTouched)
  const reset      = useProductFormStore((s) => s.reset)

  useEffect(() => () => reset(), [])  // Reset au démontage

  return (
    <input
      value={name.value}
      onChange={(e) => setField('name', e.target.value)}
      onBlur={() => markTouched('name')}
      aria-invalid={name.touched && !!name.error}
    />
  )
}

// Règle : formulaires ≥ 5 champs → Zustand store.
//         formulaires < 5 champs → useState local acceptable.
```

---

### 16.3 Debounced Server-Side Search (P1)

**Problème** : recherche frontend locale sur 10k items = freeze. Debounce + pagination serveur.

```typescript
// frontend/src/hooks/useServerSearch.ts
import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useDebouncedCallback } from 'use-debounce'

interface UseServerSearchOptions<T> {
  queryKey: string
  fetcher: (q: string, page: number) => Promise<{ items: T[]; total: number }>
  debounceMs?: number
  minLength?: number
}

export function useServerSearch<T>({
  queryKey,
  fetcher,
  debounceMs = 300,
  minLength = 2,
}: UseServerSearchOptions<T>) {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [page, setPage] = useState(1)

  const flush = useDebouncedCallback((q: string) => {
    setDebouncedQuery(q)
    setPage(1)
  }, debounceMs)

  const handleSearch = useCallback(
    (q: string) => {
      setQuery(q)
      if (q.length >= minLength) flush(q)
      else setDebouncedQuery('')
    },
    [flush, minLength]
  )

  const { data, isFetching } = useQuery({
    queryKey: [queryKey, 'search', debouncedQuery, page],
    queryFn: () => fetcher(debouncedQuery, page),
    enabled: debouncedQuery.length >= minLength,
    placeholderData: (prev) => prev,   // Garder résultats précédents pendant chargement
    staleTime: 30_000,
  })

  return {
    query,
    handleSearch,
    results: data?.items ?? [],
    total: data?.total ?? 0,
    page,
    setPage,
    isFetching,
  }
}

// Usage
function ProductsPage() {
  const { query, handleSearch, results, isFetching } = useServerSearch({
    queryKey: 'products',
    fetcher: (q, page) => productsApi.search({ q, page, limit: 20 }),
  })

  return (
    <>
      <input value={query} onChange={(e) => handleSearch(e.target.value)} />
      {isFetching && <Spinner />}
      {results.map((p) => <ProductRow key={p.id} product={p} />)}
    </>
  )
}
```

```python
# Backend — endpoint search avec full-text PostgreSQL
@router.get("/products/search", response_model=PaginatedResponse[ProductResponse])
def search_products(
    q: str = Query(min_length=2, max_length=100),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Recherche server-side avec index ILIKE ou ts_vector."""
    offset = (page - 1) * limit
    base_filter = and_(
        Product.tenant_id == current_user.tenant_id,
        Product.is_active == True,
        or_(
            Product.name.ilike(f"%{q}%"),
            Product.sku.ilike(f"%{q}%"),
            Product.description.ilike(f"%{q}%"),
        ),
    )
    total = db.scalar(select(func.count()).where(base_filter))
    items = db.scalars(
        select(Product).where(base_filter).order_by(Product.name).offset(offset).limit(limit)
    ).all()
    return PaginatedResponse(items=items, total=total, page=page, limit=limit)
```

---

### 16.4 Secret Rotation — Versioning des clés JWT (P1)

**Problème** : `JWT_SECRET` statique compromise → tous les tokens actifs invalides d'un coup **OU** brèche silencieuse pendant 30j.
Solution : versioning des secrets, grace period, rotation sans downtime.

```python
# app/models/secret_key.py
class SecretKey(Base, TimestampMixin):
    __tablename__ = "secret_keys"
    id:          Mapped[int]  = mapped_column(BigInteger, primary_key=True)
    key_type:    Mapped[str]  = mapped_column(String(50), nullable=False)   # "jwt", "api_signing"
    version:     Mapped[int]  = mapped_column(Integer, nullable=False)
    value_hash:  Mapped[str]  = mapped_column(String(128), nullable=False)  # Argon2id
    is_active:   Mapped[bool] = mapped_column(Boolean, default=True)
    retire_at:   Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("key_type", "version", name="uq_secret_key_type_version"),
    )

# app/core/secret_manager.py
class SecretManager:
    GRACE_PERIOD_DAYS = 7   # Ancienne clé acceptée 7j après rotation

    def get_current(self, key_type: str) -> tuple[str, int]:
        """Retourne (secret_value, version) — caché Redis 1h."""
        redis_key = f"secret:{key_type}:current"
        if cached := self._redis.get(redis_key):
            return json.loads(cached)
        entry = self._get_active_from_db(key_type)
        self._redis.setex(redis_key, 3600, json.dumps((entry.raw_value, entry.version)))
        return entry.raw_value, entry.version

    def rotate(self, key_type: str) -> int:
        """Crée nouvelle version, programme expiration de l'ancienne."""
        new_value = secrets.token_hex(32)
        with get_db_context() as db:
            last = db.scalar(
                select(SecretKey)
                .where(SecretKey.key_type == key_type, SecretKey.is_active == True)
                .order_by(SecretKey.version.desc())
            )
            new_version = (last.version if last else 0) + 1
            if last:
                last.retire_at = utcnow() + timedelta(days=self.GRACE_PERIOD_DAYS)
            db.add(SecretKey(key_type=key_type, version=new_version, value_hash=hash_secret(new_value)))
            db.commit()
        self._redis.delete(f"secret:{key_type}:current")
        logger.info("SECRET_ROTATED", extra={"key_type": key_type, "version": new_version})
        return new_version

    def verify_token_with_rotation(self, token: str) -> dict:
        """Accepte tokens signés avec version actuelle OU version en grace period."""
        # Lire version dans header du JWT (sans vérifier signature)
        header = jwt.get_unverified_header(token)
        version = int(header.get("kid", 0))

        secret, current_version = self.get_current("jwt")
        if version == current_version:
            return jwt.decode(token, secret, algorithms=["HS256"])

        # Essayer version en grace period
        if old_secret := self._get_version("jwt", version):
            return jwt.decode(token, old_secret, algorithms=["HS256"])

        raise HTTPException(status_code=401, detail="Token signé avec clé expirée")

# Signer avec `kid` (key ID) dans le header JWT
def create_token(data: dict, secret_manager: SecretManager) -> str:
    secret, version = secret_manager.get_current("jwt")
    return jwt.encode(
        {**data, "exp": utcnow() + timedelta(hours=1)},
        secret,
        algorithm="HS256",
        headers={"kid": str(version)},
    )

# Celery Beat — rotation mensuelle
@celery_app.task(name="rotate_jwt_secret")
def rotate_jwt_secret():
    SecretManager().rotate("jwt")

# celery_app.conf.beat_schedule["rotate-jwt-monthly"] = {
#     "task": "rotate_jwt_secret",
#     "schedule": crontab(day_of_month="1", hour="3"),
# }
```

---

### 16.5 Sparse Fieldsets — Sélection de champs (P3)

**Problème** : `GET /invoices` retourne 40 colonnes JSON — le frontend en affiche 5. Bandwidth et parsing inutiles.

```python
# app/core/sparse_fields.py
from typing import TypeVar, Type
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

def filter_response_fields(obj: T, fields: str | None) -> dict:
    """
    Filtre les champs d'un schéma Pydantic selon le param `?fields=`.
    Whitelist uniquement — jamais de champs non définis dans le schéma.
    """
    data = obj.model_dump(mode="json")
    if not fields:
        return data

    allowed = set(obj.model_fields.keys())
    requested = {f.strip() for f in fields.split(",")}
    selected = allowed & requested   # Intersection = whitelist stricte

    return {k: v for k, v in data.items() if k in selected}

# Usage dans endpoint
@router.get("/invoices/{id}", response_model=None)   # response_model=None car retour dynamique
def get_invoice(
    id: int,
    fields: str | None = Query(None, example="id,invoice_number,status,total_amount_cents"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    invoice = invoice_service.get_invoice(id, current_user.tenant_id, db)
    invoice_schema = InvoiceResponse.model_validate(invoice)
    return filter_response_fields(invoice_schema, fields)

# Exemples d'appels :
# GET /invoices/42                             → tous les champs (backward compat)
# GET /invoices/42?fields=id,status,total      → 3 champs seulement
# GET /invoices/42?fields=hacked,__dict__      → ignoré (whitelist)
```

```typescript
// frontend/src/lib/api-fields.ts — helper typé
type FieldsOf<T> = (keyof T)[]

export function buildFieldsParam<T>(fields: FieldsOf<T>): string {
  return fields.join(',')
}

// Usage dans api/invoices.ts — liste avec champs réduits
export async function listInvoicesSummary(params: InvoiceListParams) {
  const fields = buildFieldsParam<InvoiceResponse>([
    'id', 'invoice_number', 'status', 'total_amount_cents', 'issue_date', 'customer_name'
  ])
  return apiClient.get('/invoices', { params: { ...params, fields } })
}
```

---

## 17. Matrice globale — Priorités Section 16

| # | Pattern | Priorité | Effort | Impact |
|---|---------|---------|--------|--------|
| 16.3 | Debounced Server-Side Search | **P1** | 1j | UX search instantané |
| 16.4 | Secret Rotation JWT | **P1** | 1.5j | Sécurité clés compromise |
| 16.1 | Bulk Operations | **P2** | 1j | Import masse performant |
| 16.2 | Form State Zustand | **P2** | 1j | Re-renders formulaires |
| 16.5 | Sparse Fieldsets | **P3** | 0.5j | Bandwidth API |

---

## 18. Architecture distribuée & Résilience avancée

---

### 18.1 Outbox Pattern — Garantie at-least-once pour événements (P0)

**Problème** : `db.commit()` + `EventBus.publish()` → si le process crash entre les deux, l'événement est perdu.
L'Outbox Pattern écrit l'événement **dans la même transaction DB** que la mutation métier.

```python
# alembic/versions/XXX_add_outbox_events.py
def upgrade():
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger, nullable=False),
        sa.Column("aggregate_type", sa.String(50), nullable=False),   # "reservation"
        sa.Column("aggregate_id", sa.BigInteger, nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),       # "ReservationConfirmed"
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("status", sa.String(20), default="pending"),         # pending|processing|done|failed
        sa.Column("attempts", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_pending", "outbox_events", ["status", "created_at"],
                    postgresql_where=sa.text("status = 'pending'"))
```

```python
# app/models/outbox_event.py
class OutboxEvent(Base, TimestampMixin):
    __tablename__ = "outbox_events"
    id:             Mapped[int]       = mapped_column(BigInteger, primary_key=True)
    tenant_id:      Mapped[int]       = mapped_column(BigInteger, nullable=False)
    aggregate_type: Mapped[str]       = mapped_column(String(50), nullable=False)
    aggregate_id:   Mapped[int]       = mapped_column(BigInteger, nullable=False)
    event_type:     Mapped[str]       = mapped_column(String(100), nullable=False)
    payload:        Mapped[dict]      = mapped_column(JSON, nullable=False)
    status:         Mapped[str]       = mapped_column(String(20), default="pending")
    attempts:       Mapped[int]       = mapped_column(Integer, default=0)
    processed_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

# app/core/outbox.py
def publish_to_outbox(db, tenant_id: int, aggregate_type: str, aggregate_id: int,
                      event_type: str, payload: dict) -> None:
    """
    Écrire événement dans la même transaction DB que la mutation.
    NE PAS appeler après db.commit() — doit être DANS la même session.
    """
    event = OutboxEvent(
        tenant_id=tenant_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        payload=payload,
    )
    db.add(event)
    # Pas de flush ici — le commit du service flush tout atomiquement

# Usage dans service — même transaction
class ReservationService:
    def confirm_reservation(self, reservation_id: int, tenant_id: int, db) -> Reservation:
        reservation = self.repo.get_by_id(reservation_id, tenant_id, db)
        reservation.status = "confirmed"

        # Outbox event dans la même transaction → atomique
        publish_to_outbox(
            db, tenant_id=tenant_id,
            aggregate_type="reservation", aggregate_id=reservation_id,
            event_type="ReservationConfirmed",
            payload={"reservation_id": reservation_id, "reference": reservation.reference},
        )
        # db.flush() dans l'endpoint → un seul commit pour mutation + event
        return reservation
```

```python
# app/tasks/outbox_relay.py — Celery Beat toutes les 5s
@celery_app.task(name="process_outbox_events")
def process_outbox_events():
    """Lit les événements pending et les publie sur le bus interne / webhooks."""
    with get_db_context() as db:
        events = db.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.status == "pending")
            .order_by(OutboxEvent.created_at)
            .limit(100)
            .with_for_update(skip_locked=True)   # Skip si autre worker traite déjà
        ).all()

        for event in events:
            event.status = "processing"
            event.attempts += 1
            db.flush()

            try:
                _dispatch_event(event)
                event.status = "done"
                event.processed_at = utcnow()
            except Exception as exc:
                logger.exception("OUTBOX_DISPATCH_FAILED", extra={"event_id": event.id})
                event.status = "failed" if event.attempts >= 5 else "pending"
            db.flush()
        db.commit()

# Beat schedule — toutes les 5 secondes
# celery_app.conf.beat_schedule["outbox-relay"] = {
#     "task": "process_outbox_events",
#     "schedule": 5.0,
# }
```

---

### 18.2 Saga Pattern — Transactions distribuées avec compensation (P2)

**Problème** : `confirm_reservation` touche stock + invoice + notification → si notification échoue, que défaire ?
Saga = séquence d'actions + compensation (undo) pour chaque étape.

```python
# app/core/saga.py
from dataclasses import dataclass, field
from typing import Callable, Any

@dataclass
class SagaStep:
    name: str
    action: Callable[..., Any]
    compensation: Callable[..., Any]   # Undo si une étape ultérieure échoue

class Saga:
    """
    Orchestrateur de saga synchrone.
    Pour saga async → chaque step publie un event dans l'outbox (18.1).
    """
    def __init__(self, name: str):
        self.name = name
        self._steps: list[SagaStep] = []
        self._executed: list[tuple[SagaStep, Any]] = []

    def step(self, name: str, action: Callable, compensation: Callable) -> "Saga":
        self._steps.append(SagaStep(name, action, compensation))
        return self

    def execute(self, context: dict) -> dict:
        for step in self._steps:
            try:
                result = step.action(context)
                context[step.name] = result
                self._executed.append((step, result))
                logger.info("SAGA_STEP_OK", extra={"saga": self.name, "step": step.name})
            except Exception as exc:
                logger.error("SAGA_STEP_FAILED", extra={"saga": self.name, "step": step.name, "exc": str(exc)})
                self._compensate(context)
                raise
        return context

    def _compensate(self, context: dict) -> None:
        """Exécuter les compensations en ordre inverse."""
        for step, result in reversed(self._executed):
            try:
                step.compensation(context)
                logger.info("SAGA_COMPENSATION_OK", extra={"step": step.name})
            except Exception:
                logger.exception("SAGA_COMPENSATION_FAILED", extra={"step": step.name})
                # Continuer quand même les autres compensations

# Usage : confirmation de réservation multi-étapes
class ReservationConfirmSaga:
    def execute(self, reservation_id: int, tenant_id: int, db) -> dict:
        saga = (
            Saga("reservation_confirm")
            .step(
                "reserve_stock",
                action=lambda ctx: stock_service.reserve(ctx["reservation_id"], tenant_id, db),
                compensation=lambda ctx: stock_service.release(ctx["reservation_id"], tenant_id, db),
            )
            .step(
                "create_invoice",
                action=lambda ctx: invoice_service.create_for_reservation(ctx["reservation_id"], tenant_id, db),
                compensation=lambda ctx: invoice_service.cancel(ctx["create_invoice"].id, tenant_id, db),
            )
            .step(
                "confirm_status",
                action=lambda ctx: reservation_repo.set_status(ctx["reservation_id"], "confirmed", db),
                compensation=lambda ctx: reservation_repo.set_status(ctx["reservation_id"], "draft", db),
            )
        )
        return saga.execute({"reservation_id": reservation_id})
```

---

### 18.3 Retry avec Exponential Backoff + Jitter (P1)

**Problème** : Celery `default_retry_delay=60` (constant) → thundering herd si 100 tâches échouent en même temps.
Jitter = ajouter aléatoire pour étaler les retry.

```python
# app/core/retry.py
import random
import math

def exponential_backoff_with_jitter(
    attempt: int,
    base_seconds: float = 1.0,
    max_seconds: float = 300.0,
    jitter_factor: float = 0.3,
) -> float:
    """
    Délai = min(base * 2^attempt, max) ± jitter(30%).
    attempt=0 → ~1s, attempt=5 → ~32s, attempt=8 → ~256s (plafonné à 300s).
    Algorithme : "Full Jitter" (AWS recommandé).
    """
    exponential = min(base_seconds * (2 ** attempt), max_seconds)
    jitter = exponential * jitter_factor * (2 * random.random() - 1)  # ±30%
    return max(0.0, exponential + jitter)

# Celery — utiliser dans les tâches
@celery_app.task(bind=True, max_retries=5)
def deliver_webhook(self, endpoint_id: int, event_type: str, payload: dict):
    try:
        _send_webhook(endpoint_id, event_type, payload)
    except Exception as exc:
        delay = exponential_backoff_with_jitter(
            attempt=self.request.retries,
            base_seconds=5.0,
            max_seconds=600.0,
        )
        logger.warning("WEBHOOK_RETRY", extra={"attempt": self.request.retries, "delay_s": round(delay, 1)})
        raise self.retry(exc=exc, countdown=delay)

# httpx — retry avec jitter pour appels externes
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    reraise=True,
)
def call_external_api(url: str, payload: dict) -> dict:
    with httpx.Client(timeout=10.0) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        return response.json()
```

---

### 18.4 Timeout Strategy — Matrice par opération (P1)

**Règle** : chaque type d'opération a un timeout explicite. Pas de timeout = thread bloqué à l'infini.

```python
# app/constants/timeouts.py
"""
Timeouts centralisés — toute opération réseau/externe doit utiliser cette matrice.
Modifier ici = modifier partout.
"""

# Requêtes HTTP sortantes (webhooks, API tierces)
HTTP_CONNECT_TIMEOUT_S = 5.0
HTTP_READ_TIMEOUT_S    = 10.0
HTTP_WRITE_TIMEOUT_S   = 5.0
HTTP_POOL_TIMEOUT_S    = 2.0

# Requêtes DB SQLAlchemy (via PostgreSQL statement_timeout)
DB_STATEMENT_TIMEOUT_MS = 30_000    # 30s max par query
DB_LOCK_TIMEOUT_MS      = 5_000     # 5s max pour acquérir un lock

# Redis
REDIS_SOCKET_TIMEOUT_S    = 5.0
REDIS_CONNECT_TIMEOUT_S   = 2.0

# Celery tasks (soft=warning, hard=kill)
CELERY_SOFT_TIME_LIMIT_S = 300     # 5min → SoftTimeLimitExceeded (cleanup possible)
CELERY_HARD_TIME_LIMIT_S = 360     # 6min → SIGKILL

# FastAPI endpoint timeout (via middleware)
API_REQUEST_TIMEOUT_S = 60         # 1min max par requête HTTP entrante

# httpx clients — utiliser partout
HTTPX_TIMEOUT = httpx.Timeout(
    connect=HTTP_CONNECT_TIMEOUT_S,
    read=HTTP_READ_TIMEOUT_S,
    write=HTTP_WRITE_TIMEOUT_S,
    pool=HTTP_POOL_TIMEOUT_S,
)
```

```python
# app/core/database.py — statement_timeout PostgreSQL
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={
        "options": (
            f"-c statement_timeout={DB_STATEMENT_TIMEOUT_MS}"
            f" -c lock_timeout={DB_LOCK_TIMEOUT_MS}"
        )
    },
)

# app/main.py — timeout middleware (starlette)
from starlette.middleware.timeout import TimeoutMiddleware
app.add_middleware(TimeoutMiddleware, timeout=API_REQUEST_TIMEOUT_S)
```

---

### 18.5 SSRF Prevention — Validation URLs sortantes (P1)

**Problème** : si un champ `callback_url` vient de l'utilisateur → attaquant peut faire appeler `http://169.254.169.254/` (metadata AWS) ou services internes.

```python
# app/core/ssrf_guard.py
import ipaddress
import socket
from urllib.parse import urlparse
from fastapi import HTTPException

BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),   # AWS metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

ALLOWED_SCHEMES = {"https"}   # Jamais http en prod

def validate_callback_url(url: str) -> str:
    """
    Valider une URL fournie par l'utilisateur avant tout appel HTTP.
    Lever HTTPException 400 si SSRF détecté.
    """
    parsed = urlparse(url)

    if parsed.scheme not in ALLOWED_SCHEMES:
        raise HTTPException(400, f"Schéma interdit : {parsed.scheme}. Utiliser HTTPS.")

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(400, "URL invalide : hostname manquant.")

    # Résoudre le hostname → IP
    try:
        ip_str = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_str)
    except (socket.gaierror, ValueError) as exc:
        raise HTTPException(400, f"Hostname non résolvable : {hostname}") from exc

    # Vérifier que l'IP n'est pas privée/réservée
    for blocked in BLOCKED_NETWORKS:
        if ip in blocked:
            raise HTTPException(400, f"URL pointe vers un réseau interdit ({ip}).")

    return url

# Usage — dans les endpoints acceptant une URL utilisateur
class WebhookCreate(BaseModel):
    url: str
    events: list[str]

    @field_validator("url")
    @classmethod
    def url_ssrf_safe(cls, v: str) -> str:
        return validate_callback_url(v)
```

---

### 18.6 Bulkhead Pattern — Isolation des pools de ressources (P2)

**Problème** : un burst de webhooks peut épuiser le pool de connexions DB → pages front 503.
Bulkhead = pools séparés par domaine critique.

```python
# app/core/bulkhead.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Pool dédié pour opérations critiques (invoices/payments)
_critical_engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
    pool_recycle=1800,
)

# Pool standard pour lectures (catalogue, dashboard)
_standard_engine = create_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=2,
    pool_pre_ping=True,
)

# Pool minimal pour tâches Celery (background)
_celery_engine = create_engine(
    settings.DATABASE_URL,
    pool_size=2,
    max_overflow=1,
)

CriticalSession = sessionmaker(bind=_critical_engine, autoflush=False, autocommit=False)
StandardSession  = sessionmaker(bind=_standard_engine, autoflush=False, autocommit=False)
CelerySession    = sessionmaker(bind=_celery_engine, autoflush=False, autocommit=False)

# Dépendances FastAPI
def get_critical_db(): yield from _session_context(CriticalSession)
def get_db():          yield from _session_context(StandardSession)

# Usage — endpoints financiers sur pool critique
@router.post("/invoices/{id}/add-payment", dependencies=[Depends(tenant_rate_limit())])
def add_payment(id: int, payload: AddPaymentRequest, db: Session = Depends(get_critical_db)):
    ...
```

---

## 19. Sécurité avancée

---

### 19.1 Field-Level Encryption — PII au repos (P1)

**Problème** : email/phone/address en clair en DB → accès DBA ou dump DB = exposition PII.
Solution : chiffrement transparent au niveau ORM via TypeDecorator.

```python
# app/core/field_encryption.py
from sqlalchemy import types
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64, os, json

class EncryptedString(types.TypeDecorator):
    """
    SQLAlchemy TypeDecorator — chiffre/déchiffre transparent avec AES-256-GCM.
    En DB : base64(nonce + ciphertext). En Python : string en clair.
    """
    impl = types.Text
    cache_ok = True
    _PREFIX = "enc:v1:"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        key = os.environ.get("FIELD_ENCRYPTION_KEY", "")
        if not key or len(base64.b64decode(key)) != 32:
            raise ValueError("FIELD_ENCRYPTION_KEY doit être 32 octets en base64")
        self._aesgcm = AESGCM(base64.b64decode(key))

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        """Avant écriture DB → chiffrer."""
        if value is None:
            return None
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, value.encode(), None)
        return self._PREFIX + base64.b64encode(nonce + ciphertext).decode()

    def process_result_value(self, value: str | None, dialect) -> str | None:
        """Après lecture DB → déchiffrer."""
        if value is None or not value.startswith(self._PREFIX):
            return value   # Compatibilité données non-chiffrées (migration)
        raw = base64.b64decode(value[len(self._PREFIX):])
        nonce, ciphertext = raw[:12], raw[12:]
        return self._aesgcm.decrypt(nonce, ciphertext, None).decode()

# app/models/customer.py — champs PII chiffrés
class Customer(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "customers"
    id:    Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(EncryptedString, nullable=False)    # Chiffré ✓
    phone: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)  # Chiffré ✓
    # first_name, last_name → non chiffrés (nécessaires pour recherche/affichage)
    # Selon sensibilité RGPD : chiffrer si requis par DPO

# Migration — données existantes à re-chiffrer via script backfill
# scripts/encrypt_pii_backfill.py :
# for customer in db.scalars(select(Customer)).all():
#     customer.email = customer.email   # Force process_bind_param → stocke chiffré
# db.commit()
```

**Règle** : `FIELD_ENCRYPTION_KEY` injecté par Docker secrets / K8s secrets. **Jamais** dans `.env` commité.

---

### 19.2 Re-authentification avant opérations destructives (P1)

**Problème** : session volée (XSS, token leak) → attaquant peut supprimer données sans connaître le mot de passe.

```python
# app/core/reauth.py
from fastapi import Depends, HTTPException, Header
from app.core.security import verify_password
from app.repositories.user import UserRepository

REAUTH_WINDOW_SECONDS = 300   # 5 minutes

def require_reauth(
    x_confirm_password: str | None = Header(None, alias="X-Confirm-Password"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Dépendance FastAPI — vérifie que le header X-Confirm-Password est correct.
    À utiliser sur : DELETE entité critique, purge, transfer ownership, revoke all sessions.
    """
    if not x_confirm_password:
        raise HTTPException(
            status_code=403,
            detail="Cette action requiert une confirmation de mot de passe.",
            headers={"X-Require-Reauth": "true"},
        )
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(current_user.id)
    if not verify_password(x_confirm_password, user.hashed_password):
        raise HTTPException(status_code=403, detail="Mot de passe incorrect.")

# Usage — endpoints destructifs
@router.delete("/customers/{id}", status_code=204)
def delete_customer(
    id: int,
    _: None = Depends(require_reauth),                     # ← Re-auth obligatoire
    current_user: User = Depends(require_permission("customer:delete")),
    db: Session = Depends(get_db),
):
    customer_service.soft_delete(id, current_user.tenant_id, db)
```

```typescript
// frontend/src/components/ui/ReauthModal.tsx
interface ReauthModalProps {
  isOpen: boolean
  onConfirm: (password: string) => void
  onCancel: () => void
  action: string
}

export function ReauthModal({ isOpen, onConfirm, onCancel, action }: ReauthModalProps) {
  const [password, setPassword] = useState('')

  return (
    <Modal isOpen={isOpen} title="Confirmation requise">
      <p className="text-sm text-gray-600 mb-4">
        Pour <strong>{action}</strong>, confirmez votre mot de passe.
      </p>
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Votre mot de passe"
        className="input w-full"
        autoFocus
      />
      <div className="flex gap-2 mt-4">
        <button className="btn-danger flex-1" onClick={() => onConfirm(password)}>
          Confirmer
        </button>
        <button className="btn-secondary flex-1" onClick={onCancel}>Annuler</button>
      </div>
    </Modal>
  )
}

// Usage dans CustomerDeleteModal
const [showReauth, setShowReauth] = useState(false)
const deleteMutation = useMutation({
  mutationFn: (password: string) =>
    customersApi.delete(customerId, { headers: { 'X-Confirm-Password': password } }),
})
```

---

### 19.3 ReDoS Protection — Timeouts et validation regex (P2)

**Problème** : regex complexe sur input utilisateur → CPU 100% pendant 30s (Denial of Service).

```python
# app/core/safe_regex.py
import re
import signal
from contextlib import contextmanager

class RegexTimeout(Exception):
    pass

@contextmanager
def regex_timeout(seconds: float = 1.0):
    """Context manager — interrompt regex si > N secondes (Unix only)."""
    def _handler(signum, frame):
        raise RegexTimeout("Regex timeout")

    old_handler = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)

# Règles préventives (à appliquer dans les validateurs Pydantic)
#
# ❌ Regex catastrophique
# re.match(r'(a+)+$', user_input)   → exponentiel sur "aaaaaaaaX"
#
# ✅ Ancré + sans imbrication
# re.match(r'^[a-z0-9._-]{1,100}$', user_input)   → O(n)

# Validateurs sûrs pour les champs utilisateur
SAFE_EMAIL_RE    = re.compile(r'^[a-zA-Z0-9._%+\-]{1,64}@[a-zA-Z0-9.\-]{1,255}\.[a-zA-Z]{2,10}$')
SAFE_PHONE_RE    = re.compile(r'^\+?[0-9\s\-().]{7,20}$')
SAFE_IBAN_RE     = re.compile(r'^[A-Z]{2}[0-9]{2}[A-Z0-9]{4,30}$')
SAFE_SLUG_RE     = re.compile(r'^[a-z0-9-]{1,100}$')

# Dans les schémas Pydantic — jamais de pattern user-controlled
class CustomerCreate(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email_safe(cls, v: str) -> str:
        if not SAFE_EMAIL_RE.match(v):
            raise ValueError("Email invalide")
        return v.lower()
```

---

## 20. Frontend React 18 — Patterns avancés

---

### 20.1 Zod — Validation de formulaires typée (P1)

**Note** : Zod est déjà utilisé dans le codebase (ProfilePage, EventFormModal). Cette section documente le **pattern canonique** à uniformiser sur tous les formulaires.

```typescript
// Pattern uniforme — à appliquer sur TOUT formulaire avec validation complexe

// 1. Schéma Zod — source de vérité (types inférés automatiquement)
import { z } from 'zod'

export const CustomerSchema = z.object({
  first_name:    z.string().min(1, 'Prénom requis').max(100),
  last_name:     z.string().min(1, 'Nom requis').max(100),
  email:         z.string().email('Email invalide'),
  phone:         z.string().regex(/^\+?[0-9\s\-().]{7,20}$/, 'Téléphone invalide').optional(),
  customer_type: z.enum(['individual', 'company']),
  company_name:  z.string().max(200).optional(),
}).refine(
  (data) => data.customer_type !== 'company' || !!data.company_name,
  { message: 'Nom de société requis pour les entreprises', path: ['company_name'] }
)

export type CustomerFormData = z.infer<typeof CustomerSchema>

// 2. Usage avec React Hook Form + resolver Zod
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'

function CustomerFormModal({ onSubmit }: { onSubmit: (data: CustomerFormData) => void }) {
  const { register, handleSubmit, watch, formState: { errors, isSubmitting } } =
    useForm<CustomerFormData>({
      resolver: zodResolver(CustomerSchema),
      defaultValues: { customer_type: 'individual' },
    })

  const customerType = watch('customer_type')

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input {...register('first_name')} aria-invalid={!!errors.first_name} />
      {errors.first_name && <span role="alert">{errors.first_name.message}</span>}

      {customerType === 'company' && (
        <input {...register('company_name')} placeholder="Nom de société" />
      )}

      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Enregistrement…' : 'Enregistrer'}
      </button>
    </form>
  )
}

// Règle : tout formulaire avec > 3 champs validés → zodResolver obligatoire.
//         PAS de validation manuelle dans les handlers onChange.
```

---

### 20.2 MSW — Mock Service Worker pour tests frontend (P1)

**Problème** : tests Vitest mockent `vi.mocked(api)` → ne testent pas les vraies transformations HTTP.
MSW intercepte au niveau réseau → tests proches de la réalité.

```typescript
// frontend/src/test/mocks/handlers.ts
import { http, HttpResponse } from 'msw'
import { InvoiceFactory } from '../factories/invoice.factory'

export const handlers = [
  http.get('/api/v1/invoices', ({ request }) => {
    const url = new URL(request.url)
    const page = Number(url.searchParams.get('page') ?? 1)
    return HttpResponse.json({
      items: InvoiceFactory.buildList(5),
      total: 20, page, limit: 5,
    })
  }),

  http.post('/api/v1/invoices/:id/add-payment', async ({ params, request }) => {
    const body = await request.json() as { amount_cents: number }
    return HttpResponse.json({ id: Number(params.id), paid_amount_cents: body.amount_cents })
  }),

  // Simuler une erreur 422 pour tests edge case
  http.post('/api/v1/customers', async ({ request }) => {
    const body = await request.json() as { email: string }
    if (body.email.includes('taken')) {
      return HttpResponse.json(
        { detail: 'Email déjà utilisé' },
        { status: 422 }
      )
    }
    return HttpResponse.json(CustomerFactory.build({ email: body.email }), { status: 201 })
  }),
]

// frontend/src/test/setup.ts
import { setupServer } from 'msw/node'
import { handlers } from './mocks/handlers'

export const server = setupServer(...handlers)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())   // Reset overrides entre tests
afterAll(() => server.close())

// Test utilisant MSW — pas de mock Vitest
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

it('affiche erreur si email déjà pris', async () => {
  render(<CustomerFormModal />)
  await userEvent.type(screen.getByLabelText('Email'), 'taken@example.com')
  await userEvent.click(screen.getByRole('button', { name: /enregistrer/i }))
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Email déjà utilisé'))
})
```

---

### 20.3 React 18 Concurrent — useTransition & useDeferredValue (P2)

**Problème** : filtrage de liste sur frappe → chaque keystroke re-render synchrone → janky UI.

```typescript
// useTransition — marquer une mise à jour comme non urgente
import { useState, useTransition } from 'react'

function ReservationsPage() {
  const [query, setQuery] = useState('')
  const [filteredList, setFilteredList] = useState(reservations)
  const [isPending, startTransition] = useTransition()

  function handleSearch(value: string) {
    setQuery(value)   // Mise à jour urgente (champ input réactif immédiatement)

    startTransition(() => {
      // Mise à jour non urgente — React peut interrompre pour prioriser
      // des events plus urgents (ex: autre keystroke)
      setFilteredList(reservations.filter(r =>
        r.reference.includes(value) || r.customer_name.includes(value)
      ))
    })
  }

  return (
    <>
      <input value={query} onChange={(e) => handleSearch(e.target.value)} />
      {isPending && <span className="text-xs text-gray-400">Filtrage…</span>}
      <ReservationList items={filteredList} />
    </>
  )
}

// useDeferredValue — déférer la valeur utilisée par un composant lourd
import { useDeferredValue, memo } from 'react'

function InventoryPage() {
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)   // Décalé, stale pendant frappe

  return (
    <>
      <input value={search} onChange={(e) => setSearch(e.target.value)} />
      {/* ProductGrid reçoit deferredSearch → ne re-render pas à chaque keystroke */}
      <ProductGrid search={deferredSearch} isStale={search !== deferredSearch} />
    </>
  )
}

const ProductGrid = memo(({ search, isStale }: { search: string; isStale: boolean }) => {
  const products = useFilteredProducts(search)
  return (
    <div style={{ opacity: isStale ? 0.6 : 1 }}>   // Feedback visuel pendant déférence
      {products.map(p => <ProductCard key={p.id} product={p} />)}
    </div>
  )
})

// Règle :
// - useTransition : quand l'action UI doit déclencher une transition d'état coûteuse
// - useDeferredValue : quand un composant reçoit une prop qui change fréquemment
```

---

### 20.4 URL State Sync — Filtres et pagination dans l'URL (P1)

**Problème** : rafraîchir la page ou partager un lien perd les filtres actifs (page, search, status).

```typescript
// frontend/src/hooks/useUrlState.ts
import { useSearchParams } from 'react-router-dom'
import { useCallback } from 'react'

type Serializable = string | number | boolean | null | undefined

export function useUrlState<T extends Record<string, Serializable>>(defaults: T) {
  const [params, setParams] = useSearchParams()

  const state = Object.fromEntries(
    Object.entries(defaults).map(([key, defaultVal]) => {
      const raw = params.get(key)
      if (raw === null) return [key, defaultVal]
      if (typeof defaultVal === 'number') return [key, Number(raw)]
      if (typeof defaultVal === 'boolean') return [key, raw === 'true']
      return [key, raw]
    })
  ) as T

  const setState = useCallback(
    (updates: Partial<T>) => {
      setParams((prev) => {
        const next = new URLSearchParams(prev)
        Object.entries(updates).forEach(([key, val]) => {
          if (val === null || val === undefined || val === defaults[key]) {
            next.delete(key)   // Valeur par défaut → propre dans l'URL
          } else {
            next.set(key, String(val))
          }
        })
        return next
      }, { replace: true })   // replace: true → pas de nouvelle entrée dans l'historique
    },
    [setParams, defaults]
  )

  return [state, setState] as const
}

// Usage dans InvoicesPage
function InvoicesPage() {
  const [filters, setFilters] = useUrlState({
    page: 1,
    search: '',
    status: '',       // '' = tous
    year: new Date().getFullYear(),
  })

  // URL : /invoices?page=2&status=sent&year=2026
  // Partager le lien → même état

  const { data } = useQuery({
    queryKey: ['invoices', filters],
    queryFn: () => invoicesApi.list(filters),
  })

  return (
    <>
      <input value={filters.search}
             onChange={(e) => setFilters({ search: e.target.value, page: 1 })} />
      <select value={filters.status}
              onChange={(e) => setFilters({ status: e.target.value, page: 1 })}>
        <option value="">Tous</option>
        <option value="sent">Envoyées</option>
        <option value="paid">Payées</option>
      </select>
      <Pagination page={filters.page} onChange={(p) => setFilters({ page: p })} />
    </>
  )
}
```

---

## 21. Tests avancés

---

### 21.1 TestContainers — DB éphémère par suite de tests (P2)

**Problème** : tests d'intégration partagent une DB → ordre d'exécution crée des dépendances cachées.
TestContainers = PostgreSQL frais par session de test.

```python
# tests/conftest_containers.py — alternative à conftest.py pour suites isolées
import pytest
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer
from sqlalchemy import create_engine, text
from alembic.config import Config
from alembic import command

@pytest.fixture(scope="session")
def postgres_container():
    """Container PostgreSQL éphémère pour toute la session de test."""
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg

@pytest.fixture(scope="session")
def redis_container():
    with RedisContainer("redis:7-alpine") as redis:
        yield redis

@pytest.fixture(scope="session")
def test_engine(postgres_container):
    engine = create_engine(postgres_container.get_connection_url())

    # Appliquer toutes les migrations Alembic → DB propre et à jour
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", postgres_container.get_connection_url())
    command.upgrade(alembic_cfg, "head")

    yield engine
    engine.dispose()

@pytest.fixture
def db(test_engine):
    """Session avec savepoint → rollback parfait entre tests."""
    connection = test_engine.connect()
    transaction = connection.begin()
    savepoint = connection.begin_nested()

    session = Session(bind=connection, autoflush=False)
    yield session

    session.close()
    savepoint.rollback()
    transaction.rollback()
    connection.close()
```

---

### 21.2 Visual Regression — Playwright screenshots (P3)

```typescript
// frontend/tests/e2e/visual-regression.spec.ts
import { test, expect } from '@playwright/test'

test.describe('Visual Regression — composants clés', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    // Login rapide
  })

  test('InvoicesPage — état initial', async ({ page }) => {
    await page.goto('/invoices')
    await page.waitForLoadState('networkidle')

    // Masquer données dynamiques (dates, montants variables)
    await page.evaluate(() => {
      document.querySelectorAll('[data-testid="dynamic"]').forEach(el => {
        (el as HTMLElement).style.visibility = 'hidden'
      })
    })

    await expect(page).toHaveScreenshot('invoices-page.png', {
      maxDiffPixelRatio: 0.02,   // Tolérance 2% de pixels différents
      animations: 'disabled',
    })
  })

  test('EventDetailsModal — facture partiellement payée', async ({ page }) => {
    await page.goto('/events')
    await page.locator('[data-testid="event-row"]').first().click()
    await page.waitForSelector('[role="dialog"]')

    await expect(page.locator('[role="dialog"]')).toHaveScreenshot('event-detail-modal.png')
  })
})

// playwright.config.ts — configuration snapshots
export default defineConfig({
  expect: {
    toHaveScreenshot: {
      threshold: 0.02,
      animations: 'disabled',
    },
  },
  snapshotDir: 'tests/e2e/snapshots',
})

// Mettre à jour les snapshots de référence :
// npx playwright test --update-snapshots
```

---

### 21.3 Flaky Test Quarantine (P2)

```python
# pyproject.toml — pytest-rerunfailures pour retry
# [tool.pytest.ini_options]
# addopts = "--reruns 2 --reruns-delay 0.5"  # Retry 2x avant fail

# Marqueur @flaky pour tests connus instables
import pytest

@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_celery_task_email_sent():
    """Test E2E async — légèrement flaky par nature."""
    ...

# CI — quarantine les tests flaky (pas de blocage de pipeline)
# .github/workflows/test.yml :
# - run: pytest tests/ -v --ignore=tests/quarantine/
# - run: pytest tests/quarantine/ -v || echo "Quarantine failures (non-blocking)"
#   continue-on-error: true
```

```python
# tests/quarantine/README.md — règles de quarantine
# Un test va en quarantine si :
# 1. Il échoue de façon intermittente sur 3 branches consécutives
# 2. Le root cause n'est pas identifiable en < 30 minutes
# Sortie de quarantine : fix + preuve de stabilité sur 10 runs consécutifs
```

---

## 22. DX — Developer Experience & Process

---

### 22.1 Pre-commit Hooks — Qualité automatique avant commit (P0)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
        args: [--fix]          # Auto-fix lint errors
      - id: ruff-format        # Formatter (remplace black)

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
        args: [--strict, --ignore-missing-imports]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-merge-conflict
      - id: detect-private-key     # Bloque si clé SSH/PEM dans le commit
      - id: no-commit-to-branch    # Interdit commit direct sur main
        args: [--branch, main]

  - repo: https://github.com/commitizen-tools/commitizen
    rev: v3.14.0
    hooks:
      - id: commitizen             # Valide format Conventional Commits
```

```bash
# Installation en une commande
pip install pre-commit
pre-commit install          # Hook sur git commit
pre-commit install --hook-type commit-msg   # Hook sur message de commit

# Makefile
pre-commit-setup:
	pip install pre-commit
	pre-commit install
	pre-commit install --hook-type commit-msg
	@echo "✅ Pre-commit hooks installés"
```

---

### 22.2 Conventional Commits + Changelog automatique (P1)

```
# Format obligatoire
<type>(<scope>): <description>

# Types valides
feat     → nouvelle fonctionnalité (MINOR en semver)
fix      → correction bug (PATCH)
perf     → amélioration performance
refactor → refactoring sans changement de comportement
test     → ajout/modification de tests
docs     → documentation uniquement
chore    → maintenance (deps, CI, tooling)
ci       → modifications CI/CD
revert   → revert d'un commit

# Breaking change → MAJOR
feat(api)!: remove legacy /v0/ endpoints
BREAKING CHANGE: /api/v0/* supprimés — migrer vers /api/v1/*

# Exemples valides
feat(invoices): add addCharge endpoint with tenant isolation
fix(deposits): fix missing timestamp NOT NULL on migration
test(payments): add cross-tenant isolation test
perf(dashboard): replace raw query with materialized view
```

```yaml
# .commitlintrc.yml
extends:
  - '@commitlint/config-conventional'
rules:
  scope-enum:
    - 2
    - always
    - [invoices, reservations, customers, products, inventory, auth, admin, dashboard, api, db, ci, deps]
  subject-max-length:
    - 2
    - always
    - 100
```

```bash
# CHANGELOG.md généré automatiquement via git-cliff
# pyproject.toml (ou cliff.toml)
# [tool.git-cliff.changelog]
# body = """
# ## [{{ version }}] - {{ timestamp | date(format="%Y-%m-%d") }}
# {% for group, commits in commits | group_by(attribute="group") %}
# ### {{ group }}
# {% for commit in commits %}
# - {{ commit.message }} ([{{ commit.id | truncate(length=7, end="") }}](https://github.com/...))
# {%- endfor %}
# {% endfor %}
# """

# Makefile
changelog:
	git-cliff --output CHANGELOG.md
	@echo "✅ CHANGELOG.md mis à jour"
```

---

### 22.3 ADR — Architecture Decision Records (P1)

**Objectif** : tracer le POURQUOI des décisions architecturales (pas seulement le QUOI).

```markdown
<!-- docs/adr/0001-biginteger-centimes.md -->
# ADR-0001 : Montants en BigInteger centimes

**Date** : 2025-01-15
**Statut** : Accepté
**Décideurs** : [noms]

## Contexte

Les montants monétaires doivent être stockés en base de données pour les factures,
paiements, cautions et frais supplémentaires.

## Options évaluées

1. `FLOAT` (PostgreSQL `float8`)
2. `DECIMAL(12,2)` (PostgreSQL `numeric`)
3. **`BIGINT` centimes** (PostgreSQL `bigint`)

## Décision

**Option 3 — BigInteger centimes** : stocker 250 pour représenter 2,50 €.

## Justification

- `FLOAT` → erreurs d'arrondi binaire : `0.1 + 0.2 ≠ 0.3`
- `DECIMAL` → précis mais plus lent, et risque de conversion Python `Decimal` ↔ `int`
- `BigInteger centimes` → arithmétique entière exacte, performant, pas d'erreur d'arrondi

## Conséquences

- ✅ Calculs financiers exacts sans arrondi
- ✅ Comparaisons simples (`amount == 0`, `amount > 1000`)
- ⚠️  Conversion systématique `/ 100` pour affichage (centralisée dans `_euros` computed fields)
- ⚠️  Pas intuitif pour les développeurs → documenté dans CLAUDE.md
```

```
# Structure docs/adr/
docs/adr/
├── README.md              # Comment lire/créer un ADR
├── 0001-biginteger-centimes.md
├── 0002-multi-tenant-row-level.md
├── 0003-soft-delete-is-active.md
├── 0004-redis-rate-limiting.md
├── 0005-alembic-expand-contract.md
├── 0006-outbox-vs-saga.md
└── 0007-cursor-vs-offset-pagination.md

# Template (docs/adr/template.md)
# # ADR-XXXX : Titre
# **Date** : YYYY-MM-DD | **Statut** : Proposé / Accepté / Déprécié / Remplacé par ADR-XXXX
# ## Contexte
# ## Options évaluées
# ## Décision
# ## Justification
# ## Conséquences
```

---

## 23. Observabilité avancée & Data

---

### 23.1 SLO / Error Budgets (P2)

```yaml
# docs/ops/SLO.md — Définition des SLOs (Service Level Objectives)
#
# SLO 1 : Disponibilité API
#   - Target : 99.9% (max 8.7h downtime/an)
#   - Mesure : (requêtes 2xx + 3xx + 4xx) / total requêtes sur 30j
#   - Error Budget : 43.8min/mois
#
# SLO 2 : Latence P95
#   - Target : 95% des requêtes < 500ms (window 7j)
#   - Exclusions : /health/*, /metrics
#
# SLO 3 : Taux de succès mutations critiques
#   - Target : 99.5% success sur POST /invoices, POST /payments, POST /deposits
#   - Error Budget brûlé si : double-débit, perte d'état, 500 sur mutation
```

```python
# app/core/metrics.py — métriques pour SLO
from prometheus_client import Histogram, Counter

# SLO latence
http_request_duration = Histogram(
    "http_request_duration_seconds",
    "Durée des requêtes HTTP",
    labelnames=["method", "endpoint", "status_code"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)

# SLO taux d'erreur mutations critiques
critical_mutation_errors = Counter(
    "critical_mutation_errors_total",
    "Erreurs sur mutations financières critiques",
    labelnames=["endpoint", "error_type"],
)

# Alertes Prometheus — rules/slo_alerts.yml
# - alert: SLOLatencyBudgetExhausted
#   expr: |
#     (
#       1 - (
#         rate(http_request_duration_seconds_bucket{le="0.5"}[7d]) /
#         rate(http_request_duration_seconds_count[7d])
#       )
#     ) > 0.05   # > 5% des requêtes > 500ms
#   for: 10m
#   annotations:
#     summary: "SLO P95 latence en danger — error budget > 50% consommé"
```

---

### 23.2 Data Anonymisation — Environnements staging/dev (P1)

**Règle** : jamais de dump de production directement en staging. PII à anonymiser.

```python
# scripts/anonymize_db.py — à exécuter après pg_dump → avant restauration staging
"""
Anonymise les PII d'un dump PostgreSQL pour usage en staging/dev.
Préserve la cohérence des données (FK, statuts, montants).
"""
import secrets
import string
from sqlalchemy import create_engine, text, update

STAGING_DB_URL = "postgresql://..."   # DB cible staging

def anonymize_customers(db):
    customers = db.execute(text("SELECT id FROM customers")).fetchall()
    for row in customers:
        fake_email = f"user_{row.id}@staging.invalid"
        fake_phone = f"+33600{row.id:06d}"
        db.execute(
            text("""
                UPDATE customers SET
                    email = :email,
                    phone = :phone,
                    address = 'Adresse anonymisée',
                    city = 'Ville',
                    postal_code = '75000',
                    first_name = 'Prénom' || :id,
                    last_name = 'Nom' || :id
                WHERE id = :id
            """),
            {"email": fake_email, "phone": fake_phone, "id": row.id}
        )

def anonymize_users(db):
    db.execute(text("""
        UPDATE users SET
            email = 'admin@staging.invalid' WHERE role = 'admin',
            hashed_password = :hash
    """), {"hash": hash_password("StagingPassword123!")})

def run():
    engine = create_engine(STAGING_DB_URL)
    with engine.begin() as db:
        anonymize_customers(db)
        anonymize_users(db)
        print(f"✅ Anonymisation complète")

if __name__ == "__main__":
    run()

# Makefile
# staging-refresh:
#     pg_dump ${PROD_DB_URL} | psql ${STAGING_DB_URL}
#     python scripts/anonymize_db.py
#     @echo "✅ Staging DB refreshed + anonymisée"
```

---

### 23.3 Backup & Restore Runbook (P1)

```bash
# scripts/ops/backup.sh — Backup PostgreSQL + Redis

#!/bin/bash
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/${TIMESTAMP}"
mkdir -p "${BACKUP_DIR}"

# 1. PostgreSQL — dump compressé
echo "[1/3] PostgreSQL dump..."
pg_dump \
  --format=custom \
  --compress=9 \
  --file="${BACKUP_DIR}/marveline_${TIMESTAMP}.dump" \
  "${DATABASE_URL}"

# 2. Redis — RDB snapshot
echo "[2/3] Redis BGSAVE..."
redis-cli -u "${REDIS_URL}" BGSAVE
sleep 5   # Attendre fin de BGSAVE
redis-cli -u "${REDIS_URL}" --rdb "${BACKUP_DIR}/redis_${TIMESTAMP}.rdb"

# 3. Upload S3 (ou équivalent)
echo "[3/3] Upload backup..."
aws s3 cp "${BACKUP_DIR}/" "s3://${BACKUP_BUCKET}/marveline/" --recursive

# Nettoyage local (garder 7j)
find /backups -mtime +7 -delete

echo "✅ Backup terminé : ${BACKUP_DIR}"
```

```bash
# scripts/ops/restore.sh — Point-in-time restore

#!/bin/bash
BACKUP_FILE="${1:?Usage: restore.sh <backup_file.dump>}"

echo "⚠️  RESTAURATION EN COURS — DB CIBLE : ${DATABASE_URL}"
read -p "Confirmer ? (yes/no): " confirm
[[ "${confirm}" == "yes" ]] || exit 1

# Arrêter l'application d'abord
echo "[1/3] Arrêt application..."
docker compose stop api worker

echo "[2/3] Restauration PostgreSQL..."
pg_restore \
  --clean \
  --if-exists \
  --dbname="${DATABASE_URL}" \
  "${BACKUP_FILE}"

echo "[3/3] Vérification migrations..."
docker compose run --rm api alembic current

echo "[4/4] Redémarrage..."
docker compose up -d api worker

echo "✅ Restauration terminée"
```

```
# Politique de rétention des backups
# - Daily  : 7 jours
# - Weekly : 4 semaines
# - Monthly: 12 mois
# - RPO cible : < 24h (Recovery Point Objective)
# - RTO cible : < 2h (Recovery Time Objective)
# Tester restore mensuel en staging — résultat documenté dans docs/ops/RESTORE_TESTS.md
```

---

## 24. Matrice globale — Sections 18–23

| # | Pattern | Priorité | Effort |
|---|---------|---------|--------|
| 14.15 + 22.1 | Pre-commit hooks (ruff/mypy/black) | **P0** | 0.5j |
| 18.1 | Outbox Pattern (events atomiques) | **P0** | 2j |
| 19.1 | Field-level Encryption PII | **P1** | 2j |
| 19.2 | Re-auth avant ops destructives | **P1** | 1j |
| 18.3 | Retry Jitter exponentiel | **P1** | 0.5j |
| 18.4 | Timeout Strategy centralisée | **P1** | 0.5j |
| 18.5 | SSRF Prevention | **P1** | 1j |
| 20.1 | Zod resolver uniforme | **P1** | 1j |
| 20.2 | MSW Mock Service Worker | **P1** | 1j |
| 20.4 | URL State Sync searchParams | **P1** | 1j |
| 22.2 | Conventional Commits + Changelog | **P1** | 0.5j |
| 22.3 | ADR Architecture Decision Records | **P1** | 1j |
| 23.2 | Data Anonymisation staging | **P1** | 1j |
| 23.3 | Backup/Restore runbook | **P1** | 0.5j |
| 18.2 | Saga + Compensation | **P2** | 3j |
| 18.6 | Bulkhead pools séparés | **P2** | 1j |
| 19.3 | ReDoS Protection | **P2** | 0.5j |
| 20.3 | React 18 useTransition | **P2** | 0.5j |
| 21.1 | TestContainers | **P2** | 1j |
| 21.3 | Flaky Test Quarantine | **P2** | 0.5j |
| 23.1 | SLO / Error Budgets | **P2** | 1j |
| 21.2 | Visual Regression Playwright | **P3** | 1j |

---

## Section 25 — Infrastructure & Sécurité Avancée

### 25.1 Docker Multi-Stage Build — Backend (non-root, read-only)

**Problème actuel** : Le `Dockerfile` backend n'utilise pas de multi-stage build. L'image contient les outils de build en production (gcc, pip, etc.), augmentant la surface d'attaque et la taille de l'image.

**Convention** :

```dockerfile
# Dockerfile (backend)
# ── Stage 1 : builder ──────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install --prefix=/install .

# ── Stage 2 : runtime ─────────────────────────────────────
FROM python:3.12-slim AS runtime

# Dépendances système runtime uniquement
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 && rm -rf /var/lib/apt/lists/*

# Non-root user obligatoire
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --no-create-home appuser

# Copier les artefacts compilés depuis builder
COPY --from=builder /install /usr/local
WORKDIR /app
COPY --chown=appuser:appgroup . .

USER appuser

# Read-only filesystem (forcer en docker-compose via read_only: true + tmpfs)
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "4", "--no-access-log"]
```

**docker-compose.yml** :
```yaml
services:
  api:
    build:
      context: .
      target: runtime          # Exclut le stage builder
    read_only: true             # Filesystem read-only
    tmpfs:
      - /tmp                    # Seul répertoire writable
      - /app/logs
    security_opt:
      - no-new-privileges:true  # Interdit escalade de privilèges
    cap_drop:
      - ALL                     # Supprime toutes les Linux capabilities
    cap_add:
      - NET_BIND_SERVICE        # Réajouter uniquement ce qui est nécessaire
```

**Règle** : Toute image backend doit passer `docker scout cves` (ou `trivy image`) avant merge. Taille cible : < 200 MB.

---

### 25.2 Secrets Management — HashiCorp Vault / Doppler

**Problème actuel** : Les secrets sont stockés en clair dans `.env` / `docker-compose.yml`. En production, toute compromission du filesystem expose tous les credentials.

**Convention** :

```python
# app/core/secrets.py
"""
Abstraction secrets : env local en dev, Vault/Doppler en prod.
Jamais accéder os.environ directement pour les secrets critiques.
"""
import os
from functools import lru_cache
from typing import Optional

try:
    import hvac  # HashiCorp Vault client
    _VAULT_AVAILABLE = True
except ImportError:
    _VAULT_AVAILABLE = False


class SecretsManager:
    def __init__(self):
        self._vault_client: Optional[object] = None
        self._use_vault = os.getenv("SECRETS_BACKEND", "env") == "vault"

    def _get_vault_client(self):
        if self._vault_client is None:
            client = hvac.Client(
                url=os.environ["VAULT_ADDR"],
                token=os.environ["VAULT_TOKEN"],
            )
            assert client.is_authenticated(), "Vault auth failed"
            self._vault_client = client
        return self._vault_client

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        if self._use_vault and _VAULT_AVAILABLE:
            try:
                secret = self._get_vault_client().secrets.kv.v2.read_secret_version(
                    path=f"carocorp/{os.getenv('ENV', 'dev')}/{key}"
                )
                return secret["data"]["data"].get(key, default)
            except Exception:
                # Fallback env en cas d'échec Vault (dev/test)
                pass
        return os.getenv(key, default)


@lru_cache(maxsize=1)
def get_secrets() -> SecretsManager:
    return SecretsManager()


# Usage dans app/core/config.py
secrets = get_secrets()

DATABASE_URL: str = secrets.get("DATABASE_URL") or ""
SECRET_KEY: str = secrets.get("SECRET_KEY") or ""
REDIS_URL: str = secrets.get("REDIS_URL") or ""
```

**Rotation sans downtime** :
```python
# Les secrets rotatifs doivent avoir une version ET une grace period
# Voir Section 16.4 (Secret Rotation JWT) pour le pattern complet
# DATABASE_URL rotation : utiliser pgBouncer comme proxy + rotation côté pool
```

**Règles** :
- `DATABASE_URL`, `SECRET_KEY`, `REDIS_URL`, clés API tiers → toujours via `SecretsManager`
- `.env` interdit en production. `.env.example` avec valeurs factices dans le repo
- `detect-private-key` hook pre-commit (déjà configuré section 22.1)
- En staging/prod : `SECRETS_BACKEND=vault` obligatoire

---

### 25.3 Database SSL/TLS + Connection String sécurisée

**Problème actuel** : `DATABASE_URL` sans `sslmode=require`. Les connexions PostgreSQL circulent en clair sur le réseau interne.

**Convention** :

```python
# app/core/database.py
import os
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.environ["DATABASE_URL"]

# Forcer SSL en production
if os.getenv("ENV", "dev") in ("staging", "production"):
    # Append sslmode si absent
    if "sslmode=" not in DATABASE_URL:
        separator = "&" if "?" in DATABASE_URL else "?"
        DATABASE_URL = f"{DATABASE_URL}{separator}sslmode=require"

engine = create_async_engine(
    DATABASE_URL,
    connect_args={
        "ssl": os.getenv("ENV") != "dev",  # SSL hors dev
        "server_settings": {
            "application_name": "carocorp-api",
            "statement_timeout": "30000",   # 30s max query time
            "lock_timeout": "10000",        # 10s max lock wait
        },
    },
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
)
```

**PostgreSQL server config** (`postgresql.conf`) :
```ini
ssl = on
ssl_cert_file = 'server.crt'
ssl_key_file = 'server.key'
ssl_min_protocol_version = 'TLSv1.3'
log_connections = on
log_disconnections = on
```

---

### 25.4 Immutable Infrastructure & Blue/Green Deployment

**Convention** :

```yaml
# docker-compose.prod.yml — Blue/Green via labels
services:
  api-blue:
    image: carocorp/api:${BLUE_TAG}
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.api.rule=Host(`api.carocorp.fr`)"
      - "traefik.http.services.api.loadbalancer.server.port=8000"
    deploy:
      replicas: ${BLUE_REPLICAS:-2}
      update_config:
        order: start-first          # Démarrer nouveau avant stopper l'ancien
        failure_action: rollback
      rollback_config:
        order: stop-first

  api-green:
    image: carocorp/api:${GREEN_TAG}
    labels:
      - "traefik.enable=${GREEN_ACTIVE:-false}"  # Inactif par défaut
    deploy:
      replicas: ${GREEN_REPLICAS:-0}
```

**Script de bascule** :
```bash
#!/usr/bin/env bash
# scripts/deploy/blue_green_switch.sh
set -euo pipefail

CURRENT_ACTIVE="${1:-blue}"
NEW_COLOR=$([ "$CURRENT_ACTIVE" = "blue" ] && echo "green" || echo "blue")
NEW_TAG="${2:?Provide image tag}"

echo "Deploying $NEW_COLOR with tag $NEW_TAG"

# 1. Déployer nouvelle version (0 trafic)
GREEN_TAG="$NEW_TAG" GREEN_REPLICAS=2 GREEN_ACTIVE=false \
  docker compose -f docker-compose.prod.yml up -d "api-${NEW_COLOR}"

# 2. Health check nouveau déploiement
for i in {1..30}; do
  if curl -sf "http://api-${NEW_COLOR}:8000/health/ready"; then
    echo "New version healthy"
    break
  fi
  sleep 2
done

# 3. Basculer le trafic
eval "${NEW_COLOR^^}_ACTIVE=true ${CURRENT_ACTIVE^^}_REPLICAS=0" \
  docker compose -f docker-compose.prod.yml up -d

echo "Traffic switched to $NEW_COLOR"
```

**Canary** (5% trafic vers nouvelle version via Traefik weights) :
```yaml
labels:
  - "traefik.http.services.api-canary.loadbalancer.server.port=8000"
  - "traefik.http.middlewares.weighted.plugin.traefik-plugin-canary.canaryHeaderName=X-Canary"
  - "traefik.http.middlewares.weighted.plugin.traefik-plugin-canary.ratio=5"
```

---

## Section 26 — Performance Frontend Avancée

### 26.1 React.memo — Stratégie d'application

**Règle** : `React.memo` ne doit PAS être appliqué partout aveuglément (overhead inutile si props changent à chaque render). Appliquer uniquement sur les composants :
- Rendus fréquemment avec les **mêmes props** (ex: lignes de tableau, cartes de liste)
- Coûteux à calculer (graphiques, listes longues)
- Enfants d'un parent qui re-render souvent pour des raisons indépendantes

```tsx
// ✅ Bon usage : ligne de tableau réutilisée (même props entre renders)
interface ReservationRowProps {
  reservation: ReservationSummary;
  onOpen: (id: number) => void;  // Doit être stable (useCallback du parent)
}

export const ReservationRow = React.memo<ReservationRowProps>(
  ({ reservation, onOpen }) => {
    return (
      <tr onClick={() => onOpen(reservation.id)}>
        <td>{reservation.reference}</td>
        <td>{reservation.customer_name}</td>
        <td>{formatDate(reservation.start_date)}</td>
      </tr>
    );
  },
  // Custom comparator si props complexes
  (prev, next) =>
    prev.reservation.id === next.reservation.id &&
    prev.reservation.updated_at === next.reservation.updated_at
);

// ✅ Bon usage : composant chart coûteux
export const RevenueChart = React.memo(({ data }: { data: MonthlyRevenue[] }) => {
  return <BarChart data={data} width={600} height={300} />;
});

// ❌ Mauvais usage : composant simple, props toujours différentes
// export const UserAvatar = React.memo(({ initials }: { initials: string }) => <div>{initials}</div>)
// → overhead inutile, `initials` est une string primitive (comparaison déjà rapide)
```

**useCallback obligatoire avec memo** :
```tsx
// Parent qui passe des callbacks à un enfant memoized
const EventsPage = () => {
  const [selectedId, setSelectedId] = useState<number | null>(null);

  // ✅ Stable : ne recrée pas la fonction à chaque render
  const handleOpen = useCallback((id: number) => {
    setSelectedId(id);
  }, []);  // Dépendances vides → toujours la même référence

  return <ReservationRow onOpen={handleOpen} ... />;
};
```

**useMemo — critères d'application** :
```tsx
// ✅ Calcul coûteux (tri/filtre sur grande liste)
const filteredEvents = useMemo(() =>
  events
    .filter(e => e.status === filter)
    .sort((a, b) => new Date(a.start_date).getTime() - new Date(b.start_date).getTime()),
  [events, filter]  // Recalcule seulement si ces dépendances changent
);

// ❌ Inutile : pas coûteux
// const label = useMemo(() => `${firstName} ${lastName}`, [firstName, lastName])
// → juste écrire `${firstName} ${lastName}` directement
```

---

### 26.2 Zustand avec Immer Middleware

**Problème** : Les mutations d'état imbriquées en Zustand nécessitent du spread verbeux et error-prone.

**Convention** :

```typescript
// frontend/src/stores/reservationStore.ts
import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'
import { persist, createJSONStorage } from 'zustand/middleware'

interface ReservationFilters {
  status: string;
  customer_id: number | null;
  date_from: string | null;
  date_to: string | null;
}

interface ReservationStore {
  filters: ReservationFilters;
  page: number;
  pageSize: number;
  setFilter: <K extends keyof ReservationFilters>(key: K, value: ReservationFilters[K]) => void;
  resetFilters: () => void;
  setPage: (page: number) => void;
}

const DEFAULT_FILTERS: ReservationFilters = {
  status: '',
  customer_id: null,
  date_from: null,
  date_to: null,
};

export const useReservationStore = create<ReservationStore>()(
  persist(
    immer((set) => ({
      filters: DEFAULT_FILTERS,
      page: 1,
      pageSize: 20,

      setFilter: (key, value) =>
        set((state) => {
          // Immer : mutation directe lisible, immutabilité garantie
          state.filters[key] = value;
          state.page = 1;  // Reset page sur tout changement de filtre
        }),

      resetFilters: () =>
        set((state) => {
          state.filters = DEFAULT_FILTERS;
          state.page = 1;
        }),

      setPage: (page) =>
        set((state) => {
          state.page = page;
        }),
    })),
    {
      name: 'marveline-reservations',
      storage: createJSONStorage(() => sessionStorage),  // sessionStorage pour état temporaire
      partialize: (state) => ({
        filters: state.filters,
        pageSize: state.pageSize,
        // Ne pas persister `page` → toujours repartir de page 1
      }),
    }
  )
);
```

**Installation** : `immer` est déjà une peer dep de Zustand — `import { immer } from 'zustand/middleware/immer'` suffit.

---

### 26.3 Design Tokens CSS avec Tailwind

**Problème** : Les couleurs et spacings sont hardcodés dans `tailwind.config.js` sans système de tokens. Difficile à maintenir sur un branding update.

**Convention** :

```css
/* frontend/src/styles/tokens.css */
:root {
  /* Brand */
  --color-brand-50: #f0f4ff;
  --color-brand-100: #e0e9ff;
  --color-brand-500: #4f6ef7;
  --color-brand-600: #3b55e6;
  --color-brand-700: #2a42c8;

  /* Semantic */
  --color-success: #16a34a;
  --color-warning: #d97706;
  --color-error: #dc2626;
  --color-info: #2563eb;

  /* Neutral */
  --color-surface: #ffffff;
  --color-surface-secondary: #f9fafb;
  --color-border: #e5e7eb;
  --color-text-primary: #111827;
  --color-text-secondary: #6b7280;
  --color-text-muted: #9ca3af;

  /* Spacing scale (base 4px) */
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-4: 1rem;
  --space-6: 1.5rem;
  --space-8: 2rem;

  /* Typography */
  --font-sans: 'Inter', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgb(0 0 0 / 0.05);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1);
  --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1);

  /* Radius */
  --radius-sm: 0.375rem;
  --radius-md: 0.5rem;
  --radius-lg: 0.75rem;
  --radius-xl: 1rem;

  /* Transitions */
  --transition-fast: 150ms ease;
  --transition-base: 250ms ease;
}

/* Dark mode override */
[data-theme="dark"] {
  --color-surface: #0f172a;
  --color-surface-secondary: #1e293b;
  --color-border: #334155;
  --color-text-primary: #f1f5f9;
  --color-text-secondary: #94a3b8;
  --color-text-muted: #64748b;
}
```

```javascript
// tailwind.config.js — référencer les tokens CSS
module.exports = {
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: 'var(--color-brand-50)',
          100: 'var(--color-brand-100)',
          500: 'var(--color-brand-500)',
          600: 'var(--color-brand-600)',
          700: 'var(--color-brand-700)',
        },
        surface: 'var(--color-surface)',
        'surface-secondary': 'var(--color-surface-secondary)',
        border: 'var(--color-border)',
        'text-primary': 'var(--color-text-primary)',
        'text-secondary': 'var(--color-text-secondary)',
      },
      fontFamily: {
        sans: 'var(--font-sans)',
        mono: 'var(--font-mono)',
      },
      borderRadius: {
        sm: 'var(--radius-sm)',
        DEFAULT: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        xl: 'var(--radius-xl)',
      },
    },
  },
};
```

**Règle** : Tout nouveau composant UI utilise les classes Tailwind `text-text-primary`, `bg-surface`, `border-border` — jamais de couleurs hardcodées comme `text-gray-900` en dehors de `tokens.css`.

---

## Section 27 — Tests Avancés

### 27.1 Snapshot Testing — Stratégie

**Quand utiliser** : uniquement pour les structures de données stables (schémas API, transformations de données), **pas** pour les snapshots DOM (trop fragiles).

```typescript
// frontend/src/utils/__tests__/formatters.test.ts
import { describe, it, expect } from 'vitest';
import { formatInvoiceSummary } from '../formatters';

describe('formatInvoiceSummary', () => {
  it('formats correctly (inline snapshot)', () => {
    const result = formatInvoiceSummary({
      reference: 'FAC-2026-001',
      total_cents: 25000,
      status: 'paid',
      customer_name: 'Jean Dupont',
    });

    // Snapshot inline : visible dans le code, reviewable en PR
    expect(result).toMatchInlineSnapshot(`
      {
        "displayTotal": "250,00 €",
        "label": "FAC-2026-001 — Jean Dupont",
        "statusBadge": "Payée",
      }
    `);
  });
});
```

```python
# tests/unit/test_schemas_snapshot.py
"""Snapshot tests pour les schémas Pydantic — détecter les breaking changes API."""
import json
import pytest
from pathlib import Path
from app.schemas.invoice import InvoiceResponse

SNAPSHOTS_DIR = Path(__file__).parent / "__snapshots__"


def test_invoice_response_schema_snapshot():
    """Détecte toute modification breaking du schéma InvoiceResponse."""
    schema = InvoiceResponse.model_json_schema()
    snapshot_file = SNAPSHOTS_DIR / "invoice_response_schema.json"

    if not snapshot_file.exists():
        # Première exécution : créer le snapshot
        SNAPSHOTS_DIR.mkdir(exist_ok=True)
        snapshot_file.write_text(json.dumps(schema, indent=2, sort_keys=True))
        pytest.skip("Snapshot created, re-run to validate")

    expected = json.loads(snapshot_file.read_text())

    # Vérifier les champs obligatoires (required) n'ont pas changé silencieusement
    assert schema.get("required", []) == expected.get("required", []), \
        f"Breaking change: required fields changed.\n" \
        f"Was: {expected.get('required')}\n" \
        f"Now: {schema.get('required')}"
```

---

### 27.2 Property-Based Testing avec Hypothesis

**Compléter la section déjà documentée** avec les stratégies composite :

```python
# tests/property/test_business_rules_hypothesis.py
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant

# ── Machine à états pour le cycle de vie d'une réservation ──
class ReservationLifecycleMachine(RuleBasedStateMachine):
    """Vérifie que les transitions d'état sont toujours cohérentes."""

    def __init__(self):
        super().__init__()
        self.status = "draft"
        self.deposit_paid = False
        self.total_cents = 0

    @initialize(total=st.integers(min_value=5000, max_value=5_000_000))
    def create_reservation(self, total):
        self.total_cents = total

    @rule()
    def confirm(self):
        if self.status == "draft":
            self.status = "confirmed"

    @rule()
    def pay_deposit(self):
        if self.status == "confirmed":
            self.deposit_paid = True

    @rule()
    def cancel(self):
        if self.status in ("draft", "confirmed"):
            self.status = "cancelled"

    @invariant()
    def deposit_only_when_confirmed(self):
        """Une caution ne peut être payée que si la réservation est confirmée."""
        if self.deposit_paid:
            assert self.status in ("confirmed", "completed"), \
                f"Invariant violated: deposit_paid=True but status={self.status}"

    @invariant()
    def cancelled_not_paid(self):
        """Une réservation annulée ne peut pas avoir une caution payée."""
        if self.status == "cancelled":
            assert not self.deposit_paid, \
                "Invariant violated: cancelled reservation has deposit_paid=True"


TestReservationLifecycle = ReservationLifecycleMachine.TestCase
TestReservationLifecycle.settings = settings(
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
)
```

---

## Section 28 — Patterns GraphQL & Temps Réel (Décision)

### 28.1 Décision : REST vs GraphQL vs gRPC

**Décision actée pour CaroCorp** :

| Couche | Protocole | Justification |
|--------|-----------|---------------|
| API publique (frontend) | **REST + JSON** | Outillage mature, équipe familière, CORS simple |
| Inter-services futurs (microservices) | **gRPC interne** | Performance, contrats stricts via protobuf |
| Real-time (notifications, live updates) | **SSE (Server-Sent Events)** | Unidirectionnel suffit, pas besoin de WebSocket bidirectionnel |
| Analytique complexe (futurs besoins) | **GraphQL** sous-couche séparée | Pas maintenant — documenter pour V2 si besoin |

### 28.2 Server-Sent Events — Pattern Standard

```python
# app/api/v1/endpoints/notifications.py
import asyncio
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter()


async def event_generator(tenant_id: int, user_id: int):
    """Génère des événements SSE pour un utilisateur connecté."""
    # Connexion au canal Redis PubSub de ce tenant
    import redis.asyncio as redis_async
    r = redis_async.from_url("redis://redis:6379")
    pubsub = r.pubsub()
    await pubsub.subscribe(f"tenant:{tenant_id}:user:{user_id}")

    try:
        # Heartbeat pour maintenir la connexion (évite timeout proxy)
        heartbeat_interval = 30
        last_heartbeat = asyncio.get_event_loop().time()

        async for message in pubsub.listen():
            now = asyncio.get_event_loop().time()

            # Heartbeat si pas de message depuis 30s
            if now - last_heartbeat > heartbeat_interval:
                yield "event: heartbeat\ndata: {}\n\n"
                last_heartbeat = now

            if message["type"] == "message":
                data = message["data"].decode()
                yield f"data: {data}\n\n"
                last_heartbeat = now
    finally:
        await pubsub.unsubscribe()
        await r.aclose()


@router.get("/notifications/stream")
async def stream_notifications(
    current_user: User = Depends(get_current_user),
):
    """SSE endpoint — connexion persistante pour notifications temps réel."""
    return StreamingResponse(
        event_generator(current_user.tenant_id, current_user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Désactive le buffering nginx
            "Connection": "keep-alive",
        },
    )
```

**Client React** :
```typescript
// frontend/src/hooks/useNotifications.ts
import { useEffect, useRef } from 'react';
import { useAuthStore } from '../stores/authStore';

interface Notification {
  type: 'reservation_confirmed' | 'payment_received' | 'stock_alert';
  payload: Record<string, unknown>;
}

export function useNotifications(onNotification: (n: Notification) => void) {
  const { token } = useAuthStore();
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!token) return;

    const es = new EventSource(
      `/api/v1/notifications/stream`,
      { withCredentials: true }
    );

    es.onmessage = (e) => {
      try {
        const notification = JSON.parse(e.data) as Notification;
        onNotification(notification);
      } catch { /* ignore malformed events */ }
    };

    es.onerror = () => {
      // Reconnexion automatique gérée par le navigateur (SSE standard)
      // Backoff personnalisé si nécessaire
      es.close();
    };

    eventSourceRef.current = es;
    return () => es.close();
  }, [token]);
}
```

---

### 28.3 WebSockets — Quand utiliser vs SSE

```
Decision tree :
  Besoin unidirectionnel (serveur → client) ?
    → SSE (plus simple, HTTP/2 multiplexé, pas de lib spéciale)
  Besoin bidirectionnel (chat, collaboration temps réel) ?
    → WebSocket avec FastAPI WebSocket + Redis PubSub
  Besoin très haute fréquence (trading, gaming) ?
    → WebSocket avec binary framing (MessagePack)
```

```python
# app/api/v1/endpoints/ws.py — Pattern WebSocket avec auth
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.core.token import decode_access_token

router = APIRouter()


@router.websocket("/ws/collaboration/{document_id}")
async def websocket_collaboration(
    websocket: WebSocket,
    document_id: int,
    token: str = Query(...),  # Token JWT en query param (WS ne supporte pas les headers)
):
    # Valider le token avant d'accepter la connexion
    try:
        claims = decode_access_token(token)
        tenant_id = claims["tenant_id"]
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            # Broadcast aux autres connexions du même document/tenant
            # Utiliser un ConnectionManager avec un dict de connexions actives
    except WebSocketDisconnect:
        pass
```

---

## Section 29 — Patterns Git & CI/CD Avancés

### 29.1 Trunk-Based Development + Feature Flags

**Convention adoptée pour CaroCorp** : Trunk-Based Development (TBD) avec feature flags pour les features longues.

```
Règles :
1. Branche principale : `main` (seule branche longue durée)
2. Feature branches : max 2 jours de vie → merge obligatoire
3. Hotfix : branch depuis tag de production, merge en main + cherry-pick si nécessaire
4. Release : tags semver (v1.2.3) sur main, jamais de release branch
```

```bash
# Workflow quotidien
git checkout main && git pull --rebase
git checkout -b feat/invoice-pdf-export   # Feature courte < 2j
# ... travail ...
git push origin feat/invoice-pdf-export
# Ouvrir PR → review → merge squash → supprimer la branche

# Feature longue (> 2j) : utiliser feature flag
# 1. Créer le flag : POST /admin/feature-flags { key: "invoice_pdf_export", enabled: false }
# 2. Wrapper le code derrière le flag
# 3. Merger en main dès que le code compile (même si incomplet)
# 4. Activer le flag quand prêt
```

**Protection de branche** (`github/branch-protection.yml` ou config manuelle) :
```yaml
# .github/branch-protection.md (documenter la config attendue)
# main :
#   - Require PR review (min 1)
#   - Require status checks: test, lint, typecheck
#   - No direct push (sauf admin en urgence)
#   - Require up-to-date before merge
#   - Dismiss stale reviews on new push
```

---

### 29.2 GitHub Actions — Pipeline CI Complet

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true  # Annuler les runs obsolètes sur nouvelle push

jobs:
  # ── Backend ────────────────────────────────────────────
  backend-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with: { python-version: "3.12" }
      - run: uv run ruff check . && uv run ruff format --check .
      - run: uv run mypy app/ --ignore-missing-imports

  backend-test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env: { POSTGRES_DB: test_db, POSTGRES_USER: test, POSTGRES_PASSWORD: test }
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
    env:
      DATABASE_URL: postgresql+asyncpg://test:test@localhost/test_db
      REDIS_URL: redis://localhost:6379
      ENV: test
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv run pytest tests/ -v --tb=short --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v4
        with: { files: coverage.xml }

  # ── Frontend ───────────────────────────────────────────
  frontend-lint:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: frontend } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: npm, cache-dependency-path: frontend/package-lock.json }
      - run: npm ci
      - run: npm run lint && npm run typecheck

  frontend-test:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: frontend } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: npm, cache-dependency-path: frontend/package-lock.json }
      - run: npm ci
      - run: npm run test -- --coverage

  # ── Sécurité ───────────────────────────────────────────
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: fs
          scan-ref: .
          severity: CRITICAL,HIGH
          exit-code: 1
      - name: Python audit
        run: pip install pip-audit && pip-audit -r requirements.txt
      - name: NPM audit
        run: cd frontend && npm audit --audit-level=high

  # ── Build & Push (main only) ───────────────────────────
  build:
    needs: [backend-lint, backend-test, frontend-lint, frontend-test, security-scan]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          context: .
          target: runtime
          push: true
          tags: ghcr.io/${{ github.repository }}/api:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          provenance: true    # SBOM attestation
          sbom: true
```

---

### 29.3 ULID comme identifiants distribués

**Décision** : Conserver `BigInteger` auto-incrémenté comme PK interne (performance, index B-tree), mais introduire ULID comme identifiant public exposé dans les API et URLs.

**Avantages ULID** :
- Triable par temps (préfixe timestamp 48 bits) → pas de "hotspot" index
- Opaque pour les clients (pas d'énumération)
- Universellement unique sans coordination

```python
# app/models/mixins.py — Ajouter ULID comme external_id
import ulid
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class ULIDMixin:
    """
    Ajoute un external_id ULID exposable dans les API.
    La PK interne (BigInteger) reste pour les JOINs.
    """
    external_id: Mapped[str] = mapped_column(
        String(26),
        default=lambda: str(ulid.new()),
        unique=True,
        nullable=False,
        index=True,
    )


# Usage sur les modèles exposés publiquement
class Reservation(Base, TimestampMixin, SoftDeleteMixin, ULIDMixin):
    __tablename__ = "reservations"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # external_id = "01HXYZ..." — utilisé dans les URLs /api/reservations/01HXYZ
    # id = 42 — utilisé en interne pour les JOINs
```

```python
# Endpoint : accepter les deux formes
@router.get("/reservations/{reservation_ref}")
async def get_reservation(
    reservation_ref: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accepte l'external_id ULID ou l'id numérique (rétrocompatibilité)."""
    if reservation_ref.isdigit():
        reservation = await reservation_repo.get_by_id(db, int(reservation_ref), current_user.tenant_id)
    else:
        reservation = await reservation_repo.get_by_external_id(db, reservation_ref, current_user.tenant_id)
    if not reservation:
        raise NotFound("Reservation")
    return ReservationResponse.model_validate(reservation)
```

**Migration** :
```sql
-- Expand : ajouter external_id nullable
ALTER TABLE reservations ADD COLUMN external_id VARCHAR(26);
-- Backfill (batch processing)
-- Contract : NOT NULL + unique index
```

---

## Section 30 — Matrice Priorité Sections 25–29

| Ref | Pattern | Priorité | Effort |
|-----|---------|----------|--------|
| 25.1 | Docker multi-stage backend non-root | **P0** | 1j |
| 25.3 | DB SSL/TLS sslmode=require | **P0** | 0.5j |
| 29.2 | GitHub Actions CI complet | **P0** | 2j |
| 25.2 | Secrets Management (Vault/Doppler) | **P1** | 3j |
| 26.3 | Design Tokens CSS | **P1** | 1j |
| 28.2 | SSE Notifications temps réel | **P1** | 2j |
| 29.1 | Trunk-Based Dev + Feature Flags docs | **P1** | 0.5j |
| 29.3 | ULID external_id | **P1** | 2j |
| 26.1 | React.memo stratégie | **P2** | 1j |
| 26.2 | Zustand Immer middleware | **P2** | 0.5j |
| 25.4 | Blue/Green deployment | **P2** | 3j |
| 27.1 | Snapshot Testing | **P2** | 1j |
| 27.2 | Hypothesis StateMachine | **P2** | 1j |
| 28.3 | WebSockets bidirectionnel | **P3** | 3j |

---

## Section 31 — Observabilité Distribuée Avancée

### 31.1 Distributed Tracing — OpenTelemetry Propagation

**Problème actuel** : Les logs ont un `request_id` par service, mais aucune propagation `traceparent` entre services. Impossible de suivre une requête à travers API → Celery → worker.

**Convention** :

```python
# app/core/tracing.py
"""
OpenTelemetry distributed tracing avec propagation W3C Trace Context.
Corrèle automatiquement API → Celery → sous-services via traceparent header.
"""
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat
import os


def configure_tracing(app) -> None:
    """Initialise le tracing OTLP + instruments FastAPI/SQLAlchemy/Redis."""
    if os.getenv("OTEL_ENABLED", "false").lower() != "true":
        return

    provider = TracerProvider(
        resource=Resource.create({
            "service.name": "carocorp-api",
            "service.version": os.getenv("APP_VERSION", "dev"),
            "deployment.environment": os.getenv("ENV", "dev"),
        })
    )

    exporter = OTLPSpanExporter(
        endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://tempo:4317"),
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Propagation W3C Trace Context (traceparent header standard)
    set_global_textmap(B3MultiFormat())

    # Instruments automatiques
    FastAPIInstrumentor.instrument_app(app, excluded_urls="/health.*")
    SQLAlchemyInstrumentor().instrument(enable_commenter=True)
    RedisInstrumentor().instrument()


# app/middleware/correlation.py — Enrichir les logs avec le trace_id
from opentelemetry import trace as otel_trace
from starlette.middleware.base import BaseHTTPMiddleware

class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        span = otel_trace.get_current_span()
        trace_id = format(span.get_span_context().trace_id, '032x') if span else None

        # Injecter dans les ContextVars de logging (section existante)
        if trace_id:
            request.state.trace_id = trace_id

        response = await call_next(request)
        if trace_id:
            response.headers["X-Trace-Id"] = trace_id
        return response
```

**Propagation vers Celery** :
```python
# app/tasks/base.py — Propagation du contexte de trace dans les tasks Celery
from celery import Task
from opentelemetry import context, propagate

class InstrumentedTask(Task):
    """Task de base qui propage le contexte de tracing."""

    def apply_async(self, args=None, kwargs=None, **options):
        # Sérialiser le contexte de trace dans les headers de la task
        carrier = {}
        propagate.inject(carrier)
        kwargs = kwargs or {}
        kwargs["_otel_carrier"] = carrier
        return super().apply_async(args, kwargs, **options)

    def __call__(self, *args, **kwargs):
        carrier = kwargs.pop("_otel_carrier", {})
        ctx = propagate.extract(carrier)
        token = context.attach(ctx)
        try:
            return super().__call__(*args, **kwargs)
        finally:
            context.detach(token)
```

**docker-compose.yml** (Tempo + Grafana stack) :
```yaml
  tempo:
    image: grafana/tempo:latest
    command: ["-config.file=/etc/tempo.yaml"]
    volumes: ["./infra/tempo.yaml:/etc/tempo.yaml"]
    ports: ["3200:3200", "4317:4317"]

  grafana:
    image: grafana/grafana:latest
    environment:
      - GF_DATASOURCES_TEMPO_URL=http://tempo:3200
    ports: ["3000:3000"]
```

---

### 31.2 Slow Query Detection + EXPLAIN ANALYZE Automatique

**Convention** :

```python
# app/core/database.py — Slow query listener
import time
import logging
from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger("carocorp.slow_queries")

SLOW_QUERY_THRESHOLD_MS = float(os.getenv("SLOW_QUERY_THRESHOLD_MS", "500"))


@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info["query_start_time"] = time.monotonic()


@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    duration_ms = (time.monotonic() - conn.info.pop("query_start_time", 0)) * 1000

    if duration_ms > SLOW_QUERY_THRESHOLD_MS:
        logger.warning(
            "slow_query",
            extra={
                "duration_ms": round(duration_ms, 2),
                "statement": statement[:500],  # Tronquer pour éviter les logs géants
                "threshold_ms": SLOW_QUERY_THRESHOLD_MS,
            }
        )

        # En dev uniquement : EXPLAIN ANALYZE automatique
        if os.getenv("ENV") == "dev" and "SELECT" in statement.upper():
            try:
                # ⚠️ EXPLAIN ne peut pas réutiliser les paramètres du statement original.
                # On explique seulement le plan estimé (sans ANALYZE) pour éviter l'exécution réelle.
                from sqlalchemy import text as sa_text
                explain_result = conn.execute(
                    sa_text(f"EXPLAIN (FORMAT JSON) {statement}")
                ).fetchone()
                logger.debug(
                    "slow_query_explain",
                    extra={"plan": explain_result[0] if explain_result else None}
                )
            except Exception:
                pass  # Ne jamais faire crasher l'app pour un EXPLAIN
```

**Règle** : Seuil 500ms en prod, 200ms en staging. Toute query dépassant le seuil déclenche une alerte Sentry (breadcrumb).

---

### 31.3 Cache Invalidation par Tag

**Problème actuel** : Le cache Redis utilise uniquement des TTLs statiques. Une mise à jour d'un produit ne purge pas immédiatement les caches de listes qui l'incluent.

**Convention** :

```python
# app/core/cache_tags.py
"""
Cache invalidation par tag (tag-based cache busting).
Chaque entrée cache est associée à un ou plusieurs tags.
Invalider un tag invalide toutes les entrées associées.
"""
import json
from typing import Any, Optional
import redis.asyncio as aioredis

redis_client: aioredis.Redis = None  # Initialisé au démarrage


class TaggedCache:
    """Cache Redis avec invalidation par tags."""

    PREFIX = "cache:"
    TAG_PREFIX = "tag:"

    async def get(self, key: str) -> Optional[Any]:
        value = await redis_client.get(f"{self.PREFIX}{key}")
        return json.loads(value) if value else None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 300,
        tags: list[str] | None = None,
    ) -> None:
        pipe = redis_client.pipeline()
        pipe.setex(f"{self.PREFIX}{key}", ttl, json.dumps(value))

        # Associer la clé à chaque tag
        for tag in (tags or []):
            pipe.sadd(f"{self.TAG_PREFIX}{tag}", f"{self.PREFIX}{key}")
            pipe.expire(f"{self.TAG_PREFIX}{tag}", ttl + 60)  # Tag légèrement plus long

        await pipe.execute()

    async def invalidate_tag(self, tag: str) -> int:
        """Invalider toutes les clés associées à ce tag."""
        tag_key = f"{self.TAG_PREFIX}{tag}"
        keys = await redis_client.smembers(tag_key)

        if not keys:
            return 0

        pipe = redis_client.pipeline()
        pipe.delete(*keys)     # Supprimer toutes les entrées du tag
        pipe.delete(tag_key)   # Supprimer le tag lui-même
        await pipe.execute()
        return len(keys)

    async def invalidate_tenant(self, tenant_id: int) -> int:
        """Purge complète du cache pour un tenant (ex: opération admin)."""
        return await self.invalidate_tag(f"tenant:{tenant_id}")


tagged_cache = TaggedCache()


# Usage dans les services
class ProductService:
    async def get_products(self, tenant_id: int, filters: dict) -> list:
        import hashlib, json
        cache_key = f"products:{tenant_id}:{hashlib.md5(json.dumps(filters, sort_keys=True).encode()).hexdigest()}"
        # ⚠️ hash() Python n'est PAS déterministe entre process (PYTHONHASHSEED aléatoire).
        #    Toujours hashlib.md5() ou sha256() pour les cache keys.
        cached = await tagged_cache.get(cache_key)
        if cached:
            return cached

        products = await product_repo.list(...)
        await tagged_cache.set(
            cache_key,
            [p.model_dump() for p in products],
            ttl=300,
            tags=[f"tenant:{tenant_id}", f"products:{tenant_id}"],  # Tags sémantiques
        )
        return products

    async def update_product(self, tenant_id: int, product_id: int, data: dict):
        product = await product_repo.update(...)
        # Invalider tout le cache produits de ce tenant
        await tagged_cache.invalidate_tag(f"products:{tenant_id}")
        return product
```

---

## Section 32 — Patterns Frontend Avancés

### 32.1 Optimistic UI Updates avec Rollback

**Problème actuel** : Les mutations utilisent `onError` pour afficher une erreur, mais sans optimistic update — l'UI attend la réponse serveur avant de se mettre à jour, dégradant la réactivité perçue.

**Convention** :

```typescript
// frontend/src/hooks/useOptimisticMutation.ts
import { useMutation, useQueryClient } from '@tanstack/react-query';

interface OptimisticMutationOptions<TData, TVariables, TContext> {
  mutationFn: (variables: TVariables) => Promise<TData>;
  queryKey: unknown[];
  /** Applique la mise à jour optimiste sur les données existantes */
  updater: (old: TData[] | undefined, variables: TVariables) => TData[];
  onSuccess?: (data: TData) => void;
  onError?: (error: unknown) => void;
}

export function useOptimisticMutation<TData, TVariables>({
  mutationFn,
  queryKey,
  updater,
  onSuccess,
  onError,
}: OptimisticMutationOptions<TData, TVariables, { previousData: TData[] | undefined }>) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn,

    onMutate: async (variables) => {
      // 1. Annuler les requêtes en cours pour éviter l'écrasement
      await queryClient.cancelQueries({ queryKey });

      // 2. Snapshot des données actuelles (pour rollback)
      const previousData = queryClient.getQueryData<TData[]>(queryKey);

      // 3. Mise à jour optimiste immédiate
      queryClient.setQueryData(queryKey, updater(previousData, variables));

      // 4. Retourner le contexte de rollback
      return { previousData };
    },

    onError: (error, _variables, context) => {
      // Rollback en cas d'échec
      if (context?.previousData !== undefined) {
        queryClient.setQueryData(queryKey, context.previousData);
      }
      onError?.(error);
    },

    onSettled: () => {
      // Revalidation après succès ou échec pour synchroniser avec le serveur
      queryClient.invalidateQueries({ queryKey });
    },

    onSuccess,
  });
}

// Exemple d'usage — Toggle statut paiement
export function useMarkPaymentOptimistic(invoiceId: number) {
  return useOptimisticMutation({
    mutationFn: (paymentId: number) => invoicesApi.markPaymentReceived(paymentId),
    queryKey: ['invoice', invoiceId, 'payments'],
    updater: (old, paymentId) =>
      old?.map(p =>
        p.id === paymentId ? { ...p, status: 'received' as const } : p
      ) ?? [],
  });
}
```

---

### 32.2 Infinite Scroll avec useInfiniteQuery

**Convention** : Utiliser `useInfiniteQuery` pour les listes potentiellement longues (logs, historique, audit trail).

```typescript
// frontend/src/hooks/useInfiniteList.ts
import { useInfiniteQuery } from '@tanstack/react-query';
import { useRef, useEffect, useCallback } from 'react';

interface InfiniteListOptions<T> {
  queryKey: unknown[];
  fetchPage: (params: { page: number; pageSize: number }) => Promise<{
    items: T[];
    total: number;
    page: number;
  }>;
  pageSize?: number;
}

export function useInfiniteList<T>({
  queryKey,
  fetchPage,
  pageSize = 20,
}: InfiniteListOptions<T>) {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } =
    useInfiniteQuery({
      queryKey,
      queryFn: ({ pageParam = 1 }) => fetchPage({ page: pageParam as number, pageSize }),
      getNextPageParam: (lastPage) => {
        const loadedCount = lastPage.page * pageSize;
        return loadedCount < lastPage.total ? lastPage.page + 1 : undefined;
      },
      initialPageParam: 1,
    });

  const items = data?.pages.flatMap(p => p.items) ?? [];

  // Intersection Observer pour auto-fetch au scroll
  const sentinelRef = useRef<HTMLDivElement>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);

  const handleIntersect = useCallback(
    (entries: IntersectionObserverEntry[]) => {
      if (entries[0]?.isIntersecting && hasNextPage && !isFetchingNextPage) {
        fetchNextPage();
      }
    },
    [hasNextPage, isFetchingNextPage, fetchNextPage]
  );

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;

    observerRef.current = new IntersectionObserver(handleIntersect, {
      threshold: 0.1,
      rootMargin: '200px',  // Précharger 200px avant d'atteindre le bas
    });
    observerRef.current.observe(sentinel);
    return () => observerRef.current?.disconnect();
  }, [handleIntersect]);

  return { items, isLoading, isFetchingNextPage, hasNextPage, sentinelRef };
}

// Usage dans AuditLogsPage
function AuditLogsPage() {
  const { items: logs, isLoading, isFetchingNextPage, sentinelRef } =
    useInfiniteList({
      queryKey: ['audit-logs'],
      fetchPage: ({ page, pageSize }) =>
        auditApi.getLogs({ page, page_size: pageSize }),
      pageSize: 50,
    });

  return (
    <div>
      {logs.map(log => <AuditLogRow key={log.id} log={log} />)}
      {/* Sentinel invisible — déclenche le chargement de la page suivante */}
      <div ref={sentinelRef} className="h-4" />
      {isFetchingNextPage && <Spinner />}
    </div>
  );
}
```

---

### 32.3 Form Dirty State — Pattern Généralisé + Navigation Guard

**Problème actuel** : Seule `ProfilePage` utilise `isDirty`. Les modals de formulaire (EventFormModal, CustomerFormModal, etc.) n'avertissent pas l'utilisateur s'il ferme une modale avec des modifications non sauvegardées.

**Convention** :

```typescript
// frontend/src/hooks/useFormGuard.ts
import { useEffect } from 'react';
import { UseFormReturn } from 'react-hook-form';
import { useBlocker } from 'react-router-dom';

/**
 * Bloque la navigation et avertit si le formulaire a des modifications non sauvegardées.
 * Ajouter sur tout formulaire modal ou page avec données importantes.
 */
export function useFormGuard(form: UseFormReturn<any>, enabled = true) {
  const { formState: { isDirty, isSubmitting, isSubmitSuccessful } } = form;
  const shouldBlock = enabled && isDirty && !isSubmitting && !isSubmitSuccessful;

  // Bloquer la navigation React Router
  const blocker = useBlocker(shouldBlock);

  // Avertir sur rechargement / fermeture onglet (événement navigateur natif)
  useEffect(() => {
    if (!shouldBlock) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = '';  // Chrome exige cette ligne
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [shouldBlock]);

  // Confirmation si bloquer est activé
  useEffect(() => {
    if (blocker.state === 'blocked') {
      const confirmed = window.confirm(
        'Vous avez des modifications non sauvegardées. Quitter quand même ?'
      );
      if (confirmed) blocker.proceed();
      else blocker.reset();
    }
  }, [blocker]);

  return { isDirty: shouldBlock };
}

// Ajouter sur tous les formulaires modaux importants
function EventFormModal({ onClose }: { onClose: () => void }) {
  const form = useForm<EventFormData>({ resolver: zodResolver(eventSchema) });
  const { isDirty } = useFormGuard(form);

  const handleClose = () => {
    if (isDirty) {
      if (!confirm('Modifications non sauvegardées. Fermer ?')) return;
    }
    onClose();
  };
  // ...
}
```

---

### 32.4 Result Type — Gestion d'erreurs sans exceptions

**Convention** : Utiliser un type `Result<T, E>` pour les fonctions utilitaires pouvant échouer, évitant les try/catch imbriqués.

```typescript
// frontend/src/utils/result.ts
export type Ok<T> = { ok: true; value: T };
export type Err<E> = { ok: false; error: E };
export type Result<T, E = string> = Ok<T> | Err<E>;

export const Result = {
  ok: <T>(value: T): Ok<T> => ({ ok: true, value }),
  err: <E>(error: E): Err<E> => ({ ok: false, error }),

  /** Wraps une fonction pouvant throw en Result */
  try: <T>(fn: () => T): Result<T, Error> => {
    try {
      return Result.ok(fn());
    } catch (e) {
      return Result.err(e instanceof Error ? e : new Error(String(e)));
    }
  },

  /** Async variant */
  tryAsync: async <T>(fn: () => Promise<T>): Promise<Result<T, Error>> => {
    try {
      return Result.ok(await fn());
    } catch (e) {
      return Result.err(e instanceof Error ? e : new Error(String(e)));
    }
  },
};

// Usage
async function parseImportedCSV(file: File): Promise<Result<ReservationImport[]>> {
  const text = await Result.tryAsync(() => file.text());
  if (!text.ok) return Result.err(`Lecture fichier: ${text.error.message}`);

  const rows = Result.try(() => parseCSV(text.value));
  if (!rows.ok) return Result.err(`Parsing CSV: ${rows.error.message}`);

  return Result.ok(rows.value);
}

// Dans le composant
const result = await parseImportedCSV(file);
if (!result.ok) {
  toast.error(result.error);
  return;
}
// result.value est maintenant typé ReservationImport[]
```

**Backend Python** — équivalent :
```python
# app/core/result.py
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T
    ok: bool = True


@dataclass(frozen=True)
class Err(Generic[E]):
    error: E
    ok: bool = False


Result = Ok | Err  # Type union


# Usage dans les services utilitaires (parsing, validation complexe)
def parse_iban(raw: str) -> Ok[str] | Err[str]:
    raw = raw.replace(" ", "").upper()
    if len(raw) < 15 or len(raw) > 34:
        return Err("IBAN invalide : longueur incorrecte")
    if not raw[:2].isalpha() or not raw[2:4].isdigit():
        return Err("IBAN invalide : format incorrect")
    return Ok(raw)
```

---

## Section 33 — PWA & Service Worker

### 33.1 Progressive Web App — Configuration Complète

**Problème actuel** : `manifest.json` présent mais sans Service Worker. L'app n'est pas installable et ne fonctionne pas hors-ligne.

**Convention** :

```typescript
// vite.config.ts — Ajouter vite-plugin-pwa
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      workbox: {
        // Précacher les assets statiques
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        // Stratégie réseau-first pour les API (données fraîches)
        runtimeCaching: [
          {
            urlPattern: /^\/api\/v1\//,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              expiration: { maxEntries: 100, maxAgeSeconds: 60 * 5 },  // 5min
              networkTimeoutSeconds: 10,
            },
          },
          // Cache-first pour les assets statiques (images produits)
          {
            urlPattern: /\.(png|jpg|jpeg|webp|svg)$/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'images-cache',
              expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 7 },  // 7j
            },
          },
        ],
      },
      manifest: {
        name: 'Marveline',
        short_name: 'Marveline',
        description: 'Gestion de location événementielle',
        theme_color: '#4f6ef7',
        background_color: '#0f172a',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icons/icon-512-maskable.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      // Afficher un prompt "Mettre à jour" quand nouvelle version disponible
      devOptions: { enabled: true },
    }),
  ],
});
```

**Composant de notification de mise à jour** :
```tsx
// frontend/src/components/ui/UpdatePrompt.tsx
import { useRegisterSW } from 'virtual:pwa-register/react';

export function UpdatePrompt() {
  const { needRefresh: [needRefresh], updateServiceWorker } = useRegisterSW();

  if (!needRefresh) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 bg-brand-600 text-white px-4 py-3 rounded-lg shadow-lg flex items-center gap-3">
      <span className="text-sm">Nouvelle version disponible</span>
      <button
        onClick={() => updateServiceWorker(true)}
        className="text-sm font-semibold underline"
      >
        Mettre à jour
      </button>
    </div>
  );
}
```

---

## Section 34 — Patterns Utilitaires Backend

### 34.1 Pipe/Compose — Transformations fonctionnelles

```python
# app/core/functional.py
"""Utilitaires fonctionnels : pipe, compose, memoize."""
from typing import TypeVar, Callable, Any
from functools import reduce, wraps, lru_cache

T = TypeVar("T")


def pipe(*fns: Callable) -> Callable:
    """
    Compose des fonctions de gauche à droite.
    pipe(f, g, h)(x) == h(g(f(x)))
    """
    return lambda x: reduce(lambda v, f: f(v), fns, x)


def compose(*fns: Callable) -> Callable:
    """
    Compose des fonctions de droite à gauche (ordre mathématique).
    compose(f, g, h)(x) == f(g(h(x)))
    """
    return pipe(*reversed(fns))


# Usage : pipeline de transformation de données
normalize_customer_name = pipe(
    str.strip,
    str.lower,
    lambda s: s.title(),
)

assert normalize_customer_name("  jean DUPONT  ") == "Jean Dupont"


# Pipeline de validation d'un montant
def validate_amount_cents(raw: Any) -> int:
    """Valide et normalise un montant en centimes."""
    pipeline = pipe(
        lambda v: int(v) if not isinstance(v, int) else v,
        lambda v: (_ for _ in ()).throw(ValueError("Montant négatif")) if v < 0 else v,
        lambda v: (_ for _ in ()).throw(ValueError("Montant trop élevé")) if v > 99_999_999 else v,
    )
    return pipeline(raw)
```

**Frontend** :
```typescript
// frontend/src/utils/pipe.ts
export const pipe = <T>(...fns: Array<(arg: T) => T>) =>
  (value: T): T => fns.reduce((acc, fn) => fn(acc), value);

export const compose = <T>(...fns: Array<(arg: T) => T>) =>
  pipe(...[...fns].reverse());

// Usage : normalisation données formulaire
const normalizePhone = pipe<string>(
  s => s.replace(/\s/g, ''),
  s => s.replace(/^0/, '+33'),
  s => s.replace(/[^+\d]/g, ''),
);
```

---

### 34.2 Stale-While-Revalidate Frontend

**Convention** : React Query implémente SWR nativement via `staleTime` + `gcTime`. Pattern à appliquer systématiquement sur les données de référence (produits, catégories, clients).

```typescript
// frontend/src/api/queryOptions.ts
import { queryOptions } from '@tanstack/react-query';
import { categoriesApi } from './categories';
import { productsApi } from './products';

/** Données de référence : fraîches 5min, en cache 30min */
export const categoriesQueryOptions = queryOptions({
  queryKey: ['categories'],
  queryFn: () => categoriesApi.getCategories({ limit: 1000 }),
  staleTime: 5 * 60 * 1000,   // 5 min — pas de refetch si données < 5min
  gcTime: 30 * 60 * 1000,     // 30 min — garder en cache (SWR)
  refetchOnWindowFocus: false, // Catégories changent rarement
});

/** Données transactionnelles : toujours revalider au focus */
export const reservationsQueryOptions = (filters: ReservationFilters) =>
  queryOptions({
    queryKey: ['reservations', filters],
    queryFn: () => reservationsApi.list(filters),
    staleTime: 30 * 1000,       // 30s — données business peuvent changer vite
    gcTime: 5 * 60 * 1000,
    refetchOnWindowFocus: true,  // Revalider quand l'utilisateur revient sur l'onglet
    refetchInterval: false,      // Pas de polling (utiliser SSE pour temps réel)
  });

/** Données critiques : jamais de cache (facturation) */
export const invoiceQueryOptions = (invoiceId: number) =>
  queryOptions({
    queryKey: ['invoice', invoiceId],
    queryFn: () => invoicesApi.get(invoiceId),
    staleTime: 0,                // Toujours considérée périmée
    gcTime: 60 * 1000,
    refetchOnMount: true,
    refetchOnWindowFocus: true,
  });
```

**Règle** : Toutes les requêtes `useQuery` doivent utiliser un `queryOptions` centralisé dans `api/queryOptions.ts` — jamais de `staleTime`/`gcTime` inline dans les composants.

---

## Section 35 — Matrice Priorité Sections 31–34

| Ref | Pattern | Priorité | Effort |
|-----|---------|----------|--------|
| 31.2 | Slow Query Detection auto | **P0** | 0.5j |
| 31.3 | Cache invalidation par tag | **P1** | 1j |
| 32.1 | Optimistic UI + rollback | **P1** | 1j |
| 32.3 | Form dirty state généralisé | **P1** | 1j |
| 34.2 | SWR queryOptions centralisés | **P1** | 0.5j |
| 31.1 | OpenTelemetry distributed tracing | **P1** | 2j |
| 32.4 | Result type TS + Python | **P2** | 0.5j |
| 32.2 | Infinite scroll useInfiniteQuery | **P2** | 1j |
| 33.1 | PWA + Service Worker | **P2** | 2j |
| 34.1 | Pipe/compose utilities | **P3** | 0.5j |

---

## Section 36 — Event Sourcing (Décision + Pattern)

### 36.1 Quand adopter Event Sourcing

**Décision CaroCorp** : Event Sourcing complet (append-only event store) est **hors-scope pour la V1**. Raisons :
- Complexité opérationnelle élevée (projections, replays, snapshots)
- L'Outbox Pattern (section 18.1) couvre le besoin d'atomicité événements/DB
- L'Audit Log existant couvre le besoin de traçabilité

**Adopter Event Sourcing si** :
- Besoin de rejouer l'historique des états (ex: reconstituer l'état d'une réservation à une date donnée)
- Besoin de projections multiples depuis la même source de vérité
- Volume d'écriture >> lecture sur entités financières

**Pattern documenté pour V2** :

```python
# app/models/event_store.py
"""
Event Store append-only.
Jamais d'UPDATE ni DELETE sur cette table.
La vérité est dans les events, pas dans les projections.
"""
from sqlalchemy import BigInteger, String, JSON, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class StoredEvent(Base, TimestampMixin):
    __tablename__ = "event_store"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)  # "Reservation"
    aggregate_id: Mapped[str] = mapped_column(String(26), nullable=False)     # ULID
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)         # Version optimiste
    event_type: Mapped[str] = mapped_column(String(200), nullable=False)      # "ReservationConfirmed"
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # causation_id, correlation_id

    __table_args__ = (
        # Optimistic concurrency : interdire deux events avec le même sequence sur le même aggregate
        UniqueConstraint("aggregate_type", "aggregate_id", "sequence",
                         name="uq_event_store_aggregate_sequence"),
        Index("ix_event_store_tenant_aggregate", "tenant_id", "aggregate_type", "aggregate_id"),
        Index("ix_event_store_created_at", "created_at"),
    )


# app/core/event_sourcing.py
from dataclasses import dataclass, field
from typing import Any
import ulid

@dataclass
class DomainEvent:
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload: dict[str, Any]
    sequence: int
    causation_id: str | None = None   # ID de la commande qui a causé cet event
    correlation_id: str | None = None  # ID de trace bout-en-bout


class EventSourcedRepository:
    """Dépôt basé sur les events. Reconstruit l'état par replay."""

    async def append(
        self,
        db: AsyncSession,
        tenant_id: int,
        events: list[DomainEvent],
    ) -> None:
        """Appende des events atomiquement (compare-and-swap sur sequence)."""
        for event in events:
            stored = StoredEvent(
                tenant_id=tenant_id,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                sequence=event.sequence,
                event_type=event.event_type,
                payload=event.payload,
                metadata={
                    "causation_id": event.causation_id,
                    "correlation_id": event.correlation_id,
                },
            )
            db.add(stored)
        # L'UniqueConstraint sur (aggregate_type, aggregate_id, sequence)
        # protège contre les écritures concurrentes (optimistic locking natif)
        await db.flush()

    async def load(
        self,
        db: AsyncSession,
        tenant_id: int,
        aggregate_type: str,
        aggregate_id: str,
    ) -> list[DomainEvent]:
        """Charge tous les events d'un aggregate, dans l'ordre."""
        result = await db.execute(
            select(StoredEvent)
            .where(
                StoredEvent.tenant_id == tenant_id,
                StoredEvent.aggregate_type == aggregate_type,
                StoredEvent.aggregate_id == aggregate_id,
            )
            .order_by(StoredEvent.sequence)
        )
        return result.scalars().all()
```

**Snapshot pattern** (éviter replay complet sur aggregates longs) :
```python
# Tous les N events, sauvegarder un snapshot de l'état
SNAPSHOT_EVERY_N = 50

async def get_aggregate_with_snapshot(db, aggregate_id: str):
    snapshot = await load_snapshot(db, aggregate_id)
    if snapshot:
        events = await load_events_after(db, aggregate_id, snapshot.sequence)
        return replay(snapshot.state, events)
    else:
        events = await load_all_events(db, aggregate_id)
        return replay({}, events)
```

---

## Section 37 — Sécurité Expert

### 37.1 CSP Nonce Dynamique

**Problème actuel** : La CSP statique `script-src 'self'` bloque les scripts inline mais ne peut pas whitelister des scripts inline légitimes sans `'unsafe-inline'` (qui annule la protection).

**Convention** : Nonce cryptographique par requête, injecté dans les headers ET dans le HTML.

```python
# app/middleware/csp_nonce.py
import base64
import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class CSPNonceMiddleware(BaseHTTPMiddleware):
    """
    Génère un nonce cryptographique par requête.
    L'injecte dans le header CSP et le rend disponible pour le HTML.
    """

    def __init__(self, app: ASGIApp, report_only: bool = False):
        super().__init__(app)
        self._report_only = report_only
        self._header = "Content-Security-Policy-Report-Only" if report_only else "Content-Security-Policy"

    async def dispatch(self, request, call_next):
        nonce = base64.b64encode(os.urandom(16)).decode("ascii")
        request.state.csp_nonce = nonce

        response = await call_next(request)

        csp = (
            f"default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            f"style-src 'self' 'nonce-{nonce}'; "
            f"img-src 'self' data: blob: https:; "
            f"font-src 'self'; "
            f"connect-src 'self' ws: wss:; "
            f"frame-ancestors 'none'; "
            f"base-uri 'self'; "
            f"form-action 'self'; "
            f"upgrade-insecure-requests; "
            f"report-uri /api/v1/security/csp-report"
        )
        response.headers[self._header] = csp
        return response
```

```nginx
# frontend/nginx.conf — Pour le frontend SPA, utiliser sub_filter pour injecter le nonce
# Note : le nonce est généré par l'API, pas nginx (SPA = pas de SSR)
# Solution alternative : hash SHA256 des scripts inline connus
add_header Content-Security-Policy
  "default-src 'self';
   script-src 'self' 'sha256-{HASH_DU_SCRIPT_VITE_RUNTIME}';
   style-src 'self' 'unsafe-inline';
   img-src 'self' data: blob:;
   connect-src 'self' ws://localhost:* wss://localhost:*;"
  always;
```

**Endpoint de rapport CSP** :
```python
@router.post("/security/csp-report", status_code=204)
async def csp_report(request: Request):
    """Reçoit et logue les violations CSP du navigateur."""
    body = await request.json()
    logger.warning("csp_violation", extra={"report": body.get("csp-report", {})})
```

---

### 37.2 mTLS Inter-Services

**Quand adopter** : dès que le projet passe en microservices (API + worker Celery + service tiers interne). Actuellement non nécessaire (mono-container), mais documenter pour la migration.

```yaml
# docker-compose.prod.yml — mTLS avec certificats auto-signés
services:
  api:
    environment:
      - SSL_CERT_FILE=/certs/api.crt
      - SSL_KEY_FILE=/certs/api.key
      - CA_CERT_FILE=/certs/ca.crt
    volumes:
      - ./certs:/certs:ro   # Certificats en read-only

  celery-worker:
    environment:
      - SSL_CERT_FILE=/certs/worker.crt
      - SSL_KEY_FILE=/certs/worker.key
      - CA_CERT_FILE=/certs/ca.crt
    volumes:
      - ./certs:/certs:ro
```

```python
# app/core/http_client.py — Client HTTP interne avec mTLS
import httpx
import os
import ssl

def get_internal_client() -> httpx.AsyncClient:
    """Client HTTP pour appels inter-services avec mTLS."""
    # create_default_context() sans cafile= charge les CAs système.
    # On charge ensuite la CA custom pour inter-services (auto-signée).
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.load_verify_locations(cafile=os.getenv("CA_CERT_FILE"))  # CA custom
    ssl_ctx.load_cert_chain(
        certfile=os.getenv("SSL_CERT_FILE"),
        keyfile=os.getenv("SSL_KEY_FILE"),
    )
    ssl_ctx.verify_mode = ssl.CERT_REQUIRED

    return httpx.AsyncClient(
        verify=ssl_ctx,
        timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )
```

**Génération certificats** (script ops) :
```bash
#!/usr/bin/env bash
# scripts/ops/gen_mtls_certs.sh
set -euo pipefail
mkdir -p certs

# CA
openssl genrsa -out certs/ca.key 4096
openssl req -new -x509 -days 3650 -key certs/ca.key -out certs/ca.crt \
  -subj "/CN=CaroCorp Internal CA"

# Service cert (remplacer SERVICE_NAME par api, worker, etc.)
for SERVICE in api worker; do
  openssl genrsa -out "certs/${SERVICE}.key" 2048
  openssl req -new -key "certs/${SERVICE}.key" -out "certs/${SERVICE}.csr" \
    -subj "/CN=${SERVICE}.carocorp.internal"
  openssl x509 -req -days 365 -in "certs/${SERVICE}.csr" \
    -CA certs/ca.crt -CAkey certs/ca.key -CAcreateserial \
    -out "certs/${SERVICE}.crt"
done
echo "Certificats générés dans ./certs/"
```

---

### 37.3 Chaos Engineering — Fault Injection en Tests

**Convention** : Pas besoin d'outils externes (Chaos Monkey). Implémenter fault injection native dans les tests d'intégration.

```python
# tests/utils/fault_injection.py
"""
Fault injection pour tests de résilience.
Simule les défaillances de services externes sans infrastructure.
"""
import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch
from typing import AsyncGenerator


@asynccontextmanager
async def redis_unavailable() -> AsyncGenerator[None, None]:
    """Simule Redis indisponible pendant le contexte."""
    with patch("redis.asyncio.Redis.get", side_effect=ConnectionError("Redis down")):
        with patch("redis.asyncio.Redis.set", side_effect=ConnectionError("Redis down")):
            yield


@asynccontextmanager
async def database_slow(delay_seconds: float = 2.0) -> AsyncGenerator[None, None]:
    """Simule une base de données lente (> timeout configuré)."""
    original_execute = AsyncSession.execute

    async def slow_execute(self, *args, **kwargs):
        await asyncio.sleep(delay_seconds)
        return await original_execute(self, *args, **kwargs)

    with patch.object(AsyncSession, "execute", slow_execute):
        yield


@asynccontextmanager
async def network_partition(service: str) -> AsyncGenerator[None, None]:
    """Simule une partition réseau vers un service externe."""
    with patch(f"app.services.{service}.httpx.AsyncClient.get",
               side_effect=httpx.ConnectTimeout("Network partition")):
        yield


# Usage dans les tests
@pytest.mark.asyncio
async def test_cache_miss_graceful_fallback(client, db):
    """L'API doit fonctionner (avec dégradation) si Redis est down."""
    async with redis_unavailable():
        response = await client.get("/api/v1/products")
        # Doit répondre 200 (fallback DB), pas 500
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_slow_query_timeout_returns_503(client, db):
    """Une requête trop lente doit retourner 503, pas bloquer."""
    async with database_slow(delay_seconds=35.0):  # > statement_timeout 30s
        response = await client.get("/api/v1/reservations")
        assert response.status_code in (503, 504)
```

---

## Section 38 — Composants UI & Design System

### 38.1 Storybook — Documentation Composants

**Convention** : Storybook est **optionnel en V1** mais recommandé dès que l'équipe frontend > 2 personnes ou que des composants UI sont partagés.

```bash
# Installation
cd frontend
npx storybook@latest init --type react
```

```typescript
// frontend/src/components/ui/Button/Button.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';
import { Button } from './Button';

const meta: Meta<typeof Button> = {
  title: 'UI/Button',
  component: Button,
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component: 'Bouton principal Marveline. Utiliser `variant` pour le style, `size` pour la taille.',
      },
    },
  },
  argTypes: {
    variant: {
      control: 'select',
      options: ['primary', 'secondary', 'danger', 'ghost'],
    },
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
    },
    disabled: { control: 'boolean' },
    loading: { control: 'boolean' },
  },
};

export default meta;
type Story = StoryObj<typeof Button>;

export const Primary: Story = {
  args: { children: 'Confirmer', variant: 'primary', size: 'md' },
};

export const Danger: Story = {
  args: { children: 'Supprimer', variant: 'danger', size: 'md' },
};

export const Loading: Story = {
  args: { children: 'Enregistrement...', variant: 'primary', loading: true },
};

export const AllVariants: Story = {
  render: () => (
    <div className="flex gap-3 flex-wrap">
      {(['primary', 'secondary', 'danger', 'ghost'] as const).map(v => (
        <Button key={v} variant={v}>{v}</Button>
      ))}
    </div>
  ),
};
```

**Règle** : Tout nouveau composant `src/components/ui/` doit avoir sa Story correspondante avec au minimum : état par défaut, états spéciaux (loading, error, disabled), et test d'accessibilité.

**CI Storybook** :
```yaml
# .github/workflows/ci.yml — Ajouter
  storybook-build:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: frontend } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: npm, cache-dependency-path: frontend/package-lock.json }
      - run: npm ci && npm run build-storybook
      # Déployer sur Chromatic ou GitHub Pages pour review visuelle en PR
```

---

### 38.2 Command Pattern — Actions Réversibles

**Convention** : Pour les opérations batch ou les actions UX nécessitant un "Annuler" (ex: archivage massif, réorganisation), implémenter le Command Pattern.

```typescript
// frontend/src/utils/command.ts
export interface Command<T = void> {
  execute(): Promise<T>;
  undo(): Promise<void>;
  description: string;
}

export class CommandHistory {
  private _history: Command[] = [];
  private _pointer = -1;

  async execute(command: Command): Promise<void> {
    await command.execute();
    // Supprimer les commandes "futures" (après undo)
    this._history = this._history.slice(0, this._pointer + 1);
    this._history.push(command);
    this._pointer++;
  }

  async undo(): Promise<string | null> {
    if (this._pointer < 0) return null;
    const command = this._history[this._pointer];
    await command.undo();
    this._pointer--;
    return command.description;
  }

  async redo(): Promise<string | null> {
    if (this._pointer >= this._history.length - 1) return null;
    this._pointer++;
    const command = this._history[this._pointer];
    await command.execute();
    return command.description;
  }

  get canUndo() { return this._pointer >= 0; }
  get canRedo() { return this._pointer < this._history.length - 1; }
}

// Exemple : Command pour archiver une réservation
function createArchiveReservationCommand(
  reservationId: number,
  api: ReservationsApi
): Command {
  return {
    description: `Archivage réservation #${reservationId}`,
    execute: () => api.archive(reservationId),
    undo: () => api.unarchive(reservationId),
  };
}

// Hook Zustand pour l'historique global
const useCommandHistory = create<{
  history: CommandHistory;
  execute: (cmd: Command) => Promise<void>;
  undo: () => Promise<void>;
}>((set, get) => ({
  history: new CommandHistory(),
  execute: async (cmd) => { await get().history.execute(cmd); set({}); },
  undo: async () => { await get().history.undo(); set({}); },
}));
```

**Backend** — Idempotency pour supporter undo/redo :
```python
# Les endpoints archive/unarchive doivent être idempotents
# PUT /reservations/{id}/archive → 200 même si déjà archivé
# PUT /reservations/{id}/unarchive → 200 même si déjà actif
```

---

## Section 39 — gRPC Inter-Services (Décision + Pattern V2)

### 39.1 gRPC pour Communications Inter-Services

**Décision** : REST pour l'API publique frontend. gRPC pour les communications entre services internes (API → service de notification, API → service de facturation PDF, etc.) quand ils existent.

**Avantages gRPC vs REST interne** :
- Contrats stricts via protobuf (pas de dérive silencieuse)
- Performance 5-10x (binary, HTTP/2 multiplexé)
- Streaming bidirectionnel natif
- Code généré automatiquement (client + serveur)

```protobuf
// proto/notification.proto
syntax = "proto3";
package carocorp.v1;

service NotificationService {
  rpc SendReservationConfirmed (ReservationConfirmedRequest) returns (NotificationResponse);
  rpc StreamUserNotifications (StreamRequest) returns (stream Notification);
}

message ReservationConfirmedRequest {
  int64 tenant_id = 1;
  int64 reservation_id = 2;
  string customer_email = 3;
  string customer_name = 4;
  string event_date = 5;
}

message NotificationResponse {
  bool success = 1;
  string notification_id = 2;
}

message Notification {
  string type = 1;
  bytes payload = 2;  // JSON encodé
  int64 timestamp = 3;
}
```

```python
# Génération du code Python
# pip install grpcio-tools
# python -m grpc_tools.protoc -I proto --python_out=app/grpc --grpc_python_out=app/grpc proto/notification.proto

# app/grpc/notification_client.py
import grpc
from app.grpc import notification_pb2, notification_pb2_grpc
import os

_channel: grpc.aio.Channel | None = None

async def get_notification_channel() -> grpc.aio.Channel:
    global _channel
    if _channel is None:
        ssl_creds = grpc.ssl_channel_credentials(
            root_certificates=open(os.getenv("CA_CERT_FILE"), "rb").read(),
            private_key=open(os.getenv("SSL_KEY_FILE"), "rb").read(),
            certificate_chain=open(os.getenv("SSL_CERT_FILE"), "rb").read(),
        )
        _channel = grpc.aio.secure_channel(
            os.getenv("NOTIFICATION_SERVICE_ADDR", "notification-svc:50051"),
            ssl_creds,
        )
    return _channel

async def send_reservation_confirmed(tenant_id: int, reservation_id: int, **kwargs):
    channel = await get_notification_channel()
    stub = notification_pb2_grpc.NotificationServiceStub(channel)
    response = await stub.SendReservationConfirmed(
        notification_pb2.ReservationConfirmedRequest(
            tenant_id=tenant_id,
            reservation_id=reservation_id,
            **kwargs,
        ),
        timeout=5.0,  # Timeout strict pour services internes
    )
    return response
```

---

## Section 40 — Matrice Priorité Sections 36–39

| Ref | Pattern | Priorité | Effort |
|-----|---------|----------|--------|
| 37.1 | CSP Nonce dynamique | **P1** | 1j |
| 37.3 | Chaos Engineering fault injection | **P1** | 2j |
| 38.2 | Command Pattern actions réversibles | **P2** | 2j |
| 38.1 | Storybook composants UI | **P2** | 3j |
| 36.1 | Event Sourcing (V2) | **P3** | 5j |
| 37.2 | mTLS inter-services | **P3** | 2j |
| 39.1 | gRPC inter-services | **P3** | 5j |

---

## Section 41 — Rate Limiting Distribué Avancé

### 41.1 Sliding Window Cross-Instance avec Script Lua

**Problème actuel** : Le rate limiting utilise `INCR + TTL` Redis — non atomique sur les edge cases (INCR puis crash avant TTL → compteur immortel). En multi-instance, chaque pod lit/écrit indépendamment, exposant à des race conditions.

**Convention** : Script Lua exécuté atomiquement côté Redis (garantie strong consistency).

```python
# app/core/rate_limiter_advanced.py
"""
Sliding window rate limiter distribué via script Lua Redis.
Atomique, correct en multi-instance, sans race condition.
"""
import time
import hashlib
import redis.asyncio as aioredis
from fastapi import HTTPException, Request

# Script Lua : sliding window exact
# Supprime les entrées hors fenêtre, ajoute la nouvelle, compte le total
_SLIDING_WINDOW_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local request_id = ARGV[4]

-- Supprimer les entrées expirées (hors fenêtre glissante)
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

-- Compter les requêtes actuelles dans la fenêtre
local count = redis.call('ZCARD', key)

if count >= limit then
    -- Retourner le temps avant reset (TTL de l'entrée la plus ancienne)
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    if #oldest > 0 then
        return {0, tonumber(oldest[2]) + window - now}
    end
    return {0, window}
end

-- Ajouter la requête courante avec score = timestamp
redis.call('ZADD', key, now, request_id)
redis.call('EXPIRE', key, window)
return {1, limit - count - 1}
"""

# SHA1 du script (pour EVALSHA — évite de retransmettre le script à chaque appel)
_SCRIPT_SHA = hashlib.sha1(_SLIDING_WINDOW_SCRIPT.encode()).hexdigest()


class DistributedRateLimiter:
    def __init__(self, redis: aioredis.Redis):
        self._redis = redis
        self._script_loaded = False

    async def _ensure_script_loaded(self):
        if not self._script_loaded:
            await self._redis.script_load(_SLIDING_WINDOW_SCRIPT)
            self._script_loaded = True

    async def check(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """
        Vérifie le rate limit.
        Retourne (allowed: bool, remaining: int).
        En cas de Redis down : fail-open (autoriser, logguer).
        """
        await self._ensure_script_loaded()
        now_ms = int(time.time() * 1000)
        request_id = f"{now_ms}-{id(self)}"  # Unique par requête

        try:
            result = await self._redis.evalsha(
                _SCRIPT_SHA,
                1,            # nombre de KEYS
                key,          # KEYS[1]
                now_ms,       # ARGV[1] — timestamp courant en ms
                window_seconds * 1000,  # ARGV[2] — fenêtre en ms
                limit,        # ARGV[3]
                request_id,   # ARGV[4]
            )
            allowed, remaining_or_retry_after = result
            return bool(allowed), int(remaining_or_retry_after)

        except aioredis.NoScriptError:
            # Le script a été évincé du cache Redis (SCRIPT FLUSH ou restart)
            self._script_loaded = False
            return await self.check(key, limit, window_seconds)

        except Exception as exc:
            # Fail-open : Redis indisponible → autoriser la requête
            import logging
            logging.getLogger("carocorp.rate_limit").error(
                "rate_limit_redis_error", extra={"error": str(exc)}
            )
            return True, limit


# Matrice de limits par endpoint (centraliser dans constants)
RATE_LIMIT_MATRIX = {
    "login":             {"limit": 5,    "window": 60},    # 5/min par IP
    "api_mutation":      {"limit": 100,  "window": 60},    # 100/min par user
    "api_read":          {"limit": 300,  "window": 60},    # 300/min par user
    "api_bulk":          {"limit": 10,   "window": 60},    # 10/min (opérations lourdes)
    "tenant_global":     {"limit": 5000, "window": 60},    # 5000/min par tenant (burst)
    "export":            {"limit": 5,    "window": 3600},  # 5 exports/heure
}


# Dépendance FastAPI
def rate_limit(rule: str):
    async def dependency(request: Request):
        config = RATE_LIMIT_MATRIX[rule]
        limiter: DistributedRateLimiter = request.app.state.rate_limiter

        # Clé : tenant + user + endpoint (isolation multi-tenant)
        tenant_id = getattr(request.state, "tenant_id", "anon")
        user_id = getattr(request.state, "user_id", request.client.host)
        key = f"rl:{rule}:t{tenant_id}:u{user_id}"

        allowed, remaining = await limiter.check(key, config["limit"], config["window"])

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Trop de requêtes. Réessayez dans quelques secondes.",
                headers={"Retry-After": str(remaining // 1000)},
            )

        # Exposer les headers de rate limit (bonne pratique API)
        request.state.rate_limit_remaining = remaining

    return dependency
```

---

### 41.2 Token Bucket — Pour le Burst Control

**Quand utiliser Token Bucket vs Sliding Window** :

| Cas | Algorithme | Raison |
|-----|-----------|--------|
| API générale (équité) | Sliding Window | Pas de burst, distribution uniforme |
| Export/génération PDF | Token Bucket | Autoriser un burst initial puis throttle |
| Webhook delivery (outbound) | Token Bucket | Absorber les pics d'événements |
| Login bruteforce | Fixed Window | Simplicité + reset clair |

```python
# app/core/token_bucket.py
"""Token Bucket via Redis — permet le burst contrôlé."""

_TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])   -- tokens par seconde
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1]) or capacity
local last_refill = tonumber(bucket[2]) or now

-- Remplir le bucket en fonction du temps écoulé
local elapsed = math.max(0, now - last_refill)
local new_tokens = math.min(capacity, tokens + elapsed * refill_rate)

if new_tokens < requested then
    -- Pas assez de tokens — calculer le délai d'attente
    local wait_seconds = (requested - new_tokens) / refill_rate
    redis.call('HSET', key, 'tokens', new_tokens, 'last_refill', now)
    redis.call('EXPIRE', key, math.ceil(capacity / refill_rate) + 10)
    return {0, math.ceil(wait_seconds * 1000)}  -- ms
end

-- Consommer les tokens
redis.call('HSET', key, 'tokens', new_tokens - requested, 'last_refill', now)
redis.call('EXPIRE', key, math.ceil(capacity / refill_rate) + 10)
return {1, math.floor(new_tokens - requested)}
"""
```

---

## Section 42 — API Design Avancé

### 42.1 Sparse Fieldsets — ?fields= Whitelist

**Problème actuel** : Les endpoints retournent toujours tous les champs. Un `GET /reservations` retourne 30 champs quand le frontend n'a besoin que de 5 pour une liste.

**Convention** :

```python
# app/core/sparse_fields.py
"""
Sparse fieldsets : ?fields=id,reference,status,customer_name
Réduit la taille des réponses et le travail de sérialisation.
"""
from typing import Any
from fastapi import Query
from pydantic import BaseModel


def sparse_response(data: BaseModel | list[BaseModel], fields: str | None) -> dict | list[dict]:
    """Filtre les champs d'une réponse Pydantic selon la whitelist ?fields=."""
    if not fields:
        return data.model_dump() if isinstance(data, BaseModel) else [d.model_dump() for d in data]

    allowed = {f.strip() for f in fields.split(",")}

    def filter_dict(d: dict) -> dict:
        return {k: v for k, v in d.items() if k in allowed}

    if isinstance(data, list):
        return [filter_dict(d.model_dump()) for d in data]
    return filter_dict(data.model_dump())


# Dépendance réutilisable
def fields_param(fields: str | None = Query(
    default=None,
    description="Champs à retourner, séparés par virgule. Ex: id,reference,status",
    example="id,reference,status,customer_name",
)) -> str | None:
    return fields


# Usage dans un endpoint
@router.get("/reservations")
async def list_reservations(
    fields: str | None = Depends(fields_param),
    # ... autres params
):
    reservations = await reservation_service.list(...)
    return sparse_response(reservations, fields)
```

**Frontend — utilisation** :
```typescript
// Listes : ne charger que les champs nécessaires à l'affichage
const { data } = useQuery({
  queryKey: ['reservations', 'list', filters],
  queryFn: () => reservationsApi.list({
    ...filters,
    fields: 'id,reference,status,customer_name,start_date,end_date,total_cents',
  }),
});

// Détail : charger tous les champs
const { data: detail } = useQuery({
  queryKey: ['reservation', id],
  queryFn: () => reservationsApi.get(id),  // Pas de ?fields= → tout
});
```

---

### 42.2 Contract-First API Design

**Problème actuel** : Le projet est code-first (FastAPI génère l'OpenAPI). Les changements breaking ne sont pas détectés avant que le frontend soit cassé.

**Convention** :

```bash
# Workflow contract-first :
# 1. Modifier docs/openapi.yaml (vérité contractuelle)
# 2. Valider le contrat
# 3. Générer les types TypeScript
# 4. Implémenter le backend
```

```yaml
# docs/openapi.yaml — Source de vérité (versionnée dans git)
openapi: "3.1.0"
info:
  title: Marveline API
  version: "1.0.0"
paths:
  /reservations:
    get:
      operationId: listReservations
      parameters:
        - name: fields
          in: query
          schema: { type: string }
      responses:
        "200":
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ReservationListResponse'
```

```python
# CI : vérifier que le contrat committé correspond à l'implémentation
# Makefile
contract-check:
    docker compose run --rm api python -m pytest tests/contract/ -v

# tests/contract/test_openapi_contract.py
import json
import yaml
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

def test_openapi_schema_matches_committed_contract():
    """Détecte les breaking changes entre l'implémentation et le contrat committé."""
    committed = yaml.safe_load(Path("docs/openapi.yaml").read_text())
    generated = json.loads(TestClient(app).get("/openapi.json").text)

    # Comparer les endpoints critiques
    for path, methods in committed["paths"].items():
        assert path in generated["paths"], f"Endpoint {path} manquant dans l'implémentation"
        for method, spec in methods.items():
            assert method in generated["paths"][path], \
                f"Méthode {method.upper()} {path} manquante"
```

**Génération types frontend depuis le contrat** :
```bash
# package.json
"generate:api": "openapi-typescript docs/openapi.yaml --output frontend/src/types/api.generated.ts"
# → Types TypeScript auto-générés depuis le contrat YAML
# → Erreur TypeScript si le frontend utilise un champ qui n'existe plus dans le contrat
```

---

### 42.3 API Versioning Strategy — Coexistence v1/v2

**Convention** :

```python
# app/api/router.py — Routing multi-version avec deprecation
from fastapi import FastAPI, APIRouter
from app.api.v1 import router as v1_router
# from app.api.v2 import router as v2_router  # À venir


def setup_versioned_routes(app: FastAPI) -> None:
    # v1 : toujours disponible (backward compat)
    app.include_router(v1_router, prefix="/api/v1", tags=["v1"])

    # v2 : quand disponible
    # app.include_router(v2_router, prefix="/api/v2", tags=["v2"])

    # Route non versionnée → redirige vers la dernière version stable
    # app.include_router(v2_router, prefix="/api", tags=["latest"])


# Middleware de deprecation : ajouter des headers sur les endpoints v1 dépréciés
class DeprecationMiddleware:
    """Ajoute Deprecation/Sunset headers sur les routes v1 qui ont un équivalent v2."""

    DEPRECATED_PATHS = {
        "/api/v1/reservations": "2027-01-01",  # Remplacé par /api/v2/reservations
    }

    async def __call__(self, request, call_next):
        response = await call_next(request)
        sunset_date = self.DEPRECATED_PATHS.get(request.url.path)
        if sunset_date:
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = sunset_date
            response.headers["Link"] = (
                f'<{request.url.path.replace("/v1/", "/v2/")}>;rel="successor-version"'
            )
        return response
```

**Stratégie de migration v1→v2** :
1. **Expand** : Ajouter les nouveaux champs dans v1 (optionnels, backward compat)
2. **Contract** : Créer v2 avec le nouveau schéma
3. **Deprecate** : Ajouter headers `Deprecation` + `Sunset` sur v1 (6 mois min)
4. **Remove** : Supprimer v1 après la date Sunset

---

## Section 43 — Accessibilité & Performance Monitoring

### 43.1 Accessibility Testing Automatisé (axe-playwright)

**Convention** : Tests d'accessibilité WCAG 2.1 AA intégrés dans la suite E2E Playwright.

```bash
npm install --save-dev @axe-core/playwright
```

```typescript
// frontend/tests/e2e/accessibility.spec.ts
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Accessibilité WCAG 2.1 AA', () => {
  test.beforeEach(async ({ page }) => {
    // Login standard E2E
    await page.goto('/login');
    await page.fill('[name=username]', 'admin@test.com');
    await page.fill('[name=password]', 'password');
    await page.click('button[type=submit]');
    await page.waitForURL('/dashboard');
  });

  const PAGES_TO_AUDIT = [
    { name: 'Dashboard', url: '/dashboard' },
    { name: 'Réservations', url: '/events' },
    { name: 'Clients', url: '/customers' },
    { name: 'Factures', url: '/invoices' },
    { name: 'Inventaire', url: '/inventory/stock' },
  ];

  for (const { name, url } of PAGES_TO_AUDIT) {
    test(`${name} — aucune violation critique`, async ({ page }) => {
      await page.goto(url);
      await page.waitForLoadState('networkidle');

      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
        .exclude('.recharts-wrapper')  // Exclure les graphiques (complexes à rendre accessibles)
        .analyze();

      // Formatter les violations pour un message d'erreur lisible
      const criticalViolations = results.violations.filter(
        v => ['critical', 'serious'].includes(v.impact ?? '')
      );

      expect(criticalViolations, formatViolations(criticalViolations)).toHaveLength(0);
    });
  }

  test('Navigation clavier — modals', async ({ page }) => {
    await page.goto('/events');
    await page.waitForLoadState('networkidle');

    // Ouvrir une modal via clavier
    const firstRow = page.locator('table tbody tr').first();
    await firstRow.focus();
    await page.keyboard.press('Enter');

    // Vérifier que le focus est piégé dans la modal
    const modal = page.locator('[role=dialog]');
    await expect(modal).toBeVisible();

    // Tab doit rester dans la modal
    await page.keyboard.press('Tab');
    const focusedElement = await page.evaluate(() => document.activeElement?.tagName);
    const isInsideModal = await modal.locator(':focus').count() > 0;
    expect(isInsideModal).toBe(true);

    // Escape doit fermer
    await page.keyboard.press('Escape');
    await expect(modal).not.toBeVisible();
  });
});

function formatViolations(violations: any[]) {
  return violations.map(v =>
    `\n[${v.impact}] ${v.id}: ${v.description}\n  Nodes: ${
      v.nodes.map((n: any) => n.html).join(', ')
    }`
  ).join('\n');
}
```

---

### 43.2 Lighthouse CI — Performance Budget

**Convention** :

```bash
npm install --save-dev @lhci/cli
```

```json
// frontend/.lighthouserc.json
{
  "ci": {
    "collect": {
      "url": [
        "http://localhost:4173/login",
        "http://localhost:4173/dashboard",
        "http://localhost:4173/events"
      ],
      "numberOfRuns": 3,
      "settings": {
        "preset": "desktop",
        "throttlingMethod": "simulate"
      }
    },
    "assert": {
      "preset": "lighthouse:recommended",
      "assertions": {
        "categories:performance": ["error", { "minScore": 0.85 }],
        "categories:accessibility": ["error", { "minScore": 0.90 }],
        "categories:best-practices": ["error", { "minScore": 0.90 }],
        "categories:seo": ["warn", { "minScore": 0.80 }],

        "first-contentful-paint": ["error", { "maxNumericValue": 2000 }],
        "largest-contentful-paint": ["error", { "maxNumericValue": 3500 }],
        "total-blocking-time": ["error", { "maxNumericValue": 300 }],
        "cumulative-layout-shift": ["error", { "maxNumericValue": 0.1 }],
        "speed-index": ["warn", { "maxNumericValue": 3000 }],

        "uses-optimized-images": "warn",
        "uses-text-compression": "error",
        "uses-long-cache-ttl": "warn",
        "no-unused-javascript": ["warn", { "maxLength": 0 }]
      }
    },
    "upload": {
      "target": "temporary-public-storage"
    }
  }
}
```

```yaml
# .github/workflows/ci.yml — Ajouter le job Lighthouse
  lighthouse:
    needs: [frontend-test]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - run: npm ci --prefix frontend
      - run: npm run build --prefix frontend
      - name: Serve built app
        run: npx serve -s frontend/dist -p 4173 &
      - name: Wait for server
        run: npx wait-on http://localhost:4173
      - name: Run Lighthouse CI
        run: npx lhci autorun --config=frontend/.lighthouserc.json
        env:
          LHCI_GITHUB_APP_TOKEN: ${{ secrets.LHCI_GITHUB_APP_TOKEN }}
```

---

### 43.3 Tenant Onboarding Automation

**Convention** : La création d'un tenant doit être atomique (toutes les tables de référence initialisées) et idempotente.

```python
# app/services/tenant_provisioning.py
"""
Provisioning automatique d'un nouveau tenant.
Idempotent : peut être rejoué sans effet de bord.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Tenant, User, FeatureFlag
from app.constants.business import DEFAULT_FEATURE_FLAGS, DEFAULT_CATEGORIES
import logging

logger = logging.getLogger("carocorp.provisioning")


async def provision_tenant(
    db: AsyncSession,
    *,
    company_name: str,
    admin_email: str,
    admin_password_hash: str,
    plan: str = "standard",
) -> int:
    """
    Crée un tenant complet avec :
    - L'entrée tenant
    - L'utilisateur admin
    - Les feature flags par défaut selon le plan
    - Les catégories produits de base
    Retourne le tenant_id créé.
    """
    # 1. Créer le tenant
    tenant = Tenant(
        name=company_name,
        plan=plan,
        is_active=True,
    )
    db.add(tenant)
    await db.flush()  # Obtenir l'ID

    # 2. Créer l'admin
    admin = User(
        tenant_id=tenant.id,
        email=admin_email,
        hashed_password=admin_password_hash,
        role="admin",
        is_active=True,
        email_verified=True,
    )
    db.add(admin)

    # 3. Feature flags selon le plan
    for flag_key, flag_config in DEFAULT_FEATURE_FLAGS.get(plan, {}).items():
        db.add(FeatureFlag(
            tenant_id=tenant.id,
            key=flag_key,
            enabled=flag_config["enabled"],
            description=flag_config["description"],
        ))

    # 4. Catégories produits de base
    for cat_name in DEFAULT_CATEGORIES:
        db.add(ProductCategory(
            tenant_id=tenant.id,
            name=cat_name,
            is_active=True,
        ))

    await db.flush()

    logger.info("tenant_provisioned", extra={
        "tenant_id": tenant.id,
        "company": company_name,
        "plan": plan,
    })

    return tenant.id


# scripts/provision_tenant.py — CLI pour onboarding manuel
if __name__ == "__main__":
    import asyncio, argparse
    from app.core.database import get_db_context
    from app.core.security import hash_password

    parser = argparse.ArgumentParser()
    parser.add_argument("--company", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--plan", default="standard")
    args = parser.parse_args()

    async def run():
        async with get_db_context() as db:
            tenant_id = await provision_tenant(
                db,
                company_name=args.company,
                admin_email=args.email,
                admin_password_hash=hash_password(args.password),
                plan=args.plan,
            )
            await db.commit()
            print(f"Tenant #{tenant_id} créé : {args.company} ({args.plan})")

    asyncio.run(run())
```

---

### 43.4 Alembic — Migration Dry-Run & Audit

**Convention** :

```bash
# Visualiser le SQL généré AVANT d'exécuter (dry-run)
alembic upgrade head --sql > migration_preview.sql
# Inspecter migration_preview.sql avant tout merge en prod

# Makefile
migration-preview:
    docker compose run --rm api alembic upgrade head --sql

migration-audit:
    # Vérifier qu'aucune migration n'est destructive directe
    docker compose run --rm api alembic upgrade head --sql | \
        grep -iE '(DROP TABLE|DROP COLUMN|TRUNCATE|DELETE FROM)' && \
        echo "⚠️  Migration destructive détectée — vérifier expand/contract" || \
        echo "✅ Migration non destructive"

migration-status:
    docker compose run --rm api alembic current
    docker compose run --rm api alembic history --verbose
```

```python
# tests/contract/test_migrations.py
"""Vérifie que les migrations respectent les conventions expand/contract."""
import subprocess
import pytest

def test_no_destructive_direct_migration():
    """Aucune migration ne doit DROP TABLE ou DROP COLUMN directement."""
    result = subprocess.run(
        ["alembic", "upgrade", "head", "--sql"],
        capture_output=True, text=True
    )
    sql = result.stdout.upper()

    forbidden = ["DROP TABLE ", "DROP COLUMN ", "TRUNCATE TABLE"]
    violations = [f for f in forbidden if f in sql]

    assert not violations, (
        f"Migration destructive directe détectée : {violations}\n"
        "Utiliser expand/contract (renommer, nullable, backfill)."
    )

def test_all_new_columns_have_defaults_or_nullable():
    """Toute nouvelle colonne NOT NULL doit avoir un DEFAULT (sinon migration échoue sur table peuplée)."""
    result = subprocess.run(
        ["alembic", "upgrade", "head", "--sql"],
        capture_output=True, text=True
    )
    sql = result.stdout

    # Regex simplifiée — adapter à l'output Alembic réel
    import re
    add_col_pattern = re.compile(r"ADD COLUMN\s+\w+\s+\w+\s+NOT NULL(?!\s+DEFAULT)", re.IGNORECASE)
    violations = add_col_pattern.findall(sql)

    assert not violations, (
        f"Colonnes NOT NULL sans DEFAULT détectées : {violations}\n"
        "Ajouter un DEFAULT ou rendre nullable."
    )
```

---

## Section 44 — Feature Flags A/B Testing

### 44.1 Variants & Expérimentations

**Problème actuel** : Les feature flags sont binaires (on/off + rollout%). Pas de support de variants pour A/B testing.

**Convention** :

```python
# app/models/feature_flag.py — Étendre avec variants
from sqlalchemy import JSON

class FeatureFlag(Base, TimestampMixin, SoftDeleteMixin):
    # ... champs existants ...
    variants: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Ex: {'control': 0.5, 'variant_a': 0.3, 'variant_b': 0.2}"
    )
    # Poids des variantes (doivent sommer à 1.0)


# app/services/feature_flag.py — Résolution de variant
import hashlib

def get_flag_variant(
    flag: FeatureFlag,
    tenant_id: int,
    user_id: int | None = None,
) -> str | None:
    """
    Retourne le variant assigné à cet utilisateur/tenant.
    Déterministe : même user → toujours même variant (sticky assignment).
    """
    if not flag.variants:
        # Flag simple on/off
        return "enabled" if _is_flag_enabled(flag, tenant_id) else None

    # Hash déterministe user → bucket [0, 1)
    seed = f"{flag.key}:{tenant_id}:{user_id or 'anon'}"
    bucket = int(hashlib.md5(seed.encode()).hexdigest(), 16) / (2 ** 128)

    # Assigner au variant selon les poids cumulatifs
    cumulative = 0.0
    for variant, weight in sorted(flag.variants.items()):
        cumulative += weight
        if bucket < cumulative:
            return variant

    return "control"  # Fallback


# Usage
variant = get_flag_variant(flag, tenant_id=user.tenant_id, user_id=user.id)

if variant == "variant_a":
    return new_checkout_flow_response()
elif variant == "variant_b":
    return simplified_checkout_response()
else:
    return legacy_checkout_response()
```

**Tracking des métriques par variant** :
```python
# Émettre un event pour chaque interaction avec un flag à variants
async def track_flag_exposure(flag_key: str, variant: str, tenant_id: int, user_id: int):
    """Enregistre l'exposition à un variant pour l'analyse A/B."""
    await redis.incr(f"ab:{flag_key}:{variant}:exposures:{tenant_id}")
    # Agréger quotidiennement via Celery beat pour le dashboard analytique
```

---

## Section 45 — Matrice Priorité Sections 41–44

| Ref | Pattern | Priorité | Effort |
|-----|---------|----------|--------|
| 43.1 | Accessibility Testing axe-playwright | **P0** | 1j |
| 43.4 | Alembic dry-run + audit CI | **P0** | 0.5j |
| 43.3 | Tenant Onboarding Automation | **P1** | 2j |
| 41.1 | Sliding Window Lua cross-instance | **P1** | 1j |
| 42.1 | Sparse Fieldsets ?fields= | **P1** | 1j |
| 42.3 | API Versioning v1/v2 coexistence | **P1** | 1j |
| 43.2 | Lighthouse CI Performance Budget | **P1** | 1j |
| 44.1 | Feature Flags A/B variants | **P2** | 2j |
| 41.2 | Token Bucket burst control | **P2** | 1j |
| 42.2 | Contract-First API Design | **P2** | 2j |

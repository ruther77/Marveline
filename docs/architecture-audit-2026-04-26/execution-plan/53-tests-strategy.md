# 53 — Stratégie de tests

> **Objectif** : Garantir que la refonte 7-blocs n'introduit aucune régression sur les 1782 tests existants ET que chaque nouvelle feature livrée dispose d'une couverture de tests suffisante pour être déployée sereinement en production.
>
> **Cadre** : 100% des PRs doivent passer la pyramide complète. Aucun merge sans preuve d'exécution (`pytest -q` capturée dans la PR description). Coverage gate : **≥ 85% lignes / 75% branches** sur tout module touché.
>
> **Source de vérité** : Ce document complète `02-conventions.md §Tests` et fixe les règles opposables (interdictions, ratios, seuils).

---

## Sommaire

1. [Pyramide de tests cible](#1-pyramide-de-tests-cible)
2. [État actuel — baseline 1782 tests](#2-état-actuel--baseline-1782-tests)
3. [Plan de rattrapage dette](#3-plan-de-rattrapage-dette)
4. [Conventions et organisation](#4-conventions-et-organisation)
5. [Fixtures et helpers](#5-fixtures-et-helpers)
6. [Règles inviolables](#6-règles-inviolables)
7. [Tests par bloc — couverture cible](#7-tests-par-bloc--couverture-cible)
8. [Tests d'invariants](#8-tests-dinvariants)
9. [Tests de performance et régression](#9-tests-de-performance-et-régression)
10. [Tests E2E et smoke](#10-tests-e2e-et-smoke)
11. [Coverage gates et CI](#11-coverage-gates-et-ci)
12. [Mutation testing](#12-mutation-testing)
13. [Calendrier d'exécution](#13-calendrier-dexécution)

---

## 1. Pyramide de tests cible

```
                 ▲
                 │  E2E / Smoke
                 │  ~5% (≈ 100 tests)
                 │  Critères : flux critiques bout-en-bout via TestClient
                 │  Durée max : 2 min (CI)
                 │
            ▲    ┤
            │    │  Intégration
            │    │  ~25% (≈ 500 tests)
            │    │  DB réelle PostgreSQL, Redis réel, Celery eager
            │    │  Durée max : 5 min
            │    │
       ▲    ┤    ┤
       │    │    │  Unitaires
       │    │    │  ~70% (≈ 1400 tests)
       │    │    │  Fonctions pures, services mockés DB
       │    │    │  Durée max : 30 sec
       │    │    │
       └────┴────┴──────────────────────────────────────►
```

**Justification ratios** :
- **70% unitaires** : Logique métier (PricingEngine, FSM, calculs CMP/PMP, validators) doit être testée vite et exhaustivement
- **25% intégration** : Repositories, endpoints API, transactions DB, cascades — détectent les vrais bugs
- **5% E2E** : Couvrent les flux critiques (login, paiement, conversion devis) — coûteux mais essentiels

**Anti-pattern interdit** : pyramide inversée (50% E2E, 30% intégration, 20% unitaires) → suite trop lente, feedback loop dégradé, debug pénible.

---

## 2. État actuel — baseline 1782 tests

> Source : `tech-debt-tests.md` (mémoire) + `pytest --collect-only` au 2026-04-25.

### 2.1 Vue agrégée

```
Total collecté : 1782 tests
  Pass         : 1422 (79.8%)
  Fail         : 360 (20.2%)
  Skip         : 0
Durée run complet : ~14 min (CI gh-actions)
Coverage global    : ~71% lignes (varie 35% → 92% selon module)
```

### 2.2 Répartition échecs par catégorie

| Catégorie | Nombre fails | Cause racine | Sprint de fix |
|-----------|--------------|--------------|---------------|
| IAM v2 (auth_factor, MFA backup) | 142 | Migration SHA1→Argon2 incomplète, fixtures obsolètes | Sprint 2 (B2.S1) |
| KMS / chiffrement | 78 | Mock KMS jamais wiré, `EncryptedField` pète sans context manager | B6.S2 |
| Async / Celery | 62 | Tests appellent `.delay()` sans `CELERY_TASK_ALWAYS_EAGER=1` | B5.S5 |
| Régression sed ISO-APP-01 | 41 | Substitution massive a cassé fixtures `tenant.app_code` | Sprint 3 |
| Cross-tenant fixtures | 23 | Fixture `other_tenant` non isolée, fuit dans test suivant | Sprint 1 (renforcement) |
| Divers (timezone, locale FR, fl-formats) | 14 | Hardcoded `datetime.now()` au lieu de `freeze_time` | Continu |

### 2.3 Modules les plus faibles (coverage < 60%)

| Module | Coverage | Justification dette |
|--------|----------|---------------------|
| `app/services/instance_preparation.py` | 38% | F906 latent jamais détecté → preuve faiblesse |
| `app/services/relances.py` | 42% | F1058 `status='sent'` jamais vérifié sur transport |
| `app/core/crypto.py` | 51% | KMS mock incomplet |
| `app/services/etl/parser_metro_v2.py` | 56% | Fixtures CSV trop pauvres (3 fixtures vs 200 lignes prod) |
| `app/services/pricing.py` | 58% | Tests historiques sur ancien `PricingService`, jamais portés |
| `app/middleware/audit.py` | 59% | Decorator `@audit_action` non testé sur 6 mutations sur 23 |

### 2.4 Modules excellents (coverage > 90%)

| Module | Coverage | Pourquoi |
|--------|----------|----------|
| `app/core/permissions.py` | 94% | Test matrix RBAC v3 complète (146 cas) |
| `app/services/devis_to_reservation.py` | 92% | Conversion testée avec freeze_time, idempotence, rollback |
| `app/services/loyalty.py` | 91% | Régressions Q-points → tests exhaustifs |
| `app/repositories/customer.py` | 90% | Pattern repository bien rodé |

---

## 3. Plan de rattrapage dette

### 3.1 Sprint dédié "TEST-DEBT-CLEANUP"

**Position dans roadmap** : Sprint 2 (parallèle Bloc 2 IAM v2, car les fix IAM débloquent 142 tests d'un coup).

**Owner** : Dev2 (pair avec Lead pour validation)

**Effort** : 8 j-h cumulés sur 2 sprints (Sprint 2 + Sprint 3)

### 3.2 Découpage incrémental

| Story | Description | Tests débloqués | J-h |
|-------|-------------|-----------------|-----|
| TEST-DEBT-01 | Fix fixture `tenant` post-ISO-APP-01 (ajout `app_code` partout) | 41 | 1 |
| TEST-DEBT-02 | Fixture `kms_mock` context manager + wire dans conftest | 78 | 2 |
| TEST-DEBT-03 | `pytest.ini` : `CELERY_TASK_ALWAYS_EAGER=1` global | 62 | 0.5 |
| TEST-DEBT-04 | Migration tests IAM v2 → Argon2, drop SHA1 fixtures | 142 | 3 |
| TEST-DEBT-05 | Isolation cross-tenant fixtures (drop session, recreate) | 23 | 1 |
| TEST-DEBT-06 | `freeze_time` global pour tests temporels | 14 | 0.5 |

**Critère d'acceptation Sprint 3** : `pytest -q` → 0 fails, ou justifications explicites par ticket xfail référencé en mémoire.

### 3.3 Anti-régression

- **Hook pre-commit** : `pytest -x --lf` (last failed) → on n'introduit pas un nouveau fail si on part d'un build vert
- **CI** : `pytest --strict-markers --strict-config -p no:randomly` (déterministe)
- **Quarantaine** : Tests flaky (échouent 1x/20) déplacés dans `tests/_flaky/` + ticket de fix dans 7j max ou suppression

---

## 4. Conventions et organisation

### 4.1 Arborescence

```
tests/
├── conftest.py                         # Fixtures partagées globales (db, redis, kms, celery)
├── unit/                                # Tests unitaires (≈ 1400)
│   ├── core/
│   │   ├── test_crypto.py
│   │   ├── test_permissions.py
│   │   └── test_password_policy.py
│   ├── services/
│   │   ├── test_pricing_engine.py
│   │   ├── test_marmite_consumption.py
│   │   └── ...
│   └── ...
├── integration/                         # Tests intégration (≈ 500)
│   ├── api/
│   │   ├── test_auth_endpoints.py
│   │   ├── test_devis_endpoints.py
│   │   └── ...
│   ├── repositories/
│   │   └── test_customer_repository.py
│   └── workflows/                       # Workflows multi-services (devis→résa, encaissement, ETL)
│       ├── test_devis_to_reservation_atomic.py
│       └── test_etl_metro_full_pipeline.py
├── e2e/                                  # Tests bout-en-bout (≈ 100)
│   ├── test_flow_login_mfa.py
│   ├── test_flow_paiement_restaurant.py
│   ├── test_flow_provisioning_tenant.py
│   └── test_flow_rgpd_export.py
├── invariants/                           # Tests d'invariants permanents (§8)
│   ├── test_no_cross_tenant_leak.py
│   ├── test_audit_chain_hmac.py
│   ├── test_ledger_immutable.py
│   └── test_fsm_transitions_valid.py
├── performance/                          # Benchmarks régression (§9)
│   ├── test_customer_search_perf.py
│   └── test_etl_throughput.py
├── fixtures/                             # Données réutilisables
│   ├── csv/
│   │   ├── metro_sample_200_lignes.csv
│   │   ├── eurociel_sample.csv
│   │   └── taiyat_sample.csv
│   └── pdf/
│       └── facture_metro_sample.pdf
└── _flaky/                               # Tests en quarantaine (à fixer ou supprimer dans 7j)
    └── README.md                         # Liste tickets de fix associés
```

### 4.2 Nommage

- Fichier : `test_<module_testé>.py`
- Classe : `class Test<Comportement>` (regroupement logique)
- Fonction : `test_<scenario>__<résultat_attendu>`

```python
class TestPricingEngineMarveline:
    def test_calculate_subtotal_with_loyalty_discount__applies_15pct(self):
        ...

    def test_calculate_subtotal_with_caution_negative__raises_validation_error(self):
        ...
```

### 4.3 Markers

```python
# pyproject.toml ou pytest.ini
[tool.pytest.ini_options]
markers = [
    "slow: tests > 1 sec",
    "e2e: tests bout-en-bout (lents, peu nombreux)",
    "invariant: tests d'invariants (run en CI séparée)",
    "perf: benchmarks régression (gate métrique)",
    "flaky: tests en quarantaine, run autorisé en local seul",
    "integration: nécessite DB réelle / Redis réel",
    "kms: nécessite mock KMS context wired",
]
```

---

## 5. Fixtures et helpers

### 5.1 conftest.py — fixtures globales

```python
# tests/conftest.py
"""
Fixtures globales — alignées Phase 1 :
- Q5 : SQLAlchemy 100% async (AsyncSession + async_sessionmaker)
- Bloc 2 §2.1 : Account + TenantMembership (User est mort — F339)
- Bloc 7 §7.2 : Tenant.vertical = FK string verticals(code)
- Bloc 2 §2.3 : scopes au format `domain:action`
"""
import os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import Base
from app.core.config import settings


# Force eager Celery globally — interdit aux tests d'oublier
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "1"
os.environ["CELERY_TASK_EAGER_PROPAGATES"] = "1"


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """Engine PostgreSQL async test — schéma recréé par session."""
    engine = create_async_engine(settings.DATABASE_URL_TEST, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db(db_engine):
    """Session AsyncSession transactionnelle — rollback systématique."""
    async with db_engine.connect() as connection:
        transaction = await connection.begin()
        SessionLocal = async_sessionmaker(bind=connection, expire_on_commit=False)
        session = SessionLocal()

        yield session

        await session.close()
        await transaction.rollback()


@pytest_asyncio.fixture
async def tenant(db):
    """Tenant standard — Marveline location.

    Phase 1 §2.2 + tableau §7.4 : `Tenant` a 2 colonnes d'identification :
    - `app_code` : identifiant unique d'instance (ex: 'marveline', 'splendid')
    - `vertical` : FK string `verticals(code)` (Bloc 7 §7.2)

    Pas de `slug`, pas de `vertical_id`. Modèle réel app/models/tenant.py:41.
    """
    from app.models import Tenant
    t = Tenant(
        app_code="marveline-test",
        nom="Marveline Test SARL",
        vertical="location",   # FK string vers verticals(code)
        siret="12345678901234",
        is_active=True,
    )
    db.add(t)
    await db.flush()
    return t


@pytest_asyncio.fixture
async def other_tenant(db):
    """Second tenant pour tests cross-tenant — DOIT être différent du principal."""
    from app.models import Tenant
    t = Tenant(
        app_code="other-test",
        nom="Other Tenant SARL",
        vertical="location",
        siret="98765432109876",
        is_active=True,
    )
    db.add(t)
    await db.flush()
    return t


@pytest.fixture
def kms_mock(monkeypatch):
    """Mock KMS — context manager wireé, encrypt/decrypt déterministes."""

    class FakeKMS:
        def encrypt(self, plaintext: bytes, context: dict) -> bytes:
            return b"FAKE_ENC:" + plaintext + b":" + str(context).encode()

        def decrypt(self, ciphertext: bytes, context: dict) -> bytes:
            assert ciphertext.startswith(b"FAKE_ENC:")
            return ciphertext.split(b":", 2)[1]

    monkeypatch.setattr("app.core.crypto._kms_client", FakeKMS())
    yield


@pytest_asyncio.fixture
async def redis_client():
    """Redis async client sur DB test isolée — flushdb après chaque test."""
    from redis.asyncio import Redis
    client = Redis.from_url(settings.REDIS_URL_TEST)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def client(db, tenant, redis_client):
    """AsyncClient httpx + ASGITransport — DB et Redis injectés."""
    from app.core.deps import get_async_db, get_redis
    app.dependency_overrides[get_async_db] = lambda: db
    app.dependency_overrides[get_redis] = lambda: redis_client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authenticated_client(client, tenant, db):
    """AsyncClient avec Account authentifié + JWT en header.

    Modèle Bloc 2 §2.1 : `Account` (pas `User` — F339 mort).
    Rôles via `TenantMembership(account_id, tenant_id, role)`,
    pas via champ ARRAY sur l'entité.
    """
    from app.models import Account, TenantMembership
    from app.core.security import create_access_token
    from app.permissions.scope import Scope

    account = Account(
        email="test@test.fr",
        is_active=True,
    )
    db.add(account)
    await db.flush()

    membership = TenantMembership(
        account_id=account.id,
        tenant_id=tenant.id,
        role="admin",
    )
    db.add(membership)
    await db.flush()

    token = create_access_token(
        sub=str(account.id),
        tenant_id=str(tenant.id),
        scopes=[
            Scope.RESERVATIONS_WRITE.value,   # 'reservations:write'
            Scope.RESERVATIONS_READ.value,    # 'reservations:read'
            Scope.TENANTS_ADMIN.value,        # 'tenants:admin'
        ],
        vertical=tenant.vertical,             # string code, pas .code
    )
    client.headers["Authorization"] = f"Bearer {token}"
    return client
```

> **Note** : `pytest-asyncio` doit être configuré en mode `auto` dans `pyproject.toml` :
> ```toml
> [tool.pytest.ini_options]
> asyncio_mode = "auto"
> ```

### 5.2 Fixtures factories

```python
# tests/fixtures/factories.py
"""Factories pour générer données de test cohérentes."""
from decimal import Decimal
import factory
from factory.alchemy import SQLAlchemyModelFactory
from app.models import Customer, Reservation, Devis


class CustomerFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Customer
        sqlalchemy_session_persistence = "commit"

    nom = factory.Faker("last_name", locale="fr_FR")
    prenom = factory.Faker("first_name", locale="fr_FR")
    email = factory.Faker("email")
    telephone = factory.Faker("phone_number", locale="fr_FR")
    type = "particulier"


class DevisFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Devis
        sqlalchemy_session_persistence = "commit"

    statut = "brouillon"
    montant_ht_centimes = factory.Faker("pyint", min_value=10000, max_value=500000)
    # tva_rate_snapshot = Numeric(5,4) — taux décimal, pas centimes
    tva_rate_snapshot = factory.Faker(
        "random_element",
        elements=[Decimal("0.20"), Decimal("0.10"), Decimal("0.055")],
    )
```

### 5.3 Helpers de test

```python
# tests/helpers/assertions.py
def assert_no_cross_tenant_leak(response_json: list, expected_tenant_id: str):
    """Vérifie qu'aucun élément n'appartient à un autre tenant."""
    for item in response_json:
        if "tenant_id" in item:
            assert item["tenant_id"] == expected_tenant_id, (
                f"Cross-tenant leak detected: {item}"
            )


async def assert_audit_log_created(db, action: str, entity_id: str):
    """Vérifie qu'un AuditLog a été créé pour cette action.

    Async — Q5=A : sessions sync supprimées, on utilise AsyncSession.execute()
    avec select() au lieu de session.query().
    """
    from sqlalchemy import select
    from app.models import AuditLog

    result = await db.execute(
        select(AuditLog).filter_by(action=action, entity_id=entity_id)
    )
    log = result.scalar_one_or_none()
    assert log is not None, f"Missing AuditLog for {action}({entity_id})"
    assert log.actor_id is not None
    assert log.timestamp is not None


async def assert_outbox_event_created(db, event_type: str, aggregate_id: str):
    """Vérifie qu'un OutboxEvent a été créé."""
    from sqlalchemy import select
    from app.models import OutboxEvent

    result = await db.execute(
        select(OutboxEvent).filter_by(event_type=event_type, aggregate_id=aggregate_id)
    )
    evt = result.scalar_one_or_none()
    assert evt is not None, f"Missing OutboxEvent {event_type}({aggregate_id})"
    assert evt.status == "pending"
```

---

## 6. Règles inviolables

### R1. Pas de mock de la DB

❌ **INTERDIT** : `mock(SQLAlchemy session)`, `mock(Session.query)`, fake repositories qui retournent des dicts.

✅ **AUTORISÉ** : DB réelle (PostgreSQL test) avec rollback transactionnel par test.

**Justification** : Mocker la DB cache les vraies bugs (contraintes FK, triggers, RLS, types).

### R2. Pas d'assertion triviale

❌ **INTERDIT** : `def test_foo(): assert True`

Doit être détecté par `flake8-assertive` en CI.

### R3. Une assertion principale par test

Sauf cas justifié (ex: vérification d'un ensemble de propriétés invariantes après une action).

### R4. Pas de logique métier dans les tests

Les tests ne doivent jamais répliquer la logique testée — sinon ils valident le mock du code, pas le code lui-même.

### R5. Anti-cross-tenant systématique

Tout endpoint qui retourne une liste DOIT avoir au moins un test avec `other_tenant` qui vérifie qu'aucun élément ne fuit.

```python
def test_list_reservations__does_not_leak_cross_tenant(authenticated_client, db, tenant, other_tenant):
    """RESA cross-tenant : tenant A ne voit pas les résa de tenant B."""
    # Setup : 1 résa tenant A, 1 résa tenant B
    resa_a = ReservationFactory(tenant_id=tenant.id)
    resa_b = ReservationFactory(tenant_id=other_tenant.id)
    db.commit()

    response = authenticated_client.get("/api/v1/reservations")
    assert response.status_code == 200
    data = response.json()
    ids = [r["id"] for r in data["items"]]
    assert str(resa_a.id) in ids
    assert str(resa_b.id) not in ids
```

### R6. Tests temporels = `freeze_time`

❌ **INTERDIT** : `datetime.now()` dans le code de test (non déterministe en CI).

✅ **AUTORISÉ** : `freezegun.freeze_time("2026-04-27 14:30:00+00:00")` autour du test.

### R7. Pas de désérialisation arbitraire

Pas d'exécution dynamique de chaînes utilisateur, pas de désérialisation de données binaires non contrôlées. Si fixture binaire, fichier dédié et chargé en lecture seule via `Path.read_bytes()`.

### R8. Coverage gate par module touché

Si une PR modifie `app/services/foo.py`, alors `coverage[app/services/foo.py] >= 85%` après merge. Sinon CI rouge.

### R9. Pas de skip silencieux

❌ **INTERDIT** : `@pytest.mark.skip` sans raison documentée.

✅ **AUTORISÉ** : `@pytest.mark.skip(reason="Bloqué par F1234, ticket TEST-DEBT-08")` avec ticket référencé.

### R10. Tests de migration Alembic

Toute migration Alembic doit avoir un test :
- Appliquée sur DB vide → schéma final correct
- Appliquée puis downgrade → DB revenue à l'état initial (sauf migration explicitement non-réversible)

```python
# tests/integration/test_migrations.py
def test_migration_upgrade_then_downgrade__returns_to_original(alembic_runner):
    alembic_runner.migrate_up_to("a1b2c3d4e5f6")  # avant la migration testée
    initial_state = alembic_runner.get_schema_signature()

    alembic_runner.migrate_up_one()
    alembic_runner.migrate_down_one()

    final_state = alembic_runner.get_schema_signature()
    assert initial_state == final_state
```

---

## 7. Tests par bloc — couverture cible

### 7.1 Bloc 1 — Audit chaîné, FSM, Outbox

| Module | Tests requis | Type | Owner |
|--------|--------------|------|-------|
| `app/core/audit.py` (HMAC chain) | 18 | Unitaire | Lead |
| `app/services/outbox_dispatcher.py` | 12 | Intégration | Dev1 |
| `app/services/fsm.py` (helper) | 24 | Unitaire | Dev2 |
| Décorateur `@audit_action` | 8 | Unitaire (AST) | Dev1 |

**Tests-clés** :
- `test_audit_chain__hmac_continuity__valid_after_1000_inserts`
- `test_audit_chain__tampered_record__verification_fails`
- `test_outbox__publish_after_commit__exactly_once`
- `test_outbox__commit_rollback__no_publish`
- `test_fsm__invalid_transition__raises_with_clear_message`
- `test_fsm__matrix_complete__all_pairs_documented`

### 7.2 Bloc 2 — Auth, Authz, IAM v2

| Module | Tests requis | Type | Owner |
|--------|--------------|------|-------|
| `app/services/auth_factor.py` | 32 | Unitaire | Dev2 |
| `app/services/mfa.py` (TOTP + backup) | 28 | Unitaire + Intégration | Dev2 |
| `app/core/permissions.py` (RBAC v3) | 146 (matrix) | Unitaire | Dev1 |
| `app/services/scope_resolution.py` | 18 | Unitaire | Lead |
| Endpoints `/auth/*` | 24 | Intégration | Dev2 |

**Tests-clés** :
- `test_login__valid_credentials__returns_jwt_with_correct_scopes`
- `test_login__expired_account__returns_403_with_renewal_link`
- `test_mfa_backup_code__used_once__cannot_be_reused`
- `test_scope_resolution__user_in_2_verticals__intersection_correct`
- `test_jwt__signed_with_kid__validates_against_jwks`
- `test_argon2__rehash_on_login__if_params_outdated`

**Matrix RBAC v3** : 146 cas (rôles × actions × ressources) générés par `pytest.parametrize`. Doit couvrir 100% des combinaisons explicitement.

### 7.3 Bloc 3 — Devis, Réservation, Caution

| Module | Tests requis | Type | Owner |
|--------|--------------|------|-------|
| `app/services/pricing_engine.py` | 42 | Unitaire | Lead |
| `app/services/devis_to_reservation.py` | 16 | Intégration (atomique) | Lead |
| `app/services/cancellation.py` (cascade) | 18 | Intégration | Dev1 |
| `app/services/caution.py` (FSM) | 20 | Unitaire | Dev2 |
| Endpoints `/devis/*`, `/reservations/*` | 36 | Intégration | Dev1 |

**Tests-clés** :
- `test_devis_to_reservation__success__creates_resa_lines_caution_atomically`
- `test_devis_to_reservation__line_creation_fails__rollbacks_all`
- `test_cancellation__cascade__refunds_caution_via_outbox`
- `test_pricing_engine__loyalty_15pct__centimes_exact`
- `test_pricing_engine__caution_negative__raises_validation`

### 7.4 Bloc 4 — Customer, Loyalty, RFM

| Module | Tests requis | Type | Owner |
|--------|--------------|------|-------|
| `app/services/loyalty.py` | 38 | Unitaire | Dev1 |
| `app/services/rfm.py` (per-tenant thresholds) | 24 | Unitaire | Dev2 |
| `app/services/customer_import.py` (CSV) | 18 | Intégration | Dev1 |
| Endpoints `/customers/*` | 28 | Intégration | Dev1 |

**Tests-clés** :
- `test_loyalty_points__earn_then_redeem__balance_correct`
- `test_loyalty_q_points__expiry_24h__purged_correctly`
- `test_rfm__tenant_with_custom_thresholds__bucket_assigned_correctly`
- `test_customer_import__500_rows_csv__creates_all_async_via_celery`
- `test_customer_import__duplicate_email_in_csv__rejects_with_clear_error`

### 7.5 Bloc 5 — Stock, ETL, Marmite, Transferts

| Module | Tests requis | Type | Owner |
|--------|--------------|------|-------|
| `app/services/etl/parser_metro_v2.py` | 32 | Unitaire | Dev3 |
| `app/services/etl/parser_taiyat_v2.py` | 28 | Unitaire | Dev3 |
| `app/services/etl/parser_eurociel.py` | 22 | Unitaire | Dev3 |
| `app/services/etl/import_validator.py` (idempotence) | 18 | Intégration | Lead |
| `app/services/stock_items.py` (CMP/PMP) | 26 | Unitaire | Dev2 |
| `app/services/marmite.py` (consommation recette) | 24 | Intégration | Dev3 |
| `app/services/transfer_request.py` (FSM workflow) | 22 | Intégration | Dev1 |

**Tests-clés** :
- `test_etl__validate_import_called_twice__idempotent_no_dupes` (regression F870)
- `test_etl_metro__parse_200_lignes__brand_extraction_>=95pct`
- `test_etl_eurociel__no_price_in_csv__rejects_with_actionable_error`
- `test_marmite__consumption__decrements_ingredients_via_recipe` (regression F906)
- `test_marmite__instance_preparation__uses_qte_par_portion_field` (regression F906)
- `test_transfer_request__approve_then_fulfill__creates_internal_transfer`

### 7.6 Bloc 6 — Sécurité, RGPD, Observabilité

| Module | Tests requis | Type | Owner |
|--------|--------------|------|-------|
| `app/core/crypto.py` (KMS envelope) | 24 | Unitaire | Lead |
| `app/services/rgpd_export.py` | 18 | Intégration | Dev2 |
| `app/services/access_review.py` | 16 | Intégration | Dev1 |
| `app/middleware/mtls.py` (/metrics gate) | 12 | Intégration | Ops |
| Endpoints `/me/export`, `/admin/access-reviews/*` | 22 | Intégration | Dev2 |

**Tests-clés** :
- `test_crypto__encrypt_decrypt__context_mismatch__fails`
- `test_rgpd_export__user_data__includes_all_pii_decrypted`
- `test_access_review__auto_suspend_uncertified__deactivates_account` (regression F1055)
- `test_mtls__no_cert__metrics_returns_403`
- `test_mtls__valid_cert__metrics_returns_200`
- `test_relances__sent_status__only_after_email_actually_sent` (regression F1058)

### 7.7 Bloc 7 — DEVUP Platform, Provisioning, Multi-vertical

| Module | Tests requis | Type | Owner |
|--------|--------------|------|-------|
| `app/services/tenant_provisioning.py` | 24 | Intégration (E2E) | DEVUP |
| `app/services/vertical_resolution.py` | 14 | Unitaire | Lead |
| Endpoints `/admin/devup/*` | 18 | Intégration | DEVUP |
| `app/services/feature_flags.py` (per-tenant) | 16 | Unitaire | Dev1 |

**Tests-clés** :
- `test_provision_tenant__location_vertical__creates_all_seed_data_atomically`
- `test_provision_tenant__partial_failure__rollbacks_completely`
- `test_provision_tenant__creates_initial_admin_user_with_temp_pwd`
- `test_vertical_resolution__user_in_marveline__scopes_match_location_vertical`
- `test_feature_flag__enabled_for_tenant_a__disabled_for_tenant_b__no_leak`
- `test_no_brand_code__catalogue_has_zero_brand_code_references`

---

## 8. Tests d'invariants

> **Objectif** : Vérifier en continu que des propriétés architecturales fondamentales ne sont jamais violées. Ces tests sont **séparés** de la suite normale (`pytest -m invariant`) et tournent en CI dédiée.

### 8.1 INV-1 : No cross-tenant leak

```python
# tests/invariants/test_no_cross_tenant_leak.py
import pytest
from app.core.database import get_db
from app.main import app

@pytest.mark.invariant
def test_invariant_all_tenant_scoped_endpoints_filter_by_tenant(authenticated_client, db, tenant, other_tenant):
    """Pour tous les endpoints listant des entités tenant-scoped,
    aucune entité d'un autre tenant ne doit apparaître."""
    from tests.helpers.endpoints_inventory import TENANT_SCOPED_LIST_ENDPOINTS

    for endpoint, factory_other in TENANT_SCOPED_LIST_ENDPOINTS:
        # Crée 1 entité dans other_tenant
        entity_other = factory_other(tenant_id=other_tenant.id)
        db.commit()

        response = authenticated_client.get(endpoint)
        assert response.status_code in (200, 204), f"Endpoint {endpoint} broken"

        if response.status_code == 200:
            data = response.json()
            items = data.get("items", data) if isinstance(data, dict) else data
            ids = [item.get("id") for item in items]
            assert str(entity_other.id) not in ids, (
                f"CROSS-TENANT LEAK: {endpoint} returned entity from other tenant"
            )
```

### 8.2 INV-2 : Audit chain HMAC

```python
@pytest.mark.invariant
@pytest.mark.asyncio
async def test_invariant_audit_chain_hmac_intact(db):
    """La chaîne HMAC des audit_logs doit être valide bout-en-bout."""
    from app.services.audit import verify_chain
    result = await verify_chain(db)
    assert result.valid, f"Audit chain broken at log_id={result.first_break}"
```

### 8.3 INV-3 : Ledger immutable

> **Périmètre Q1** : 7 tables append-only avec trigger DB qui refuse UPDATE/DELETE.
> Convention de nommage : `trg_{table}_immutable` (alignée avec `54-ci-invariants.md` §9
> `REQUIRED_LEDGER_TRIGGERS`). Toute divergence = CI rouge garantie.

```python
import pytest
from sqlalchemy import text

@pytest.mark.invariant
@pytest.mark.asyncio
async def test_invariant_ledger_immutable_triggers_active(db):
    """Les triggers d'immutabilité doivent être actifs en DB sur les 7 tables Q1."""
    expected_triggers = {
        # Ledgers financiers/loyalty
        "revenue_ledger": "trg_revenue_ledger_immutable",
        "payment_ledger": "trg_payment_ledger_immutable",
        "points_ledger": "trg_points_ledger_immutable",
        # Audit (journal HMAC chaîné)
        "audit_logs": "trg_audit_logs_immutable",
        # Stock movements (tous flux confondus)
        "inventory_movements": "trg_inventory_movements_immutable",
        "epicerie_stock_movements": "trg_epicerie_stock_movements_immutable",
        "mouvements_stock_restaurant": "trg_mouvements_stock_restaurant_immutable",
    }
    for table, trigger_name in expected_triggers.items():
        result = await db.execute(text("""
            SELECT 1 FROM pg_trigger
            WHERE tgname = :trigger_name
            AND tgrelid = (:table)::regclass
        """), {"trigger_name": trigger_name, "table": table})
        row = result.fetchone()
        assert row is not None, f"Trigger {trigger_name} on {table} missing!"
```

### 8.4 INV-4 : FSM transitions valides

```python
from sqlalchemy import text

@pytest.mark.invariant
@pytest.mark.asyncio
async def test_invariant_fsm_transitions_only_documented(db):
    """Toutes les transitions FSM en DB (table fsm_transitions) doivent être
    dans la matrice documentée."""
    from app.services.fsm import FSM_MATRICES

    result = await db.execute(text(
        "SELECT entity_type, from_state, to_state FROM fsm_transitions"
    ))
    for entity_type, from_state, to_state in result.fetchall():
        matrix = FSM_MATRICES.get(entity_type)
        assert matrix is not None, f"Unknown FSM entity_type: {entity_type}"
        assert (from_state, to_state) in matrix.transitions, (
            f"Undocumented transition: {entity_type} {from_state} → {to_state}"
        )
```

### 8.5 INV-5 : Pas de `brand_code` dans Catalogue

```python
from sqlalchemy import text

@pytest.mark.invariant
@pytest.mark.asyncio
async def test_invariant_no_brand_code_in_catalogue(db):
    """Post-Bloc 7 : la colonne brand_code doit être supprimée du catalogue."""
    result = await db.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'catalogue_produits' AND column_name = 'brand_code'
    """))
    row = result.fetchone()
    assert row is None, "Column brand_code still exists in catalogue_produits!"
```

### 8.6 INV-6 : Tous les endpoints ont un scope déclaré

```python
@pytest.mark.invariant
def test_invariant_all_endpoints_have_scopes_declared():
    """Aucun endpoint mutable ne doit être sans scope déclaré
    (sauf whitelist explicite : /health, /docs)."""
    from scripts.ci.check_endpoint_scopes import find_unprotected_endpoints
    unprotected = find_unprotected_endpoints("app/api/v1")
    whitelist = {"/health/live", "/health/ready", "/docs", "/openapi.json"}
    violations = [e for e in unprotected if e not in whitelist]
    assert not violations, f"Unprotected endpoints: {violations}"
```

### 8.7 INV-7 : Tous les BigInteger centimes ont contrainte CHECK

```python
from sqlalchemy import text

@pytest.mark.invariant
@pytest.mark.asyncio
async def test_invariant_all_centimes_columns_have_check_positive(db):
    """Toutes les colonnes _centimes doivent avoir CHECK >= 0
    (sauf colonnes signed comme variation_centimes)."""
    result = await db.execute(text("""
        SELECT table_name, column_name FROM information_schema.columns
        WHERE column_name LIKE '%_centimes'
        AND data_type = 'bigint'
    """))
    rows = result.fetchall()

    signed_whitelist = {"variation_centimes", "ajustement_centimes", "credit_centimes"}

    for table, col in rows:
        if col in signed_whitelist:
            continue
        check_result = await db.execute(text("""
            SELECT 1 FROM information_schema.check_constraints
            WHERE constraint_name LIKE :pattern
        """), {"pattern": f"%{table}_{col}_positive%"})
        assert check_result.fetchone(), f"Missing CHECK >= 0 on {table}.{col}"
```

### 8.8 INV-8 : Anti-régression cross-tenant ApiKey (F02 — vague 3)

> **Friction prévenue** : F02 (cf. `01-core-foundations.md` §F02) — `_resolve_api_key_async`
> n'appelle pas `set_tenant_context()`. Avec RLS active (B1.S2), le résultat dépend
> de la correction effective de F02 dans B1.S1. Ce test est la garde de régression.

```python
import pytest
from sqlalchemy import select

@pytest.mark.invariant
@pytest.mark.asyncio
async def test_invariant_apikey_isolated_by_rls(db, tenant, other_tenant):
    """Un ApiKeyClient du tenant A ne voit PAS les données du tenant B
    via RLS PostgreSQL (et non par filtres Python applicatifs).

    Setup : crée 1 customer dans tenant A et 1 dans tenant B.
    Crée une API key pour tenant A. Simule la session DB
    après resolve_api_key (set_tenant_context appelé).
    Vérifie que SELECT * FROM customers ne retourne QUE le customer du tenant A.
    """
    from app.models import ApiKey, Customer
    from app.core.database import set_tenant_context

    # Setup : 2 customers cross-tenant
    customer_a = Customer(tenant_id=tenant.id, nom="Dupont A", email="a@a.fr")
    customer_b = Customer(tenant_id=other_tenant.id, nom="Dupont B", email="b@b.fr")
    db.add_all([customer_a, customer_b])
    await db.flush()

    # Simule contexte ApiKey du tenant A
    api_key = ApiKey(tenant_id=tenant.id, key_hash="hash", is_active=True)
    db.add(api_key)
    await db.flush()
    await set_tenant_context(db, tenant.id)

    # SELECT global — doit retourner UNIQUEMENT customer_a (RLS filtre)
    result = await db.execute(select(Customer))
    customers_visible = result.scalars().all()
    customer_ids = {c.id for c in customers_visible}

    assert customer_a.id in customer_ids
    assert customer_b.id not in customer_ids, (
        "RLS leak: ApiKey context du tenant A voit customers du tenant B. "
        "Vérifier que F02 est corrigé : _resolve_api_key_async doit appeler "
        "set_tenant_context() après résolution de la clé."
    )
```

### 8.9 INV-9 : Audit atomicity via Outbox (F117 — vague 3)

> **Friction prévenue** : F117 (cf. `04-middleware.md` §F117) — `AuditMiddleware._audit_mutation`
> ouvrait une session DB séparée → si commit métier réussit + audit échoue, mutation non auditée.
> Outbox pattern (Q4=A) résout. Ce test garantit que le rollback métier rollback aussi l'audit.

```python
@pytest.mark.invariant
@pytest.mark.asyncio
async def test_invariant_audit_outbox_atomic_with_business_tx(db, tenant):
    """Si la transaction métier échoue, l'event Outbox correspondant
    DOIT être rollbacké (pas de fantôme dans la table outbox)."""
    from sqlalchemy import select
    from app.models import OutboxEvent, Customer
    from app.services.audit import audit_service

    # Compte initial outbox
    initial = await db.execute(select(OutboxEvent).filter_by(event_type="CustomerCreated"))
    count_before = len(initial.scalars().all())

    # Tente une mutation qui va échouer (constraint violation)
    try:
        async with db.begin_nested():  # SAVEPOINT
            customer = Customer(tenant_id=tenant.id, nom="A", email="invalid_email_format")
            db.add(customer)
            await audit_service.log("customer.create", actor_id=1, payload={"customer_id": "?"})
            # Force une violation de contrainte
            db.add(Customer(tenant_id=tenant.id, nom="A", email="invalid_email_format"))  # duplicate email
            await db.flush()
    except Exception:
        pass  # constraint violation attendue → SAVEPOINT rollbacké

    # Vérifier qu'aucun OutboxEvent fantôme n'est resté
    after = await db.execute(select(OutboxEvent).filter_by(event_type="CustomerCreated"))
    count_after = len(after.scalars().all())

    assert count_after == count_before, (
        f"Outbox event fantôme : {count_after - count_before} CustomerCreated events "
        "créés alors que la transaction métier a été rollbackée. "
        "Vérifier que audit_service.log() utilise la même session (pas une session séparée)."
    )
```

### 8.11 INV-11 : JWT sans claim `type` rejeté (F47 — vague 4)

> **Friction prévenue** : F47 — `app/core/security.py:262` retournait le payload sans validation
> audience si `actual_type` n'était ni `ACCESS` ni `REFRESH`. Cross-app escalation possible.

```python
import time
import jwt
from app.core.config import settings

@pytest.mark.invariant
@pytest.mark.asyncio
async def test_invariant_jwt_without_type_claim__rejected_on_all_audiences():
    """Forge un JWT sans claim 'type' — doit être rejeté avec TokenInvalid."""
    from app.core.security import decode_token, TokenInvalid

    # Token signé valide MAIS sans claim 'type' (ni ACCESS ni REFRESH)
    payload_no_type = {
        "sub": "1",
        "tenant_id": "1",
        "aud": "marveline",  # Audience valide
        "exp": int(time.time()) + 3600,
    }
    token = jwt.encode(payload_no_type, settings.JWT_SECRET_KEY, algorithm="HS256")

    with pytest.raises(TokenInvalid, match="Invalid token type|token type"):
        decode_token(token, expected_audience="marveline")


@pytest.mark.invariant
@pytest.mark.asyncio
async def test_invariant_jwt_unknown_type__rejected():
    """Token avec type='internal'/'service' (forgé) — doit être rejeté."""
    from app.core.security import decode_token, TokenInvalid

    for forged_type in ("internal", "service", "system", "admin", ""):
        payload = {
            "sub": "1", "type": forged_type, "aud": "marveline",
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
        with pytest.raises(TokenInvalid):
            decode_token(token, expected_audience="marveline")
```

### 8.12 INV-12 : OAuth callback respecte le MFA gate (F404 — vague 5)

> **Friction prévenue** : F404 — `oauth.py:296` `mfa_verified=False` hardcodé permettait
> à un user MFA-enrôlé de bypass MFA via login Google/Microsoft.

```python
@pytest.mark.invariant
@pytest.mark.asyncio
async def test_invariant_oauth_callback__mfa_enrolled__returns_mfa_required(
    client, db, tenant
):
    """Compte avec auth_factor TOTP actif + login Google → mfa_required=True, pas tokens."""
    from app.models import Account, TenantMembership, AuthFactor

    account = Account(email="user@test.fr", is_active=True)
    db.add(account)
    await db.flush()
    membership = TenantMembership(account_id=account.id, tenant_id=tenant.id, role="admin")
    db.add(membership)
    await db.flush()
    factor = AuthFactor(
        membership_id=membership.id, type="TOTP", is_active=True,
        encrypted_secret=b"fake", encrypted_secret_key_version=1,
        label="Test TOTP",
    )
    db.add(factor)
    await db.flush()

    # Mock OAuth callback (simule retour Google avec code valide)
    response = await client.get(
        "/api/v1/auth/oauth/google/callback",
        params={"code": "mock_valid_code", "state": "mock_state"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body.get("mfa_required") is True, (
        "F404 régression : OAuth callback émet tokens directement alors que MFA enrôlée"
    )
    assert "access_token" not in body, "Token émis sans gate MFA — F404 NON CORRIGÉ"
    assert "pending_token" in body
```

### 8.13 INV-13 : WebAuthn RP_ID matche le tenant (F368 — vague 4)

> **Friction prévenue** : F368 — `RP_ID = settings.JWT_ISSUER.replace("www.", "")` global hardcodé.
> Cassait WebAuthn pour tout vertical ≠ Marveline. Bloque démo Splendid 28/04.

```python
@pytest.mark.invariant
@pytest.mark.asyncio
async def test_invariant_webauthn_register_options__uses_tenant_rp_id(
    authenticated_client, db, tenant
):
    """register/options doit retourner le rp_id du tenant courant, pas le global."""
    tenant.rp_id = "splendid.events"
    tenant.frontend_url = "https://splendid.events"
    await db.flush()

    response = await authenticated_client.post("/api/v1/auth/webauthn/register/options")
    assert response.status_code == 200
    body = response.json()
    assert body["rp"]["id"] == "splendid.events", (
        f"F368 régression : RP_ID = {body['rp']['id']!r} — devrait être 'splendid.events'"
    )
    assert body["rp"]["id"] != "marveline.com"


@pytest.mark.invariant
@pytest.mark.asyncio
async def test_invariant_webauthn__null_rp_id_fallback_to_jwt_issuer(
    authenticated_client, db, tenant
):
    """Si tenant.rp_id IS NULL, fallback vers settings.JWT_ISSUER (rétro-compat)."""
    tenant.rp_id = None
    tenant.frontend_url = None
    await db.flush()

    response = await authenticated_client.post("/api/v1/auth/webauthn/register/options")
    assert response.status_code == 200
    # Fallback safe — pas un fail
    assert body := response.json()
    assert body["rp"]["id"] is not None
```

### 8.14 INV-14 : PII customer toutes colonnes chiffrées (V5-P0-01 — vague 5)

> **Friction prévenue** : V5-P0-01 — B4.S5 chiffrait `notes` seul. Phone, address,
> first_name, last_name restaient en plain text — exposition RGPD Art.25.

```python
@pytest.mark.invariant
@pytest.mark.asyncio
async def test_invariant_customer_pii_all_columns_encrypted(db):
    """Toutes les colonnes PII Customer doivent avoir leur pendant `*_encrypted` BYTEA.

    Périmètre PII : phone, address, first_name, last_name, notes (Bloc 4 Q24 + V5-P0-01).
    Si une colonne PII existe en plain text VARCHAR/TEXT et n'a pas de version `*_encrypted`,
    c'est une violation RGPD Art.25 (privacy by design).
    """
    from sqlalchemy import text

    pii_columns = ["phone", "address", "first_name", "last_name", "notes"]

    result = await db.execute(text("""
        SELECT column_name, data_type FROM information_schema.columns
        WHERE table_name = 'customers'
        AND column_name = ANY(:pii_columns)
    """), {"pii_columns": pii_columns})
    plain_text_pii = {row[0]: row[1] for row in result.fetchall()}

    result_encrypted = await db.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'customers'
        AND column_name LIKE '%_encrypted'
    """))
    encrypted_columns = {row[0] for row in result_encrypted.fetchall()}

    violations = []
    for col in pii_columns:
        if col in plain_text_pii:
            # Colonne plain text encore présente → doit être en cours de migration
            # Si la colonne `_encrypted` existe → backfill en cours OK
            # Si elle n'existe pas → violation
            if f"{col}_encrypted" not in encrypted_columns:
                violations.append(
                    f"customers.{col} ({plain_text_pii[col]}) sans pendant {col}_encrypted"
                )

    assert not violations, (
        f"PII partielle (V5-P0-01 / RGPD Art.25) : {violations}. "
        f"B4.S5 doit étendre le chiffrement à toutes les colonnes PII (pas seulement `notes`)."
    )
```

### 8.15 INV-15 : Suppliers + supplier_orders contraintes UNIQUE+CHECK présentes (V6-P0-03/04)

> **Friction prévenue** : V6-P0-03/04 (F826/F827/F828) — modules suppliers absents Phase 3.
> Doublons silencieux + statuts corrompus acceptés.

```python
@pytest.mark.invariant
@pytest.mark.asyncio
async def test_invariant_suppliers_constraints_present(db):
    """Suppliers + supplier_orders doivent avoir UNIQUE et CHECK contraintes (B3.S7)."""
    from sqlalchemy import text

    expected_constraints = [
        ("suppliers", "uq_suppliers_tenant_name", "UNIQUE"),
        ("suppliers", "ck_suppliers_status_valid", "CHECK"),
        ("supplier_orders", "uq_supplier_orders_tenant_reference", "UNIQUE"),
        ("supplier_orders", "ck_supplier_orders_status_valid", "CHECK"),
        ("supplier_order_receipt_lines", "ck_receipt_qty_within_order", "CHECK"),
    ]

    missing = []
    for table, constraint_name, constraint_type in expected_constraints:
        result = await db.execute(text("""
            SELECT 1 FROM information_schema.table_constraints
            WHERE table_name = :table AND constraint_name = :name
            AND constraint_type = :type
        """), {"table": table, "name": constraint_name, "type": constraint_type})
        if result.fetchone() is None:
            missing.append(f"{table}.{constraint_name} ({constraint_type})")

    assert not missing, (
        f"Contraintes B3.S7 absentes (V6-P0-03/04 F826/F827/F828) : {missing}. "
        f"Sprint B3.S7 doit livrer ces constraints avant que suppliers/supplier_orders soient utilisés en prod."
    )
```

### 8.10 INV-10 : Sessions révoquées post-membership.suspend (F259 — vague 3)

> **Friction prévenue** : F259 (cf. `09-tenant-multi-app-brand.md` §F259) — `MembershipService.suspend/revoke`
> ne révoque pas les sessions actives → fenêtre de 15 min post-révocation.

```python
@pytest.mark.invariant
@pytest.mark.asyncio
async def test_invariant_revoke_membership_invalidates_sessions(db, redis_client, tenant):
    """Suspendre un membership doit invalider toutes les sessions actives
    de l'account sur ce tenant immédiatement (pas de fenêtre de 15 min)."""
    from app.models import Account, TenantMembership, AccountSession
    from app.services.membership import membership_service

    # Setup : account + membership + 2 sessions actives
    account = Account(email="user@test.fr", is_active=True)
    db.add(account)
    await db.flush()
    membership = TenantMembership(account_id=account.id, tenant_id=tenant.id, role="admin")
    db.add(membership)
    session_1 = AccountSession(account_id=account.id, tenant_id=tenant.id, jti="jti-1", is_active=True)
    session_2 = AccountSession(account_id=account.id, tenant_id=tenant.id, jti="jti-2", is_active=True)
    db.add_all([session_1, session_2])
    await db.flush()

    # Simule cache JWT en Redis
    await redis_client.set(f"session:jti-1", str(account.id), ex=3600)
    await redis_client.set(f"session:jti-2", str(account.id), ex=3600)

    # Action : suspend membership
    await membership_service.suspend(db, membership.id, reason="audit_compliance")

    # Vérification : sessions DB désactivées
    from sqlalchemy import select
    result = await db.execute(
        select(AccountSession).filter_by(account_id=account.id, tenant_id=tenant.id, is_active=True)
    )
    active_sessions = result.scalars().all()
    assert len(active_sessions) == 0, (
        "Sessions DB toujours actives après suspend(). Membership.suspend doit cascade "
        "AccountSession.is_active = False."
    )

    # Vérification : cache Redis invalidé
    assert await redis_client.exists("session:jti-1") == 0
    assert await redis_client.exists("session:jti-2") == 0, (
        "Cache Redis session non invalidé après suspend(). "
        "Membership.suspend doit DEL toutes les session:jti:* de l'account/tenant."
    )
```

---

## 9. Tests de performance et régression

> Voir `55-performance-benchmarks.md` pour les cibles détaillées. Cette section spécifie les tests automatisés.

### 9.1 Stratégie

- **Benchmarks régression** : exécutés en CI sur PR touchant les modules sensibles (`pytest-benchmark`)
- **Gate stricte** : régression > 20% par rapport à la baseline → CI rouge
- **Stockage baseline** : `.benchmarks/baseline.json` versionné

### 9.2 Endpoints critiques sous benchmark

```python
# tests/performance/test_customer_search_perf.py
import pytest

@pytest.mark.perf
def test_customer_search__10k_customers__p95_lt_50ms(benchmark, authenticated_client, db, tenant):
    """Recherche par nom dans 10k clients doit retourner en < 50ms P95."""
    from tests.fixtures.factories import CustomerFactory
    CustomerFactory.create_batch(10000, tenant_id=tenant.id)
    db.commit()

    result = benchmark(
        lambda: authenticated_client.get(
            f"/api/v1/customers?search=Dupont&tenant_id={tenant.id}"
        )
    )
    assert result.status_code == 200
    # pytest-benchmark vérifie automatiquement vs baseline
```

### 9.3 ETL throughput

```python
@pytest.mark.perf
def test_etl_metro__1000_lines__throughput_gt_100_per_sec(benchmark, db, tenant):
    """Parser METRO doit traiter > 100 lignes/sec."""
    from app.services.etl.parser_metro_v2 import ParserMetroV2

    csv_content = open("tests/fixtures/csv/metro_sample_1000_lignes.csv").read()
    parser = ParserMetroV2(tenant_id=tenant.id, db=db)

    result = benchmark(parser.parse, csv_content)
    assert len(result.lines) == 1000
    # Si throughput < 100/sec → benchmark fail
```

### 9.4 Régression exemples détectées

| Métrique | Baseline | Cible | Régression > | Action |
|----------|----------|-------|--------------|--------|
| `GET /customers?search=X` (10k rows) | 28ms P95 | <50ms | 60ms | CI rouge |
| `POST /devis/{id}/convert` | 180ms | <300ms | 360ms | CI rouge — gate calé sur baseline 2026-04-25. À recalibrer après B3.S4 (cible 220ms cf. `55-performance-benchmarks.md` §4.2) → nouveau gate 264ms (+20%). |
| `POST /reservations` (5 lignes + caution) | 95ms | <150ms | 180ms | CI rouge |
| `GET /metrics` scrape complet | 380ms | <500ms | 600ms | CI rouge |
| ETL METRO parse 1000 lignes | 7.2s | <10s | 12s | CI rouge |
| Login + JWT issuance P99 | 145ms | <200ms | 240ms | CI rouge |

---

## 10. Tests E2E et smoke

### 10.1 Flux critiques

| Flux | Fichier | Étapes | Durée cible |
|------|---------|--------|-------------|
| Login + MFA | `test_flow_login_mfa.py` | 8 | <3s |
| Conversion devis → résa | `test_flow_devis_to_reservation.py` | 12 | <5s |
| Paiement restaurant complet | `test_flow_paiement_restaurant.py` | 15 | <8s |
| Provisioning tenant DEVUP | `test_flow_provisioning_tenant.py` | 22 | <12s |
| Export RGPD complet | `test_flow_rgpd_export.py` | 10 | <15s (async) |
| ETL METRO bout-en-bout | `test_flow_etl_metro.py` | 18 | <30s |
| Réception fournisseur → stock | `test_flow_reception_to_stock.py` | 14 | <6s |
| Cycle marmite : prep → consommation → audit | `test_flow_marmite_complete.py` | 16 | <8s |

### 10.2 Exemple : conversion devis

```python
# tests/e2e/test_flow_devis_to_reservation.py
import pytest
from freezegun import freeze_time

@pytest.mark.e2e
@freeze_time("2026-04-27 10:00:00+00:00")
def test_e2e_devis_to_reservation__success__all_state_consistent(
    authenticated_client, db, tenant, kms_mock
):
    # 1. Créer client
    r = authenticated_client.post("/api/v1/customers", json={
        "nom": "Dupont", "prenom": "Jean", "email": "j.dupont@test.fr",
        "telephone": "0612345678", "type": "particulier"
    })
    assert r.status_code == 201
    customer_id = r.json()["id"]

    # 2. Créer devis
    r = authenticated_client.post("/api/v1/devis", json={
        "customer_id": customer_id,
        "date_evenement": "2026-05-15",
        "lines": [
            {"product_id": "...", "qte": 50, "prix_unitaire_centimes": 1200},
        ],
        "deposit_required_pct": 30,
    })
    assert r.status_code == 201
    devis_id = r.json()["id"]
    assert r.json()["statut"] == "brouillon"

    # 3. Valider devis
    r = authenticated_client.post(f"/api/v1/devis/{devis_id}/valider")
    assert r.status_code == 200
    assert r.json()["statut"] == "valide"

    # 4. Convertir en réservation (atomique)
    r = authenticated_client.post(f"/api/v1/devis/{devis_id}/convert")
    assert r.status_code == 201
    resa_id = r.json()["reservation_id"]

    # 5. Vérifier états cohérents
    devis_after = authenticated_client.get(f"/api/v1/devis/{devis_id}").json()
    assert devis_after["statut"] == "converti"

    resa_after = authenticated_client.get(f"/api/v1/reservations/{resa_id}").json()
    assert resa_after["statut"] == "active"
    assert len(resa_after["lines"]) == 1
    assert resa_after["caution_centimes"] == 18000  # 30% de 60000

    # 6. Vérifier audit chain
    from tests.helpers.assertions import assert_audit_log_created
    assert_audit_log_created(db, "devis.convert", devis_id)
    assert_audit_log_created(db, "reservation.create", resa_id)

    # 7. Vérifier outbox events
    from tests.helpers.assertions import assert_outbox_event_created
    assert_outbox_event_created(db, "DevisConverted", devis_id)
    assert_outbox_event_created(db, "ReservationCreated", resa_id)
```

### 10.3 Smoke tests (post-deploy)

```python
# tests/e2e/test_smoke_post_deploy.py
"""Smoke tests exécutés après chaque déploiement prod.
Doit prendre < 30 sec total."""

@pytest.mark.smoke
def test_smoke__health_live():
    response = requests.get(f"{PROD_URL}/api/v1/health/live")
    assert response.status_code == 200

@pytest.mark.smoke
def test_smoke__health_ready__all_components_up():
    response = requests.get(f"{PROD_URL}/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["database"]["status"] == "up"
    assert data["redis"]["status"] == "up"
    assert data["broker"]["status"] == "up"

@pytest.mark.smoke
def test_smoke__login_known_user__returns_jwt():
    """User canary qui doit toujours pouvoir se connecter."""
    response = requests.post(f"{PROD_URL}/api/v1/auth/login", json={
        "email": "canary@devup.fr",
        "password": os.environ["CANARY_PASSWORD"],
    })
    assert response.status_code == 200
    assert "access_token" in response.json()
```

---

## 11. Coverage gates et CI

### 11.1 Configuration

```toml
# pyproject.toml
[tool.coverage.run]
source = ["app"]
omit = [
    "*/migrations/*",
    "*/tests/*",
    "*/conftest.py",
]
branch = true

[tool.coverage.report]
fail_under = 85
precision = 2
show_missing = true
skip_covered = false

[tool.coverage.paths]
source = ["app/"]
```

### 11.2 Gates par module (extrait)

| Module | Coverage min | Critique ? |
|--------|--------------|------------|
| `app/core/` | 90% | OUI |
| `app/services/pricing_engine.py` | 95% | OUI |
| `app/services/devis_to_reservation.py` | 95% | OUI |
| `app/services/marmite.py` | 90% | OUI (regression F906) |
| `app/services/relances.py` | 90% | OUI (regression F1058) |
| `app/services/loyalty.py` | 90% | OUI |
| `app/services/etl/` | 80% | NON (mais cible 85%) |
| `app/api/v1/endpoints/` | 75% | NON (couvert par intégration) |
| `app/middleware/` | 85% | OUI |

### 11.3 GitHub Actions workflow

```yaml
# .github/workflows/tests.yml
name: tests
on: [push, pull_request]

jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -e .[test]
      - run: pytest tests/unit -q --cov=app --cov-report=xml --cov-report=term
      - uses: codecov/codecov-action@v4

  integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_PASSWORD: test, POSTGRES_DB: test }
      redis: { image: redis:7 }
      rabbitmq: { image: rabbitmq:3.13 }
    steps:
      - uses: actions/checkout@v4
      - run: pytest tests/integration -q --cov=app --cov-append

  e2e:
    runs-on: ubuntu-latest
    needs: [unit, integration]
    steps:
      - uses: actions/checkout@v4
      - run: pytest tests/e2e -q --maxfail=1

  invariants:
    runs-on: ubuntu-latest
    needs: [integration]
    steps:
      - uses: actions/checkout@v4
      - run: pytest tests/invariants -q --strict-markers

  performance:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v4
      - run: pytest tests/performance --benchmark-compare=.benchmarks/baseline.json --benchmark-compare-fail=mean:20%

  coverage-gate:
    runs-on: ubuntu-latest
    needs: [unit, integration]
    steps:
      - run: |
          coverage report --fail-under=85
          # Per-module gate
          python scripts/ci/check_coverage_per_module.py
```

---

## 12. Mutation testing

### 12.1 Pourquoi

Coverage haute ne garantit pas que les tests détectent les bugs. Mutation testing introduit des bugs artificiels et vérifie que les tests les attrapent.

### 12.2 Outil

`mutmut` (Python) — exécuté hebdomadairement sur modules critiques.

### 12.3 Modules sous mutation testing

- `app/services/pricing_engine.py`
- `app/services/loyalty.py`
- `app/services/devis_to_reservation.py`
- `app/services/marmite.py`
- `app/core/permissions.py`
- `app/services/auth_factor.py`

### 12.4 Cible

**Mutation score ≥ 80%** sur ces modules. Si < 80% → ticket de fix dans le sprint suivant.

```bash
# scripts/run_mutation_testing.sh
mutmut run --paths-to-mutate=app/services/pricing_engine.py
mutmut results
# Si score < 80%, sortir code 1
```

---

## 13. Calendrier d'exécution

### 13.1 Local (dev)

| Commande | Fréquence | Durée |
|----------|-----------|-------|
| `pytest tests/unit -x` | Pre-commit hook | <30s |
| `pytest tests/unit tests/integration -q` | Avant push | <8min |
| `pytest -m "not slow"` | Itération rapide | <2min |

### 13.2 CI (sur PR)

| Job | Trigger | Durée cible |
|-----|---------|-------------|
| Unit | Tout commit | 2 min |
| Integration | Tout commit | 5 min |
| E2E | Tout commit (post-unit) | 4 min |
| Invariants | Tout commit | 3 min |
| Performance regression | PR seulement | 6 min |
| Coverage gate | Post-tests | <30s |
| **Total CI** | — | **~15 min** |

### 13.3 Nightly

| Job | Heure UTC | Action si fail |
|-----|-----------|----------------|
| Audit chain HMAC verification | 02:00 | PagerDuty |
| Mutation testing modules critiques | 03:00 | Slack #dev-quality |
| Smoke tests prod | 04:00 + 16:00 | PagerDuty |
| Coverage trend report | 06:00 | Slack #dev-metrics |

### 13.4 Pre-prod

Pipeline complet + tests E2E sur environnement staging avec données anonymisées de prod.

---

## Annexes

### A. Outils requis

```toml
# pyproject.toml
[project.optional-dependencies]
test = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "pytest-benchmark>=4.0",
    "pytest-randomly>=3.15",
    "pytest-xdist>=3.5",
    "freezegun>=1.4",
    "factory-boy>=3.3",
    "httpx>=0.27",
    "respx>=0.21",
    "mutmut>=2.4",
    "flake8-assertive>=2.1",
]
```

### B. Commandes utiles

```bash
# Run rapide (dev)
pytest tests/unit -x --lf  # Last failed first, exit at first fail

# Coverage HTML
pytest --cov=app --cov-report=html
open htmlcov/index.html

# Tests parallèles (8 workers)
pytest -n 8 tests/

# Benchmark mode
pytest tests/performance --benchmark-only

# Run un seul invariant
pytest tests/invariants/test_no_cross_tenant_leak.py -v

# Marker spécifique
pytest -m "invariant and not slow"
```

### C. Définition de Done — tests

Pour qu'une PR soit mergeable :

- [ ] Tous les nouveaux fichiers ont leurs tests unitaires (≥ 85% coverage du fichier)
- [ ] Si endpoint touché : test d'intégration ajouté
- [ ] Si flux critique modifié : test E2E mis à jour
- [ ] Si invariant impacté : test d'invariant ajouté
- [ ] Si performance critique : benchmark régression ajouté
- [ ] `pytest -q` localement → **0 fail, 0 error**
- [ ] CI complet → vert
- [ ] Coverage gate → vert sur tous modules touchés
- [ ] Si test xfail / skip → ticket référencé en commentaire

---

**Fin du document — 53-tests-strategy.md**

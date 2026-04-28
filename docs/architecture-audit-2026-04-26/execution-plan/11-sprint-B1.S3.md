# Sprint B1.S3 — KMS + envelope encryption

> **STATUT** : ⏳ À démarrer après B1.S2
> **DURÉE MAX** : 2 semaines
> **OWNER** : Dev1 (lead Bloc 1) — collaboration Lead pour choix vendor KMS
> **BLOQUE** : B2.S5 (auth_factor TOTP encrypted), B4.S5 (PII chiffrement), B6.S2 (audit HMAC)
> **DÉPEND DE** : B1.S2 (RLS active — KMS context inclut tenant_id)
> **OBJECTIF** : Mettre en place le service KMS (Key Management Service) avec envelope encryption pattern : KEK gérée par AWS KMS / Hashicorp Vault, DEK générée par-record et chiffrée par KEK, AAD = `tenant_id + entity + record_id`.

## Vue d'ensemble

| Story | Description | Estimation | Bloque |
|---|---|---|---|
| **B1.S3.T1** | Choix vendor KMS (AWS KMS vs Vault) + provisioning | 1 j | T2 |
| **B1.S3.T2** | `app/core/crypto.py` — KMSClient + EncryptedField | 1.5 j | T3 + B2.S5/B4.S5 |
| **B1.S3.T3** | Outbox pattern transactionnel (table `outbox_events` créée B1.S3 — naming pluriel-suffixé cohérent CaroCorp) | 1.5 j | B6.S2 audit |
| **B1.S3.T4** | Test debt KMS (R21 — 78 fails) cleanup | 2 j | merge B2 |

**Total effort** : 6 jours-homme.

---

# Story B1.S3.T1 — Choix vendor KMS + provisioning

## Contexte

**Sévérité** : P0 — bloque tout chiffrement enveloppe DEVUP
**Décision** : Phase 1 §6.2.7 architecture-cible.md

### Description

Trade-off vendor :

| Vendor | Pros | Cons |
|---|---|---|
| **AWS KMS** | Géré (zero-ops), audit CloudTrail intégré, FIPS 140-2 niveau 3 | Lock-in AWS, coût ~$1/key/mois × N tenants × N keys |
| **Hashicorp Vault** | On-premise possible, multi-cloud, transit secrets engine | Ops à maintenir (HA, unsealing, backup), TCO élevé |
| **Mock dev only** | Rapidité dev | Inacceptable prod |

**Recommandation Lead** : AWS KMS pour DEVUP (zéro-ops, audit centralisé, scalable jusqu'à 1000+ tenants). Vault si exigence on-prem client (Splendid à confirmer).

## Solution

```python
# app/core/crypto/kms_aws.py (NOUVEAU)
import boto3
from cryptography.fernet import Fernet


class AWSKMSClient:
    """Client AWS KMS avec envelope encryption.

    Convention :
    - 1 KEK (Customer Master Key) par environnement (dev/staging/prod)
    - DEK générée par-record (Data Encryption Key)
    - AAD = JSON {"tenant_id": int, "entity": str, "record_id": int}
    """
    def __init__(self, kek_alias: str, region: str = "eu-west-1"):
        self.client = boto3.client("kms", region_name=region)
        self.kek_alias = kek_alias  # ex: "alias/devup-prod-kek"

    async def generate_dek(self, context: dict) -> tuple[bytes, bytes]:
        """Génère une DEK (256 bits) chiffrée par KEK.

        Returns: (plaintext_dek, encrypted_dek)
        plaintext_dek : à utiliser pour chiffrer puis OUBLIER (jamais stocké)
        encrypted_dek : à stocker en DB (récupérable via decrypt_dek)
        """
        response = self.client.generate_data_key(
            KeyId=self.kek_alias,
            KeySpec="AES_256",
            EncryptionContext={k: str(v) for k, v in context.items()},
        )
        return response["Plaintext"], response["CiphertextBlob"]

    async def decrypt_dek(self, encrypted_dek: bytes, context: dict) -> bytes:
        """Déchiffre une DEK avec AAD validation.

        Si context différent de celui d'encryption → InvalidCiphertextException.
        """
        response = self.client.decrypt(
            CiphertextBlob=encrypted_dek,
            EncryptionContext={k: str(v) for k, v in context.items()},
        )
        return response["Plaintext"]
```

### Provisioning AWS

```bash
# tools/kms_provision_prod.sh
aws kms create-key \
    --description "DEVUP prod KEK — envelope encryption" \
    --key-usage ENCRYPT_DECRYPT \
    --customer-master-key-spec SYMMETRIC_DEFAULT \
    --tags TagKey=env,TagValue=prod TagKey=managed_by,TagValue=devup

aws kms create-alias \
    --alias-name alias/devup-prod-kek \
    --target-key-id <key-id-from-output>

# Rotation automatique annuelle
aws kms enable-key-rotation --key-id alias/devup-prod-kek
```

## Definition of Done

- [ ] AWS KMS keys créées en dev/staging/prod
- [ ] Aliases `alias/devup-{env}-kek` configurés
- [ ] Rotation automatique activée (1 an)
- [ ] CloudTrail audit configuré (compliance SOC2)
- [ ] IAM role `devup-app-{env}` avec permission `kms:GenerateDataKey` + `kms:Decrypt` uniquement sur cette KEK

## Risque

- Probabilité 2, impact 4 → score 8 MEDIUM
- Mitigation : test E2E avec vrai AWS KMS en staging avant prod (pas de mock)

---

# Story B1.S3.T2 — `EncryptedField` SQLAlchemy custom type

## Contexte

**Sévérité** : P0 — type Python utilisé partout (Customer.notes, AuthFactor.encrypted_secret, etc.)

### Description

Type SQLAlchemy custom qui chiffre/déchiffre transparent à l'ORM, avec AAD KMS.

## Solution

```python
# app/core/crypto/encrypted_field.py
from sqlalchemy.types import TypeDecorator, LargeBinary
from cryptography.fernet import Fernet

from app.core.crypto.kms_aws import AWSKMSClient


_kms_client: Optional[AWSKMSClient] = None


def get_kms_client() -> AWSKMSClient:
    global _kms_client
    if _kms_client is None:
        _kms_client = AWSKMSClient(kek_alias=settings.KMS_KEK_ALIAS)
    return _kms_client


class EncryptedField(TypeDecorator):
    """Type SQLAlchemy : chiffrement automatique avec KMS envelope.

    Usage :
        class Customer(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
            phone_encrypted: Mapped[Optional[str]] = mapped_column(
                EncryptedField(context_entity="customer", context_field="phone"),
                nullable=True,
            )

    Le contexte AAD inclut automatiquement :
    - tenant_id (depuis _request_tenant_var)
    - entity (paramètre constructeur)
    - record_id (id de la row, après flush)
    """
    impl = LargeBinary
    cache_ok = True

    def __init__(self, context_entity: str, context_field: str, **kwargs):
        super().__init__(**kwargs)
        self.context_entity = context_entity
        self.context_field = context_field

    def process_bind_param(self, value: Optional[str], dialect):
        """Appelé avant INSERT/UPDATE — chiffre la valeur."""
        if value is None:
            return None
        from app.core.database import _request_tenant_var
        tenant_id = _request_tenant_var.get(None)
        if tenant_id is None:
            raise RuntimeError(
                "EncryptedField requires tenant_context (set_tenant_context not called)"
            )

        kms = get_kms_client()
        context = {
            "tenant_id": tenant_id,
            "entity": self.context_entity,
            "field": self.context_field,
        }
        plaintext_dek, encrypted_dek = await kms.generate_dek(context)
        cipher = Fernet(base64.urlsafe_b64encode(plaintext_dek[:32]))
        encrypted_value = cipher.encrypt(value.encode("utf-8"))

        # Format storage : encrypted_dek + encrypted_value
        return encrypted_dek + b"::" + encrypted_value

    def process_result_value(self, value: Optional[bytes], dialect):
        """Appelé après SELECT — déchiffre."""
        if value is None:
            return None
        from app.core.database import _request_tenant_var
        tenant_id = _request_tenant_var.get(None)
        if tenant_id is None:
            return None  # Fail-closed — pas de tenant context = pas de déchiffrement

        kms = get_kms_client()
        context = {
            "tenant_id": tenant_id,
            "entity": self.context_entity,
            "field": self.context_field,
        }
        encrypted_dek, encrypted_value = value.split(b"::", 1)
        plaintext_dek = await kms.decrypt_dek(encrypted_dek, context)
        cipher = Fernet(base64.urlsafe_b64encode(plaintext_dek[:32]))
        return cipher.decrypt(encrypted_value).decode("utf-8")
```

## Tests

```python
@pytest.mark.asyncio
async def test_encrypted_field__encrypt_decrypt_round_trip(db, tenant, kms_mock):
    """EncryptedField roundtrip avec contexte tenant."""
    from app.models import Customer
    from app.core.database import tenant_context

    with tenant_context(tenant.id):
        customer = Customer(
            nom="Dupont",
            phone_encrypted="+33612345678",  # Chiffré au flush
            tenant_id=tenant.id,
        )
        db.add(customer)
        await db.flush()
        await db.refresh(customer)

        # Lecture déchiffrée transparente
        assert customer.phone_encrypted == "+33612345678"


@pytest.mark.asyncio
async def test_encrypted_field__cross_tenant_decrypt__fails(db, tenant, other_tenant, kms_mock):
    """Tenter de déchiffrer avec mauvais contexte AAD → InvalidCiphertextException."""
    from app.models import Customer
    from app.core.database import tenant_context

    with tenant_context(tenant.id):
        customer = Customer(nom="A", phone_encrypted="+33611111111", tenant_id=tenant.id)
        db.add(customer)
        await db.flush()
        customer_id = customer.id

    # Tente lecture sous tenant B → AAD mismatch → exception
    with tenant_context(other_tenant.id):
        with pytest.raises(Exception):  # InvalidCiphertextException AWS KMS
            await db.execute(select(Customer).filter_by(id=customer_id))
```

## Definition of Done

- [ ] `EncryptedField` type implémenté + 5 tests unit/intégration
- [ ] Documentation `docs/encryption-conventions.md`
- [ ] B2.S5 (auth_factor) + B4.S5 (PII) peuvent l'utiliser

## Risque

- Probabilité 3, impact 4 → score 12 HIGH
- Mitigation : test sous charge avec vraie AWS KMS (latence DEK ~10ms × N rows = goulot)

---

# Story B1.S3.T3 — Outbox pattern transactionnel

## Contexte

**Migration** : `c1d2e3f4a5b9` (cf. `51-alembic-migrations.md` ligne 17)
**Sévérité** : P0 — bloque B6.S2 audit refondu

### Description

Cf. `50-sql-schema.md §1.2` pour la table `outbox_events` complète. Cette story crée la table + worker dispatcher Celery.

## Solution

Migration table : déjà spécifiée dans `50-sql-schema.md §1.2` (BIGSERIAL, tenant_id NULLABLE, status, retry_count, etc.).

```python
# app/services/outbox.py (NOUVEAU)
class OutboxService:
    async def enqueue(
        self,
        db: AsyncSession,
        event_type: str,
        aggregate_type: str,
        aggregate_id: Optional[int],
        payload: dict,
        actor_account_id: Optional[int] = None,
        actor_api_key_id: Optional[int] = None,
        actor_type: str = "system",
    ) -> int:
        """Enqueue un event dans la même transaction que la mutation métier.

        Pattern Q4=A : pas de pub vers RabbitMQ ici, juste insert.
        Le worker dispatch_outbox_task lit et publie async.
        """
        from app.core.database import _request_tenant_var
        from app.models import OutboxEvent

        event = OutboxEvent(
            tenant_id=_request_tenant_var.get(None),  # NULL pour events globaux
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            actor_account_id=actor_account_id,
            actor_api_key_id=actor_api_key_id,
            actor_type=actor_type,
            status="pending",
        )
        db.add(event)
        await db.flush()
        return event.id


# app/tasks/outbox.py (NOUVEAU)
@celery_app.task(name="app.tasks.outbox.dispatch_outbox", bind=True, queue="outbox")
async def dispatch_outbox_task(self):
    """Worker qui dispatche les events outbox vers RabbitMQ + audit_log.

    Polling 5s. SELECT FOR UPDATE SKIP LOCKED pour parallélisme.
    """
    async with AsyncSessionLocal() as db:
        # Lit batch de 100 events pending (ou retry)
        result = await db.execute(text("""
            SELECT * FROM outbox_events
            WHERE status IN ('pending', 'retry')
            AND (next_retry_at IS NULL OR next_retry_at <= NOW())
            ORDER BY created_at
            LIMIT 100
            FOR UPDATE SKIP LOCKED
        """))
        events = result.fetchall()

        for event in events:
            try:
                # 1. Publier vers RabbitMQ (B6.S7 — pour l'instant Redis)
                await broker_client.publish(event.event_type, event.payload)
                # 2. Insérer dans audit_log si entity audit
                if event.event_type.endswith("Created") or event.event_type.endswith("Updated"):
                    await audit_service.log_from_outbox(db, event)
                # 3. Marquer dispatched
                await db.execute(text("""
                    UPDATE outbox_events SET status = 'dispatched', dispatched_at = NOW()
                    WHERE id = :id
                """), {"id": event.id})
            except Exception as e:
                # Retry avec backoff exponentiel
                await db.execute(text("""
                    UPDATE outbox_events SET
                        status = CASE WHEN dispatch_attempts >= 5 THEN 'dead_letter' ELSE 'retry' END,
                        dispatch_attempts = dispatch_attempts + 1,
                        last_dispatch_error = :error,
                        next_retry_at = NOW() + INTERVAL '2 seconds' * (2 ^ dispatch_attempts)
                    WHERE id = :id
                """), {"id": event.id, "error": str(e)[:500]})

        await db.commit()
```

## Definition of Done

- [ ] Migration `c1d2e3f4a5b9` (table outbox) appliquée
- [ ] `OutboxService.enqueue()` API stable
- [ ] Worker `dispatch_outbox_task` en celery_app, queue `outbox` (cf. 55-perf §6.3 — queue dédiée pour isoler polling 5s du throughput général)
- [ ] Test E2E : mutation métier → enqueue → dispatcher → audit_log peuplé
- [ ] Test E2E : mutation rollback → outbox event aussi rollback (atomique)
- [ ] DLQ `dead_letter` après 5 retries

## Risque

- Probabilité 2, impact 4 → score 8 MEDIUM

---

# Story B1.S3.T4 — Cleanup test debt KMS (R21)

## Contexte

**R21** (cf. `05-risk-register.md`) : 78 tests KMS fail dans la baseline (mémoire `tech-debt-tests.md`). Bloque CI verte avant merge B2.

### Description

Cf. `53-tests-strategy.md §3.2` story TEST-DEBT-02 :
- Fixture `kms_mock` context manager wireé dans conftest
- Migration tests obsolètes vers `EncryptedField` API
- Wire `monkeypatch` dans `tests/conftest.py:307-320` (déjà spec — vérifier exécution)

## Definition of Done

- [ ] Fixture `kms_mock` opérationnelle dans tous les tests
- [ ] 78 fails KMS → 0 fails (validation `pytest -k kms`)
- [ ] R21 marqué résolu dans risk register

## Risque

- Probabilité 1, impact 2 → score 2 LOW (effort connu, pas de surprise architecturale)

---

## Critères de succès Sprint B1.S3

- [ ] AWS KMS provisionné dev/staging/prod
- [ ] `EncryptedField` opérationnel (5 tests verts)
- [ ] Outbox table + worker dispatcher livrés
- [ ] 78 tests KMS désormais verts
- [ ] B2.S5 (auth_factor TOTP encrypted) + B4.S5 (PII) débloqués

---

**Fin du document — 11-sprint-B1.S3.md**

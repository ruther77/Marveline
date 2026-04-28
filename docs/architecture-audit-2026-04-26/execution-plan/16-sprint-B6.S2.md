# Sprint B6.S2 — Audit refondu + HMAC chaîné + RGPD Art.15

> **STATUT** : ⏳ À démarrer après B6.S1
> **DURÉE MAX** : 2 semaines
> **OWNER** : Dev1
> **BLOQUE** : B6.S3 (FF audit), B6.S6 (mTLS observability réutilise audit chain)
> **DÉPEND DE** : B1.S3 (KMS pour `EncryptedField`), B3.S5 (EmailGateway pour notification export)
> **OBJECTIF** : Refondre l'audit en cassant les 6 frictions structurelles : middleware mute audit hors TX (drop), HMAC ne couvre pas `changes` (refait avec chaînage blockchain), `SENSITIVE_PATTERNS` incomplets (étendu), `/auth/login` exclu (réintégré + masking password), pas de PII envelope sur `changes` (`EncryptedField`), pas d'export RGPD Art.15 (Celery + S3 signed URL), pas de purge >7y (Celery cron mensuel).

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B6.S2.T1** | TR-66 — Audit service-level dans TX métier + Outbox + drop middleware mutations + `@audit_action` decorator | P0 | 2 j | T2, T3 |
| **B6.S2.T2** | TR-67 — HMAC chaîné couvrant `changes` + advisory lock per-tenant + DB triggers immutability + `verify_audit_chain` nightly | P0 | 2 j | T6 |
| **B6.S2.T3** | TR-68/TR-69 — `SENSITIVE_READ_PATTERNS` étendu (10 patterns) + `ATTEMPT_DENIED` 4xx + `/auth/login` réintégré masking | P0 | 1 j | aucun |
| **B6.S2.T4** | TR-70 — `EncryptedField` KMS sur `AuditLog.changes` + `AuditLog.description` + scope `audit:read_pii` | P0 | 1.5 j | aucun |
| **B6.S2.T5** | TR-71 — Export RGPD Art.15 Celery + S3 signed URL 24h (Q38=A) | P1 | 1.5 j | aucun |
| **B6.S2.T6** | TR-72 — Purge audit >7y Celery cron + backup S3 + verify chain pré-DELETE | P1 | 1 j | aucun |
| **B6.S2.T7** | F1004 — `EntityType` enum sur `AuditLog.entity_type` (drop string libre) | P1 | 0.5 j | aucun |

**Total effort** : 9.5 jours-homme.

---

# Story B6.S2.T1 — Audit service-level dans TX métier (TR-66)

## Contexte

**Friction** : TR-66 (cf. `architecture-cible.md §6.1`)
**Sévérité** : P0 — `AuditMiddleware` ouvre TX parallèle → audit perdu silencieusement quand audit échoue OU TX métier rollback (audit committé)

### Description

Aujourd'hui : `app/middleware/audit.py` capture la requête et l'écrit dans une session SQLAlchemy distincte. Conséquences :
- **Audit fantôme** : TX métier rollback → audit committé → état inconsistant
- **Audit perdu** : audit DB error → middleware swallow exception → action non auditée
- **Pas de capture changes** : middleware ne connaît pas le diff `before/after`

Cible :
1. Drop écriture mutations depuis middleware (garde seulement READ patterns)
2. Service-level `AuditService.log(...)` appelé dans la TX métier (même session)
3. Outbox event `AuditLogCreated` publié dans même TX (durabilité asynchrone)
4. Décorateur `@audit_action(entity='Customer')` factorise le pattern

## Solution

### Service AuditLogger

```python
# app/services/audit/logger.py (NEW)
class AuditService:
    def __init__(self, db: AsyncSession, hmac_signer: HmacSigner):
        self.db = db
        self.hmac_signer = hmac_signer

    async def log(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        changes: dict | None,
        description: str,
        account_id: UUID | None,
        tenant_id: int,
        request_id: str | None = None,
    ) -> AuditLog:
        """Insert dans la TX métier courante. Pas de TX parallèle."""
        # Lecture dernier hmac (advisory lock per tenant — T2)
        await self.db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext('audit:tenant:' || :tid))"),
            {"tid": tenant_id},
        )
        prev_hmac = await self.db.scalar(
            select(AuditLog.hmac_signature)
            .where(AuditLog.tenant_id == tenant_id)
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )

        canonical = {
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "changes": changes,
            "description": description,
            "account_id": str(account_id) if account_id else None,
            "tenant_id": tenant_id,
            "request_id": request_id,
            "created_at": datetime.now(UTC).isoformat(),
        }
        new_hmac = self.hmac_signer.compute(prev_hmac, canonical)

        log = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            changes=changes,
            description=description,
            account_id=account_id,
            tenant_id=tenant_id,
            request_id=request_id,
            prev_hmac=prev_hmac,
            hmac_signature=new_hmac,
        )
        self.db.add(log)
        # Outbox event durabilité asynchrone
        self.db.add(OutboxEvent(
            event_type="AuditLogCreated",
            aggregate_id=str(log.id),
            tenant_id=tenant_id,
            payload={"action": action, "entity_type": entity_type, "entity_id": entity_id},
        ))
        return log
```

### Décorateur

```python
# app/services/audit/decorator.py (NEW)
def audit_action(entity_type: str, action_template: str = "{op}"):
    """Décore une méthode service pour capturer audit auto.
    
    Usage:
        @audit_action(entity_type="Customer", action_template="customer.{op}")
        async def update_customer(self, customer_id, changes, actor_id, tenant_id):
            ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(self, *args, **kwargs):
            entity_id = kwargs.get("customer_id") or kwargs.get("id") or args[0]
            actor_id = kwargs.get("actor_id")
            tenant_id = kwargs.get("tenant_id")
            # Capture before
            before = await self._snapshot(entity_id) if hasattr(self, "_snapshot") else None
            result = await fn(self, *args, **kwargs)
            # Capture after
            after = await self._snapshot(entity_id) if hasattr(self, "_snapshot") else None
            changes = compute_diff(before, after)
            # Audit
            await self.audit.log(
                action=action_template.format(op=fn.__name__),
                entity_type=entity_type,
                entity_id=str(entity_id),
                changes=changes,
                description=f"{fn.__name__} on {entity_type}({entity_id})",
                account_id=actor_id,
                tenant_id=tenant_id,
            )
            return result
        return wrapper
    return decorator
```

### Drop mutations depuis middleware

```python
# app/middleware/audit.py (refacto)
class AuditMiddleware:
    """Garde seulement READ tracking (sensitive patterns) + ATTEMPT_DENIED.
    
    Toute mutation est auditée côté service via AuditService dans la TX métier.
    """
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Read tracking (T3)
        if self._is_sensitive_read(request, response):
            await self._log_read(request, response)
        # Attempt denied (T3)
        if response.status_code in ATTEMPT_DENIED_STATUSES:
            await self._log_attempt_denied(request, response)
        return response
```

### Tests

```python
async def test_audit_in_same_tx_as_business(db, customer_service, audit_service):
    """Si rollback TX métier → audit aussi rollback."""
    with pytest.raises(ValueError):
        async with db.begin():
            await customer_service.update(customer_id, name="X")  # audit logged
            raise ValueError("rollback")
    # Audit ne doit pas exister
    audits = await db.scalars(
        select(AuditLog).where(AuditLog.entity_id == str(customer_id))
    )
    assert len(audits.all()) == 0

async def test_audit_decorator_captures_changes(db, customer_service):
    customer = await customer_service.create(name="A", tenant_id=1)
    await customer_service.update(customer.id, name="B", actor_id=user.id, tenant_id=1)

    log = await db.scalar(select(AuditLog).where(AuditLog.entity_id == str(customer.id)))
    assert log.changes == {"name": {"old": "A", "new": "B"}}
```

## DoD

- [ ] `AuditService.log()` insère dans TX métier
- [ ] Décorateur `@audit_action` capture changes auto
- [ ] Middleware audit n'écrit plus mutations (juste reads + denied)
- [ ] Outbox event `AuditLogCreated` publié dans même TX
- [ ] Test : rollback TX métier → audit aussi rollback (cohérence)
- [ ] Test : décorateur capture diff `before/after`

---

# Story B6.S2.T2 — HMAC chaîné blockchain (TR-67)

## Contexte

**Friction** : TR-67, F1001, F1011 (cf. `architecture-cible.md §6.2.4`)
**Sévérité** : P0 — théâtre de sécurité : HMAC actuel ne couvre pas `changes` → attaquant DB-direct mute le JSON sans invalider

### Description

Cible :
1. `AuditLog.prev_hmac` + `AuditLog.hmac_signature` (chaînage blockchain)
2. `canonical_payload` JSON canonique de TOUS les champs (`action, entity_type, entity_id, changes, description, account_id, tenant_id, request_id, created_at`)
3. Advisory lock per `tenant_id` durant insert (chaîne strictement séquentielle)
4. DB triggers BEFORE UPDATE/DELETE → exception (immutable)
5. `verify_audit_chain_task` nightly + alerte rupture
6. KMS-managed HMAC key avec versioning (`v1$hmac` format)

## Solution

### Migration

```python
# alembic/versions/h1a2b3c4d5f1_audit_hmac_chain.py
def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("prev_hmac", sa.String(64), nullable=True))
    op.add_column("audit_logs", sa.Column("hmac_signature", sa.String(80), nullable=False, server_default=""))
    # Index pour lookup chaîne per-tenant
    op.create_index("ix_audit_logs_tenant_created", "audit_logs", ["tenant_id", "created_at"])

    # Trigger immutability (cohérent Bloc 3 §3.2.5)
    op.execute(text("""
        CREATE OR REPLACE FUNCTION audit_logs_immutable_check()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs_immutable: UPDATE/DELETE forbidden on audit (id=%)', OLD.id;
        END $$ LANGUAGE plpgsql;
    """))
    op.execute(text("""
        CREATE TRIGGER trg_audit_logs_immutable
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION audit_logs_immutable_check()
    """))
```

### Signer KMS-versioned

```python
# app/services/audit/hmac_signer.py (NEW)
class HmacSigner:
    """KMS-managed HMAC key with versioning (v1$hmac, v2$hmac after rotation)."""

    def __init__(self, kms_client, current_version: str = "v1"):
        self.kms = kms_client
        self.current_version = current_version

    def compute(self, prev_hmac: str | None, canonical_payload: dict) -> str:
        """Format: 'v1$<sha256_hex>'."""
        key = self.kms.get_secret(f"audit_hmac_{self.current_version}")
        canonical_json = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
        msg = ((prev_hmac or "") + canonical_json).encode()
        digest = hmac.new(key, msg, "sha256").hexdigest()
        return f"{self.current_version}${digest}"

    def verify(self, log: AuditLog, prev_log: AuditLog | None) -> bool:
        """Re-compute and compare. Handle versioned keys for rotation safety."""
        version, _, expected_digest = log.hmac_signature.partition("$")
        key = self.kms.get_secret(f"audit_hmac_{version}")
        canonical_payload = self._build_canonical(log)
        canonical_json = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
        prev_h = prev_log.hmac_signature if prev_log else None
        msg = ((prev_h or "") + canonical_json).encode()
        actual = hmac.new(key, msg, "sha256").hexdigest()
        return hmac.compare_digest(actual, expected_digest)
```

### Verify chain task

```python
# app/workers/tasks/verify_audit_chain.py (NEW)
@shared_task(name="verify_audit_chain")
def verify_audit_chain_task():
    """Nightly — parcourt audit_logs per-tenant, alerte rupture."""
    async def _run():
        async with AsyncSessionLocal() as db:
            tenants = await db.scalars(select(Tenant.id))
            for tenant_id in tenants.all():
                logs = await db.scalars(
                    select(AuditLog)
                    .where(AuditLog.tenant_id == tenant_id)
                    .order_by(AuditLog.created_at)
                )
                prev = None
                for log in logs.all():
                    if not signer.verify(log, prev):
                        # Outbox alert ops
                        db.add(OutboxEvent(
                            event_type="AuditChainBroken",
                            aggregate_id=str(log.id),
                            tenant_id=tenant_id,
                            payload={"audit_id": str(log.id), "expected_prev": prev.id if prev else None},
                        ))
                        logger.error(
                            "AUDIT_CHAIN_BROKEN",
                            tenant_id=tenant_id, audit_id=str(log.id),
                            prev_id=str(prev.id) if prev else None,
                        )
                    prev = log
            await db.commit()
    asyncio.run(_run())
```

### Tests

```python
async def test_audit_chain_intact(db, audit_service, tenant):
    log1 = await audit_service.log(action="a1", entity_type="X", entity_id="1", ...)
    log2 = await audit_service.log(action="a2", entity_type="X", entity_id="2", ...)
    assert log2.prev_hmac == log1.hmac_signature

async def test_audit_immutable_db_trigger(db, audit_service):
    log = await audit_service.log(action="a", entity_type="X", entity_id="1", ...)
    with pytest.raises(IntegrityError, match="audit_logs_immutable"):
        await db.execute(update(AuditLog).where(AuditLog.id == log.id).values(action="hacked"))
    with pytest.raises(IntegrityError, match="audit_logs_immutable"):
        await db.execute(delete(AuditLog).where(AuditLog.id == log.id))

async def test_verify_chain_detects_tampering(db, audit_service):
    log = await audit_service.log(action="a", entity_type="X", entity_id="1", ...)
    # Tamper via raw SQL bypass trigger (impossible normalement, mais simulate corrupt DB)
    await db.execute(text("ALTER TABLE audit_logs DISABLE TRIGGER trg_audit_logs_immutable"))
    await db.execute(text("UPDATE audit_logs SET action='tampered' WHERE id=:id"), {"id": str(log.id)})
    await db.execute(text("ALTER TABLE audit_logs ENABLE TRIGGER trg_audit_logs_immutable"))

    verify_audit_chain_task.apply().get()
    # Outbox event AuditChainBroken doit exister
    event = await db.scalar(select(OutboxEvent).where(OutboxEvent.event_type == "AuditChainBroken"))
    assert event is not None
```

## DoD

- [ ] Migration `prev_hmac` + `hmac_signature` + trigger immutable
- [ ] `HmacSigner` avec versioning KMS (`v1$<digest>`)
- [ ] Advisory lock per-tenant durant insert (chaîne séquentielle)
- [ ] Task `verify_audit_chain` nightly + Outbox alert
- [ ] Test chain intacte cross-logs
- [ ] Test trigger immutable bloque UPDATE/DELETE
- [ ] Test tampering détecté par verify

---

# Story B6.S2.T3 — `SENSITIVE_PATTERNS` étendu + `/auth/login` réintégré (TR-68/TR-69, F1002)

## Contexte

**Friction** : TR-68, TR-69, F1002 (audit refondu vs Sprint 1 patch tactique)
**Sévérité** : P0 — Sprint 1 a retiré `/auth/login` de `EXCLUDED_PATHS` (patch tactique). Cette story livre la version propre middleware-level avec masking password + extension SENSITIVE_PATTERNS.

### Description

Cible :
- `SENSITIVE_READ_PATTERNS` étendu à 10 patterns (vs 3 actuels)
- Capture `ATTEMPT_DENIED` pour status 401/403/422
- POST `/auth/login` 401 → audit capturé avec `password=***` masqué

## Solution

```python
# app/constants/audit.py
SENSITIVE_READ_PATTERNS = [
    r"^/api/v1/customers/\d+",
    r"^/api/v1/customers/\d+/history",
    r"^/api/v1/invoices/\d+",
    r"^/api/v1/users/\d+",
    r"^/api/v1/reservations/\d+",
    r"^/api/v1/devis/\d+",
    r"^/api/v1/mfa/\w+",
    r"^/api/v1/sessions/\d+",
    r"^/api/v1/loyalty/members/\d+",
    r"^/api/v1/audit",  # méta-audit
]
ATTEMPT_DENIED_STATUSES = {401, 403, 422}

PASSWORD_MASKING_FIELDS = {"password", "current_password", "new_password", "totp_code", "backup_code"}

# app/middleware/audit.py
def _mask_sensitive_body(body: dict) -> dict:
    return {k: "***" if k in PASSWORD_MASKING_FIELDS else v for k, v in body.items()}

class AuditMiddleware:
    async def dispatch(self, request: Request, call_next):
        body = None
        if request.method == "POST" and request.url.path in ("/api/v1/auth/login", "/api/v1/mfa/verify"):
            body = await request.json()
        response = await call_next(request)
        
        if self._is_sensitive_read(request, response):
            await self._log_read(request, response)
        if response.status_code in ATTEMPT_DENIED_STATUSES:
            masked_body = _mask_sensitive_body(body) if body else None
            await self._log_attempt_denied(request, response, masked_body)
        return response
```

### Test

```python
async def test_login_failed_audited_with_masked_password(client, db):
    response = await client.post("/api/v1/auth/login", json={"email": "x@y.com", "password": "secret123"})
    assert response.status_code == 401
    log = await db.scalar(
        select(AuditLog).where(AuditLog.action == "ATTEMPT_DENIED", AuditLog.entity_type == "auth")
    )
    assert log is not None
    assert "secret123" not in str(log.changes)
    assert "***" in str(log.changes)

async def test_sensitive_read_audited(client, db, customer):
    await client.get(f"/api/v1/customers/{customer.id}")
    log = await db.scalar(
        select(AuditLog).where(AuditLog.action == "READ", AuditLog.entity_id == str(customer.id))
    )
    assert log is not None
```

## DoD

- [ ] 10 patterns `SENSITIVE_READ_PATTERNS`
- [ ] `ATTEMPT_DENIED_STATUSES` = {401, 403, 422}
- [ ] Body masking sur fields sensibles
- [ ] `/auth/login` 401 → audit capturé avec password masqué
- [ ] Test : login fail → audit `ATTEMPT_DENIED` ; password absent du JSON

---

# Story B6.S2.T4 — `EncryptedField` sur `AuditLog.changes` + scope `audit:read_pii` (TR-70)

## Contexte

**Friction** : TR-70, F1014
**Sévérité** : P0 — RGPD : audit log peut contenir PII (email, phone, notes) en clair

### Description

Cible : `EncryptedField(KMSContext)` sur `AuditLog.changes` (JSONB chiffré au repos) et `AuditLog.description`. Endpoint `GET /audit` masque `changes` sauf si scope `audit:read_pii`.

## Solution

```python
# app/models/audit_log.py
class AuditLog(Base):
    # ... existing
    changes: Mapped[dict | None] = mapped_column(EncryptedField(KMSContext("audit:changes"), JSONB))
    description: Mapped[str] = mapped_column(EncryptedField(KMSContext("audit:description"), Text))

# app/api/v1/endpoints/audit.py
@router.get("/audit")
async def list_audit(
    user: User = Depends(require_scope(Scope.AUDIT_READ)),
    has_pii: bool = Depends(check_scope(Scope.AUDIT_READ_PII, optional=True)),
):
    logs = await audit_service.list(...)
    return [
        AuditLogRead(
            id=l.id, action=l.action, entity_type=l.entity_type, entity_id=l.entity_id,
            changes=l.changes if has_pii else "[encrypted]",
            description=l.description if has_pii else "[masked]",
        )
        for l in logs
    ]

# app/constants/security.py
class Scope(str, Enum):
    # ... existing
    AUDIT_READ = "audit:read"
    AUDIT_READ_PII = "audit:read_pii"  # NEW
```

### Migration backfill

```python
# Celery task (one-shot)
@shared_task(name="migrate_audit_pii_encryption")
def migrate_audit_pii_encryption_task():
    """Chiffre les rows existantes."""
    # Lis batch 1000, re-écrit via SQLAlchemy ORM (déclenche EncryptedField)
```

### Tests

```python
async def test_audit_changes_encrypted_at_rest(db, audit_service):
    log = await audit_service.log(action="a", changes={"email": "user@example.com"}, ...)
    # Lecture raw SQL → JSONB chiffré
    raw = await db.execute(text("SELECT changes FROM audit_logs WHERE id = :id"), {"id": str(log.id)})
    raw_value = raw.scalar()
    assert "user@example.com" not in str(raw_value)

async def test_audit_endpoint_masks_changes_without_pii_scope(client_no_pii):
    response = await client_no_pii.get("/api/v1/audit")
    assert all(log["changes"] == "[encrypted]" for log in response.json())

async def test_audit_endpoint_returns_changes_with_pii_scope(client_with_pii):
    response = await client_with_pii.get("/api/v1/audit")
    assert any(log["changes"] != "[encrypted]" for log in response.json())
```

## DoD

- [ ] `EncryptedField` sur `changes` + `description`
- [ ] Scope `audit:read_pii` dans Scope enum
- [ ] Endpoint `/audit` masque sans scope, expose avec scope
- [ ] Celery task migration backfill
- [ ] Test : raw SQL → données chiffrées illisibles
- [ ] Test : endpoint masque/expose selon scope

---

# Story B6.S2.T5 — Export RGPD Article 15 (TR-71)

## Contexte

**Friction** : TR-71 (cf. `architecture-cible.md §6.2.7`)
**Décision** : Q38=A — Async Celery + S3 signed URL 24h

### Description

Cible :
1. Endpoint `POST /me/export?format=csv|json`
2. Celery task aggrège : `Customer + Reservations + Invoices + AuditLog + LoyaltyMember`
3. Export ZIP → S3 signed URL TTL 24h
4. Email user (EmailGateway B3.S5) avec lien

## Solution

```python
# app/api/v1/endpoints/me.py (NEW)
@router.post("/me/export")
async def request_personal_data_export(
    format: Literal["csv", "json"] = "json",
    user: User = Depends(require_authenticated),
):
    task = export_personal_data_task.delay(str(user.account_id), format)
    return {"task_id": task.id, "status": "queued"}

# app/workers/tasks/export_personal_data.py
@shared_task(name="export_personal_data")
def export_personal_data_task(account_id: str, format: str):
    async def _run():
        async with AsyncSessionLocal() as db:
            account = await db.get(Account, UUID(account_id))
            customer = await db.scalar(select(Customer).where(Customer.account_id == account.id))

            # 1. Aggregate
            data = {
                "account": {"email": account.email, "created_at": account.created_at.isoformat()},
                "customer": _serialize_customer(customer),
                "reservations": [_serialize_reservation(r) for r in await _fetch_reservations(db, customer.id)],
                "invoices": [_serialize_invoice(i) for i in await _fetch_invoices(db, customer.id)],
                "audit": [_serialize_audit(a) for a in await _fetch_audit(db, account.id)],
                "loyalty": _serialize_loyalty(await _fetch_loyalty(db, customer.id)),
            }

            # 2. Build ZIP in memory
            buf = BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                if format == "json":
                    zf.writestr("export.json", json.dumps(data, default=str, indent=2))
                else:
                    for section, rows in data.items():
                        zf.writestr(f"{section}.csv", _to_csv(rows))
            buf.seek(0)

            # 3. Upload S3 + signed URL 24h
            key = f"exports/{account.id}/{datetime.now(UTC).isoformat()}.zip"
            await s3.upload_fileobj(buf, settings.S3_EXPORT_BUCKET, key)
            url = await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.S3_EXPORT_BUCKET, "Key": key},
                ExpiresIn=86400,
            )

            # 4. Email user
            await email_gateway.send(
                to=account.email,
                subject="Votre export de données personnelles",
                body_html=render_template("export_ready.html.j2", {"url": url}),
                tenant_id=customer.tenant_id,
            )

            # 5. Audit
            await audit_service.log(
                action="rgpd.export",
                entity_type="Account",
                entity_id=str(account.id),
                description=f"Export RGPD Art.15 ({format})",
                account_id=account.id,
                tenant_id=customer.tenant_id,
            )
    asyncio.run(_run())
```

### Test

```python
async def test_export_request_returns_task_id(client, user):
    response = await client.post("/api/v1/me/export?format=json")
    assert response.status_code == 200
    assert "task_id" in response.json()

async def test_export_aggregates_all_data(db, account, customer, reservation, invoice):
    export_personal_data_task.apply(args=(str(account.id), "json")).get()
    # Verifier audit log RGPD créé
    audit = await db.scalar(
        select(AuditLog).where(AuditLog.action == "rgpd.export", AuditLog.entity_id == str(account.id))
    )
    assert audit is not None
```

## DoD

- [ ] Endpoint `POST /me/export` async
- [ ] Celery task aggrège 5 sources
- [ ] ZIP S3 + signed URL TTL 24h
- [ ] Email user via EmailGateway
- [ ] Audit log RGPD créé
- [ ] Test E2E : request → task → ZIP S3 + email envoyé

---

# Story B6.S2.T6 — Purge audit >7y (TR-72)

## Contexte

**Friction** : TR-72
**Sévérité** : P1 — croissance illimitée table audit

### Description

Cible :
1. Celery cron mensuel (1er du mois 02:00)
2. Avant DELETE : `verify_audit_chain` (chaîne intacte)
3. Backup S3 chiffré (audit ultérieur possible)
4. DELETE batch 1000 avec advisory lock

## Solution

```python
# app/workers/tasks/purge_audit.py
@shared_task(name="purge_audit_logs_older_than_7y")
def purge_audit_logs_older_than_7y_task():
    async def _run():
        cutoff = datetime.now(UTC) - relativedelta(years=7)
        async with AsyncSessionLocal() as db:
            # 1. Verify chain integrity FIRST
            await verify_audit_chain_task.apply_async().get()

            # 2. Backup to S3 (encrypted) per tenant
            tenants = await db.scalars(select(Tenant.id))
            for tenant_id in tenants.all():
                logs = await db.scalars(
                    select(AuditLog).where(
                        AuditLog.tenant_id == tenant_id,
                        AuditLog.created_at < cutoff,
                    )
                )
                if not logs:
                    continue
                # Backup
                key = f"audit_archive/tenant_{tenant_id}/{datetime.now(UTC).isoformat()}.json.gz"
                await s3.put_object(
                    Bucket=settings.S3_AUDIT_ARCHIVE_BUCKET,
                    Key=key,
                    Body=gzip.compress(json.dumps([_serialize(l) for l in logs.all()]).encode()),
                    ServerSideEncryption="aws:kms",
                )
                # 3. DELETE — bypass trigger immutable via cleanup function
                await db.execute(text("""
                    SET LOCAL app.audit_purge_authorized = 'true';
                    DELETE FROM audit_logs WHERE tenant_id = :tid AND created_at < :cutoff;
                """), {"tid": tenant_id, "cutoff": cutoff})

            await db.commit()
    asyncio.run(_run())
```

### Trigger update

```sql
-- Modifie le trigger pour autoriser DELETE seulement si flag session-level
CREATE OR REPLACE FUNCTION audit_logs_immutable_check() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' AND current_setting('app.audit_purge_authorized', true) = 'true' THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'audit_logs_immutable: UPDATE/DELETE forbidden';
END $$ LANGUAGE plpgsql;
```

## DoD

- [ ] Celery cron mensuel `purge_audit_logs_older_than_7y`
- [ ] `verify_audit_chain` exécuté pré-DELETE
- [ ] Backup S3 chiffré KMS
- [ ] Trigger autorise DELETE conditionnel sur flag session-level
- [ ] Test : log >7y backup S3 + supprimé

---

# Story B6.S2.T7 — `EntityType` enum (F1004)

## Contexte

**Friction** : F1004 (vague 5)
**Sévérité** : P1 — `AuditLog.entity_type: String(64)` accepte n'importe quoi → drift entre `Customer` / `customer` / `Customers`

### Description

Cible : ENUM strict avec valeurs canoniques.

## Solution

```python
def upgrade() -> None:
    op.execute(text("""
        CREATE TYPE audit_entity_type AS ENUM (
            'Account', 'User', 'Customer', 'Tenant',
            'Devis', 'Reservation', 'Invoice', 'Vente', 'Deposit',
            'Product', 'Variant', 'Bundle', 'Category',
            'StockItem', 'InventoryMovement',
            'LoyaltyMember', 'PointsLedger',
            'Supplier', 'SupplierOrder',
            'Evenement', 'EventIncident',
            'auth', 'mfa', 'session', 'api_key', 'webauthn', 'rgpd',
            'feature_flag', 'admin'
        )
    """))
    # Backfill normalisation
    op.execute(text("""
        UPDATE audit_logs SET entity_type = INITCAP(entity_type)
        WHERE entity_type ~ '^[a-z]'
    """))
    op.execute(text("""
        ALTER TABLE audit_logs ALTER COLUMN entity_type TYPE audit_entity_type
        USING entity_type::audit_entity_type
    """))
```

```python
# app/constants/audit.py — IMPORTÉ depuis B6.S1.T6 (créé là-bas, juste consommé ici)
from app.constants.audit import EntityType
# Cohérence : l'enum est déjà créé Sprint B6.S1.T6 ; B6.S2.T7 ne fait que créer l'ENUM PostgreSQL
# correspondant et appliquer l'ALTER COLUMN. Pas de redéclaration Python.
```

## DoD

- [ ] ENUM `audit_entity_type` créé
- [ ] Backfill normalisation casse
- [ ] Constants Python alignée
- [ ] Test : insert string non valide → IntegrityError

---

## Critères de succès Sprint B6.S2

- [ ] **TR-66** : audit dans TX métier ; rollback métier = rollback audit
- [ ] **TR-67** : HMAC chaîné couvre `changes` ; trigger immutable ; verify nightly
- [ ] **TR-68/TR-69** : 10 SENSITIVE_READ_PATTERNS + ATTEMPT_DENIED 4xx + login masking
- [ ] **TR-70** : `EncryptedField` sur changes/description + scope `audit:read_pii`
- [ ] **TR-71** : Export RGPD Art.15 async + S3 signed URL 24h
- [ ] **TR-72** : Purge >7y mensuelle + backup S3 chiffré
- [ ] **F1004** : EntityType enum strict
- [ ] Test E2E : tampering DB → verify_audit_chain alerte ops via Outbox

---

**Fin du document — 16-sprint-B6.S2.md**

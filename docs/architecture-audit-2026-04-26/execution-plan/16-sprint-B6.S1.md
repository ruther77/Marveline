# Sprint B6.S1 — Hotfixes cross-cutting (Notification + email Celery + scope print + auto_suspend)

> **STATUT** : ⏳ À démarrer après Bloc 2
> **DURÉE MAX** : 1 semaine
> **OWNER** : Dev1 + Ops
> **BLOQUE** : B6.S2 (audit refondu réutilise EmailGateway), B6.S3 (FF utilise audit refondu)
> **DÉPEND DE** : B3.S5 (EmailGateway Postmark prod livré)
> **OBJECTIF** : Corriger frictions cross-cutting P0 : F848 (Celery email task wrap NotificationService), F849 (TLS+auth SMTP fallback), F1058 (RELANCE-FAKE-SENT-01 — déjà ciblé B3.S5.T4 mais cross-vérifier coverage), F1053 (queue loyalty routée), F1089 (require_scope print), F1055 décision Q39 (auto_suspend_uncertified implémenté réel — compliance SOC2). Refacto Notification model (F848-F851) Mapped + TenantMixin + account_id.

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B6.S1.T1** | F848 — Celery `send_email_task` wrap NotificationService + retry/DLQ | P0 | 1 j | aucun |
| **B6.S1.T2** | F849 — Fallback SMTP TLS + auth obligatoire (`SmtpGateway` cohérent) | P0 | 0.5 j | aucun |
| **B6.S1.T3** | F1053 — Queue `loyalty` routée + worker spécialisé + monitoring | P0 | 0.5 j | aucun |
| **B6.S1.T4** | F1089 — `require_scope(Scope.PRINTER_PRINT)` sur endpoints `/print/*` | P0 | 0.5 j | aucun |
| **B6.S1.T5** | Q39=A / F1055 — `auto_suspend_uncertified` réel + table `access_reviews` | P0 | 2 j | aucun |
| **B6.S1.T6** | F848-F851 — Notification model refacto (Mapped + TenantMixin + account_id) | P1 | 1 j | aucun |
| **B6.S1.T7** | F1004 — `EntityType` enum AuditLog (cohérent B6.S2.T7 mais hotfix prep) | P1 | 0.5 j | B6.S2 |
| **B6.S1.T8** | **Vague 2** — Création table `notification_log` (NEW 50-sql-schema §11.2) + EmailGateway logue automatiquement chaque send | P0 | 0.5 j | aucun |

**Total effort** : 6.5 jours-homme.

---

# Story B6.S1.T1 — Celery `send_email_task` (F848)

## Contexte

**Friction** : F848 (cf. `architecture-cible.md §6.1`)
**Sévérité** : P0 — `notification_service.send_plain_email` synchrone bloque endpoint
**Code source** : `app/services/notification.py`

### Description

Cible :
1. `send_email_task` Celery wrap NotificationService.send → async
2. Retry exponentiel sur fail
3. Cohérent avec `EmailGateway` (B3.S5.T3)

## Solution

```python
# app/workers/tasks/email/send.py
@shared_task(
    name="send_email",
    bind=True,
    autoretry_for=(httpx.HTTPError, EmailGatewayError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 5},
)
def send_email_task(self, to: str, subject: str, body_html: str, tenant_id: int, idempotency_key: str | None = None):
    async def _run():
        gateway = await get_email_gateway()
        result = await gateway.send(to=to, subject=subject, body_html=body_html, tenant_id=tenant_id, idempotency_key=idempotency_key)
        if not result.success:
            raise EmailGatewayError(result.error_message)
        return result.message_id
    return asyncio.run(_run())
```

```python
# app/services/notification.py — refacto
class NotificationService:
    async def send_plain_email(self, to, subject, body, tenant_id, async_mode: bool = True):
        if async_mode:
            send_email_task.delay(to=to, subject=subject, body_html=body, tenant_id=tenant_id)
        else:
            # Sync mode pour tests
            return await self.gateway.send(...)
```

## DoD

- [ ] Task `send_email` async avec retry
- [ ] `NotificationService.send_plain_email` enqueue par défaut
- [ ] Test : email enqueued < 100ms (vs sync 2s)
- [ ] Test : 5 retries sur fail réseau

---

# Story B6.S1.T2 — Fallback SMTP TLS+auth (F849)

## Contexte

**Friction** : F849
**Sévérité** : P0 — fallback SMTP sans TLS ni auth en dev → fuite credentials potentielle si env mal config

### Description

Cible : `SmtpGateway` requiert TLS + auth obligatoire si `EMAIL_PROVIDER=smtp`.

## Solution

```python
# app/services/email/smtp.py
class SmtpGateway:
    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.username = settings.SMTP_USERNAME
        self.password = settings.SMTP_PASSWORD
        self.use_tls = settings.SMTP_USE_TLS

        if not (self.username and self.password and self.use_tls):
            if settings.ENVIRONMENT in ("staging", "production"):
                raise ConfigError("SMTP requires TLS+auth in staging/prod")

    async def send(self, ...):
        async with aiosmtplib.SMTP(hostname=self.host, port=self.port, use_tls=self.use_tls) as client:
            await client.login(self.username, self.password)
            await client.send_message(...)
```

## DoD

- [ ] SMTP TLS+auth obligatoire prod/staging
- [ ] Test : config sans TLS en prod → ConfigError au boot
- [ ] Dev local OK sans TLS (env=development)

---

# Story B6.S1.T3 — Queue `loyalty` routée (F1053)

## Contexte

**Friction** : F1053
**Sévérité** : P0 — queue `loyalty` s'empile indéfiniment dans Redis (pas dans `task_routes`)
**Code source** : `app/workers/celery_app.py:task_routes`

### Description

Cible : ajouter `loyalty` dans `task_routes` + worker dédié monitoring.

## Solution

```python
# app/workers/celery_app.py
celery_app.conf.task_routes = {
    "expire_points": {"queue": "loyalty"},
    "loyalty_revenue_window_recompute": {"queue": "loyalty"},
    "credit_points_async": {"queue": "loyalty"},
    # ... autres tasks loyalty
    "send_email": {"queue": "email"},
    "run_etl_import": {"queue": "etl"},
}
```

```bash
# Docker compose worker dédié
celery -A app worker -Q loyalty -n loyalty-worker --loglevel=info
```

### Monitoring

```python
# Prometheus metric
celery_queue_length = Gauge("celery_queue_length", "Tasks waiting in queue", ["queue"])

# Alerte AlertManager si > 1000 pending
```

## DoD

- [ ] Queue `loyalty` dans task_routes
- [ ] Worker dédié spawn
- [ ] Metric `celery_queue_length{queue=loyalty}`
- [ ] Test : task routée correctement

---

# Story B6.S1.T4 — `require_scope(Scope.PRINTER_PRINT)` (F1089)

## Contexte

**Friction** : F1089
**Sévérité** : P0 — endpoints `/print/*` sans scope check

### Description

Cible : tous endpoints `/print/*` requièrent `Scope.PRINTER_PRINT` + audit.

## Solution

```python
# app/api/v1/endpoints/print.py
@router.post("/print/ticket", dependencies=[Depends(require_scope(Scope.PRINTER_PRINT))])
async def print_ticket(...):
    ...

@router.post("/print/invoice", dependencies=[Depends(require_scope(Scope.PRINTER_PRINT))])
async def print_invoice(...):
    ...
```

## DoD

- [ ] Tous endpoints `/print/*` avec `require_scope`
- [ ] Test sans scope → 403
- [ ] Audit log enqueue + result

---

# Story B6.S1.T5 — `auto_suspend_uncertified` réel (Q39=A / F1055)

## Contexte

**Friction** : F1055, SOC2-AUTOSUSP-01
**Sévérité** : P0 — compliance theater violation SOC2 §10
**Décision** : Q39=A (verrouillée 2026-04-27) — implémenter réel

### Description

Cible :
1. Table `access_reviews(id, account_id, reviewer_id, reviewed_at, decision, certified_until)`
2. Task quotidien : accounts sans certification depuis 30j → `is_active=False` + audit
3. Endpoint admin pour certifier `POST /admin/access-reviews/{account_id}/certify`

## Solution

### Migration

```python
def upgrade() -> None:
    op.create_table(
        "access_reviews",
        sa.Column("id", postgresql.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_id", postgresql.UUID, sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID, sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("decision", sa.String(32), nullable=False),  # certified | denied | pending
        sa.Column("certified_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
    )
    op.create_index("ix_access_reviews_account", "access_reviews", ["account_id", "reviewed_at"])
```

### Task

```python
@shared_task(name="auto_suspend_uncertified")
def auto_suspend_uncertified_task():
    async def _run():
        async with AsyncSessionLocal() as db:
            cutoff = datetime.now(UTC) - timedelta(days=30)
            # Accounts sans review certified valide
            stale = await db.scalars(
                select(Account.id)
                .outerjoin(AccessReview, and_(
                    AccessReview.account_id == Account.id,
                    AccessReview.decision == "certified",
                    AccessReview.certified_until > datetime.now(UTC),
                ))
                .where(
                    Account.is_active.is_(True),
                    AccessReview.id.is_(None),
                    Account.created_at < cutoff,
                )
                .limit(500)
            )
            for account_id in stale.all():
                async with db.begin():
                    account = await db.get(Account, account_id, with_for_update=True)
                    account.is_active = False
                    account.suspended_at = datetime.now(UTC)
                    account.suspended_reason = "uncertified_30d"
                    await audit_service.log(
                        action="USER_SUSPENDED_UNCERTIFIED",
                        entity_type="Account",
                        entity_id=str(account_id),
                        description="Auto-suspended after 30d uncertified",
                        account_id=None,
                        tenant_id=account.tenant_id,
                    )
    asyncio.run(_run())
```

### Endpoint admin

```python
@router.post("/admin/access-reviews/{account_id}/certify")
async def certify_account(
    account_id: UUID,
    payload: CertifyPayload,  # {certified_until: date, notes: str}
    user: User = Depends(require_scope(Scope.ADMIN_ACCESS_REVIEW)),
):
    review = AccessReview(
        account_id=account_id,
        reviewer_id=user.id,
        decision="certified",
        certified_until=payload.certified_until,
        notes=payload.notes,
    )
    db.add(review)
    await db.commit()
    return {"status": "certified", "until": payload.certified_until}
```

### Test

```python
async def test_auto_suspend_after_30d_uncertified(db, account_old):
    auto_suspend_uncertified_task.apply().get()
    await db.refresh(account_old)
    assert not account_old.is_active

async def test_certified_account_not_suspended(db, account_certified):
    auto_suspend_uncertified_task.apply().get()
    await db.refresh(account_certified)
    assert account_certified.is_active
```

## DoD

- [ ] Table `access_reviews` migration
- [ ] Task `auto_suspend_uncertified` daily
- [ ] Endpoint admin certify
- [ ] Audit log `USER_SUSPENDED_UNCERTIFIED`
- [ ] SOC2 §10 conformité **réelle** (pas placebo)

---

# Story B6.S1.T6 — Notification model refacto (F848-F851)

## Contexte

**Friction** : F848-F851 — Notification model legacy non Mapped + sans TenantMixin + sans account_id

### Description

Cible : refacto Python `Notification` modern style (Mapped + TenantMixin + account_id FK).

## Solution

```python
# app/models/notification.py (refacto)
class Notification(Base, TimestampMixin, TenantMixin):
    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(64))  # 'email_sent', 'sms_failed', etc.
    payload: Mapped[dict] = mapped_column(JSONB)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
```

## DoD

- [ ] Modèle Mapped + TenantMixin
- [ ] FK account_id
- [ ] Migration backfill colonnes
- [ ] Test : insertion + lecture cohérente

---

# Story B6.S1.T7 — `EntityType` enum prep (F1004)

## Contexte

Hotfix prep avant refonte audit B6.S2.

### Description

Définir l'enum Python `EntityType` (sans encore migrer la colonne — fait B6.S2.T7).

## Solution

```python
# app/constants/audit.py (NEW)
class EntityType(str, Enum):
    ACCOUNT = "Account"
    USER = "User"
    CUSTOMER = "Customer"
    # ... 28 valeurs (cohérent B6.S2.T7)
```

## DoD

- [ ] Enum `EntityType` défini
- [ ] Imports utilisés dans services Catalogue/Money/Multi-app pour `@audit_action(entity_type=...)`
- [ ] Migration colonne ENUM repoussée à B6.S2.T7

---

# Story B6.S1.T8 — `notification_log` table + EmailGateway audit log (Vague 2)

## Contexte

**Référence** : `50-sql-schema.md §11.2` table `notification_log` annotée `(NEW)` mais **aucune story sprint** ne la créait jusqu'à présent (lacune Vague 2 audit cohérence)
**Sévérité** : **P0** — sans cette table :
- Pas de tracking bounce/delivery email (Postmark webhook impossible à corréler)
- Pas d'audit RGPD retention 7 ans des communications envoyées
- Pas de visibilité ops sur les emails échoués

### Description

Cible :
1. Migration création table `notification_log` (cf. DDL `50-sql-schema §11.2`)
2. Refonte `EmailGateway.send()` pour logue chaque envoi en base (succès ET échec)
3. Webhook Postmark `/webhooks/postmark/delivery` met à jour `notification_log.delivered_at` / `bounced_at`
4. Endpoint `GET /admin/notification-log` (scope `admin:notifications`) pour ops

## Solution

### Migration

```python
# alembic/versions/b3c4d5e6f7ae_create_notification_log_table.py
def upgrade() -> None:
    op.create_table(
        "notification_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.BigInteger, sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("customer_id", sa.BigInteger, sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("channel", sa.String(20), nullable=False),  # 'email' | 'sms' | 'push' | 'in_app'
        sa.Column("template_key", sa.String(100), nullable=False),
        sa.Column("recipient", sa.String(500), nullable=False),
        sa.Column("subject", sa.String(255), nullable=True),
        sa.Column("gateway_provider", sa.String(50), nullable=True),  # 'postmark', 'smtp', etc.
        sa.Column("gateway_message_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        # 'pending' | 'sent' | 'delivered' | 'bounced' | 'failed' | 'rejected'
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("related_entity_type", sa.String(64), nullable=True),  # 'Reservation', 'Invoice', 'Relance'
        sa.Column("related_entity_id", sa.BigInteger, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bounced_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "channel IN ('email', 'sms', 'push', 'in_app')",
            name="ck_notification_log_channel",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'delivered', 'bounced', 'failed', 'rejected')",
            name="ck_notification_log_status",
        ),
    )
    op.create_index("idx_notification_log_tenant_created", "notification_log", ["tenant_id", "created_at"])
    op.create_index(
        "idx_notification_log_status_failed", "notification_log", ["status", "created_at"],
        postgresql_where=sa.text("status IN ('bounced', 'failed', 'rejected')"),
    )
    op.create_index(
        "idx_notification_log_gateway_msg", "notification_log", ["gateway_message_id"],
        postgresql_where=sa.text("gateway_message_id IS NOT NULL"),
    )
    op.create_index("idx_notification_log_related", "notification_log", ["related_entity_type", "related_entity_id"])
    # RLS tenant-scoped
    op.execute(text("ALTER TABLE notification_log ENABLE ROW LEVEL SECURITY"))
    op.execute(text("ALTER TABLE notification_log FORCE ROW LEVEL SECURITY"))
    op.execute(text("""
        CREATE POLICY tenant_isolation_notification_log ON notification_log
        FOR ALL TO devup_app
        USING (tenant_id = current_setting('app.current_tenant_id', true)::bigint)
    """))
```

### Modèle ORM

```python
# app/models/notification_log.py (NEW)
class NotificationLog(Base, TimestampMixin, TenantMixin):
    __tablename__ = "notification_log"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id: Mapped[int]
    account_id: Mapped[int | None]
    customer_id: Mapped[int | None]
    channel: Mapped[str]
    template_key: Mapped[str]
    recipient: Mapped[str]
    subject: Mapped[str | None]
    gateway_provider: Mapped[str | None]
    gateway_message_id: Mapped[str | None]
    status: Mapped[str] = mapped_column(default="pending")
    error_code: Mapped[str | None]
    error_message: Mapped[str | None]
    related_entity_type: Mapped[str | None]
    related_entity_id: Mapped[int | None]
    sent_at: Mapped[datetime | None]
    delivered_at: Mapped[datetime | None]
    bounced_at: Mapped[datetime | None]
```

### EmailGateway logue automatiquement

```python
# app/services/email/gateway_with_log.py (NEW — wrapper autour B3.S5.T3 PostmarkGateway)
class LoggingEmailGateway:
    """Wrapper qui log chaque send dans notification_log avant/après."""
    
    def __init__(self, inner: EmailGateway, db_factory):
        self.inner = inner
        self.db_factory = db_factory  # AsyncSessionLocal
    
    async def send(
        self,
        to: str,
        subject: str,
        body_html: str,
        tenant_id: int,
        template_key: str = "unknown",
        related_entity_type: str | None = None,
        related_entity_id: int | None = None,
        idempotency_key: str | None = None,
    ) -> EmailResult:
        # 1. Log pre-send (status=pending)
        async with self.db_factory() as db:
            log_entry = NotificationLog(
                tenant_id=tenant_id,
                channel="email",
                template_key=template_key,
                recipient=to,
                subject=subject,
                gateway_provider="postmark",
                status="pending",
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
            )
            db.add(log_entry)
            await db.commit()
            log_id = log_entry.id
        
        # 2. Send via inner gateway
        result = await self.inner.send(to, subject, body_html, tenant_id, idempotency_key)
        
        # 3. Update log après envoi
        async with self.db_factory() as db:
            await db.execute(
                update(NotificationLog).where(NotificationLog.id == log_id).values(
                    status="sent" if result.success else "failed",
                    gateway_message_id=result.message_id,
                    error_code=result.error_code,
                    error_message=result.error_message,
                    sent_at=datetime.now(UTC) if result.success else None,
                )
            )
            await db.commit()
        
        return result
```

### Webhook Postmark delivery

```python
# app/api/v1/endpoints/webhooks/postmark.py (NEW)
@router.post("/webhooks/postmark/delivery", include_in_schema=False)
async def postmark_delivery_webhook(payload: PostmarkWebhookPayload, request: Request):
    """Postmark POST sur cet endpoint pour bounce/delivery events.
    
    Sécurité : verify signature header X-Postmark-Signature (HMAC du payload).
    """
    if not _verify_postmark_signature(request.headers, request.body):
        raise HTTPException(401)
    
    # Match via gateway_message_id
    log = await db.scalar(
        select(NotificationLog).where(NotificationLog.gateway_message_id == payload.MessageID)
    )
    if log is None:
        return {"status": "unknown_message"}
    
    if payload.RecordType == "Delivery":
        log.status = "delivered"
        log.delivered_at = datetime.now(UTC)
    elif payload.RecordType == "Bounce":
        log.status = "bounced"
        log.bounced_at = datetime.now(UTC)
        log.error_code = payload.Type
        log.error_message = payload.Description
    elif payload.RecordType == "SpamComplaint":
        log.status = "rejected"
        log.error_code = "SPAM_COMPLAINT"
    
    await db.commit()
    return {"status": "ok"}
```

### Endpoint admin lecture

```python
@router.get("/admin/notification-log", dependencies=[Depends(require_scope(Scope.ADMIN_NOTIFICATIONS))])
async def list_notification_log(
    tenant_id: int = Depends(get_tenant_id),
    status: str | None = None,
    template_key: str | None = None,
    limit: int = 100,
):
    query = select(NotificationLog).where(NotificationLog.tenant_id == tenant_id)
    if status:
        query = query.where(NotificationLog.status == status)
    if template_key:
        query = query.where(NotificationLog.template_key == template_key)
    query = query.order_by(NotificationLog.created_at.desc()).limit(limit)
    return (await db.scalars(query)).all()
```

### Tests

```python
async def test_notification_log_created_on_send(db, gateway_with_log, tenant):
    result = await gateway_with_log.send(
        to="user@example.com", subject="Test", body_html="<p>x</p>",
        tenant_id=tenant.id, template_key="reservation_confirmed",
    )
    log = await db.scalar(
        select(NotificationLog).where(NotificationLog.recipient == "user@example.com")
    )
    assert log is not None
    assert log.status == "sent"
    assert log.gateway_message_id is not None
    assert log.template_key == "reservation_confirmed"

async def test_notification_log_failed_status_on_error(db, gateway_with_log_failing):
    result = await gateway_with_log_failing.send(...)
    log = await db.scalar(select(NotificationLog).order_by(NotificationLog.id.desc()))
    assert log.status == "failed"
    assert log.error_code is not None

async def test_postmark_webhook_marks_delivered(client, db, sent_log):
    response = await client.post("/api/v1/webhooks/postmark/delivery", json={
        "RecordType": "Delivery",
        "MessageID": sent_log.gateway_message_id,
    }, headers={"X-Postmark-Signature": _compute_test_sig(...)})
    assert response.status_code == 200
    await db.refresh(sent_log)
    assert sent_log.status == "delivered"
    assert sent_log.delivered_at is not None
```

## DoD

- [ ] Migration `notification_log` table créée avec RLS
- [ ] Modèle ORM `NotificationLog`
- [ ] `LoggingEmailGateway` wrapper (DI swap : `LoggingEmailGateway` enveloppe `PostmarkGateway` B3.S5.T3)
- [ ] Webhook Postmark `/webhooks/postmark/delivery` opérationnel (signature HMAC vérifiée)
- [ ] Endpoint admin `GET /admin/notification-log` avec filtres
- [ ] Test : send → row pending → row sent + message_id
- [ ] Test : webhook delivery → status=delivered + delivered_at
- [ ] Test : webhook bounce → status=bounced + error_code

---

## Critères de succès Sprint B6.S1

- [ ] **F848 résolu** : email Celery async + retry
- [ ] **F849 résolu** : SMTP TLS+auth obligatoire prod
- [ ] **F1053 résolu** : queue loyalty routée + worker
- [ ] **F1089 résolu** : `require_scope` print
- [ ] **Q39=A / F1055 résolu** : auto_suspend réel SOC2 conforme
- [ ] **F848-F851 résolu** : Notification model refacto
- [ ] EntityType enum prep B6.S2
- [ ] **Vague 2** : `notification_log` table + LoggingEmailGateway + webhook Postmark

---

**Fin du document — 16-sprint-B6.S1.md**

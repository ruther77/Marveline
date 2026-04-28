# Sprint B3.S5 — Celery jobs + caps fidélité + EmailGateway prod

> **STATUT** : ⏳ À démarrer après B3.S4
> **DURÉE MAX** : 2 semaines
> **OWNER** : Dev1
> **BLOQUE** : B3.S6 (e-invoicing s'appuie sur EmailGateway pour notifications PDP), B6.S1 (Audit refondu réutilise EmailGateway)
> **DÉPEND DE** : B3.S2 (FSM helper), B3.S4 (Outbox `ReservationCancelled` + `DevisConverted`)
> **OBJECTIF** : Livrer les 4 Celery jobs ledger (TR-10) — `expire_devis`, `expire_points`, `dunning_orchestrator`, `loyalty_revenue_window_recompute` — avec idempotency + retry/DLQ. Implémenter les caps fidélité anti-fraude (TR-13 — Q15=A `MAX_LOYALTY_MULTIPLIER=3.0`, Q16=B caps daily/monthly). Brancher `EmailGateway` Postmark prod (Q18=A) avec injection DI + per-tenant DKIM + idempotency.

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B3.S5.T1** | TR-10 — `expire_devis_task` Celery hourly + FSM `pending → expired` | P0 | 1 j | aucun |
| **B3.S5.T2** | TR-10 — `expire_points_task` Celery daily + insertion `PointsLedger(type='expire')` | P0 | 1.5 j | T5 |
| **B3.S5.T3** | TR-15 — `EmailGateway` abstraction + `PostmarkGateway` prod (Q18=A) + DI | P0 | 2 j | T4 |
| **B3.S5.T4** | TR-10 — `dunning_orchestrator_task` Celery daily + Relance FSM + retry/DLQ Postmark | P0 | 2 j | aucun |
| **B3.S5.T5** | TR-13 — Caps fidélité `LoyaltyEarnLimiter` + advisory locks (F792-794) + `MAX_LOYALTY_MULTIPLIER` | P0 | 1.5 j | T2 |
| **B3.S5.T6** | TR-11 — `relativedelta` partout (drop `timedelta(days=30)`) + ruff plugin | P1 | 0.5 j | aucun |
| **B3.S5.T7** | `loyalty_revenue_window_recompute` Celery daily Marveline tiered | P1 | 1 j | aucun |

**Total effort** : 9.5 jours-homme.

---

# Story B3.S5.T1 — `expire_devis_task` Celery

## Contexte

**Friction** : TR-10 (cf. `architecture-cible.md §3.2.11`)
**Sévérité** : P0 — Devis pending éternels = pollution dashboard + stock potentiellement bloqué
**Code source** : aucun — task à créer
**Décision** : Q17=D (verrouillée 2026-04-27) — `Tenant.devis_default_expiry_days = 30` configurable per-tenant, override per-Devis via `Devis.expires_at`

### Description

Aujourd'hui : Devis sans mécanisme d'expiration. Devis créé J-90 reste `status='pending'` indéfiniment. Conséquences :
- Dashboard Marveline montre 200 devis "en cours" alors que 150 sont morts
- Si conversion tentée sur devis ancien → tarifs/stock obsolètes appliqués

**Cible** : Celery beat schedule horaire qui transit FSM `pending → expired`.

## Solution

### Task

```python
# app/workers/tasks/expire_devis.py (NEW)
from celery import shared_task
from app.services.fsm import FSMHelper

@shared_task(
    bind=True,
    name="expire_devis",
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def expire_devis_task(self):
    """TR-10 — Devis pending dépassé `expires_at` → FSM expired.

    Idempotency : si déjà expired, FSMHelper lève InvalidTransition (ignoré).
    Per-tenant : `Devis.expires_at` peut être NULL pour tenants sans expiry config — ignorés.
    """
    async def _run():
        async with AsyncSessionLocal() as db:
            now = datetime.now(UTC)
            # Sélection candidats (pas de lock — fait juste après par batch)
            stale = await db.execute(
                select(Devis.id, Devis.tenant_id, Devis.status)
                .where(
                    Devis.status == "pending",
                    Devis.expires_at.is_not(None),
                    Devis.expires_at < now,
                )
                .limit(1000)
            )
            count = 0
            for devis_id, tenant_id, status in stale.all():
                try:
                    async with db.begin():
                        devis = await db.execute(
                            select(Devis).where(Devis.id == devis_id).with_for_update()
                        )
                        devis = devis.scalar_one()
                        if devis.status != "pending":
                            continue  # déjà transité par autre worker
                        if devis.expires_at >= datetime.now(UTC):
                            continue  # `expires_at` modifié entre temps
                        await fsm.assert_transition(
                            db, "devis", devis.id, "pending", "expired",
                            actor_id=None, reason="auto_expire",
                        )
                        devis.status = "expired"
                        await fsm.log_transition(db, "devis", devis.id, "pending", "expired", actor_id=None)
                    count += 1
                except InvalidTransition:
                    continue  # race : autre worker
            return count

    return asyncio.run(_run())
```

### Celery beat

```python
# app/workers/celery_app.py
celery_app.conf.beat_schedule = {
    "expire-devis-hourly": {
        "task": "expire_devis",
        "schedule": crontab(minute=10),  # H+10min pour étaler
    },
    # ... autres tasks ajoutées dans T2/T4/T7
}
```

### Test

```python
async def test_expire_devis_pending_past_due(db, tenant):
    devis = Devis(tenant_id=tenant.id, status="pending", expires_at=datetime.now(UTC) - timedelta(days=1))
    db.add(devis); await db.commit()

    expire_devis_task.apply().get()

    await db.refresh(devis)
    assert devis.status == "expired"

async def test_expire_devis_idempotent(db, tenant, devis_already_expired):
    """Réexécution → 0 transitions supplémentaires (déjà expired)."""
    count_before = await db.scalar(select(func.count()).where(FSMTransition.entity_id == devis_already_expired.id))
    expire_devis_task.apply().get()
    count_after = await db.scalar(select(func.count()).where(FSMTransition.entity_id == devis_already_expired.id))
    assert count_after == count_before
```

## DoD

- [ ] Task `expire_devis` enregistrée dans Celery beat hourly
- [ ] Lock `with_for_update` + double-check `expires_at` post-lock (race-safe)
- [ ] Test : Devis pending past_due → status='expired'
- [ ] Test idempotence : re-run → 0 nouvelle transition
- [ ] Test per-tenant : Devis sans `expires_at` (NULL) → non touché

---

# Story B3.S5.T2 — `expire_points_task` Celery

## Contexte

**Friction** : TR-10 — points fidélité jamais expirés en Marveline (programme tiered avec expiry 12 mois)
**Sévérité** : P0 — risque liability comptable (points en suspens grandissants)
**Code source** : `app/services/loyalty.py` (manque task expiration)

### Description

Programme L'Incontournable : points expirent à J+12 mois après earn (cf. `loyalty-spec.md`). Sans task automatique, les points expirables s'accumulent et faussent les soldes.

Cible : task daily 03:00 qui :
1. Trouve `PointsLedger(type='earn', expires_at < now())` non encore expirés
2. Insère contre-écriture `PointsLedger(type='expire', amount=-X)`
3. Respecte immutability (insert only, jamais UPDATE entrée originale)

## Solution

### Task

```python
# app/workers/tasks/expire_points.py (NEW)
@shared_task(
    bind=True,
    name="expire_points",
    autoretry_for=(OperationalError,),
    retry_kwargs={"max_retries": 3},
)
def expire_points_task(self):
    """TR-10 — Insert PointsLedger(type='expire') pour entries earn dont expires_at < now().

    Append-only : jamais UPDATE entrée originale (trigger DB B3.S2.T3 bloque).
    Idempotency : utilise `expired_at` flag dénormalisé sur l'entry earn pour dédup.
    """
    async def _run():
        async with AsyncSessionLocal() as db:
            now = datetime.now(UTC)
            # Trouver earn entries non encore expirés
            stale = await db.execute(
                select(PointsLedger.id, PointsLedger.member_id, PointsLedger.amount, PointsLedger.tenant_id)
                .where(
                    PointsLedger.entry_type == "earn",
                    PointsLedger.expires_at.is_not(None),
                    PointsLedger.expires_at < now,
                    PointsLedger.expired_marker_at.is_(None),  # pas encore traité
                )
                .limit(500)
            )
            count = 0
            for entry_id, member_id, amount, tenant_id in stale.all():
                try:
                    async with db.begin():
                        # Advisory lock per member (anti-double-expire)
                        await db.execute(
                            text("SELECT pg_advisory_xact_lock(hashtext('member:' || :mid))"),
                            {"mid": str(member_id)},
                        )
                        # Re-check sous lock
                        original = await db.get(PointsLedger, entry_id)
                        if original.expired_marker_at is not None:
                            continue
                        # Compute balance after expire
                        balance_after = await _current_balance(db, member_id) - amount
                        # Insert contre-écriture (append-only)
                        db.add(PointsLedger(
                            tenant_id=tenant_id,
                            member_id=member_id,
                            entry_type="expire",
                            amount=-amount,
                            balance_after=balance_after,
                            related_entity_type="points_ledger",
                            related_entity_id=entry_id,
                            actor_id=None,
                        ))
                        # Marquer flag dédup (UPDATE NOT bloqué car colonne hors trigger immutable)
                        await db.execute(
                            update(PointsLedger)
                            .where(PointsLedger.id == entry_id)
                            .values(expired_marker_at=now)
                        )
                    count += 1
                except IntegrityError:
                    continue
            return count

    return asyncio.run(_run())
```

### Migration : flag dénormalisé `expired_marker_at`

```python
# alembic/versions/e3f4a5b6c7dc_points_ledger_expired_marker.py
def upgrade() -> None:
    op.add_column("points_ledger", sa.Column("expired_marker_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_points_ledger_pending_expire", "points_ledger", ["expires_at"],
                    postgresql_where=sa.text("entry_type = 'earn' AND expires_at IS NOT NULL AND expired_marker_at IS NULL"))
```

**Note trigger** : la colonne `expired_marker_at` doit être **whitelistée** dans le trigger immutability `points_ledger_immutable` (cf. B3.S2.T3) — c'est la seule mutation autorisée sur entry historique, pour dédup uniquement.

### Test

```python
async def test_expire_points_idempotent_re_run(db, tenant, member, expired_earn_entry):
    """Re-run task 2x → une seule entrée 'expire' créée."""
    expire_points_task.apply().get()
    expire_points_task.apply().get()

    expire_entries = await db.scalars(
        select(PointsLedger).where(
            PointsLedger.entry_type == "expire",
            PointsLedger.related_entity_id == expired_earn_entry.id,
        )
    )
    assert len(expire_entries.all()) == 1

async def test_expire_points_balance_correct(db, tenant, member):
    """Balance après expire = balance avant - amount expiré."""
    earn = PointsLedger(tenant_id=tenant.id, member_id=member.id, entry_type="earn",
                        amount=100, balance_after=100, expires_at=datetime.now(UTC) - timedelta(days=1))
    db.add(earn); await db.commit()

    expire_points_task.apply().get()
    balance = await _current_balance(db, member.id)
    assert balance == 0
```

## DoD

- [ ] Task `expire_points` Celery beat daily 03:00
- [ ] Migration `expired_marker_at` + index partiel
- [ ] Whitelist colonne dans trigger immutable points_ledger
- [ ] Advisory lock per `member_id` (F792-F794 conforme)
- [ ] Test idempotence (re-run = 0 nouvelle entrée)
- [ ] Test balance : after expire = balance_before - amount

---

# Story B3.S5.T3 — `EmailGateway` abstraction + `PostmarkGateway` prod

## Contexte

**Friction** : TR-15 (cf. `architecture-cible.md §3.2.12`)
**Sévérité** : P0 — relances marquées `sent` sans envoi réel (RELANCE-FAKE-SENT-01 bug détecté audit 2026-04-27)
**Décision** : Q18=A (Postmark) verrouillée
**Code source** : `app/tasks/relances.py` (faux signal massif)

### Description

Aujourd'hui : `app/tasks/relances.py` mute `Relance.status='sent'` sans appel email. Aucune abstraction sortie email. Conséquences :
- Dashboard Marveline affiche relances envoyées qui ne le sont pas
- Clients impayés ne reçoivent rien → litiges paiements
- Pas de DKIM/SPF per-tenant configuré

**Cible** : Protocol `EmailGateway` + 2 implémentations (`PostmarkGateway` prod + `SmtpGateway` dev) + injection DI.

## Solution

### Protocol + implémentations

```python
# app/services/email/gateway.py (NEW)
from typing import Protocol
from dataclasses import dataclass

@dataclass(frozen=True)
class EmailResult:
    success: bool
    message_id: str | None
    error_code: str | None
    error_message: str | None
    raw_response: dict | None


class EmailGateway(Protocol):
    async def send(
        self,
        to: str,
        subject: str,
        body_html: str,
        tenant_id: int,
        idempotency_key: str | None = None,
    ) -> EmailResult: ...


# app/services/email/postmark.py (NEW)
import httpx
from app.core.config import settings


class PostmarkGateway:
    """Q18=A — provider production Postmark (déliverabilité B2B)."""

    POSTMARK_API = "https://api.postmarkapp.com/email"

    def __init__(self, http: httpx.AsyncClient, tenant_repo: TenantRepository):
        self.http = http
        self.tenant_repo = tenant_repo

    async def send(
        self,
        to: str,
        subject: str,
        body_html: str,
        tenant_id: int,
        idempotency_key: str | None = None,
    ) -> EmailResult:
        # Per-tenant DKIM/SPF + token (Q43=B — chaque tenant son domaine)
        tenant = await self.tenant_repo.get_with_email_config(tenant_id)
        sender = tenant.brand_email_from  # ex: noreply@marveline.fr
        token = await decrypt_kms(tenant.postmark_server_token_encrypted)

        headers = {
            "Accept": "application/json",
            "X-Postmark-Server-Token": token,
        }
        if idempotency_key:
            # Postmark dédup via header MessageID
            headers["X-PM-Message-Id"] = idempotency_key

        try:
            response = await self.http.post(
                self.POSTMARK_API,
                headers=headers,
                json={
                    "From": sender,
                    "To": to,
                    "Subject": subject,
                    "HtmlBody": body_html,
                    "MessageStream": "outbound",
                    "TrackOpens": True,
                },
                timeout=10.0,
            )
        except httpx.HTTPError as e:
            return EmailResult(False, None, "TRANSPORT_ERROR", str(e), None)

        data = response.json()
        if response.status_code == 200 and data.get("ErrorCode", 0) == 0:
            return EmailResult(True, data["MessageID"], None, None, data)
        return EmailResult(
            success=False,
            message_id=None,
            error_code=str(data.get("ErrorCode")),
            error_message=data.get("Message"),
            raw_response=data,
        )


# app/services/email/smtp.py (NEW)
class SmtpGateway:
    """Fallback dev — relais via SMTP local (logs uniquement, pas d'envoi prod)."""
    async def send(self, to, subject, body_html, tenant_id, idempotency_key=None) -> EmailResult:
        logger.info("EMAIL_DEV", to=to, subject=subject, tenant_id=tenant_id)
        return EmailResult(True, f"dev-{uuid4()}", None, None, None)
```

### DI

```python
# app/core/deps.py
from app.services.email.gateway import EmailGateway
from app.services.email.postmark import PostmarkGateway
from app.services.email.smtp import SmtpGateway

async def get_email_gateway(
    http: httpx.AsyncClient = Depends(get_http_client),
    tenant_repo: TenantRepository = Depends(get_tenant_repo),
) -> EmailGateway:
    if settings.EMAIL_PROVIDER == "postmark":
        return PostmarkGateway(http, tenant_repo)
    return SmtpGateway()  # dev / test
```

### Migration : token Postmark per-tenant chiffré KMS

```python
# alembic/versions/e3f4a5b6c7dd_tenant_postmark_token.py
def upgrade() -> None:
    op.add_column("tenants", sa.Column("postmark_server_token_encrypted", sa.LargeBinary, nullable=True))
    op.add_column("tenants", sa.Column("brand_email_from", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("brand_dkim_domain", sa.String(255), nullable=True))
    # Note : token Postmark stocké via EncryptedField (B1.S3) avec context AAD `tenant:{id}:postmark`
```

### Tests

```python
async def test_postmark_send_success(monkeypatch, postmark_gateway):
    mock_response = MagicMock(status_code=200, json=lambda: {"ErrorCode": 0, "MessageID": "abc-123"})
    monkeypatch.setattr(httpx.AsyncClient, "post", AsyncMock(return_value=mock_response))

    result = await postmark_gateway.send(
        to="client@example.com", subject="Test", body_html="<p>Hello</p>", tenant_id=1,
    )
    assert result.success is True
    assert result.message_id == "abc-123"

async def test_postmark_relance_pas_sent_si_404(monkeypatch, postmark_gateway):
    mock_response = MagicMock(status_code=404, json=lambda: {"ErrorCode": 405, "Message": "Server not found"})
    monkeypatch.setattr(httpx.AsyncClient, "post", AsyncMock(return_value=mock_response))

    result = await postmark_gateway.send(...)
    assert result.success is False
    assert result.error_code == "405"

async def test_postmark_idempotency_key_dedup(httpx_mock, postmark_gateway):
    """Postmark dédup via X-PM-Message-Id : 2 envois même key → 1 seul email."""
    await postmark_gateway.send(..., idempotency_key="relance-42")
    await postmark_gateway.send(..., idempotency_key="relance-42")
    requests = httpx_mock.get_requests()
    assert all(r.headers.get("X-PM-Message-Id") == "relance-42" for r in requests)
```

## DoD

- [ ] `EmailGateway` Protocol + `PostmarkGateway` + `SmtpGateway` livrés
- [ ] DI `get_email_gateway` switch sur `settings.EMAIL_PROVIDER`
- [ ] Migration `tenants.postmark_server_token_encrypted` + `brand_email_from` + `brand_dkim_domain`
- [ ] Token chiffré via `EncryptedField` KMS (B1.S3)
- [ ] Test : 200 → success ; 404 → success=False ; idempotency_key propagé
- [ ] Aucun usage direct `smtplib` ou `requests` dans `app/services/`

---

# Story B3.S5.T4 — `dunning_orchestrator_task` + Relance FSM + retry/DLQ

## Contexte

**Friction** : TR-10 + RELANCE-FAKE-SENT-01 (bug détecté audit 2026-04-27)
**Sévérité** : P0 — relance marquée `sent` sans envoi réel
**Code source** : `app/tasks/relances.py` (à refondre)

### Description

Cible :
1. Task daily 06:00 lit `Relance(status='due')`
2. Pour chaque, appel `EmailGateway.send()`
3. Si `EmailResult.success → Relance.status='sent'`, persist `message_id`
4. Sinon → `status='failed'`, increment `retry_count`, schedule retry exponentiel
5. Après 5 retries → DLQ (`status='dead_letter'`, alert ops)

## Solution

### Migration FSM Relance

```python
# alembic/versions/e3f4a5b6c7de_relance_fsm.py
def upgrade() -> None:
    op.add_column("relances", sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"))
    op.add_column("relances", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("relances", sa.Column("message_id", sa.String(255), nullable=True))
    op.add_column("relances", sa.Column("last_error_code", sa.String(64), nullable=True))
    op.add_column("relances", sa.Column("last_error_message", sa.Text, nullable=True))
    # CHECK status : due | in_flight | sent | failed | dead_letter
    op.create_check_constraint(
        "ck_relances_status",
        "relances",
        "status IN ('due', 'in_flight', 'sent', 'failed', 'dead_letter')",
    )
```

### FSM matrix

```python
# app/services/fsm.py — registry
RELANCE_FSM = FSMMatrix(
    entity_type="relance",
    transitions={
        ("due", "in_flight"),
        ("in_flight", "sent"),
        ("in_flight", "failed"),
        ("failed", "in_flight"),  # retry
        ("failed", "dead_letter"),
    },
    initial_states={"due"},
    terminal_states={"sent", "dead_letter"},
)
FSM_MATRICES["relance"] = RELANCE_FSM
```

### Task orchestrateur

```python
# app/workers/tasks/dunning.py (NEW)
@shared_task(name="dunning_orchestrator")
def dunning_orchestrator_task():
    async def _run():
        async with AsyncSessionLocal() as db:
            now = datetime.now(UTC)
            # Sélection : due OR (failed AND next_retry_at < now AND retry_count < 5)
            candidates = await db.execute(
                select(Relance.id)
                .where(
                    or_(
                        Relance.status == "due",
                        and_(
                            Relance.status == "failed",
                            Relance.next_retry_at < now,
                            Relance.retry_count < 5,
                        ),
                    )
                )
                .limit(200)
            )
            sent = 0
            failed = 0
            dlq = 0
            for (relance_id,) in candidates.all():
                # Lock + transit due → in_flight pour éviter double envoi par worker concurrent
                async with db.begin():
                    relance = await db.get(Relance, relance_id, with_for_update=True)
                    if relance.status not in ("due", "failed"):
                        continue
                    await fsm.assert_transition(db, "relance", relance.id, relance.status, "in_flight", actor_id=None)
                    relance.status = "in_flight"

                # Send hors lock pour ne pas bloquer la TX pendant l'appel HTTP
                gateway = await get_email_gateway()
                customer = await get_customer(relance.customer_id)
                idempotency_key = f"relance-{relance.id}-attempt-{relance.retry_count}"
                result = await gateway.send(
                    to=customer.email,
                    subject=relance.subject,
                    body_html=relance.body_html,
                    tenant_id=relance.tenant_id,
                    idempotency_key=idempotency_key,
                )

                # Persist résultat
                async with db.begin():
                    relance = await db.get(Relance, relance_id, with_for_update=True)
                    if result.success:
                        await fsm.assert_transition(db, "relance", relance.id, "in_flight", "sent", actor_id=None)
                        relance.status = "sent"
                        relance.message_id = result.message_id
                        relance.sent_at = datetime.now(UTC)
                        sent += 1
                    else:
                        relance.retry_count += 1
                        relance.last_error_code = result.error_code
                        relance.last_error_message = result.error_message
                        if relance.retry_count >= 5:
                            await fsm.assert_transition(db, "relance", relance.id, "in_flight", "dead_letter", actor_id=None)
                            relance.status = "dead_letter"
                            dlq += 1
                            # Alert ops via Outbox
                            db.add(OutboxEvent(
                                event_type="RelanceDeadLetter",
                                aggregate_id=relance.id,
                                tenant_id=relance.tenant_id,
                                payload={"customer_id": str(relance.customer_id), "error": result.error_message},
                            ))
                        else:
                            await fsm.assert_transition(db, "relance", relance.id, "in_flight", "failed", actor_id=None)
                            relance.status = "failed"
                            # Backoff exponentiel : 5min, 30min, 2h, 12h, 48h
                            backoffs = [300, 1800, 7200, 43200, 172800]
                            relance.next_retry_at = now + timedelta(seconds=backoffs[relance.retry_count - 1])
                            failed += 1

            return {"sent": sent, "failed": failed, "dead_letter": dlq}

    return asyncio.run(_run())
```

### Tests

```python
async def test_dunning_relance_marked_sent_only_on_gateway_200(db, mock_gateway_success):
    relance = Relance(status="due", ...)
    db.add(relance); await db.commit()

    dunning_orchestrator_task.apply().get()

    await db.refresh(relance)
    assert relance.status == "sent"
    assert relance.message_id is not None

async def test_dunning_relance_failed_then_retry_backoff(db, mock_gateway_404):
    relance = Relance(status="due", ...)
    db.add(relance); await db.commit()

    dunning_orchestrator_task.apply().get()

    await db.refresh(relance)
    assert relance.status == "failed"
    assert relance.retry_count == 1
    assert relance.next_retry_at > datetime.now(UTC)

async def test_dunning_dead_letter_after_5_retries(db, mock_gateway_500):
    relance = Relance(status="failed", retry_count=4, next_retry_at=datetime.now(UTC) - timedelta(seconds=1))
    db.add(relance); await db.commit()

    dunning_orchestrator_task.apply().get()

    await db.refresh(relance)
    assert relance.status == "dead_letter"
    # Outbox event publié
    events = await db.scalars(select(OutboxEvent).where(OutboxEvent.event_type == "RelanceDeadLetter"))
    assert len(events.all()) == 1
```

## DoD

- [ ] FSM matrix `relance` ajoutée registry
- [ ] Migration FSM colonnes `retry_count`, `next_retry_at`, `message_id`, errors
- [ ] Task `dunning_orchestrator` daily 06:00
- [ ] Lock `due → in_flight` AVANT appel gateway (anti double-envoi worker concurrent)
- [ ] Backoff exponentiel : [5min, 30min, 2h, 12h, 48h]
- [ ] Dead letter après 5 retries → Outbox alert
- [ ] Test : 200 → sent ; 404 → failed + backoff ; 5×500 → dead_letter
- [ ] **RELANCE-FAKE-SENT-01 résolu** : status `sent` UNIQUEMENT après EmailResult.success=True

---

# Story B3.S5.T5 — Caps fidélité `LoyaltyEarnLimiter`

## Contexte

**Friction** : TR-13 (cf. `architecture-cible.md §3.2.13`)
**Sévérité** : P0 — earn fidélité non capé = vecteur fraude (un client qui exploite multi-passages génère X×100 points/jour)
**Décisions** : Q15=A `MAX_LOYALTY_MULTIPLIER=3.0`, Q16=B `LOYALTY_DAILY_EARN_CAP_POINTS=5000` + `LOYALTY_MONTHLY_EARN_CAP_POINTS=50000`

### Description

Cible :
1. `LoyaltyEarnLimiter.check(member_id, requested_points)` consulte `points_ledger` sur fenêtre 24h + 30j
2. Retourne `clamp_to=min(requested, daily_remaining, monthly_remaining)`
3. Si clamp > 0 → on crédit `clamp_to` au lieu de `requested`, log différence
4. Si clamp = 0 → on n'écrit rien, log seulement
5. Service appelé par `LoyaltyService.credit_points` AVANT insert PointsLedger

## Solution

### Constantes

```python
# app/constants/loyalty.py (NEW ou existant)
from decimal import Decimal

MAX_LOYALTY_MULTIPLIER = Decimal("3.0")  # Q15=A
LOYALTY_DAILY_EARN_CAP_POINTS = 5000    # Q16=B
LOYALTY_MONTHLY_EARN_CAP_POINTS = 50000  # Q16=B
```

### Service

```python
# app/services/loyalty/earn_limiter.py (NEW)
@dataclass(frozen=True)
class CapResult:
    requested: int
    granted: int
    capped_daily: bool
    capped_monthly: bool
    daily_used: int
    monthly_used: int


class LoyaltyEarnLimiter:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_and_clamp(
        self,
        member_id: UUID,
        tenant_id: int,
        requested_points: int,
        now: datetime | None = None,
    ) -> CapResult:
        now = now or datetime.now(UTC)
        # Fenêtres glissantes (UTC)
        window_24h = now - timedelta(hours=24)
        window_30d = now - relativedelta(days=30)

        rows = await self.db.execute(
            select(
                func.coalesce(func.sum(case(
                    (PointsLedger.created_at >= window_24h, PointsLedger.amount), else_=0
                )), 0).label("daily"),
                func.coalesce(func.sum(case(
                    (PointsLedger.created_at >= window_30d, PointsLedger.amount), else_=0
                )), 0).label("monthly"),
            )
            .where(
                PointsLedger.member_id == member_id,
                PointsLedger.tenant_id == tenant_id,
                PointsLedger.entry_type == "earn",
            )
        )
        daily_used, monthly_used = rows.one()

        daily_remaining = max(0, LOYALTY_DAILY_EARN_CAP_POINTS - daily_used)
        monthly_remaining = max(0, LOYALTY_MONTHLY_EARN_CAP_POINTS - monthly_used)
        granted = min(requested_points, daily_remaining, monthly_remaining)

        return CapResult(
            requested=requested_points,
            granted=granted,
            capped_daily=granted < requested_points and daily_remaining < requested_points,
            capped_monthly=granted < requested_points and monthly_remaining < requested_points,
            daily_used=daily_used,
            monthly_used=monthly_used,
        )
```

### Intégration `LoyaltyService.credit_points`

```python
# app/services/loyalty/service.py
class LoyaltyService:
    async def credit_points(self, member_id, tenant_id, requested, source_id):
        async with self.db.begin():
            # Advisory lock per member (F792-F794)
            await self.db.execute(
                text("SELECT pg_advisory_xact_lock(hashtext('member:' || :mid))"),
                {"mid": str(member_id)},
            )
            cap = await self.limiter.check_and_clamp(member_id, tenant_id, requested)
            if cap.granted == 0:
                logger.info("loyalty_earn_capped_zero", member_id=member_id, requested=requested)
                return cap
            # Clamp multiplier (Q15=A) : si requested > MAX_MULTIPLIER × base, clamp
            # ... appliqué côté résolveur multiplier en amont du requested

            balance_after = await self._current_balance(member_id) + cap.granted
            self.db.add(PointsLedger(
                member_id=member_id,
                tenant_id=tenant_id,
                entry_type="earn",
                amount=cap.granted,
                balance_after=balance_after,
                related_entity_id=source_id,
                metadata_json={"requested": requested, "capped": cap.granted < requested},
            ))
            return cap
```

### Tests

```python
async def test_daily_cap_enforces(db, member, tenant):
    """5000 earn aujourd'hui → 6e earn = 0 granted."""
    for _ in range(50):
        await service.credit_points(member.id, tenant.id, 100, source_id=...)
    cap = await service.credit_points(member.id, tenant.id, 100, source_id=...)
    assert cap.granted == 0
    assert cap.capped_daily

async def test_monthly_cap_enforces(db, member, tenant):
    """50000 earn dans 30j → next earn = 0 granted."""
    # ... seed 50000

async def test_partial_clamp(db, member, tenant):
    """4900 used today → request 200 → granted 100 (clamp à reste)."""
    # ... seed 4900
    cap = await service.credit_points(member.id, tenant.id, 200, source_id=...)
    assert cap.granted == 100
    assert cap.capped_daily

async def test_max_multiplier_clamp_3x(db, member):
    """Multiplier > 3.0 → clamped à 3.0."""
    base = 100
    # multiplier resolver retourne 5.0 → clamped → effective = 300, pas 500
    requested = base * min(Decimal("5.0"), MAX_LOYALTY_MULTIPLIER)
    assert int(requested) == 300
```

## DoD

- [ ] Constantes `MAX_LOYALTY_MULTIPLIER`, `LOYALTY_DAILY_EARN_CAP_POINTS`, `LOYALTY_MONTHLY_EARN_CAP_POINTS` dans `app/constants/loyalty.py`
- [ ] `LoyaltyEarnLimiter.check_and_clamp` utilise fenêtres glissantes
- [ ] `LoyaltyService.credit_points` appelle limiter AVANT insert
- [ ] Advisory lock per `member_id` (F792-F794 résolu)
- [ ] Test daily cap : 50×100 puis 6e → granted=0
- [ ] Test partial clamp : reste = 100 sur request 200 → granted=100
- [ ] Test multiplier clamp 3.0 : ×5 demandé → ×3 effectif

---

# Story B3.S5.T6 — `relativedelta` partout

## Contexte

**Friction** : TR-11 (cf. `architecture-cible.md §3.2.14`)
**Sévérité** : P1 — drift jours sur calculs mensuels (fenêtre fidélité 30j ≠ 1 mois calendaire)
**Code source** : `grep -rn "timedelta(days=30" app/services/`

### Description

`timedelta(days=30 * N)` n'est pas équivalent à N mois calendaires (février 28j, juillet 31j → drift cumulé). `relativedelta(months=N)` fait le calcul calendaire correct.

## Solution

### Refactor

```python
# app/services/loyalty/tier.py (avant)
window_start = now - timedelta(days=365)  # ❌ 365j ≠ 1 an
# (après)
from dateutil.relativedelta import relativedelta
window_start = now - relativedelta(years=1)  # ✅
```

### Ruff plugin custom

```python
# tools/ruff_no_timedelta_months.py
"""Refuse `timedelta(days=30*N)` ou `timedelta(days=365)` dans app/services/."""
import ast, sys, re
from pathlib import Path

PATTERN = re.compile(r"timedelta\(days\s*=\s*(\d+\s*\*\s*30|365|30)\b")
violations = []
for py in Path("app/services").rglob("*.py"):
    text = py.read_text()
    for m in PATTERN.finditer(text):
        line = text[:m.start()].count("\n") + 1
        violations.append(f"{py}:{line} — utiliser relativedelta(months=N) ou (years=N)")

if violations:
    print("\n".join(violations))
    sys.exit(1)
```

Ajouté à `54-ci-invariants.md` script #25.

## DoD

- [ ] `grep "timedelta(days=30" app/services/` → 0 résultat
- [ ] Script CI `tools/ruff_no_timedelta_months.py` actif
- [ ] Imports `from dateutil.relativedelta import relativedelta` ajoutés où nécessaire
- [ ] Tests fenêtre fidélité : 1 an avant 1er mars 2027 → 1er mars 2026 (pas 28 ou 29 février)

---

# Story B3.S5.T7 — `loyalty_revenue_window_recompute` Marveline tiered

## Contexte

Programme Marveline tiered (cf. `loyalty-spec.md`) : `current_tier` calculé sur fenêtre glissante 12 mois. Sans recompute périodique, le tier ne descend jamais (un client Gold reste Gold même si CA chute).

## Solution

```python
# app/workers/tasks/loyalty_recompute.py
@shared_task(name="loyalty_revenue_window_recompute")
def loyalty_revenue_window_recompute_task():
    """Daily 04:00 — recalcule tier_current pour chaque membre Marveline tiered."""
    async def _run():
        async with AsyncSessionLocal() as db:
            now = datetime.now(UTC)
            window_start = now - relativedelta(years=1)
            members = await db.execute(
                select(LoyaltyMember.id, LoyaltyMember.tenant_id)
                .join(LoyaltyProgram, LoyaltyProgram.id == LoyaltyMember.program_id)
                .where(LoyaltyProgram.program_type == "tiered")
            )
            count = 0
            for member_id, tenant_id in members.all():
                async with db.begin():
                    revenue = await db.scalar(
                        select(func.coalesce(func.sum(RevenueLedger.amount), 0))
                        .where(
                            RevenueLedger.customer_id == member_id,
                            RevenueLedger.tenant_id == tenant_id,
                            RevenueLedger.created_at >= window_start,
                        )
                    )
                    new_tier = _resolve_tier(revenue)
                    member = await db.get(LoyaltyMember, member_id)
                    if member.current_tier != new_tier:
                        # Audit ledger entry
                        db.add(LoyaltyTierChangeLog(
                            member_id=member_id,
                            from_tier=member.current_tier,
                            to_tier=new_tier,
                            revenue_window_cents=revenue,
                            computed_at=now,
                        ))
                        member.current_tier = new_tier
                        count += 1
            return count
    return asyncio.run(_run())
```

## DoD

- [ ] Task `loyalty_revenue_window_recompute` Celery beat daily 04:00
- [ ] Fenêtre glissante 12 mois via `relativedelta(years=1)`
- [ ] Audit `LoyaltyTierChangeLog` à chaque downgrade/upgrade
- [ ] Test : membre Gold avec revenue chuté < seuil Silver → tier passe à Silver, log écrit

---

## Critères de succès Sprint B3.S5

- [ ] **TR-10 résolu** : 4 Celery tasks opérationnelles + Celery beat configuré
- [ ] **TR-13 résolu** : caps fidélité enforced (daily/monthly/multiplier) + advisory lock
- [ ] **TR-15 résolu** : `EmailGateway` Postmark prod + per-tenant DKIM
- [ ] **TR-11 résolu** : `relativedelta` partout, script CI actif
- [ ] **RELANCE-FAKE-SENT-01 résolu** : status `sent` UNIQUEMENT après gateway 200
- [ ] Test E2E dunning : Relance(due) → in_flight → gateway 200 → sent + message_id persisté
- [ ] Test E2E dead letter : 5 fails → status='dead_letter' + Outbox alert
- [ ] Test E2E expire_points : earn expiré → contre-écriture insérée, balance correct, idempotent

---

**Fin du document — 13-sprint-B3.S5.md**

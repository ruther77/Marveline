# Sprint B6.S4 — Celery refacto async + beat heartbeat + fanout per-tenant

> **STATUT** : ⏳ À démarrer après B6.S3
> **DURÉE MAX** : 2 semaines
> **OWNER** : Dev1
> **BLOQUE** : B6.S5 (Print/VPN async), B6.S7 (RabbitMQ migration)
> **DÉPEND DE** : B6.S2 (audit), B5.S4 (tenant-aware tasks)
> **OBJECTIF** : Standardiser Celery sur sessions async (drop sync). Livrer beat heartbeat avec metric Prometheus + alerte AlertManager si beat down 2 min. Ajouter `celery_task_duration_seconds` histogramme. Jitter beat schedule (anti thundering herd). Fanout per-tenant invoicing (drop iteration sequentielle). Task `cleanup_expired_sessions_task`. Advisory lock `expire_points` cohérent Bloc 3 (déjà partiellement livré B3.S5.T2). **NB : DLQ déplacée Sprint B6.S7 (RabbitMQ Q42=B)**.

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B6.S4.T1** | Celery sessions async standardisées (drop sync `Session()` partout) | P0 | 2 j | T2 |
| **B6.S4.T2** | Beat heartbeat + metric Prometheus `celery_beat_last_run_seconds` + alerte | P0 | 1 j | aucun |
| **B6.S4.T3** | Histogramme `celery_task_duration_seconds{task_name}` Prometheus | P0 | 0.5 j | aucun |
| **B6.S4.T4** | Jitter beat schedule (anti thundering herd) | P1 | 0.5 j | aucun |
| **B6.S4.T5** | Fanout per-tenant invoicing (parallèle vs séquentiel) | P0 | 1.5 j | aucun |
| **B6.S4.T6** | `cleanup_expired_sessions_task` daily | P1 | 0.5 j | aucun |
| **B6.S4.T7** | Audit cohérence advisory lock `expire_points` (post-B3.S5.T2) | P1 | 0.5 j | aucun |

**Total effort** : 6.5 jours-homme.

---

# Story B6.S4.T1 — Celery sessions async standardisées

## Contexte

**Sévérité** : P0 — mix sync `Session` et async `AsyncSession` dans tasks → blocage event loop, DB connection pool fragmenté

### Description

Cible : tous les tasks utilisent `AsyncSessionLocal` + `asyncio.run(_run())` pattern. Drop `Session()` legacy.

## Solution

```python
# Pattern unique
@shared_task(name="my_task")
def my_task(arg, tenant_id: int):
    async def _run():
        async with AsyncSessionLocal() as db:
            await db.execute(text("SET LOCAL app.current_tenant_id = :tid"), {"tid": tenant_id})
            # ... logique async
    return asyncio.run(_run())
```

```bash
# Audit grep
grep -rn "from sqlalchemy.orm import Session\|SessionLocal()" app/workers/tasks/
```

### Script CI

```python
# tools/check_celery_async_only.py
"""Refuse import Session sync dans app/workers/tasks/."""
PATTERN = re.compile(r"from\s+sqlalchemy\.orm\s+import\s+Session\b|SessionLocal\(\)")
```

## DoD

- [ ] Tous tasks pattern async
- [ ] Script CI actif
- [ ] Test : task complète async, pas de `BlockingIOError`

---

# Story B6.S4.T2 — Beat heartbeat + alerte

## Contexte

**Sévérité** : P0 — beat down 2 min = pas d'expire_devis, pas de dunning, etc. → drift métier silencieux

### Description

Cible :
1. Task `beat_heartbeat` toutes les 30s
2. Metric Prometheus `celery_beat_last_run_seconds_ago`
3. Alerte AlertManager si > 120s

## Solution

```python
# app/workers/tasks/beat_heartbeat.py
from prometheus_client import Gauge

celery_beat_heartbeat = Gauge("celery_beat_last_run_seconds_ago", "Seconds since last beat heartbeat")

@shared_task(name="beat_heartbeat")
def beat_heartbeat_task():
    """Beat envoie un ping → update metric."""
    celery_beat_heartbeat.set(0)  # Reset à chaque run
    # Set timestamp dans Redis
    redis_sync.set("celery_beat_last_run_at", int(time.time()))


# Process worker side : update metric chaque 10s
async def _heartbeat_metric_updater():
    while True:
        last_run = await redis_async.get("celery_beat_last_run_at")
        if last_run:
            elapsed = time.time() - int(last_run)
            celery_beat_heartbeat.set(elapsed)
        await asyncio.sleep(10)


# Beat schedule
celery_app.conf.beat_schedule["beat-heartbeat"] = {
    "task": "beat_heartbeat",
    "schedule": 30.0,  # 30 sec
}
```

### AlertManager rule

```yaml
# alertmanager/celery.yml
- alert: CeleryBeatDown
  expr: celery_beat_last_run_seconds_ago > 120
  for: 1m
  annotations:
    summary: "Celery beat is down ({{ $value }}s since last run)"
```

## DoD

- [ ] Task heartbeat 30s
- [ ] Metric Prometheus exposed
- [ ] AlertManager rule
- [ ] Test : kill beat → metric grimpe → alert tirée

---

# Story B6.S4.T3 — `celery_task_duration_seconds` histogram

## Solution

```python
# app/workers/instrumentation.py
from prometheus_client import Histogram
from celery import signals

celery_task_duration = Histogram(
    "celery_task_duration_seconds",
    "Duration of Celery tasks",
    ["task_name", "status"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 300),
)

@signals.task_prerun.connect
def track_task_start(sender, task_id, **kwargs):
    sender._start_time = time.time()

@signals.task_postrun.connect
def track_task_end(sender, task_id, state, **kwargs):
    elapsed = time.time() - sender._start_time
    celery_task_duration.labels(task_name=sender.name, status=state).observe(elapsed)
```

## DoD

- [ ] Histogram exporté
- [ ] Buckets adaptés ([0.1, ..., 300])
- [ ] Labels `task_name`, `status`
- [ ] Dashboard Grafana panneau `celery_task_duration`

---

# Story B6.S4.T4 — Jitter beat schedule

## Contexte

**Sévérité** : P1 — `crontab(hour=3, minute=0)` → toutes les tâches 03:00 → pic CPU + DB connections

### Description

Cible : ajouter jitter 0-5min sur chaque task daily/hourly.

## Solution

```python
import random

celery_app.conf.beat_schedule = {
    "expire_devis": {
        "task": "expire_devis",
        "schedule": crontab(minute=10),  # H+10min étalé
    },
    "expire_points": {
        "task": "expire_points",
        "schedule": crontab(hour=3, minute=random.randint(0, 60)),  # Aléatoire au boot
    },
    # Pattern : minute différent par task
}
```

Note : `random.randint` au boot fixe le minute pour la durée du process (sinon non-déterministe ops). Idéal : utiliser hash du nom du task pour reproductibilité.

```python
def _stable_jitter(task_name: str, max_minutes: int = 60) -> int:
    return int(hashlib.sha256(task_name.encode()).digest()[0]) % max_minutes
```

## DoD

- [ ] Jitter stable per task (pas full random)
- [ ] Tasks distribuées sur la fenêtre minute
- [ ] Test : 5 tasks → 5 minutes différents

---

# Story B6.S4.T5 — Fanout per-tenant invoicing

## Contexte

**Sévérité** : P0 — séquentiel 50 tenants × 30 sec = 25 min ; fanout = ~30 sec total

### Description

Cible : tasks "globales" (ex: `monthly_invoicing`) → enqueue N sub-tasks per-tenant en parallèle.

## Solution

```python
# app/workers/tasks/invoicing.py
@shared_task(name="monthly_invoicing_orchestrator")
def monthly_invoicing_orchestrator_task():
    """Beat 1er du mois 02:00 → fanout per-tenant."""
    async def _run():
        async with AsyncSessionLocal() as db:
            tenants = await db.scalars(select(Tenant.id).where(Tenant.is_active.is_(True)))
            for tenant_id in tenants.all():
                monthly_invoicing_per_tenant_task.delay(tenant_id)
    asyncio.run(_run())


@shared_task(name="monthly_invoicing_per_tenant")
def monthly_invoicing_per_tenant_task(tenant_id: int):
    async def _run():
        async with AsyncSessionLocal() as db:
            await db.execute(text("SET LOCAL app.current_tenant_id = :tid"), {"tid": tenant_id})
            # ... génération facturation mensuelle pour ce tenant
    asyncio.run(_run())
```

## DoD

- [ ] Pattern orchestrator + per-tenant
- [ ] 50 tenants → 50 tasks parallèles workers (pas 1 séquentiel)
- [ ] Test : 50 tenants, 5 workers → durée totale ≈ max(per-tenant) × 50/5

---

# Story B6.S4.T6 — `cleanup_expired_sessions_task` daily

## Solution

```python
@shared_task(name="cleanup_expired_sessions")
def cleanup_expired_sessions_task():
    async def _run():
        async with AsyncSessionLocal() as db:
            cutoff = datetime.now(UTC) - timedelta(days=30)
            await db.execute(
                delete(Session).where(Session.expires_at < cutoff)
            )
            await db.commit()
    asyncio.run(_run())

celery_app.conf.beat_schedule["cleanup-sessions-daily"] = {
    "task": "cleanup_expired_sessions",
    "schedule": crontab(hour=4, minute=15),
}
```

## DoD

- [ ] Task daily 04:15
- [ ] Test : sessions > 30j supprimées

---

# Story B6.S4.T7 — Audit advisory lock `expire_points`

## Contexte

Cohérent avec B3.S5.T2 — vérifier que advisory lock per `member_id` est bien en place après cumul Bloc 3 + Bloc 6 patterns.

### Description

Audit code review : `expire_points_task` doit avoir `pg_advisory_xact_lock(hashtext('member:' || member_id))` AVANT toute mutation `points_ledger`.

## DoD

- [ ] Audit confirme lock en place
- [ ] Test concurrence : 2 workers expire_points → no double-expire

---

## Critères de succès Sprint B6.S4

- [ ] Sessions Celery 100% async
- [ ] Beat heartbeat + alerte AlertManager
- [ ] Histogramme `celery_task_duration_seconds`
- [ ] Jitter stable beat schedule
- [ ] Fanout per-tenant invoicing
- [ ] cleanup_expired_sessions daily
- [ ] Test : 50 tenants invoicing en parallèle < 1 min total

---

**Fin du document — 16-sprint-B6.S4.md**

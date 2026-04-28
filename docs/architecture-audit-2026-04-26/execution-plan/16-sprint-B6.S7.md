# Sprint B6.S7 — Migration broker Redis → RabbitMQ (Q42=B)

> **STATUT** : ⏳ À démarrer après B6.S6
> **DURÉE MAX** : 1 semaine
> **OWNER** : Ops + Dev1
> **BLOQUE** : aucun (sprint final Bloc 6)
> **DÉPEND DE** : B6.S4 (Celery async), B6.S6 (mTLS pour RabbitMQ Management UI)
> **OBJECTIF** : Migrer broker Celery de Redis vers RabbitMQ (Q42=B verrouillé). Déploiement RabbitMQ 3.13 parallèle, drain progressif Redis queues, switch `CELERY_BROKER_URL=amqp://`. DLQ natif via `x-dead-letter-exchange` + métrique `celery_dlq_total{task_name}`. UI Management port 15672 accessible aux ops. **result_backend reste Redis** (séparation broker ≠ backend).

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B6.S7.T1** | Déploiement RabbitMQ 3.13-management Docker Compose + healthcheck + UI 15672 | P0 | 1 j | T2 |
| **B6.S7.T2** | Configuration Celery : broker amqp://, `task_acks_late=True`, `worker_prefetch_multiplier=1` | P0 | 1 j | T3 |
| **B6.S7.T3** | DLQ natif RabbitMQ via `x-dead-letter-exchange` + métrique `celery_dlq_total{task_name}` | P0 | 1 j | aucun |
| **B6.S7.T4** | Migration ordonnée : déploiement parallèle, drain Redis queues, switch progressif | P0 | 1.5 j | aucun |
| **B6.S7.T5** | Cleanup queues Redis legacy + monitoring switch over | P1 | 0.5 j | aucun |
| **B6.S7.T6** | Runbook ops RabbitMQ + alerting (queue length, consumer count, DLQ) | P1 | 0.5 j | aucun |

**Total effort** : 5.5 jours-homme.

---

# Story B6.S7.T1 — Déploiement RabbitMQ + UI Management

## Contexte

**Décision** : Q42=B (verrouillée 2026-04-27)
**Sévérité** : P0 — service infra nouveau

### Description

Cible :
1. Service Docker Compose `rabbitmq:3.13-management`
2. Healthcheck + persistance `/var/lib/rabbitmq`
3. UI Management port 15672 accessible (mTLS via nginx-ingress B6.S6)
4. User admin créé via `rabbitmq.conf`

## Solution

```yaml
# docker-compose.yml
services:
  rabbitmq:
    image: rabbitmq:3.13-management
    container_name: devup-rabbitmq
    ports:
      - "5672:5672"     # AMQP
      - "15672:15672"   # Management UI
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
      RABBITMQ_DEFAULT_VHOST: devup
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
      - ./infra/rabbitmq/rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 30s
      timeout: 10s
      retries: 5

volumes:
  rabbitmq_data:
```

```ini
# infra/rabbitmq/rabbitmq.conf
loopback_users.guest = false
listeners.tcp.default = 5672
management.listener.port = 15672

# Limits
default_vhost = devup
default_user = ${RABBITMQ_USER}
default_pass = ${RABBITMQ_PASSWORD}

# Memory + disk thresholds
vm_memory_high_watermark.relative = 0.6
disk_free_limit.absolute = 2GB
```

## DoD

- [ ] Service `rabbitmq` Docker Compose
- [ ] Healthcheck OK
- [ ] UI 15672 accessible (via nginx mTLS B6.S6)
- [ ] Persistance `rabbitmq_data` volume
- [ ] Test : `rabbitmq-diagnostics ping` retourne OK

---

# Story B6.S7.T2 — Configuration Celery RabbitMQ

## Contexte

**Sévérité** : P0 — switch broker URL impacte tous les workers

### Description

Cible :
- `CELERY_BROKER_URL=amqp://user:pass@rabbitmq:5672/devup`
- `result_backend=redis://...` (inchangé)
- `task_acks_late=True` (ack après exec, pas avant) — fiabilité
- `worker_prefetch_multiplier=1` (1 task à la fois par worker — pas de hoarding)

## Solution

```python
# app/workers/celery_app.py
from celery import Celery

celery_app = Celery(
    "devup",
    broker=settings.CELERY_BROKER_URL,           # amqp://...
    backend=settings.CELERY_RESULT_BACKEND_URL,  # redis://... (inchangé)
)

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    broker_transport_options={
        "confirm_publish": True,  # publisher confirms RabbitMQ
    },
)
```

```bash
# .env.example
CELERY_BROKER_URL=amqp://devup_user:CHANGE_ME@rabbitmq:5672/devup
CELERY_RESULT_BACKEND_URL=redis://redis-results:6379/0
```

## DoD

- [ ] Configuration broker amqp://
- [ ] result_backend reste Redis
- [ ] `task_acks_late=True`, `worker_prefetch_multiplier=1`
- [ ] Test : task échouée mid-exec → re-livrée à un autre worker

---

# Story B6.S7.T3 — DLQ natif RabbitMQ + métrique

## Contexte

**Sévérité** : P0 — sans DLQ, tasks échouées après max_retries disparaissent silencieusement

### Description

Cible :
1. Exchange `dlx` avec routing key `dead_letter`
2. Queue `dead_letter` bound à dlx
3. Tasks queues configurées avec `x-dead-letter-exchange: dlx`
4. Métrique Prometheus `celery_dlq_total{task_name}`
5. Endpoint admin `GET /admin/dlq` pour consultation
6. Endpoint admin `POST /admin/dlq/{message_id}/replay`

## Solution

```python
# app/workers/celery_app.py
from kombu import Exchange, Queue

dlx_exchange = Exchange("dlx", type="topic", durable=True)
dead_letter_queue = Queue(
    "dead_letter",
    exchange=dlx_exchange,
    routing_key="#",
    durable=True,
)

# Pour chaque queue prod, ajouter x-dead-letter-exchange
celery_app.conf.task_queues = [
    Queue("loyalty", routing_key="loyalty", queue_arguments={"x-dead-letter-exchange": "dlx"}),
    Queue("email", routing_key="email", queue_arguments={"x-dead-letter-exchange": "dlx"}),
    Queue("etl", routing_key="etl", queue_arguments={"x-dead-letter-exchange": "dlx"}),
    dead_letter_queue,
]
```

### Métrique

```python
# app/workers/instrumentation.py
from prometheus_client import Counter

celery_dlq_total = Counter(
    "celery_dlq_total",
    "Tasks landed in DLQ",
    ["task_name"],
)

# Worker dédié DLQ qui consume + log + metric
@shared_task(name="dlq_consumer", queue="dead_letter")
def dlq_consumer_task(original_task_name: str, original_args: list, error: str):
    celery_dlq_total.labels(task_name=original_task_name).inc()
    logger.error("celery_dlq", task=original_task_name, args=original_args, error=error)
    # Audit DB
    db.add(DlqEntry(task_name=original_task_name, payload={"args": original_args, "error": error}))
```

### Endpoint admin replay

```python
@router.post("/admin/dlq/{entry_id}/replay")
async def replay_dlq(
    entry_id: UUID,
    user: User = Depends(require_scope(Scope.ADMIN_DLQ_REPLAY)),
):
    entry = await db.get(DlqEntry, entry_id)
    task = celery_app.send_task(entry.task_name, args=entry.payload["args"])
    return {"task_id": task.id}
```

## DoD

- [ ] Exchange + queue `dead_letter`
- [ ] Queues prod ont `x-dead-letter-exchange`
- [ ] Métrique `celery_dlq_total`
- [ ] Endpoint admin replay
- [ ] Test : task échouée 5× → dans DLQ + métrique +1

---

# Story B6.S7.T4 — Migration ordonnée

## Contexte

**Sévérité** : P0 — switch broker = downtime potentiel si mal géré

### Description

Cible : runbook migration zero-downtime :
1. Déployer RabbitMQ parallèle Redis broker
2. Workers existants continuent de consommer Redis
3. Spawn nouveaux workers configurés AMQP (sur les mêmes queues)
4. Drain progressif Redis : un sous-ensemble de tasks routés vers RabbitMQ
5. Vérifier : queue length Redis baisse, RabbitMQ monte
6. Switch complet : `CELERY_BROKER_URL=amqp://...` partout, restart workers
7. Cleanup Redis queues legacy

## Solution

```bash
# Étape 1 : Deploy RabbitMQ
docker-compose up -d rabbitmq
# Étape 2 : Workers parallèle (legacy + new)
celery -A app worker --broker=redis://... -Q legacy_queue &  # legacy
celery -A app worker --broker=amqp://... -Q new_queue &       # new

# Étape 3 : Switch endpoint enqueue
# Modifier code endpoint pour publier vers AMQP

# Étape 4 : Drain Redis
# Attendre que LLEN celery_legacy → 0

# Étape 5 : Restart workers AMQP only
docker-compose restart workers

# Étape 6 : Cleanup
redis-cli DEL celery_legacy
```

### Test runbook

```python
async def test_dual_broker_period():
    """Pendant migration, vérifier que tasks Redis legacy ET RabbitMQ new fonctionnent."""
    legacy_task = legacy_celery.send_task("expire_devis")
    new_task = new_celery.send_task("expire_devis")
    assert legacy_task.get(timeout=10) is not None
    assert new_task.get(timeout=10) is not None
```

## DoD

- [ ] Runbook documenté
- [ ] Test dual-broker period
- [ ] Migration testée en staging avec rollback plan
- [ ] Pas de downtime ops critique

---

# Story B6.S7.T5 — Cleanup queues Redis legacy

## Solution

```bash
# Vérifier Redis queues vides
redis-cli LLEN celery
redis-cli LLEN celery_etl
# = 0 partout

# Drop queues
redis-cli DEL celery
redis-cli DEL celery_etl
redis-cli DEL celery_loyalty
```

```python
# Documentation : ne plus utiliser Redis pour broker
# Settings cleanup
# Drop deprecated env vars CELERY_REDIS_BROKER_URL
```

## DoD

- [ ] Redis broker keys droppées
- [ ] Settings cleanup
- [ ] Test : aucun worker écoute encore Redis broker

---

# Story B6.S7.T6 — Runbook ops + alerting

## Solution

```yaml
# alertmanager/rabbitmq.yml
- alert: RabbitMQQueueLengthHigh
  expr: rabbitmq_queue_messages > 5000
  for: 5m

- alert: RabbitMQNoConsumer
  expr: rabbitmq_queue_consumers == 0 and rabbitmq_queue_messages > 0
  for: 2m

- alert: RabbitMQDLQNotEmpty
  expr: celery_dlq_total > 0
  for: 1m
```

### Runbook

```markdown
# RabbitMQ Ops Runbook

## Incident: Queue length high
1. Check workers count: `docker ps | grep worker`
2. Scale: `docker-compose up -d --scale worker=10`
3. Check task duration: Grafana panel `celery_task_duration`

## Incident: DLQ messages
1. List: `GET /admin/dlq`
2. Investigate root cause (task error)
3. Replay or discard: `POST /admin/dlq/{id}/replay`
```

## DoD

- [ ] AlertManager rules
- [ ] Runbook documenté
- [ ] Dashboard Grafana RabbitMQ

---

## Critères de succès Sprint B6.S7

- [ ] **Q42=B livré** : RabbitMQ 3.13 broker + UI Management
- [ ] Celery configuration `task_acks_late=True` + prefetch=1
- [ ] DLQ natif via `x-dead-letter-exchange`
- [ ] Métrique `celery_dlq_total{task_name}` + endpoint admin replay
- [ ] Migration zero-downtime testée
- [ ] Cleanup Redis broker queues legacy
- [ ] Runbook ops + alertes
- [ ] **Bloc 6 verrouillé** : 7 sprints livrés (B6.S1 → B6.S7), TR-62 à TR-90 résolus

---

**Fin du document — 16-sprint-B6.S7.md**

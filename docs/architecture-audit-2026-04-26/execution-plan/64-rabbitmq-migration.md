# RabbitMQ Migration — Plan détaillé broker Redis → AMQP

> **Source de vérité** : Sprint B6.S7 (`16-sprint-B6.S7.md`)
> **Décision** : Q42=B verrouillée
> **Durée totale migration** : 1 semaine + 24h monitoring

---

## 1. Architecture cible

```
┌─────────────────┐         ┌─────────────────┐
│   FastAPI app   │  amqp:// │   RabbitMQ 3.13 │
│   (publishers)  │ ──────▶ │   (broker)      │
└─────────────────┘         │                 │
                            │   Queues:       │
┌─────────────────┐  amqp:// │   - email      │
│  Celery workers │ ◀────── │   - etl        │
│   (consumers)   │         │   - loyalty    │
└─────────────────┘         │   - dead_letter │
        │                   │                 │
        │   redis://         │   x-DLX exch   │
        ▼                   └─────────────────┘
┌─────────────────┐
│  Redis backend  │  ← results only (séparation broker ≠ backend)
│   (results)     │
└─────────────────┘
```

---

## 2. Pré-requis

- [ ] Bloc 6.S4 livré (Celery sessions async + heartbeat)
- [ ] Bloc 6.S6 livré (mTLS pour RabbitMQ Management UI)
- [ ] Backup Redis broker queues
- [ ] Communication ops sur Slack `#deploys`
- [ ] Maintenance window planifiée (samedi 02:00-04:00)

---

## 3. Phase 1 — Déploiement RabbitMQ parallèle (J-3)

### Docker Compose

```yaml
services:
  rabbitmq:
    image: rabbitmq:3.13-management
    container_name: devup-rabbitmq
    ports:
      - "5672:5672"      # AMQP
      - "15672:15672"    # Management UI (mTLS via nginx)
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
      RABBITMQ_DEFAULT_VHOST: devup
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
      - ./infra/rabbitmq/rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf
      - ./infra/rabbitmq/definitions.json:/etc/rabbitmq/definitions.json:ro
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 30s
      timeout: 10s
      retries: 5
```

### Definitions pré-load (queues + exchanges + bindings)

```json
// infra/rabbitmq/definitions.json
{
  "exchanges": [
    {"name": "celery", "type": "direct", "durable": true},
    {"name": "dlx", "type": "topic", "durable": true}
  ],
  "queues": [
    {"name": "email", "durable": true, "arguments": {"x-dead-letter-exchange": "dlx"}},
    {"name": "etl", "durable": true, "arguments": {"x-dead-letter-exchange": "dlx"}},
    {"name": "loyalty", "durable": true, "arguments": {"x-dead-letter-exchange": "dlx"}},
    {"name": "default", "durable": true, "arguments": {"x-dead-letter-exchange": "dlx"}},
    {"name": "dead_letter", "durable": true}
  ],
  "bindings": [
    {"source": "celery", "destination": "email", "routing_key": "email"},
    {"source": "celery", "destination": "etl", "routing_key": "etl"},
    {"source": "celery", "destination": "loyalty", "routing_key": "loyalty"},
    {"source": "celery", "destination": "default", "routing_key": "default"},
    {"source": "dlx", "destination": "dead_letter", "routing_key": "#"}
  ]
}
```

### Verify

```bash
docker-compose up -d rabbitmq
docker exec devup-rabbitmq rabbitmq-diagnostics ping
curl -u admin:pass http://localhost:15672/api/queues  # Management API
```

---

## 4. Phase 2 — Workers parallèles (J-2)

### Spawn workers AMQP en parallèle Redis

```bash
# Workers existants (Redis broker) continuent
celery -A app worker --broker=redis://redis:6379/0 -Q email,etl,loyalty -n redis-worker --loglevel=info

# Nouveaux workers (AMQP) sur même queues
celery -A app worker --broker=amqp://devup:pass@rabbitmq:5672/devup -Q email,etl,loyalty -n amqp-worker --loglevel=info
```

### Endpoints ne changent pas (publishent toujours sur Redis)

Pas de switch publisher pour l'instant.

### Verify dual workers

```bash
celery -A app inspect active_queues
# Retourne 2 workers : redis-worker (broker=redis), amqp-worker (broker=amqp)
```

---

## 5. Phase 3 — Switch progressif publishers (J0 — maintenance window 02:00-04:00)

### T0 : Publishers basculent sur AMQP

```python
# app/workers/celery_app.py
celery_app = Celery(
    "devup",
    broker=settings.CELERY_BROKER_URL,  # amqp://... (env switch)
    backend=settings.CELERY_RESULT_BACKEND_URL,  # redis:// (inchangé)
)

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    broker_transport_options={"confirm_publish": True},
)
```

### Deploy

```bash
# 1. Changer env var
sed -i 's|CELERY_BROKER_URL=redis://.*|CELERY_BROKER_URL=amqp://devup:pass@rabbitmq:5672/devup|' .env.production

# 2. Restart API (publishers maintenant AMQP)
kubectl rollout restart deployment/api

# 3. Verify
kubectl logs -l app=api | grep "broker amqp"
```

### T+15min : Drain Redis queues

```bash
# Attendre que LLEN celery → 0
while [ $(redis-cli LLEN celery) -gt 0 ]; do
  echo "Redis queue length: $(redis-cli LLEN celery)"
  sleep 10
done
```

### T+30min : Stop workers Redis

```bash
docker stop redis-worker
```

### T+45min : Verify AMQP only

```bash
celery -A app inspect active_queues
# Doit retourner uniquement amqp-worker
```

---

## 6. Phase 4 — Cleanup (J+1)

### Drop Redis broker keys

```bash
redis-cli DEL celery
redis-cli DEL celery_email
redis-cli DEL celery_etl
redis-cli DEL celery_loyalty
redis-cli DEL _kombu.binding.celery
```

### Nettoyer settings

```python
# Drop deprecated env vars
# CELERY_REDIS_BROKER_URL → suppression
# Documentation : tenir à jour
```

---

## 7. Tests post-migration

### Smoke tests obligatoires

```python
# tests/smoke/test_rabbitmq_migration.py
async def test_task_routes_to_rabbitmq():
    task = send_email_task.delay(to="test@example.com", subject="...", ...)
    # Vérifier queue RabbitMQ
    assert get_rabbitmq_queue_length("email") > 0
    # Wait for processing
    assert task.get(timeout=30) is not None

async def test_dlq_works_after_5_retries():
    # Simulate task qui fail toujours
    failing_task.delay()
    time.sleep(60)  # Wait retries
    assert get_rabbitmq_queue_length("dead_letter") > 0
```

### Smoke tests métier

- [ ] Login OK
- [ ] Create devis OK (publish task `audit_log`)
- [ ] Convert devis OK (publish task `outbox_dispatch`)
- [ ] Email send OK
- [ ] ETL import OK

---

## 8. Monitoring 24h post-deploy

### Métriques à surveiller

```yaml
# AlertManager
- alert: RabbitMQQueueDepthHigh
  expr: rabbitmq_queue_messages{queue=~"email|etl|loyalty"} > 10000
  for: 10m

- alert: RabbitMQNoConsumer
  expr: rabbitmq_queue_consumers == 0 and rabbitmq_queue_messages > 0
  for: 5m

- alert: AMQPConnectionDrop
  expr: increase(rabbitmq_connection_closed_total[10m]) > 5
  for: 5m
```

### Dashboard Grafana panel

- RabbitMQ queue length per queue
- Consumer count
- Message rate (in/out)
- Connection count
- Memory usage RabbitMQ

---

## 9. Rollback plan

### Si migration échoue à T0-T+15min

```bash
# 1. Revert env var
sed -i 's|CELERY_BROKER_URL=amqp://.*|CELERY_BROKER_URL=redis://redis:6379/0|' .env.production

# 2. Restart API + workers
kubectl rollout restart deployment/api
docker start redis-worker
docker stop amqp-worker

# 3. Verify Redis broker en service
celery -A app inspect active_queues
```

### Si rollback après cleanup (Phase 4)

⚠️ **Plus complexe** : Redis broker keys droppées.
- Restore Redis backup
- Re-spawn workers
- Re-publish AMQP queue messages bloqués vers Redis

---

## 10. Risques + mitigations

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| RabbitMQ down post-deploy | Faible | Élevé | Pre-deploy : healthcheck + replication HA |
| Task lost pendant switch | Moyen | Moyen | `task_acks_late=True` + drain Redis |
| Performance dégradée | Faible | Moyen | RabbitMQ benchmark < Redis broker mais < 10ms p99 |
| DLQ ignored par ops | Moyen | Faible | AlertManager rule + dashboard panel |

---

**Fin du document — 64-rabbitmq-migration.md**

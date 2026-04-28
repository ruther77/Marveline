# Observability Rollout — Dashboards Grafana + AlertManager + Loki queries

> **Objectif** : observabilité complète pendant les 36 sprints — sans drift entre métriques techniques et métiers.
> **Stack** : Prometheus + Grafana + Loki + Tempo (post-Bloc 6.S6 OpenTelemetry).

---

## 1. Dashboards Grafana par bloc

### Dashboard 1 — `DEVUP / API Health`

Panels :
- HTTP requests rate (`http_requests_total`)
- Latency p50/p95/p99 (`http_request_duration_seconds`)
- Error rate per endpoint (`http_requests_total{status=~"5.."}`)
- Active sessions (`session_count`)
- DB connection pool (`db_pool_size`, `db_pool_used`)

### Dashboard 2 — `DEVUP / Money`

Panels (post-Bloc 3) :
- Devis créés/h, conversions/h
- Reservations confirmed/h
- Invoices émises/h + total CA
- Loyalty points earned/expired
- Email gateway success rate (Postmark)
- Dunning queue length + dead_letter count

### Dashboard 3 — `DEVUP / Stock & ETL`

Panels (post-Bloc 4 + 5) :
- Stock available per tenant (top 20 products)
- Stock movements/h (entries vs exits)
- ETL imports : SUCCES/PARTIEL/ECHEC count
- ETL processing duration p99
- Vendor matching AWAITING queue

### Dashboard 4 — `DEVUP / Audit & Security`

Panels (post-Bloc 6.S2) :
- Audit logs/h
- ATTEMPT_DENIED count (login fails, RBAC denied)
- HMAC chain verify status (last_verified_at)
- PII export requests (RGPD Article 15)
- Feature flag changes/h

### Dashboard 5 — `DEVUP / Celery & Workers`

Panels (post-Bloc 6.S4 + S7) :
- Tasks per queue : enqueued/processed/failed
- Task duration p99 per task_name
- Beat heartbeat (last_run_seconds_ago)
- DLQ count per task_name (post-RabbitMQ)
- Worker count alive

### Dashboard 6 — `DEVUP / Rollout Metrics`

Panels :
- Feature flag rollout % per flag
- Canary error rate (flag=true vs flag=false)
- Migration progress (rows migrated / total)
- Deploy frequency

---

## 2. AlertManager rules

### Rules critiques (P0 → page on-call)

```yaml
- alert: APIDown
  expr: up{job="devup-api"} == 0
  for: 1m
  
- alert: DBConnectionPoolExhausted
  expr: db_pool_used / db_pool_size > 0.9
  for: 5m

- alert: AuditChainBroken
  expr: increase(audit_chain_broken_total[1h]) > 0
  for: 0m
  
- alert: CrossTenantLeakDetected
  expr: increase(cross_tenant_access_total[1h]) > 0
  for: 0m
  severity: P0
```

### Rules majeures (P1 → Slack alert)

```yaml
- alert: HighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.01
  for: 10m

- alert: CeleryBeatDown
  expr: celery_beat_last_run_seconds_ago > 120
  for: 1m

- alert: EmailGatewayDegraded
  expr: rate(email_send_failures_total[10m]) / rate(email_send_total[10m]) > 0.05
  for: 10m

- alert: RabbitMQQueueBacklog
  expr: rabbitmq_queue_messages > 5000
  for: 5m

- alert: FeatureFlagFailSafeTriggered
  expr: increase(ff_fail_safe_triggered_total[5m]) > 0
  for: 1m
```

### Rules mineures (P2 → ticket Linear auto)

```yaml
- alert: StockViewStale
  expr: time() - product_stock_view_last_refresh_seconds > 600
  for: 10m

- alert: DLQGrowing
  expr: increase(celery_dlq_total[1h]) > 10
  for: 0m
```

---

## 3. Loki queries (logs structurés)

### Recherches types

```logql
# Erreurs auth
{app="devup-api"} |= "auth" |= "ATTEMPT_DENIED"

# Audit cross-tenant tentatives
{app="devup-api"} |~ "cross_tenant" |~ "denied"

# Slow queries SQL
{app="devup-api"} | json | duration > 1s | line_format "{{.query}} {{.duration}}"

# Celery tasks failed
{app="devup-celery"} |= "task_failed" | json | line_format "{{.task_name}} {{.exception}}"

# ETL errors per tenant
{app="devup-api"} |~ "etl_error" | json | tenant_id="42"
```

### Saved searches

- `Cross-tenant violations 24h`
- `Failed payments today`
- `MFA bypass attempts`
- `Audit chain breaks last 7d`

---

## 4. Tempo distributed tracing (post-Bloc 6.S6)

### Critical traces à investiguer

1. **Devis conversion** : `convert_devis_to_reservation` span complet (lock → reserve_stock → invoice → outbox)
2. **Login + MFA + scope resolution** : `auth.login` → `mfa.verify` → `scope.resolve`
3. **ETL import** : `etl.parse → vendor_resolve → categorize → match → finalize`
4. **Print job** : `print.enqueue → wireguard.send → printer.execute`

### Trace_id propagation chain

```
Frontend (TanStack Query) → API (FastAPI) → Celery (task_send) → WG handler (httpx)
                          → SQL queries (SQLAlchemy)
                          → Redis ops
```

Search Tempo : `trace_id="abc-123"` retourne le span complet.

---

## 5. SLO globaux

| SLO | Cible | Mesure |
|---|---|---|
| Uptime API | 99.5% / mois | `up{job="devup-api"}` |
| Latency p99 / endpoint critique | < 500ms | `histogram_quantile(0.99, http_request_duration)` |
| Email gateway success | > 99% | Postmark API |
| Audit chain integrity | 100% | nightly verify_chain_task |
| RGPD export delivery | < 24h | task duration P99 |

### Error budget

50% du budget consommé = freeze features non-critiques, focus stabilité.

---

## 6. Onboarding ops post-Bloc 6.S6

Pour chaque ops qui rejoint :
1. Accès Grafana (lecture)
2. Accès AlertManager Slack channel
3. Lecture des 6 dashboards
4. Runbooks `61-zero-downtime-strategy.md` + `62-rollback-plans.md`
5. Shadow on-call 1 semaine
6. Solo on-call (rotation)

---

## 7. Rollout des dashboards par sprint

| Bloc | Dashboard rollout | Sprint trigger |
|---|---|---|
| Bloc 1 | API Health (basic) | B1.S5 |
| Bloc 2 | + Auth metrics | B2.S4 |
| Bloc 3 | + Money + Email | B3.S5 |
| Bloc 4 | + Stock view | B4.S2 |
| Bloc 5 | + ETL | B5.S2 |
| Bloc 6.S2 | + Audit | B6.S2 |
| Bloc 6.S4 | + Celery | B6.S4 |
| Bloc 6.S6 | + OpenTelemetry traces | B6.S6 |
| Bloc 6.S7 | + RabbitMQ DLQ | B6.S7 |
| Bloc 7 | + AppSelector usage | B7.S3 |

---

**Fin du document — 63-observability-rollout.md**

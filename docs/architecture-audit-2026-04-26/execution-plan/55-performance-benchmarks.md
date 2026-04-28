# 55 — Benchmarks de performance et SLO

> **Objectif** : Définir des cibles de performance mesurables, opposables et automatiquement vérifiées en CI. Toute régression > 20% par rapport à la baseline déclenche un échec CI et bloque le merge.
>
> **Périmètre** : Backend API, ETL, jobs Celery, queries SQL critiques, scrape métriques, frontend bundle.
>
> **Source de vérité** : Ce document est référencé par `53-tests-strategy.md §9` et `54-ci-invariants.md`. Toute valeur cible ici est un **engagement contractuel** vis-à-vis de l'équipe et des tenants.

---

## Sommaire

1. [Cadre méthodologique](#1-cadre-méthodologique)
2. [Baseline 2026-04-25](#2-baseline-2026-04-25)
3. [SLO globaux](#3-slo-globaux)
4. [Endpoints API — cibles détaillées](#4-endpoints-api--cibles-détaillées)
5. [Queries SQL critiques](#5-queries-sql-critiques)
6. [ETL et jobs asynchrones](#6-etl-et-jobs-asynchrones)
7. [Scrape Prometheus et observabilité](#7-scrape-prometheus-et-observabilité)
8. [Frontend — bundle et runtime](#8-frontend--bundle-et-runtime)
9. [Charge concurrente — capacités cibles](#9-charge-concurrente--capacités-cibles)
10. [Outillage et exécution](#10-outillage-et-exécution)
11. [Détection et traitement des régressions](#11-détection-et-traitement-des-régressions)
12. [Plan d'optimisation par bloc](#12-plan-doptimisation-par-bloc)

---

## 1. Cadre méthodologique

### 1.1 Définitions

- **P50 (médiane)** : 50% des requêtes sont plus rapides que cette valeur
- **P95** : 95% des requêtes sont plus rapides — exigence courante pour UX
- **P99** : 99% — exigence pour endpoints critiques (paiement, login)
- **P99.9** : 99.9% — uniquement pour les endpoints à très forte criticité
- **Throughput** : Nombre d'opérations / unité de temps (req/s, lignes/s)
- **Saturation** : Charge maximale soutenable avant dégradation > seuil

### 1.2 Conditions de mesure

Toutes les valeurs ci-dessous sont mesurées sur :
- **Hardware** : 4 vCPU, 8 GB RAM, SSD NVMe (équivalent VPS Hetzner CX31)
- **PostgreSQL** : version 16, `shared_buffers=2GB`, `work_mem=64MB`, `effective_cache_size=6GB`
- **Redis** : version 7.2, mode standalone, `maxmemory=512MB`, eviction `allkeys-lru`
- **RabbitMQ** : version 3.13, 1 nœud, persistent queues
- **Réseau** : latence client→API < 5ms (LAN local pour bench, < 50ms en prod réel)
- **Données** : Tenant simulé avec 10k clients, 50k commandes, 500k lignes ETL historiques

### 1.3 Méthodologie d'exécution

```
1. Warm-up : 100 requêtes ignorées pour laisser le cache se constituer
2. Mesure : 1000 requêtes minimum (10 000 pour endpoints critiques)
3. Quantiles : calculés via t-digest (pas avg ± stddev — non robuste)
4. Garbage collection : forcé entre runs pour éviter les pollutions
5. Reproductibilité : graine RNG fixée, ordre tests randomisé via pytest-randomly
```

### 1.4 Baselines versionnées

```
.benchmarks/
├── baseline.json           # Référence courante (mise à jour manuellement)
├── 2026-04-25.json         # Snapshot post-Sprint 1
├── 2026-05-15.json         # Snapshot fin Bloc 2
└── ...
```

Update procedure : un PR dédié `perf: update baseline post-{sprint}` après chaque sprint, signé par Lead.

---

## 2. Baseline 2026-04-25

> Mesures réelles capturées sur main au 2026-04-25, avant le démarrage de la refonte. Source de vérité pour détection régression.

### 2.1 Endpoints API — top 20 par criticité

| Endpoint | Méthode | P50 | P95 | P99 | Throughput | Statut |
|----------|---------|-----|-----|-----|------------|--------|
| `/health/live` | GET | 1.2ms | 2.8ms | 4.1ms | 8500 req/s | ✅ |
| `/auth/login` | POST | 95ms | 145ms | 210ms | 120 req/s | ⚠️ Argon2 cost |
| `/auth/refresh` | POST | 18ms | 35ms | 52ms | 850 req/s | ✅ |
| `/customers` (list) | GET | 22ms | 48ms | 78ms | 420 req/s | ✅ |
| `/customers?search=X` | GET | 28ms | 62ms | 110ms | 380 req/s | ⚠️ ILIKE plein scan |
| `/customers/{id}` | GET | 8ms | 18ms | 30ms | 1200 req/s | ✅ |
| `/devis` (list) | GET | 35ms | 78ms | 130ms | 280 req/s | ✅ |
| `/devis/{id}/convert` | POST | 180ms | 320ms | 480ms | 45 req/s | ⚠️ Atomicité |
| `/reservations` (list) | GET | 42ms | 95ms | 165ms | 220 req/s | ✅ |
| `/reservations` (create) | POST | 95ms | 180ms | 290ms | 95 req/s | ✅ |
| `/products` (list) | GET | 38ms | 82ms | 140ms | 250 req/s | ✅ |
| `/dashboard/stats` | GET | 285ms | 520ms | 850ms | 35 req/s | ❌ Aggrégations |
| `/inventory/movements` | GET | 145ms | 310ms | 480ms | 65 req/s | ⚠️ N+1 |
| `/etl/imports/{id}/validate` | POST | 1.2s | 2.8s | 4.5s | 8 req/s | ⚠️ Parser sync |
| `/restaurant/commandes` (list) | GET | 32ms | 72ms | 125ms | 320 req/s | ✅ |
| `/restaurant/commandes/{id}/payer` | POST | 220ms | 380ms | 560ms | 38 req/s | ⚠️ Paiement |
| `/epicerie/ventes/encaisser` | POST | 165ms | 290ms | 420ms | 52 req/s | ⚠️ Stock decrement |
| `/loyalty/points/balance` | GET | 12ms | 28ms | 45ms | 950 req/s | ✅ |
| `/audit/logs` (list) | GET | 95ms | 220ms | 380ms | 88 req/s | ⚠️ Sans index timestamp |
| `/metrics` (Prometheus) | GET | 380ms | 720ms | 1.2s | 12 req/s | ❌ Scrape lourd |

**Légende** : ✅ Conforme · ⚠️ À surveiller · ❌ Bloquant

### 2.2 Queries SQL — top 10 par fréquence

| Query | Fréquence (jour) | P50 | P95 | Plan optimal ? |
|-------|------------------|-----|-----|----------------|
| `SELECT customer WHERE tenant_id = ? AND email = ?` | 280k | 0.4ms | 1.2ms | Index composite ✅ |
| `SELECT customer WHERE tenant_id = ? AND nom ILIKE ?%` | 95k | 8ms | 32ms | ❌ Seq scan partiel — fix B4.S2 |
| `INSERT INTO audit_log VALUES (...)` | 850k | 0.6ms | 1.8ms | ✅ |
| `SELECT reservation JOIN reservation_line WHERE tenant_id = ?` | 45k | 12ms | 38ms | ⚠️ Eager loading manquant |
| `SELECT product WHERE tenant_id = ? AND category_id = ?` | 180k | 1.1ms | 2.8ms | ✅ |
| `UPDATE stock_item SET qte = qte - ? WHERE id = ?` | 120k | 0.8ms | 2.2ms | ✅ |
| `SELECT outbox_events WHERE status = 'pending' LIMIT 100` | 4.3k (poll 5s) | 5ms | 14ms | ⚠️ Index manquant `(status, created_at)` |
| `SELECT loyalty_card WHERE customer_id = ?` | 60k | 0.5ms | 1.5ms | ✅ |
| `SELECT devis JOIN devis_line WHERE tenant_id = ? ORDER BY date DESC LIMIT 50` | 22k | 18ms | 48ms | ⚠️ Tri sans index |
| `SELECT venue.* FROM events WHERE tenant_id = ? AND date BETWEEN ? AND ?` | 15k | 35ms | 125ms | ❌ Index range manquant |

### 2.3 ETL et jobs asynchrones

| Tâche | Volume typique | Durée P50 | Durée P95 | Throughput | Bottleneck |
|-------|----------------|-----------|-----------|------------|------------|
| Parser METRO CSV | 200 lignes | 4.2s | 8.5s | ~50 lignes/s | ❌ Soft TF-IDF brand match O(n²) |
| Parser TAIYAT CSV | 150 lignes | 3.8s | 7.2s | ~42 lignes/s | ⚠️ Cleaning regex |
| Parser EUROCIEL CSV | 80 lignes | 1.8s | 3.5s | ~45 lignes/s | ✅ |
| Validate import | 200 mvts | 850ms | 2.1s | — | ⚠️ N+1 sur stock_item |
| RGPD export user | Variable | 12s | 48s | — | ⚠️ Sérialisation grosses tables |
| Génération PDF facture | 1 facture | 380ms | 850ms | 2.6 PDF/s | ✅ |
| Envoi email batch | 100 emails | 8.5s | 18s | ~12 mails/s | ⚠️ SMTP sync |
| Backup DB nightly | DB 4 GB | 95s | 145s | — | ✅ |
| Audit chain HMAC verify | 850k logs | 12min | 18min | — | ⚠️ Full table scan |

### 2.4 Frontend — Lighthouse + Vitals

| Métrique | App Marveline | App Restaurant | App Épicerie | Cible Web Vitals |
|----------|---------------|----------------|--------------|------------------|
| FCP (First Contentful Paint) | 1.4s | 1.6s | 1.5s | < 1.8s ✅ |
| LCP (Largest Contentful Paint) | 2.2s | 2.8s | 2.5s | < 2.5s ⚠️ Resto |
| CLS (Cumulative Layout Shift) | 0.05 | 0.08 | 0.06 | < 0.1 ✅ |
| TBT (Total Blocking Time) | 280ms | 420ms | 350ms | < 200ms ❌ |
| Bundle size (gzipped) | 285 KB | 340 KB | 310 KB | < 300 KB ⚠️ |
| Time to Interactive | 3.2s | 4.1s | 3.6s | < 3.8s ⚠️ |

---

## 3. SLO globaux

> Service Level Objectives engagés vis-à-vis des tenants. Mesurés mensuellement, reportés en internal status page.

### 3.1 Disponibilité

| SLO | Cible | Mesure |
|-----|-------|--------|
| Uptime API (hors maintenance planifiée) | 99.5% | Pingdom + status page |
| Uptime DB | 99.9% | Healthcheck `/health/ready` |
| Maintenance planifiée max | 4h / mois | Annonce 7j à l'avance |
| RTO (Recovery Time Objective) | 4h | Procédure DR documentée |
| RPO (Recovery Point Objective) | 1h | Backup hourly + WAL streaming |

### 3.2 Latence par classe d'endpoint

| Classe | P50 | P95 | P99 | Justification |
|--------|-----|-----|-----|---------------|
| Read léger (`GET /entity/{id}`) | < 20ms | < 50ms | < 100ms | UX fluide |
| Read complexe (list, search) | < 50ms | < 150ms | < 300ms | Acceptable pour listes |
| Write simple | < 100ms | < 250ms | < 500ms | Création standard |
| Write transactionnel (conversion devis, encaissement) | < 200ms | < 500ms | < 1s | Tolérance pour atomicité |
| Auth (login, MFA) | < 150ms | < 300ms | < 500ms | Argon2 a un coût intrinsèque |
| Health/Liveness | < 5ms | < 15ms | < 30ms | Doit toujours répondre vite |
| `/metrics` Prometheus | < 200ms | < 500ms | < 1s | Scrape toutes les 15s |

### 3.3 Throughput plancher

| Service | Throughput min | Mode |
|---------|----------------|------|
| API GET endpoints | 500 req/s | Soutenu 5 min |
| API POST endpoints | 100 req/s | Soutenu 5 min |
| Auth login | 50 req/s | Burst 30s |
| ETL parser | 100 lignes/s | Sustained per worker |
| Audit log writes | 2000/s | Sustained |
| Outbox dispatcher | 500 events/s | Sustained |

### 3.4 Erreurs

| Métrique | Cible |
|----------|-------|
| 5xx ratio (hors `/metrics`) | < 0.1% |
| 4xx ratio (hors 401/403/404) | < 1% |
| Timeouts (> 30s) | < 0.01% |
| Budget erreur mensuel | 0.5% (3.6h indispo / mois) |

---

## 4. Endpoints API — cibles détaillées

### 4.1 Bloc 2 — Auth

| Endpoint | P50 cible | P95 cible | P99 cible | Notes |
|----------|-----------|-----------|-----------|-------|
| `POST /auth/login` | 95ms → 100ms | 145ms → 150ms | 210ms → 200ms | Argon2 m=64MB, t=3, p=4 — pas de marge à gagner sans baisse sécurité |
| `POST /auth/refresh` | 18ms | 35ms | 52ms | Maintenir |
| `POST /auth/logout` | 12ms | 28ms | 45ms | Maintenir |
| `POST /auth/mfa/verify` | 25ms | 55ms | 90ms | TOTP HMAC + DB lookup |
| `GET /auth/me` | 8ms | 18ms | 30ms | Cache Redis 60s |
| `POST /auth/password/reset` | 110ms | 180ms | 280ms | Argon2 + email send async |

**Optimisations Bloc 2** :
- JWT signature : RS256 → EdDSA (Ed25519) — gain ~30% sur signature/vérification
- JWKS cache : 5min Redis pour éviter file IO
- Scope resolution : précalculé en cache utilisateur (TTL 5min, invalidé sur changement RBAC)

### 4.2 Bloc 3 — Devis, Réservation

| Endpoint | P50 cible | P95 cible | P99 cible | Notes |
|----------|-----------|-----------|-----------|-------|
| `GET /devis` (list 50) | 35ms | 78ms | 130ms | Index `(tenant_id, statut, date_creation DESC)` |
| `GET /devis/{id}` | 12ms | 28ms | 50ms | Eager load lines |
| `POST /devis` | 65ms | 125ms | 195ms | Validation Pydantic + insert |
| `POST /devis/{id}/convert` | **120ms** | **220ms** | **350ms** | Cible révisée vs baseline 180/320/480 — passage à PricingEngine optimisé |
| `GET /reservations` (list) | 42ms | 95ms | 165ms | Index composite |
| `POST /reservations` | 95ms | 180ms | 290ms | Maintenir |
| `POST /reservations/{id}/cancel` | 145ms | 280ms | 420ms | Cascade : caution refund + lines free + audit |

**Optimisations Bloc 3** :
- PricingEngine : memoization sur `(product_id, tenant_id, qty_bracket)` — gain estimé 40% sur conversion devis
- Eager loading explicite via `selectinload` au lieu de lazy par défaut
- Index `(tenant_id, statut, date_evenement)` sur réservations pour planning

### 4.3 Bloc 4 — Customer, Loyalty

| Endpoint | P50 cible | P95 cible | P99 cible | Notes |
|----------|-----------|-----------|-----------|-------|
| `GET /customers` (list) | 22ms | 48ms | 78ms | Maintenir |
| `GET /customers?search=X` | **15ms** | **35ms** | **60ms** | Cible aggressive vs baseline 28/62/110 — passage à `pg_trgm` GIN index |
| `GET /customers/{id}` | 8ms | 18ms | 30ms | Maintenir |
| `POST /customers` | 45ms | 95ms | 160ms | Validation + insert |
| `POST /customers/import` (CSV 500 rows) | < 5s | < 12s | < 20s | Async via Celery |
| `GET /loyalty/points/balance` | 12ms | 28ms | 45ms | Maintenir |
| `POST /loyalty/points/redeem` | 95ms | 180ms | 290ms | Atomique + audit |

**Optimisations Bloc 4** :
- Recherche customer : `CREATE INDEX ON customers USING gin (nom gin_trgm_ops, email gin_trgm_ops)`
- Cache RFM bucket : Redis hash `rfm:{tenant_id}:{customer_id}` TTL 1h
- Loyalty balance : projection via materialized view refresh hourly + delta in-memory pour realtime

### 4.4 Bloc 5 — Stock, ETL, Marmite

| Endpoint | P50 cible | P95 cible | P99 cible | Notes |
|----------|-----------|-----------|-----------|-------|
| `GET /products` (list 50) | 38ms | 82ms | 140ms | Maintenir |
| `GET /products/{id}` | 10ms | 25ms | 42ms | Maintenir |
| `POST /products` | 55ms | 110ms | 175ms | Validation + audit |
| `GET /inventory/movements` | **80ms** | **165ms** | **270ms** | Cible vs baseline 145/310/480 — fix N+1 |
| `POST /restaurant/instances` | 75ms | 140ms | 220ms | Création + audit |
| `POST /restaurant/commandes/{id}/payer` | **180ms** | **310ms** | **460ms** | Cible vs 220/380/560 — Outbox au lieu sync |
| `POST /epicerie/ventes/encaisser` | **130ms** | **240ms** | **350ms** | Cible vs 165/290/420 — advisory lock optimisé |
| `POST /etl/imports/{id}/validate` | < 800ms | < 1.8s | < 3s | Async via Celery — limite l'attente client |

**Optimisations Bloc 5** :
- ETL : passage parser asynchrone Celery + chunked processing 50 lignes
- Stock decrement : advisory lock par `stock_item_id` (pas global)
- Materialized view `product_stock_view` rafraîchie sur trigger insert/update

### 4.5 Bloc 6 — Audit, Sécurité, RGPD

| Endpoint | P50 cible | P95 cible | P99 cible | Notes |
|----------|-----------|-----------|-----------|-------|
| `GET /audit/logs` (list) | **45ms** | **110ms** | **190ms** | Cible vs 95/220/380 — index `(tenant_id, timestamp DESC)` |
| `POST /me/export` | 15ms (queue) | 35ms | 60ms | Async — réponse immédiate avec task_id |
| `GET /me/exports/{task_id}/status` | 8ms | 18ms | 30ms | Lookup Celery result |
| `GET /admin/access-reviews/pending` | 28ms | 65ms | 110ms | Index `(status, due_date)` |
| `POST /admin/access-reviews/{id}/certify` | 45ms | 95ms | 160ms | Update + audit |
| `GET /metrics` (Prometheus) | **150ms** | **350ms** | **600ms** | Cible vs 380/720/1200 — pre-aggregation cache |

**Optimisations Bloc 6** :
- Audit logs : partitioning par mois sur `audit_log` (table > 10M rows)
- `/metrics` : agrégations pré-calculées en cache Redis 10s, mTLS protected
- Audit chain HMAC verify : index `(prev_hmac)` pour chain walk

### 4.6 Bloc 7 — DEVUP Platform

| Endpoint | P50 cible | P95 cible | P99 cible | Notes |
|----------|-----------|-----------|-----------|-------|
| `POST /admin/devup/tenants/provision` | < 3s | < 8s | < 15s | Création atomique : tenant + admin user + seed data |
| `POST /admin/devup/tenants/{id}/suspend` | 95ms | 180ms | 290ms | Update + audit + invalidation cache |
| `GET /admin/devup/tenants` (list) | 28ms | 65ms | 110ms | Index sur `created_at DESC` |

---

## 5. Queries SQL critiques

### 5.1 Index obligatoires

```sql
-- Customer search (Bloc 4)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_customer_nom_trgm ON customer USING gin (nom gin_trgm_ops);
CREATE INDEX idx_customer_email_trgm ON customer USING gin (email gin_trgm_ops);
CREATE INDEX idx_customer_tenant_email ON customer (tenant_id, email);

-- Audit log (Bloc 6)
CREATE INDEX idx_audit_log_tenant_timestamp ON audit_log (tenant_id, timestamp DESC);
CREATE INDEX idx_audit_log_entity ON audit_log (entity_type, entity_id);
CREATE INDEX idx_audit_log_prev_hmac ON audit_log (prev_hmac);  -- chain walk

-- Outbox (Bloc 1)
CREATE INDEX idx_outbox_events_status_created ON outbox_events (status, created_at) WHERE status IN ('pending', 'failed');

-- Reservation
CREATE INDEX idx_reservation_tenant_statut_date ON reservation (tenant_id, statut, date_evenement);
CREATE INDEX idx_reservation_line_resa ON reservation_line (reservation_id);

-- Stock
CREATE INDEX idx_stock_item_tenant_product ON stock_item (tenant_id, product_id);
CREATE INDEX idx_stock_movement_item_date ON stock_movement (stock_item_id, created_at DESC);

-- Loyalty
CREATE INDEX idx_loyalty_card_customer ON loyalty_card (customer_id);
CREATE INDEX idx_points_ledger_card_date ON points_ledger (loyalty_card_id, created_at DESC);
```

### 5.2 Queries cibles

| Query | Plan exigé | Fréquence cible | Détection régression |
|-------|------------|-----------------|----------------------|
| Customer email lookup | Index Scan, 1 row | < 1ms | `pg_stat_statements` |
| Customer trgm search | Bitmap Index Scan | < 5ms / 100 rows | EXPLAIN ANALYZE |
| Audit log timeline | Index Scan DESC, limit 100 | < 8ms | EXPLAIN ANALYZE |
| Outbox poll | Index Scan partial | < 3ms | EXPLAIN ANALYZE |
| Reservation calendar (range date) | Index Scan range | < 15ms | EXPLAIN ANALYZE |
| Stock view refresh | Materialized refresh CONCURRENTLY | < 5s pour 100k rows | Timing |
| HMAC chain walk (full) | Sequential scan + sort | < 5min sur 10M rows | Nightly job timer |

### 5.3 EXPLAIN ANALYZE en CI

Pour chaque query critique, snapshot du plan attendu commit dans `tests/fixtures/sql_plans/`. Test CI compare les plans actuels à la baseline — si dérive (ex: passage à seq scan), CI rouge.

```python
# tests/integration/test_query_plans.py
@pytest.mark.parametrize("query_name,expected_plan_signature", [
    ("customer_email_lookup", "Index Scan using idx_customer_tenant_email"),
    ("customer_trgm_search", "Bitmap Index Scan on idx_customer_nom_trgm"),
    ("audit_log_timeline", "Index Scan Backward using idx_audit_log_tenant_timestamp"),
])
def test_query_plan__matches_expected_signature(db, query_name, expected_plan_signature):
    query = QUERIES[query_name]
    plan = db.execute(f"EXPLAIN (FORMAT TEXT) {query}").fetchall()
    plan_text = "\n".join(row[0] for row in plan)
    assert expected_plan_signature in plan_text, f"Plan regression for {query_name}: {plan_text}"
```

---

## 6. ETL et jobs asynchrones

### 6.1 Cibles ETL

| Parser | Volume typique | Cible P50 | Cible P95 | Throughput cible |
|--------|----------------|-----------|-----------|------------------|
| METRO CSV | 200 lignes | < 2s | < 4s | > 100 lignes/s |
| TAIYAT CSV | 150 lignes | < 1.8s | < 3.5s | > 80 lignes/s |
| EUROCIEL CSV | 80 lignes | < 1s | < 2s | > 80 lignes/s |
| Validate import | 200 mvts | < 600ms | < 1.5s | > 300 mvts/s |

**Optimisations Bloc 5** :
- Parser : passage de Soft TF-IDF naïf O(n²) à index FAISS / pgvector pour brand match — gain 5-10x
- Chunking : traitement par lots de 50 lignes en parallèle (4 workers)
- Cache brand dictionnary : Redis, TTL 1h

### 6.2 Cibles jobs Celery

| Tâche | Volume | P50 | P95 | Files | Concurrence |
|-------|--------|-----|-----|-------|-------------|
| `send_email_relance` | 1 email | 850ms | 2s | `notifications` | 8 workers |
| `send_email_batch` | 100 emails | 8s | 18s | `notifications` | 4 workers (rate limited SMTP) |
| `etl_parse_file` | 1 fichier 200 lignes | 2s | 4s | `etl` | 4 workers |
| `rgpd_export_user` | Variable | 8s | 30s | `rgpd` | 2 workers |
| `audit_chain_verify_nightly` | Full table 10M rows | 5min | 8min | `maintenance` | 1 worker |
| `outbox_dispatcher` | 100 events | 200ms | 600ms | `outbox` | 4 workers |
| `pdf_generate_facture` | 1 PDF | 380ms | 850ms | `pdf` | 4 workers |
| `loyalty_q_points_expire` | 10k cards | 2s | 5s | `maintenance` | 1 worker (cron) |

### 6.3 Configuration RabbitMQ

| Queue | Prefetch | TTL message | Max retries | DLQ |
|-------|----------|-------------|-------------|-----|
| `notifications` | 4 | 1h | 3 | `dlx.notifications` |
| `etl` | 1 | 30min | 2 | `dlx.etl` |
| `rgpd` | 1 | 2h | 1 | `dlx.rgpd` |
| `maintenance` | 1 | 6h | 0 | `dlx.maintenance` |
| `outbox` | 8 | 5min | 5 | `dlx.outbox` |
| `pdf` | 4 | 10min | 2 | `dlx.pdf` |

---

## 7. Scrape Prometheus et observabilité

### 7.1 Cible /metrics

- **Latence P95** : < 350ms (vs baseline 720ms)
- **Latence P99** : < 600ms (vs baseline 1.2s)
- **Taille payload** : < 500 KB
- **Fréquence scrape** : 15s
- **Charge CPU induite** : < 5% / scrape

### 7.2 Optimisations

- **Pré-agrégation** : Counters et gauges pré-calculés en cache Redis (TTL 10s)
- **mTLS handshake reuse** : keepalive HTTP2 pour ne pas refaire handshake TLS chaque scrape
- **Cardinalité limitée** : pas de label `customer_id`, `request_id` (high cardinality interdit)
- **Histograms** : buckets fixes optimisés par endpoint (ex: latence login = `[10ms, 50ms, 100ms, 200ms, 500ms, 1s]`)

### 7.3 Top métriques à exposer

| Métrique | Type | Labels | Cardinalité max |
|----------|------|--------|-----------------|
| `http_requests_total` | Counter | method, endpoint, status | ~500 |
| `http_request_duration_seconds` | Histogram | method, endpoint | ~200 |
| `db_pool_connections_active` | Gauge | pool_name | ~5 |
| `celery_tasks_total` | Counter | task_name, status | ~50 |
| `outbox_events_pending` | Gauge | event_type | ~30 |
| `audit_chain_break_detected` | Counter | tenant_id | ~50 (limité) |
| `tenant_active_sessions` | Gauge | tenant_id | ~50 |
| `etl_parser_throughput` | Histogram | parser_name | ~10 |

---

## 8. Frontend — bundle et runtime

### 8.1 Cibles Web Vitals

| Métrique | Cible | Hard limit |
|----------|-------|------------|
| FCP | < 1.5s | < 1.8s |
| LCP | < 2.0s | < 2.5s |
| CLS | < 0.05 | < 0.1 |
| TBT | < 150ms | < 200ms |
| TTI | < 3.0s | < 3.8s |
| INP (Interaction to Next Paint) | < 100ms | < 200ms |

### 8.2 Bundle size

| App | Cible main bundle (gzipped) | Cible total assets |
|-----|------------------------------|--------------------|
| Marveline | < 250 KB | < 600 KB |
| Restaurant | < 280 KB | < 700 KB |
| Épicerie | < 270 KB | < 650 KB |

### 8.3 Optimisations frontend

- Code splitting par route (TanStack Router lazy)
- Tree shaking Lucide icons (import direct, pas barrel)
- Image optimization : WebP/AVIF, responsive `srcset`
- Service Worker : cache shell + assets statiques
- Bundle analyzer en CI : alerte si bundle > cible
- React 19 : Compiler activé (auto memo)

### 8.4 CI gate frontend

```yaml
# .github/workflows/frontend-perf.yml
- name: Check bundle size
  run: |
    pnpm build
    pnpm size-limit  # fail si > seuils définis dans .size-limit.json

- name: Lighthouse CI
  uses: treosh/lighthouse-ci-action@v10
  with:
    urls: |
      http://localhost:5173/
    budgetPath: ./lighthouse-budget.json
    uploadArtifacts: true
```

```json
// lighthouse-budget.json
[
  {
    "path": "/*",
    "timings": [
      { "metric": "first-contentful-paint", "budget": 1500 },
      { "metric": "largest-contentful-paint", "budget": 2000 },
      { "metric": "interactive", "budget": 3000 },
      { "metric": "cumulative-layout-shift", "budget": 0.05 }
    ],
    "resourceSizes": [
      { "resourceType": "script", "budget": 280 },
      { "resourceType": "total", "budget": 700 }
    ]
  }
]
```

---

## 9. Charge concurrente — capacités cibles

### 9.1 Capacités plateforme cible (post-Bloc 7)

| Métrique | Cible 2026-Q4 | Cible 2027-Q2 |
|----------|---------------|---------------|
| Tenants actifs simultanés | 50 | 200 |
| Utilisateurs concurrents | 500 | 2000 |
| Requêtes/sec soutenues (peak) | 800 | 3000 |
| Connexions DB max | 100 | 200 (PgBouncer) |
| Connexions Redis max | 50 | 100 |
| Workers Celery total | 32 | 96 |
| Throughput audit logs | 2000/s | 8000/s |

### 9.2 Tests de charge

```python
# tests/load/test_load_concurrent.py
"""Tests de charge — exécutés en pre-prod uniquement."""
import asyncio
import httpx

async def test_load__500_concurrent_users__no_degradation():
    """500 users en parallèle pendant 5 min — P95 < 200ms maintenu."""
    async with httpx.AsyncClient(base_url="https://staging.devup.fr") as client:
        async def user_session(user_id: int):
            # Login
            r = await client.post("/auth/login", json={...})
            token = r.json()["access_token"]
            client.headers["Authorization"] = f"Bearer {token}"

            # Boucle 5 min : list customers, get devis, search
            end = time.time() + 300
            while time.time() < end:
                await client.get("/api/v1/customers?limit=20")
                await client.get("/api/v1/devis?limit=20")
                await asyncio.sleep(2)

        tasks = [user_session(i) for i in range(500)]
        await asyncio.gather(*tasks)

    # Vérifier metrics Prometheus a posteriori
    metrics = await fetch_metrics()
    assert metrics["http_request_duration_seconds_p95"] < 0.2
    assert metrics["http_requests_total{status=~'5..'}"] / metrics["http_requests_total"] < 0.001
```

### 9.3 Outils

- **Locust** : tests de charge interactifs en pre-prod
- **k6** : tests de charge scriptés en CI hebdomadaire
- **Artillery** : smoke load post-deploy (50 users, 60s)

---

## 10. Outillage et exécution

### 10.1 pytest-benchmark

```python
# tests/performance/conftest.py
import pytest

@pytest.fixture(autouse=True)
def benchmark_config(benchmark):
    benchmark.pedantic = True
    benchmark.min_rounds = 100
    benchmark.warmup_rounds = 10
    benchmark.disable_gc = True
```

### 10.2 Locust

```python
# tests/load/locustfile.py
from locust import HttpUser, task, between

class DevupUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.client.post("/api/v1/auth/login", json={
            "email": "load@test.fr",
            "password": "..."
        })
        # extract JWT, set header

    @task(5)
    def list_customers(self):
        self.client.get("/api/v1/customers?limit=20")

    @task(3)
    def get_devis_list(self):
        self.client.get("/api/v1/devis?limit=20")

    @task(1)
    def search_customer(self):
        self.client.get("/api/v1/customers?search=Dup")
```

### 10.3 Run commandes

```bash
# Benchmark régression CI
pytest tests/performance --benchmark-compare=.benchmarks/baseline.json --benchmark-compare-fail=mean:20%

# Update baseline (manuel, après sprint)
pytest tests/performance --benchmark-save=baseline

# Locust pre-prod
locust -f tests/load/locustfile.py --host=https://staging.devup.fr --users 500 --spawn-rate 10 --run-time 5m

# k6 hebdomadaire
k6 run --vus 100 --duration 5m tests/load/k6-script.js

# Frontend Lighthouse
pnpm exec lhci autorun
```

---

## 11. Détection et traitement des régressions

### 11.1 Seuils de détection

| Régression | Seuil | Action |
|------------|-------|--------|
| Latence P95 +20% | Strict CI | Block merge |
| Latence P95 +10% | Warning CI | Slack notify, merge ok |
| Throughput -20% | Strict CI | Block merge |
| Bundle frontend +10% | Warning CI | Slack notify |
| Bundle frontend +20% | Strict CI | Block merge |
| Coverage -2% absolu | Strict CI | Block merge |

### 11.2 Workflow régression détectée

```
1. CI rouge sur perf bench
2. Auteur PR analyse — exécute localement avec profiling
3. Si fix possible → push fix
4. Si fix non possible immédiat :
   a. Discuter avec Lead
   b. Soit accepter régression (mise à jour baseline + ticket dette)
   c. Soit revert et redécouper le travail
5. Aucun bypass --no-verify autorisé
```

### 11.3 Profiling outils

- **py-spy** : sampling profiler, low overhead, prod-safe
- **scalene** : CPU + memory profiler, Python-aware
- **EXPLAIN (ANALYZE, BUFFERS)** : diagnostique SQL
- **Chrome DevTools Performance** : frontend profiling
- **Lighthouse** : audit frontend automatisé

---

## 12. Plan d'optimisation par bloc

### Sprint 1 (PROD FIRE-DRILL)
- Pas d'optimisation perf — focus stabilité
- Baseline figée 2026-04-25

### Bloc 1 (Audit, Outbox, FSM)
- Index `idx_outbox_status_created` partial
- Audit log partitioning préparation (mois)
- HMAC chain index `(prev_hmac)`

### Bloc 2 (Auth)
- JWT EdDSA migration
- Scope cache Redis 5min
- Argon2 params tunés selon hardware réel

### Bloc 3 (Devis, Réservation)
- PricingEngine memoization
- Eager loading explicite réservations
- Index `(tenant_id, statut, date_evenement)`

### Bloc 4 (Customer, Loyalty)
- pg_trgm GIN index sur customer
- RFM cache Redis hash
- Loyalty balance projection materialized view

### Bloc 5 (Stock, ETL, Marmite)
- Materialized view `product_stock_view`
- ETL parser → async chunked
- Brand match : pgvector / FAISS
- Advisory lock per stock_item (pas global)

### Bloc 6 (Audit, RGPD, Observabilité)
- /metrics pre-aggregation cache
- Audit log partitioning effectif
- mTLS keepalive
- RGPD export streaming (pas memory load)

### Bloc 7 (DEVUP)
- Provisioning : pré-création seed data en cache
- Per-tenant feature flags : cache local 60s
- Vertical resolution : précalcul au login

---

## Annexes

### A. Critères de Done — perf

Pour qu'un sprint soit considéré perf-ready :

- [ ] Aucune régression > 20% détectée vs baseline
- [ ] Nouvelles features ont leur entrée dans `.benchmarks/baseline.json`
- [ ] Queries SQL nouvelles ont leur plan EXPLAIN snapshot commit
- [ ] Coverage des tests de perf ≥ 80% sur modules critiques touchés
- [ ] Lighthouse CI vert sur frontend si UI touché
- [ ] Documentation `55-performance-benchmarks.md` mise à jour

### B. Hardware de bench reproductible

```
Container Docker avec :
- 4 vCPU (cgroup limit)
- 8 GB RAM (cgroup limit)
- SSD NVMe 100 GB
- Réseau LAN 1 Gbps
- PostgreSQL 16 + Redis 7 + RabbitMQ 3.13 dans containers séparés
- Latence inter-container < 0.5ms
```

### C. Réviseurs perf

- **Lead Architect** : reviewer obligatoire toute PR touchant `app/services/pricing_engine.py`, `app/services/devis_to_reservation.py`, `app/core/audit.py`
- **Ops** : reviewer obligatoire toute PR touchant `app/middleware/`, configuration DB/Redis/RabbitMQ
- **Frontend Lead** : reviewer obligatoire toute PR augmentant bundle > 5%

---

**Fin du document — 55-performance-benchmarks.md**

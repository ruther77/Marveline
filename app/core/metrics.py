"""Prometheus metrics pour observabilité CaroCorp.

Expose métriques RED (Rate, Errors, Duration) pour monitoring production.

Metrics exposées :
- http_requests_total : Counter requêtes HTTP par method/path/status
- http_request_duration_seconds : Histogram latence requêtes (buckets p50/p90/p99)
- http_requests_in_progress : Gauge requêtes en cours
- rate_limit_hits_total : Counter rate limit atteint par scope

Endpoint Prometheus :
- GET /metrics : Exposition métriques format Prometheus

Example Prometheus config (prometheus.yml) :
    scrape_configs:
      - job_name: 'carocorp'
        scrape_interval: 15s
        static_configs:
          - targets: ['localhost:8001']

Example Grafana dashboard :
    - Panel 1 : rate(http_requests_total[5m]) → Req/s
    - Panel 2 : histogram_quantile(0.99, http_request_duration_seconds) → p99 latency
    - Panel 3 : http_requests_total{status=~"5.."} → Erreurs 5xx
    - Panel 4 : rate_limit_hits_total → Rate limit hits/s

Alerting rules (Prometheus alertmanager) :
    - HTTPErrorRate5xx > 1% pendant 5min → PagerDuty
    - HTTPLatencyP99 > 1s pendant 2min → Slack
    - RateLimitHitsSpike > 100/min → Slack
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

# ===== Metrics HTTP (Pattern RED) =====

# RATE : Throughput (requêtes par seconde)
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'path', 'status']
)
"""Counter HTTP requests total.

Labels :
- method : HTTP method (GET, POST, PUT, DELETE, PATCH)
- path : Endpoint path (ex: /api/v1/products)
- status : HTTP status code (200, 401, 404, 429, 500, etc.)

Queries PromQL :
- Req/s : rate(http_requests_total[5m])
- Req/s par endpoint : rate(http_requests_total[5m]) by (path)
- Req/s par status : rate(http_requests_total[5m]) by (status)
"""

# ERRORS : Error rate (taux d'erreur)
# Calculé depuis http_requests_total{status=~"5.."} / http_requests_total
# Pas besoin de metric dédiée, on filtre sur status

# DURATION : Latence requêtes (histogramme p50/p90/p99)
http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'path'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)
"""Histogram HTTP request duration.

Labels :
- method : HTTP method
- path : Endpoint path

Buckets (secondes) :
- 0.005s (5ms) : Très rapide (cache hit, health check)
- 0.01s (10ms) : Rapide (requête simple DB)
- 0.025s (25ms) : Normal (requête DB avec joins)
- 0.05s (50ms) : Acceptable (requête complexe)
- 0.1s (100ms) : Lent (requête lourde)
- 0.25s (250ms) : Très lent (requête très lourde)
- 0.5s, 1s, 2.5s, 5s, 10s : Timeout progressif

Queries PromQL :
- p50 latency : histogram_quantile(0.50, http_request_duration_seconds)
- p90 latency : histogram_quantile(0.90, http_request_duration_seconds)
- p99 latency : histogram_quantile(0.99, http_request_duration_seconds)
- Moyenne : rate(http_request_duration_seconds_sum[5m]) / rate(http_request_duration_seconds_count[5m])
"""

# Gauge requêtes en cours (concurrency)
http_requests_in_progress = Gauge(
    'http_requests_in_progress',
    'HTTP requests currently in progress',
    ['method', 'path']
)
"""Gauge HTTP requests in progress.

Labels :
- method : HTTP method
- path : Endpoint path

Queries PromQL :
- Requêtes en cours : http_requests_in_progress
- Requêtes en cours par endpoint : http_requests_in_progress by (path)
- Max concurrency : max_over_time(http_requests_in_progress[5m])

Alerting :
- http_requests_in_progress > 100 pendant 1min → Saturation workers
"""

# ===== Metrics Rate Limiting =====

rate_limit_hits_total = Counter(
    'rate_limit_hits_total',
    'Total rate limit hits (429 responses)',
    ['scope', 'identifier_type']
)
"""Counter rate limit hits (429 Too Many Requests).

Labels :
- scope : Rate limit scope (global_ip, login, user_authenticated, mutations, reads)
- identifier_type : Type identifier (ip, user_id)

Queries PromQL :
- Rate limit hits/s : rate(rate_limit_hits_total[5m])
- Hits par scope : rate(rate_limit_hits_total[5m]) by (scope)
- Login brute force : rate(rate_limit_hits_total{scope="login"}[5m])

Alerting :
- rate_limit_hits_total{scope="login"} > 10/min pendant 5min → Attaque brute force
- rate_limit_hits_total{scope="global_ip"} > 100/min → Attaque DDoS
"""

# ===== Metrics Database =====

db_queries_total = Counter(
    'db_queries_total',
    'Total database queries',
    ['operation']
)
"""Counter database queries total.

Labels :
- operation : Type opération (select, insert, update, delete)

Queries PromQL :
- DB queries/s : rate(db_queries_total[5m])
- Queries par opération : rate(db_queries_total[5m]) by (operation)
"""

db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query duration in seconds',
    ['operation'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)
"""Histogram database query duration.

Labels :
- operation : Type opération (select, insert, update, delete)

Buckets (secondes) :
- 0.001s (1ms) : Query très rapide (SELECT simple)
- 0.005s (5ms) : Query rapide (SELECT avec index)
- 0.01s (10ms) : Query normale
- 0.025s (25ms) : Query avec JOIN
- 0.05s (50ms) : Query complexe
- 0.1s+ : Query lente (alerte performance)

Queries PromQL :
- p99 DB latency : histogram_quantile(0.99, db_query_duration_seconds)
- Slow queries : db_query_duration_seconds_bucket{le="0.1"} / db_query_duration_seconds_count

Alerting :
- p99 DB latency > 100ms pendant 5min → Problème DB performance
"""

# ===== Metrics Redis =====

redis_commands_total = Counter(
    'redis_commands_total',
    'Total Redis commands',
    ['command']
)
"""Counter Redis commands total.

Labels :
- command : Commande Redis (get, set, incr, del, ping, etc.)

Queries PromQL :
- Redis commands/s : rate(redis_commands_total[5m])
- Commands par type : rate(redis_commands_total[5m]) by (command)
"""

redis_command_duration_seconds = Histogram(
    'redis_command_duration_seconds',
    'Redis command duration in seconds',
    ['command'],
    buckets=(0.0001, 0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1)
)
"""Histogram Redis command duration.

Buckets (secondes) :
- 0.0001s (0.1ms) : Très rapide (GET/SET simple)
- 0.001s (1ms) : Rapide (commande simple)
- 0.005s (5ms) : Normal
- 0.01s+ : Lent (alerte performance)

Queries PromQL :
- p99 Redis latency : histogram_quantile(0.99, redis_command_duration_seconds)

Alerting :
- p99 Redis latency > 10ms pendant 2min → Problème Redis network/performance
"""

# ===== Metrics Cache =====

cache_hits_total = Counter(
    'cache_hits_total',
    'Total cache hits',
    ['entity']
)
"""Counter cache hits total.

Labels :
- entity : Type entité (product, customer, reservation, invoice)

Queries PromQL :
- Cache hits/s : rate(cache_hits_total[5m])
- Hits par entity : rate(cache_hits_total[5m]) by (entity)
"""

cache_misses_total = Counter(
    'cache_misses_total',
    'Total cache misses',
    ['entity']
)
"""Counter cache misses total.

Labels :
- entity : Type entité (product, customer, reservation, invoice)

Queries PromQL :
- Cache misses/s : rate(cache_misses_total[5m])
- Cache hit rate : rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))

Alerting :
- Cache hit rate < 50% pendant 10min → Problème cache (TTL trop court, invalidation excessive)
"""

cache_hit_rate = Gauge(
    'cache_hit_rate',
    'Current cache hit rate (hits / total requests)',
    ['entity']
)
"""Gauge cache hit rate.

Labels :
- entity : Type entité (product, customer, reservation, invoice)

Valeur :
- 0.0 à 1.0 (0% à 100%)
- Calculé comme : hits / (hits + misses)
- Mis à jour après chaque opération get_by_id()

Queries PromQL :
- Cache hit rate actuel : cache_hit_rate
- Hit rate par entity : cache_hit_rate{entity="product"}

Alerting :
- cache_hit_rate < 0.5 pendant 10min → Cache inefficace (vérifier TTL, invalidation)
- cache_hit_rate < 0.3 → Cache surchargé ou TTL trop court
"""

# ===== Metrics Business =====

reservations_total = Counter(
    'reservations_total',
    'Total reservations',
    ['status']
)
"""Counter réservations total.

Labels :
- status : Statut réservation (draft, confirmed, cancelled, completed)

Queries PromQL :
- Réservations/jour : rate(reservations_total[24h])
- Taux confirmation : rate(reservations_total{status="confirmed"}[24h]) / rate(reservations_total[24h])
- Taux annulation : rate(reservations_total{status="cancelled"}[24h]) / rate(reservations_total[24h])
"""

invoices_total = Counter(
    'invoices_total',
    'Total invoices',
    ['status']
)
"""Counter factures total.

Labels :
- status : Statut facture (draft, sent, paid, overdue, cancelled)

Queries PromQL :
- Factures/jour : rate(invoices_total[24h])
- Taux paiement : rate(invoices_total{status="paid"}[24h]) / rate(invoices_total[24h])
- Factures impayées : invoices_total{status="overdue"}
"""

# ===== Endpoint Metrics =====

def metrics_endpoint() -> Response:
    """Endpoint GET /metrics pour Prometheus scraping.

    Returns:
        Response Prometheus format (text/plain)

    Example curl :
        $ curl http://localhost:8001/metrics
        # HELP http_requests_total Total HTTP requests
        # TYPE http_requests_total counter
        http_requests_total{method="GET",path="/api/v1/products",status="200"} 42.0
        http_requests_total{method="POST",path="/api/v1/auth/login",status="401"} 5.0
        ...

    Example Prometheus scrape_config :
        scrape_configs:
          - job_name: 'carocorp'
            scrape_interval: 15s
            static_configs:
              - targets: ['localhost:8001']

    Notes:
        - Appelé toutes les 15s par Prometheus (scrape_interval)
        - Format texte Prometheus (pas JSON)
        - Compression gzip automatique si client supporte
        - Pas d'authentification requise (metrics endpoint public)
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

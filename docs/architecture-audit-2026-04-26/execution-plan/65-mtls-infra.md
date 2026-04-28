# mTLS Infra — Service mesh + cert-manager + SPIFFE IDs

> **Source de vérité** : Sprint B6.S6 (`16-sprint-B6.S6.md`)
> **Décision** : Q40=B verrouillée — mTLS pur sur `/metrics`
> **Phase** : avenir K8s production-grade

---

## 1. Choix : nginx-ingress vs Istio vs Linkerd

| Critère | nginx-ingress | Istio | Linkerd |
|---|---|---|---|
| Complexité ops | Faible | Élevée | Moyenne |
| Performance | Excellent | Bon | Excellent |
| mTLS | Manual config | Auto via PeerAuthentication | Auto via Server policies |
| Observability | Basic | Avancée (Kiali) | Bonne |
| Coût licence | Gratuit | Gratuit | Gratuit (Linkerd2) |
| Maturité | Très haute | Haute | Haute |
| Cas d'usage DEVUP | Migration douce | Production complète | Compromis |

**Recommandation Phase 1** : **nginx-ingress avec mTLS** (simple, suffit pour `/metrics`)
**Phase 2 (post-Q40 K8s production)** : **Linkerd** ou **Istio** selon adoption ops

---

## 2. Phase 1 — nginx-ingress mTLS (Bloc 6.S6)

### Architecture

```
┌──────────────────┐
│  Prometheus      │  cert: spiffe://devup/prometheus-scraper
│  (with client)   │
└──────────────────┘
        │ HTTPS + mTLS
        ▼
┌──────────────────┐
│  nginx-ingress   │  verify cert + check SPIFFE ID
│                  │  CA: /etc/nginx/client_ca.pem
└──────────────────┘
        │ HTTP (interne K8s safe)
        ▼
┌──────────────────┐
│   API /metrics   │
└──────────────────┘
```

### Configuration nginx

```nginx
# infra/nginx/metrics.conf
server {
    listen 443 ssl;
    server_name metrics.devup.fr;
    
    # Server cert (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/metrics.devup.fr/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/metrics.devup.fr/privkey.pem;
    
    # mTLS : require client cert
    ssl_client_certificate /etc/nginx/client_ca.pem;
    ssl_verify_client on;
    ssl_verify_depth 2;
    
    location /metrics {
        # Verify SPIFFE ID dans subject DN
        if ($ssl_client_s_dn !~ "URI:spiffe://devup/prometheus-scraper") {
            return 401 "SPIFFE ID required";
        }
        proxy_pass http://api:8000/metrics;
        proxy_set_header X-Client-Cert-DN $ssl_client_s_dn;
    }
}
```

### Application defense-in-depth

```python
# app/api/v1/endpoints/metrics.py
@router.get("/metrics")
async def prometheus_metrics(request: Request):
    client_cert_dn = request.headers.get("X-Client-Cert-DN", "")
    if "spiffe://devup/prometheus-scraper" not in client_cert_dn:
        raise HTTPException(401, "mTLS client cert with SPIFFE ID required")
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

### Cert-manager pour rotation

```yaml
# infra/cert-manager/prometheus-cert.yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: prometheus-scraper
  namespace: monitoring
spec:
  secretName: prometheus-scraper-tls
  duration: 720h        # 30 jours
  renewBefore: 168h     # 7 jours
  subject:
    organizations: [DEVUP]
    organizationalUnits: [Monitoring]
  commonName: prometheus-scraper
  uris:
    - spiffe://devup/prometheus-scraper
  issuerRef:
    name: ca-issuer
    kind: ClusterIssuer
```

### CA private interne

```bash
# Génération CA root (one-shot)
openssl genrsa -out devup_ca.key 4096
openssl req -x509 -new -nodes -key devup_ca.key -sha256 -days 3650 -out devup_ca.pem -subj "/CN=DEVUP Internal CA/O=DEVUP"

# Charger dans cert-manager via Secret
kubectl create secret tls ca-key-pair --cert=devup_ca.pem --key=devup_ca.key -n cert-manager
```

---

## 3. Phase 2 — Service mesh Linkerd (Q40 K8s prod)

### Quand activer

- Migration K8s production complète
- 3+ services internes communiquant
- Besoin observabilité distributed > Tempo (Linkerd Tap, Linkerd Viz)

### Installation

```bash
# Install Linkerd CLI
linkerd install --crds | kubectl apply -f -
linkerd install | kubectl apply -f -

# Enable mTLS automatique pour namespace
kubectl annotate namespace devup linkerd.io/inject=enabled
```

### Server authorization (équivalent PeerAuthentication Istio)

```yaml
apiVersion: policy.linkerd.io/v1beta3
kind: Server
metadata:
  name: api-metrics
  namespace: devup
spec:
  podSelector:
    matchLabels:
      app: devup-api
  port: 8000
  proxyProtocol: HTTP/2

---
apiVersion: policy.linkerd.io/v1beta3
kind: ServerAuthorization
metadata:
  name: prometheus-scraper-auth
  namespace: devup
spec:
  server:
    name: api-metrics
  client:
    meshTLS:
      identities:
        - "prometheus-scraper.monitoring.serviceaccount.identity.linkerd.cluster.local"
```

---

## 4. SPIFFE IDs — convention de nommage

```
spiffe://devup/<namespace>/<workload>

Examples:
- spiffe://devup/monitoring/prometheus-scraper
- spiffe://devup/api/devup-api-v1
- spiffe://devup/celery/celery-worker
- spiffe://devup/wireguard/wg-handler
```

### Génération auto via cert-manager

Chaque service Pod a un cert injecté avec son SPIFFE ID via `cert-manager` + ServiceAccount mapping.

---

## 5. Migration progressive

### Sprint B6.S6 — phase nginx-ingress

- [x] CA private DEVUP
- [x] Client cert Prometheus avec SPIFFE ID
- [x] nginx mTLS config
- [x] Application check SPIFFE ID
- [x] Test : scrape sans cert → 401

### Future — phase Linkerd K8s

- [ ] Migration K8s production
- [ ] Install Linkerd
- [ ] Inject mesh dans namespace devup
- [ ] mTLS automatique entre tous les services
- [ ] Drop nginx mTLS config (Linkerd prend le relai)

---

## 6. Tests mTLS

### Test cert valide

```bash
curl --cert prometheus-cert.pem \
     --key prometheus-key.pem \
     --cacert devup_ca.pem \
     https://metrics.devup.fr/metrics
# 200 OK + content métriques
```

### Test sans cert

```bash
curl https://metrics.devup.fr/metrics
# 401 Unauthorized
```

### Test SPIFFE ID invalide

```bash
# Cert valide mais SPIFFE ID = "spiffe://attacker/..."
curl --cert attacker.pem --key attacker.key https://metrics.devup.fr/metrics
# 401 SPIFFE ID required
```

### Test rotation cert

```bash
# Force renewal via cert-manager
kubectl annotate certificate prometheus-scraper cert-manager.io/issue-temporary-certificate=true
# Verify new cert serial number changed
```

---

## 7. Risques + mitigations

| Risque | Mitigation |
|---|---|
| Cert expiré non renouvelé | cert-manager `renewBefore: 168h` + AlertManager rule expiry < 14j |
| CA private compromise | Procédure rotation : generate new CA, re-issue all certs, drop old CA |
| Mismatch SPIFFE ID | Tests CI vérifient SPIFFE ID format |
| nginx config error | CI lint `nginx -t` avant deploy |

---

## 8. AlertManager rules

```yaml
- alert: CertExpiringIn14Days
  expr: certmanager_certificate_expiration_timestamp_seconds - time() < 1209600
  for: 1h
  
- alert: MTLSConnectionFailure
  expr: increase(nginx_ssl_handshake_failures_total[10m]) > 100
  for: 5m

- alert: SpiffeIdMismatchAttempts
  expr: increase(metrics_endpoint_spiffe_mismatch_total[1h]) > 10
  for: 0m
```

---

**Fin du document — 65-mtls-infra.md**

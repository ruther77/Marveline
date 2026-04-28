# Sprint B6.S5 — Print + VPN audit + circuit breaker + httpx async

> **STATUT** : ⏳ À démarrer après B6.S4
> **DURÉE MAX** : 1 semaine
> **OWNER** : Dev1 + Ops
> **BLOQUE** : B6.S6 (observability mTLS s'appuie sur Print/VPN cleanup)
> **DÉPEND DE** : B6.S2 (audit), B6.S4 (Celery async), B5.S2.T6 (peer_id tenant guard)
> **OBJECTIF** : Refondre Print + VPN cross-cutting : audit log enqueue/result (F1089-F1090), circuit breaker Redis sur imprimantes (F1093), httpx async pool WireGuard (F1091 — drop sync httpx), JWT signé court rotation KMS, tenant guard peer_id confirmé (F1110), ventilation paiement ticket card+espèces, mention légale FR auto. **Q41=B verrouillé** : pas de prep multi-pays.

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B6.S5.T1** | F1091 — `httpx.AsyncClient` pool partagé pour WireGuard handlers (drop sync httpx) | P0 | 1 j | T2 |
| **B6.S5.T2** | F1093 — Circuit breaker Redis sur imprimantes (3 fails → ouvert 60s) | P0 | 1 j | aucun |
| **B6.S5.T3** | F1089/F1090 — Audit log Print enqueue + result (cohérent B6.S2 service-level) | P0 | 0.5 j | aucun |
| **B6.S5.T4** | F1104 — Rate-limit `/print/*` per-tenant per-printer | P1 | 0.5 j | aucun |
| **B6.S5.T5** | F1110 — Audit confirmation tenant guard peer_id (post B5.S2.T6) | P1 | 0.5 j | aucun |
| **B6.S5.T6** | Ventilation paiement ticket (card+espèces+chèque mix) + mention légale FR auto | P1 | 1 j | aucun |
| **B6.S5.T7** | JWT signé court (5 min TTL) + rotation KMS pour print/VPN | P1 | 0.5 j | aucun |
| **B6.S5.T8** | TR-86 (Vague 4) — Rotation `WG_INTERNAL_API_KEY` via KMS + audit. Full mTLS WG hors scope Q40=B → différé post-K8s service mesh. | P1 | 0.5 j | T7 |

**Total effort** : 5.5 jours-homme.

---

# Story B6.S5.T1 — `httpx.AsyncClient` pool WireGuard (F1091)

## Contexte

**Friction** : F1091
**Sévérité** : P0 — `httpx.Client()` sync dans handler async → bloque event loop, latence cumulative
**Code source** : `app/services/wireguard.py`, `app/integrations/wg_handler.py`

### Description

Cible : `httpx.AsyncClient` instancié au boot, pool partagé via DI.

## Solution

```python
# app/core/http_client.py (NEW)
_async_http_client: httpx.AsyncClient | None = None

async def get_http_client() -> httpx.AsyncClient:
    global _async_http_client
    if _async_http_client is None:
        _async_http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            transport=httpx.AsyncHTTPTransport(retries=3),
        )
    return _async_http_client


async def close_http_client():
    global _async_http_client
    if _async_http_client:
        await _async_http_client.aclose()
        _async_http_client = None


# app/main.py
@app.on_event("startup")
async def _startup():
    await get_http_client()  # init pool

@app.on_event("shutdown")
async def _shutdown():
    await close_http_client()
```

```python
# app/services/wireguard.py — refacto
class WireguardService:
    def __init__(self, http: httpx.AsyncClient):
        self.http = http

    async def add_peer(self, ...):
        response = await self.http.post(f"{WG_API}/peers", json={...})
```

### Script CI

```python
# tools/check_no_sync_httpx_in_async.py (déjà ciblé en CI invariants #22)
"""Refuse `httpx.Client()` ou `requests.*` dans `app/` (async only)."""
```

## DoD

- [ ] Pool async partagé instancié au startup
- [ ] WireGuard handlers utilisent injection DI
- [ ] Script CI `check_no_sync_httpx_in_async.py` actif
- [ ] Test : 100 calls parallèles WG handler → ne bloquent pas event loop

---

# Story B6.S5.T2 — Circuit breaker imprimantes (F1093)

## Contexte

**Friction** : F1093
**Sévérité** : P0 — imprimante offline → 30s timeout × N requêtes → DOS interne

### Description

Cible : `RedisCircuitBreaker` per-imprimante :
- 3 fails consécutifs → ouvert 60s
- Pendant ouvert → `503 Service Unavailable` immédiat (pas de timeout)
- Après 60s → half-open (1 essai test)

## Solution

```python
# app/services/circuit_breaker.py (NEW)
from enum import Enum

class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class RedisCircuitBreaker:
    def __init__(self, redis: Redis, key: str, fail_threshold: int = 3, open_duration: int = 60):
        self.redis = redis
        self.key = f"cb:{key}"
        self.fail_threshold = fail_threshold
        self.open_duration = open_duration

    async def call(self, func: Callable, *args, **kwargs):
        state = await self._get_state()
        if state == CircuitState.OPEN:
            raise CircuitOpenError(f"Circuit breaker open for {self.key}")
        try:
            result = await func(*args, **kwargs)
            if state == CircuitState.HALF_OPEN:
                await self._reset()
            return result
        except Exception:
            await self._record_failure()
            raise

    async def _get_state(self) -> CircuitState:
        state_data = await self.redis.hgetall(self.key)
        if not state_data:
            return CircuitState.CLOSED
        if state_data.get(b"state") == b"open":
            opened_at = int(state_data.get(b"opened_at", 0))
            if time.time() - opened_at >= self.open_duration:
                return CircuitState.HALF_OPEN
            return CircuitState.OPEN
        return CircuitState.CLOSED

    async def _record_failure(self):
        fails = await self.redis.hincrby(self.key, "fails", 1)
        if fails >= self.fail_threshold:
            await self.redis.hset(self.key, mapping={"state": "open", "opened_at": int(time.time())})

    async def _reset(self):
        await self.redis.delete(self.key)


# app/services/print/printer.py
class PrinterService:
    def __init__(self, redis):
        self.redis = redis

    async def print_ticket(self, printer_id: UUID, content: bytes):
        cb = RedisCircuitBreaker(self.redis, key=f"printer:{printer_id}")
        try:
            return await cb.call(self._send_to_printer, printer_id, content)
        except CircuitOpenError:
            raise HTTPException(503, f"Printer {printer_id} temporarily unavailable")
```

## DoD

- [ ] `RedisCircuitBreaker` livré
- [ ] PrinterService utilise CB per-printer
- [ ] Test : 3 fails → ouvert 60s ; 503 retourné instantané ; après 60s half-open

---

# Story B6.S5.T3 — Audit Print enqueue + result (F1089/F1090)

## Solution

```python
# app/services/print/printer.py
class PrinterService:
    @audit_action(entity_type="Print", action_template="print.{op}")
    async def enqueue(self, printer_id, content, ...):
        # Audit auto via décorateur
        ...

    async def _on_print_result(self, job_id, success, error_msg):
        await audit_service.log(
            action="print.result",
            entity_type="Print",
            entity_id=str(job_id),
            description=f"Result: {'success' if success else 'fail: ' + error_msg}",
            ...
        )
```

## DoD

- [ ] Audit enqueue + result via décorateur
- [ ] Test : print success → 2 audits (enqueue + success) ; fail → 2 audits (enqueue + fail)

---

# Story B6.S5.T4 — Rate-limit `/print/*` (F1104)

## Solution

```python
# app/api/v1/endpoints/print.py
@router.post("/print/ticket", dependencies=[Depends(require_scope(Scope.PRINTER_PRINT))])
@rate_limit(per_tenant=300, per_minute=True)  # 300 prints/min/tenant
async def print_ticket(...):
    ...
```

## DoD

- [ ] Rate-limit per-tenant 300/min
- [ ] Test : 301 prints/min → 429

---

# Story B6.S5.T5 — Audit tenant guard peer_id (F1110)

## Contexte

B5.S2.T6 a livré le check côté `WireguardService.get_peer`. Cette story confirme + ajoute audit log si tentative cross-tenant.

## Solution

```python
async def get_peer(self, peer_id, tenant_id):
    peer = await self.db.scalar(
        select(WgPeer).where(WgPeer.id == peer_id)  # sans filtre tenant
    )
    if peer is None:
        raise NotFound(...)
    if peer.tenant_id != tenant_id:
        # Audit attempt denied
        await audit_service.log(
            action="ATTEMPT_DENIED",
            entity_type="WgPeer",
            entity_id=str(peer_id),
            description=f"Cross-tenant access attempt: requested {tenant_id}, peer belongs to {peer.tenant_id}",
            tenant_id=tenant_id,
        )
        raise NotFound(...)  # 404, pas 403 (info disclosure)
    return peer
```

## DoD

- [ ] Audit log sur tentative cross-tenant
- [ ] 404 retourné (pas 403)
- [ ] Test : audit créé sur cross-tenant attempt

---

# Story B6.S5.T6 — Ventilation paiement ticket + mention légale FR auto + validation brand

## Contexte

Q41=B verrouillé : strict FR. Format ticket :
- Ventilation paiement : `card 30€ + espèces 10€ + chèque 5€ = 45€`
- Mention légale FR auto selon `Invoice.tva_regime`
- **TR-81 / Vague 2** : validation `Tenant.brand_display_name` NOT NULL avant render (sinon DB error silent → ticket sans header → réclamation client)

### Description

Cible : `TicketRenderer.render(invoice)` génère contenu cohérent FR avec **fail-fast** si données tenant incomplètes.

## Solution

```python
# app/services/print/ticket_renderer.py
class TicketRenderingError(Exception):
    """TR-81 — fail-fast si données tenant incomplètes pour render ticket."""


class TicketRenderer:
    def render(self, invoice: Invoice, payments: list[Payment], tenant: Tenant) -> bytes:
        # TR-81 — validation pre-render fail-fast
        self._validate_tenant_for_print(tenant)
        
        lines = [
            self._header(tenant),
            *[self._line(l) for l in invoice.lines],
            self._totals(invoice),
            *self._ventilation(payments),  # card 30€ + espèces 10€ + ...
            self._mention_legale(invoice),
            self._footer(tenant, invoice),
        ]
        return "\n".join(lines).encode("cp858")  # cp858 hardcoded Q41=B

    def _validate_tenant_for_print(self, tenant: Tenant):
        """TR-81 / Vague 2 — fail-fast si infos commerciales incomplètes.
        
        Sans cette validation : DB error silent à _header → ticket imprimé sans
        nom_commerce → réclamation client + non-conformité légale (mention obligatoire).
        """
        missing = []
        if not tenant.brand_display_name:
            missing.append("brand_display_name")
        if not tenant.legal_name:
            missing.append("legal_name")
        if not tenant.siret:
            missing.append("siret")  # obligatoire pour facture/ticket FR
        if missing:
            raise TicketRenderingError(
                f"Cannot render ticket: tenant {tenant.id} missing required fields: {missing}. "
                "Configure via /admin/tenant-settings before printing."
            )

    def _header(self, tenant: Tenant) -> str:
        """Header avec nom commercial + SIRET (mention légale FR obligatoire)."""
        return (
            f"{tenant.brand_display_name}\n"
            f"{tenant.legal_name}\n"
            f"SIRET: {tenant.siret}\n"
            f"{'-' * 32}\n"
        )

    def _ventilation(self, payments: list[Payment]) -> list[str]:
        if len(payments) == 1:
            p = payments[0]
            return [f"Paiement: {p.method} {self._fmt_cts(p.amount_cents)}"]
        # Mixte
        lines = ["Paiement mixte:"]
        for p in payments:
            lines.append(f"  - {p.method}: {self._fmt_cts(p.amount_cents)}")
        return lines

    def _mention_legale(self, invoice: Invoice) -> str:
        if invoice.tva_regime == "FRANCHISE_TVA":
            return "TVA non applicable, art. 293B du CGI"
        if invoice.tva_regime == "AUTOLIQUIDATION":
            return "Autoliquidation - art. 283-1 du CGI"
        return ""  # Régime normal : pas de mention spécifique
```

### Endpoint propage l'erreur

```python
# app/api/v1/endpoints/print.py
@router.post("/print/ticket", dependencies=[Depends(require_scope(Scope.PRINTER_PRINT))])
async def print_ticket(invoice_id: UUID, ...):
    try:
        ticket_bytes = renderer.render(invoice, payments, tenant)
    except TicketRenderingError as e:
        raise HTTPException(status_code=409, detail={
            "error": "TENANT_BRAND_INCOMPLETE",
            "message": str(e),
            "action": "Compléter brand_display_name + legal_name + SIRET dans /admin/tenant-settings",
        })
    # ... envoi imprimante via WireGuard
```

### Tests

```python
def test_render_fails_if_tenant_brand_missing(tenant_no_brand, invoice, payments):
    """TR-81 — fail-fast si brand_display_name absent."""
    with pytest.raises(TicketRenderingError, match="brand_display_name"):
        renderer.render(invoice, payments, tenant_no_brand)

def test_render_fails_if_siret_missing(tenant_no_siret, invoice, payments):
    """SIRET obligatoire FR pour ticket de caisse."""
    with pytest.raises(TicketRenderingError, match="siret"):
        renderer.render(invoice, payments, tenant_no_siret)

def test_render_includes_legal_header(tenant_complete, invoice, payments):
    output = renderer.render(invoice, payments, tenant_complete).decode("cp858")
    assert tenant_complete.brand_display_name in output
    assert tenant_complete.legal_name in output
    assert tenant_complete.siret in output

async def test_endpoint_returns_409_on_brand_missing(client, tenant_no_brand, invoice):
    response = await client.post("/api/v1/print/ticket", json={"invoice_id": str(invoice.id)})
    assert response.status_code == 409
    assert response.json()["error"] == "TENANT_BRAND_INCOMPLETE"

def test_ventilation_mixed_payments(tenant_complete, invoice, payments_mixed):
    output = renderer.render(invoice, payments_mixed, tenant_complete).decode("cp858")
    assert "Paiement mixte" in output
    assert "card" in output
    assert "espèces" in output
```

## DoD

- [ ] Ventilation paiement multi-modes
- [ ] Mention légale auto selon `tva_regime`
- [ ] cp858 codepage hardcoded (Q41=B)
- [ ] **TR-81 / Vague 2** : validation pre-render `brand_display_name` + `legal_name` + `siret` obligatoires
- [ ] `TicketRenderingError` → 409 propre côté endpoint (pas 500)
- [ ] Test : ticket mix card+espèces → ventilation render
- [ ] Test : tenant sans brand → 409 + message orientation admin
- [ ] Test : header inclut nom commercial + raison sociale + SIRET

---

# Story B6.S5.T7 — JWT signé court + rotation KMS

## Contexte

JWT pour authent print/VPN backend → backend service-to-service.

### Description

Cible : JWT signed avec key KMS, TTL 5 min, rotation hebdo.

## Solution

```python
# app/services/print/jwt_signer.py
class PrintJwtSigner:
    def __init__(self, kms):
        self.kms = kms

    def sign(self, payload: dict) -> str:
        key = self.kms.get_secret("print_jwt_v1")
        payload_with_exp = {**payload, "exp": int(time.time()) + 300}  # 5 min
        return jwt.encode(payload_with_exp, key, algorithm="HS256")
```

## DoD

- [ ] JWT TTL 5 min
- [ ] Rotation KMS hebdo
- [ ] Test : token expiré → 401

---

# Story B6.S5.T8 — Rotation `WG_INTERNAL_API_KEY` via KMS (TR-86 / Vague 4)

## Contexte

**Friction** : TR-86 / F1094 — `WG_INTERNAL_API_KEY` plain header sniffable par sidecar compromis, aucune rotation.
**Sévérité** : P1 — Sans rotation, une fuite unique compromet la liaison API↔WG indéfiniment.
**Décision** : full mTLS WireGuard **hors scope Q40=B** (qui couvre uniquement `/metrics`). Mitigation pragmatique : rotation hebdomadaire KMS + audit, en attendant K8s + service mesh.

> **Why** : déployer un sidecar mTLS sur le service WG nécessite Istio/Linkerd ou nginx-ingress + cert-manager — infrastructure pas encore en place. Rotation KMS résout le risque "compromis permanent" sans bloquer le rollout.
> **How to apply** : suit le pattern T7 (JWT court rotation KMS) avec `KMS.generate_data_key` hebdo + propagation env var WG.

## Solution

```python
# app/workers/tasks/wg_key_rotation.py
@shared_task(name="rotate_wg_internal_api_key")
def rotate_wg_internal_api_key():
    """TR-86 — rotation hebdo WG_INTERNAL_API_KEY via KMS + audit."""
    new_key = kms.generate_data_key(key_id=settings.KMS_WG_KEY_ID, key_spec="AES_256")
    encrypted_key = base64.b64encode(new_key.ciphertext).decode()

    # Propage en cluster secrets (K8s Secret ou Docker swarm secret)
    secret_store.update("wg_internal_api_key", encrypted_key)

    # Audit
    audit_log.append(
        action="WG_API_KEY_ROTATED",
        actor_type="system",
        metadata={"key_id": settings.KMS_WG_KEY_ID, "ciphertext_version": new_key.key_version},
    )

# Beat schedule weekly Monday 03:00
celery_app.conf.beat_schedule["rotate-wg-key-weekly"] = {
    "task": "rotate_wg_internal_api_key",
    "schedule": crontab(hour=3, minute=0, day_of_week=1),
}
```

```python
# app/services/wg/client.py — lecture key cachée 60s
class WireGuardClient:
    _key_cache: TTLCache = TTLCache(maxsize=1, ttl=60)

    async def _get_api_key(self) -> str:
        cached = self._key_cache.get("key")
        if cached:
            return cached
        key = await secret_store.read("wg_internal_api_key")
        self._key_cache["key"] = key
        return key
```

## DoD

- [ ] Beat task `rotate_wg_internal_api_key` planifiée hebdomadaire
- [ ] Audit log `WG_API_KEY_ROTATED` à chaque rotation
- [ ] Test : ancienne key invalidée 60s après rotation (TTL cache + secret_store)
- [ ] Doc différée : ticket "TR-86-FOLLOWUP — full mTLS WG post-K8s" ouvert
- [ ] **TR-86 mitigé** (pas résolu intégralement) : rotation hebdo + audit, full mTLS différé

---

## Critères de succès Sprint B6.S5

- [ ] **F1091 résolu** : httpx async pool partagé
- [ ] **F1093 résolu** : circuit breaker imprimantes
- [ ] **F1089/F1090 résolus** : audit Print enqueue + result
- [ ] **F1104 résolu** : rate-limit print
- [ ] **F1110 confirmé** : audit cross-tenant peer
- [ ] Ticket ventilation + mention légale FR
- [ ] JWT court + rotation KMS
- [ ] **TR-86 mitigé (Vague 4)** : rotation hebdo `WG_INTERNAL_API_KEY` via KMS

---

**Fin du document — 16-sprint-B6.S5.md**

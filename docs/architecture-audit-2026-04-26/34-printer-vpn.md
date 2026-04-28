# Module 34 — Printer ESC/POS + VPN WireGuard

> **Phase E — module 4/5.** Audit des intégrations bas-niveau : impression tickets thermiques 80mm via TCP raw 9100 + proxy WireGuard microservice externe.

---

## 1. Inventaire — lecture intégrale

| Fichier | LoC |
|---|---|
| `app/services/printer.py` | 239 |
| `app/api/v1/endpoints/printer.py` | 97 |
| `app/tasks/printing.py` | 105 (déjà mod. 33) |
| `app/services/wireguard_client.py` | 174 |
| `app/api/v1/endpoints/vpn.py` | 223 |
| `app/schemas/vpn.py` | 137 |

**Volume total** : 975 LoC (hors mod. 33 printing tâche déjà couverte F1067, F1059).

---

## 2. Architecture observée

```
PRINTER (ESC/POS thermique 80mm)
  endpoint POST /print/ticket (auth requise, scope NON vérifié — F1090)
    ↓ enqueue
  Celery print_ticket_task (queue probable "default")
    ↓
  print_ticket(data: TicketData, host, port=9100)
    ↓
  build_ticket_bytes(data) → bytes ESC/POS (CP858 codepage)
    en-tête : nom, adresse, SIRET, tél (DOUBLE_HEIGHT bold center)
    lignes article ($_fmt_cts$, two-cols)
    sous-total HT + TVA breakdown + TOTAL TTC bold double
    QR code (ESC/POS Model 2 module 4 ECC L)
    mention légale center + feed 4 lignes + cut partial
    KICK_DRAWER si ouvrir_tiroir
  send_to_printer(bytes, host, port=9100, timeout=5s)
    socket.create_connection raw TCP

VPN WireGuard
  endpoint /vpn/* (RBAC granulaire VpnReaderV3 / VpnWriterV3 / VpnAdminV3)
    ↓
  WireGuardClient(tenant_id, actor_id) httpx sync
    base_url = settings.WG_SERVICE_URL
    headers : X-Internal-API-Key, X-Tenant-ID, X-Actor-ID
    timeout 10s
  resources gérées :
    /peers (list/get/create/update/delete/rotate/enable/disable)
    /peers/{id}/config + /qrcode (PNG)
    /status
    /ip-pools (list/create)
```

---

## 3. Frictions identifiées — module 34

> Compteur cumulé (mod. 01-33) ≈ 1 088. Module 34 ouvre à **F1089**.

### 3.1 P0

#### F1089 — `print_ticket` endpoint utilise `Depends(get_current_user)` **sans scope** (commentaire promet "scope vérifié par app-level" mais c'est faux)

`endpoints/printer.py:50`. Le decorator dit `get_current_user` simple, **pas** `require_scope(Scope.PRINTER_PRINT)`. Le commentaire dit "scope vérifié par app-level" — il n'y a aucun middleware ou dependency qui enforce un scope spécifique pour `/print`. Concrètement : tout utilisateur authentifié peut imprimer, même un viewer.

→ Fuite RBAC : un compte de support sans accès POS peut envoyer des tickets arbitraires sur l'imprimante d'un tenant (DoS papier, impression de tickets fantaisistes).

**Action** : `current_user: UserCompat = Depends(require_scope(Scope.PRINTER_PRINT))`.

---

#### F1090 — `print_ticket` **N'EFFECTUE AUCUN AUDIT** ni log structuré métier

Aucun `audit_service.log_action` ni `AuditLog` créé. Imprimer un ticket = action métier sensible (preuve fiscale potentielle). Aucune trace.

**Action** : audit sur enqueue + audit succès/échec dans la task Celery.

---

#### F1091 — `WireGuardClient` utilise **httpx synchrone dans des handlers FastAPI async**

`endpoints/vpn.py:46-55` : signature `def list_vpn_peers(...)` — pas `async def`. FastAPI exécute dans threadpool, mais l'appel `httpx.Client(timeout=10.0)` bloque un thread du pool 10s en cas de service WG lent. Si WG service est down, threadpool s'épuise → API entière inaccessible.

→ Pattern anti-async dans une stack 100% async ailleurs.

**Action** : `httpx.AsyncClient` + endpoints `async def`.

---

#### F1092 — `_request_raw` (wireguard_client.py:103) ouvre `httpx.Client(...)` à chaque appel — **pas de connection pooling**

Idem `_request` (l. 66). Chaque appel = nouveau handshake TCP+TLS vers le microservice WG. Pour un dashboard qui appelle `/peers + /status + /ip-pools` en parallèle = 3 connexions séquentielles. Latence multipliée.

**Action** : `httpx.AsyncClient` partagé au niveau application (singleton) + pool.

---

#### F1093 — `send_to_printer` `timeout_seconds=5` **bloque le worker Celery 5s par tentative × 3 retries = 15s minimum**

`services/printer.py:215-233`. Celery `task_time_limit = 30 minutes`, le worker prefetch_multiplier=4 (mod. 33). Si l'imprimante est offline, chaque tâche attend 15s avant de fail → 4 tâches en attente = 1 minute par worker. Pour 100 tickets en attente, queue stagne.

→ Couplé à F1067 mod. 33 (pas de retry sur TimeoutError) — drift opérationnel.

**Action** : circuit breaker sur (host, port) — si N échecs consécutifs, fail fast pendant 60s sans tenter le réseau.

---

#### F1094 — `WG_INTERNAL_API_KEY` envoyé en clair dans header `X-Internal-API-Key` — **pas mTLS** ni signature

`wireguard_client.py:42`. Si le WG microservice est sur un réseau partagé (Docker bridge, k8s service mesh sans mTLS), un sidecar compromis peut sniffer la clé et appeler le WG service librement. Pas de rotation de clé documentée.

**Action** : mTLS entre app ↔ WG microservice + rotation key (KMS) ; ou JWT signé courte durée.

---

### 3.2 P1

#### F1095 — `printer.py` **codepage CP858 hardcoded** — drift accents pour autres langues

`services/printer.py:42` `CMD_CODEPAGE_858`. CP858 = euro symbol + accents Europe Ouest. Les caractères chinois, arabes, russes échouent silencieusement (`encode("cp858", errors="replace")` remplace par `?`). Pour client SPLENDID Sénégal en français OK, mais Marveline souhaite expansion internationale (cf. F958 mod. 30).

---

#### F1096 — `_fmt_cts` hardcoded `EUR` symbol et virgule décimale française

`services/printer.py:95-98` + ligne 173 `f"TOTAL  {_fmt_cts(...)} EUR"`. Multi-pays bloqué (Sénégal = XOF, Polynésie = XPF, etc.). Cf. F857 mod. 27.

---

#### F1097 — `printer.py` **n'imprime PAS** les fractions de paiement (mode mix) ni le mode_paiement

Une commande payée mix carte+espèces (cf. mod. 29 commande resto F911) : le ticket affiche juste le total, **pas** la ventilation paiement. Non conforme arrêté du 28 mai 2019 (mode de règlement requis sur ticket).

---

#### F1098 — `qr_url` `encode("ascii", errors="replace")` — **URL avec accents** ou tilde devient `?` dans le QR

`printer.py:183`. Si `qr_url = "https://example.com/reçu/123"`, le QR encode "https://example.com/re?u/123" → 404.

**Action** : urlencode avant encode QR.

---

#### F1099 — `_load_commerce_info` (printing.py mod. 33) ne contient **pas le numéro de TVA intracommunautaire**

Mention obligatoire pour B2B (factures épicerie cross-border). Pas dans tenant_settings ni dans le ticket.

---

#### F1100 — `WireGuardClient.delete_peer` `status_code=204` mais commentaire promet "soft delete"

`endpoints/vpn.py:99-108`. Code dit DELETE (REST hard) mais le doc dit "soft delete (peer désactivé)". Selon l'implémentation côté WG microservice, comportement différent. Source de confusion + tests.

---

#### F1101 — `WireGuardClient` **pas de retry** sur erreur réseau

`wireguard_client.py:74-85` `httpx.ConnectError` → raise direct. Pas de backoff. Une instabilité réseau ponctuelle propage 503 à l'utilisateur.

---

#### F1102 — `rotate_peer_keys` ne retourne **PAS** le nouveau private key au caller

`endpoints/vpn.py:111-121`. Retourne le peer mis à jour (public key visible). Pour reconfigurer le client, le user doit télécharger `/config` séparément. Ergonomie + race : entre rotate et fetch config, le client peut perdre la connectivité.

**Action** : single endpoint `POST /peers/{id}/rotate` qui retourne directement le nouveau config + QR.

---

#### F1103 — `enable_peer` / `disable_peer` retournent `VpnPeerResponse` mais **pas d'audit log** sur changement

Action critique RBAC (un peer disabled ne peut plus se connecter). Mod. 31 audit middleware capture POST /peers/{id}/disable mais sans before/after state.

---

#### F1104 — Pas de **rate limit** sur `/print/ticket` et `/vpn/*` endpoints

Un user authentifié peut spammer 1000 print/sec → DoS papier ; ou 1000 rotate/sec → microservice WG saturé.

---

#### F1105 — `print_ticket_task` `tenant_id` arg — **mais le service ne re-vérifie pas** que `printer_host` appartient bien au tenant

Si admin malveillant configure `printer_host = "192.168.1.5"` dans son `tenant_settings` mais l'IP appartient à l'imprimante d'un autre tenant (LAN partagé), tickets imprimés cross-tenant. Pas de validation IP whitelist par tenant.

---

#### F1106 — `build_ticket_bytes` n'a aucune **dimension max paper roll** check

Si `data.lignes` contient 500 lignes × ~20 caractères, le ticket fait des mètres de papier. Pas de pagination ESC/POS ni warning.

---

#### F1107 — `_separator(char="-", width=PAPER_WIDTH_CHARS)` `PAPER_WIDTH_CHARS = 48` magic — **assume 80mm font A**

Pour imprimante 58mm (32 chars) ou font B (64 chars), drift visuel garanti.

---

#### F1108 — `mention_legale` default `"Merci de votre visite"` — **pas conforme** mention obligatoire France

L'art. 290 CGI exige mentions selon type ticket (TVA non applicable, autoliquidation, etc.). Pas de mention auto-conforme.

---

#### F1109 — VPN endpoints **n'utilisent pas** require_scope() classique mais des aliases `VpnReaderV3` (mod. 11 IAM v2)

`endpoints/vpn.py:11`. Pattern différent du reste du code (`require_scope(Scope.X)`). Deux conventions cohabitent.

---

#### F1110 — `endpoints/vpn.py` **pas de tenant_id check** sur `peer_id` — repose sur le WG service

Si le WG service ne vérifie pas la cohérence `peer.tenant_id == headers.X-Tenant-ID`, un user peut accéder à un peer d'un autre tenant via `GET /peers/{peer_id_d_un_autre_tenant}`. Confiance aveugle.

---

### 3.3 P2

#### F1111 — `CMD_KICK_DRAWER` byte sequence hardcoded pour pin 2 — `pin 5` selon modèle

#### F1112 — Pas de **gestion** type d'imprimante autre qu'Epson-compatible (Star, Bixolon)

#### F1113 — `WG_REQUEST_TIMEOUT = 10.0` magic — devrait être env var

#### F1114 — `socket.create_connection` IPv4-only par défaut — IPv6 imprimante non supportée

#### F1115 — `print_ticket_task` ne logge PAS `ticket_bytes` size pour observabilité

#### F1116 — `VpnConfigResponse` schema expose probablement le private_key (à vérifier schema/vpn.py)

#### F1117 — `endpoints/vpn.py` `current_user` paramètre déclaré mais jamais utilisé dans le corps des handlers (juste dependency injection RBAC)

#### F1118 — `WireGuardClient.create_peer` `data: dict` libre — pas de Pydantic strict typing côté client

---

### 3.4 P3

#### F1119 — Comments `Cre`, `Recu` sans accent

#### F1120 — `PRINTER_PORT = 9100` magic Epson default

#### F1121 — `numero_ticket` String libre — pas formatted (TKT-YYYY-NNNN convention manquante)

---

## 4. Synthèse module 34

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 6 | F1089 (no scope check print), F1090 (no audit log print), F1091 (httpx sync dans async), F1092 (no pooling), F1093 (timeout block worker), F1094 (API key plain header) |
| P1 | 16 | F1095 → F1110 |
| P2 | 8 | F1111 → F1118 |
| P3 | 3 | F1119 → F1121 |
| **Total** | **33** | F1089 → F1121 |

**Compteur cumulé après module 34** : ≈ 1 088 + 33 = **1 121 frictions**.

---

## 5. Décision architecturale

> **P0 immédiat** : (1) `require_scope(PRINTER_PRINT)` (F1089) ; (2) audit log enqueue + résultat impression (F1090) ; (3) migrer `WireGuardClient` httpx async + connection pool (F1091+F1092) ; (4) circuit breaker imprimante (F1093) ; (5) mTLS WG ou JWT signé court (F1094).
>
> **Refactor** : multi-pays currency/codepage (F1095+F1096) ; ventilation paiement ticket (F1097) ; rotate retourne config (F1102) ; rate limit /print + /vpn (F1104) ; tenant guard peer_id (F1110).

---

# Module 35 (suivant) — Health / Metrics / Observabilité

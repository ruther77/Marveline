# Module 12 — MFA TOTP / WebAuthn / Trusted Device + PIN

> **Phase B — Identité & Sécurité.** Audit du sous-système step-up authentication : TOTP (RFC 6238), recovery codes, WebAuthn/FIDO2, trusted device + PIN (login restaurant), step-up tokens.
>
> **Forward-références purgées :**
> - F195 (mod. 07) — `MFAConfig.ISSUER_NAME = "Marveline"` hardcodé
> - F295 (mod. 10) — `settings.FRONTEND_URL` global pour multi-brand
> - F336/F371 (mod. 11) — `auth_roles.mfa_required` jamais consulté
> - F47 (mod. 02) — JWT audience bypass

---

## 1. Inventaire des fichiers lus intégralement

| Fichier | LoC | Rôle |
|---|---|---|
| `app/models/mfa.py` | 93 | `MFADevice` (TOTP + recovery codes + envelope encryption v2) |
| `app/models/webauthn_credential.py` | 77 | `WebAuthnCredential` (FIDO2) |
| `app/models/trusted_device.py` | 63 | `TrustedDevice` (PIN restaurant) |
| `app/services/mfa.py` | 560 | TOTP setup/verify, recovery, step-up, MFA session Redis |
| `app/services/webauthn.py` | 276 | py_webauthn ceremonies + step-up shortcut |
| `app/services/pin_auth.py` | 172 | Argon2id PIN + register/verify trusted device |
| `app/api/v1/endpoints/mfa.py` | 425 | 7 endpoints REST MFA |
| `app/api/v1/endpoints/webauthn.py` | 112 | 6 endpoints REST WebAuthn |
| `app/schemas/mfa.py` | 175 | 9 schémas Pydantic |
| `app/schemas/webauthn.py` | 60 | 6 schémas Pydantic |
| `app/services/auth_v2.py` (85-130) | 45 | Login : MFA gate (`is_mfa_enabled` + adaptive) |
| `app/constants/security.py` (337-360) | 23 | `MFAConfig` (TOTP_DIGITS, STEPUP_TTL, etc.) + `RedisKeys.stepup()` |

**Volume total** : ~2 050 LoC sécurité step-up.

---

## 2. Architecture observée

```
┌──────────────────────────────────────────────────────────────────────┐
│                      LOGIN FLOW (services/auth_v2.py)                  │
│   email+password ──► account ──► membership ──► is_mfa_enabled?       │
│                                                       │                 │
│                            ┌──────────────────────────┴──────┐         │
│                            │                                  │         │
│                          OUI                                NON         │
│                            │                                  │         │
│                            ▼                                  ▼         │
│           create_mfa_session() Redis 5 min          access_token direct │
│           ◄─── mfa_session_token ─                                      │
│                            │                                            │
│                  POST /mfa/verify (TOTP ou recovery)                   │
│                            │                                            │
│                            ▼                                            │
│           verify_totp / verify_recovery_code (anti-replay)              │
│           ◄─── access+refresh tokens ─                                 │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                      STEP-UP FLOW (action sensible)                   │
│   POST /mfa/stepup/verify { totp_code }                              │
│           ──► verify_totp + write Redis-SEC stepup:{uid}:{did} 5 min │
│   ──► endpoint protégé par require_stepup() lit cette clé             │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                 PIN FLOW (login restaurant tablette)                  │
│   1. Premier login email+pw ──► register_device(account, tenant, did) │
│   2. Admin set_pin(account, pin) ──► Argon2id stocké accounts.pin_hash│
│   3. POST /pin/login { pin, device_id, tenant_id }                    │
│            ──► verify_pin_login → Account                              │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│              ENVELOPE ENCRYPTION v2 (TOTP secret en DB)              │
│   mfa_devices.encrypted_secret  : bytes (CT + GCM tag)               │
│   mfa_devices.totp_secret_nonce : 12 bytes (GCM nonce)               │
│   mfa_devices.totp_encrypted_dek: bytes (DEK chiffré par KEK)        │
│   mfa_devices.totp_key_version  : "dev-v1" ou ARN AWS KMS version    │
│   ─────────────────────────────────────────────────────────────────  │
│   Note : 3 colonnes sur 4 sont nullable=True bien que requises       │
└──────────────────────────────────────────────────────────────────────┘
```

**Trois rails MFA indépendants** :
1. **TOTP** (`MFADevice` lié à `tenant_membership_id`) — 1 device par membership
2. **WebAuthn** (`WebAuthnCredential` lié à `account_id`, **pas** au membership)
3. **PIN** (`accounts.pin_hash` + `TrustedDevice`) — global au compte, sur device autorisé

> ⚠ Asymétrie majeure : TOTP est **par membership** (multi-tenant explicite), WebAuthn et PIN sont **par account** (cross-tenant). Cf. F375.

---

## 3. Frictions identifiées — module 12

> Compteur global cumulé (modules 01–11) ≈ 364 frictions.
> Le module 12 ouvre à **F365**.

### 3.1 P0 — Bloquant production

#### F365 — `DELETE /mfa` (disable_mfa) n'exige PAS de preuve d'identité (TOTP ni step-up)

**Constat.** `endpoints/mfa.py:289-314` :
```python
@router.delete("", ...)
async def disable_mfa(
    current_user: UserCompat = Depends(get_current_user_async),
    async_db: AsyncSession = Depends(get_async_db),
):
    await mfa_service.disable_mfa(db=async_db, user_id=current_user.id, tenant_id=...)
```

Aucune vérification TOTP, aucune `Depends(require_stepup)`, aucun mot de passe re-confirmé. Un attacker qui obtient un access token (XSS, exfiltration localStorage, MITM) peut **désactiver MFA** sans aucune preuve de possession du second facteur.

**Comparer avec `regenerate_backup_codes`** (l. 322-391) qui exige un `body.totp_code` pour prouver l'identité.

**Conséquence** : MFA neutralisé en 1 requête depuis n'importe quel JWT volé. Combiné avec F292 (sessions non révoquées sur change_password) et F47 (audience JWT contournable), c'est une chaîne d'évasion complète.

**Action** : ajouter `Depends(require_stepup)` ou exiger `body.totp_code` validé via `verify_totp`. Auditer toutes les actions critiques de la même manière (mot de passe, MFA, recovery codes, WebAuthn, PIN).

---

#### F366 — `DELETE /webauthn/credentials/{id}` n'exige PAS de preuve d'identité

**Constat.** `endpoints/webauthn.py:102-112` :
```python
@router.delete("/credentials/{credential_id}")
async def delete_credential(
    credential_id: int,
    current_user: UserCompat = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
):
    await svc.delete_credential(current_user.id, credential_id)
```

Même pattern que F365. Un attacker peut supprimer toutes les FIDO keys du compte avec un simple JWT. Si l'utilisateur a WebAuthn comme **seul** second facteur (no TOTP), il perd accès et l'attacker prend le contrôle.

**Action** : `Depends(require_stepup)` obligatoire ; ou exiger une nouvelle assertion WebAuthn (challenge-response) avant suppression.

---

#### F367 — PIN auth : aucun lockout réel (3 tentatives = 10 000 combinaisons)

**Constat.** `services/pin_auth.py:31-32` :
```python
PIN_MAX_ATTEMPTS = 3
PIN_LOCKOUT_WINDOW_SECONDS = 300  # 5 minutes
```

Le docstring du module l. 8-11 promet :
```
4. lock_check(device_id)
   → Lockout 3 tentatives / 5 min
```

**Mais `lock_check` n'est pas implémentée**. `verify_pin_login` (l. 109-152) :
- Trouve le device → charge l'account → vérifie le PIN.
- En cas d'échec : retourne `None`. **Aucun INCR Redis, aucun update DB, aucun lockout**.

PIN = 4-6 chiffres = max 10 000 + 100 000 + 1 000 000 = ~1.11 M combinaisons. Sans rate limit, en attaque online (HTTP), à 100 req/s = 11 100 secondes ≈ 3 heures pour un PIN à 6 chiffres ; **15 minutes** pour un PIN à 4 chiffres (10 000 / 11 = 9 minutes).

Combiné avec un device_id deviné/copié (F-future), le PIN est trivialement forçable.

**Action** : implémenter `lock_check` (Redis-SEC `pin_lockout:{device_id}` INCR + EXPIRE), bloquer après 3 tentatives consécutives. Idéalement par compte ET par device.

---

#### F368 — WebAuthn `RP_ID` hardcodé global (Splendid bloqué)

**Constat.** `services/webauthn.py:22-23` :
```python
RP_ID = settings.JWT_ISSUER.replace("www.", "")  # "marveline.com"
RP_NAME = settings.APP_NAME
```

Or **WebAuthn impose** que les credentials enregistrés sur `RP_ID=X` ne fonctionnent que sur ce domaine. Splendid frontend = `lesplendid.fr` (hypothèse) → tentative de register → navigateur refuse car `expected_rp_id="marveline.com"` ne match pas l'origine.

**Conséquence** : WebAuthn impossible pour Splendid, Restaurant, Épicerie sauf si tous sont hébergés sur `*.marveline.com`. Le multi-brand est cassé pour FIDO2.

**Cf. F295 (mod. 10)** — même bug racine pour `FRONTEND_URL`.

**Action** : lire `tenant_settings.frontend_url` (déjà colonne existante mod. 09) → en extraire le domaine → `RP_ID = parse(frontend_url).netloc`. Mais WebAuthn impose alors qu'un user enregistré sur Marveline ne pourra pas s'authentifier sur Splendid (par design — c'est une feature de WebAuthn, pas un bug). Acceptable.

---

#### F369 — WebAuthn `expected_origin = settings.FRONTEND_URL` global

**Constat.** `services/webauthn.py:127, 219` :
```python
expected_origin=settings.FRONTEND_URL,
```

Même problème que F368 et F295. Tous les tenants partagent l'origin Marveline → tentative depuis Splendid → 400 "Verification du credential echouee".

**Action** : déduire de `tenant_settings.frontend_url` à l'exécution (passer `tenant_id` au service). Le `WebAuthnService` actuel ignore le tenant_id complètement (cf. F394).

---

#### F370 — WebAuthn `/authenticate/verify` écrit step-up token avec `device_id=""` (inutilisable)

**Constat.** `endpoints/webauthn.py:85-87` :
```python
device_id = getattr(current_user, '_device_id', '') or ''
stepup_key = f"stepup:{current_user.id}:{device_id}"
await redis_sec.client.setex(stepup_key, MFAConfig.STEPUP_TTL, "1")
```

`UserCompat` (deps.py:88-200) n'a **pas** d'attribut `_device_id`. `getattr(..., '', '')` retourne `''`. La clé écrite est `stepup:{uid}:` (avec `:` final).

`require_stepup` (deps.py:758-788) lit le `did` depuis le JWT puis appelle `mfa_service.is_stepup_valid(uid, device_id)` qui regarde `stepup:{uid}:{did_du_jwt}`. La clé attendue n'est **pas** celle écrite par WebAuthn.

**Conséquence** : WebAuthn step-up est **inopérant**. Un user qui valide via FIDO key ne peut jamais accéder à un endpoint protégé par `require_stepup` — il doit re-valider en TOTP.

**Action** : le endpoint doit lire `did` du JWT exactement comme `endpoints/mfa.py:411-416` :
```python
auth_header = request.headers.get("Authorization", "")
if auth_header.startswith("Bearer "):
    tok = decode_token(auth_header[len("Bearer "):])
    device_id = tok.get("did", "")
```

Et utiliser `RedisKeys.stepup(user_id, device_id)` au lieu d'un f-string ad hoc (cf. F384).

---

#### F371 — `auth_roles.mfa_required` est défini en DB mais **jamais lu** au login

**Constat.** `models/auth_role.py:44-48` :
```python
mfa_required: Mapped[bool] = mapped_column(
    Boolean, nullable=False, default=False,
    comment="MFA obligatoire pour ce role"
)
```

Recherche dans le code :
```bash
grep -rn "mfa_required" app/
```
→ uniquement la définition (model + migration). **Aucune lecture**. `services/auth_v2.py:101` lit `is_mfa_enabled()` (existence d'un device), pas la propriété du rôle.

**Conséquence** : un super_admin (rôle `mfa_required=True` en DB) peut se connecter **sans MFA** s'il n'a pas configuré de device. La promesse "MFA obligatoire pour ce rôle" est cosmétique.

**Action** : à l'étape `login`, si `role.mfa_required` mais pas de device → forcer `MFASetupRequired` (réponse spéciale qui force le user à configurer MFA avant accès).

---

#### F372 — Adaptive MFA : skip silencieux si `mfa_enabled=False`

**Constat.** `services/auth_v2.py:113-117` :
```python
# Ne pas forcer adaptive MFA si aucun device MFA n'est configuré
if adaptive_trigger and not mfa_enabled:
    adaptive_trigger = False
    logger.info("Adaptive MFA skipped: no MFA device for account=%d", account.id)
```

Le commentaire l. 113-114 admet le bug : "sinon le login est bloqué". Donc :
- IP/device inconnus → adaptive_trigger=True
- Pas de MFA configuré → adaptive_trigger forcé à False
- Login direct sans aucun second facteur

**Conséquence** : un attacker depuis une IP **étrangère** vers un compte **sans MFA** se connecte sans friction. Adaptive MFA ne protège que les comptes déjà MFA-équipés.

**Action** : sur trigger sans device, retourner `MFASetupRequired` (forcer setup avant accès) ou envoyer un OTP par email comme alternative. Ne **jamais** silently skip.

---

### 3.2 P1 — Forte friction architecturale

#### F373 — TOTP rate limit `totp_lockout:{ip}` partagé entre tous les comptes

**Constat.** `endpoints/mfa.py:131-139` :
```python
client_ip = request.client.host if request.client else "unknown"
totp_lockout_key = f"totp_lockout:{client_ip}"
totp_attempts_raw = await redis_sec.client.get(totp_lockout_key)
if totp_attempts_raw and int(totp_attempts_raw) >= TOTP_MAX_ATTEMPTS:
    raise HTTPException(429, ...)
```

Une seule IP = un seul compteur, **tous comptes confondus**. Conséquences :
- Attacker pivote d'IP → jamais bloqué.
- 100 users derrière le NAT d'une école/entreprise → un seul mauvais code partagé bloque tout le monde.

**Action** : clé composite `totp_lockout:{user_id}:{ip}` ou `totp_lockout:{mfa_session_token}` (l'attacker ne devine pas le token). Garder la clé IP en supplément pour rate limit anti-bot général.

---

#### F374 — Recovery codes : 32 bits d'entropie (`token_hex(4)`)

**Constat.** `services/mfa.py:99-101` :
```python
recovery_codes = [
    secrets.token_hex(MFAConfig.RECOVERY_CODE_LENGTH // 2)  # 8 // 2 = 4 → 8 chars hex
    for _ in range(MFAConfig.RECOVERY_CODE_COUNT)  # 8 codes
]
```

`token_hex(4)` = 4 octets = 32 bits = 8 caractères hexadécimaux = 4.3 milliards de combinaisons. Avec 8 codes actifs simultanément → fenêtre 8× = 2³² / 8 ≈ 5×10⁸. Bcrypt rounds=10 = ~100 ms par tentative. À 10 tentatives/s en parallèle = **560 ans** brute-force online — OK en pratique.

**Mais** : standard de l'industrie = 64 bits (16 hex chars) ou 80 bits (10 caractères Base32). NIST SP 800-63B § 5.1.6 exige ≥ 64 bits.

**Action** : passer à `token_hex(8)` = 16 chars hex = 64 bits, ou format `token_urlsafe(10)` = ~80 bits.

---

#### F375 — PIN cross-tenant (stocké sur `Account` global)

**Constat.** `models/account.py` (mod. 10) : `pin_hash` est sur `Account`. `pin_auth.set_pin(account_id, pin)` écrit globalement. Conséquence :
- User membre Marveline + Restaurant → même PIN sur les deux apps.
- User compromis via PIN sur tablette restaurant → peut s'authentifier sur tablette Marveline avec le même PIN.

Cohérent avec le modèle Account global IAM v2, mais probablement pas le mental model métier (le PIN est un secret par établissement physique, pas par identité).

**Action** : déplacer `pin_hash` sur `TenantMembership` (cf. mod. 09) ou créer un `MembershipPin` séparé.

---

#### F376 — `_DUMMY_HASH` partagé global (timing attack partielle)

**Constat.** `services/pin_auth.py:35` :
```python
_DUMMY_HASH = _ph.hash("000000")
```

Hash unique pour tout le service. Un attacker précalcule un timing baseline pour ce hash → distinguishability avec le path "device existe + account existe + PIN faux" reste plausible (timing constant garanti seulement quand device n'existe **pas** ou pin_hash absent).

**Action** : générer dummy hash par tentative (`_ph.hash(secrets.token_hex(3))`) ou utiliser `argon2.exceptions` proprement.

---

#### F377 — `PIN_LOCKOUT_WINDOW_SECONDS` constant défini mais jamais utilisé

Cf. F367 — la constante existe pour donner l'illusion d'un mécanisme. Code mort jusqu'à implémentation.

---

#### F378 — `MFADevice.encrypted_secret` NOT NULL mais nonce/dek/key_version NULL — état corrompu possible

**Constat.** `models/mfa.py:48-71` :
```python
encrypted_secret: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
totp_secret_nonce: Mapped[Optional[bytes]] = mapped_column(LargeBinary(12), nullable=True)
totp_encrypted_dek: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
totp_key_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
```

Un device avec `encrypted_secret` mais sans `nonce` est **irrécupérable** (decrypt impossible). `decrypt_totp_secret` raise. La nullability v2 est un artifact de migration v1 → v2 mais aucune contrainte CHECK ne garantit la cohérence.

**Action** : ajouter `CHECK (totp_secret_nonce IS NOT NULL AND totp_encrypted_dek IS NOT NULL AND totp_key_version IS NOT NULL)` sur la table actuelle (les rows v1 doivent être migrées avant).

---

#### F379 — `recovery_codes_hash` JSON list sans limite de taille → DoS bcrypt verify

**Constat.** `models/mfa.py:80-84` : `Text` colonne. `services/mfa.py:266-269` :
```python
for i, stored_hash in enumerate(hashes):
    if bcrypt.checkpw(code_bytes, stored_hash.encode("utf-8")):
        ...
```

bcrypt verify O(n). Si un attacker contrôle le contenu (via SQL injection ou bug ailleurs) et insère 10 000 hashes → chaque tentative recovery = 10 000 × 100 ms = 1 000 s de CPU.

**Mais** : `regenerate_recovery_codes` remplace toute la liste, et `setup_totp` remplace aussi. L'attacker doit avoir un autre vecteur (SQLi, role admin DB). Probabilité faible mais surface inutile.

**Action** : `CHECK (json_array_length(recovery_codes_hash::jsonb) <= 16)` ou refactor en table `mfa_recovery_codes (mfa_device_id, code_hash, used_at)` pour éliminer la sérialisation.

---

#### F380 — `StepUpVerifyResponse.valid_for_seconds=900` ment au client (réel = `MFAConfig.STEPUP_TTL=300`)

**Constat.** `schemas/mfa.py:171-175` :
```python
class StepUpVerifyResponse(BaseSchema):
    status: str = Field(default="verified", ...)
    valid_for_seconds: int = Field(
        default=900,
        description="Durée de validité du step-up en secondes (15 min)"
    )
```

`constants/security.py:357` :
```python
STEPUP_TTL = 300  # P2-08 : 5 minutes (etait 15 min — trop long pour ops sensibles)
```

Le commentaire indique une réduction volontaire 15 → 5 min, mais le **schéma de réponse** n'a pas été mis à jour. Le frontend reçoit `valid_for_seconds: 900` et continue à considérer le step-up valide pendant 15 min → 10 minutes pendant lesquelles les actions sensibles échouent en 403.

**Action** : `valid_for_seconds: int = Field(default=MFAConfig.STEPUP_TTL, ...)` (computed default) ou retourner la valeur réelle depuis le service.

---

#### F381 — `TrustedDevice.registered_at` redondant avec `TimestampMixin.created_at`

**Constat.** `models/trusted_device.py:22, 40-42` :
```python
class TrustedDevice(Base, TimestampMixin):  # → created_at + updated_at
    ...
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False,
    )
```

Deux colonnes équivalentes, valeurs divergentes possibles (registered_at peut être réinitialisée par un re-register, created_at non).

**Action** : supprimer `registered_at`, utiliser `updated_at` pour le re-register (ou ajouter un `last_registered_at` séparé). De plus `server_default="now()"` au lieu de `server_default=func.now()` — fragile selon le dialecte.

---

#### F382 — `MFADevice.membership_id nullable=True` + `unique=True` → contradictoire

**Constat.** `models/mfa.py:40-46` :
```python
membership_id: Mapped[Optional[int]] = mapped_column(
    BigInteger,
    ForeignKey("tenant_memberships.id", ondelete="CASCADE"),
    nullable=True,
    unique=True,
    ...
)
```

Pourquoi un MFADevice avec `membership_id=NULL` ? Soit cas d'usage légitime (devices "système") non documenté, soit migration laxiste depuis v1. Plusieurs NULL sont autorisés en PostgreSQL → orphelins multiples possibles.

**Action** : passer à `nullable=False` après migration vérifiée (ou justifier la nullability dans le docstring).

---

#### F383 — `WebAuthnService(db)` instance vs `MFAService` singleton — incohérence pattern

**Constat.**
- `MFAService` (mfa.py:560) : `mfa_service = MFAService()` singleton, db passée en paramètre.
- `WebAuthnService(db)` (webauthn.py:40) : instance avec db en constructeur, créée à chaque endpoint.
- `PinAuthService(db)` (pin_auth.py:59) : idem WebAuthn.

Trois patterns pour trois services. Conventions §1 du projet exigent uniformité.

**Action** : harmoniser sur le pattern `MFAService` (singleton, db en param) ou inverser (instance partout).

---

#### F384 — `endpoints/webauthn.py:86` hardcode `"stepup:{uid}:{did}"` au lieu de `RedisKeys.stepup()`

**Constat.** `endpoints/webauthn.py:84-87` :
```python
from app.constants.security import MFAConfig
device_id = getattr(current_user, '_device_id', '') or ''
stepup_key = f"stepup:{current_user.id}:{device_id}"
```

`RedisKeys.stepup(uid, did)` existe (security.py:177-179). Ne pas l'utiliser = drift garanti si on change le préfixe.

**Action** : `from app.constants import RedisKeys; stepup_key = RedisKeys.stepup(current_user.id, device_id)`.

---

#### F385 — `disable_mfa` / `delete_credential` accessibles à tout user authentifié (pas de scope)

**Constat.** Aucune `require_scope` sur les endpoints destructifs MFA/WebAuthn. N'importe quel rôle (même `viewer`) peut désactiver son propre MFA via JWT valide.

C'est probablement intentionnel (un user gère son propre MFA), mais combiné avec F365/F366 (pas de TOTP confirmation), c'est dangereux.

**Action** : `Depends(require_stepup)` ou re-confirmation password.

---

#### F386 — Aucun audit log sur `disable_mfa` ni sur `delete_credential` WebAuthn

**Constat.** `endpoints/mfa.py:289-314` ne crée pas d'`AuditService.log_action`. Idem pour `endpoints/webauthn.py:102-112`.

`regenerate_backup_codes` (l. 372-388) écrit `RECOVERY_CODES_REGENERATED`. `disable_mfa` plus dangereux et pas tracé.

**Action** : log `MFA_DISABLED` et `WEBAUTHN_CREDENTIAL_DELETED` avec `severity=critical`.

---

#### F387 — TOTP setup pas de rate limit (brute-force possible)

**Constat.** `verify_setup` (mfa.py:133-180) accepte un code 6 chiffres. Aucune protection si un attacker via JWT volé essaie d'activer le MFA pour un secret qu'il connaîtrait. 1 chance sur 1M par essai. Sans rate limit, en quelques heures = setup bypass.

L'attacker n'a pas le secret → il ne peut pas activer un MFA frauduleux qu'il contrôle. Donc impact réel limité (bug "user fait un mauvais code" cosmétique). Mais le pattern manque.

**Action** : appliquer le même `totp_lockout:{user_id}` que `/mfa/verify`.

---

#### F388 — `WebAuthnRegisterOptions` / `WebAuthnAuthenticateOptions` schémas inutilisés

**Constat.** `schemas/webauthn.py:12-26, 37-43` définit ces schémas. Mais `services/webauthn.py:43-84, 149-173` retourne un `dict` brut. Schémas dead.

**Action** : utiliser les schémas pour la response model FastAPI (`response_model=WebAuthnRegisterOptions`).

---

#### F389 — `pin_auth_service` non exposé via singleton ni `app/services/__init__.py`

**Constat.** `services/pin_auth.py` ne crée pas de singleton. Aucun import `from app.services import pin_auth_service`. Chaque endpoint instancie `PinAuthService(db)` localement. Pas grave, mais incohérent.

---

### 3.3 P2 — Friction modérée

#### F390 — `MFAVerifyRequest.recovery_code` `min_length=4` mais codes générés font 8 chars

**Constat.** `schemas/mfa.py:55-59` accepte min_length=4 ; codes générés font 8 chars hex (`token_hex(4)`). Pourquoi 4 ? Aucune justification. Permet des typos qui n'auraient jamais matché.

**Action** : `min_length=8, max_length=8, pattern=r"^[a-f0-9]{8}$"`.

---

#### F391 — `WebAuthn attestation = "none"` désactive vérification authenticator (clones non détectés)

**Constat.** `services/webauthn.py:77` :
```python
"attestation": "none",
```

L'attestation `"direct"` ou `"indirect"` permet de vérifier que l'authenticator est légitime (signé par fabricant). `"none"` = on accepte n'importe quoi, y compris un authenticator logiciel/cloné.

C'est un trade-off ergonomie vs sécurité. Pour Marveline (B2B, peu de FIDO keys volées), acceptable. Pour un système CaroCorp avec staff externe (intérimaires), risqué.

**Action** : option configurable `Settings.WEBAUTHN_ATTESTATION` (default "none", critique apps en "direct").

---

#### F392 — `pin_auth.set_pin` pas de check force PIN faible (1234, 0000, 1111, ...)

**Constat.** `validate_pin_format` (l. 51-53) vérifie uniquement digits 4-6 chars. Aucun blocklist. PIN `0000`, `1234`, `1111` acceptés.

**Action** : blocklist top-100 PINs faibles (DataGenetics).

---

#### F393 — `TrustedDevice.tenant_id` sans FK vers `tenants` (cf. F148 module 05)

Confirmé. `models/trusted_device.py:31`.

---

#### F394 — `WebAuthnCredential` non tenant-scoped (cross-tenant key reuse)

**Constat.** `models/webauthn_credential.py:30-34` : `account_id` seulement. Un user membre de 2 tenants utilise les mêmes FIDO keys partout. Si un tenant compromis exfiltre une `credential_id`, l'attacker peut tenter authentification sur l'autre tenant (mais sign_count anti-clone protège partiellement).

Cohérent avec design Account global, mais asymétrique avec MFADevice (par membership).

---

#### F395 — `MFADevice` pas de relationship vers `TenantMembership`

**Constat.** `models/mfa.py:40-46` a la FK mais aucune `relationship(...)`. Pas de `device.membership.tenant_id` accessible — il faut JOIN explicite (mfa.py:469-477 le fait à la main).

**Action** : ajouter `membership: Mapped["TenantMembership"] = relationship(..., lazy="joined")`.

---

#### F396 — Rate limit Redis sans namespace propre

**Constat.** `endpoints/mfa.py:133` : `f"totp_lockout:{client_ip}"`. Pas dans `RedisKeys`. Pas de séparation Redis-SEC vs Redis-CACHE explicite (utilise Redis-SEC implicitement via `redis_sec.client`).

**Action** : `RedisKeys.totp_rate_limit(ip)` puis utiliser explicitement.

---

#### F397 — `MFASession Redis` stocke email/role en clair (PII)

**Constat.** `services/mfa.py:413-421` :
```python
data = json.dumps({
    "user_id": user_id, "tenant_id": tenant_id,
    "email": email, "role": role, "ip_address": ip_address,
})
await redis_client.client.setex(key, MFAConfig.MFA_SESSION_TTL_SECONDS, data)
```

`email` est PII. Stocké 5 min en Redis-SEC clair. RGPD compatible (durée courte, périmètre auth) mais à minima logger l'événement.

**Action** : ne stocker que `user_id, tenant_id` ; re-fetch email/role à la consommation.

---

#### F398 — `pin_auth` aucun schéma Pydantic (params dict ad-hoc)

**Constat.** `services/pin_auth.py` n'importe ni `BaseSchema`. Pas de schéma `PinLoginRequest`, `PinSetRequest`. Endpoints (à vérifier en module 13+) probablement avec params positionnels.

---

#### F399 — `TrustedDevice.is_active` est `@property` pas mappé colonne (incohérence avec convention)

**Constat.** `trusted_device.py:61-63` :
```python
@property
def is_active(self) -> bool:
    return self.revoked_at is None
```

Convention CaroCorp (cf. `SoftDeleteMixin`) utilise `is_active: Mapped[bool]` colonne. Ici computed property ; pas filtrable côté SQL (impossible `WHERE is_active = True`). Tous les `revoked_at IS NULL` filters dispersés dans le code.

---

### 3.4 P3 — Cosmétique / dette légère

#### F400 — Imports webauthn dans le corps de la fonction (l. 100-103, 188-192)

```python
try:
    from webauthn import verify_registration_response
except ImportError:
    raise HTTPException(500, detail="py_webauthn not installed")
```

Test d'import à chaque appel (rapide grâce au cache, mais pollue). Mettre en top-level avec guard sur module.

---

#### F401 — `_b64url_decode` calcul padding correct mais peu lisible (`if padding != 4`)

```python
padding = 4 - len(s) % 4
if padding != 4:
    s += "=" * padding
```

Cas `len(s) % 4 == 0` → padding=4 → skip. OK. Mais utiliser `base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))` directement.

---

#### F402 — `MFAService.singleton` mais `_resolve_membership_id` méthode d'instance (sans état)

Pourrait être `@staticmethod` (la classe n'a aucun state, justifié docstring l. 56).

---

#### F403 — `pin_auth.PinAuthService.lock_check` fonction promise dans docstring jamais ajoutée

Cf. F367. Code mort déclaré.

---

## 4. Synthèse module 12

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 8 | F365 (disable_mfa sans TOTP), F366 (delete_webauthn sans TOTP), F367 (PIN sans lockout), F368 (RP_ID hardcodé), F369 (origin global), F370 (stepup webauthn key cassé), F371 (`role.mfa_required` mort), F372 (adaptive MFA skip silencieux) |
| P1 | 17 | F373→F389 |
| P2 | 10 | F390→F399 |
| P3 | 4 | F400→F403 |
| **Total module 12** | **39** | F365 → F403 |

**Compteur cumulé après module 12** : ≈ 364 + 39 = **403 frictions** (51 P0, 163 P1, 145 P2, 44 P3).

---

## 5. Forward-références à traiter

- **Module 13 (API Key / OAuth / Password Reset)** : vérifier si OAuth flow contourne le MFA gate (un user OAuth-only sans password peut-il avoir MFA actif et être bypass ?).
- **Module 14+** : pour chaque endpoint admin (delete user, change role, transfer ownership), vérifier la présence de `Depends(require_stepup)` — pattern manquant systématiquement à confirmer.
- **Module 99 (registry)** : F365/F366/F367 forment une **triple chaîne d'évasion MFA** à signaler en synthèse globale.

---

## 6. Décision architecturale recommandée

> **Triplet de fix P0 immédiat** :
> 1. `Depends(require_stepup)` sur tous les endpoints `DELETE /mfa`, `DELETE /webauthn/credentials/{id}`, `PATCH /accounts/me/password` (cf. mod. 10), `PUT /accounts/me/email`, `DELETE /accounts/me` (à venir).
> 2. Implémenter `lock_check` PIN (Redis-SEC INCR + EXPIRE) — F367 est exploitable trivialement.
> 3. Tenant-aware WebAuthn : passer `tenant_id` au `WebAuthnService.__init__` et lire `tenant_settings.frontend_url` pour `RP_ID` + `expected_origin`.
>
> **Refactor structurel à planifier** :
> - Unifier `MFADevice`/`WebAuthnCredential`/`TrustedDevice` sous une abstraction `AuthFactor` (type=TOTP|FIDO|PIN, membership_id) pour rendre cohérent le scoping (par-membership) et le lifecycle (audit, révocation).
> - Tester en CI : "user.role.mfa_required=True ET pas de device → login bloqué".
> - Tests d'invariants envelope encryption (pas de row avec `encrypted_secret IS NOT NULL AND nonce IS NULL`).

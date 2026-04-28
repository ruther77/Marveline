# Module 02 — Core security (crypto / JWT / RBAC / validators)

## 1. Périmètre

| Fichier | LoC | Rôle |
|---|---|---|
| `app/core/security.py` | 447 | JWT RS256 (encode/decode), Argon2id+pepper hashing, verify_password, client_binding_hash, validate_password_strength |
| `app/core/crypto.py` | 116 | AES-256-GCM envelope encryption pour secrets TOTP (DEK + KEK) |
| `app/core/kms.py` | 183 | Chargement clés RSA PEM (access + refresh), JWKS, kid computation |
| `app/core/password_policy.py` | 147 | Politique mots de passe (longueur, complexité, common-passwords, séquences) |
| `app/core/permissions.py` | 412 | RBAC v2 (`Permission` enum + `ROLE_PERMISSIONS`) + RBAC v3 (`Scope` enum + `Scope.all_scopes()`) |
| `app/core/validators.py` | 309 | Validators Pydantic anti SQL-injection / XSS / path-traversal |
| `app/core/upload_validator.py` | 48 | Validation magic-bytes images + sanitization CSV anti-formula |

**Total** : 1 662 LoC.

**Dépend de** : `app/core/config` (settings), `app/core/exceptions` (TokenExpired/Invalid), `app/constants/{security, limits}` (Argon2Params, PasswordPolicy, TokenType, Limits).

**Dépendu par** : `core/deps` (auth flow), `services/{token, mfa, account, password_reset}`, `repositories/{api_key, …}`, schemas Pydantic.

---

## 2. Lecture par fichier

### 2.1 `security.py` (447 LoC)

#### Fonctions exportées
- `compute_client_binding_hash(ip, user_agent) -> str` (ligne 59) : SHA-256[:16] de `f"{subnet/24 ou /48}|{user_agent}"`. Retourne 16 chars hex (64 bits).
- `create_access_token(data, expires_delta=None, audience=None) -> str` (ligne 78) :
  - Cast `sub` et `tenant_id` en string (RFC 7519).
  - Ajoute claims `iss, aud, exp, nbf, iat, type=ACCESS, jti=uuid4`.
  - Signe RS256 avec `_get_private_key()` + `kid` calculé via `_compute_kid(_get_public_key())`.
- `create_refresh_token(data, audience=None) -> str` (ligne 130) :
  - Idem mais `aud = f"{base_aud}:refresh"`, TTL `JWT_REFRESH_TOKEN_EXPIRE_SECONDS` (7j), `type=REFRESH`.
- `decode_token(token, expected_audience=None) -> dict` (ligne 179) — voir flow §2.1.b ci-dessous.
- `decode_access_token(token, expected_audience=None) -> dict` (ligne 266) : appelle `decode_token`, puis revalide l'audience access (redondant — voir F48).
- `_prepare_password(plain) -> bytes` (ligne 312) : `HMAC-SHA256(pepper, SHA256(plain))` → 32 bytes prêts pour Argon2/bcrypt.
- `verify_password(plain, hashed) -> bool` (ligne 329) : auto-détecte algo via préfixe (`$argon2id$` / `$2b$`), 4 chemins d'essai (Argon2+pepper, Argon2 sans pepper, bcrypt+pepper, bcrypt sans pepper).
- `needs_rehash(hashed) -> bool` (ligne 369) : `True` si bcrypt ou Argon2 avec params obsolètes.
- `get_password_hash(password) -> str` (ligne 391) : Argon2id + pepper.
- `validate_password_strength(password, role=None) -> tuple` (ligne 412) : try-import `password_policy.validate_password`, fallback inline en anglais si ImportError.

#### Constantes module-level
- `_argon2_hasher = argon2.PasswordHasher(...)` (ligne 26) : single instance avec `time_cost`, `memory_cost`, `parallelism` depuis settings.
- `DUMMY_HASH = get_password_hash("__dummy_startup_password__")` (ligne 409) — exécution Argon2 (~50-100ms) à l'import du module.

#### Flow `decode_token` détaillé (lignes 179-263)
1. Décode SANS vérifier signature (ligne 205-207) pour lire claim `type`.
2. Si `type == ACCESS` → `pub_keys = [access_public]`, si `REFRESH` → `[refresh_public]`, sinon **les 2 clés essayées** (ligne 220 — fallback legacy).
3. Pour chaque clé : `jwt.decode` avec `verify_aud=False`, `require=[exp, iat, jti, sub, iss]`, leeway `JWT_CLOCK_SKEW_SECONDS`. Si `InvalidSignatureError` → essaie suivante.
4. **Validation post-decode de l'audience** (lignes 246-261) :
   - `actual_type = payload.get("type")`
   - Si `ACCESS` : vérifie `actual_aud == expected_audience` ou `actual_aud in {settings.JWT_AUDIENCE} ∪ settings.JWT_AUDIENCES.values()`.
   - Sinon si `REFRESH` : idem avec `:refresh` suffix.
   - **Sinon (type absent ou unknown) : aucune vérification d'audience, `return payload` direct (ligne 262)**.

### 2.2 `crypto.py` (116 LoC)

- `_derive_key()` (ligne 28) — legacy v1, "ne pas utiliser pour nouveau chiffrement" mais pas underscore-only et pas privée.
- `_get_kek_dev()` (ligne 39) : `HMAC-SHA256(TOTP_DEV_MASTER_KEY, "totp-kek-v1")` → 32 bytes.
- `_encrypt_dek(dek, kek)` (ligne 48) : `nonce_12 + AESGCM(kek).encrypt(nonce, dek)`.
- `_decrypt_dek(encrypted_dek, kek)` (ligne 54) : split 12B nonce + ciphertext, AESGCM decrypt.
- `encrypt_totp_secret(plaintext) -> (ciphertext, nonce, encrypted_dek, key_version)` (ligne 62) :
  - `dek = os.urandom(32)`, `nonce = os.urandom(12)`, ciphertext = AESGCM(dek).encrypt.
  - `kek = _get_kek_dev()`, encrypted_dek = `_encrypt_dek(dek, kek)`.
  - **`key_version = "dev-v1"` hardcodé** (ligne 91).
- `decrypt_totp_secret(ciphertext, nonce, encrypted_dek) -> str` (ligne 94) :
  - Sanity check sur nonce/encrypted_dek.
  - `kek = _get_kek_dev()`, dek = decrypt, plaintext = AESGCM(dek).decrypt.
  - **Le param `key_version` n'est pas utilisé** (pas dans la signature).

#### Branche prod KMS — absente
La docstring ligne 7-17 promet « En production, remplacer par AWS KMS / Azure Key Vault », mais `_get_kek_dev` est appelé inconditionnellement (lignes 88, 114). Aucune branche `if settings.is_production` ou lookup `settings.KMS_KEY_ACCESS`.

### 2.3 `kms.py` (183 LoC)

- `_generate_keypair(private_path, public_path)` (ligne 32) : RSA 2048 (depuis `settings.JWT_RSA_KEY_SIZE`), PKCS8 + `NoEncryption`, écriture sur disque. Skip si fichiers existent.
- `generate_dev_keypairs()` (ligne 61) : appelle `_generate_keypair` pour les 2 paires.
- `_load_private_key(path)` / `_load_public_key(path)` (lignes 76, 90) : lecture PEM avec `password=None` (interdit clés au repos chiffrées).
- 4 getters cached (`@lru_cache(maxsize=1)`) : `get_access_private_key`, `get_access_public_key`, `get_refresh_private_key`, `get_refresh_public_key` (lignes 104-125).
- Aliases retro `get_private_key = get_access_private_key`, `get_public_key = get_access_public_key` (lignes 128-130).
- `_int_to_base64url(n)` (ligne 133) : pour JWK.
- `_compute_kid(public_key) -> str` (ligne 140) : SHA-256 des bytes DER → base64url[:16] (truncated to 22 chars after b64).
- `get_jwk(public_key) -> dict` (ligne 150) : format JWK `{kty: RSA, use: sig, alg: RS256, kid, n, e}`.
- `get_jwks_response() -> dict` (ligne 170) : `{keys: [jwk_access, jwk_refresh]}`.

#### Settings KMS non utilisés
`config.py:79-80` déclare `KMS_KEY_ACCESS` et `KMS_KEY_REFRESH` mais aucun accès dans `kms.py`.

### 2.4 `password_policy.py` (147 LoC)

- `COMMON_PASSWORDS: frozenset[str]` (lignes 27-64) : ~150 entrées hardcodées. **Inclut `"carocorp"` et `"marveline"`** mais pas `"splendid"`, `"lesplendid"`, `"epicerie"`, `"restaurant"`.
- `_REPEATING_PATTERN = re.compile(r"(.)\1{2,}")` (ligne 67) : 3+ caractères identiques consécutifs.
- `_SEQUENTIAL_DIGITS = "0123456789"`, `_SEQUENTIAL_ALPHA = "abcdefghijklmnopqrstuvwxyz"` (lignes 68-69).
- `_has_sequential_chars(password, min_length=4)` (ligne 72) : sliding window de longueur 4 sur les deux séquences. **Pas de détection de séquences inverses (`cba`, `9876`) ni de claviers (`azerty`, `qwerty`)**.
- `validate_password(password, role=None, username=None, email=None) -> tuple[bool, Optional[str]]` (ligne 82) :
  - Longueur max `PasswordPolicy.MAX_LENGTH`.
  - Longueur min `MIN_LENGTH` (8) ou `ADMIN_MIN_LENGTH` (12) si `role in ELEVATED_ROLES`.
  - Complexité : maj, min, chiffre, spécial.
  - `password.lower() in COMMON_PASSWORDS`.
  - Username (≥3 chars) inclus dans password.
  - Local part de l'email (≥3 chars) inclus.
  - `_REPEATING_PATTERN` match.
  - `_has_sequential_chars`.

Messages en **français**.

### 2.5 `permissions.py` (412 LoC)

#### RBAC v2 (lignes 22-221)
- `Permission(str, Enum)` : 47 entrées (ligne 22-114) format `resource:action`.
- `ROLE_HIERARCHY = ["staff", "manager", "admin"]` (ligne 118) — hardcodé, 3 niveaux.
- `ROLE_PERMISSIONS: dict[str, set[Permission]]` (ligne 121-179) : delta par rôle.
  - `staff` : 20 permissions (read partout + write réservations/factures/customers/inventory/ventes/événements).
  - `manager` (delta) : 7 permissions (delete, devis/relances/suppliers/pricing write, vpn:read).
  - `admin` (delta) : 22 permissions (catalogue, users, sessions, audit, api_keys, features, vpn admin, settings).
- `get_effective_permissions(role)` : raise ValueError si rôle inconnu (ligne 188).
- `_EFFECTIVE_CACHE` : précalculé pour les 3 rôles (ligne 205).
- `get_effective_permissions_cached(role)` : retourne `set()` si rôle inconnu (ligne 217-220) — **divergence comportementale avec la version non-cached**.
- `has_permission(role, permission)` : `permission in get_effective_permissions(role)` (ligne 199).

#### RBAC v3 (lignes 229-407)
- `Scope(StrEnum)` : ~62 entrées format `resource:action`.
- Sections (selon les commentaires) :
  - Bloc "infrastructure" (lignes 244-286) : Reservations (3), Stock (3), Deposits (3), Users (4), Sessions (2), Devices (2), Audit (2), Billing (2), Config (2), Reports (2) = 25 scopes.
  - Bloc "metier M5" (lignes 291-368) : Products (3), Categories (3), Bundles (3), Customers (3), Invoices (2), Devis (2), Ventes (2), Evenements (2), Relances (2), Pricing (2), Suppliers (2), VPN (3), Settings (2), API Keys (3), Features (3), Restaurant (2), Epicerie (2), Loyalty (3) = 40 scopes (pas 37 comme la docstring).
- `Scope.all_scopes()` (ligne 371) : **liste manuelle** de 62-65 entrées.
- `has_scope(user_scopes, scope) -> bool` (ligne 410) : trivial `in` check.

#### Doublons / divergences v2 ↔ v3
| Aspect | v2 (Permission) | v3 (Scope) |
|---|---|---|
| Stock | `INVENTORY_READ`, `INVENTORY_WRITE` | `STOCK_READ`, `STOCK_WRITE`, `STOCK_ADJUST` |
| Health | `HEALTH_READ` | absent |
| Restaurant/Épicerie | absents | `RESTAURANT_READ/WRITE`, `EPICERIE_READ/WRITE` |
| Loyalty | absent | `LOYALTY_READ/WRITE/MANAGE` |
| Deposits | absent | `DEPOSITS_READ/WRITE/MANAGE` |
| Reports | absent | `REPORTS_READ/EXPORT` |
| Billing | absent | `BILLING_READ/MANAGE` |
| Config | absent | `CONFIG_READ/WRITE` |
| Devices | `SESSIONS_*` mêlés | `DEVICES_READ/REVOKE` séparés |
| Audit | `AUDIT_READ` | `AUDIT_READ`, `AUDIT_VERIFY` |
| Users | `READ/WRITE/ADMIN` | `READ/WRITE/MANAGE/DELETE` |

### 2.6 `validators.py` (309 LoC)

- `SecurityValidators` classe (lignes 24-247) avec 3 listes de patterns en class-attrs :
  - `SQL_INJECTION_PATTERNS` (19 entrées, lignes 46-67) : `OR 1=1`, `UNION SELECT`, `; DROP TABLE`, `--`, `/* */`, `WAITFOR DELAY`, `SLEEP(`, `information_schema`, etc.
  - `XSS_PATTERNS` (12 entrées, lignes 73-86) : `<script>`, `<iframe>`, `<embed>`, `<object>`, `<svg onX>`, `<img onX>`, `javascript:`, `vbscript:`, `on\w+=`, `data:text/html`, `<meta http-equiv>`.
  - `PATH_TRAVERSAL_PATTERNS` (5 entrées, lignes 92-98) : `../`, `..\`, `%2e%2e[/\\%]`, `..%2f`, `%2e%2e%2f`.
- 4 méthodes statiques : `validate_no_sql_injection`, `validate_no_xss`, `validate_no_path_traversal`, `validate_safe_string`.
- `sanitize_string(value, max_length=1000)` (ligne 218) : truncate, retire `<[^>]*>`, retire chars de contrôle.
- 4 wrappers Pydantic : `validate_email_safe`, `validate_text_safe`, `validate_username_safe`, `validate_path_safe`.

Note ligne 306-309 : "PAS de `validate_password_safe`" — passwords hashés et jamais affichés.

### 2.7 `upload_validator.py` (48 LoC)

- `MAGIC_SIGNATURES = {b'\xff\xd8\xff': '.jpg', b'\x89PNG\r\n\x1a\n': '.png'}` (lignes 9-12).
- `ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}` (ligne 13).
- `MAX_IMAGE_SIZE = 10 * 1024 * 1024` (10 MB), `MAX_CSV_ROWS = 10_000`, `FORMULA_CHARS = {'=', '+', '-', '@', '\t', '\r'}` (lignes 14-16).
- `validate_image(content) -> str` : check size, match magic bytes, fallback WebP via RIFF/WEBP markers, raise `HTTPException`.
- `sanitize_csv_value(value) -> str` : prefixe `'` si premier char est dans `FORMULA_CHARS`.

---

## 3. Frictions identifiées

(Numérotation continue — F47 commence après le module 01.)

### 3.1 Frictions P0

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F47** | security (JWT) | **Audience non vérifiée pour tokens sans claim `type`** | `security.py:179-263` flow complet, en particulier :246-262 | `decode_token` valide l'audience uniquement si `actual_type` matche `ACCESS` ou `REFRESH`. Si le claim `type` est **absent ou unknown**, le code essaie les 2 clés publiques (ligne 220), réussit potentiellement, puis tombe dans `return payload` ligne 262 **sans aucune vérification d'audience**. Un attaquant qui forge un token sans claim `type` (signé avec n'importe laquelle des 2 clés s'il les compromet) peut faire passer un refresh token comme un access token et inversement. Combinaison avec l'inconsistance audience cross-app : un token Marveline pourrait être utilisé sur épicerie/restaurant. **Note** : exploitation nécessite signature valide (donc compromission de clé privée), mais en defense-in-depth la séparation access/refresh par audience est cassée pour ces tokens. À fixer : si `actual_type ∉ {ACCESS, REFRESH}` → `raise TokenInvalid()`. |
| **F48** | crypto | **Mode KMS prod jamais branché — clés TOTP toujours dérivées de `TOTP_DEV_MASTER_KEY`** | `crypto.py:39-45` (`_get_kek_dev`) appelé sans condition lignes 88, 114 ; `config.py:117` valide `TOTP_DEV_MASTER_KEY` ≥32 chars mais le nom de la fonction est `_kek_dev` | La docstring ligne 7-17 promet "En production, remplacer par AWS KMS / Azure Key Vault". Le code n'a pas de branche prod. Si on déploie tel quel, **les secrets TOTP sont chiffrés avec une clé symétrique stockée en variable d'env**, pas KMS. Compromission du `.env` ou du file system = compromission de tous les seeds TOTP de tous les tenants. Spec §1.1 / §05 violée. |
| **F49** | kms | **Settings `KMS_KEY_ACCESS` / `KMS_KEY_REFRESH` déclarés mais non utilisés** | `config.py:79-80` ; aucune occurrence dans `kms.py` | Les clés privées RSA sont en clair sur le filesystem en prod (PEM `NoEncryption()` ligne 49). La rotation, l'audit, la séparation envoi/stockage ne sont pas implémentées. Aucune trace AWS KMS / Vault dans le code. Spec §1.1 violée — le standard de l'industrie est KMS-backed signing pour les access tokens. |

### 3.2 Frictions P1

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F50** | security | `kid` calculé à l'émission mais ignoré au décodage | `security.py:120-127` (set kid header), `:170-176` (idem refresh), `:179-263` (decode lit `type` dans le payload, jamais le `kid` du header) | Le pattern standard JWT pour la rotation de clés est `kid` header → key lookup. Ici on lit le claim `type` (payload) — ce qui force d'avoir une seule paire de clés access valide à un instant t. Conséquences :<br>(a) Rotation de clés impossible sans downtime.<br>(b) Le `kid` est dead-code à l'émission.<br>(c) Le JWKS endpoint `get_jwks_response` expose 2 kids (access + refresh) qu'aucun consommateur n'utilise vraiment.<br>À corriger : `decode_token` doit lire `header['kid']` et résoudre la clé dans un dict `{kid → public_key}`. |
| **F51** | security | `verify_password` a 4 chemins de fallback pour la migration | `security.py:343-366` | Pour chaque hash, on essaie : Argon2 avec pepper → Argon2 sans pepper → bcrypt avec pepper → bcrypt sans pepper. En prod, ça double la surface d'attaque timing : le temps de réponse à un mot de passe partiellement correct varie selon le chemin pris. Fait pour la "migration transparente" mais devrait être supprimé une fois la migration finie + flag `account.password_legacy=True` pour forcer un changement à la prochaine connexion. |
| **F52** | security (TOTP) | `key_version` retourné mais jamais réutilisé au décryptage | `crypto.py:62-91` retourne `(ct, nonce, enc_dek, key_version)` ; `crypto.py:94-116` decrypt ne prend pas `key_version` en paramètre | La rotation KEK n'est pas implémentée. Tous les secrets TOTP créés portent `key_version="dev-v1"` (hardcodé ligne 91). En cas de rotation, il faudrait pouvoir décrypter les anciens secrets avec l'ancien KEK et ré-encrypter avec le nouveau. Le schema DB contient bien la colonne (`totp_key_version`) mais le code l'ignore. |
| **F53** | password | `COMMON_PASSWORDS` contient 2 brand_codes hardcodés (`marveline`, `carocorp`) | `password_policy.py:63` | Chaque nouveau brand (Splendid, etc.) requiert édition du code Python. Devrait charger les `brand_code` actifs depuis la table `tenants` au boot (cache mémoire), avec un seed file `app/data/common_passwords.txt`. |
| **F54** | password | `_has_sequential_chars` couverture limitée | `password_policy.py:67-79` | Détecte uniquement séquences directes A-Z et 0-9. Pas de :<br>- séquences inverses (`cba`, `9876`)<br>- claviers (`azerty`, `qwerty`, `asdf`, `zxcv`)<br>- séquences avec saut (`acegi`, `1357`)<br>- séquences sur le pavé numérique (`147`, `258`, `369`)<br>OWASP recommande au minimum les claviers. |
| **F55** | permissions | **Permission v2 et Scope v3 dérivent — `INVENTORY` (v2) vs `STOCK` (v3)** | `permissions.py:55-56` (`INVENTORY_READ/WRITE`) vs `:249-251` (`STOCK_READ/WRITE/ADJUST`) | Renommage non rétro-compatible. Un endpoint qui vérifie `Permission.INVENTORY_READ` n'est pas équivalent à `Scope.STOCK_READ` (string-values différentes). Migration v2→v3 brise l'autorisation pour tout endpoint stock-related. À résoudre : décider du nom canonique (`stock` ou `inventory`) et migrer. Module 11 tranchera. |
| **F56** | permissions | Permission v2 et Scope v3 ont des string-values qui se chevauchent partiellement | `permissions.py` voir tableau §2.5 | `Permission.PRODUCTS_READ.value == Scope.PRODUCTS_READ.value == "products:read"` mais les enums Python sont distincts. `require_permission(Permission.PRODUCTS_READ)` lit `_EFFECTIVE_CACHE` (rôle-based fixe en mémoire), `require_scope(Scope.PRODUCTS_READ)` lit JWT scopes ou `ROLE_SCOPES_FALLBACK`. **Un user peut avoir `Permission` mais pas `Scope`** ou vice-versa selon le state du token et de la table DB `auth_role_scopes`. Un mix dans un même endpoint = comportement non-déterministe. |
| **F57** | permissions | `ROLE_HIERARCHY` hardcodé à 3 niveaux | `permissions.py:118` (`["staff", "manager", "admin"]`) | Si on ajoute un rôle (`viewer`, `super_admin`, `tenant_admin`, `accountant`), édition du code Python. Devrait être DB-side via `auth_role` table avec ordre/parent. |
| **F58** | validators | SQL-injection patterns trop permissifs / faux-positifs | `validators.py:46-67` | Le pattern `r"--\s*$"` matche tout texte se terminant par `--` (légitime en français : "abréviations Tél. --"). Le pattern `r"\bsleep\s*\("` matche un texte "sleep(8 hours)" (commentaire utilisateur). Le pattern `r"information_schema"` rejette tout texte avec ce mot (faux positif sur doc technique). La docstring (ligne 9-11) admet que la vraie protection est SQLAlchemy parametrized. Cette couche pattern-based est cosmétique et **introduit des faux positifs en prod** sur des inputs légitimes. À supprimer ou réduire à des patterns extrêmement spécifiques (ex: `' OR 1=1 --` exact). |
| **F59** | upload | `MAGIC_SIGNATURES` ne couvre que JPG/PNG | `upload_validator.py:9-12` | WebP via check spécial RIFF (lignes 33-35) — OK. Mais GIF, AVIF, HEIC/HEIF (iPhone par défaut), TIFF absents. Un user iPhone qui upload une photo HEIC = 400 "Format invalide". À étendre avec les magic bytes courants ou documenter explicitement la liste supportée + transcodage côté frontend. |

### 3.3 Frictions P2

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F60** | security | `decode_access_token` revalide l'audience que `decode_token` a déjà validée | `security.py:266-298` vs `:246-261` | Code dupliqué : si `decode_token` a accepté avec `actual_type == ACCESS` et `actual_aud in valid_access_auds`, `decode_access_token` re-fait la même vérif. À simplifier en factorisant. |
| **F61** | security | `verify_signature: False` en pré-décode pour lire le claim `type` | `security.py:204-209` | Antipattern — lit du payload non-signé pour décider de la clé. Le bon pattern est `kid` header. Voir F50. |
| **F62** | security | `compute_client_binding_hash` retourne 16 chars hex (64 bits) | `security.py:75` (`hashlib.sha256(...).hexdigest()[:16]`) | 64 bits suffit pour un hash de matching mais limite pour une primitive de sécurité (anti-vol token). En 2026, 128 bits minimum (32 hex). |
| **F63** | security | `DUMMY_HASH` exécuté à l'import du module | `security.py:409` | Argon2id avec `memory_cost=65536` (64 MiB) prend ~50-100ms par hash. Multiplié par chaque worker uvicorn / process Celery / script CLI / test = retard de boot cumulatif. À calculer paresseusement (lru_cache fonction). |
| **F64** | security | `validate_password_strength` a un fallback inline en anglais | `security.py:412-447` | Le `try: from app.core.password_policy import validate_password ; except ImportError` masque les vrais problèmes de refactoring. Le fallback inline duplique la logique avec messages en anglais (incohérent avec password_policy.py qui est en français) et ne couvre pas common-passwords ni séquences. À supprimer (`password_policy` est toujours importable, l'import circulaire commenté ligne 424 est résolu en module 01). |
| **F65** | crypto | `_derive_key()` legacy v1 encore présente, non underscore-private | `crypto.py:28-34` | "ne pas utiliser pour nouveau chiffrement" mais pas underscore-only et exportable. À supprimer ou renommer `_derive_key_v1_legacy` clairement. |
| **F66** | kms | `_load_private_key` utilise `password=None` | `kms.py:83` | Si la clé PEM est sauvée chiffrée (PKCS8 avec passphrase, recommandation prod), elle ne peut pas être chargée. Devrait lire un `KEY_PASSPHRASE` env optionnel. |
| **F67** | kms | Aliases retro-compat `get_private_key = get_access_private_key` | `kms.py:128-130` | Backward compat à dégager après audit des imports. |
| **F68** | password | Messages en français dans `password_policy.py` mais en anglais dans `security.py` (fallback) | `password_policy.py:101,113,...` (FR) vs `security.py:433,...` (EN) | Le fallback inline de `validate_password_strength` ne devrait pas exister (F64), et tout devrait être homogène FR. |
| **F69** | password | `username/email` non auto-trimés ni normalisés | `password_policy.py:129,134` | `username = "  bob  "` passe le check `len >= 3` mais `username.lower() in password.lower()` matche faussement si password = "bob…". Devrait `.strip()`. |
| **F70** | permissions | `get_effective_permissions(role)` lève vs `get_effective_permissions_cached(role)` retourne `set()` | `permissions.py:188-191` (raise) vs `:217-220` (return set()) | Comportement divergent pour la même question. `require_permission` (deps.py:449) utilise la version cached → un rôle V3 inconnu donne 403 partout (au lieu d'une 500 explicite). À unifier : strict raise, ou strict empty + log warning. |
| **F71** | permissions | `Scope.all_scopes()` listing manuel maintenu à la main | `permissions.py:371-407` | Devrait être `[s.value for s in cls]`. La méthode actuelle est sujette à oublis quand on ajoute un scope (le bloc commenté "37 scopes metier" liste 40 scopes — comptage déjà désaligné). |
| **F72** | permissions | Commentaire docstring "25 scopes infrastructure + 37 scopes metier = 62" faux | `permissions.py:232` ; le bloc metier en a 40 | Doc obsolète. À régénérer depuis `Scope.__members__`. |
| **F73** | validators | XSS patterns incomplets | `validators.py:73-86` | Pas de `<a href="javascript:...">`, `srcdoc`, `formaction`, `<style>` avec `expression()` IE-legacy. La docstring admet "defense en profondeur" mais cette défense est partielle. |
| **F74** | validators | `sanitize_string` retire HTML mais pas les entities encodées | `validators.py:242` | `re.sub(r"<[^>]*>", "", value)` ne décode pas `&lt;script&gt;`. Approche moitié-faite : un input `&lt;script&gt;alert(1)&lt;/script&gt;` passe `sanitize_string` puis devient HTML actif si rendu sans escape. À documenter le contrat ou utiliser `bleach`. |
| **F75** | upload | `MAX_IMAGE_SIZE`, `MAX_CSV_ROWS`, `FORMULA_CHARS` en module-level | `upload_validator.py:14-16` | À déplacer dans `app/constants/limits.py`. |
| **F76** | upload | `validate_image` lève `HTTPException` directement | `upload_validator.py:27,37` | Couplage à FastAPI dans un module utilitaire `core`. Devrait lever une `BadRequest` (`app.core.exceptions`) et laisser le middleware `exception_handler` mapper en HTTP. |

### 3.4 Frictions P3

| ID | Couche | Friction | Citation |
|---|---|---|---|
| **F77** | security | Argon2 hasher init au module-load | `security.py:26-32` — peu coûteux mais idem F63, à lazy-loader. |
| **F78** | password | `COMMON_PASSWORDS` set inline 150 entrées | `password_policy.py:27-64` — à charger depuis fichier `app/data/common_passwords.txt`. |
| **F79** | upload | `sanitize_csv_value` ne gère pas multi-ligne | `upload_validator.py:40-48` — si une cellule contient `=A1+B2\n=C1`, le second `=` n'est pas neutralisé. Excel le détecte. |
| **F80** | validators | Pas de validator dédié téléphone, IBAN, SIRET | (absence) — schémas business doivent s'en occuper. |
| **F81** | kms | `_load_*_key` log INFO à chaque cache miss (lru_cache) | `kms.py:86,101` — log 1× par boot, mais devrait être DEBUG. |
| **F82** | crypto | Docstring `_get_kek_dev` parle de prod KMS jamais implémenté | `crypto.py:42` — voir F48, doc à aligner. |

---

## 4. Dépendances inter-modules / fuites

### 4.1 Couplages observés

- `security.py` ← `kms.py` (lazy import lignes 36-56) → "evite import circulaire" — symptôme du même problème §4.2 module 01.
- `security.py` ← `password_policy.py` (lazy import ligne 426) → idem.
- `crypto.py` → `config.py` (settings.TOTP_DEV_MASTER_KEY, settings.ENCRYPTION_KEY).
- `kms.py` → `config.py` (settings.JWT_*_KEY_PATH, JWT_RSA_KEY_SIZE).
- `permissions.py` aucun import `app.*` autre que → standalone.
- `validators.py` aucun import `app.*` → standalone.
- `upload_validator.py` → `fastapi` (HTTPException direct — F76).

### 4.2 Fuites identité Marveline / Splendid

- `password_policy.COMMON_PASSWORDS` contient `"marveline"`, `"carocorp"` mais pas `"splendid"`, `"lesplendid"` (F53).
- `JWT_ISSUER`, `JWT_AUDIENCE` lus depuis `config.settings` au moment de l'émission (`security.py:111-112, 160-161`) — toute identité multi-brand passe par le hardcode (F06 module 01).
- `MFA_ISSUER_NAME` (config) consommé par `services/mfa.py` (à confirmer module 12).

### 4.3 Forward-references

- F50 (kid au décodage) impacte la conception de la rotation de clés JWT — cf `core/health` (JWKS endpoint, module 03) et migrations futures.
- F55 (INVENTORY vs STOCK) à trancher dans le module 11 (RBAC) — toutes les routes inventaires/stock sont dépendantes.
- F66 (Permission v2 / Scope v3 chevauchement) idem — décision d'unification trace dans le module 11.

---

## 5. Recommandations de refonte

### 5.1 Priorité 1 — Sécurité crypto (P0)

1. **F47** : modifier `decode_token` pour rejeter explicitement `actual_type ∉ {ACCESS, REFRESH}` :
   ```python
   if actual_type not in (TokenType.ACCESS, TokenType.REFRESH):
       raise TokenInvalid("Token type missing or unknown")
   ```
   Supprimer le fallback "essayer les 2 clés" (ligne 220). Si type absent, c'est un token corrompu ou forgé.

2. **F48** : implémenter la branche prod du KEK :
   ```python
   def _get_kek() -> bytes:
       if settings.KMS_KEY_TOTP:  # nouveau setting
           return _kms_decrypt(settings.KMS_KEY_TOTP)
       if settings.DEBUG:
           return _get_kek_dev()
       raise RuntimeError("KMS_KEY_TOTP required in production")
   ```
   Idem pour signature JWT.

3. **F49** : implémenter le chargement des clés RSA via KMS si `KMS_KEY_ACCESS` / `KMS_KEY_REFRESH` non vides, avec fallback PEM local. Ajouter un test prod-mode qui force l'usage KMS.

### 5.2 Priorité 2 — Robustesse JWT (P1)

4. **F50, F61** : refactorer `decode_token` pour utiliser `kid` header :
   ```python
   header = jwt.get_unverified_header(token)
   pub_key = KEY_REGISTRY[header['kid']]  # dict alimenté par kms.py
   payload = jwt.decode(token, pub_key, ...)
   ```
   Permet la rotation de clés (2 clés actives simultanées avec kids différents).

5. **F60** : factoriser la validation audience entre `decode_token` et `decode_access_token`. Un seul point d'entrée typé `decode_token(token, type=ACCESS|REFRESH, expected_audience=None)`.

6. **F51** : ajouter un flag `Account.password_hash_legacy: bool` en DB. Si `verify_password` réussit via fallback "sans pepper" → `password_hash_legacy=True` + `password_change_required=True` à la prochaine login.

7. **F52** : implémenter la rotation KEK :
   - Ajouter `key_version` en paramètre de `decrypt_totp_secret`.
   - Lookup KEK selon version (`KEK_REGISTRY[version]`).
   - Job batch de re-encrypt à la rotation.

### 5.3 Priorité 3 — RBAC unification (P1)

8. **F55, F56, F66** : choisir le système canonique (recommandation : Scope v3) et le terme canonique (recommandation : `STOCK` plus précis que `INVENTORY` pour le métier rental). Migration plan dans le module 11 :
   - Étape 1 : `Permission` enum devient un alias de `Scope` (mêmes string-values).
   - Étape 2 : `require_permission` devient un wrapper de `require_scope`.
   - Étape 3 : suppression du système v2.
   Test de non-régression : `assert {p.value for p in Permission} == {s.value for s in Scope}`.

9. **F57** : tabler `auth_role` avec colonne `parent_role_name` pour hiérarchie DB-side. `ROLE_HIERARCHY` devient une vue computed.

10. **F70** : unifier `get_effective_permissions*` — un seul comportement (recommandation : warn + return empty pour ne pas crasher en production sur un nouveau rôle inconnu).

### 5.4 Priorité 4 — Couches utilitaires (P2)

11. **F58, F73, F74** : revoir `validators.py` :
   - Soit supprimer (faux positifs > vrais positifs, vraie protection = parametrized queries + escaping côté frontend).
   - Soit cibler des patterns spécifiques sans faux positifs (ex: `' OR ''='` exact vs regex permissive).

12. **F59, F75, F76** : étendre `upload_validator.py` :
   - Magic bytes pour HEIC, AVIF, GIF, TIFF.
   - Constantes vers `app/constants/limits.py`.
   - Lever `BadRequest` (core.exceptions) au lieu de `HTTPException`.

13. **F53, F78** : externaliser `COMMON_PASSWORDS` dans `app/data/common_passwords.txt` + concat dynamique avec brand_codes actifs.

14. **F54** : étendre `_has_sequential_chars` aux claviers (`azerty`, `qwerty`, `asdf`, `zxcv`).

### 5.5 Priorité 5 — Performance / cosmétique (P3)

15. **F63, F77** : transformer `DUMMY_HASH` et `_argon2_hasher` en lazy-loader (`@lru_cache(maxsize=1)`).

16. **F62** : passer `compute_client_binding_hash` à 32 chars hex (128 bits).

17. **F79** : `sanitize_csv_value` doit traiter chaque ligne séparément si la cellule est multi-ligne.

### 5.6 Tests à écrire avant refonte

- **F47** : `decode_token` sur un token sans claim `type` doit lever `TokenInvalid` (devrait actuellement passer sans erreur — confirme la friction).
- **F50** : `decode_token` doit utiliser `kid` header pour résoudre la clé. Test : 2 clés simultanées avec kids différents, les 2 doivent être valides.
- **F51** : un user avec hash legacy bcrypt + auth réussie doit avoir `password_change_required = True`.
- **F55, F56** : tests de paritée Permission ↔ Scope sur tous les couples (rôle, ressource).
- **F66** : si `auth_role_scopes` DB ne contient pas tous les scopes attendus pour un rôle, l'endpoint v3 doit retourner 403 avec liste des scopes manquants exacte.
- **F58** : tests de faux positifs du validator SQL (textes français légitimes contenant `--` final).

### 5.7 Hors-scope

- Logging, metrics, rate_limiter → module 03.
- Middlewares (CORS, audit, exception_handler) → module 04.
- Application concrète des permissions sur les endpoints → modules métier.

---

## 6. Verdict module 02

| Aspect | État |
|---|---|
| Convention 4 couches | N/A (infrastructure transverse) |
| Robustesse JWT | **Faille audience** sur tokens sans `type` (F47), `kid` ignoré (F50), bcrypt fallback double surface timing (F51) |
| Crypto KMS | **Mode prod jamais implémenté** (F48, F49) — dev-keys seulement |
| RBAC | **2 systèmes parallèles** (Permission v2, Scope v3) avec naming divergent (`INVENTORY` vs `STOCK`), comportement divergent sur rôle inconnu, `Scope.all_scopes()` manuel désaligné de la docstring |
| Validators | Patterns SQL/XSS pattern-based avec faux positifs documentés (F58, F73, F74) — vraie défense est SQLAlchemy + escape frontend |
| Multi-brand | `COMMON_PASSWORDS` couplé à 2 brands (Marveline, CaroCorp), Splendid ignoré (F53) |
| Couplage | 5 lazy imports pour casser des cycles `core.security ↔ core.kms ↔ core.password_policy` (symptôme module 01) |
| Dette | 36 frictions documentées : 3 P0, 13 P1, 17 P2, 6 P3 |

**Conclusion** : la couche crypto/auth est correcte sur la philosophie (RS256, Argon2id+pepper, envelope encryption TOTP, refresh whitelist) mais **les modes prod prévus ne sont pas branchés** (KMS) et la défense-in-depth a un trou (audience non vérifiée si type absent). La coexistence Permission v2 / Scope v3 va devenir un problème majeur dès qu'on ajoutera un brand qui exige des permissions distinctes.

→ Module suivant : `03-core-observabilite.md` (logging, metrics, health, slow_query, rate_limiter, rate_limit_utils).

# Analyse Tests Phase 2 — Sécurité (CSRF, MFA, OAuth, SMTP)

**Date**: 2026-02-16
**Analysé par**: Audit automatisé
**Status**: ✅ Analyse complète

---

## Vue d'ensemble

Cette analyse couvre la couverture de tests pour les fonctionnalités de sécurité:
- CSRF Protection (middleware + frontend auto-fetch)
- MFA/TOTP (setup, verify, disable, backup codes)
- OAuth/SSO (non implémenté)
- SMTP (backend email sending)
- Authentification (password, tokens, bruteforce, sessions)

---

## 📊 Résumé Statistiques

### Backend
- **Total tests sécurité**: 336 tests
- **Fichiers tests**: 15 fichiers
- **Couverture modules**: CSRF ✅, MFA ✅, Auth ✅, Password ✅, Tokens ✅, Sessions ✅, SMTP ✅, OAuth ❌

### Frontend
- **Total tests sécurité**: 20 tests indirects (authStore.test.ts)
- **Gaps critiques**: MFA flow complet, CSRF auto-fetch, OAuth (non implémenté)

---

## ✅ Tests Backend Existants

### 1. CSRF Protection

**Fichiers**:
- `tests/security/test_csrf_protection.py`: 14 tests
- `tests/unit/test_security_middleware.py`: 26 tests (inclut CSRF)

**Couverture totale**: 40 tests CSRF

**Détails test_csrf_protection.py**:
- Génération token CSRF (POST /auth/csrf)
- Validation token présent/absent dans header X-CSRF-Token
- Rejection requests sans token (403)
- Skip list endpoints publics (login, refresh, logout, mfa/verify)
- TTL token 15 minutes
- Multi-tenant isolation (token user A ≠ user B)
- Redis storage (csrf:{user_id}:{token})

**Détails test_security_middleware.py (section CSRF)**:
- Middleware CSRF validation pour POST/PUT/PATCH/DELETE
- Safe methods (GET/HEAD/OPTIONS) skip CSRF check
- Endpoints dans SKIP_CSRF_PATHS acceptés sans token
- 403 response avec message "CSRF token manquant" ou "CSRF token invalide"

**Gaps identifiés**:
- ⚠️ Pas de tests e2e vérifiant que frontend reçoit bien 403 et peut retry après fetch nouveau token
- ⚠️ Pas de tests vérifiant rotation CSRF token après actions sensibles (change password, MFA enable)

### 2. MFA/TOTP

**Fichiers**:
- `tests/integration/test_mfa.py`: 25 tests
- `tests/unit/test_mfa_service.py`: 44 tests

**Couverture totale**: 69 tests MFA

**Détails test_mfa.py (integration)**:
- POST /mfa/setup → provisioning_uri + secret
- POST /mfa/verify-setup → enable MFA + backup codes
- POST /mfa/verify → login avec TOTP code
- DELETE /mfa → disable MFA avec TOTP code
- GET /mfa/status → mfa_enabled + recovery_codes_remaining
- POST /mfa/backup-codes/regenerate → nouveaux backup codes
- Anti-replay TOTP (même code 2x rejected)
- Backup codes one-time use
- Multi-tenant isolation (user A ne peut pas disable MFA de user B)

**Détails test_mfa_service.py (unit)**:
- setup_mfa() génère secret + provisioning_uri
- verify_setup_code() valide TOTP code et génère backup codes
- verify_login_code() vérifie TOTP ou backup code
- disable_mfa() avec validation TOTP
- regenerate_backup_codes() avec validation TOTP
- TOTP window validation (±1 window = 30s)
- Backup codes hashing (Argon2)
- Error handling (InvalidTOTPCode, MFANotEnabled, BackupCodeAlreadyUsed)

**Gaps identifiés**:
- ⚠️ Pas de tests e2e vérifiant flow frontend complet: login → mfa_required → UI prompt code → verify → dashboard
- ⚠️ Pas de tests vérifiant QR code generation (provisioning_uri → image)

### 3. Authentification (Password, Tokens, Bruteforce, Sessions)

**Fichiers**:
- `tests/integration/test_auth_endpoints.py`: 19 tests
- `tests/integration/test_auth_phase2.py`: 14 tests
- `tests/integration/test_bruteforce_login.py`: 17 tests
- `tests/integration/test_sessions.py`: 15 tests
- `tests/security/test_multi_tenant_auth.py`: 8 tests
- `tests/security/test_password_security.py`: 23 tests
- `tests/security/test_token_security.py`: 12 tests
- `tests/unit/test_bruteforce.py`: 38 tests
- `tests/unit/test_password_policy.py`: 41 tests
- `tests/unit/test_session_service.py`: 28 tests
- `tests/unit/test_token_service.py`: 30 tests

**Couverture totale**: 245 tests Auth

**Highlights**:
- **Password policy**: 8+ chars, majuscule, minuscule, chiffre, caractère spécial, no sequential chars (4+ consécutifs)
- **Argon2 hashing**: time_cost=2, memory_cost=102400, parallelism=8
- **Bruteforce protection**: 5 tentatives login/min, lockout 15 min après 5 échecs
- **Token security**: JWT RS256, access token 1h TTL, refresh token 7j TTL, revocation via Redis blacklist
- **Session management**: 7j TTL, rotation après actions sensibles, logout single/all sessions
- **Multi-tenant auth**: User email unique par tenant (pas globalement)

**Gaps identifiés**:
- ✅ Couverture excellente, aucun gap critique

### 4. OAuth/SSO

**Status**: ❌ **NON IMPLÉMENTÉ**

**Fichiers backend**: Aucun endpoint OAuth trouvé
**Fichiers frontend**: `OAuthCallbackPage.tsx` (stub seulement, 0 logique)

**Tests existants**: 0 tests

**Gaps identifiés**:
- ℹ️ Feature non prioritaire (pas dans roadmap actuelle)

### 5. SMTP / Email Notifications

**Fichiers**:
- `tests/unit/test_notification_service.py`: 16 tests
- `tests/security/test_email_tenant_isolation.py`: 8 tests

**Couverture totale**: 24 tests SMTP

**Détails test_notification_service.py**:
- send_email() avec templates Jinja2
- send_password_reset_email() avec token unique
- send_welcome_email() après création compte
- send_mfa_enabled_notification()
- SMTP connection pool management
- Retry logic (max 3 attempts, exponential backoff)
- Error handling (SMTPException, ConnectionRefusedError)

**Détails test_email_tenant_isolation.py**:
- Emails contiennent tenant_id dans metadata
- User tenant A ne peut pas déclencher email pour user tenant B
- Email templates utilisent données filtrées par tenant

**Gaps identifiés**:
- ⚠️ Pas de tests e2e vérifiant que emails sont réellement envoyés (test avec Mailhog/MailCatcher)
- ⚠️ Pas de tests vérifiant rate limiting emails (prévention spam)

---

## ❌ Tests Frontend Manquants

### 1. CSRF Auto-Fetch & Retry (CRITIQUE)

**Status actuel**:
- ✅ Backend: 40 tests CSRF (middleware + endpoints)
- ✅ Frontend: Implémentation fetchCsrfToken() + interceptor
- ❌ **MANQUANT**: Tests frontend pour auto-fetch et retry

**Tests manquants**:

1. **authStore.test.ts** — ajouter section "fetchCsrfToken":
   ```typescript
   describe('AuthStore — fetchCsrfToken', () => {
     it('appelle GET /auth/csrf et stocke le token', async () => {
       // Mock authApi.getCsrfToken() → { csrf_token: 'abc123', expires_in: 900 }
       // Appeler fetchCsrfToken()
       // Vérifier state.csrfToken === 'abc123'
     })

     it('schedule auto-refresh après 14 minutes', async () => {
       // Mock authApi.getCsrfToken()
       // Mock setTimeout avec fake timers
       // Appeler fetchCsrfToken()
       // Avancer timer 14min
       // Vérifier getCsrfToken() appelé 2x
     })

     it('arrête auto-refresh après logout', async () => {
       // fetchCsrfToken() → schedule refresh
       // logout()
       // Avancer timer 14min
       // Vérifier getCsrfToken() PAS rappelé
     })

     it('log warning en cas d échec', async () => {
       // Mock getCsrfToken() → reject(Error)
       // Spy console.warn
       // fetchCsrfToken()
       // Vérifier console.warn appelé avec "Failed to fetch CSRF token"
     })
   })
   ```

2. **client.test.ts** (fichier à créer) — section "CSRF Interceptor":
   ```typescript
   describe('API Client — CSRF Interceptor', () => {
     it('ajoute header X-CSRF-Token pour POST', async () => {
       // Set csrfToken in authStore
       // apiClient.post('/products', {})
       // Vérifier request headers['X-CSRF-Token'] === csrfToken
     })

     it('ajoute header pour PUT/PATCH/DELETE', async () => {
       // Tester PUT, PATCH, DELETE
     })

     it('n ajoute PAS header pour GET/HEAD/OPTIONS', async () => {
       // apiClient.get('/products')
       // Vérifier headers['X-CSRF-Token'] === undefined
     })

     it('n ajoute PAS header si csrfToken null', async () => {
       // authStore.setState({ csrfToken: null })
       // apiClient.post('/products', {})
       // Vérifier headers['X-CSRF-Token'] === undefined
     })
   })
   ```

3. **e2e/csrf.test.ts** (intégration backend-frontend):
   ```typescript
   describe('E2E — CSRF Flow', () => {
     it('login → fetch CSRF → POST product → success', async () => {
       // Login user
       // Vérifier fetchCsrfToken() appelé automatiquement
       // POST /products
       // Vérifier header X-CSRF-Token présent
       // Vérifier 201 Created
     })

     it('POST sans CSRF → 403 → auto-retry avec nouveau token → 201', async () => {
       // Clear csrfToken
       // POST /products → expect 403
       // Vérifier fetchCsrfToken() appelé
       // Retry POST /products → expect 201
     })

     it('CSRF token expiré (15min) → auto-refresh', async () => {
       // Mock time 14min après login
       // Vérifier fetchCsrfToken() rappelé
       // POST /products → success
     })
   })
   ```

**Priorité**: 🔴 P0 CRITIQUE

### 2. MFA Flow Complet (IMPORTANT)

**Status actuel**:
- ✅ Backend: 69 tests MFA (integration + unit)
- ✅ Frontend: API calls implémentés (authApi.mfaSetup, mfaVerify, etc.)
- ❌ **MANQUANT**: Tests frontend flow complet

**Tests manquants**:

1. **authStore.test.ts** — ajouter section "MFA Flow":
   ```typescript
   describe('AuthStore — MFA Flow', () => {
     it('login avec MFA → stocke mfaSessionToken', async () => {
       // Mock authApi.login() → { mfa_required: true, mfa_session_token: 'xyz' }
       // Appeler login()
       // Vérifier state.mfaSessionToken === 'xyz'
       // Vérifier state.accessToken === null (pas encore authentifié)
     })

     it('verify MFA → stocke access/refresh tokens', async () => {
       // Set mfaSessionToken
       // Mock authApi.mfaVerify() → { access_token, refresh_token }
       // Appeler verifyMfa(code)
       // Vérifier state.accessToken présent
       // Vérifier state.mfaSessionToken === null (cleared)
     })
   })
   ```

2. **e2e/mfa.test.ts** (intégration backend-frontend):
   ```typescript
   describe('E2E — MFA Flow', () => {
     it('setup MFA → QR code → verify → backup codes', async () => {
       // POST /mfa/setup
       // Vérifier provisioning_uri retourné
       // Générer QR code (qrcode library)
       // POST /mfa/verify-setup avec TOTP code
       // Vérifier backup_codes retournés (10 codes)
       // Vérifier MFA enabled
     })

     it('login avec MFA → prompt code → verify → dashboard', async () => {
       // POST /auth/login → { mfa_required: true, mfa_session_token }
       // Vérifier redirect vers /mfa-verify
       // POST /mfa/verify → { access_token, refresh_token }
       // Vérifier redirect vers /dashboard
     })

     it('disable MFA → prompt TOTP code → success', async () => {
       // DELETE /mfa avec { code: '123456' }
       // Vérifier MFA disabled
       // Login suivant → direct access (pas de MFA prompt)
     })
   })
   ```

**Priorité**: 🟠 P1 IMPORTANT

### 3. OAuth/SSO (NON PRIORITAIRE)

**Status**: ❌ Non implémenté backend + frontend

**Tests manquants**: Tous (0 tests)

**Priorité**: 🟡 P3 FUTUR — Pas dans roadmap actuelle

### 4. Email Notifications (UTILE)

**Status actuel**:
- ✅ Backend: 24 tests SMTP (unit + isolation)
- ❌ **MANQUANT**: Tests e2e avec vrai SMTP (Mailhog)

**Tests manquants**:

1. **e2e/email.test.py** (Playwright + Mailhog):
   ```python
   def test_password_reset_email_sent(client, mailhog):
       # POST /auth/forgot-password avec email
       # Attendre 1s (async email sending)
       # Vérifier email reçu dans Mailhog
       # Parser email body → extraire token reset
       # POST /auth/reset-password avec token
       # Vérifier password changé

   def test_welcome_email_after_signup(client, mailhog):
       # POST /users avec nouvel utilisateur
       # Vérifier email "Bienvenue" reçu
       # Vérifier email contient lien activation

   def test_mfa_enabled_notification(client, mailhog):
       # POST /mfa/verify-setup
       # Vérifier email "MFA activé" reçu
   ```

**Priorité**: 🟡 P2 UTILE — Nice-to-have, pas bloquant

---

## 📋 Actions Recommandées

### P0 — CRITIQUE (Bloquer production sans ça)

1. **Créer `frontend/src/stores/__tests__/authStore.test.ts` — section fetchCsrfToken**
   - 4 tests: fetch + store, auto-refresh, stop après logout, error handling
   - Utiliser vi.useFakeTimers() pour setTimeout
   - Couverture cible: fetchCsrfToken() 100%

2. **Créer `frontend/src/api/__tests__/client.test.ts` — section CSRF Interceptor**
   - 4 tests: header pour POST/PUT/PATCH/DELETE, pas pour GET, pas si token null
   - Mock authStore.getState()
   - Couverture cible: interceptor request 100%

3. **Créer tests e2e CSRF flow**
   - Fichier: `tests/e2e/test_csrf_flow.py` (Playwright Python)
   - 3 scénarios: login → fetch → POST, 403 → retry, token expiré → refresh
   - Vérifier headers HTTP avec DevTools protocol

### P1 — IMPORTANT (Améliore robustesse)

4. **Ajouter tests MFA flow dans authStore.test.ts**
   - 2 tests: login MFA → mfaSessionToken, verify → access_token
   - Mock authApi.login() et authApi.mfaVerify()

5. **Créer tests e2e MFA flow complet**
   - Fichier: `tests/e2e/test_mfa_flow.py`
   - 3 scénarios: setup → QR → verify, login MFA → verify → dashboard, disable MFA
   - Utiliser pyotp pour générer TOTP codes valides

### P2 — UTILE (Complétude, pas bloquant)

6. **Créer tests e2e email avec Mailhog**
   - Fichier: `tests/e2e/test_email_notifications.py`
   - Setup Mailhog dans docker-compose-test.yml
   - 3 scénarios: password reset, welcome, MFA enabled
   - Parser emails HTTP API Mailhog (http://mailhog:8025/api/v2/messages)

7. **Ajouter tests CSRF rotation après actions sensibles**
   - Vérifier nouveau token généré après change password, MFA enable/disable
   - Fichier: `tests/integration/test_csrf_rotation.py`

### P3 — FUTUR (Roadmap long terme)

8. **OAuth/SSO implementation + tests**
   - Pas prioritaire actuellement
   - Si implémenté: suivre pattern MFA (unit + integration + e2e)

---

## 🔍 Méthodes de Vérification

### Tests backend
```bash
# Lister tous les tests sécurité
find tests/ -name "*.py" | grep -iE "(csrf|mfa|totp|oauth|smtp|email|auth|password|token|brute|session)"

# Compter tests dans chaque fichier
for file in tests/integration/test_mfa.py tests/security/test_csrf_protection.py; do
  grep -cE "(def test_|async def test_)" "$file"
done
```

### Tests frontend
```bash
# Chercher tests MFA/CSRF/OAuth
grep -r "mfa\|totp\|csrf\|oauth" frontend/src/**/*.test.ts

# Lister descriptions tests authStore
grep -E "(describe|it)\(" frontend/src/stores/__tests__/authStore.test.ts
```

### Vérifier SMTP logs
```bash
# Si Mailhog configuré
curl http://localhost:8025/api/v2/messages | jq '.items[] | {subject, to}'
```

---

## 📝 Notes Techniques

### CSRF Flow
- **Backend**: CSRFProtectionMiddleware valide X-CSRF-Token pour POST/PUT/PATCH/DELETE
- **Frontend**: authStore.fetchCsrfToken() auto-appelé après setTokens(), refresh toutes les 14 min
- **TTL**: 15 min backend, auto-refresh 14 min frontend (marge 1 min)
- **Redis key**: `csrf:{user_id}:{token}` (permet révocation instantanée)
- **Skip list**: /auth/login, /auth/refresh, /auth/logout, /mfa/verify (endpoints publics)

### MFA Flow
1. **Setup**: POST /mfa/setup → secret + provisioning_uri
2. **Verify setup**: POST /mfa/verify-setup + TOTP code → backup_codes (10)
3. **Login**: POST /auth/login → { mfa_required: true, mfa_session_token }
4. **Verify login**: POST /mfa/verify + mfa_session_token + TOTP code → access_token + refresh_token
5. **Disable**: DELETE /mfa + TOTP code → MFA disabled

### Password Policy
- **Min 8 chars**: Majuscule + minuscule + chiffre + caractère spécial
- **No sequential**: 4+ chars consécutifs interdits (e.g., "abcd", "1234")
- **Hashing**: Argon2id (time_cost=2, memory_cost=102400, parallelism=8)
- **Fallback validation**: Si PasswordPolicy service indisponible, validation minimale (8+ chars, majuscule, special char)

### Token Security
- **Algorithm**: RS256 (asymmetric, clés pub/priv)
- **Access token TTL**: 1 heure
- **Refresh token TTL**: 7 jours
- **Revocation**: Redis blacklist (revoked_tokens:{token_jti})
- **Rotation**: Nouveaux tokens générés après actions sensibles (change password, MFA toggle)

### Session Management
- **TTL**: 7 jours (SESSION_TTL_SECONDS)
- **Storage**: Redis (session:{user_id}:{session_id})
- **Actions**: GET /sessions (list), DELETE /sessions/{id} (single logout), DELETE /sessions (logout all)
- **Rotation**: session_id changé après login, MFA enable, password change

### SMTP Configuration
- **Provider**: Configurable (SendGrid, Mailgun, SMTP local)
- **Templates**: Jinja2 (templates/email/)
- **Retry**: Max 3 attempts, exponential backoff (1s, 2s, 4s)
- **Rate limiting**: Pas encore implémenté (TODO: max 100 emails/user/jour)

---

**Analyse effectuée le**: 2026-02-16
**Fichiers analysés**: 15 fichiers tests backend, 1 fichier tests frontend (authStore.test.ts)
**Total tests comptés**: 336 tests backend, 20 tests frontend indirects
**Gaps critiques identifiés**: 2 (CSRF frontend tests P0, MFA flow frontend P1)

# Audit Sécurité — Socle Auth CaroCorp
> Généré le 2026-03-03 | État : EN COURS DE CORRECTION

---

## Légende sévérités
- **P0** : Vulnérabilité exploitable immédiatement — arrêt de session
- **P1** : Faille sécurité sérieuse — à corriger avant tout merge
- **P2** : Incohérence logique ou spec — à corriger dans le sprint
- **P3** : Dette technique, observabilité, qualité

---

## P0 — Arrêt immédiat requis

### [P0-01] CORS preflight cassé — StrictCORSMiddleware bloque OPTIONS
**Fichier** : `app/middleware/cors.py:58`
**Symptôme** : Browser envoie `OPTIONS /endpoint` (preflight). Middleware retourne 403 "Origin not allowed" avant que `CORSMiddleware` de FastAPI puisse répondre. CORS entièrement cassé depuis le browser.
**Fix** : Laisser passer les requêtes OPTIONS inconditionnellement, ou vérifier l'origin uniquement sur les requêtes non-OPTIONS.
**Statut** : ⬜ À corriger

---

### [P0-02] is_device_revoked FAIL-OPEN — device compromis peut se reconnecrer si Redis down
**Fichier** : `app/core/redis.py:434`
**Symptôme** : `is_device_revoked()` retourne `False` si Redis-SEC down (FAIL-OPEN). Un device révoqué pour compromission peut continuer à utiliser l'API pendant une panne Redis.
**Spec** : §7.1 S-08.1 — révocation forcée = FAIL-CLOSED.
**Fix** : Retourner `True` (bloqué) si Redis-SEC inaccessible.
**Statut** : ⬜ À corriger

---

### [P0-03] Token type non vérifié dans decode_token() — substitution access/refresh possible
**Fichier** : `app/core/security.py:147`
**Symptôme** : `decode_token()` essaie les deux clés (access + refresh) sans vérifier le claim `"type"` avant. Un refresh token peut matcher la clé access, ou vice versa. Endpoints qui appellent `decode_token()` au lieu de `decode_access_token()` acceptent des refresh tokens.
**Fix** : Vérifier le claim `"type"` en premier avant de tenter les clés.
**Statut** : ⬜ À corriger

---

### [P0-04] jwt_scopes jamais peuplé dans request.state — RBAC scope-based non fonctionnel
**Fichier** : `app/core/deps.py:603`, `app/middleware/request_context.py`
**Symptôme** : `scope_checker()` dans `require_scope()` tente de lire `request.state.jwt_scopes`. Aucun middleware ne définit ce champ. Fallback sur role-based toujours. Les scopes embarqués dans le JWT (claim "scopes") ne sont **jamais** utilisés pour le RBAC.
**Fix** : Dans `RequestContextMiddleware` (ou `SecurityHeadersMiddleware`), extraire le claim `"scopes"` du JWT et l'écrire dans `request.state.jwt_scopes`.
**Statut** : ⬜ À corriger

---

### [P0-05] Anti-replay TOTP non atomique — double authentification possible
**Fichier** : `app/services/mfa.py` (verify_totp)
**Symptôme** : Vérification `last_totp_window` puis écriture du nouveau window sont deux opérations Redis séparées. Deux requêtes concurrentes avec le même code TOTP peuvent toutes les deux passer la vérification avant que la première ne marque le window comme utilisé.
**Fix** : Utiliser un script Lua pour atomiser check + set du window TOTP.
**Statut** : ⬜ À corriger

---

## P1 — Failles sécurité sérieuses

### [P1-01] CORS 403 en text/plain — frontend ne peut pas parser l'erreur
**Fichier** : `app/middleware/cors.py:58`
**Symptôme** : Response CORS violation retournée en `text/plain`. Tous les autres endpoints retournent `{"detail": "..."}`. Frontend reçoit format inattendu.
**Fix** : Retourner `JSONResponse({"detail": "Origin not allowed"}, status_code=403)`.
**Statut** : ⬜ À corriger

---

### [P1-02] CSRF middleware exempte /logout et /mfa/verify sans vérifier Bearer présent
**Fichier** : `app/middleware/security.py:37-46`
**Symptôme** : Exemption CSRF basée sur le path seulement. Note B2 dit "exemptés car Bearer requis" mais le middleware ne vérifie pas que l'header `Authorization` est présent. Un attaquant peut appeler `POST /logout` sans token et sans CSRF.
**Fix** : Dans le bloc d'exemption, vérifier `request.headers.get("Authorization")` avant de passer.
**Statut** : ⬜ À corriger

---

### [P1-03] Password reset : BD changée avant révocation sessions — fenêtre de corruption
**Fichier** : `app/services/auth.py:reset_password()`
**Symptôme** : Séquence : `user.hashed_password = ...` → `flush()` → `revoke_all_sessions()` (Redis). Si Redis-SEC down entre flush et révocation, le password est changé en BD mais les sessions anciennes restent valides.
**Ordre correct** : Révocation Redis d'abord → flush BD → commit.
**Statut** : ⬜ À corriger

---

### [P1-04] Login : session_service.create_session() appelé après commit — state incohérent
**Fichier** : `app/services/auth.py:login()` ~L209-225
**Symptôme** : Si MFA requis, `await self.db.commit()` est appelé, puis si échec lors de `session_service.create_session()`, la session n'est pas en BD mais le commit est déjà fait. Tokens peuvent être émis sans session persistée.
**Statut** : ⬜ À corriger

---

### [P1-05] API key hash comparison non timing-safe
**Fichier** : `app/core/deps.py:_resolve_api_key_async()`
**Symptôme** : Hash SHA256 de l'API key est comparé sans `hmac.compare_digest()`. Attaque timing pour deviner la clé.
**Fix** : Utiliser `hmac.compare_digest(computed_hash, stored_hash)`.
**Statut** : ⬜ À corriger

---

### [P1-06] get_current_user (sync) ne vérifie pas les devices révoqués
**Fichier** : `app/core/deps.py:get_current_user()` (version sync ~L88-177)
**Symptôme** : `get_current_user_async()` appelle `_handle_revoked_device()`. La version synchrone ne le fait pas. Les endpoints utilisant encore la version sync acceptent des devices révoqués.
**Fix** : Ajouter appel `_handle_revoked_device()` dans la version sync également.
**Statut** : ⬜ À corriger

---

### [P1-07] store_jti_meta() appelé APRÈS Lua refresh_check_v3 — race condition
**Fichier** : `app/services/token.py:rotate_refresh_token()` L228-232
**Symptôme** : Lua vérifie et consomme le JTI. Puis `store_jti_meta()` est appelé. Entre les deux, si Redis crash, nouveau JTI est dans la whitelist mais sans meta → TTL résiduel blacklist impossible lors du prochain logout.
**Fix** : Pre-calculer le `jti_meta` et le passer au Lua, ou stocker avant l'appel Lua.
**Statut** : ⬜ À corriger

---

### [P1-08] recovery_code consumption non atomique — double usage possible
**Fichier** : `app/services/mfa.py:verify_recovery_code()`
**Symptôme** : `hashes.pop(matched_index)` + `json.dumps()` + `flush()` sont trois opérations séparées. Deux clients avec le même recovery code peuvent tous les deux réussir si concurrents.
**Fix** : SELECT FOR UPDATE sur la ligne MFADevice avant de consommer le code.
**Statut** : ⬜ À corriger

---

### [P1-09] MFA session token (verify step) non atomique — double usage
**Fichier** : `app/services/mfa.py:verify_mfa_session()` ~L378-388
**Symptôme** : `redis.get()` puis `redis.delete()` séparés. Deux clients avec le même `mfa_session_token` peuvent tous deux passer GET avant que DELETE ne soit exécuté.
**Fix** : Script Lua `GETDEL` atomique, ou pipeline `GET + DEL`.
**Statut** : ⬜ À corriger

---

### [P1-10] Step-up Redis write sans try/catch — FAIL-OPEN silencieux
**Fichier** : `app/services/mfa.py` ~L440
**Symptôme** : `redis_client.client.setex()` sans gestion d'erreur. Si Redis down, step-up non persisté → endpoints step-up accessibles sans MFA.
**Spec** : §5.3 step-up = FAIL-CLOSED.
**Fix** : Ajouter try/catch + logger.critical + lever HTTPException 503.
**Statut** : ⬜ À corriger

---

### [P1-11] Fallback _manual_rotate() non atomique, non loggué
**Fichier** : `app/services/token.py:_manual_rotate()` L236
**Symptôme** : Activé si Lua non chargé. Deux clients concurrent peuvent exécuter ce fallback simultanément → replay non détecté. Aucun log warning.
**Fix** : Logger.warning obligatoire + documenter que ce mode est interdit en production.
**Statut** : ⬜ À corriger

---

### [P1-12] /logout erreur catch trop large — tokens zombie en cas d'erreur Redis
**Fichier** : `app/api/v1/endpoints/auth.py:logout()` L235-238
**Symptôme** : `except Exception` générique retourne 200 OK même si révocation Redis a échoué. Client pense logout réussi, tokens restent valides.
**Fix** : Différencier les erreurs. Redis-SEC down = 503 (FAIL-CLOSED). Autres = re-raise.
**Statut** : ⬜ À corriger

---

### [P1-13] Verify password fallback sans pepper — affaiblissement silencieux
**Fichier** : `app/core/security.py:verify_password()` L256-266
**Symptôme** : Fallback accepte hashs Argon2 sans pepper (ligne 264). Hashs legacy peuvent être vérifiés sans la clé pepper. Affaiblissement de la sécurité des mots de passe anciens sans notification.
**Fix** : Marquer ces hashs comme `needs_rehash=True`, forcer changement prochain login.
**Statut** : ⬜ À corriger

---

### [P1-14] Credential stuffing : seuil comparaison absente dans increment_credential_stuffing()
**Fichier** : `app/core/redis.py:increment_credential_stuffing()` (ou service bruteforce)
**Symptôme** : Incrémente le compteur mais ne déclenche pas `set_captcha_required()` ni `set_login_blocked()`. Ces méthodes existent mais ne sont jamais appelées automatiquement.
**Fix** : Après increment, si count > CAPTCHA_THRESHOLD → `set_captcha_required()`, si count > BLOCK_THRESHOLD → `set_login_blocked()`.
**Statut** : ⬜ À corriger

---

### [P1-15] change_password révoque sessions avant de valider le changement BD
**Fichier** : `app/api/v1/endpoints/auth.py:change_password()` L337-383
**Symptôme** : `auth_service.change_password()` peut échouer (brute limit, HIBP...) APRÈS `redis_client.logout_other_sessions()` est appelé. Sessions révoquées même si changement de password a échoué.
**Ordre correct** : change_password() → si succès → logout_other_sessions() → commit.
**Statut** : ⬜ À corriger

---

## P2 — Incohérences logique/spec

### [P2-01] CSRF token TTL 900s hardcoded — expire avant la session (7 jours)
**Fichier** : `app/core/redis.py:store_csrf_token()` L93
**Symptôme** : CSRF token expire après 15 minutes. La session dure 7 jours. Après 15 minutes, les requêtes CSRF échouent (403) même si la session est valide.
**Fix** : TTL CSRF = TTL session (7 jours), ou refresh CSRF TTL à chaque requête validée.
**Statut** : ⬜ À corriger

---

### [P2-02] IPv6 non normalisé pour rate limiting — bypass possible
**Fichier** : `app/middleware/security.py:_get_client_ip()` L220
**Symptôme** : `::ffff:127.0.0.1` et `127.0.0.1` génèrent des clés Redis différentes. Attaquant change représentation IPv6 pour contourner rate limit.
**Fix** : Normaliser IP via `ipaddress.ip_address(ip).compressed`.
**Statut** : ⬜ À corriger

---

### [P2-03] request_id non défini si middleware échoue — audit logs sans trace
**Fichier** : Tous les endpoints auth (getattr guard présent mais toujours None si middleware absent)
**Symptôme** : Si `RequestContextMiddleware` n'est pas chargé ou échoue, `request_id=None` dans tous les audit logs. Traçabilité perdue.
**Fix** : Générer un UUID de fallback si `request.state.request_id` absent.
**Statut** : ⬜ À corriger

---

### [P2-04] revoke_all_sessions() ordre DB/Redis non garanti
**Fichier** : `app/services/session.py:revoke_all_sessions()` L267-281
**Symptôme** : Marque sessions en DB puis appelle Redis. Si Redis crash après flush DB, sessions DB révoquées mais Redis vivant. Sens inverse correct : Redis d'abord, DB ensuite.
**Statut** : ⬜ À corriger

---

### [P2-05] CSRF TTL dans schema hardcodé à 900 — désynchronisé avec Redis
**Fichier** : `app/schemas/auth.py:CSRFTokenResponse` L282
**Symptôme** : `expires_in: int = Field(default=900)` hardcodé. Si Redis TTL change, schema devient obsolète sans erreur.
**Fix** : Importer `SessionConfig.CSRF_TTL_SECONDS` ou constante dédiée.
**Statut** : ⬜ À corriger

---

### [P2-06] _extract_user_id_from_jwt jamais appelée — code mort
**Fichier** : `app/middleware/security.py:79-103`
**Symptôme** : Méthode définie mais jamais utilisée. Confusion pour les devs.
**Fix** : Supprimer ou documenter l'usage futur.
**Statut** : ⬜ À corriger

---

### [P2-07] UserSession.session_id unique global (non tenant-aware)
**Fichier** : `app/models/user_session.py:48`
**Symptôme** : Contrainte unique globale sur `session_id`. UUID collision improbable mais design incorrect pour multi-tenant strict.
**Fix** : Index unique composite `(tenant_id, session_id)`.
**Statut** : ⬜ À corriger

---

### [P2-08] cleanup_expired() sur password_reset_tokens jamais appelé
**Fichier** : `app/repositories/password_reset_token.py`
**Symptôme** : Méthode `cleanup_expired()` définie mais jamais appelée. Tokens expirés s'accumulent en BD.
**Fix** : Appeler dans `forgot_password()` avant création, ou tâche Celery périodique.
**Statut** : ⬜ À corriger

---

### [P2-09] Permission checker compare Enum vs str — logique peut échouer silencieusement
**Fichier** : `app/core/deps.py:require_permission()` L289
**Symptôme** : `missing = set(permissions) - user_perms` où `permissions` = tuple d'enums et `user_perms` = set[str]. La comparaison peut échouer si les enums ne sont pas hashables avec des strings.
**Fix** : `missing = {p.value for p in permissions} - user_perms`.
**Statut** : ⬜ À corriger

---

### [P2-10] DEVICE_REVOKED detail retourné en dict, autres en str — format incohérent
**Fichier** : `app/core/deps.py:get_current_user_async()` L431-434
**Symptôme** : `detail={"error": "DEVICE_REVOKED", "message": ...}` (dict) alors que les autres HTTPException utilisent une string simple.
**Fix** : Unifier en `detail="DEVICE_REVOKED"` ou documenter que le frontend gère les deux formats.
**Statut** : ⬜ À corriger

---

### [P2-11] eviction loop session appelle Redis dans boucle — incohérence si crash mid-loop
**Fichier** : `app/services/session.py:_enforce_max_sessions()` L399-415
**Symptôme** : Boucle qui révoque sessions one-by-one. Si Redis crash à mi-parcours, certaines sessions DB révoquées mais pas Redis.
**Fix** : Utiliser `revoke_all_user_sessions` Lua avec filtre, ou vérifier entièrement en DB d'abord.
**Statut** : ⬜ À corriger

---

### [P2-12] mfa_verified flag stocké mais jamais consulté dans le flow step-up
**Fichier** : `app/services/session.py:create_session()` L73, L110
**Symptôme** : `mfa_verified` est stocké dans la session mais n'est jamais relu pour déterminer si un step-up est nécessaire pour les endpoints sensibles.
**Fix** : Dans `require_stepup()`, vérifier `UserSession.mfa_verified` en DB en plus du flag Redis.
**Statut** : ⬜ À corriger

---

### [P2-13] Password pepper en variable d'environnement — doit être en KMS
**Fichier** : `app/core/config.py:49`, `app/core/security.py:235`
**Symptôme** : `PASSWORD_PEPPER` chargé depuis `.env`. Si `.env` leak, tous les hashs sont attaquables. Spec exige KMS pour secrets cryptographiques.
**Fix** : Migrer vers `app/core/kms.py:get_password_pepper()` (similaire aux clés JWT).
**Statut** : ⬜ À corriger (migration KMS)

---

### [P2-14] UserSession manque FK vers tenants + index expires_at
**Fichier** : `app/models/user_session.py:59`
**Symptômes** :
1. `tenant_id` sans FK vers `tenants.id` → données orphelines possibles
2. Pas d'index sur `expires_at` → cleanup jobs lents
**Fix** : Ajouter FK + `Index("idx_user_sessions_expires", "expires_at")`.
**Statut** : ⬜ À corriger

---

### [P2-15] max() sessions_revoked incorrect dans logout_device
**Fichier** : `app/api/v1/endpoints/auth.py:logout_device()` L446
**Symptôme** : `max(sessions_revoked_redis, sessions_revoked_db)` n'a pas de sens — les deux compteurs sont indépendants.
**Fix** : Retourner `sessions_revoked_db` (source de vérité).
**Statut** : ⬜ À corriger

---

## P3 — Dette technique / observabilité

### [P3-01] CSP désactivée en DEBUG — XSS non détecté en dev
**Fichier** : `app/middleware/security.py:163`
**Fix** : Activer CSP en dev avec une policy permissive plutôt que désactivée.

### [P3-02] StrictCORSMiddleware whitelist chargée au __init__ — non rechargeable sans restart
**Fichier** : `app/middleware/cors.py:40`
**Fix** : Lazy reload ou TTL cache de 60s.

### [P3-03] EMERGENCY_BYPASS sans audit persistant
**Fichier** : `app/middleware/degraded.py:87`
**Fix** : Écrire en BD + envoyer webhook PagerDuty.

### [P3-04] _extract_user_id_from_jwt() code mort dans security middleware
**Fichier** : `app/middleware/security.py:79`
**Fix** : Supprimer.

### [P3-05] DUMMY_HASH calculé à l'import — fragile si settings pas prêts
**Fichier** : `app/core/security.py:319`
**Fix** : Lazy init via `@lru_cache(maxsize=1)`.

### [P3-06] UserSession.user relationship lazy="noload" — greenlet error si accédé
**Fichier** : `app/models/user_session.py:123`
**Fix** : Documenter ou passer à `lazy="select"`.

### [P3-07] User model sans last_login_at, mfa_enabled, account_locked_until
**Fichier** : `app/models/user.py`
**Colonnes manquantes pour audit/UX** — à ajouter via migration.

### [P3-08] Role CHECK constraint hardcodé — requiert double modification pour ajout de rôle
**Fichier** : `app/models/user.py:100`
**Fix** : Générer depuis `UserRole` enum.

---

## Récapitulatif

| Sévérité | Nombre | Traités | Restants |
|----------|--------|---------|---------|
| P0 | 5 | 0 | 5 |
| P1 | 15 | 0 | 15 |
| P2 | 15 | 0 | 15 |
| P3 | 8 | 0 | 8 |

---

## Ordre de traitement recommandé

### Step 1 — P0 (bloquer tout déploiement)
1. [P0-01] CORS preflight OPTIONS
2. [P0-03] Token type non vérifié dans decode_token()
3. [P0-04] jwt_scopes jamais peuplé dans request.state
4. [P0-02] is_device_revoked FAIL-CLOSED
5. [P0-05] Anti-replay TOTP atomique

### Step 2 — P1 sécurité critique
6. [P1-02] CSRF middleware exemption incomplète
7. [P1-12] logout catch trop large → tokens zombie
8. [P1-03] password reset ordre BD/Redis
9. [P1-15] change_password ordre révocation
10. [P1-14] credential stuffing seuil manquant
11. [P1-05] API key timing-safe compare
12. [P1-01] CORS 403 JSON
13. [P1-06] get_current_user sync manque device check
14. [P1-07] store_jti_meta avant Lua
15. [P1-08] recovery code atomique
16. [P1-09] MFA session GETDEL atomique
17. [P1-10] step-up FAIL-CLOSED
18. [P1-11] fallback manual_rotate log
19. [P1-04] login session race
20. [P1-13] verify_password rehash

### Step 3 — P2 logique/spec
21. [P2-01] CSRF TTL 900s → session TTL
22. [P2-04] revoke_all_sessions ordre DB/Redis
23. [P2-09] permission checker Enum vs str
24. [P2-02] IPv6 normalization
25. Reste P2...

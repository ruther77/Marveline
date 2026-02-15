# TÂCHES COMPLÈTES — CaroCorp_new / Marveline

> Généré le 2026-02-13 après audit exhaustif (6 agents backend + 4 agents complémentaires).
> Couvre : code backend, frontend, tests, infrastructure, CI/CD, DevOps.

---

## Légende

- **P0** = Critique (faille sécurité, crash prod, perte données)
- **P1** = Important (bug fonctionnel, perf, risque prod)
- **P2** = Moyen (qualité code, maintenabilité, bonnes pratiques)
- **P3** = Mineur (style, typos, cosmétique)

---

## 1. AUDIT BACKEND — Issues originales (32)

### P0 — CRITIQUE (3)

| # | Fichier | Ligne(s) | Problème | Correction |
|---|---------|----------|----------|------------|
| A1 | `app/api/v1/endpoints/audit.py` | 27, 129, 224 | `AdminUser` non lié avec `Depends()` — 3 endpoints audit accessibles sans auth admin. Faille sécurité majeure. | Ajouter `Depends()` sur AdminUser paramètre |
| A2 | `app/tasks/celery_app.py` | 39-44 | 4 modules autodiscovered inexistants (`reservations`, `invoicing`, `notifications`, `reports`). Celery fail silencieusement. | Créer fichiers vides ou commenter autodiscover |
| A3 | `app/middleware/audit.py` | 336-348 | Bug `_singularize_entity_type` : `invoices` → `invoic` (pas `invoice`). Branche `endswith("ies")` contient `pass` sans implémentation. | Implémenter la logique de singularisation |

### P1 — IMPORTANT (7)

| # | Fichier | Ligne(s) | Problème | Correction |
|---|---------|----------|----------|------------|
| B1 | `app/middleware/audit.py` | 186-218, 248-269 | DB session leak : `next(get_db())` + `.close()` manuel sans context manager. Exception entre les deux → connexion fuitée. | Utiliser `get_db_context()` context manager |
| B2 | `app/middleware/security.py` | 44-47 | CSRF bypass sur LOGOUT : endpoint exempté. Attaquant peut forcer déconnexion via CSRF. | Re-évaluer exemption CSRF logout |
| B3 | `app/middleware/` | security.py, audit.py, request_context.py | JWT décodé 3 fois par requête (chaque middleware re-decode). Perf + risque de divergence. | Centraliser JWT parsing via `request.state` |
| B4 | `app/api/v1/endpoints/invoices.py` | 97 | GET `/overdue` sans pagination : retourne `list[InvoiceList]` sans limite. | Ajouter `PaginationParams` ou limit max |
| B5 | `alembic/env.py` | 10 | Imports partiels : 5 modèles importés. `User`, `MFADevice`, `AuditLog` manquent → autogenerate incomplet. | Importer tous les modèles via `app.models` |
| B6 | `app/repositories/product.py` | 167-196 | Race condition stock : `reserve_stock()` / `release_stock()` sans `SELECT FOR UPDATE`. | Ajouter `with_for_update()` |
| B7 | `app/middleware/security.py` | ~119 | Timing attack CSRF : comparaison longueur token sans `secrets.compare_digest`. | Utiliser `secrets.compare_digest()` |

### P2 — MOYEN (14)

| # | Fichier | Ligne(s) | Problème |
|---|---------|----------|----------|
| C1 | `app/core/config.py` | 28, 34, 46, 55 | Secrets DEV hardcodés (JWT_SECRET, REDIS password, CSRF_SECRET, ENCRYPTION_KEY). Devrait être `.env`-only. |
| C2 | `app/core/redis.py` | Partout | `import json` répété dans 8+ fonctions au lieu de top-level. |
| C3 | `app/core/security.py` | 236-246 | Fallback validation password trop léger si `password_policy` import fail. Devrait fail-close ou logger warning. |
| C4 | `app/core/exceptions.py` | 71-80 | `TokenRevoked` et `TokenReplayDetected` définis mais non exportés dans `__init__.py`. |
| C5 | `app/services/reservation.py` | 32 | Class variable mutable `_generated_references: set = set()`. Partagée entre instances (même pattern bug que ancien MFA). |
| C6 | `app/models/mfa.py` | — | Pas de `UniqueConstraint(tenant_id, user_id)` → possible d'avoir 2 MFA devices par user. |
| C7 | `app/models/` | 5 tables | FK indexes manquants : `customer.email`, `reservation.customer_id`, `reservation_line.product_id`, `product.category`, `product.available_quantity`. |
| C8 | Services | invoice, product, reservation | Messages erreur hardcodés avec `str(e)` exposent détails implémentation. Utiliser `ErrorMessages.*`. |
| C9 | Endpoints | customers, products, reservations, invoices | Catch-all `except Exception` avec `str(e)` dans response HTTP. Information disclosure. |
| C10 | `app/middleware/security.py` | — | CORS `allow_methods=["*"]` trop permissif. Lister explicitement les méthodes. |
| C11 | `app/middleware/` | security.py + metrics.py | `_determine_scope()` dupliqué dans 2 middlewares. Risque de divergence. |
| C12 | `app/middleware/` | audit.py + metrics.py | Patterns hardcodés (`SENSITIVE_READ_PATTERNS`, `PATH_PATTERNS`). Nouvel endpoint = édition middleware. |
| C13 | `app/constants/security.py` vs `config.py` | — | Duplication Argon2 params (`TIME_COST`, `MEMORY_COST`, `PARALLELISM`) définis aux 2 endroits. |
| C14 | `app/constants/security.py` | — | Incohérence TTL : `Limits.SESSION_TIMEOUT_SECONDS=3600` (1h) vs `SessionConfig.SESSION_TTL_SECONDS=604800` (7j). |

### P3 — MINEUR (8)

| # | Fichier | Problème |
|---|---------|----------|
| D1 | `app/api/v1/endpoints/health.py:173` | Version hardcodée `"0.1.0"` (TODO existant). |
| D2 | Services (`token.py:144`, `auth.py:368`, `cache.py:92+`) | Imports dynamiques dans fonctions au lieu de top-level. |
| D3 | `app/core/deps.py:111` | Indentation accidentelle sur `ManagerUser`. |
| D4 | `app/services/invoice.py:229,325,375` + `reservation.py:299,366` | Espacement manquant `status=X` au lieu de `status = X`. |
| D5 | `app/services/cache.py:347,356` | `None` non cachée → miss permanent pour valeurs nulles légitimes. |
| D6 | `app/services/cache.py:96+` | Accès direct `self.redis.client` contourne l'abstraction du wrapper Redis. |
| D7 | `app/schemas/audit.py` | Filtres audit trop permissifs (`entity_id` sans `entity_type` accepté). |
| D8 | `app/middleware/` | Pas d'audit trail pour échecs CSRF/rate limit. |

---

## 2. TODO/FIXME DANS LE CODE (6)

| # | Fichier | Ligne | Contenu | Type |
|---|---------|-------|---------|------|
| TD1 | `app/api/v1/endpoints/health.py` | 173 | `# TODO: récupérer depuis settings ou pyproject.toml` | Backend |
| TD2 | `app/services/mfa.py` | 157 | `# noqa: E712` (comparaison `== False` SQLAlchemy — justifié) | Ignorable |
| TD3 | `app/services/mfa.py` | 434 | `# noqa: E712` (comparaison `== True` SQLAlchemy — justifié) | Ignorable |
| TD4 | `frontend/src/pages/profile/ProfilePage.tsx` | 35 | `// TODO: Implement profile update API` | Frontend |
| TD5 | `frontend/src/pages/agenda/AgendaMobilePage.tsx` | 53 | `// TODO: Remplacer par un vrai appel API` | Frontend |
| TD6 | `frontend/src/api/admin.ts` | 55 | `// Audit Logs - TODO: Implement when backend endpoint is available` | Frontend |

---

## 3. FRONTEND — Gaps (19)

### Fonctionnalité

| # | Fichier | Problème | Priorité |
|---|---------|----------|----------|
| F1 | `frontend/src/pages/profile/ProfilePage.tsx:35-36` | Profile update = `console.log()` au lieu d'appel API réel. | P1 |
| F2 | `frontend/src/pages/agenda/AgendaMobilePage.tsx:53-56` | `fetch()` brut sans `apiClient` (pas d'auth, pas de tenant). | P1 |
| F3 | `frontend/src/api/admin.ts:55-61` | `getAuditLogs()` retourne `{ items: [], total: 0 }` — mock vide. Dépend de A1 côté backend. | P1 |
| F4 | `frontend/src/api/auth.ts:24-26` | `logoutAll()` appelle `POST /auth/logout-all` — endpoint backend inexistant (seul `/auth/logout` existe). | P1 |
| F5 | `frontend/src/pages/admin/AuditLogsPage.tsx:64-70` | Champ recherche `<input>` sans `onChange` handler — ne filtre rien. | P2 |
| F6 | `frontend/src/pages/admin/SessionsPage.tsx:39-46` | Structure réponse incompatible avec backend (`sessions` vs `items`, champs manquants). | P1 |
| F7 | `frontend/src/pages/dashboard/DashboardPage.tsx:47` | Navigation vers `/settings` — route inexistante (404). | P2 |
| F8 | `frontend/src/components/auth/OAuthButtons.tsx` | Composant UI existe mais backend OAuth pas implémenté. | P2 |
| F9 | `frontend/src/pages/auth/OAuthCallbackPage.tsx` | Page callback OAuth — backend OAuth non documenté. | P2 |

### UI manquante pour features backend

| # | Feature backend | UI manquante | Priorité |
|---|----------------|--------------|----------|
| F10 | Brute force (5 niveaux escalation) | Aucun message utilisateur quand compte verrouillé, captcha requis, ou délai appliqué. | P2 |
| F11 | MFA recovery codes | Flow complet mais non testé end-to-end. | P3 |

### Qualité code frontend

| # | Fichier(s) | Problème | Priorité |
|---|-----------|----------|----------|
| F12 | `errors/reporter.ts:46-70` | `console.log/warn/info` en production (5+ occurrences). | P2 |
| F13 | `hooks/useLocalStorage.ts` (7 lignes), `hooks/useAuth.ts:78`, `components/ui/FileUpload.tsx:80`, `pages/agenda/AgendaMobilePage.tsx:194` | `console.error/warn/log` au lieu de ErrorReporter. | P2 |
| F14 | `pages/dashboard/DashboardPage.tsx:37,42,52` | Typos français : `Securite`, `Gerer`, `Parametres` (accents manquants). | P3 |
| F15 | `api/client.ts:5-6` | API URL et Tenant ID hardcoded fallback (`/api/v1`, `'1'`). Pas de `.env` frontend documenté. | P2 |
| F16 | `frontend/.eslintrc.cjs` | `no-explicit-any: 'off'`, `no-unused-vars: 'off'` — règles trop permissives. | P2 |

### Tests frontend

| # | Problème | Priorité |
|---|----------|----------|
| F17 | **0 fichiers test** sur 124 fichiers TS/TSX. Vitest configuré (`package.json`), helpers présents (`test/setup.ts`, `test/test-utils.tsx`), mais aucun test écrit. | P1 |
| F18 | Error boundaries (`AppErrorBoundary`, `PageErrorBoundary`, `WidgetErrorBoundary`) sans aucun test. | P2 |
| F19 | `ForgotPasswordPage` et `ResetPasswordPage` existent mais non testés. | P2 |

---

## 4. TESTS BACKEND — Gaps de couverture (15)

### Modules sans tests unitaires dédiés

| # | Module | Lignes | Criticité | Priorité |
|---|--------|--------|-----------|----------|
| T1 | `app/core/redis.py` | 594 | **CRITIQUE** — 40+ méthodes (CSRF, tokens, sessions, brute force, MFA) avec 0 unit test dédié. | P1 |
| T2 | `app/core/security.py` | 246 | CRITIQUE — Argon2id, JWT, DUMMY_HASH. Testé indirectement seulement. | P1 |
| T3 | `app/core/rate_limiter.py` | 213 | HAUTE — Rate limiting Redis multi-scope. | P2 |
| T4 | `app/core/metrics.py` | 340 | HAUTE — Prometheus metrics. | P2 |
| T5 | `app/core/deps.py` | 111 | HAUTE — DI, get_current_user, require_role. | P2 |
| T6 | `app/core/database.py` | 54 | MOYENNE — Engine, session factory. | P3 |
| T7 | `app/core/config.py` | 69 | BASSE — Settings Pydantic. | P3 |

### Repositories et modèles sans tests

| # | Module | Lignes | Priorité |
|---|--------|--------|----------|
| T8 | `app/repositories/customer.py` | 153 | P2 |
| T9 | `app/models/user.py` | 105 | P2 |
| T10 | `app/models/mfa.py` | 69 | P3 |

### Middlewares sans tests unitaires dédiés

| # | Module | Lignes | Priorité |
|---|--------|--------|----------|
| T11 | `app/middleware/security.py` | 396 | P1 — CRITIQUE pour sécurité |
| T12 | `app/middleware/audit.py` | 372 | P2 |
| T13 | `app/middleware/metrics.py` | 228 | P3 |

### Qualité tests existants

| # | Fichier | Problème | Priorité |
|---|---------|----------|----------|
| T14 | `tests/conftest.py` | 3 fixtures mortes : `auth_token_admin` (l.267), `auth_token_tenant2` (l.279), `auth_token_admin_tenant2` (l.291). | P3 |
| T15 | `tests/security/test_multi_tenant_auth.py:157` | `pytest.skip()` conditionnel dans `test_tenant2_cannot_revoke_tenant1_session`. | P3 |

---

## 5. INFRASTRUCTURE & DEVOPS — Gaps (25)

### Dockerfile backend

| # | Problème | Priorité |
|---|----------|----------|
| I1 | Pas de non-root user — conteneur tourne en `root`. | P0 |
| I2 | Pas de `HEALTHCHECK` directive. | P1 |
| I3 | Pas de multi-stage build — dépendances compilation dans image finale. | P2 |
| I4 | `COPY . .` copie `.git`, `.venv`, tests, docs. | P2 |

### Dockerfile frontend

| # | Problème | Priorité |
|---|----------|----------|
| I5 | Pas de non-root user pour nginx. | P1 |
| I6 | Pas de `HEALTHCHECK` directive. | P2 |

### docker-compose.yml

| # | Problème | Priorité |
|---|----------|----------|
| I7 | Pas de réseau personnalisé — tous services sur bridge default. | P1 |
| I8 | `--reload` dans la commande uvicorn (ne devrait être qu'en dev). | P1 |
| I9 | Volume `.:/app` monté — code modifiable depuis l'hôte. | P2 |
| I10 | Pas de limites ressources (`mem_limit`, `cpus`). | P2 |
| I11 | Pas de healthcheck pour API et frontend. | P2 |
| I12 | `DATABASE_URL` hardcodée visible en `docker inspect`. | P2 |

### nginx.conf

| # | Problème | Priorité |
|---|----------|----------|
| I13 | **Aucun header sécurité** : X-Frame-Options, CSP, HSTS, X-Content-Type-Options, Referrer-Policy manquants. | P0 |
| I14 | Pas de gzip activé. | P2 |
| I15 | Pas de cache headers pour assets statiques. | P2 |
| I16 | Pas de timeouts (`proxy_connect_timeout`, `proxy_send_timeout`, `proxy_read_timeout`). | P2 |
| I17 | Pas de `X-Forwarded-For` / `X-Forwarded-Proto` pour reverse proxy. | P2 |

### Fichiers manquants

| # | Fichier | Priorité |
|---|---------|----------|
| I18 | `.dockerignore` — images Docker contiennent fichiers inutiles (~500MB). | P1 |
| I19 | `Makefile` — pas de commandes make standardisées. | P2 |
| I20 | `.flake8` ou config ruff — pas de linting Python configuré. | P2 |
| I21 | `mypy.ini` — pas de type-checking configuré. | P2 |
| I22 | `.pre-commit-config.yaml` — pas de hooks pre-commit. | P2 |
| I23 | `.env.example` appliqué dans CI/CD — tests CI utilisent secrets hardcodés. | P2 |

### CI/CD (.github/workflows/ci.yml)

| # | Problème | Priorité |
|---|----------|----------|
| I24 | Secrets en plaintext dans env CI (JWT_SECRET, CSRF_SECRET). Devrait être GitHub Secrets. | P1 |
| I25 | Pas de `timeout-minutes` sur jobs — peut s'exécuter indéfiniment. | P2 |

### Secrets & credentials

| # | Problème | Priorité |
|---|----------|----------|
| I26 | `.env` avec `POSTGRES_PASSWORD` en clair. Vérifier qu'il est dans `.gitignore`. | P0 |
| I27 | `alembic.ini:7` — URL DB hardcodée avec `password@localhost`. Utiliser `env.py` + `os.getenv()`. | P1 |

### pyproject.toml

| # | Problème | Priorité |
|---|----------|----------|
| I28 | Pas de config centralisée `[tool.black]`, `[tool.mypy]`, `[tool.pytest]`. | P2 |

---

## 6. BACKLOG PHASE 3+ (features futures)

Issues reportées volontairement à des phases ultérieures.

### Phase 3 — Features métier

| # | Feature | Justification report |
|---|---------|---------------------|
| PH3-1 | OAuth2 providers (Google, Microsoft) | Pas de use case métier immédiat |
| PH3-2 | Email verification flow (inscription + reset password) | Nécessite service email (SMTP/SES) |
| PH3-3 | API key management (clés API pour intégrations) | Pas de use case métier immédiat |
| PH3-4 | `database_async.py` — migration async SQLAlchemy | Performance, pas sécurité |
| PH3-5 | Pages `/settings` frontend | Route morte actuellement (F7) |
| PH3-6 | Page `/finances` frontend | Stub "Bientôt" existant |
| PH3-7 | Internationalisation (i18n) frontend | Messages hardcodés en français |
| PH3-8 | Profile update API + endpoint backend | TODO frontend (F1, TD4) |
| PH3-9 | Audit logs endpoint sécurisé (après fix A1) + frontend fonctionnel | Dépend de A1 |

### Phase 4 — Hardening & compliance

| # | Feature | Justification report |
|---|---------|---------------------|
| PH4-1 | Vault / secrets management (HashiCorp, Infisical, AWS) | ENV vars suffisent pour l'instant |
| PH4-2 | Audit signature HMAC-SHA256 (immutabilité cryptographique) | Trigger PostgreSQL suffit |
| PH4-3 | Password history (N derniers mots de passe) | Feature compliance avancée |
| PH4-4 | WebAuthn/FIDO2 | Complexité significative |
| PH4-5 | Kubernetes manifests (deployment, service, ingress, HPA) | Pas de K8s en dev |
| PH4-6 | Load testing (k6/locust) | Après stabilisation fonctionnelle |
| PH4-7 | SBOM (Software Bill of Materials) | Compliance avancée |

---

## 7. RÉSUMÉ PAR PRIORITÉ

| Priorité | Count | Catégories |
|----------|-------|------------|
| **P0** | 6 | A1, A2, A3 (audit backend) + I1, I13, I26 (infra) |
| **P1** | 19 | B1-B7 (backend) + F1-F4, F6, F17 (frontend) + T1, T2, T11 (tests) + I2, I5, I7, I8, I18, I24, I27 (infra) |
| **P2** | 39 | C1-C14 (backend) + F5, F7-F10, F12-F13, F15-F16, F18-F19 (frontend) + T3-T5, T8-T9, T12 (tests) + I3-I4, I6, I9-I12, I14-I17, I19-I23, I25, I28 (infra) |
| **P3** | 14 | D1-D8 (backend) + F11, F14 (frontend) + T6-T7, T10, T13-T15 (tests) |
| **Backlog** | 16 | PH3-1 à PH3-9 + PH4-1 à PH4-7 |

**Total : 94 items identifiés** (78 actionnables + 16 backlog)

---

## 8. ORDRE DE CORRECTION RECOMMANDÉ

### Immédiat (avant tout déploiement)

1. **A1** — Ajouter `Depends()` sur AdminUser dans audit endpoints
2. **A3** — Corriger `_singularize_entity_type` (invoices → invoice)
3. **I26** — Vérifier `.env` dans `.gitignore`, rotationner secrets si commité
4. **I1** — Ajouter non-root user dans Dockerfile backend
5. **I13** — Ajouter headers sécurité dans nginx.conf
6. **B7** — `secrets.compare_digest()` pour CSRF

### Court terme (semaine 1)

7. **A2** — Commenter ou créer les 4 modules Celery manquants
8. **B1** — Context manager pour DB sessions dans audit middleware
9. **B3** — Centraliser JWT parsing via `request.state`
10. **B5** — Compléter imports `alembic/env.py`
11. **B6** — `SELECT FOR UPDATE` sur stock
12. **I18** — Créer `.dockerignore`
13. **I24** — Migrer secrets CI vers GitHub Secrets
14. **I27** — Dynamiser URL dans `alembic.ini`
15. **F4** — Corriger `logoutAll()` (utiliser bon endpoint ou créer backend)
16. **F6** — Aligner structure réponse sessions frontend/backend

### Moyen terme (semaine 2-3)

17. **T1** — Tests unitaires `redis.py`
18. **T2** — Tests unitaires `security.py`
19. **T11** — Tests unitaires `middleware/security.py`
20. **C1-C14** — Nettoyage config, exports, patterns, duplication
21. **F17** — Écrire premiers tests frontend (composants critiques)
22. **I7-I12** — Hardening docker-compose
23. **I19-I22** — Créer fichiers config manquants (Makefile, flake8, mypy, pre-commit)

### Long terme (Phase 3+)

24. **PH3-1 à PH3-9** — Features métier
25. **PH4-1 à PH4-7** — Hardening & compliance

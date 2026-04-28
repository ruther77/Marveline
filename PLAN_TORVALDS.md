# PLAN_TORVALDS — Roadmap branche `Torvalds`

> **Dev** : Torvalds  
> **Branche** : `Torvalds` (push autorisé) ; `main` interdit  
> **Période** : 2026-04-28 → 2026-07-28 (3 mois ; 1 mois priorité ci-dessous)  
> **Périmètre** : Auth (Bloc 2) + ETL/Restaurant (Bloc 5) + Ops (Bloc 6) + Frontend (Bloc 7) + 7 hotfixes Sprint 1  
> **Volume** : 22 sprints (~115 j-h ≈ 3 mois solo)

---

## ⛔ Règles avant tout

1. **JAMAIS push sur `main`**. Cf. `CONTRIBUTING.md`.
2. **prepare(file)** obligatoire avant `Edit` Python (PreToolUse hook bloquera).
3. **Spec gagne sur intuition** : si conflit avec architecture-cible.md → spec wins (invariant I7).
4. **Zones partagées** = annonce 24h en daily : `notification.py` (B6.S1 après Page B3.S5), `customer.py` (B4.S5 PII après Page B4.S4 RFM), `permissions/scope.py` (Torvalds owner).
5. **Tests dans la même session** que le code (jamais "plus tard").

---

## Mois 1 (mai 2026) — Bloc 2 Auth + B7.S1 verticals + hotfixes Sprint 1

### Sprint 1 FIRE-DRILL — T2 relance ✅ DÉJÀ FAIT

Livré 2026-04-28 par Lead. Validation : `pytest tests/integration/test_relances.py` (22/22 passent).  
**Action Torvalds** : valider via smoke prod-like (déclencher manuellement la task + vérifier email reçu sur boîte test).

### Sprint 1 FIRE-DRILL — T3-T12 (T0+1, 1 sem max)

**Doc** : `docs/architecture-audit-2026-04-26/execution-plan/10-sprint-1-PROD-FIRE-DRILL.md`

**À livrer en parallèle des B2/B7 du début Mois 1** (priorité absolue, débloque démo Splendid 28/04 pour T11) :

| Story | Bug | Effort |
|---|---|---|
| **S1.T3** | F870 EPI-CHECKSTK-01 — vente épicerie `check_stock=True` par défaut | 0.5 j |
| **S1.T6** | F1002 AUDIT-LOGIN-EXCL-01 — audit login 401 dans middleware | 0.5 j |
| **S1.T8** | F370 STEPUP-WEBAUTHN-01 — stepup WebAuthn cassé | 0.5 j |
| **S1.T9** | F296 OAUTH-ONLY-TYPEERROR-01 — 500 + user enumeration | 0.25 j |
| **S1.T10** | F404 OAUTH-MFA-BYPASS-01 — MFA contournée via Google/MS | 1 j |
| **S1.T11** | F368 WEBAUTHN-RPID-MULTITENANT-01 — **bloque démo Splendid 28/04** | 1 j |
| **S1.T12** | F1126 METRICS-PATH-DOS-01 — DoS Prometheus via paths random | 0.25 j |

Total ~4 j-h — **livrer dans la 1ère semaine**.

### B2.S1 — Password reset + email templates (T0+1, 1.5 sem)

- **Doc** : `12-sprint-B2.S1.md`
- **Stories** : T1 password_reset_token + T2 forgot-password endpoint + T3 reset-password endpoint + T4 password policy bind dynamique + T5 audit reset + T6 cleanup PIN sync + **T7 templates email Jinja2 i18n FR (Vague 2 patch — TR-64)** : `app/templates/email/fr/_base.html.j2` + 4 templates (password_reset, mfa_setup, welcome, email_change_verify)
- **Touches** : `app/api/v1/endpoints/auth.py`, `app/services/account.py`, `app/services/auth_v2.py`, `app/templates/email/fr/` (NEW)

### B2.S2 — Tenant provisioning atomique (T0+2.5, 1.5 sem)

- **Doc** : `12-sprint-B2.S2.md`
- **Stories** : T1 `TenantService.provision()` 1 TX atomique + T2 verticals table + T3 endpoint `/admin/devup/tenants/provision` + T4 `/admin/devup/tenants/{id}/suspend` + T5 OutboxEvent `TenantProvisioned` + T6 tests E2E rollback atomic
- **Migration** : `d1e2f3a4b5c6_create_verticals_table.py` + `d1e2f3a4b5c7_provisioning_atomic_helpers.py`
- **Précondition** : Page B1.S2 RLS livré (gate)
- **Touches** : `app/services/tenant.py`, `app/api/v1/endpoints/tenant_provisioning.py` (NEW), `app/models/vertical.py` (NEW)

### B2.S3 — Auth scopes catalog + drop permission_v2 (T0+4, 2 sem)

- **Doc** : `12-sprint-B2.S3.md`
- **Stories** : T1 catalog `Scope` enum + T2 auth_vertical_scopes table + T3 `require_scope` decorator + T4 drop permission_v2 legacy + T5 6 rôles canoniques (admin/manager/staff/viewer/api/superadmin) + T6 audit scope CRUD
- **🟡 Coordination** : Page importera `Scope.X` (read-only) dans Bloc 3/4. Définir scope `PRINTER_PRINT`, `RFM_*`, `ETL_*`, etc. en début de sprint.
- **Touches** : `app/permissions/scope.py`, `app/permissions/auth_vertical_scopes.py` (NEW), `app/core/permissions.py`

### B2.S4 — OAuth provider + step-up MFA (T0+6, 2 sem)

- **Doc** : `12-sprint-B2.S4.md`
- **Stories** : T1 OAuth Google + T2 OAuth Microsoft + T3 OAuthRelinkBlocked anti-takeover (Vague 1 patch Q11=A) + T4 step-up MFA TOTP + T5 step-up WebAuthn + T6 backup codes + T7 schema_constants_coherence (binding dynamique MFAConfig.STEPUP_TTL — Vague 4 invariant CI) + T8 admin DELETE oauth-identities (Vague 1 patch Q11=A)
- **Migration** : `c4d5e6f7a8be_tenants_rp_id_frontend_url.py` (V4-P0-03 F368 + V5-P0-02 F295)

### B2.S5 — auth_factors unifié (T0+8, 2 sem)

- **Doc** : `12-sprint-B2.S5.md`
- **Stories** : T1 create auth_factors table (Q6=B) + T2 migrate MFADevice → auth_factors + T3 email_exists/sku_exists soft-delete cohérence (TR-32) + T4 drop mfa_devices legacy + T5 customer.address → Customer migration (TR-7) + T6 cleanup
- **Migration** : `d1e2f3a4b5d0_create_auth_factor_table.py` + `d1e2f3a4b5d1_migrate_mfa_devices_to_auth_factor.py` + `d1e2f3a4b5d2_drop_mfa_devices_legacy.py`

### B7.S1 — Verticals rename (T0+10, 1 sem)

- **Doc** : `17-sprint-B7.S1.md`
- **Stories** : T1 `apps` → `verticals` rename + backfill + T2 `Tenant.app_code` → `Tenant.vertical FK` + T3 frontend impact (Splendid Events tenant)
- **Migration** : `c4d5e6f7a8b9_tenants_add_vertical_brand.py` + `c4d5e6f7a8ba_backfill_tenants_vertical.py` + `c4d5e6f7a8bc_rename_apps_to_verticals.py`
- **Risque** : R3 — frontend cassera tant que B7.S2-S4 pas livrés. Procédure : feature flag `vertical_rollout=False` initial, bascule sprint par sprint.

**Mois 1 livré** : 5 sprints Bloc 2 + 1 sprint B7.S1 + 7 hotfixes.

---

## Mois 2 (juin 2026) — Bloc 5 ETL + Restaurant

### B5.S1 — Hotfixes restaurant + transfert resto/épicerie (T0+11, 2 sem)

- **Doc** : `15-sprint-B5.S1.md`
- **Stories** : T1 marmite v2 (post Sprint 1.T1) + T2 `with_for_update` valider_transfert (TR-41) + T3 cancel cascade restitution stock (TR-42) + T4 `CommandeRestaurant.payer` → `FinanceInvoice` (TR-43) + T5 `EpicerieVente.annuler_vente` credit_note (TR-44) + T6 single source of truth protéine (TR-45) + T7 workflow APPROVED→FULFILLED (TR-54) + T8 drop `_TENANT_RESTAURANT` hardcoded (TR-55) + T9 `encaisser(check_stock=True)` default (TR-58)
- **Touches** : `app/services/restaurant/`, `app/services/epicerie/`, `app/services/transfer_request.py`

### B5.S2 — ETL multi-tenant (T0+13, 2 sem)

- **Doc** : `15-sprint-B5.S2.md`
- **Stories** : T1 split référentiel ETL per-tenant (TR-39) + T2 bulk insert ETL (TR-31) + T3 cross-tenant FK validation (TR-40) + T4 catalogue prix history audit (TR-46) + T5 versioning lignes_data JSONB (TR-47) + T6 `run_etl_import(tenant_id)` arg (TR-48) + T7 idempotency (TR-49) + T8 `_global_idf` per-import context (TR-50) + T9 strict FinanceVendor validation (TR-51) + T10 `stock_alerte` default NULL (TR-52) + T11 `categorie_id ForeignKey` (TR-53) + T12 vrai `lookup_correction_history` (TR-59) + T13 drop frozenset `_FINAL_CATEGORIES` (TR-60) + T14 statut `ECHEC` ETL (TR-61)
- **Migration** : `a2b3c4d5e6f7_split_etl_referential_per_tenant.py` + 3 autres
- **Effort élevé** : 14 stories — sprint plus long, ~3 sem si nécessaire

### B5.S3 — Restaurant FSM commande + finance (T0+15, 2 sem)

- **Doc** : `15-sprint-B5.S3.md`
- **Stories** : T1 CommandeFSM (états ouverte/encaissee/annulee) + T2 LedgerEntryMixin pour resto + T3 protéine sourcing single source (cont. B5.S1.T6)

### B5.S4 — Restaurant export + reporting (T0+17, 1 sem)

- **Doc** : `15-sprint-B5.S4.md`
- **Stories** : Celery export quotidien CA + uplift reporting (cf. `tenant_settings.reservation_uplift_pct`)

### B5.S5 — Carrier integration (T0+18, 1 sem)

- **Doc** : `15-sprint-B5.S5.md`
- **Stories** : carrier rates per-vertical + delivery_zone + `categorie_id` FK catalogue
- **Migration** : `a2b3c4d5e6fa_categorie_id_fk_catalogue.py`

### B5.S6 — Catalogue ETL price history (T0+19, 1 sem)

- **Doc** : `15-sprint-B5.S6.md`
- **Stories** : `catalogue_produit_price_history` + audit overwrite prix
- **Migration** : `a2b3c4d5e6fb_catalogue_produit_price_history.py`

**Mois 2 livré** : 6 sprints Bloc 5.

---

## Mois 3 (juillet 2026) — Bloc 6 Ops + Bloc 7 Frontend

### B6.S1 — Email gateway Postmark + notification_log (T0+20, 2 sem)

- **Doc** : `16-sprint-B6.S1.md`
- **Stories** : T1 Postmark backend (TR-62, TR-63) + T2 TLS+auth + T3 refactor `Notification` SQLA 2.0 (TR-65) + **T4 `require_scope(Scope.PRINTER_PRINT)` sur /print** (Vague 4 normalisé) + T5 access_reviews certify endpoint + T6 EntityType enum + T7 wrapper EmailGateway pour relances (refonte complète post Sprint 1.T2) + **T8 `notification_log` table NEW + LoggingEmailGateway + webhook Postmark `/webhooks/postmark/delivery`** (Vague 2)
- **Migration** : `b3c4d5e6f7ae_notification_log_table.py` + `b3c4d5e6f7af_notifications_v2_account_id.py`
- **🟡 Coordination** : ce sprint refactore `notification.py` qui a été touché par Page B3.S5. **Pull origin Page** avant de toucher (et rebase).

### B6.S2 — Audit HMAC + RGPD audit (T0+22, 2 sem)

- **Doc** : `16-sprint-B6.S2.md`
- **Stories** : T1 HMAC chained audit_logs (refondu architecture-cible §6.2.4) + T2 DB triggers immutability (TR-7) + T3 audit delete_* universal (TR-36) + T4 audit dans même TX que mutation (TR-66) + T5 HMAC couvre `changes` JSON (TR-67) + T6 audit /auth/login 401 (TR-68) + T7 SENSITIVE_PATTERNS étendu (TR-69) + T8 PII encryption audit (TR-70) + T9 audit 4xx ATTEMPT_DENIED (TR-73)
- **Migration** : `b3c4d5e6f7a8_audit_logs_hmac_chain.py` + `b3c4d5e6f7a9_audit_logs_pii_encrypted.py` + `b3c4d5e6f7aa_audit_logs_drop_clear_text.py`

### B6.S3 — RGPD export + purge (T0+24, 1 sem)

- **Doc** : `16-sprint-B6.S3.md`
- **Stories** : T1 endpoint `GET /rgpd/export/me` (TR-71) + T2 Celery task purge >7y (TR-72) + T3 feature_flag_tenants table + T4 feature_flag_history
- **Gate stakeholder** : DPO valide format export AVANT (cf. RACI §7.1)

### B6.S4 — Feature flags fail-safe (T0+25, 1 sem)

- **Doc** : `16-sprint-B6.S4.md`
- **Stories** : T1 fail-safe deny by default (TR-74) + T2 hashlib.sha256 bucketing (TR-75) + T3 audit feature flag CRUD (TR-76)

### B6.S5 — Print + WireGuard async (T0+26, 1.5 sem)

- **Doc** : `16-sprint-B6.S5.md`
- **Stories** : T1 httpx.AsyncClient WG (TR-84, TR-85) + T2 circuit breaker imprimantes + T3 audit Print (TR-83) + T4 rate-limit print + T5 audit cross-tenant peer + T6 `_validate_tenant_for_print` fail-fast (TR-81 Vague 2) + T7 JWT court rotation KMS + **T8 rotation `WG_INTERNAL_API_KEY` KMS** (TR-86 Vague 4)

### B6.S6 — Observability mTLS + OTel (T0+27.5, 2 sem)

- **Doc** : `16-sprint-B6.S6.md`
- **Stories** : T1 `/metrics` mTLS (Q40=B) + T2 sanitize status page + T3 health async + T4 cardinality whitelist + T5 labels app_code+tenant_id cap + T6 OpenTelemetry (Q37=A) + T7 cache_hit_rate Gauge + **T8 OTel→Prometheus bridge `db_queries_total`/`redis_commands_total`** (TR-97 Vague 2)
- **Gate stakeholder** : budget K8s mTLS validé (cf. RACI §7.1)

### B6.S7 — RabbitMQ migration + DLQ (T0+29.5, 1 sem)

- **Doc** : `16-sprint-B6.S7.md`
- **Stories** : T1 task_routes queue loyalty (TR-77) + T2 DLQ RabbitMQ (TR-94) + T3 Beat heartbeat (TR-95)
- **Gate stakeholder** : budget RabbitMQ + maintenance window communication client

### B7.S2 — Drop brand_code Catalogue (T0+30.5, 1 sem)

- **Doc** : `17-sprint-B7.S2.md`
- **Stories** : drop `brand_code` Product/Category/Bundle/Collection (Bloc 7 Q43=B = 2 tenants distincts Splendid)

### B7.S3 — AppSelector refonte UI (T0+31.5, 1.5 sem)

- **Doc** : `17-sprint-B7.S3.md`
- **Stories** : refonte UI AppSelector + verticals navigation
- **Communication client** : ANNONCE -7j changement visuel notable

### B7.S4 — Frontend monorepo finalisation (T0+33, 1 sem)

- **Doc** : `17-sprint-B7.S4.md`
- **Stories** : 4 apps consolidées (Marveline, Restaurant, Épicerie, Splendid), white-label per-tenant (brand_logo, brand_primary_color), packages/shared cohérents

**Mois 3 livré** : 7 sprints Bloc 6 + 3 sprints Bloc 7.

---

## Synthèse 3 mois Torvalds

| Mois | Sprints | Tables nouvelles | Migrations | Tests minima |
|---|---|---|---|---|
| Mai | B2.S1-S5 + B7.S1 (6) + 7 hotfixes | verticals, auth_factors, auth_vertical_scopes, access_reviews | 8 | 60+ |
| Juin | B5.S1-S6 (6) | catalogue_produit_seed, catalogue_produit_price_history | 6 | 70+ |
| Juillet | B6.S1-S7 + B7.S2-S4 (10) | notification_log, feature_flag_*, audit_logs HMAC | 14 | 80+ |
| **Total** | **22 sprints + 7 hotfixes** | **9 tables** | **28 migrations** | **210+ tests** |

---

## Dépendances ordre topologique

```
Sprint 1.T2 (✅ done)
  ↓
Sprint 1.T3-T12 (S1 PROD FIRE-DRILL — semaine 1)
  ↓                            ↘ (parallèle dès gate Page B1.S2)
                                B2.S1 — password_reset + templates email FR
                                  ↓
                                B2.S2 — provisioning atomique (gate B1.S2 OK)
                                  ↓
                                B2.S3 — Scope catalog (🟡 Page consomme)
                                  ↓
                                B2.S4 — OAuth + step-up
                                  ↓
                                B2.S5 — auth_factors unifié
                                  ↓
                                B7.S1 — verticals rename (frontend prep)
                                  ↓
B5.S1 (gate Page B3.S2 FSM helper) → B5.S2 (gros) → B5.S3 → B5.S4 → B5.S5 → B5.S6
                                                                              ↓
B6.S1 (🟡 notification.py post Page B3.S5) → B6.S2 → B6.S3 → B6.S4
                                                                ↓
B6.S5 → B6.S6 → B6.S7 (RabbitMQ migration)
                                                                ↓
B7.S2 → B7.S3 → B7.S4
```

**Préconditions Page → Torvalds** :
- B1.S2 RLS livré (T+5 sem) → ouvre B2.S2 provisioning
- B3.S2 FSM helper livré (T+13 sem) → ouvre B5.S1 cascade restaurant
- B3.S5 EmailGateway interface livré (T+19 sem) → ouvre B6.S1 Postmark backend

**Préconditions Torvalds → Page** :
- B2.S3 catalog scopes livré → Page peut commencer Bloc 3/4 avec `Scope.X`
- B7.S1 verticals rename livré → Page peut migrer ses references `app_code` (nettoyage)

---

## Outils

- `mcp__context-engine__prepare(file_path)` avant chaque Edit Python
- `mcp__context-engine__explore(module)` pour orientation
- `mcp__context-engine__search(query)` pour grep symbolique
- `mcp__context-engine__checkpoint(notes)` pour checkpoint progrès session
- Senior protocol : `~/.claude/skills/senior-protocol`
- Backend rules : `~/.claude/skills/backend-rules`
- Frontend rules : `~/.claude/skills/frontend-rules`

---

## Communication

- Daily standup `#devup-refactor` 09:30 (15 min)
- **Annonce zone partagée** 24h avant : `notification.py` (B6.S1), `customer.py` (B4.S5), `tenant_settings` ALTERs
- **Communication client critique** :
  - 28/04 démo Splendid → bloque jusqu'à S1.T11 livré
  - Avant B6.S7 RabbitMQ : maintenance window (Lead communique)
  - Avant B7.S3 AppSelector : changement visuel (Lead communique)
- Push sur `Torvalds` à minimum 1× par jour (sauvegarde + visibilité Page)
- PR review croisée des sprints en zones partagées

---

## Si bloqué

1. Lire le sprint complet `docs/.../execution-plan/<sprint>.md`
2. Lire architecture-cible.md section correspondante
3. Si conflit code↔spec : spec gagne (I7)
4. Si > 2h bloqué : ping Lead Slack

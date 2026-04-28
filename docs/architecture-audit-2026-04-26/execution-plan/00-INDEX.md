# Execution Plan — DEVUP Architecture Refactor 2026-04-27

> **Source de vérité décisionnelle** : `../architecture-cible.md` (decision log, gelé après lock)
> **Source d'exécution équipe** : ce dossier `execution-plan/` (tickets actionnables, schemas SQL, plans rollout)

## ⚠️ STATUT ACTUEL

**Sprint 1 PROD FIRE-DRILL** : 12 bugs P0 production confirmés bloquant (cf. architecture-cible.md §5.4 B5.S1 + §6.4 B6.S1 + audits cohérence vagues 3-5 modules 02/09/12/13/27/31/35) :

### Bugs métier (Bloc 5+6)
- **F906 MARMITE-QPP-01** — Restaurant ne peut pas lancer de marmite avec recette (AttributeError 500). Champ `qte_par_portion` lu via nom inexistant.
- **F1058 RELANCE-FAKE-SENT-01** — Relances marquées `status='sent'` sans envoyer d'email (faux signal massif, trésorerie impactée).
- **F870 EPI-CHECKSTK-01** — `check_stock=False` par défaut → ventes encaissées sans stock disponible (IntegrityError 500 au lieu de 409 actionnable).
- **F1055 SOC2-AUTOSUSP-01** — `auto_suspend_uncertified` est un no-op : compliance theater (violation SOC2 §10).

### Bugs infra (Bloc 1+6)
- **F255 PROVISION-DEGRADED-AWAIT** — `provisioning.py:140,159,179,180` appellent `redis_sec.*` async sans `await` → `GET /admin/provision/degraded/status` retourne HTTP 500, mode dégradé `READ_ONLY`/`AUTH_DOWN`/`EMERGENCY_BYPASS` inopérant. Fix trivial : 4 `await`.
- **F1002 AUDIT-LOGIN-EXCLUDED** — `app/middleware/audit.py:63` `EXCLUDED_PATHS` contient `/auth/login` → tentatives échouées non auditées par middleware. Brute-force invisible. Non-conformité RGPD Art.30. Fix : retirer du EXCLUDED_PATHS + audit explicite côté endpoint avec masquage password.
- **F1126 METRICS-PATH-DOS** — `app/middleware/metrics.py:_normalize_path` retourne path original si aucun pattern match → un attaquant qui spam `/api/v1/foo/{random_uuid}` génère N séries Prometheus → OOM kill. Fix : retourner `"other"` en fallback.

### Bugs sécurité auth (Bloc 2) — vrais exploits prod
- **F47 JWT-AUDIENCE-BYPASS** — `app/core/security.py:262` : tokens sans claim `type` (ni ACCESS ni REFRESH) bypassent la vérification d'audience → cross-app escalation. Fix : raise `TokenInvalid` si `actual_type ∉ {ACCESS, REFRESH}`.
- **F370 WEBAUTHN-STEPUP-BROKEN** — `app/api/v1/endpoints/webauthn.py:85` : `device_id = getattr(current_user, '_device_id', '') or ''` → toujours vide. Clé Redis `stepup:{uid}:` ne match jamais le guard `stepup:{uid}:{device_id}` → 100% des stepup WebAuthn échouent post-vérification. Fix : injecter `X-Device-ID` header dans context.
- **F368 WEBAUTHN-RPID-HARDCODED** — `app/services/webauthn.py:22` : `RP_ID = settings.JWT_ISSUER.replace("www.", "")` = "marveline.com" hardcodé. WebAuthn cassé pour tout vertical ≠ Marveline. **Bloque démo Splendid 28/04**. Fix : `tenants.rp_id` per-tenant + lecture via context.
- **F296 OAUTH-ONLY-TYPEERROR** — `app/services/account.py:70` : `verify_password(password, account.hashed_password)` sans check None. Compte OAuth-only (`hashed_password=None`) tente login email+password → `TypeError: argument should be str, not None` → 500. Exploitable pour user enumeration. Fix : check None + comparaison timing-safe.
- **F404 OAUTH-MFA-BYPASS** — `app/api/v1/endpoints/oauth.py:296` : `mfa_verified=False` hardcodé dans `_issue_oauth_tokens`. User avec TOTP enrôlé contourne MFA en se connectant via Google/MS. Vecteur principal account takeover. Fix : check `mfa_service.is_enrolled(account_id, tenant_id)` avant émission tokens, retourner `MFARequiredResult` si True.

**STOP all feature work jusqu'à livraison Sprint 1**. Cf. `10-sprint-1-PROD-FIRE-DRILL.md`.

**Total** : 12 stories, ~7 j-h, parallélisable en 3 jours avec 4 devs (Lead, Dev1, Dev2, Dev3).

## Convention de lecture

Chaque ticket de sprint suit le format **Jira-ready** :
- **ID ticket** + sévérité (P0/P1/P2/P3) + lien friction FXXX
- **Story** : 1 ligne (forme « En tant que X, je veux Y, pour Z »)
- **Contexte technique** : citation exacte du code actuel (`fichier.py:LIGNE`)
- **Solution** : code après modification, schemas SQL, migrations Alembic
- **Fichiers à modifier** : liste exhaustive (pas « ~30 fichiers » — la liste exacte)
- **Tests** : E2E + unitaires + invariants CI à écrire
- **Definition of Done** : critères d'acceptation testables
- **Owner** : dev pressenti (cf. RACI)
- **Estimation** : jours-homme avec breakdown
- **Dépendances** : blocked_by / blocks
- **Risques** : matrice probabilité × impact + plan rollback

## Navigation

### Fondations équipe

| Doc | Rôle | Statut |
|---|---|---|
| `00-INDEX.md` | Ce fichier — navigation + statut sprints | ✅ Rédigé |
| `01-glossaire.md` | Vocabulaire DEVUP (vertical, tenant, app_code, Principal, FSM helper, Outbox…) | ✅ Rédigé |
| `02-conventions.md` | Naming, tests, git, PR review, structure code | ✅ Rédigé |
| `03-quickstart-dev.md` | Onboarding dev — par où commencer lundi matin | ✅ Rédigé |
| `04-RACI.md` | Responsable / Accountable / Consulted / Informed par sprint | ✅ Rédigé |
| `05-risk-register.md` | Matrice risques par bloc + plans mitigation | ✅ Rédigé |

### Sprints détaillés (36 sprints au total)

| Sprint | Priorité | Owner pressenti | Doc | Statut |
|---|---|---|---|---|
| **Sprint 1 PROD FIRE-DRILL** | 🔥 P0 PROD CASSÉE | Lead + Dev1 | `10-sprint-1-PROD-FIRE-DRILL.md` | ✅ Rédigé |
| B1.S1 — Hotfixes core (F01 RLS f-string→param, F02 ApiKey set_tenant_context, F05 cache_invalidate await/drop, F111 réordonnancement middlewares, F94 rate-limit INCR+EXPIRE atomic Lua, F85 SENSITIVE_FIELDS étendu KMS secrets) | P0 | Dev1 | `11-sprint-B1.S1.md` | ✅ Rédigé |
| B1.S2 — RLS PostgreSQL + tenant context | P0 | Dev1 | `11-sprint-B1.S2.md` | ✅ Rédigé |
| B1.S3 — KMS + envelope encryption + Outbox + R21 cleanup | P0 | Dev1 | `11-sprint-B1.S3.md` | ✅ Rédigé |
| B1.S4 — Stores Redis éclatés + DegradedMode + UserCompat drop + F113 | P1 | Dev1 | `11-sprint-B1.S4.md` | ✅ Rédigé |
| B1.S5 — Constants éclatées + observability + BaseSchema | P1 | Dev1 | `11-sprint-B1.S5.md` | ✅ Rédigé |
| B2.S1 — Hotfixes IAM (refresh rotation, password policy HIBP, session fingerprint, audit enrichments, rate-limit endpoints sensibles, backup codes prep) | P0 | Dev2 | `12-sprint-B2.S1.md` | ✅ Rédigé |
| B2.S2 — Provisioning atomique + table verticals + F265 backfill + F1015/F1016 prep | P0 | Dev2 | `12-sprint-B2.S2.md` | ✅ Rédigé |
| B2.S3 — RBAC unifié + auth_vertical_scopes (F329 + F407 + F408 — placebo R25 résolu, **Q9=A 6 rôles incl. api M2M + superadmin**) | P0 | Dev2 | `12-sprint-B2.S3.md` | ✅ Rédigé |
| B2.S4 — MFA enforcement + sessions cascade (F371/F372/F368/F404/F405/F406/F259/F303/F380 + **F411 OAuthRelinkBlocked Q11=A**) | P0 | Dev2 | `12-sprint-B2.S4.md` | ✅ Rédigé |
| B2.S5 — auth_factors unifié (Q6=B migration + F296 + recovery codes 96 bits NIST + **Q7=A Account.address → Customer migration**) | P0 | Dev2 | `12-sprint-B2.S5.md` | ✅ Rédigé |
| B3.S1 — Hotfixes ledger (F17 sequences PG, TR-6 charges drop, TR-8 finance/, TR-9 reference UNIQUE per-tenant, Invoice immutable service-level) | P0 | Dev1 | `13-sprint-B3.S1.md` | ✅ Rédigé |
| B3.S2 — FSM helper + DB triggers immutability (5 matrices Devis/Resa/Invoice/Deposit/Vente + 7 triggers ledgers) | P0 | Dev1 | `13-sprint-B3.S2.md` | ✅ Rédigé |
| B3.S3 — PricingEngine + tva_rate_snapshot (TR-3, TR-14, F565 cumul additif, drop fallback 0.20, table tva_rates per-country) | P0 | Dev1 | `13-sprint-B3.S3.md` | ✅ Rédigé |
| B3.S4 — Conversion Devis→Résa atomique + Cancel cascade (TR-12 Q12=A, TR-5, F675 Deposit immutable, Q14=C DepositPolicyService) | P0 | Dev1 | `13-sprint-B3.S4.md` | ✅ Rédigé |
| B3.S5 — Celery jobs + caps fidélité + EmailGateway prod (F792-F794 ledger fidélité `with_for_update` ou UPDATE...RETURNING atomique, F797 `relativedelta` mois calendaires vs timedelta(days×30), V4-P2-03 cap MAX_LOYALTY_MULTIPLIER=3 appliqué, F751 retry/DLQ sur EmailGateway, F807 dunning_orchestrator, RELANCE-FAKE-SENT-01 résolu) | P0 | Dev1 | `13-sprint-B3.S5.md` | ✅ Rédigé |
| B3.S6 — e-invoicing schema prep (Q19=A colonnes nullables Invoice, einvoicing_enabled per-tenant, EInvoicingDispatcher Protocol, drop final `app/models/finance/`) | P1 | Dev1 | `13-sprint-B3.S6.md` | ✅ Rédigé |
| **B3.S7 — Supplier + Vente fiscal + Deposit immutable** (NOUVEAU vague 6 — angles morts Phase 3 : F826 `UNIQUE(tenant_id, code)` suppliers, F827/F828 supplier_orders UNIQUE ref + CHECK status, F829 qty_received <= qty_ordered guard, F833 dédup `lines_json`/`receipt_lines`, F728 `tva_rate_snapshot NUMERIC(5,4)` sur `vente_lines`, F737 payment_method ENUM, F739 CHECK total = sum(lines), F675 deposit `amount_cents` immutable trigger, F767 evenement.reference UNIQUE, F773 `incident_sla_hours` per-tenant settings) | P1 | Dev1 | `13-sprint-B3.S7.md` | ✅ Rédigé |
| B4.S1 — Hotfixes catalogue | P0 | Dev2 | `14-sprint-B4.S1.md` | ✅ Rédigé |
| B4.S2 — StockItemFSM + view matérialisée + PMP/WAC (F641 release_n signature `reservation_id` obligatoire, F640/F642 FSM, Q13=A migration `weighted_avg_cost_cents` + trigger trg_stock_management_wac_recompute) | P0 | Dev2 | `14-sprint-B4.S2.md` | ✅ Rédigé |
| B4.S3 — Category FK + tva_rate Category (**Q23=A `Product.tva_rate_override` Numeric(5,4) NULL exception métier**) | P0 | Dev2 | `14-sprint-B4.S3.md` | ✅ Rédigé |
| B4.S4 — PricingEngine fusion + RFMService + validators (F532 stratégie cumulative vs first-match documentée et unifiée, F533 scope `pricing:read` pour /simulate vs `pricing:write`, F499 calculate_price variants pricing, **Q26=A SIRET override admin via header**, **Q27=B RFM per-tenant via tenant_settings.rfm_thresholds JSONB**) | P0 | Dev2 | `14-sprint-B4.S4.md` | ✅ Rédigé |
| B4.S5 — PII chiffrement complet (notes + **phone + address + first_name + last_name** Q24 — pas seulement `notes` ⚠️ effet placebo si limité), scope `customers:read_pii`, audit_action delete cascade, condition unifié | P1 | Dev2 | `14-sprint-B4.S5.md` | ✅ Rédigé |
| B4.S6 — CSV bulk + Bundle.check_availability | P1 | Dev2 | `14-sprint-B4.S6.md` | ✅ Rédigé |
| B5.S1 — Hotfixes multi-app | P0 | Dev3 | `15-sprint-B5.S1.md` | ✅ Rédigé |
| B5.S2 — tenant_id ETL + triggers cross-tenant (F869 UNIQUE(tenant_id, ean) sur epicerie_produits, F875 lignes_data JSONB versioning + migrator, F1110 peer_id VPN tenant binding check, **Q29=A `categorie_produit_seed` M00 91 codes + helper provisioning**) | P0 | Dev3 | `15-sprint-B5.S2.md` | ✅ Rédigé |
| B5.S3 — FSM helper appliqué multi-app + cancel cascade (F908/F909 restitution stock à annulation commande resto + REINTEGRATION_ANNULATION movement, F913 dédup ingrédients variante+recette dans `_consommer_stocks`, F872 annuler_vente VALIDEE → CreditNote + remise stock + audit) | P0 | Dev3 | `15-sprint-B5.S3.md` | ✅ Rédigé |
| B5.S4 — Celery tenant-aware + advisory lock + IdfCorpus | P0 | Dev3 | `15-sprint-B5.S4.md` | ✅ Rédigé |
| B5.S5 — categorie_id FK + drop _FINAL_CATEGORIES | P1 | Dev3 | `15-sprint-B5.S5.md` | ✅ Rédigé |
| B5.S6 — TransferRequest workflow + smart stock_alerte (F907 algo `stock_alerte = moyenne_consommation_7j × 2` au calcul ETL + backfill, F871 valider_transfert `with_for_update`, F912 conversion auto InternalTransfer) | P1 | Dev3 | `15-sprint-B5.S6.md` | ✅ Rédigé |
| B6.S1 — Hotfixes cross-cutting (F848-F851 Notification model refacto Mapped + TenantMixin + account_id, refacto Python pas seulement DDL) | P0 | Dev1 + Ops | `16-sprint-B6.S1.md` | ✅ Rédigé |
| B6.S2 — Audit refondu + HMAC chaîné + EntityType enum (F1004) + SENSITIVE_READ_PATTERNS étendu (F118/F1003) + Export RGPD Art.15 (F1015) + Purge 7 ans (F1016) + retrait /auth/login de EXCLUDED_PATHS (refonte F1002 Sprint 1 patch tactique → middleware-level avec masquage password) | P0 | Dev1 | `16-sprint-B6.S2.md` | ✅ Rédigé |
| B6.S3 — Feature flag fail-safe + history (F1031 colonne `fail_safe_value BOOLEAN NOT NULL` + politique fail-closed mfa_enabled, F1032 `hashlib.md5` → `sha256` salté tenant_id, F1033 audit changements via Outbox) | P0 | Dev1 | `16-sprint-B6.S3.md` | ✅ Rédigé |
| B6.S4 — Celery async standardisé + heartbeat | P0 | Dev1 | `16-sprint-B6.S4.md` | ✅ Rédigé |
| B6.S5 — Print + VPN audit + circuit breaker (F1091 migration `httpx.AsyncClient` + handlers VPN async, F1089-F1090 scope print + audit, F1093 circuit breaker httpx, F1104 rate-limit print, F1110 peer_id tenant guard) | P1 | Dev1 + Ops | `16-sprint-B6.S5.md` | ✅ Rédigé |
| B6.S6 — Observability mTLS + OpenTelemetry (F83/F84/F1128/F1131 labels `app_code` + tenant_id bucketisé sur métriques HTTP/rate-limit, F1123 sanitisation `/health/status` (EMERGENCY_BYPASS → "degraded"), F1125 liveness async (`await asyncio.sleep(0)`), F1126 normalize_path fallback="other" déjà fixé Sprint 1 mais consolidation + invariants CI, F1139 cache_hit_rate Gauge multi-process) | P0 | Ops | `16-sprint-B6.S6.md` | ✅ Rédigé |
| B6.S7 — Migration broker RabbitMQ | P0 | Ops + Dev1 | `16-sprint-B6.S7.md` | ✅ Rédigé |
| B7.S1 — Tenant.vertical + auth_vertical_scopes | P0 | Dev2 | `17-sprint-B7.S1.md` | ✅ Rédigé |
| B7.S2 — Drop brand_code Catalogue (Q43=B drop intégral 4 colonnes Product/Category/Bundle/Collection + is_multi_brand + middleware X-Brand-Code + migration data split intra-tenant + CI invariant) | P0 | Dev2 | `17-sprint-B7.S2.md` | ✅ Rédigé |
| B7.S3 — Refonte AppSelector frontend | P0 | Frontend | `17-sprint-B7.S3.md` | ✅ Rédigé |
| B7.S4 — Provisioning workflow tenant | P1 | Dev2 | `17-sprint-B7.S4.md` | ✅ Rédigé |

### Spec techniques foundation

| Doc | Contenu | Statut |
|---|---|---|
| `50-sql-schema.md` | `CREATE TABLE` complet — 14 nouvelles tables (verticals, auth_factors, auth_vertical_scopes, access_reviews, outbox_events, points/revenue/payment ledgers, notification_log, feature_flag_tenants, feature_flag_history, categorie_produit_seed, catalogue_produit_price_history, fsm_transitions) + ALTER `tenant_settings` (existante — §3bis Vague 8) + 20+ autres ALTER + 15+ triggers PL/pgSQL + RLS policies | ✅ Rédigé |
| `51-alembic-migrations.md` | 58 migrations ordonnées Sprint 1 → B7.S2 — détail code pour 6 critiques (RLS enable, outbox_events RLS custom NULL, tenant_settings ALTERs successifs Vague 8, backfill TVA, materialized stock_view, drop brand_code, backfill tenants.vertical) + 4-step backward-compatible pattern | ✅ Rédigé |
| `52-api-contracts.openapi.yml` | OpenAPI 3.1 — 25+ nouveaux endpoints (provision tenant, /me/export, transfer-requests workflow, /etl/imports resolve-vendor, /admin/health, access-reviews, customers/import, devis/convert, reservations/cancel, invoices/credit-note, restaurant payer/annuler, épicerie encaisser, /print mTLS) avec schémas complets | ✅ Rédigé |
| `53-tests-strategy.md` | Pyramide 70/25/5%, baseline 1782 tests (360 fails analysés par cause), plan rattrapage 8 j-h, 7 invariants codés, fixtures async (AsyncSession + Account + scopes colon), coverage gates par module, mutation testing | ✅ Rédigé |
| `54-ci-invariants.md` | 15 scripts CI : `check_endpoint_scopes.py` (AST), `check_celery_queues.py`, `check_no_finance_legacy.py`, `check_mapped_datetime.py`, `check_scope_catalog.py`, `check_no_brand_code.py`, `check_audit_action_decorator.py`, `verify_audit_chain.py` (HMAC nightly), `check_ledger_immutable_triggers.py`, `check_celery_tenant_arg.py` + 5 squelettes + intégration GitHub Actions | ✅ Rédigé |
| `55-performance-benchmarks.md` | Baseline 2026-04-25 mesurée (top 20 endpoints, top 10 SQL, ETL, frontend Vitals), SLO globaux (uptime 99.5%, latences par classe), cibles per-endpoint per-bloc, index obligatoires, gates régression CI 20% | ✅ Rédigé |
| `56-sequence-diagrams.md` | 10 diagrammes Mermaid : login + MFA + scope resolution (RBAC v3 TenantMembership), conversion Devis→Résa atomique avec Invoice Q12=A, cancel cascade, vente épicerie atomique, marmite (fix F906), ETL routing TAIYAT/METRO/EUROCIEL, outbox dispatching, réception fournisseur, provisioning DEVUP, export RGPD | ✅ Rédigé |

### Plans rollout / ops

| Doc | Contenu | Statut |
|---|---|---|
| `60-rollout-plan.md` | Feature flags par migration, % traffic progressif, séquence bascules | ✅ Rédigé |
| `61-zero-downtime-strategy.md` | Stratégie zero-downtime vs maintenance window (drop colonnes denorm, FK NOT NULL backfill, mTLS bascule, RabbitMQ drain) | ✅ Rédigé |
| `62-rollback-plans.md` | Plan rollback par migration data : criteria de fail, scripts inverse, point de non-retour | ✅ Rédigé |
| `63-observability-rollout.md` | Dashboards Grafana par sprint, alertes AlertManager, logs Loki queries | ✅ Rédigé |
| `64-rabbitmq-migration.md` | Plan détaillé migration broker Redis → RabbitMQ : déploiement parallèle, drain queues, switch broker URL, cleanup, monitoring | ✅ Rédigé |
| `65-mtls-infra.md` | Choix service mesh (Istio vs Linkerd vs nginx-ingress mTLS) + cert-manager + SPIFFE IDs + déploiement K8s | ✅ Rédigé |

### Stakeholders

| Doc | Contenu | Statut |
|---|---|---|
| `70-stakeholders-validation.md` | Validation legal/compliance (HMAC blockchain audit, RGPD Article 15 export), CFO (budget infra K8s + RabbitMQ + Postmark), DPO (PII encryption + retention 7 ans) | ✅ Rédigé |

## Workflow tickets

```
PROD FIRE-DRILL → STOP feature work → Sprint 1 → unblock prod
                                          ↓
                       Bloc 1 (Foundations) — bloque tout reste
                                          ↓
                       Bloc 2 (Identity)    — bloque Bloc 3-6
                                          ↓
              ┌──────────────────────────────────────────┐
              ↓                ↓                         ↓
        Bloc 3 (Money)   Bloc 4 (Stock)          Bloc 5 (Multi-app)
              ↓                ↓                         ↓
              └──────────────────────────────────────────┘
                                          ↓
                            Bloc 6 (Cross-cutting) ← parallèle Bloc 7
                                          ↓
                            Bloc 7 (Sémantique DEVUP)
```

## Légende statut

- 🔥 PROD CASSÉE — STOP everything
- ⏳ À rédiger — pas commencé
- 🟡 En cours — owner assigné
- ✅ Rédigé — review équipe possible
- 🔒 Validé — owner + 1 review approuvé
- 🚀 Livré — code en prod, tests verts

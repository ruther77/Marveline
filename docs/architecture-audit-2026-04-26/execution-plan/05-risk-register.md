# Risk Register — Refactor DEVUP 2026-04-27

> Inventaire complet des risques techniques et business identifiés. Mis à jour à chaque weekly bloc review. Owner du risque = Lead sauf indication contraire.

## Échelle

**Probabilité (P)** : 1 (rare, <10%) · 2 (peu probable, 10-30%) · 3 (probable, 30-60%) · 4 (très probable, 60-90%) · 5 (quasi-certain, >90%)

**Impact (I)** : 1 (négligeable) · 2 (mineur, dégradation localisée) · 3 (modéré, déradation feature) · 4 (majeur, downtime ou data loss partiel) · 5 (critique, downtime complet ou compliance breach)

**Score** : P × I (max 25). Seuils :
- 1-4 : low (acceptable)
- 5-9 : medium (mitigation requise)
- 10-15 : high (mitigation prioritaire)
- 16-25 : critical (gate bloquant)

## R1 — Bug F906 marmite production (PROD ACTUEL)

| Champ | Valeur |
|---|---|
| Bloc | Sprint 1 PROD FIRE-DRILL |
| Probabilité | 5 (quasi-certain — bug déjà actif) |
| Impact | 4 (restaurant ne peut pas lancer marmite avec recette) |
| **Score** | **20 — CRITICAL** |
| Owner | Lead + Dev1/Dev3 |
| Mitigation | Hotfix immédiat Sprint 1 (1 ligne `quantite_par_portion` → `quantite_par_batch` + formule). Tests E2E `POST /instances` avec recette. |
| Plan rollback | Si fix introduit régression → revert commit, escalade L1 dans l'heure. Rare car fix trivial. |
| Status | 🔥 ACTIF |

## R2 — Bug F1058 relances email production (PROD ACTUEL)

| Champ | Valeur |
|---|---|
| Bloc | Sprint 1 PROD FIRE-DRILL |
| Probabilité | 5 |
| Impact | 5 (clients ne reçoivent pas leurs relances → trésorerie Marveline impactée + faux signal logs massif) |
| **Score** | **25 — CRITICAL** |
| Owner | Lead + Dev1 |
| Mitigation | Hotfix avec EmailGateway minimal Sprint 1 (Postmark direct ou SMTP avec TLS). `relance.status='sent'` UNIQUEMENT après réponse 200 gateway. Idempotence via `relance.email_sent_at`. |
| Plan rollback | Feature flag `relance_email_enabled=False` permet désactiver totalement Celery task si nouveau bug. |
| Status | 🔥 ACTIF |

## R3 — Migration `Tenant.app_code` enum CHECK → UNIQUE + FK verticals

| Champ | Valeur |
|---|---|
| Bloc | B7.S1 |
| Probabilité | 3 |
| Impact | 4 (toute la stack utilise `app_code` — JWT audience, middleware, RBAC, frontend) |
| **Score** | **12 — HIGH** |
| Owner | Lead + Dev2 |
| Mitigation | Migration step-by-step : (1) ajout colonne `vertical NOT NULL` avec backfill ; (2) ajout table `verticals` ; (3) drop CHECK enum sur `app_code` ; (4) tests E2E sur les 4 tenants existants ; (5) déploiement progressif tenant-by-tenant. Cf. `61-zero-downtime-strategy.md`. |
| Plan rollback | Migration data Alembic réversible. Backup DB avant. Si JWT cassé → flag `legacy_app_code_enum=True` qui réactive l'ancien CHECK pendant fix. |
| Status | ⏳ Planifié Bloc 7 |

## R4 — Drop `brand_code` Catalogue (B7.S2)

| Champ | Valeur |
|---|---|
| Bloc | B7.S2 |
| Probabilité | 3 |
| Impact | 3 (catalogue cassé si Marveline+Splendid actuellement multi-brand intra-tenant) |
| **Score** | **9 — MEDIUM** |
| Owner | Dev2 |
| Mitigation | Audit data préalable : sont-ils 1 ou 2 tenants actuellement ? Si 1 tenant 2 brands → migration data nécessaire (clone tenant Marveline → tenant Splendid). Si déjà 2 tenants distincts → drop colonne brand_code seulement. |
| Plan rollback | Backup catalogue tenant Marveline avant drop. Restore en cas d'erreur. |
| Status | ⏳ Audit data préalable B7.S2.S0 |

## R5 — Migration broker Redis → RabbitMQ (B6.S7)

| Champ | Valeur |
|---|---|
| Bloc | B6.S7 |
| Probabilité | 4 |
| Impact | 4 (toutes les Celery tasks impactées si migration ratée) |
| **Score** | **16 — CRITICAL** |
| Owner | Ops + Dev1 |
| Mitigation | Plan détaillé `64-rabbitmq-migration.md` : (1) RabbitMQ déployé en parallèle Redis broker ; (2) workers connectent les deux brokers ; (3) drain Redis queues progressif (publishers basculent un par un) ; (4) point de non-retour quand Redis vide depuis 24h ; (5) cleanup Redis broker. Tests staging avec charge production simulée. Monitoring queue lengths Prometheus. |
| Plan rollback | Bascule env `CELERY_BROKER_URL` vers Redis pendant phases (1)-(4). Après cleanup (5), rollback nécessite re-déploiement Redis broker. |
| Status | ⏳ Planifié B6.S7 |

## R6 — Migration `/metrics` mTLS (B6.S6)

| Champ | Valeur |
|---|---|
| Bloc | B6.S6 |
| Probabilité | 3 |
| Impact | 3 (Prometheus scrape down → observabilité aveugle, mais pas impact user-facing) |
| **Score** | **9 — MEDIUM** |
| Owner | Ops |
| Mitigation | (1) Service mesh choisi (Istio recommandé pour fonctionnalités riches) déployé en staging d'abord ; (2) cert-manager configuré, certs auto-rotated ; (3) Prometheus scraper avec client cert via ServiceAccount ; (4) bascule progressive endpoint par endpoint si possible ; (5) feature flag `metrics_mtls_enabled` pour rollback. Validation budget DEVUP avant. |
| Plan rollback | Si mTLS échoue → fallback temporaire vers Q40=A (Basic+IP whitelist) en revertant la PR. Garder option A documentée. |
| Status | ⏳ Planifié B6.S6 + budget DEVUP requis |

## R7 — Drop `Product.available_quantity` (B4.S2)

| Champ | Valeur |
|---|---|
| Bloc | B4.S2 |
| Probabilité | 3 |
| Impact | 5 (stock affiché incorrect si view matérialisée pas refresh, ou code legacy lit colonne supprimée) |
| **Score** | **15 — HIGH** |
| Owner | Dev2 |
| Mitigation | Migration step-by-step : (1) créer view matérialisée `product_stock_view` en parallèle ; (2) migrer endpoints/services pour lire la view ; (3) tests E2E exhaustifs sur les 3 cas (produit avec variants, sans variants, avec stock_items) ; (4) feature flag `use_stock_view=True` activable per-tenant ; (5) après stabilisation, drop colonne `Product.available_quantity` ; (6) drop fonction `sync_available_from_variants`. Refresh debounced 5s via Redis lock. |
| Plan rollback | Si view incohérente → désactiver flag `use_stock_view`, revenir à colonne. La view est dérivée — pas de data perdue. |
| Status | ⏳ Planifié B4.S2 |

## R8 — Régression sur les 1782 tests existants

| Champ | Valeur |
|---|---|
| Bloc | Tous les blocs |
| Probabilité | 4 |
| Impact | 3 (CI rouge bloque déploiement) |
| **Score** | **12 — HIGH** |
| Owner | Lead |
| Mitigation | (1) Run full test suite avant chaque PR (CI obligatoire) ; (2) Tests d'invariant CI ajoutés (cf. `54-ci-invariants.md`) garantissent les patterns canoniques ; (3) Coverage minimum par module enforcée ; (4) Chaque PR doit faire `pytest tests/` complet vert ; (5) Plan régression spécifique aux blocs sensibles (cf. `53-tests-strategy.md`). |
| Plan rollback | CI bloque automatiquement la PR. Pas de merge possible si tests rouges. |
| Status | ⏳ Continuous |

## R9 — PII chiffrement migration data (B4.S5)

| Champ | Valeur |
|---|---|
| Bloc | B4.S5 |
| Probabilité | 2 |
| Impact | 5 (perte data PII Customer.notes, Supplier.notes si script migration buggé) |
| **Score** | **10 — HIGH** |
| Owner | Dev2 + DPO |
| Mitigation | (1) Backup DB complet avant migration ; (2) Celery task `migrate_pii_encryption_task` testée en staging d'abord ; (3) Migration step-by-step : ajouter colonne `notes_encrypted` à côté ; backfill ; switch reads ; drop ancienne ; (4) Validation DPO avant production ; (5) Rollback : restore backup ou drop colonne `notes_encrypted` (revenir clear-text). |
| Plan rollback | Backup pre-migration. Script de décryptage en cas de perte clé KMS. |
| Status | ⏳ Planifié B4.S5 |

## R10 — Audit logs HMAC chaîné (blockchain pattern, B6.S2)

| Champ | Valeur |
|---|---|
| Bloc | B6.S2 |
| Probabilité | 3 |
| Impact | 4 (perte intégrité chaîne audit = compliance SOC2 §10 cassée) |
| **Score** | **12 — HIGH** |
| Owner | Dev1 + Compliance Officer |
| Mitigation | (1) Validation Compliance avant développement (gate obligatoire) ; (2) KMS-managed key avec versioning ; (3) Job nightly `verify_audit_chain_task` parcourt et alerte AlertManager si rupture ; (4) Tests d'invariant CI : tampering détecté ; (5) Procédure documentée si rupture détectée (incident response plan). |
| Plan rollback | Audit logs append-only → pas de rollback possible si data corrompue. Mitigation = backup régulier + chain verification quotidienne. |
| Status | ⏳ Planifié B6.S2 |

## R11 — Disponibilité Postmark (Q18=A SaaS externe)

| Champ | Valeur |
|---|---|
| Bloc | B3.S5, B6.S1 |
| Probabilité | 2 |
| Impact | 3 (relances + reset password + welcome emails fail) |
| **Score** | **6 — MEDIUM** |
| Owner | Lead + Ops |
| Mitigation | (1) `EmailGateway` Protocol permet fallback `SmtpGateway` si Postmark down ; (2) Celery retry auto avec backoff ; (3) Monitoring `notification_log` table pour détecter taux échec ; (4) AlertManager si `notification_log.status='failed'` >5% en 1h. |
| Plan rollback | Feature flag `email_gateway_provider='postmark' \| 'smtp'`. Si Postmark down >24h, switch SMTP custom temporairement. |
| Status | ⏳ Planifié |

## R12 — Disponibilité KMS (envelope encryption)

| Champ | Valeur |
|---|---|
| Bloc | B1.S3, B4.S5, B6.S2 |
| Probabilité | 1 |
| Impact | 5 (KMS down = aucun decrypt PII possible, MFA TOTP cassé) |
| **Score** | **5 — MEDIUM** |
| Owner | Ops |
| Mitigation | (1) KMS HA configuré (multi-region ou multi-instance) ; (2) Cache local 5 min des KEK déchiffrées (réduit appels KMS) ; (3) Health check KMS dans `/health/ready` ; (4) Plan d'incident KMS : passage en mode dégradé READ_ONLY si KMS down >5 min. |
| Plan rollback | KMS = critical infra. Pas de rollback applicatif. Restauration KMS = priorité absolue ops. |
| Status | ⏳ Continuous monitoring |

## R13 — Performance dégradée après ajout RLS (B1.S2)

| Champ | Valeur |
|---|---|
| Bloc | B1.S2 |
| Probabilité | 3 |
| Impact | 3 (latence accrue 10-30% sur queries tenant-scoped) |
| **Score** | **9 — MEDIUM** |
| Owner | Dev1 + Lead |
| Mitigation | (1) Bench avant/après sur les top 20 queries (E2E + unit) ; (2) Index `(tenant_id, ...)` partout où nécessaire ; (3) Tests perf intégrés CI (cf. `55-performance-benchmarks.md`) avec seuils ; (4) PostgreSQL `EXPLAIN ANALYZE` sur queries critiques pour valider que RLS policy n'invalide pas les index. |
| Plan rollback | Si RLS dégrade trop : feature flag `rls_enabled=False` désactivable per-tenant, repository garde le filtre Python en backup. |
| Status | ⏳ Planifié B1.S2 |

## R14 — Effort migration `auth_factor` (B2.S5) sous-estimé

| Champ | Valeur |
|---|---|
| Bloc | B2.S5 |
| Probabilité | 4 |
| Impact | 3 (sprint déborde, retarde Bloc 3+) |
| **Score** | **12 — HIGH** |
| Owner | Dev2 |
| Mitigation | (1) Spike technique 2 jours en début sprint pour mapper exhaustivement les 3 tables source (MFADevice, WebAuthnCredential, TrustedDevice) + le champ `Account.pin_hash` ; (2) Script migration testé sur copie prod avec data réelle ; (3) Plan B : migration progressive (un type à la fois sur 2 sprints S5+S6) si trop complexe. |
| Plan rollback | Migration data Alembic avec downgrade testé. Si échec → revenir aux 3 tables (compatibilité ascendante maintenue 1 sprint). |
| Status | ⏳ Planifié B2.S5 |

## R15 — Drift entre architecture-cible.md et code réel pendant le refactor

| Champ | Valeur |
|---|---|
| Bloc | Tous |
| Probabilité | 4 |
| Impact | 2 (confusion équipe, doc obsolète) |
| **Score** | **8 — MEDIUM** |
| Owner | Lead |
| Mitigation | (1) Weekly bloc review met à jour `architecture-cible.md` avec décisions L2/L3 prises ; (2) Owner sprint cite §X.Y.Z dans la PR description ; (3) Si drift détecté → DETECT_DIVERGENCE protocol (skill `senior-protocol`) ; (4) `architecture-cible.md` est gelé sur les décisions Q1-Q45 (immuable) mais peut s'enrichir de précisions techniques. |
| Plan rollback | Pas applicable (gestion documentaire). |
| Status | ⏳ Continuous |

## R16 — Indisponibilité dev clé (vacances, démission)

| Champ | Valeur |
|---|---|
| Bloc | Tous |
| Probabilité | 3 |
| Impact | 4 (sprint bloqué si owner unique) |
| **Score** | **12 — HIGH** |
| Owner | Lead + DEVUP |
| Mitigation | (1) Pair programming pour les sprints critiques ; (2) Documentation niveau senior dev (ce dossier `execution-plan/`) permet à un nouveau de prendre le relais ; (3) Owner backup nommé pour chaque bloc dans RACI ; (4) Reviews croisées Dev1↔Dev2↔Dev3 pour partage de connaissance. |
| Plan rollback | Si owner indisponible >1 semaine : escalade Lead, réassignation sprint, communication client si retard >2 sem. |
| Status | ⏳ Continuous |

## R17 — Décalage spec produit (DEVUP) en cours de refactor

| Champ | Valeur |
|---|---|
| Bloc | Tous |
| Probabilité | 3 |
| Impact | 3 (re-travail significatif si décision produit change) |
| **Score** | **9 — MEDIUM** |
| Owner | Lead + DEVUP |
| Mitigation | (1) Bi-weekly stakeholder sync (cf. RACI §5.3) pour caler les changements business ; (2) `architecture-cible.md` Q1-Q45 verrouillés = source de vérité, changement = re-lock explicite ; (3) Décisions L4 (impact business) escaladées immédiatement, pas implémentées en silence ; (4) Si changement majeur → mini-RFC avant implémentation. |
| Plan rollback | Re-travail acceptable si décision produit change avant déploiement prod. Après déploiement, traiter comme nouveau sprint. |
| Status | ⏳ Continuous |

## R18 — Coût infra K8s + RabbitMQ + Postmark non budgétisé

| Champ | Valeur |
|---|---|
| Bloc | B6.S6, B6.S7, B3.S5 |
| Probabilité | 3 |
| Impact | 3 (DEVUP refuse → revert décisions Q40/Q42) |
| **Score** | **9 — MEDIUM** |
| Owner | DEVUP |
| Mitigation | (1) Estimation budgétaire détaillée présentée à DEVUP avant Sprint B6.S6 (cf. `70-stakeholders-validation.md`) : K8s managed (ex: GKE, EKS) ~150€/mois min, RabbitMQ managed ~30€/mois, Postmark transactional ~10€/100k emails ; (2) Alternative low-cost documentée : nginx-ingress mTLS au lieu d'Istio, RabbitMQ self-hosted Docker, SES au lieu de Postmark ; (3) Validation gate avant chaque infra payante. |
| Plan rollback | Si refus : revert décisions Q40 (mTLS → Basic+IP), Q42 (RabbitMQ → DLQ Redis), Q18 (Postmark → SMTP custom OVH). Documenter dans architecture-cible.md. |
| Status | ⏳ À valider avant B3.S5 / B6.S6 / B6.S7 |

## R19 — Cohérence données après migration multi-tenant ETL (B5.S2)

| Champ | Valeur |
|---|---|
| Bloc | B5.S2 |
| Probabilité | 3 |
| Impact | 5 (référentiel ETL cassé = ETL TAIYAT/METRO impactés = pas de catalogue alimentaire MassaCorp) |
| **Score** | **15 — HIGH** |
| Owner | Dev3 + Lead |
| Mitigation | (1) Backup complet `catalogue_produits` avant migration ; (2) Migration data testée sur staging avec snapshot prod réel ; (3) Tests E2E ETL TAIYAT importing avant et après migration (vérifier qty produits, prix, EAN) ; (4) Feature flag `etl_use_per_tenant_catalogue=False` pour rollback si incohérence ; (5) DPO consulted (data partition cross-tenant = isolation RGPD renforcée). |
| Plan rollback | Restore backup catalogue. Désactivation flag. Re-import ETL si nécessaire. |
| Status | ⏳ Planifié B5.S2 |

## R20 — Frontend monorepo refonte AppSelector (B7.S3)

| Champ | Valeur |
|---|---|
| Bloc | B7.S3 |
| Probabilité | 3 |
| Impact | 3 (UX cassée si bugs, mais frontend != prod-blocking) |
| **Score** | **9 — MEDIUM** |
| Owner | Frontend |
| Mitigation | (1) Spike UX 1 jour avant dev (validation DEVUP sur maquette) ; (2) Tests Vitest existants conservés + nouveaux pour AppSelector ; (3) Cookie SSO `devup_session` testé cross-tenant ; (4) White-label per-tenant testé sur Marveline + MassaCorp Resto + (futur) Splendid en parallèle ; (5) Feature flag `appselector_v2_enabled` pour bascule progressive. |
| Plan rollback | Frontend = bundle séparé. Rollback = redéploiement bundle précédent (pas de migration data). |
| Status | ⏳ Planifié B7.S3 |

## R22 — Sprints orphelins : artefacts Phase 3 sans assignation Phase 2

| Champ | Valeur |
|---|---|
| Bloc | Transverse (détecté audit vague 3) |
| Probabilité | 4 (les artefacts existent, mais sans owner ni date — confondus avec "fait") |
| Impact | 3 (RGPD Art.15 = obligation légale ; absence = exposition réglementaire à terme) |
| **Score** | **12 — HIGH** |
| Owner | Lead (assignment) ; Dev2 (impl. RGPD) |
| Description | Artefacts Phase 3 rédigés (séquence Mermaid, OpenAPI, schema, fixtures de test) **sans sprint d'implémentation** : F1015 export RGPD Art.15 (`/me/export`), F1016 purge audit_logs >7 ans, F02 set_tenant_context ApiKey (suppose corrigé en B1.S2 mais non listé dans son périmètre), F111 ordre middlewares (jamais mentionné dans aucun sprint). |
| Mitigation | (1) Audit cohérence vague 3 a recensé F1015/F1016 → ajouter au périmètre B6.S2 explicite (`00-INDEX.md` mis à jour 2026-04-27) ; (2) F02 + F111 ajoutés au périmètre B1.S1 (`00-INDEX.md` mis à jour) ; (3) Avant rédaction Phase 2, scan systématique : pour chaque diagramme `56-sequence-diagrams.md`, pour chaque endpoint `52-api-contracts.openapi.yml`, pour chaque table `50-sql-schema.md` → vérifier qu'une story sprint l'implémente ; (4) Convention : tout artefact Phase 3 sans tag de sprint → audit Phase 2 le rejette en review. |
| Plan rollback | N/A (risque de management, pas technique). |
| Status | 🟡 Mitigation en cours — F1015/F1016/F02/F111 réintégrés 2026-04-27 |

## R23 — Cascade FAIL-CLOSED Redis-SEC down (F16)

| Champ | Valeur |
|---|---|
| Bloc | B1.S4 |
| Probabilité | 2 (Redis-SEC tombe rarement, mais les incidents 2025 ont été observés) |
| Impact | 5 (app totalement inutilisable même pour read-only) |
| **Score** | **10 — HIGH** |
| Owner | Dev1 + Ops |
| Description | Triple cascade FAIL-CLOSED : si Redis-SEC est down, `SecurityHeadersMiddleware` (CSRF), `RateLimitMiddleware`, et `AppEnforcementMiddleware` lèvent tous une erreur → l'app ne peut plus servir aucune requête, même celles qui ne nécessitent pas Redis. La stratégie de dégradation par middleware (FAIL-OPEN vs FAIL-CLOSED) n'est pas formalisée. |
| Mitigation | (1) Documenter explicitement dans `11-sprint-B1.S4.md` la décision FAIL-OPEN/FAIL-CLOSED par middleware en mode `AUTH_DOWN` ; (2) `SecurityHeadersMiddleware` : FAIL-OPEN sur GET (lecture admise sans CSRF), FAIL-CLOSED sur POST/PUT/PATCH/DELETE ; (3) `RateLimitMiddleware` : FAIL-OPEN avec compteur in-memory dégradé (limite par-pod plutôt que cluster) ; (4) `AppEnforcementMiddleware` : FAIL-CLOSED systématique (sécurité tenant non négociable) ; (5) Test E2E `test_redis_sec_down_app_still_serves_get_requests` ; (6) Procédure runbook ops `runbook-redis-sec-incident.md`. |
| Plan rollback | Mode dégradé `EMERGENCY_BYPASS` activé manuellement par ops via CLI Redis-CACHE (pas Redis-SEC) → désactive ces 3 middlewares jusqu'à restauration. |
| Status | ⏳ Planifié B1.S4 |

## R21 — Dette tests KMS (78 tests fail, bloque Bloc 2)

| Champ | Valeur |
|---|---|
| Bloc | B2 (transverse — pré-requis B2.S1 → B2.S5) |
| Probabilité | 5 (état actuel constaté — `tech-debt-tests.md` confirme 78 fails) |
| Impact | 3 (CI rouge sur baseline → impossible de gate les sprints B2 sur tests verts. Pas de risque prod direct mais blocage organisationnel.) |
| **Score** | **15 — HIGH** |
| Owner | Dev2 (lead Bloc 2) |
| Mitigation | (1) Sprint dédié TEST-DEBT-CLEANUP (cf. 53-tests-strategy.md §3) en parallèle de Sprint 2, story TEST-DEBT-02 fixture `kms_mock` context manager wireé dans conftest (2 j-h, débloque les 78 fails d'un coup) ; (2) `pytest-asyncio` mode auto activé dans `pyproject.toml` ; (3) Coverage gate par module désactivé sur `app/core/crypto.py` jusqu'à fix puis ré-activé à 90% ; (4) Avant tout merge B2.S1 → B2.S5, exiger `pytest tests/ -k kms -q` vert. |
| Plan rollback | Tests = artefacts non-prod. Aucun rollback nécessaire si la mitigation échoue ; on garde `xfail` ciblé avec ticket de fix dans le sprint suivant. |
| Status | ⏳ À démarrer en Sprint 2 (parallèle B2.S1) |

## R24 — WebAuthn RP_ID hardcodé bloque démo Splendid Events 28/04 (V4-P0-03 F368)

| Champ | Valeur |
|---|---|
| Bloc | Sprint 1 PROD FIRE-DRILL T11 |
| Probabilité | 5 (F368 confirmé code source `webauthn.py:22`) |
| Impact | 5 (deal Splendid + sécurité MFA multi-tenant) |
| **Score** | **25 — CRITICAL** |
| Owner | Dev2 (impl WebAuthnService) + Lead (DDL tenants.rp_id + frontend_url) |
| Description | `RP_ID = settings.JWT_ISSUER.replace("www.", "")` = "marveline.com" hardcodé. WebAuthn FIDO2 lie cryptographiquement la credential au domaine. Une credential enrôlée sur Marveline ne fonctionne pas sur splendid.events. Démo Splendid 28/04 = enrôlement WebAuthn impossible sur leur domaine = blocker commercial direct. |
| Mitigation | (1) Sprint 1 T11 : DDL `tenants.rp_id VARCHAR(253)` + `tenants.frontend_url VARCHAR(512)` + backfill (Marveline → "marveline.com", autres tenants à provisioner) ; (2) Refacto `WebAuthnService` instancié avec `tenant` context — lecture `tenant.rp_id` au lieu de constante globale ; (3) Test E2E démo Splendid pré-rendez-vous : compte test sur splendid.events enrôle YubiKey + authentifie avec succès ; (4) Documentation onboarding tenant : checklist `rp_id` + `frontend_url` obligatoire au provisioning. |
| Plan rollback | Si blocker Splendid 28/04 non résolu à J-2 : reporter démo de 1 semaine OU faire la démo sur subdomain Marveline temporaire (workaround). |
| Status | 🟡 Sprint 1 T11 prévu — délai J-3 avant démo |

## R25 — B2.S3 RBAC effet placebo si F329 non corrigé en amont (V4-P0-02)

| Champ | Valeur |
|---|---|
| Bloc | B2.S3 (dépendance B1.S1 ou pré-B2) |
| Probabilité | 3 (le sprint pourrait être livré sans détecter le placebo car les tests d'intégration passent) |
| Impact | 4 (sprint majeur livré sans effet réel — perte de 2 semaines + faux sens de sécurité) |
| **Score** | **12 — HIGH** |
| Owner | Dev2 (lead B2.S3) — collaboration Dev1 (B1.S1 token.py fix) |
| Description | Sprint B2.S3 crée la table `auth_role_scopes` et migre les scopes en DB. **Mais** `app/services/token.py:49` appelle `get_role_scopes(role, db=None)` → branche fallback `ROLE_SCOPES_FALLBACK` hardcodée systématiquement → la table DB n'est jamais lue à l'émission JWT. Si F329 non corrigé en B1.S1 (pre-requis), B2.S3 livre une infra inerte. Tests d'intégration passent car ils simulent souvent le fallback. Détection en prod = jamais (hors audit forensic). |
| Mitigation | (1) Inscrire F329 dans le périmètre **explicite** de B1.S1 (déjà fait dans 00-INDEX.md) avec validation : créer un test d'invariant `check_token_creator_passes_db.py` qui AST-scan tous les call-sites de `get_role_scopes` + lève si `db is None` ; (2) DoD B2.S3 = test E2E "modifier scope DB → JWT régénéré reflète le changement (pas le fallback)" ; (3) Dépendance `blocked_by: B1.S1` explicite dans le sprint doc B2.S3. |
| Plan rollback | Si B2.S3 livré + B1.S1 oublié : ré-ouvrir B1.S1 immédiatement. |
| Status | 🟡 B1.S1 enrichi — invariant CI à créer en B1.S1 |

## R26 — B4.S5 PII partial : 4 colonnes en clair après "fin" du sprint (V5-P0-01)

| Champ | Valeur |
|---|---|
| Bloc | B4.S5 |
| Probabilité | 4 (le DDL Phase 3 actuel chiffre `notes` seul — confirmé `50-sql-schema.md:425` avant fix vague 5) |
| Impact | 4 (RGPD Art.25 privacy by design — exposition réglementaire si dump DB) |
| **Score** | **16 — CRITICAL** |
| Owner | Dev2 |
| Description | Sprint B4.S5 prévoit "PII chiffrement" mais le DDL `50-sql-schema.md` ne couvrait que `notes_encrypted`. Phase 1 (module 14) liste un périmètre PII plus large : `phone`, `address`, `first_name`, `last_name` (commerciaux y stockent typiquement numéro perso, anniversaire, allergies = données de santé RGPD). Sans extension, le sprint livre une fausse promesse RGPD. |
| Mitigation | (1) DDL §4 enrichi (vague 5 fix, déjà appliqué dans 50-sql-schema.md) : ajout `phone_encrypted`, `address_encrypted`, `first_name_encrypted`, `last_name_encrypted` + key_version pour chacun ; (2) 3 migrations Alembic correspondantes : `f1a2b3c4d5fd` add cols, `f1a2b3c4d5fe` backfill via Celery KMS, `f1a2b3c4d5ff` drop plain text ; (3) Test invariant `check_pii_columns_encrypted.py` : grep customer model — toute colonne sémantiquement PII doit avoir son pendant `_encrypted`. |
| Plan rollback | Si découverte tardive : sprint B4.S5.bis dédié rattrapage périmètre. |
| Status | 🟡 DDL étendu vague 5 (2026-04-27) — backfill à planifier |

## R27 — Modules supplier/vente_lines/deposit/evenements absents Phase 3 (vague 6)

| Champ | Valeur |
|---|---|
| Bloc | NOUVEAU sprint B3.S7 (vague 6) |
| Probabilité | 5 (confirmé absence DDL `50-sql-schema.md`) |
| Impact | 4 (4 modules métier sans constraints SQL → corruption silencieuse production) |
| **Score** | **20 — CRITICAL** |
| Owner | Dev1 (B3.S7 nouveau sprint) |
| Description | Audit cohérence vague 6 a révélé que 4 modules Phase 1 (`26-supplier`, `22-vente-directe`, `20-deposit`, `24-evenements-incidents`) ont leurs frictions P0/P1 documentées mais **aucune ligne DDL Phase 3** ne les adresse. Conséquences : (a) doublons fournisseurs silencieux (F826), (b) statuts commande corrompus acceptés (F827/F828), (c) TVA non capturée par ligne vente (F728 — non-conformité CGI L.441-3), (d) montant caution modifiable post-encaissement (F675), (e) collision référence événement (F767). |
| Mitigation | (1) Création sprint B3.S7 "Supplier + Vente fiscal + Deposit immutable" intégré au plan (`00-INDEX.md` ligne B3.S7) ; (2) DDL §16 ajouté à `50-sql-schema.md` couvrant les 4 modules ; (3) 4 migrations Alembic correspondantes (`e3f4a5b6c7d8` à `e3f4a5b6c7db`) ; (4) Tests E2E bloc 3 inclus dans B3.S7 DoD. |
| Plan rollback | N/A (ajout nouveau sprint, pas de rollback). |
| Status | 🟡 B3.S7 créé 2026-04-27 — à rédiger Phase 2 |

## Synthèse risques par sévérité

| Sévérité | Count | Risques |
|---|---|---|
| 🔥 CRITICAL (16-25) | 7 | R1 (F906), R2 (F1058), R5 (RabbitMQ migration), **R24 (Splendid F368)**, **R26 (PII partial B4.S5)**, **R27 (Modules absents B3.S7)** |
| 🟠 HIGH (10-15) | 11 | R3, R7, R8, R9, R10, R14, R16, R19, R21 (KMS test debt), R22 (sprints orphelins), R23 (cascade FAIL-CLOSED Redis-SEC), **R25 (B2.S3 placebo F329)** |
| 🟡 MEDIUM (5-9) | 9 | R4, R6, R11, R12, R13, R15, R17, R18, R20 |
| 🟢 LOW (1-4) | 0 | — |

**Action immédiate** : R1 + R2 (Sprint 1 PROD FIRE-DRILL) bloquent toute autre activité.

**Suivi** : ce risk register est revu chaque weekly bloc review. Nouveaux risques détectés ajoutés. Mitigations validées → marquer 🟢 mitigated.

# RACI — Refactor Architecture DEVUP

> **R**esponsible (réalise) · **A**ccountable (rend des comptes, 1 seul) · **C**onsulted (avis avant) · **I**nformed (notifié après)

## 1. Composition équipe pressentie

| Rôle | Profil minimum | Charge |
|---|---|---|
| **Lead Senior Backend** | 8+ ans Python, FastAPI/SQLAlchemy 2.0 expert, IAM avancé, multi-tenant, RGPD/SOC2 awareness | 100% |
| **Dev Senior Backend 1 (Dev1)** | 5+ ans, foundations + ledger + cross-cutting | 100% |
| **Dev Senior Backend 2 (Dev2)** | 5+ ans, identity + catalogue + sémantique tenant | 100% |
| **Dev Senior Backend 3 (Dev3)** | 5+ ans, multi-app verticals (épicerie/restaurant/ETL) | 100% |
| **Dev Frontend Senior** | React/TypeScript, TanStack Router/Query, design system | 50% durant Bloc 7.S3 |
| **Ops/Infra Senior** | K8s + service mesh + Postgres + RabbitMQ + cert-manager | 50% durant Bloc 6.S6/S7 |
| **Tech Lead Architecte** (= Lead) | Vision globale + arbitrages + reviews architecturaux | 100% (= Lead) |
| **Stakeholder DEVUP** (toi) | Founder, décisions produit, validations urgentes, budget | 20% |
| **Compliance/Legal Officer** | RGPD, SOC2, e-invoicing UE | Consulted ponctuel |
| **DPO (Data Protection Officer)** | RGPD, retention 7 ans, PII encryption | Consulted ponctuel |

**Note réalisme** : si l'équipe réelle = 1 lead + 1 dev + toi, le plan séquentiel pur (~63 sem) s'applique. Si 3 devs en parallèle, ~42-45 sem. Si 1 dev seul, multiplier par 1.5x → ~90 sem.

## 2. Matrice RACI globale

| Activité | Lead | Dev1 | Dev2 | Dev3 | Frontend | Ops | DEVUP (toi) | Compliance | DPO |
|---|---|---|---|---|---|---|---|---|---|
| **Décisions architecturales** | A | C | C | C | C | C | A | I | I |
| **Décisions produit (specs métier)** | C | I | I | I | I | I | **A/R** | I | I |
| **Sprint 1 PROD FIRE-DRILL** | A/R | R | R | I | I | I | I | I | I |
| **Bloc 1 Foundations** | A | R | C | C | I | I | I | I | I |
| **Bloc 2 Identity/Tenant** | A | C | R | I | I | I | C | I | I |
| **Bloc 3 Money/Ledger** | A | R | I | C | I | I | C | C | C |
| **Bloc 4 Catalogue/Stock** | A | I | R | C | I | I | C | I | C (PII) |
| **Bloc 5 Multi-app** | A | I | C | R | I | I | C | I | I |
| **Bloc 6 Cross-cutting** | A | R | I | I | I | R | C | C (audit/RGPD) | C (PII) |
| **Bloc 7 Sémantique DEVUP** | A | I | R | I | R (S3) | I | A/R | I | I |
| **Migration RabbitMQ (B6.S7)** | A | C | I | I | I | R | I | I | I |
| **Migration mTLS (B6.S6)** | A | C | I | I | I | R | C (budget) | C (audit) | I |
| **Schémas SQL + Alembic migrations** | A | R (B1,B3,B6) | R (B2,B4) | R (B5) | I | C | I | I | I |
| **API contracts OpenAPI** | A | R (B1,B3,B6) | R (B2,B4,B7) | R (B5) | C | I | I | I | I |
| **CI invariants scripts** | A/R | C | C | C | I | C | I | I | I |
| **Tests stratégie globale** | A | R | R | R | R | I | I | I | I |
| **Risk register** | A/R | C | C | C | C | C | I | C | C |
| **Glossaire/Conventions** | A/R | I | I | I | I | I | I | I | I |
| **Validation legal HMAC blockchain** | C | I | I | I | I | I | A | R | I |
| **Validation RGPD Article 15 export** | C | I | I | I | I | I | A | R | R |
| **Validation budget infra K8s+RabbitMQ+Postmark** | C | I | I | I | I | C | A/R | I | I |
| **Validation retention 7 ans audit logs** | C | I | I | I | I | I | A | C | R |
| **Onboarding nouveaux dev** | A | R | R | R | I | I | I | I | I |
| **Daily standup** | A | R | R | R | R (B7.S3) | R (B6.S6/S7) | I | I | I |
| **Weekly review Bloc** | A/R | C | C | C | C | C | C | I | I |
| **Communication client (Marveline, MassaCorp, Splendid)** | C | I | I | I | I | I | A/R | I | I |

## 3. RACI détaillé par sprint

### Sprint 1 PROD FIRE-DRILL (1 sem max — STOP TOUT)

| Story | Responsible | Accountable | Consulted | Informed |
|---|---|---|---|---|
| F906 fix marmite `qte_par_portion` | Dev1 | Lead | Dev3 (restaurant domain) | DEVUP |
| F1058 fix relance email réel (EmailGateway) | Dev1 | Lead | Dev3 (relance flow) | DEVUP |
| F870 fix `check_stock=True` default | Dev3 | Lead | Dev1 | DEVUP |
| F1055 implémenter `auto_suspend_uncertified` réel | Lead | DEVUP | Compliance | Dev1 |
| Validation prod (smoke tests, post-deploy) | Lead | Lead | Dev1 + Dev3 | DEVUP, Ops |

> **Single-R rule** : un seul **R**esponsible par story (alignement strict avec `00-INDEX.md` bandeau Sprint 1). L'ambiguïté précédente "Dev1 ou Dev3" sur F906 est tranchée → Dev1 (le code lit dans `app/services/restaurant/instance_preparation.py:118` qui est dans le périmètre Dev1 ; Dev3 reste Consulted pour le domain knowledge restaurant). Lead direct **A**ccountable pour 3/4, et **R** sur F1055 vu l'enjeu compliance SOC2.

### Bloc 1 — Foundations (Dev1 owner)

| Sprint | R | A | C | I |
|---|---|---|---|---|
| B1.S1 Hotfixes core | Dev1 | Lead | Dev2, Dev3 | Tous |
| B1.S2 RLS + tenant context | Dev1 | Lead | Lead (architecture) | Dev2, Dev3, Ops |
| B1.S3 KMS + envelope encryption | Dev1 | Lead | Compliance, DPO | Tous |
| B1.S4 Stores Redis + auth/ découpé | Dev1 | Lead | Dev2 (auth) | Tous |
| B1.S5 Constants + observability/ | Dev1 | Lead | Ops (observability) | Tous |

### Bloc 2 — Identity/Tenant (Dev2 owner)

| Sprint | R | A | C | I |
|---|---|---|---|---|
| B2.S1 Hotfixes IAM | Dev2 | Lead | Dev1 | Tous |
| B2.S2 Provisioning + table verticals | Dev2 | Lead | Lead, DEVUP | Dev1, Dev3 |
| B2.S3 RBAC unifié + auth_vertical_scopes | Dev2 | Lead | Compliance | Dev1, Dev3 |
| B2.S4 MFA enforcement + sessions cascade | Dev2 | Lead | Compliance, DPO | Dev1 |
| B2.S5 auth_factor unifié | Dev2 | Lead | Lead, DPO (migration data MFA) | Tous |

### Bloc 3 — Money/Ledger (Dev1 owner)

| Sprint | R | A | C | I |
|---|---|---|---|---|
| B3.S1 Hotfixes ledger | Dev1 | Lead | Dev2, Compliance | Tous |
| B3.S2 FSM helper + DB triggers | Dev1 | Lead | Lead (architecture pattern) | Dev2, Dev3 |
| B3.S3 PricingEngine + tva_rate_snapshot | Dev1 | Lead | Dev2 (catalogue), DEVUP (rules métier) | Dev3 |
| B3.S4 Conversion atomique + Cancel cascade | Dev1 | Lead | Dev2 (stock), DEVUP | Dev3 |
| B3.S5 Celery jobs + caps fidélité + EmailGateway | Dev1 | Lead | Ops (Celery), DEVUP | Tous |
| B3.S6 e-invoicing schema prep | Dev1 | Lead | Compliance, DEVUP | Tous |

### Bloc 4 — Catalogue/Stock (Dev2 owner)

| Sprint | R | A | C | I |
|---|---|---|---|---|
| B4.S1 Hotfixes catalogue | Dev2 | Lead | Dev3 (variants) | Tous |
| B4.S2 StockItemFSM + view matérialisée | Dev2 | Lead | Dev1 (FSM helper), Dev3 (stock épicerie) | Tous |
| B4.S3 Category FK + tva_rate Category | Dev2 | Lead | Dev3 (impact ETL Catalogue) | Tous |
| B4.S4 PricingEngine fusion + RFMService + validators | Dev2 | Lead | Dev1 (PricingEngine), DEVUP (RFM rules) | Tous |
| B4.S5 PII chiffrement + audit delete | Dev2 | Lead | DPO, Compliance | Tous |
| B4.S6 CSV bulk + Bundle.check_availability | Dev2 | Lead | DEVUP (UX bundle) | Tous |

### Bloc 5 — Multi-app verticals (Dev3 owner)

| Sprint | R | A | C | I |
|---|---|---|---|---|
| B5.S1 Hotfixes multi-app | Dev3 | Lead | Dev1, Dev2 | DEVUP, Tous |
| B5.S2 tenant_id ETL + triggers cross-tenant | Dev3 | Lead | Lead (architecture data) | Tous |
| B5.S3 FSM appliqué multi-app + cancel cascade | Dev3 | Lead | Dev1 (pattern FSM), Dev2 | Tous |
| B5.S4 Celery tenant-aware + advisory lock | Dev3 | Lead | Ops (Celery) | Dev1 |
| B5.S5 categorie_id FK + drop _FINAL_CATEGORIES | Dev3 | Lead | Dev2 (Catalogue Bloc 4) | Tous |
| B5.S6 TransferRequest workflow + smart stock_alerte | Dev3 | Lead | DEVUP (UX transfer) | Tous |

### Bloc 6 — Cross-cutting (Dev1 + Ops co-owners)

| Sprint | R | A | C | I |
|---|---|---|---|---|
| B6.S1 Hotfixes cross-cutting | Dev1 + Ops | Lead | Tous | Tous |
| B6.S2 Audit refondu + HMAC chaîné | Dev1 | Lead | Compliance, DPO | Tous |
| B6.S3 Feature flag fail-safe + history | Dev1 | Lead | Lead (kill-switch policy) | Tous |
| B6.S4 Celery async standardisé + heartbeat | Dev1 + Ops | Lead | Ops | Tous |
| B6.S5 Print + VPN audit + circuit breaker | Dev1 + Ops | Lead | Ops (WG service) | DEVUP (impact POS) |
| B6.S6 Observability mTLS + OpenTelemetry | Ops | Lead | Lead (infra K8s), DEVUP (budget) | Tous |
| B6.S7 Migration broker RabbitMQ | Ops + Dev1 | Lead | Lead (architecture broker), DEVUP (budget) | Tous |

### Bloc 7 — Sémantique DEVUP (Dev2 + Frontend co-owners)

| Sprint | R | A | C | I |
|---|---|---|---|---|
| B7.S1 Tenant.vertical + auth_vertical_scopes | Dev2 | Lead | Dev1 (Bloc 2 IAM) | Tous |
| B7.S2 Drop brand_code Catalogue | Dev2 | Lead | Dev1 (Bloc 4 catalogue) | Tous |
| B7.S3 Refonte AppSelector frontend | Frontend | Lead | DEVUP (UX), Dev2 (backend tenant API) | Tous |
| B7.S4 Provisioning workflow tenant | Dev2 | Lead | DEVUP (UX provisioning) | Tous |

## 4. Escalation matrix

### 4.1 Décisions techniques

| Niveau | Type décision | Décideur final | SLA |
|---|---|---|---|
| L1 | Choix librairie/algorithme local au sprint | Owner du sprint (Dev1/2/3) | Immédiat |
| L2 | Pattern architecture nouveau (vs FSM helper, Outbox déjà décidés) | Lead | 24h |
| L3 | Décision impactant 2+ blocs (ex: changer convention naming, drop pattern) | Lead + équipe consulted | 48h |
| L4 | Décision impactant business/produit (ex: changer comportement client) | DEVUP (toi) + Lead | 72h |
| L5 | Décision compliance/legal (ex: PII storage, retention, audit) | DEVUP + Compliance/DPO | 1 semaine |

### 4.2 Incidents production

| Sévérité | Définition | Décideur | SLA résolution |
|---|---|---|---|
| **P0 PROD CASSÉE** | Service down ou data loss | Lead immédiat | <4h |
| **P1 critique** | Feature majeure inaccessible (ex: F906 marmite, F1058 relance) | Lead (SOP fire-drill) | <24h |
| **P2 dégradation** | Feature dégradée mais workaround possible | Owner sprint concerné | <1 semaine |
| **P3 cosmétique** | Bug mineur, pas d'impact business | Triage backlog | Best effort |

### 4.3 Conflits review

Si reviewer 1 et reviewer 2 ne sont pas d'accord :
1. Discussion async sur la PR (max 24h).
2. Si non résolu → call sync 30min owner + reviewers + Lead.
3. Si toujours non résolu → Lead tranche.
4. Documenter la décision dans `architecture-cible.md` ou ADR si impact long-terme.

## 5. Communication

### 5.1 Daily standup (15 min max, 09:30 UTC)

Chaque dev répond à 3 questions :
1. Hier : qu'ai-je fini ?
2. Aujourd'hui : sur quoi je travaille ?
3. Bloqué : par qui/quoi ?

**Focus sprint en cours** : ne pas raconter du backlog ou du futur. Si bloqué → call dédié après le standup.

### 5.2 Weekly bloc review (1h, vendredi 14:00 UTC)

- Burndown bloc en cours (sprints completed vs plan)
- Démo des stories livrées (15 min max)
- Risques émergents (ajout au risk register)
- Décisions techniques L2/L3 prises pendant la semaine (info équipe)

### 5.3 Bi-weekly stakeholder sync (30 min, jeudi 16:00 UTC)

- DEVUP + Lead + Ops
- État avancement global (pourcentage par bloc)
- Risques business (budget, dates clé client, conformité)
- Décisions L4/L5 en attente

### 5.4 Channels Slack (ou équivalent)

| Channel | Usage |
|---|---|
| `#devup-eng-general` | Discussion technique générale |
| `#devup-eng-prod` | Alertes prod (PagerDuty/AlertManager intégrés) |
| `#devup-eng-pr-reviews` | Notifications PR opened/needs review |
| `#devup-eng-ci-failures` | CI rouges (action immédiate) |
| `#devup-eng-bloc-1` à `bloc-7` | Discussion par bloc (1 channel par bloc actif) |
| `#devup-eng-fire-drill` | Coordination Sprint 1 PROD (créé puis archivé) |
| `#devup-stakeholders` | DEVUP + Lead + Compliance |

## 6. Onboarding nouveau membre

Si un dev rejoint l'équipe en cours de refactor :

1. **Jour 1** : Lecture obligatoire (4h)
   - `01-glossaire.md` (vocabulaire DEVUP)
   - `02-conventions.md` (code/git/PR)
   - `architecture-cible.md` Bloc concerné (Bloc 1 d'abord, puis spécifique)
   - `00-INDEX.md` pour vue d'ensemble
2. **Jour 2-3** : Pair programming avec owner du sprint en cours.
3. **Jour 4-5** : Première PR — fix small (P3 cosmétique, friction du backlog).
4. **Semaine 2** : Story P2 du sprint courant.
5. **Semaine 3+** : Autonome, peut reviewer en peer.

**Buddy assigné** par le Lead. Buddy = répond aux questions sur Slack en <30 min ouvré.

## 7. Validation transverse

### 7.1 Stakeholder validations requises (gates obligatoires)

| Gate | Quand | Stakeholder | Action si KO |
|---|---|---|---|
| Compliance HMAC blockchain audit | Avant B6.S2 | Compliance Officer | Refactor design avec input compliance |
| RGPD Article 15 export | Avant B6.S3 | DPO | Adapter format export (CSV/JSON spec DPO) — l'endpoint `GET /rgpd/export/me` est livré en B6.S3.T1 |
| Budget infra K8s mTLS | Avant B6.S6 | DEVUP (toi) | Si refus → revenir Q40=A Basic+IP whitelist |
| Budget RabbitMQ infra | Avant B6.S7 | DEVUP (toi) | Si refus → revenir Q42=A DLQ Redis |
| Budget Postmark | Avant B3.S5 | DEVUP (toi) | Si refus → SMTP custom fallback |
| Retention 7 ans audit logs | Avant B6.S2 | DPO | Adapter durée selon DPO (max légal RGPD = 6 mois sauf preuve fiscale 10 ans) |
| Migration data multi-tenant ETL | Avant B5.S2 | DEVUP + Compliance | Plan migration validé, communication clients |

### 7.2 Communication clients (Marveline, MassaCorp, Splendid)

DEVUP (toi) communique aux clients :
- **Avant Sprint 1 FIRE-DRILL** : maintenance window pour hotfix marmite (~30 min downtime) — bug P0 PROD bloquant
- **Avant B7.S3** : refonte UI AppSelector (changement visuel notable)
- **Avant B6.S7** : RabbitMQ migration (potentiel impact tasks Celery, fenêtre maintenance)
- **Avant chaque release prod** : changelog technique simplifié

Format : email + page status DEVUP (à créer).

---

## 8. Traçabilité TR ↔ Frictions ↔ Sprint

> **Objectif** : pour chaque TR (transverse) listé en `architecture-cible.md` §2.7/3.7/4.7/5.7/6.7, identifier le sprint qui le résout. Permet :
> 1. **Audit de couverture** : aucun TR n'est laissé orphelin (CI invariant `tools/check_tr_coverage.py`).
> 2. **Code review** : un PR qui touche un fichier listé dans une friction `Fxxx` doit citer le TR-yy correspondant et le sprint.
> 3. **Reporting client** : "TR-57 marmite résolue dans Sprint 1 FIRE-DRILL" lisible sans ouvrir 5 docs.

### 8.1 Mapping Bloc 3 — FSM, devis, résa, vente (TR-1 → TR-15)

| TR | Friction(s) | Sprint résolveur | Story |
|---|---|---|---|
| TR-1 | F558, F559, F601, F604, F672, F687, F729 | **B3.S2** | T1 — FSM helper transactionnel |
| TR-2 | F559, F601, F792, F793, F794 | **B3.S3** | T1 — `FOR UPDATE` + advisory locks |
| TR-3 | F561, F698, F728 | **B4.S3** | T2 — `Category.tva_rate` + cascade resolver |
| TR-4 | F673, F685, F714, F722, F753, F805 | **B6.S2** | T1 — Audit HMAC chained |
| TR-5 | F603, F620, F687 | **B3.S4** | T2 — Cancel cascade (stock+deposit+credit_note) |
| TR-6 | F697, F700 | **B3.S5** | T3 — Invoice immutability + credit_note pattern |
| TR-7 | F715, F795 | **B6.S2** | T2 — DB triggers HMAC immutability |
| TR-8 | F715 | **B3.S5** | T1 — Cleanup `app/models/finance/` doublon |
| TR-9 | F605 | **B1.S2** | T3 — UNIQUE composite `(tenant_id, reference)` |
| TR-10 | F562, F750, F796 | **B3.S6** | T1-T3 — Celery beat expire jobs |
| TR-11 | F797 | **B3.S6** | T2 — `relativedelta(months=N)` |
| TR-12 | F558 | **B3.S2** | T2 — `reserve_stock` à conversion devis→résa |
| TR-13 | F807 | **B4.S4** | T2 — Cap multipliers fidélité |
| TR-14 | F560 | **B3.S1** | T1 — `PricingEngine` centralisé |
| TR-15 | F750 | **B3.S5** | T4 — `EmailGateway` Postmark + outbox |

### 8.2 Mapping Bloc 4 — Catalogue, stock FSM, RFM, PII (TR-16 → TR-38)

| TR | Friction(s) | Sprint résolveur | Story |
|---|---|---|---|
| TR-16 | F485, F489 | **B4.S3** | T1 — Category FK + drop `Product.category String` |
| TR-17 | F497, F498 | **B4.S3** | T3 — `product_stock_view` matérialisée |
| TR-18 | F487, F509 | **B4.S3** | T2 — `Category.tva_rate` + `Product.tva_rate_override` |
| TR-19 | F486 | **B4.S3** | T4 — `require_scope` sur `GET /products*` |
| TR-20 | F488, F514 | **B4.S3** | T5 — `brand_code` Catalogue |
| TR-21 | F530, F532 | **B3.S1** | T1 — `PricingEngine` cumul additif `÷100` unifié |
| TR-22 | F640, F642 | **B4.S2** | T1 — `StockItemFSM` matrice transitions |
| TR-23 | F641 | **B4.S2** | T2 — `release_n(reservation_id)` non-null |
| TR-24 | F644, F652 | **B4.S2** | T3 — `event_id ForeignKey(evenements.id)` |
| TR-25 | F648, F649, F771 | **B4.S2** | T4 — `Mapped[datetime]` typing fix |
| TR-26 | F454, F651, F667, F779, F786, F832, F841 | **B4.S5** | T1-T3 — PII envelope encryption KMS |
| TR-27 | F767, F826, F827 | **B1.S2** | T3 — UNIQUE composite per-tenant |
| TR-28 | F829 | **B4.S2** | T5 — CHECK constraint réception |
| TR-29 | F830 | **B4.S2** | T6 — Auto-sync stock réception |
| TR-30 | F443 | **B4.S4** | T1 — `RFMService` central |
| TR-31 | F446 | **B5.S2** | T2 — Bulk insert ETL (1 TX/batch) |
| TR-32 | F447, F501 | **B2.S5** | T3 — `email_exists`/`sku_exists` cohérence soft-delete |
| TR-33 | F496 | **B4.S3** | T6 — `Category.requires_advance_booking_days` |
| TR-34 | F500, F510 | **B4.S3** | T7 — `Bundle.check_availability(qty)` + `bundle_unit_price_cents` |
| TR-35 | F493, F494 | **B4.S3** | T8 — Cycle prevention + depth max Category |
| TR-36 | F456, F522, F541, F774, F835 | **B6.S2** | T3 — Audit delete_* universal |
| TR-37 | F495, F650 | **B4.S3** | T9 — Vocabulaire unifié `condition` enum |
| TR-38 | F442, F480 | **B3.S5** | T4 — Convergence email vers `EmailGateway` |

### 8.3 Mapping Bloc 5 — ETL, restaurant, transferts (TR-39 → TR-61)

| TR | Friction(s) | Sprint résolveur | Story |
|---|---|---|---|
| TR-39 | F874, F957, F959, F962 | **B5.S2** | T1 — `tenant_id` sur catalogue ETL + correction history |
| TR-40 | F924, F925, F965 | **B5.S2** | T3 — Validation FK cross-tenant |
| TR-41 | F871 | **B5.S1** | T2 — `with_for_update` sur `valider_transfert` |
| TR-42 | F908, F909 | **B5.S1** | T3 — Cancel cascade restitution stock resto+épicerie |
| TR-43 | F910 | **B5.S1** | T4 — `CommandeRestaurant.payer` → `FinanceInvoice` |
| TR-44 | F872 | **B5.S1** | T5 — `EpicerieVente.annuler_vente` génère credit_note |
| TR-45 | F913 | **B5.S1** | T6 — Single source of truth protéine recette |
| TR-46 | F874, F962, F977 | **B5.S2** | T4 — `CatalogueProduitPriceHistory` + audit overwrite |
| TR-47 | F875, F966 | **B5.S2** | T5 — Versionning `lignes_data` schema |
| TR-48 | F960 | **B5.S2** | T6 — `run_etl_import(tenant_id)` arg explicite |
| TR-49 | F964 | **B5.S2** | T7 — Idempotency `run_etl_import` |
| TR-50 | F967 | **B5.S2** | T8 — `_global_idf` per-import context |
| TR-51 | F980 | **B5.S2** | T9 — Validation strict `FinanceVendor` |
| TR-52 | F907 | **B5.S2** | T10 — `stock_alerte` default = NULL + UI gating |
| TR-53 | F956 | **B5.S2** | T11 — `categorie_id ForeignKey(categories_produit_seed.id)` |
| TR-54 | F923 | **B5.S1** | T7 — Workflow `APPROVED → FULFILLED` complet |
| TR-55 | F944, F945 | **B5.S1** | T8 — Drop `_TENANT_RESTAURANT` hardcoded |
| TR-56 | F891, F927, F958 | **B4.S3** | T2 — Continuation TR-18 (cascade `Category.tva_rate`) |
| TR-57 | F906 (MARMITE-QPP-01) | **Sprint 1 FIRE-DRILL** | T1 — Fix `quantite_par_portion` AttributeError (P0 PROD bloquante, livré avant tout B-feature) |
| TR-58 | F870 | **B5.S1** | T9 — `encaisser(check_stock=True)` default |
| TR-59 | F976 | **B5.S2** | T12 — Vrai `lookup_correction_history` Layer 0 |
| TR-60 | F987 | **B5.S2** | T13 — Drop frozenset, lecture DB `categories_produit_seed` |
| TR-61 | F986 | **B5.S2** | T14 — Statut `ECHEC` si 100% lignes en erreur |

### 8.4 Mapping Bloc 6 — Email, audit, RGPD, observability, infra (TR-62 → TR-97)

| TR | Friction(s) | Sprint résolveur | Story |
|---|---|---|---|
| TR-62 | F848 (+ F442, F294, F614, F1058) | **B3.S5** + **B6.S1** | B3.S5.T4 EmailGateway async + B6.S1.T1 Postmark |
| TR-63 | F849 | **B6.S1** | T2 — TLS+auth + Postmark prod |
| TR-64 | F851, F867 | **B2.S1** | T7 — Templates Jinja2 i18n FR (Vague 2 Patch 3) |
| TR-65 | F850 | **B6.S1** | T3 — Refactor `Notification` SQLA 2.0 + Mixins |
| TR-66 | F1000, F1005 | **B6.S2** | T4 — Audit dans même TX que mutation |
| TR-67 | F1001 | **B6.S2** | T5 — HMAC couvre `changes` JSON canonical |
| TR-68 | F1002 | **B6.S2** | T6 — Audit `/auth/login` 401 dans middleware |
| TR-69 | F1003 | **B6.S2** | T7 — `SENSITIVE_PATTERNS` étendu (resa+MFA+devis+fidélité+sessions) |
| TR-70 | F1007, F1008 | **B6.S2** | T8 — Encryption PII dans audit (KMS envelope) |
| TR-71 | F1015 | **B6.S3** | T1 — Endpoint `GET /rgpd/export/me` |
| TR-72 | F1016 | **B6.S3** | T2 — Celery task purge audit >7 ans |
| TR-73 | F1019 | **B6.S2** | T9 — Audit 4xx `ATTEMPT_DENIED` |
| TR-74 | F1031 | **B6.S4** | T1 — Feature flag fail-safe **deny by default** |
| TR-75 | F1032 | **B6.S4** | T2 — `hashlib.sha256` bucketing |
| TR-76 | F1033 | **B6.S4** | T3 — Audit log feature flag CRUD |
| TR-77 | F1053 | **B6.S7** | T1 — `task_routes` queue `loyalty` (RabbitMQ migration) |
| TR-78 | F1054 | **B6.S5** | T1 — Unification async DB sessions Celery |
| TR-79 | F1055 | **B6.S5** | T2 — Implémentation `auto_suspend_uncertified` réelle |
| TR-80 | F1058 (RELANCE-FAKE-SENT-01) | **Sprint 1 FIRE-DRILL** | T2 — `EmailGateway` minimal avant `status='sent'` (P0 PROD trésorerie). Refonte complète Postmark = B6.S1. |
| TR-81 | F1059 | **B6.S5** | T6 — `_validate_tenant_for_print` fail-fast (Vague 2 Patch 4) |
| TR-82 | F1089 | **B6.S1** | T4 — `require_scope(Scope.PRINTER_PRINT)` sur `/print/*` |
| TR-83 | F1090 | **B6.S5** | T3 — Audit log Print enqueue + result |
| TR-84 | F1091 | **B6.S5** | T3 — `httpx.AsyncClient` WireGuard |
| TR-85 | F1092 | **B6.S5** | T4 — Connection pooling singleton |
| TR-86 | F1094 | **B6.S5** | T8 (NEW) — Rotation `WG_INTERNAL_API_KEY` via KMS + audit. **Note** : full mTLS WG hors scope Q40=B (qui couvre uniquement `/metrics`) — différé post-K8s service mesh. |
| TR-87 | F1122 | **B6.S6** | T1 — `/metrics` mTLS pur (Q40=B) |
| TR-88 | F1123 | **B6.S6** | T2 — Sanitize `/health/status` |
| TR-89 | F1124 | **B6.S6** | T3 — Health async DB |
| TR-90 | F1125 | **B6.S6** | T3 — `await asyncio.sleep(0)` yield test |
| TR-91 | F1126 | **B6.S6** | T4 — Cardinality whitelist + `'other'` fallback |
| TR-92 | F1128, F1131 | **B6.S6** | T5 — Labels `app_code` + `tenant_id` cap top 100 |
| TR-93 | F1133 | **B1.S4** | T2 — Cache LRU TTL 5s `DegradedModeMiddleware` (Vague 2 Patch 6) |
| TR-94 | F1068 | **B6.S7** | T2 — DLQ RabbitMQ |
| TR-95 | F1070 | **B6.S7** | T3 — Beat heartbeat + alerte |
| TR-96 | F1138 | **B6.S6** | T6 — OpenTelemetry tracing 5 libs (Q37=A) |
| TR-97 | F1127, F1141 | **B6.S6** | T8 — Adapter OTel→Prometheus `db_queries_total`/`redis_commands_total` (Vague 2 Patch 7) |

### 8.5 Invariant CI — Couverture TR

```python
# tools/check_tr_coverage.py
"""
Échoue le build si :
  - un TR-yy listé dans architecture-cible.md n'a aucune ligne dans 04-RACI.md §8
  - une ligne §8 référence un sprint qui n'existe pas
  - un sprint référencé en §8 n'existe pas dans execution-plan/
"""
import re, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGET = ROOT / "docs/architecture-audit-2026-04-26/architecture-cible.md"
RACI = ROOT / "docs/architecture-audit-2026-04-26/execution-plan/04-RACI.md"
PLAN = ROOT / "docs/architecture-audit-2026-04-26/execution-plan"

declared_trs = set(re.findall(r"\bTR-(\d+)\b", TARGET.read_text()))
covered_trs = set(re.findall(r"^\| TR-(\d+) \|", RACI.read_text(), flags=re.MULTILINE))
referenced_sprints = set(re.findall(r"\*\*(B\d\.S\d)\*\*", RACI.read_text()))
existing_sprints = {f.stem.split("-sprint-")[1] for f in PLAN.glob("*-sprint-*.md")}

missing = declared_trs - covered_trs
ghost_sprints = referenced_sprints - existing_sprints

if missing:
    print(f"FAIL: TRs sans mapping en §8 : {sorted(int(x) for x in missing)}")
if ghost_sprints:
    print(f"FAIL: Sprints inexistants référencés : {sorted(ghost_sprints)}")

sys.exit(1 if (missing or ghost_sprints) else 0)
```

> **Hook CI** : exécuté via `make check-traceability` dans `.github/workflows/ci.yml` avant tout merge sur `main`. Une PR qui ajoute un TR à l'architecture-cible doit également ajouter une ligne en §8.

### 8.6 Règle d'évolution

- **Ajout TR** : ouvrir un PR qui (1) ajoute la ligne TR-xx dans architecture-cible.md, (2) ajoute la ligne dans le sous-tableau §8.x correspondant, (3) ajoute/référence le Sprint résolveur. Le CI invariant §8.5 bloque sinon.
- **Drop TR** : retirer la ligne en architecture-cible.md ET en §8 dans le même PR. Si le sprint correspondant a déjà été livré, indiquer "Résolu" en marge.
- **Re-mapping** : si un TR est déplacé d'un sprint à un autre (re-priorisation), update §8 + propager à `60-rollout-plan.md` dans le même PR.

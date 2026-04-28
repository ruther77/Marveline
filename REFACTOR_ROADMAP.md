# REFACTOR_ROADMAP — Vue globale 3 mois

> **Période** : 2026-04-28 → 2026-07-28
> **Cible** : 36 sprints + 12 hotfixes Sprint 1 PROD FIRE-DRILL
> **Devs** : Page (branche `Page`) + Torvalds (branche `Torvalds`)
> **Spec source** : `docs/architecture-audit-2026-04-26/architecture-cible.md` (Q1-Q45 verrouillés)
> **Plan détaillé** : `docs/architecture-audit-2026-04-26/execution-plan/`

---

## Décisions verrouillées (Q1-Q45)

Source : `architecture-cible.md` §2.6, 3.6, 4.6, 5.6, 6.6, 7.0bis.

**Ne pas remettre en question pendant la refonte.** Si une décision Q-X semble divergente du code à écrire : la **spec gagne** (invariant I7 du senior protocol).

---

## Découpage haut-niveau

```
T+0 ──────── Sprint 1 PROD FIRE-DRILL (1 sem) ──────── T+1
                            ↓
            ┌───────────────┴────────────────┐
            ↓                                ↓
    Branche Page (3 mois)            Branche Torvalds (3 mois)
    Bloc 1 → 3 → 4                   Bloc 2 // 5 // 6 // 7
```

**Sprint 1 FIRE-DRILL** : à livrer **avant** tout B-feature. 12 bugs P0 — 4 métier + 3 infra + 5 sécu.
- T1 marmite (✅ fait 2026-04-28) — Page
- T2 relance (✅ fait 2026-04-28) — Torvalds (livré conjointement par Lead)
- T3-T12 : à livrer collectivement avant ouverture Bloc 1/2

---

## Roadmap Page (3 mois)

| Mois | Bloc | Sprints | Critère gate |
|---|---|---|---|
| **Mois 1** (mai) | Bloc 1 Foundation | B1.S1 → B1.S5 (5 sprints) | RLS actif sur 80 tables, audit HMAC chaîné, outbox dispatcher, DegradedMode cache |
| **Mois 2** (juin) | Bloc 3 Money | B3.S1 → B3.S7 (7 sprints) | PricingEngine unifié, FSM devis/résa/vente/invoice, EmailGateway, e-invoicing prep |
| **Mois 3** (juillet) | Bloc 4 Catalog | B4.S1 → B4.S6 (6 sprints) | Category FK + tva_rate cascade, StockItemFSM, RFM per-tenant, PII coordination avec Torvalds |

**Total** : 18 sprints + 1 hotfix Sprint 1.T1.

→ Détail : `PLAN_PAGE.md`

---

## Roadmap Torvalds (3 mois)

| Mois | Bloc | Sprints | Critère gate |
|---|---|---|---|
| **Mois 1** (mai) | Bloc 2 Auth + B7.S1 | B2.S1 → B2.S5 + B7.S1 (6 sprints) | Provisioning multi-tenant, scopes catalog, MFA unifié auth_factors, OAuth, verticals rename |
| **Mois 2** (juin) | Bloc 5 ETL/Restaurant | B5.S1 → B5.S6 (6 sprints) | Multi-tenant ETL, transferts cascade, marmite v2, restaurant↔épicerie isolation |
| **Mois 3** (juillet) | Bloc 6 Ops + Bloc 7 Frontend | B6.S1 → B6.S7 + B7.S2 → B7.S4 (10 sprints) | Audit RGPD + observability mTLS + RabbitMQ + AppSelector + monorepo |

**Total** : 22 sprints + hotfixes Sprint 1.T2-T12 partagés.

→ Détail : `PLAN_TORVALDS.md`

---

## Gates de synchronisation

| T+ | Gate | Page | Torvalds | Action commune |
|---|---|---|---|---|
| T+1 sem | **Sprint 1 FIRE-DRILL livré** | T1 marmite | T2-T12 | Lead valide, déploiement prod hotfix |
| T+2 sem | **B1.S1 + B2.S1 livrés** | RLS prêt | Auth backend prêt | Page débloque Torvalds (RLS = précondition Bloc 2) |
| T+5 sem | **B1 complet + B2 complet + B7.S1** | DegradedMode + outbox actifs | provisioning + verticals rename | Mid-month review : ajustement charge |
| T+7 sem | **B3 démarré + B5 démarré** | Money en cours | ETL en cours | Coordination zone `notification.py` (Page tape avant Torvalds) |
| T+9 sem | **Mid-point review** | B3 70% | B5 80% | Re-priorisation roadmap, ajustement Bloc 4↔5↔6 |
| T+11 sem | **B4 démarré + B6 démarré** | Catalog en cours | Audit/RGPD en cours | Coordination zone `customer.py` (Page B4.S4 RFM **avant** Torvalds B4.S5 PII) |
| T+13 sem | **Refonte complète** | B4 livré | B6 + B7 livrés | Lead merge Page + Torvalds dans `main` |

---

## Risques majeurs (cf. `05-risk-register.md`)

| Risque | Impact | Mitigation |
|---|---|---|
| R3 Migration Tenant.app_code → vertical | Tous endpoints frontend cassent | Backfill `vertical` AVANT drop `app_code`. Frontend Torvalds adapte juste après. |
| R5 RabbitMQ broker migration | Tasks Celery perdues mid-migration | Déploiement RabbitMQ parallèle Redis broker. Drain Redis queues. Switch progressif. |
| R8 Régression sur 1782 tests | Couverture < 80% bloque CI | Sprint dédié Page T0 si nécessaire (cf. `tech-debt-tests.md` 360 fails). |
| R9 PII migration data B4.S5 | KMS down → toutes ops bloquées | KMS multi-region failover + circuit breaker + cache 1h. |
| R13 Performance dégradée RLS | Latence requête × 2 | Benchmark Page B1.S2.T5 ; rollback feature flag si > 50% dégradation. |
| R16 Indisponibilité dev | Sprint bloqué | Pair coverage : chaque dev review l'autre, Lead = backup. |
| R17 Spec produit DEVUP change | Décisions Q-X invalidées | Spec **gel à T+0**. Toute évolution → ticket "post-refactor". |

---

## Métriques de succès finale

À mesurer T+13 sem (fin refonte) :

| Métrique | Cible | Mesure |
|---|---|---|
| Tests verts | ≥ 95% (1700/1782) | `pytest tests/ -v` |
| RLS coverage | 100% tables tenant-scoped (~80) | `tools/check_rls_enabled_on_tenant_tables.py` |
| Endpoints sans `require_scope` | 0 (hors `/health`, `/metrics`, `/auth/*` public) | `tools/check_endpoint_scopes.py` |
| Bugs P0 ouverts | 0 (12 fixés au Sprint 1) | MEMORY.md bugs section |
| Frictions résolues TR-1 → TR-97 | 95+ | `tools/check_tr_coverage.py` |
| Latency p95 endpoints critiques | ≤ baseline 2026-04-28 | Benchmark perf doc 55-performance-benchmarks.md |
| Conventions monorepo frontend | 4 apps consolidées | Visual review |
| Multi-tenant Splendid Events ready | Démo-able | Sprint 1.T11 + Bloc 7 |

---

## Communication clients (Marveline / MassaCorp / Splendid)

| Date cible | Annonce | Owner |
|---|---|---|
| 2026-04-28 | Hotfix marmite + relance déployés | Lead |
| 2026-04-30 | Communiqué refonte 3 mois (impact 0 — backward compat) | Lead |
| 2026-06-01 | Maintenance window B6.S7 RabbitMQ (~30 min) | Torvalds |
| 2026-07-15 | Avant-refonte UI AppSelector | Torvalds |
| 2026-07-28 | Refonte livrée + changelog technique simplifié | Lead |

---

## Liens rapides

- [CONTRIBUTING.md](./CONTRIBUTING.md) — Workflow + règles main intouchable
- [ZONES.md](./ZONES.md) — Partition fichiers par dev
- `docs/architecture-audit-2026-04-26/architecture-cible.md` — Spec Q1-Q45
- `docs/architecture-audit-2026-04-26/execution-plan/00-INDEX.md` — Index 60+ docs plan
- `docs/architecture-audit-2026-04-26/execution-plan/04-RACI.md` — Mapping TR ↔ Sprint
- `docs/architecture-audit-2026-04-26/execution-plan/05-risk-register.md` — 27 risques
- `docs/architecture-audit-2026-04-26/execution-plan/55-performance-benchmarks.md` — Baseline perf

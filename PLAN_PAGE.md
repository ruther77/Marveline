# PLAN_PAGE — Roadmap branche `Page`

> **Dev** : Page  
> **Branche** : `Page` (push autorisé) ; `main` interdit  
> **Période** : 2026-04-28 → 2026-07-28 (3 mois ; 1 mois priorité ci-dessous)  
> **Périmètre** : Foundation (Bloc 1) + Money (Bloc 3) + Catalog (Bloc 4) + 1 hotfix Sprint 1  
> **Volume** : 18 sprints (~110 j-h ≈ 3 mois solo)

---

## ⛔ Règles avant tout

1. **JAMAIS push sur `main`**. Cf. `CONTRIBUTING.md`.
2. **prepare(file)** obligatoire avant `Edit` Python (PreToolUse hook bloquera).
3. **Spec gagne sur intuition** : si conflit avec architecture-cible.md → spec wins (invariant I7).
4. **Zones partagées** = annonce 24h en daily : `notification.py` (B3.S5), `customer.py` (B4.S4 RFM), `tenant_settings` ALTERs (B4.S4, B4.S5).
5. **Tests dans la même session** que le code (jamais "plus tard").

---

## Mois 1 (mai 2026) — Bloc 1 Foundation + hotfix S1.T1

### Sprint 1 FIRE-DRILL — T1 marmite ✅ DÉJÀ FAIT

Livré 2026-04-28 par Lead. Validation : `pytest tests/integration/test_relances.py`.  
**Action Page** : valider via smoke prod-like + test E2E `POST /instances` avec recette (cf. plan §188-410 de `10-sprint-1-PROD-FIRE-DRILL.md`).

### B1.S1 — Foundation security (T0+1, 2 sem)

- **Doc** : `docs/architecture-audit-2026-04-26/execution-plan/11-sprint-B1.S1.md`
- **Stories** : T1 paramétrage RLS (F01) + T2 ApiKey set_tenant_context (F02) + T3 audit HMAC base + T4 access_reviews seed
- **Migration** : `c1d2e3f4a5b5_create_pgsql_helpers.py` (helper `fn_set_updated_at`) + `c1d2e3f4a5b6_setup_audit_hmac_key_versioning.py`
- **Critère** : `tools/check_rls_enabled_on_tenant_tables.py` infrastructure prête
- **Touches** : `app/core/database.py`, `app/core/deps.py`, `app/services/api_key.py`, `app/services/audit.py`
- **Spec citation obligatoire** : architecture-cible.md §1.2.1 et §1.2.4

### B1.S2 — RLS PostgreSQL ~80 tables (T0+3, 2 sem)

- **Doc** : `11-sprint-B1.S2.md`
- **Stories** : T1 helper `tenant_context()` + T2 migration RLS enable + policies + T3 outbox RLS NULL custom + T4 tests E2E cross-tenant + T5 step-by-step pré-prod
- **Migration** : `c1d2e3f4a5b7_enable_rls_tenant_tables.py` + `c1d2e3f4a5ba_outbox_rls_null_tenant.py` + `c1d2e3f4a5bb_enable_rls_on_tenant_settings.py`
- **Critère gate B → débloque Bloc 2** : RLS testée en pré-prod, FORCE RLS bascule planifiée
- **Touches** : `app/core/database.py`, ~80 tables (DDL via migration), tests cross-tenant
- **Annonce daily Torvalds** : "B1.S2 livré → tu peux ouvrir Bloc 2"

### B1.S3 — Outbox pattern (T0+5, 2 sem)

- **Doc** : `11-sprint-B1.S3.md`
- **Stories** : T1 modèle OutboxEvent + T2 EncryptedField TypeDecorator KMS + T3 worker dispatcher Celery + T4 tests E2E mutation→event→audit
- **Table** : `outbox_events` (cf. fix Vague 1 : `outbox` → `outbox_events`)
- **Queue Celery** : `outbox` (dédiée, cf. 55-perf §6.3)
- **Touches** : `app/services/outbox.py` (NEW), `app/tasks/outbox.py` (NEW), `app/core/encrypted_field.py` (NEW)

### B1.S4 — DegradedMode + 3 Redis stores (T0+7, 2 sem)

- **Doc** : `11-sprint-B1.S4.md`
- **Stories** : T1 3 Redis stores split + **T2 DegradedModeMiddleware avec cache LRU TTL 5s** (TR-93 Vague 2) + T3 drop UserCompat legacy + T4 rate-limit namespace tenant
- **Endpoint admin** : `POST /admin/degraded/set-level` (invalide cache)
- **Touches** : `app/core/redis.py`, `app/middleware/degraded_mode.py` (NEW), `app/api/v1/endpoints/admin.py`

### B1.S5 — Constants split + cleanup loyalty (T0+9, 1 sem)

- **Doc** : `11-sprint-B1.S5.md`
- **Stories** : split `app/constants/` par domaine + cleanup constants loyalty centralisées (Bloc 1 §1.2.5)

**Mois 1 livré** : 5 sprints Bloc 1 + 1 hotfix.

---

## Mois 2 (juin 2026) — Bloc 3 Money

### B3.S1 — PricingEngine centralisé (T0+10, 1.5 sem)

- **Doc** : `13-sprint-B3.S1.md`
- **Stories** : T1 `PricingEngine.compute()` cumul additif (TR-14, TR-21) — `÷100` unifié + T2 stratégies discount cumulative vs first-match (F532)
- **Touches** : `app/services/pricing/engine.py` (NEW), `app/services/pricing.py` (refactor)
- **Spec** : architecture-cible.md §3.2.4

### B3.S2 — FSM helper transactionnel (T0+11.5, 2 sem)

- **Doc** : `13-sprint-B3.S2.md`
- **Stories** : T1 FSM helper + table `fsm_transitions` + triggers DB + T2 reserve_stock à conversion devis→résa (TR-1, TR-12) + T3 ledger immutability triggers + T4 ledger tables (points/revenue/payment) via LedgerEntryMixin
- **Migration** : `e1f2a3b4c5d6_create_fsm_transitions_table.py` + 3 autres
- **Touches** : `app/services/fsm/helper.py` (NEW), `app/models/fsm_transitions.py` (NEW), `app/services/devis.py`, `app/services/reservation.py`

### B3.S3 — tva_rate_snapshot + PricingRules (T0+13.5, 2 sem)

- **Doc** : `13-sprint-B3.S3.md`
- **Stories** : T1 `tva_rate_snapshot Numeric NOT NULL` sur Devis/Resa/Vente/Invoice lines (TR-3) + T2 Backfill + T3 `TvaRateResolver` (étape transitoire — sera remplacé B4.S3.T2 par cascade Q23=A) + T4 PricingRules Numeric discount_pct + T5 Race conditions FOR UPDATE (TR-2)
- **Touches** : `app/services/pricing/tva.py` (NEW), tous les models `*_lines.py`

### B3.S4 — Cancel cascade + invoice immutability (T0+15.5, 2 sem)

- **Doc** : `13-sprint-B3.S4.md`
- **Stories** : T1 Invoice immutability trigger DB (TR-6, TR-7) + T2 `ReservationCancelService` cascade stock+deposit+credit_note (TR-5) + T3 reference UNIQUE per-tenant (TR-9, TR-27) + T4 drop finance legacy tables (TR-8) + T5 outbox handler `handle_reservation_cancelled`

### B3.S5 — EmailGateway + invoice events (T0+17.5, 2 sem)

- **Doc** : `13-sprint-B3.S5.md`
- **Stories** : T1 cleanup finance legacy + T2 invoice TX atomique + T3 invoice immutability service-level + **T4 EmailGateway interface (Postmark prep)** (TR-15, TR-38, TR-62) + T5 outbox dispatch email
- **🟡 Coordination** : Touche `app/services/notification.py` — annoncer 24h avant. **Page tape avant Torvalds B6.S1**.
- **Touches** : `app/services/email_gateway.py` (NEW), `app/services/notification.py` (refactor)

### B3.S6 — Celery beat expire jobs (T0+19.5, 1 sem)

- **Doc** : `13-sprint-B3.S6.md`
- **Stories** : T1 expire devis (TR-10) + T2 `relativedelta(months=N)` (TR-11) + T3 expire points loyalty + T4 e-invoicing prep colonnes (Q19=A)

### B3.S7 — Supplier orders cohérence (T0+20.5, 2 sem)

- **Doc** : `13-sprint-B3.S7.md`
- **Stories** : T1 SupplierOrder constraints (V6-P0-03/04) + T2 vente_lines tva_snapshot backfill + T3 deposits immutable trigger + T4 trigger receipt sync stock_items (post-deploy gate B4.S2.T6) + T5 evenements UNIQUE reference

**Mois 2 livré** : 7 sprints Bloc 3.

---

## Mois 3 (juillet 2026) — Bloc 4 Catalog

### B4.S1 — Pricing fusion + validators (T0+22.5, 1 sem)

- **Doc** : `14-sprint-B4.S1.md`
- **Stories** : F532 stratégie cumulative documentée + F533 scope `pricing:read`/`pricing:write` séparés + F499 calculate_price variants pricing

### B4.S2 — StockItemFSM + product_stock_view (T0+23.5, 2 sem)

- **Doc** : `14-sprint-B4.S2.md`
- **Stories** : T1 StockItemFSM matrice + trigger DB BEFORE UPDATE (TR-22) + T2 release_n(reservation_id=...) mandatory (TR-23) + T3 `product_stock_view` matérialisée (TR-17) + T4 drop colonnes denorm + T5 PMP/WAC stock_management (Q13=A) + T6 test cohérence post-deploy supplier_receipt
- **Touches** : `app/services/stock_item.py`, `app/models/stock_item.py`, `app/models/stock_management.py` (NEW)

### B4.S3 — Catalogue restructuré (T0+25.5, 2 sem)

- **Doc** : `14-sprint-B4.S3.md`
- **Stories** : T1 Category FK + drop Product.category String (TR-16) + **T2 Category.tva_rate cascade Q23=A + Product.tva_rate_override** (TR-3, TR-18, TR-56) + T3 `product_stock_view` consolidation + T4 `require_scope` sur GET /products (TR-19) + T5 brand_code Catalogue (TR-20) + T6 `Category.requires_advance_booking_days` (TR-33) + T7 Bundle `check_availability` (TR-34) + T8 Cycle prevention Category (TR-35) + T9 Vocabulaire `condition` enum unifié (TR-37)
- **🟡 Coordination** : Drop `Product.tva_rate_id` après backfill `Category.tva_rate` (transitoire B3.S3).

### B4.S4 — RFM + PricingEngine cleanup (T0+27.5, 2 sem)

- **Doc** : `14-sprint-B4.S4.md`
- **Stories** : T1 `RFMService` central (TR-30) + T2 cap multipliers fidélité (TR-13) + T3 Q26=A SIRET override admin + T4 install pgtrgm + T5 customer_search_trgm_index + **T6 Q27=B `tenant_settings.rfm_thresholds JSONB` per-tenant (Vague 8 ALTER table existante)** + T7 customer ISO country
- **Migration** : `f1a2b3c4d5f8a_tenant_settings_add_rfm_thresholds.py`
- **🟡 Coordination** : Touche `app/services/customer.py` — finir AVANT que Torvalds touche pour B4.S5 PII.

### B4.S5 — PII envelope encryption (T0+29.5, 2 sem)

- **Doc** : `14-sprint-B4.S5.md`
- **🟡 Coordination majeure** : ce sprint est **partagé Page+Torvalds**. Page contribue au modèle `customer.py`+`encrypted_field` (Q28=A obligatoire), Torvalds contribue à la migration KMS Celery. **Pair-programming recommandé**.
- **Stories Page** : T1 `EncryptedField TypeDecorator` (cf. B1.S3.T2 qui prépare déjà) + T3 customer phone+address PII colonnes encrypted (TR-26)
- **Stories Torvalds** : T2 migration data PII via Celery KMS + T4 drop PII clear text + T5 `pii_encryption_enabled` setting (Q28=B)

### B4.S6 — Reservations workflow + carrier (T0+31.5, 1 sem)

- **Doc** : `14-sprint-B4.S6.md`
- **Stories** : reservations carrier integration (port → Bloc 4 §4.6 list) + delivery_zone + container + damage_type cleanup

**Mois 3 livré** : 6 sprints Bloc 4.

---

## Synthèse 3 mois Page

| Mois | Sprints | Tables nouvelles | Migrations | Tests minima |
|---|---|---|---|---|
| Mai | B1.S1-S5 (5) | outbox_events, fsm_transitions (prep), tenant_settings RLS | 5 | 25+ |
| Juin | B3.S1-S7 (7) | points/revenue/payment ledger, fsm_transitions | 12 | 50+ |
| Juillet | B4.S1-S6 (6) | product_stock_view (matérialisée), category enrichi | 8 | 40+ |
| **Total** | **18 sprints** | **6 tables/views** | **25 migrations** | **115+ tests** |

---

## Dépendances ordre topologique strict

```
Sprint 1.T1 (✅ done)
  ↓
B1.S1 — Foundation security
  ↓
B1.S2 — RLS (gate Torvalds Bloc 2)
  ↓
B1.S3 — Outbox + EncryptedField
  ↓                                    ↘
B1.S4 — DegradedMode                    B1.S5 — Constants
  ↓
B3.S1 — PricingEngine
  ↓
B3.S2 — FSM (gate Bloc 4)
  ↓
B3.S3 — tva_rate_snapshot + TvaRateResolver transitoire
  ↓
B3.S4 — Cancel cascade + Invoice immut
  ↓
B3.S5 — EmailGateway (🟡 notification.py before Torvalds B6.S1)
  ↓
B3.S6 — Celery beat
  ↓
B3.S7 — Supplier
  ↓
B4.S1 → B4.S2 → B4.S3 (drop Product.tva_rate_id, cascade Q23=A)
  ↓
B4.S4 (🟡 customer.py before Torvalds B4.S5)
  ↓
B4.S5 (🟡 partagé Torvalds — pair-programming)
  ↓
B4.S6 — Reservations carrier
```

**Gates débloquant Torvalds** :
- B1.S2 livré → Torvalds peut ouvrir Bloc 2
- B3.S2 FSM helper livré → Torvalds peut ouvrir B4.S2 dépendances supplier
- B3.S5 notification.py refactor livré → Torvalds peut commencer B6.S1 Postmark

---

## Outils

- `mcp__context-engine__prepare(file_path)` avant chaque Edit Python
- `mcp__context-engine__explore(module)` pour orientation
- `mcp__context-engine__search(query)` pour grep symbolique
- `mcp__context-engine__checkpoint(notes)` pour checkpoint progrès session
- Senior protocol : `~/.claude/skills/senior-protocol`
- Backend rules : `~/.claude/skills/backend-rules`

---

## Communication

- Daily standup `#devup-refactor` 09:30 (15 min)
- **Annonce zone partagée** 24h avant : `notification.py`, `customer.py`, `tenant_settings`, `permissions/scope.py`
- Push sur `Page` à minimum 1× par jour (sauvegarde + visibilité Torvalds)
- PR review croisée des sprints en zones partagées

---

## Si bloqué

1. Lire le sprint complet `docs/.../execution-plan/<sprint>.md`
2. Lire architecture-cible.md section correspondante
3. Si conflit code↔spec : spec gagne (I7)
4. Si > 2h bloqué : ping Lead Slack

# Module 99 — Synthèse globale frictions registry

> **Phase F — DERNIER MODULE.** Consolidation des 35 modules audités. Top 30 P0 priorisés par impact métier. Patterns transverses récurrents. Plan de triage opérationnel par sprints.

---

## 0. Statistiques globales

| Phase | Modules | LoC audités | Frictions | dont P0 |
|---|---|---|---|---|
| **Phase A** (01-08) | Foundations | ~5 000 | ~140 | ~25 |
| **Phase B** (09-13) | IAM v2 | ~6 500 | ~180 | ~25 |
| **Phase C** (14-27) | Domaine métier | ~28 000 | ~530 | ~75 |
| **Phase D** (28-30) | Épicerie/Resto/ETL | ~14 000 | ~130 | ~26 |
| **Phase E** (31-35) | Cross-cutting | ~6 200 | ~155 | ~28 |
| **TOTAL** | **35** | **~60 000** | **1 154** | **~140 (12,1%)** |

**Identifiants** : F1 → F1154. Aucun trou de séquence. Compteur ouvre F1155 pour audits ultérieurs.

---

## 1. Patterns transverses récurrents

### 1.1 Race conditions sans `with_for_update` / advisory lock

**Modules concernés** : 17 (devis), 18 (reservation FSM), 19 (inventory stock), 20 (deposit), 25 (loyalty F792-F794), 28 (épicerie F871), 29 (restaurant F914), 33 (Celery F1057).

**Pattern** : read-modify-write sans verrou ligne pour les compteurs et stocks dénormalisés. Réplications systémiques :
- `member.transaction_count += 1` (loyalty)
- `stock.quantite -= n` (épicerie/restaurant)  
- `member.points balance_after = last + delta` (loyalty)
- `commande.payer()` sans lock commande

**Impact** : drift comptable et stock invisible jusqu'à audit. Un pic POS avec 2 caissiers = des centimes ou portions perdus.

**Fix transverse** : politique d'`with_for_update()` ou `pg_advisory_xact_lock(entity_id)` pour TOUTES les mutations sur compteurs dénormalisés. Linter Python custom (AST) qui flag tout `+= 1` ou `= last + ...` sans lock préalable.

### 1.2 FSM bypass — affectation directe de status

**Modules** : 18 (reservation F602-F604), 21 (invoice F420), 22 (vente F676), 24 (evenement F769), 26 (supplier F828), 28 (épicerie F870), 29 (restaurant F932).

**Pattern** : FSM matrice définie en Python (ex: `EVENT_TRANSITIONS`) mais code utilise `obj.status = "..."` direct, sans gardien. Aucun `CHECK` SQL enum. Typo silencieuse.

**Fix transverse** : (1) `CHECK status IN (...)` SQL sur **toutes** les FSM ; (2) helper `_transition(obj, target)` obligatoire qui valide la matrice ; (3) trigger DB `BEFORE UPDATE` qui re-vérifie.

### 1.3 Audit log absent sur transitions / actions sensibles

**Modules** : 18, 19, 20, 21, 22, 24, 25 (F805), 26 (F835), 27, 28, 29 (F910 pas de FinanceInvoice resto), 31 (F1010 middleware sans diff), 32 (F1033 feature flag), 33 (F1058 relance sans audit), 34 (F1090 print sans audit), 35.

**Pattern** : transitions critiques (cancel, refund, override prix, désactivation flag) non auditées explicitement. Le middleware audit (mod. 31) capture POST/PUT/PATCH génériquement mais sans `before/after` diff.

**Fix transverse** : (1) audit dans la **même transaction** que l'action métier (pas le middleware) ; (2) services exposent `audit_service.log_*` au point de mutation ; (3) middleware audit complète mais n'est pas la source de vérité.

### 1.4 Immutabilité promise par commentaire — pas par DB trigger

**Modules** : 18 (PaymentLedger), 21 (Invoice), 22 (VenteLedger), 25 (PointsLedger F795 / RevenueLedger), 26 (SupplierOrder), 28 (EpicerieStockMovement F873), 29 (MouvementStockRestaurant F916), 31 (AuditLog F1001).

**Pattern** : commentaire model dit "JAMAIS d'UPDATE/DELETE — corrections via nouvelle ligne". Aucun trigger PostgreSQL `BEFORE UPDATE/DELETE → RAISE EXCEPTION`. Discipline reposant sur la confiance des devs et le non-accès psql admin.

**Fix transverse** : migration Alembic globale qui pose ces triggers sur **toutes** les tables ledger/journal. Ajout d'une colonne `is_immutable` annotée + script de génération de triggers.

### 1.5 FK soft (string) au lieu de FK SQL

**Modules** : 15 (product F660 categorie string), 28 (épicerie idem), 29 (restaurant F977 categorie_code), 30 (F956 catalogue cross-tenant).

**Pattern** : `CategorieProduit.code` String référencé par chaîne dans `EpicerieProduit.categorie`, `IngredientRestaurant.categorie_code`, `CatalogueProduit.categorie_code`. Aucune FK SQL. Renommage M00 = orphelins silencieux.

**Fix transverse** : migration vers `categorie_id Integer FK` ou trigger validation existence du code.

### 1.6 TVA / devise hardcodées Marveline France

**Modules** : 15 (F660 default 0.20), 21 (F423 ROUND_HALF_UP cumulatif), 27 (F857 € symbol), 28 (taux_tva default 2000), 29 (F927 default 550 = 5,5%), 30 (F958 cross-pays bloqué), 34 (F1096 EUR ticket).

**Pattern** : valeurs par défaut spécifiques France métropole. Bloque l'expansion La Réunion (TVA 0% certains alimentaires), Sénégal (XOF, TVA 18%), Polynésie (XPF).

**Fix transverse** : `tenant_settings.country_code` + table `tva_par_pays_categorie` lookup ; ticket utilise `tenant.currency_code`.

### 1.7 PII non chiffrée dans Text columns

**Modules** : 14 (Customer notes), 18 (reservation notes), 21 (invoice notes), 24 (evenement notes), 26 (supplier notes F832), 27 (notification message F862), 31 (audit description F1007 + changes JSONB).

**Pattern** : champs `notes Text nullable` peuvent contenir mots de passe portail fournisseur, données médicales (allergies events), conditions négociées B2B. Aucun chiffrement.

**Fix transverse** : envelope encryption KMS (existante pour TOTP cf. mod. 12) appliquée systématiquement sur tous les champs `notes` + `description` + `changes`.

### 1.8 Mix sync/async DB sessions et patterns SQLAlchemy 1.x vs 2.0

**Modules** : 33 (F1054 invoicing/relances/loyalty sync, risk_detection async, etl_tasks event loop persistant), 34 (F1091 httpx sync dans async).

**Pattern** : 4 patterns différents pour interagir avec la DB. Style 1.4 legacy `db.query(...)` mélangé à 2.0 `select()`. asyncio.run() recrée event loop, asyncpg conn pool perdu.

**Fix transverse** : tout migrer en async + `select()` 2.0 style. Linter pour bloquer `db.query(`.

### 1.9 No DLQ / retry policy / observability sur tasks Celery

**Modules** : 27 (F853 email pas de retry), 33 (F1068 pas de DLQ, F1080 pas de Prometheus tasks), 35 (F1151 celery_task_duration absent).

**Fix transverse** : (1) DLQ Redis pour tasks épuisant retry ; (2) `celery_task_duration_seconds{name, status}` Histogram ; (3) beat heartbeat health check.

### 1.10 Cross-tenant validation absente côté DB

**Modules** : 09 (tenant), 28 (catalogue cross-tenant), 29 (mapping F924+F925), 30 (F965 InternalTransfer + TransferRequest).

**Fix transverse** : trigger DB sur insertions cross-tenant (`epicerie_produits.tenant_id == tenants.app_code "epicerie"`) ; refus au niveau DB plutôt que confiance code.

---

## 2. Top 30 P0 par priorité métier

### 2.1 BLOC SÉCURITÉ — DOIT ÊTRE FIXÉ AVANT MEP PROD ÉLARGIE

| Rang | F# | Module | Description | Effort |
|---|---|---|---|---|
| 1 | F1122 | 35 | `/metrics` endpoint public sans auth — fuite reconnaissance + business intel | S (auth Basic) |
| 2 | F1123 | 35 | `/health/status` expose `EMERGENCY_BYPASS` aux anonymes | S (sanitize map) |
| 3 | F1094 | 34 | `WG_INTERNAL_API_KEY` plain header — pas mTLS | M (mTLS infra) |
| 4 | F1089 | 34 | POST /print/ticket sans `require_scope` | XS (1 ligne) |
| 5 | F1002 | 31 | Login échec non audité (path EXCLUDED middleware) | S |
| 6 | F1001 | 31 | HMAC AuditLog ne signe pas `changes` — falsifiable | M |
| 7 | F1003 | 31 | SENSITIVE_READ_PATTERNS incomplet (mfa, sessions, devis, fidélité) | S |
| 8 | F999  | 31 | AuditLog sans FK tenant_id | S |

### 2.2 BLOC INTÉGRITÉ DONNÉES / COMPTABLE — RISQUE FINANCIER

| Rang | F# | Module | Description | Effort |
|---|---|---|---|---|
| 9 | F906 | 29 | AttributeError runtime `quantite_par_portion` — POST /instances cassé production | XS (rename) |
| 10 | F908+F909 | 29 | Annulation ligne/commande resto sans réintégration stock — drift garanti | M |
| 11 | F910 | 29 | Restaurant.payer() sans FinanceInvoice — CA hors livre comptable | L |
| 12 | F1058 | 33 | `execute_scheduled_relances` marque "sent" sans envoyer l'email | S (wire send_email) |
| 13 | F792-F794 | 25 | Race conditions ledger fidélité (credit_points, transaction_count) | M (advisory lock) |
| 14 | F870 | 28 | encaisser() check_stock=False par défaut → IntegrityError 500 | S |
| 15 | F871 | 28 | valider_transfert sans with_for_update | S |
| 16 | F872 | 28 | annuler_vente VALIDEE ne crée pas d'avoir → désync compta | M |
| 17 | F1057 | 33 | expire_points_fifo race vs credit live | S |
| 18 | F602-F604 | 18 | FSM reservation bypass _transition | S |
| 19 | F1056 | 33 | check_overdue_invoices séquentiel tenants — sub-task échoue, queue partial | S |

### 2.3 BLOC COMPLIANCE — RISQUE AUDIT SOC2/RGPD

| Rang | F# | Module | Description | Effort |
|---|---|---|---|---|
| 20 | F1055 | 33 | auto_suspend_uncertified retourne `{"status": "skipped"}` — compliance théâtre | L (impl table) |
| 21 | F1015 | 31 | Pas d'export RGPD Article 15 (droit d'accès) | M |
| 22 | F1016 | 31 | Pas de purge automatique audit_logs >7 ans | S |
| 23 | F1000 | 31 | Audit middleware ouvre session DB séparée — perte audit silent + pool exhaust | M |
| 24 | F959 | 30 | EtlCorrectionHistory sans tenant_id — fuite cross-tenant | M |
| 25 | F957 | 30 | CategorieProduit sans tenant_id — admin SaaS peut casser tous les tenants | S |

### 2.4 BLOC PRODUCTION READINESS

| Rang | F# | Module | Description | Effort |
|---|---|---|---|---|
| 26 | F1124 | 35 | check_postgres sync dans /health/ready async — Kubernetes redémarre pods sains | S |
| 27 | F1125 | 35 | /health liveness toujours 200 même event loop bloqué | S |
| 28 | F1126 | 35 | MetricsMiddleware cardinality blow-up via 404 random paths — DoS Prometheus | S |
| 29 | F1053 | 33 | Queue Celery `loyalty` mal routée (pas dans task_routes) — tasks orphelines | XS |
| 30 | F848 | 27 | _send_email synchrone bloquant smtplib — 3s par email × 100 = 5min worker bloqué | M (Celery wrap) |

---

## 3. Plan de triage par sprints (4 semaines / sprint)

### Sprint 1 — Sécurité critique + bugs production (2 semaines)

**Objectifs** : éliminer toute exposition externe, fixer les bugs runtime visibles.

- F906 (AttributeError quantite_par_portion) — XS, mais bloque restaurant
- F1089 (scope print) — XS
- F1058 (relance email réel) — S
- F1053 (queue loyalty routée) — XS
- F1122 + F1123 (metrics + status page auth) — S
- F870 (encaisser check_stock défaut) — S
- F1124 + F1125 (health async) — S

**Livrable** : 7 fixes, ~3-4 jours de dev, déployables en hotfix.

### Sprint 2 — Race conditions ledger + audit log integrity (2 semaines)

- F792-F794 (advisory lock loyalty)
- F1057 (expire_points_fifo lock)
- F871 (transfert with_for_update)
- F872 (annuler_vente avoir)
- F908-F909 (annulations resto réintégration stock)
- F1001 (HMAC sign full payload + chaîne hash bloc précédent)
- F1000 (audit en transaction métier)

**Livrable** : audit fiabilisé + ledger sécurisé. Migration Alembic triggers immutability.

### Sprint 3 — FSM hardening + cross-tenant validation (2 semaines)

- F602-F604 + autres FSM bypass (mod. 21, 22, 24, 26, 28, 29) — pattern global
- CHECK enum SQL sur toutes les FSM
- F965 cross-tenant trigger DB validation
- F957 + F959 tenant_id sur CategorieProduit + EtlCorrectionHistory

**Livrable** : intégrité FSM + isolation tenant garantie au niveau DB, plus seulement code.

### Sprint 4 — Compliance RGPD/SOC2 + observabilité (2 semaines)

- F1015 export RGPD Art. 15
- F1016 purge auto >7 ans
- F1055 implémenter auto_suspend table access_reviews
- F1126 cardinality fix
- Labels tenant_id metrics (F1128, F1131)
- DLQ Celery (F1068)

**Livrable** : audit SOC2 ready + dashboards Grafana exploitables.

### Sprint 5 — Performance + cleanup (2 semaines)

- F848 email Celery
- F1091-F1092 httpx async + pool
- F1093 circuit breaker imprimante
- F1054 standardiser sessions DB async
- F910 FinanceInvoice restaurant — refacto profond

**Livrable** : sous charge, latence p99 stabilisée, plus de couplage ressource.

---

## 4. Patterns d'architecture à institutionnaliser

### 4.1 Convention `services/` doivent appeler `audit_service.log_*` explicitement

**Plus** se reposer sur le middleware audit pour tracer les mutations. Le service est le seul à connaître le before/after diff.

### 4.2 Convention `repositories/` exposent `with_for_update=True` flag obligatoire pour les mutations dénormalisées

`stock_repo.get_by_id_lock(id)` → SELECT ... FOR UPDATE. `stock_repo.get_by_id(id)` → simple read. Linter custom qui flag les patterns `get` + assignment sans `_lock` suffix.

### 4.3 Convention FSM matrice + helper `_transition(obj, target)` partout

Bannir `obj.status = "..."` direct. PR review + test unitaire qui exécute `assert _transition(...)` partout.

### 4.4 Convention triggers DB pour invariants critiques

Liste maintenue dans `alembic/triggers/` :
- `prevent_audit_log_modification()`
- `prevent_ledger_modification()` (PointsLedger, RevenueLedger, PaymentLedger, EpicerieStockMovement, MouvementStockRestaurant, VenteLedger)
- `validate_cross_tenant_consistency()` (InternalTransfer, IngredientEpicerieMapping, TransferRequest)

### 4.5 Convention multi-pays / multi-devise

`tenant_settings.country_code` + `tenant_settings.currency_code` lus à chaque rendering financier. Pas de `€` ni `0.20` hardcoded.

---

## 5. Modules les plus dégradés (concentration de P0)

| Module | P0 | Total | Note critique |
|---|---|---|---|
| 25 — Loyalty | 6 | 34 | Race conditions, expiration approximative, immutabilité code-only |
| 18 — Reservation FSM | 8 | 42 | FSM bypass systémique, pas d'audit transitions |
| 17 — Devis | 8 | 40 | Conversion devis→résa fragile |
| 28 — Épicerie/ETL | 7 | 37 | Catalogue cross-tenant, encaisser sans stock check |
| 33 — Orchestration Celery | 7 | 36 | Queue mal routée, sync/async mix, compliance théâtre |
| 19 — Inventory Stock | 6 | 32 | 3 sources de vérité non sync |
| 21 — Invoice Payment | 6 | 33 | Arrondis cumulatifs TVA |
| 30 — Catalogue/Transferts | 11 | 43 | FK soft, cross-tenant non validé, lignes_data pas versioned |
| 29 — Restaurant | 8 | 50 | AttributeError runtime, annulations sans réintégration, no FinanceInvoice |
| 35 — Health/Metrics | 5 | 33 | /metrics public, sync DB dans async health |

**Constat** : les 10 modules ci-dessus représentent **72 P0 / 380 frictions**, soit 51% des P0 totaux pour 33% des modules. Concentration sur le **domaine ledger/FSM/cross-tenant** + **observabilité**.

---

## 6. Dette architecturale macro

### 6.1 Le système n'a pas de "source de vérité" unique pour le stock

Trois sources :
- `Product.stock_quantity` (legacy Marveline mod. 15-19)
- `EpicerieStock.quantite` (mod. 28)
- `IngredientRestaurant.stock_actuel` (mod. 29)

Plus les ledgers : `InventoryMovement`, `EpicerieStockMovement`, `MouvementStockRestaurant`. Aucun `ASSERT sum(ledger.delta) == stock.current` automatisé.

**Action** : Celery task quotidienne `verify_stock_ledger_consistency()` qui alerte sur drift > seuil.

### 6.2 Pas de "budget" / cap quotidien sur les actions sensibles

Aucune limite : `MouvementStockService.create(type='perte')` sans cap (F950 mod. 29) ; cap absent earn points (F810 mod. 25) ; cap multipliers cumulatifs VIP×Flash (F807 mod. 25).

**Action** : table `tenant_action_quotas` + checker dans services.

### 6.3 Le système ne sait pas se mettre en erreur "fail-closed"

Patterns "fail-open" partout : audit middleware swallow exception (F1000), feature flag fallback ambigu (F1031), HMAC swallow (F963), printer load_commerce_info retourne tuples vides (F1059).

**Action** : politique explicite per-module sur fail-open vs fail-closed. Default fail-closed sauf liveness probe.

### 6.4 Multi-tenant sécurisé par filtre repository — confiance code

Le pattern "tous les repos ajoutent `WHERE tenant_id = X`" repose sur la discipline. Aucun trigger DB ni RLS PostgreSQL.

**Action** : Row Level Security PostgreSQL activée sur les tables critiques (audit_logs, customers, reservations, invoices, ventes). `current_setting('app.tenant_id')::int = tenant_id` policy.

### 6.5 ETL alimentaire — pivot fragile

Le `EtlImport.lignes_data JSONB` est central pour preview/edit/revert (F875, F966). Pas versionné. Refactor `LigneParsee` casse tous les imports historiques.

**Action** : `lignes_data_schema_version` + migrators.

---

## 7. Recommandations finales

### 7.1 Avant tout déploiement client production B2B

**Mandatory** : Sprint 1 + Sprint 2. Sans race conditions stables + audit fiable, un litige B2B (devis facturé à mauvais montant) = pas de défense possible.

### 7.2 Avant un audit SOC2 réel

**Mandatory** : Sprint 4 complet + F1055 (auto_suspend implémenté) + F1015 (RGPD Art. 15). Auditeur cherchera ces preuves.

### 7.3 Avant expansion multi-pays (Splendid Sénégal)

**Mandatory** : pattern multi-devise/multi-tva (F958, F927, F1095, F1096). Aujourd'hui le system est figé France métropole.

### 7.4 Avant mise à l'échelle (>100 tenants)

**Mandatory** : labels tenant_id metrics (F1128), Row Level Security PostgreSQL, instrumentation OpenTelemetry (F1138). Sinon impossible de debug incidents tenant-specific en production.

---

## 8. Conclusion

35 modules audités, ~60 000 LoC analysés, **1 154 frictions documentées** dont **140 P0** (12.1%). 

**Codebase mature en surface, dette critique en profondeur** : la qualité du code (typing, conventions, structure) est élevée, mais l'application des invariants au niveau DB (triggers, FK, CHECK, RLS) est dramatiquement insuffisante. Le système repose sur la discipline des développeurs plutôt que sur des barrières structurelles.

**Verdict** : code prêt à un déploiement contrôlé Marveline France métropole avec un client B2C low-volume. **Pas prêt** pour SOC2, multi-pays, ou >50 tenants concurrents sans Sprints 1-4 complétés.

**Estimation effort total triage P0** : **~10 semaines de dev senior** (5 sprints × 2 semaines), assuming aucune nouvelle feature en parallèle.

---

# 🎯 AUDIT TERMINÉ

**6 phases, 35 modules, 1 154 frictions répertoriées sur ~60 000 LoC.**

Documents livrés : `docs/architecture-audit-2026-04-26/00-INDEX.md` à `99-synthese-globale.md`.

**Prochaine étape** : revue avec le founder (DEVUP) pour prioriser les Sprints 1-2 et déterminer les commits compromettants à inclure dans le pre-launch hardening.

# Audit architecture — 2026-04-26

> **Méthode** : lecture intégrale du code source de chaque module. Aucun .md historique consulté comme source de vérité. Frictions observées par lecture, citées par `fichier:ligne`.
> **Cible** : convention 4 couches (Models → Repositories → Services → Endpoints + Schemas + Constants), scalabilité maximale, isolation tenant rigoureuse, multi-app/multi-brand propre.
> **Échelle de sévérité** :
> - **P0** — bloque la sécurité, l'intégrité tenant, ou rend la scalabilité impossible.
> - **P1** — dette structurelle qui se paiera sur chaque nouveau module/feature.
> - **P2** — incohérence de convention, mauvaise factorisation localisée.
> - **P3** — cosmétique, naming, docstring.

---

## Glossaire des frictions (numérotation globale)

Chaque friction reçoit un identifiant unique global de la forme `F<NN>` (incrémental, pas par fichier). Les .md ultérieurs réutilisent ces identifiants pour référencer des frictions déjà documentées sans les redécrire.

Index des frictions tenu à jour dans `99-frictions-registry.md` (généré à la fin).

---

## Plan d'audit (ordre = dépendance ascendante)

### Phase A — Fondations transverses
| # | Fichier | Périmètre |
|---|---|---|
| 01 | `01-core-foundations.md` | `app/core/{config,database,deps,exceptions,redis,cache,__init__}.py` |
| 02 | `02-core-security.md` | `app/core/{security,crypto,kms,password_policy,permissions,validators,upload_validator}.py` |
| 03 | `03-core-observabilite.md` | `app/core/{logging,metrics,health,slow_query,rate_limiter,rate_limit_utils}.py` |
| 04 | `04-middleware.md` | `app/middleware/*.py` |
| 05 | `05-models-base-mixins.md` | `app/models/base.py` + mixins (TimestampMixin, TenantMixin, SoftDeleteMixin) |
| 06 | `06-repositories-base.md` | `app/repositories/base.py` + génériques + filtre tenant |
| 07 | `07-constants.md` | `app/constants/*.py` |
| 08 | `08-schemas-base.md` | `app/schemas/base.py` + `common.py` + conventions Pydantic |

### Phase B — Auth & Identité
| # | Fichier | Périmètre |
|---|---|---|
| 09 | `09-tenant-multi-app-brand.md` | `Tenant`, `TenantBrand`, `TenantSettings`, `app_code`/`brand_code`, `provisioning` (CRITIQUE — sujet Marveline/Splendid) |
| 10 | `10-account-session-membership.md` | `Account`, `AccountSession`, `AccountOAuthIdentity`, `TenantMembership` |
| 11 | `11-rbac.md` | `auth_role`, `auth_role_scope`, `auth_scope`, `Permission`, `Scope`, `ROLE_*` |
| 12 | `12-mfa-webauthn-trusted-device.md` | `mfa`, `webauthn_credential`, `trusted_device` |
| 13 | `13-api-key-oauth-password-reset.md` | `api_key`, `oauth_v2`, `password_reset_token` |

### Phase C — Domaines métier (Marveline = location événementiel)
| # | Fichier | Périmètre |
|---|---|---|
| 14 | `14-customer.md` | |
| 15 | `15-product-catalog.md` | `product`, `product_variant`, `product_image`, `product_collection`, `product_maintenance`, `bundle`, `formula` |
| 16 | `16-category-container-damage.md` | |
| 17 | `17-pricing-delivery-zone.md` | |
| 18 | `18-devis.md` | |
| 19 | `19-reservation.md` | `reservation`, `reservation_version`, `reservation_workflow` |
| 20 | `20-inventory-stock.md` | `inventory_movement`, `movement_damage`, `movement_item_unit`, `stock_item`, `stock_management` |
| 21 | `21-deposit.md` | |
| 22 | `22-invoice-payment.md` | `invoice`, `invoice_charge`, `invoice_credit_note`, `payment` |
| 23 | `23-relance.md` | |
| 24 | `24-evenements.md` | |
| 25 | `25-loyalty-wallet.md` | `loyalty`, `wallet` |
| 26 | `26-supplier.md` | `supplier`, `supplier_order`, `supplier_product_price` |
| 27 | `27-notification.md` | |

### Phase D — Domaines métier secondaires
| # | Fichier | Périmètre |
|---|---|---|
| 28 | `28-epicerie.md` | tout `app/{models,repositories,services,api/v1/endpoints,schemas}/epicerie/` |
| 29 | `29-restaurant.md` | tout `.../restaurant/` |
| 30 | `30-catalogue-shared.md` | `app/models/catalogue/`, `app/repositories/catalogue/`, `app/services/catalogue/` |

### Phase E — Cross-cutting / ops
| # | Fichier | Périmètre |
|---|---|---|
| 31 | `31-audit-feature-flag.md` | `audit_log`, `feature_flag` |
| 32 | `32-orchestration-views.md` | `dashboard`, `search`, `planning`, `orders`, `operations` |
| 33 | `33-printer-receipt-carrier-treasury.md` | |
| 34 | `34-vpn-wireguard-provisioning.md` | |
| 35 | `35-health-metrics.md` | endpoints health/metrics + intégration Prometheus |

### Phase F — Synthèse
| # | Fichier | Périmètre |
|---|---|---|
| 99 | `99-synthese-globale.md` | **LIVRÉ** — Top 30 P0 priorisés, patterns transverses, plan triage 5 sprints, dette macro |

---

## État livraison (2026-04-26)

| Phase | Modules | Statut | Frictions |
|---|---|---|---|
| Phase A (01-08) | Foundations | ✅ livré | ~140 (~25 P0) |
| Phase B (09-13) | IAM v2 | ✅ livré | ~180 (~25 P0) |
| Phase C (14-27) | Domaine métier | ✅ livré | ~530 (~75 P0) |
| Phase D (28-30) | Épicerie/Resto/ETL | ✅ livré | ~130 (~26 P0) |
| Phase E (31-35) | Cross-cutting | ✅ livré | ~155 (~28 P0) |
| Phase F (99) | Synthèse globale | ✅ livré | — |
| **TOTAL** | **35 + synthèse** | **✅ COMPLET** | **1 154 (~140 P0)** |

---

## Template de chaque module

```
# Module XX — [Nom]

## 1. Périmètre
- **Fichiers analysés** : [liste avec LoC]
- **Dépend de** : [refs autres modules]
- **Dépendu par** : [refs forward, à compléter à la fin]

## 2. Lecture par couche
### 2.1 Modèle(s)
### 2.2 Schémas Pydantic
### 2.3 Repository
### 2.4 Service
### 2.5 Endpoint(s)
### 2.6 Constantes
### 2.7 Migrations Alembic associées

## 3. Frictions identifiées
| ID | Sévérité | Couche | Friction | Citation | Impact |

## 4. Dépendances inter-modules / fuites
[couplages observés, références forward]

## 5. Recommandations de refonte
[par friction, ordonnées par dépendance — quoi refactor d'abord]
```

---

## Méta-règles d'écriture

1. **Source unique** : le code. Aucun .md tiers cité comme autorité.
2. **Citations obligatoires** : chaque friction porte une citation `fichier.py:ligne`.
3. **Pas de réinvention** : si un fichier respecte la convention 4-couches, le dire en une phrase et passer. Inutile de paraphraser le code.
4. **Frictions cumulatives** : un module B peut révéler qu'une friction documentée dans A est plus grave que prévu — mettre à jour `99-frictions-registry.md`, pas le .md historique.
5. **Pas de "todo" implicite** : les recommandations sont concrètes, exécutables, ordonnées.

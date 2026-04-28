# Rollout Plan — Feature flags par migration + % traffic progressif

> **Objectif** : déployer les 36 sprints en production sans régression métier.
> **Stratégie** : feature flags B6.S3 + canary % traffic + rollback bouton un-clic.

---

## 1. Principes

1. **Toute migration data 4 étapes** (cf. `02-conventions.md`) avant feature flag visible client
2. **Feature flag par capacité** (pas par story) — ex: `rls_enforced`, `pricing_engine_v2`, `audit_chain_hmac`
3. **Canary 5% → 25% → 100%** sur 3 jours minimum par flag
4. **Métriques de succès** définies AVANT activation (Grafana panel + AlertManager rule)
5. **Rollback** : flag à `false` doit rétablir comportement précédent en <30s

---

## 2. Feature flags planifiés (par bloc)

### Bloc 1 — Foundations

| Flag | Story | Activation | Métrique succès |
|---|---|---|---|
| `rls_enforced` | B1.S2 | Canary 5% tenants pendant 3j | 0 cross-tenant leak detected |
| `kms_encryption_active` | B1.S3 | Direct 100% (no canary, low risk) | 0 decrypt errors |
| `outbox_dispatcher_v2` | B1.S3 | Canary 25% events | Latency dispatch p99 < 500ms |
| `degraded_mode_v2` | B1.S4 | Direct 100% | Health detect Redis down → READ_ONLY |

### Bloc 2 — Identity

| Flag | Story | Activation | Métrique succès |
|---|---|---|---|
| `webauthn_per_tenant_rp_id` | B2.S4 | Canary Splendid 1 tenant | Démo Splendid OK 28/04 |
| `oauth_mfa_gate` | B2.S4 | Direct 100% (security fix) | 0 MFA bypass detected |
| `auth_factors_unified` | B2.S5 | Migration data + flag à `true` | TOTP + WebAuthn + Recovery codes via single table |

### Bloc 3 — Money

| Flag | Story | Activation | Métrique succès |
|---|---|---|---|
| `pricing_engine_v2` | B3.S3 | Canary 5% devis (shadow mode) | simulate == apply au cent invariant |
| `invoice_immutable_trigger` | B3.S2 | Direct 100% (security) | 0 update sur invoice émise |
| `devis_atomic_conversion` | B3.S4 | Canary 10% conversions | 0 état inconsistant rollback |
| `email_gateway_postmark` | B3.S5 | Canary 5% emails | success_rate > 99% |
| `loyalty_caps_enforced` | B3.S5 | Direct 100% (anti-fraude) | 0 earn > daily/monthly cap |
| `einvoicing_enabled` | B3.S6 | OFF par défaut (per-tenant DB) | Activation manuelle tenant Sept 2026 |

### Bloc 4 — Catalogue

| Flag | Story | Activation | Métrique succès |
|---|---|---|---|
| `stock_view_materialized` | B4.S2 | Canary 5% queries | View refresh < 5s debounced |
| `category_fk_required` | B4.S3 | Migration + flag → 100% | 0 product orphelin |
| `pii_encryption_complete` | B4.S5 | Migration backfill + flag | 0 PII clear text post-migration |

### Bloc 5 — Multi-app

| Flag | Story | Activation | Métrique succès |
|---|---|---|---|
| `etl_tenant_aware` | B5.S2 | Canary 1 tenant | 0 cross-tenant leak ETL |
| `restaurant_invoice_on_pay` | B5.S1 | Direct 100% (compliance fiscale) | 100% commande PAYEE → Invoice |
| `transfer_request_auto_approve` | B5.S6 | Canary 1 tenant | Stock check race-safe |

### Bloc 6 — Cross-cutting

| Flag | Story | Activation | Métrique succès |
|---|---|---|---|
| `audit_chain_hmac` | B6.S2 | Direct 100% (sécurité) | verify_chain_task 0 alerte |
| `audit_pii_encrypted` | B6.S2 | Migration + flag | Audit changes chiffré at-rest |
| `metrics_mtls_enforced` | B6.S6 | Canary scraper test | 401 sans cert |
| `celery_broker_rabbitmq` | B6.S7 | Migration parallèle (cf. `64-rabbitmq-migration.md`) | 0 task lost |

### Bloc 7 — DEVUP

| Flag | Story | Activation | Métrique succès |
|---|---|---|---|
| `tenant_vertical_routing` | B7.S1 | Direct (post backfill) | Scopes vertical-based |
| `app_selector_v2` | B7.S3 | Canary 10% users | UX validée |
| `tenant_provisioning_api` | B7.S4 | OFF puis admin-only | Provisioning 10 min |

---

## 3. Calendrier rollout (timeline 10 mois)

```
T+0  ──────────────── Sprint 1 PROD FIRE-DRILL (1 sem) ─────────────── T+1
                                  ▼
T+1  ──────────── Bloc 1 Foundations (parallèle Bloc 2) ────────────── T+5
                                  ▼
T+3  ──────────── Bloc 2 Identity (overlap Bloc 1) ─────────────────── T+7
                                  ▼
T+5  ──────────── Bloc 3 Money / Bloc 4 Catalogue (parallèle) ─────── T+15
                  Dev1 = Money | Dev2 = Catalogue
                                  ▼
T+10 ──────────── Bloc 5 Multi-app (Dev3) ──────────────────────────── T+19
                                  ▼
T+12 ──────────── Bloc 6 Cross-cutting (Dev1+Ops) ──────────────────── T+22
                                  ▼
T+18 ──────────── Bloc 7 DEVUP (Dev2 + Frontend) ───────────────────── T+22
                                  ▼
T+22 ──────────── Recette + bug bash + go-live progressif ──────────── T+24
```

**Fenêtres clés** :
- Démo Splendid : **2026-04-28** — bloque B2.S4.T5 (WebAuthn RP_ID per-tenant)
- Merge freeze : **2026-03-05** — mobile release cut
- e-invoicing France : **2026-09-01** — schema doit être prêt (B3.S6)

---

## 4. Décisions de canary

### Critères pour passer 5% → 25% → 100%

Pour chaque flag :
1. **24h+ à 5% sans alerte AlertManager**
2. **Métrique de succès atteinte** (ex: `error_rate < 0.1%`)
3. **Validation produit** par 1 client pilote
4. **Pas de PR rollback ouverte**

### Critères de rollback immédiat

- 1 erreur P0 reportée
- Métrique de succès dégradée 30 min
- Cross-tenant leak détecté (peu importe la magnitude)

---

## 5. Communication clients

Pour les flags **visibles client** (UX) :
- Email J-7 avant activation
- Banner UI in-app J-1 + J0
- Lien "donner mon avis" actif 30j post-activation
- Tracking adoption (Mixpanel ou équivalent)

Pour les flags **invisibles client** (techniques) :
- Pas de communication user
- Communication interne ops/produit seulement

---

## 6. Outils

- **Feature flags** : implémentation B6.S3 (DB-backed + cache LRU + Redis PUB/SUB)
- **Métriques** : Grafana dashboards `Rollout DEVUP 2026`
- **Alertes** : AlertManager rules → Slack `#alerts-rollout`
- **Audit changes** : `feature_flag_history` table (B6.S3.T3)

---

**Fin du document — 60-rollout-plan.md**

# ZONES — Partition fichiers Page / Torvalds

> Référence : éviter les conflits de merge en respectant les zones réservées par dev.
> Mise à jour : 2026-04-28.

## Légende

- 🔵 **Page** — fichiers exclusifs Dev A (Foundation + Money + Catalog)
- 🟢 **Torvalds** — fichiers exclusifs Dev B (Auth + ETL + Ops + Frontend)
- 🟡 **Coordination** — fichiers partagés, ordre + daily check obligatoire

---

## Backend

### `app/api/v1/endpoints/`

| Endpoint | Owner | Sprint(s) |
|---|---|---|
| `auth.py`, `oauth.py`, `mfa.py`, `sessions.py`, `api_keys.py`, `webauthn.py` | 🟢 Torvalds | B2.S1-S5 |
| `users.py`, `accounts.py` | 🟢 Torvalds | B2.S2 |
| `customers.py` | 🟡 Coordination | Page B4.S4 RFM, Torvalds B4.S5 PII (séquentiel) |
| `products.py`, `categories.py`, `bundles.py`, `pricing.py` | 🔵 Page | B4.S3, B4.S4 |
| `devis.py`, `reservations.py`, `invoices.py`, `ventes.py` | 🔵 Page | B3.S2-S5 |
| `inventory_movements.py`, `stock_items.py` | 🔵 Page | B4.S2 |
| `audit.py` | 🟡 Coordination | Page B1.S1 (endpoint base lecture log), Torvalds B6.S2 (HMAC chain + verify endpoint) |
| `health.py`, `metrics.py` | 🟢 Torvalds | B6.S6 |
| `features.py` (feature flags) | 🟢 Torvalds | B6.S4 |
| `dashboard.py` | 🟡 Coordination | Page contribue (revenue), Torvalds contribue (audit) |
| `vpn.py` (WireGuard) | 🟢 Torvalds | B6.S5 |
| `restaurant/*` | 🟢 Torvalds | B5.S1, B5.S3, B5.S4 |
| `epicerie/*` | 🟢 Torvalds | B5.S1, B5.S5 |
| `transfer_requests.py` | 🟢 Torvalds | B5.S1 |
| `etl/*` | 🟢 Torvalds | B5.S2, B5.S6 |
| `tenant_provisioning.py` (NEW) | 🟢 Torvalds | B2.S2 |
| `rgpd.py` (NEW) | 🟢 Torvalds | B6.S3 |
| `print.py` | 🟢 Torvalds | B6.S1, B6.S5 |

### `app/services/`

| Service | Owner | Sprint(s) |
|---|---|---|
| `account.py`, `account_session.py`, `auth_v2.py`, `mfa.py`, `oauth_v2.py`, `pin_auth.py`, `session.py`, `webauthn.py`, `api_key.py`, `bruteforce.py`, `rbac.py`, `tenant.py`, `membership.py`, `user.py`, `token.py`, `hibp.py` | 🟢 Torvalds | Bloc 2 |
| `pricing_engine.py` (NEW), `pricing.py` | 🔵 Page | B3.S1, B3.S3 |
| `devis.py`, `devis_pdf.py`, `reservation.py`, `reservation_workflow.py` | 🔵 Page | B3.S2 |
| `invoice.py`, `invoice_pdf.py`, `invoice_credit_note.py`, `invoice_payment_rules.py` | 🔵 Page | B3.S4, B3.S5 |
| `vente.py`, `vente_pdf.py`, `payment.py`, `treasury.py`, `deposit.py` | 🔵 Page | B3.S3, B3.S4 |
| `loyalty.py`, `wallet.py` | 🔵 Page | B4.S4 |
| `category.py`, `bundle.py`, `product.py`, `product_variant.py`, `product_maintenance.py` | 🔵 Page | B4.S3 |
| `stock_item.py`, `stock_management.py` (NEW WAC), `inventory_movement.py` | 🔵 Page | B4.S2 |
| `formula.py`, `container.py`, `damage_type.py`, `delivery_zone.py` | 🔵 Page | B4.S6 |
| `customer.py` | 🟡 Coordination | Page B4.S4 RFM **avant** Torvalds B4.S5 PII |
| `evenements.py`, `orders.py` | 🔵 Page | B4.S6 |
| `restaurant/*`, `epicerie/*`, `transfer_request.py` | 🟢 Torvalds | Bloc 5 |
| `etl/*` | 🟢 Torvalds | B5.S2, B5.S6 |
| `audit.py` | 🟡 Coordination | Page B1.S1 (service base : append_log, key versioning seed, helper compute_hmac) **avant** Torvalds B6.S2 (chain enforcement + verify_chain) |
| `feature_flag.py` | 🟢 Torvalds | B6.S4 |
| `notification.py` | 🟡 Coordination | Page B3.S5 (EmailGateway interface) **avant** Torvalds B6.S1 (Postmark backend) |
| `printer.py` | 🟢 Torvalds | B6.S5 |
| `wireguard_client.py` | 🟢 Torvalds | B6.S5 |
| `carrier.py`, `carrier_rates.py` | 🟢 Torvalds | B5.S5 |
| `supplier_order.py` | 🟢 Torvalds | B3.S7 (transverse) |
| `operations.py` | 🟡 Coordination | Page B4 + Torvalds B5/B6 |

### `app/models/`

| Modèle | Owner | Notes |
|---|---|---|
| `account*.py`, `auth_*.py`, `mfa.py`, `webauthn_credential.py`, `trusted_device.py`, `password_reset_token.py`, `api_key.py`, `tenant_membership.py`, `user_role.py`, `tenant.py` | 🟢 Torvalds | B2 + B7.S1 |
| `tenant_brand.py`, `tenant_settings.py` | 🟡 Coordination | ALTERs séparés (Page B4.S4 rfm_thresholds, Torvalds B4.S5 pii_encryption_enabled) |
| `category.py`, `product.py`, `product_*.py`, `bundle.py`, `formula.py`, `container.py`, `delivery_zone.py`, `damage_type.py` | 🔵 Page | Bloc 4 |
| `stock_item.py`, `stock_management.py`, `inventory_movement.py`, `movement_*.py` | 🔵 Page | B4.S2 |
| `devis.py`, `reservation*.py`, `invoice*.py`, `vente.py`, `payment.py`, `pricing.py`, `deposit.py`, `relance.py`, `loyalty.py` | 🔵 Page | Bloc 3 + B4.S4 |
| `evenements.py`, `customer.py` | 🟡 Coordination | Page propriétaire mais Torvalds touche pour PII |
| `audit_log.py`, `audit_log_key.py` (NEW) | 🟡 Coordination | Page B1.S1 (modèles base + colonnes hmac_value/hmac_key_version/prev_hash nullable) **avant** Torvalds B6.S2 (NOT NULL + trigger immutability + chain) |
| `notification.py` | 🟢 Torvalds | B6.S1 |
| `feature_flag.py` | 🟢 Torvalds | B6.S4 |
| `restaurant/*`, `epicerie/*` | 🟢 Torvalds | Bloc 5 |
| `supplier*.py` | 🟢 Torvalds | B3.S7 |

### `app/core/`

| Fichier | Owner | Sprint |
|---|---|---|
| `database.py`, `redis.py`, `cache.py` | 🔵 Page | B1.S1, B1.S2, B1.S4 |
| `security.py`, `crypto.py`, `password_policy.py` | 🟢 Torvalds | B2 + B4.S5 KMS |
| `permissions.py`, `deps.py` | 🟢 Torvalds | B2 |
| `config.py` | 🟡 Coordination | Page ajoute config Bloc 1, Torvalds config Bloc 2/6 |
| `health.py` | 🟢 Torvalds | B6.S6 |
| `rate_limiter.py`, `rate_limit_utils.py` | 🟢 Torvalds | B6.S6 |
| `exceptions.py` | 🟡 Coordination | Append-only, ajout par les deux devs |

### `app/middleware/`

| Fichier | Owner | Sprint |
|---|---|---|
| `audit.py` | 🟡 Coordination | Page B1.S1 (middleware base : capture mutations + dispatch service.append_log) **avant** Torvalds B6.S2 (HMAC chain enforcement) |
| `security.py` | 🟢 Torvalds | B6.S2 |
| `request_context.py` | 🟢 Torvalds | B2 |
| `exception_handler.py` | 🟡 Coordination | rare, append-only |

### `app/middleware/degraded_mode.py` (NEW)

🔵 Page — B1.S4.T2 (cache LRU TTL 5s).

### `app/tasks/` (Celery)

| Fichier | Owner | Sprint |
|---|---|---|
| `celery_app.py`, `monitoring.py` | 🟢 Torvalds | B6.S7 RabbitMQ |
| `relances.py`, `invoicing.py` | 🔵 Page | B3.S6 |
| `loyalty.py` | 🔵 Page | B4.S4 |
| `notifications.py` | 🟡 Coordination | Voir `app/services/notification.py` |
| `etl_tasks.py` | 🟢 Torvalds | B5.S2 |
| `restaurant_export.py` | 🟢 Torvalds | B5.S5 |
| `printing.py` | 🟢 Torvalds | B6.S5 |
| `risk_detection.py` | 🟢 Torvalds | B6.S2 |
| `access_review.py` | 🟡 Coordination | Page B1.S1 (task base + seed access_reviews table) **avant** Torvalds B6.S2 (alerting + cascade revoke) |

### `app/permissions/`

🟢 Torvalds — B2.S3 (catalog scopes). Page importe `Scope.X` (read-only).

### `alembic/versions/`

**Convention** : nommer les fichiers avec préfixe `<owner>_` quand ambigu.
- 🔵 Page : migrations Bloc 1, 3, 4 (ex: `2026_05_01_0900_b1_setup_audit.py`)
- 🟢 Torvalds : migrations Bloc 2, 5, 6, 7 (ex: `2026_05_19_0900_b2_create_verticals.py`)

**Risque collision `down_revision`** : chacun travaille sur son propre lignage de migrations. À la fin de la refonte, le Lead reconcile les 2 lignages en un graphe unique.

### Schemas Pydantic `app/schemas/`

Suit la même partition que `app/models/`.

---

## Frontend

### `frontend/`

🟢 **Torvalds** — Bloc 7 entier (B7.S1-S4) :
- Verticals rename (drop `app_code`, use `vertical`)
- AppSelector refonte
- Monorepo organisation (apps/marveline, apps/restaurant, apps/epicerie, apps/splendid)
- White-label per-tenant (brand_logo, brand_primary_color)

🔵 Page touche le frontend uniquement si un endpoint backend qu'il modifie change le contrat OpenAPI ; dans ce cas, il **ouvre une issue** que Torvalds traite côté UI.

---

## Tests

### `tests/unit/`, `tests/integration/`, `tests/e2e/`, `tests/security/`

Suit la même partition que les services/modèles testés.

**Conventions partagées** (pas de chevauchement) :
- `tests/conftest.py` racine : 🟡 Coordination (append fixtures, jamais override)
- `tests/factories.py` : 🟡 Coordination (append factories, jamais break signature existante)
- `tests/security/test_*.py` : 🟢 Torvalds (B2.S5 + B6.S2)
- `tests/integration/test_<domain>.py` : owner = owner du domain

---

## Documents racine

| Fichier | Owner |
|---|---|
| `CONTRIBUTING.md` | 🟡 Coordination (modifs majeures = sync) |
| `ZONES.md` | 🟡 Coordination |
| `PLAN_PAGE.md` | 🔵 Page (dans branche `Page` uniquement) |
| `PLAN_TORVALDS.md` | 🟢 Torvalds (dans branche `Torvalds` uniquement) |
| `REFACTOR_ROADMAP.md` | 🟡 Coordination (vue globale) |
| `CLAUDE.md` | 🟡 Coordination (rare) |
| `Makefile`, `Dockerfile`, `docker-compose.yml` | 🟡 Coordination |
| `.env.example` | 🟡 Coordination (append uniquement) |
| `pyproject.toml`, `requirements*.txt` | 🟡 Coordination (annoncer ajout deps en daily) |
| `.github/workflows/ci.yml` | 🟡 Coordination |

---

## Procédure conflit zone partagée

1. **Annoncer 24h avant** d'entrer dans une zone 🟡 (daily standup ou Slack)
2. **Attendre confirmation** de l'autre dev (pas de WIP en cours côté lui)
3. **Pull origin de TA branche** juste avant de coder
4. **Commit + push immédiat** une fois la zone touchée (libère le lock virtuel)
5. **Rebase si nécessaire** sur ta propre branche (jamais sur `main`)

Si conflit Git malgré tout :
- Résoudre **localement** sur ta branche
- **Jamais** `git checkout --theirs/--ours` aveugle — comprendre les 2 changements
- En cas de doute : Lead arbitre

---

## Historique mises à jour

| Date | Auteur | Changement |
|---|---|---|
| 2026-04-28 | Lead | Création initiale, partition Bloc 1+3+4 vs Bloc 2+5+6+7 |
| 2026-04-28 | Page | Clarification audit/access_reviews : base modèle/table/helper en B1.S1 (Page) cohérent PLAN_PAGE.md §28-34 ; HMAC chain + verify reste B6.S2 (Torvalds). Entrées passées de 🟢 à 🟡. Annonce Torvalds requise en daily avant entrée dans la zone. |

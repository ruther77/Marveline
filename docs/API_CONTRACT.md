# API Contract — CaroCorp

> Auto-generated on 2026-02-15 18:05 UTC by `scripts/export_openapi.py`
> Version: 0.1.0
> **NE PAS MODIFIER MANUELLEMENT** — relancer `make sync-api-types`

## Endpoints

### API Keys

| Method | Path | Summary |
|--------|------|---------|
| `POST` | `/api/v1/api-keys` | Create Api Key |
| `GET` | `/api/v1/api-keys` | List Api Keys |
| `GET` | `/api/v1/api-keys/{api_key_id}` | Get Api Key |
| `PATCH` | `/api/v1/api-keys/{api_key_id}` | Update Api Key |
| `DELETE` | `/api/v1/api-keys/{api_key_id}` | Revoke Api Key |
| `POST` | `/api/v1/api-keys/{api_key_id}/rotate` | Rotate Api Key |

### Audit

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/audit` | List Audit Logs |
| `GET` | `/api/v1/audit/entity/{entity_type}/{entity_id}` | Get Entity Audit Trail |
| `GET` | `/api/v1/audit/user/{user_id}` | Get User Audit Trail |

### Authentication

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/auth/csrf` | Get Csrf Token |
| `POST` | `/api/v1/auth/login` | Login |
| `POST` | `/api/v1/auth/logout` | Logout |
| `GET` | `/api/v1/auth/me` | Get Current User Info |
| `POST` | `/api/v1/auth/refresh` | Refresh Token |

### Bundles

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/bundles` | List Bundles |
| `POST` | `/api/v1/bundles` | Create Bundle |
| `GET` | `/api/v1/bundles/{bundle_id}` | Get Bundle |
| `PATCH` | `/api/v1/bundles/{bundle_id}` | Update Bundle |
| `DELETE` | `/api/v1/bundles/{bundle_id}` | Delete Bundle |
| `GET` | `/api/v1/bundles/{bundle_id}/calculate-price` | Calculate Bundle Price |
| `POST` | `/api/v1/bundles/{bundle_id}/items` | Add Bundle Item |
| `PATCH` | `/api/v1/bundles/{bundle_id}/items/{item_id}` | Update Bundle Item |
| `DELETE` | `/api/v1/bundles/{bundle_id}/items/{item_id}` | Remove Bundle Item |

### Categories

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/categories` | List Categories |
| `POST` | `/api/v1/categories` | Create Category |
| `GET` | `/api/v1/categories/tree` | Get Category Tree |
| `GET` | `/api/v1/categories/{category_id}` | Get Category |
| `PATCH` | `/api/v1/categories/{category_id}` | Update Category |
| `DELETE` | `/api/v1/categories/{category_id}` | Delete Category |

### Customers

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/customers` | List Customers |
| `POST` | `/api/v1/customers` | Create Customer |
| `GET` | `/api/v1/customers/{customer_id}` | Get Customer |
| `PATCH` | `/api/v1/customers/{customer_id}` | Update Customer |
| `DELETE` | `/api/v1/customers/{customer_id}` | Delete Customer |

### Feature Flags

| Method | Path | Summary |
|--------|------|---------|
| `POST` | `/api/v1/features` | Create Feature Flag |
| `GET` | `/api/v1/features` | List Feature Flags |
| `GET` | `/api/v1/features/check/{flag_name}` | Check Feature Flag |
| `GET` | `/api/v1/features/{flag_id}` | Get Feature Flag |
| `PATCH` | `/api/v1/features/{flag_id}` | Update Feature Flag |
| `DELETE` | `/api/v1/features/{flag_id}` | Delete Feature Flag |

### Health

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/health` | Health Check |
| `GET` | `/api/v1/health/live` | Liveness Probe |
| `GET` | `/api/v1/health/ready` | Readiness Probe |

### Invoices

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/invoices` | List Invoices |
| `POST` | `/api/v1/invoices` | Create Invoice |
| `GET` | `/api/v1/invoices/overdue` | List Overdue Invoices |
| `GET` | `/api/v1/invoices/{invoice_id}` | Get Invoice |
| `PATCH` | `/api/v1/invoices/{invoice_id}` | Update Invoice |
| `POST` | `/api/v1/invoices/{invoice_id}/add-payment` | Add Payment |
| `POST` | `/api/v1/invoices/{invoice_id}/cancel` | Cancel Invoice |

### MFA

| Method | Path | Summary |
|--------|------|---------|
| `DELETE` | `/api/v1/mfa` | Disable Mfa |
| `POST` | `/api/v1/mfa/setup` | Setup Mfa |
| `GET` | `/api/v1/mfa/status` | Mfa Status |
| `POST` | `/api/v1/mfa/verify` | Verify Mfa |
| `POST` | `/api/v1/mfa/verify-setup` | Verify Setup |

### Other

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/` | Root |
| `GET` | `/metrics` | Metrics |

### Products

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/products` | List Products |
| `POST` | `/api/v1/products` | Create Product |
| `GET` | `/api/v1/products/{product_id}` | Get Product |
| `PATCH` | `/api/v1/products/{product_id}` | Update Product |
| `DELETE` | `/api/v1/products/{product_id}` | Delete Product |

### Reservations

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/reservations` | List Reservations |
| `POST` | `/api/v1/reservations` | Create Reservation |
| `GET` | `/api/v1/reservations/{reservation_id}` | Get Reservation |
| `PATCH` | `/api/v1/reservations/{reservation_id}` | Update Reservation |
| `POST` | `/api/v1/reservations/{reservation_id}/cancel` | Cancel Reservation |
| `POST` | `/api/v1/reservations/{reservation_id}/confirm` | Confirm Reservation |

### Sessions

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/sessions` | List Sessions |
| `DELETE` | `/api/v1/sessions` | Revoke All Sessions |
| `DELETE` | `/api/v1/sessions/{session_id}` | Revoke Session |

### Users

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/users/me` | Get My Profile |
| `PATCH` | `/api/v1/users/me` | Update My Profile |

### VPN

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/vpn/ip-pools` | List Vpn Ip Pools |
| `POST` | `/api/v1/vpn/ip-pools` | Create Vpn Ip Pool |
| `GET` | `/api/v1/vpn/peers` | List Vpn Peers |
| `POST` | `/api/v1/vpn/peers` | Create Vpn Peer |
| `GET` | `/api/v1/vpn/peers/{peer_id}` | Get Vpn Peer |
| `PATCH` | `/api/v1/vpn/peers/{peer_id}` | Update Vpn Peer |
| `DELETE` | `/api/v1/vpn/peers/{peer_id}` | Delete Vpn Peer |
| `GET` | `/api/v1/vpn/peers/{peer_id}/config` | Get Vpn Peer Config |
| `POST` | `/api/v1/vpn/peers/{peer_id}/disable` | Disable Vpn Peer |
| `POST` | `/api/v1/vpn/peers/{peer_id}/enable` | Enable Vpn Peer |
| `GET` | `/api/v1/vpn/peers/{peer_id}/qrcode` | Get Vpn Peer Qrcode |
| `POST` | `/api/v1/vpn/peers/{peer_id}/rotate` | Rotate Vpn Peer Keys |
| `GET` | `/api/v1/vpn/status` | Get Vpn Status |

## Schemas (Pydantic Models)

### `AddPaymentRequest`

_Schema pour ajouter un paiement à une facture.

Utilisé par l'endpoint POST /invoices/{id}/add-payment.

Example:
    {
        "amount_cents": 50000,
        "payment_method": "card",
        "payment_date": "2026-01-20"
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `amount_cents` | `integer` | Yes | - |
| `payment_method` | `PaymentMethod` | Yes | - |
| `payment_date` | `string` | Yes | - |

### `ApiKeyCreate`

_Schema pour creation d'une API key.

Example:
    POST /api/v1/api-keys
    {
        "name": "Caisse magasin 1",
        "scopes": ["products:read", "inventory:read"],
        "rate_limit": 500,
        "expires_at": "2027-01-01T00:00:00Z"
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `name` | `string` | Yes | - |
| `scopes` | `string[]` | Yes | - |
| `rate_limit` | `integer | null` | No | `1000` |
| `expires_at` | `datetime | null` | No | - |

### `ApiKeyCreated`

_Schema pour reponse de creation/rotation (avec full key).

Le full_key n'est visible QU'UNE SEULE FOIS (create ou rotate)._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `is_active` | `boolean` | No | `True` |
| `tenant_id` | `integer` | Yes | - |
| `created_at` | `datetime` | Yes | - |
| `updated_at` | `datetime` | Yes | - |
| `id` | `integer` | Yes | - |
| `name` | `string` | Yes | - |
| `key_prefix` | `string` | Yes | - |
| `scopes` | `string[]` | Yes | - |
| `rate_limit` | `integer | null` | No | - |
| `expires_at` | `datetime | null` | No | - |
| `last_used_at` | `datetime | null` | No | - |
| `last_used_ip` | `string | null` | No | - |
| `usage_count` | `integer` | No | `0` |
| `created_by` | `integer` | Yes | - |
| `full_key` | `string` | Yes | - |

### `ApiKeyList`

_Schema simplifie pour listing des API keys._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `id` | `integer` | Yes | - |
| `name` | `string` | Yes | - |
| `key_prefix` | `string` | Yes | - |
| `scopes` | `string[]` | Yes | - |
| `is_active` | `boolean` | Yes | - |
| `last_used_at` | `datetime | null` | No | - |
| `usage_count` | `integer` | No | `0` |
| `created_at` | `datetime` | Yes | - |

### `ApiKeyResponse`

_Schema pour reponse API key (sans le full key).

Example:
    {
        "id": 1,
        "name": "Caisse magasin 1",
        "key_prefix": "mk_live_a1b2",
        "scopes": ["products:read", "inventory:read"],
        "rate_limit": 500,
        "expires_at": "2027-01-01T00:00:00Z",
        "is_active": true,
        "last_used_at": null,
        "usage_count": 0,
        "created_by": 1,
        "created_at": "2026-02-15T10:00:00Z",
        "updated_at": "2026-02-15T10:00:00Z"
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `is_active` | `boolean` | No | `True` |
| `tenant_id` | `integer` | Yes | - |
| `created_at` | `datetime` | Yes | - |
| `updated_at` | `datetime` | Yes | - |
| `id` | `integer` | Yes | - |
| `name` | `string` | Yes | - |
| `key_prefix` | `string` | Yes | - |
| `scopes` | `string[]` | Yes | - |
| `rate_limit` | `integer | null` | No | - |
| `expires_at` | `datetime | null` | No | - |
| `last_used_at` | `datetime | null` | No | - |
| `last_used_ip` | `string | null` | No | - |
| `usage_count` | `integer` | No | `0` |
| `created_by` | `integer` | Yes | - |

### `ApiKeyUpdate`

_Schema pour mise a jour partielle d'une API key.

Example:
    PATCH /api/v1/api-keys/1
    {
        "name": "Caisse magasin 2",
        "scopes": ["products:read"],
        "is_active": false
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `name` | `string | null` | No | - |
| `scopes` | `string[] | null` | No | - |
| `rate_limit` | `integer | null` | No | - |
| `is_active` | `boolean | null` | No | - |

### `AuditLogList`

_Schema pour liste d'audit logs avec pagination.

Example:
    {
        "logs": [...],
        "total": 150,
        "skip": 0,
        "limit": 100
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `logs` | `AuditLogResponse[]` | Yes | - |
| `total` | `integer` | Yes | - |
| `skip` | `integer` | No | `0` |
| `limit` | `integer` | No | `100` |

### `AuditLogResponse`

_Schema pour réponse d'un audit log individuel.

Example:
    {
        "id": 123,
        "user_id": 42,
        "tenant_id": 1,
        "action": "UPDATE",
        "entity_type": "Reservation",
        "entity_id": 456,
        "changes": {
            "status": {"before": "draft", "after": "confirmed"}
        },
        "description": "Updated Reservation #456: status",
        "ip_address": "192.168.1.100",
        "user_agent": "Mozilla/5.0...",
        "request_id": "550e8400-e29b-41d4-a716-446655440000",
        "created_at": "2026-02-12T14:30:00Z"
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `id` | `integer` | Yes | - |
| `user_id` | `integer | null` | No | - |
| `tenant_id` | `integer` | Yes | - |
| `action` | `string` | Yes | - |
| `entity_type` | `string | null` | No | - |
| `entity_id` | `integer | null` | No | - |
| `changes` | `object | null` | No | - |
| `description` | `string | null` | No | - |
| `ip_address` | `string | null` | No | - |
| `user_agent` | `string | null` | No | - |
| `request_id` | `string | null` | No | - |
| `created_at` | `datetime` | Yes | - |

### `Body_login_api_v1_auth_login_post`

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `grant_type` | `string | null` | No | - |
| `username` | `string` | Yes | - |
| `password` | `string` | Yes | - |
| `scope` | `string` | No | `` |
| `client_id` | `string | null` | No | - |
| `client_secret` | `string | null` | No | - |

### `BundleCreate`

_Schema pour creation d'un nouveau bundle._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `name` | `string` | Yes | - |
| `slug` | `string | null` | No | - |
| `description` | `string | null` | No | - |
| `short_description` | `string | null` | No | - |
| `bundle_price_cents` | `integer` | Yes | - |
| `cleaning_fee_cents` | `integer` | No | `0` |
| `featured` | `boolean` | No | `False` |
| `display_order` | `integer` | No | `0` |
| `image_url` | `string | null` | No | - |

### `BundleItemCreate`

_Schema pour ajouter un item au bundle._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `product_id` | `integer` | Yes | - |
| `quantity` | `integer` | No | `1` |
| `display_order` | `integer` | No | `0` |

### `BundleItemResponse`

_Schema de reponse pour un item de bundle._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `id` | `integer` | Yes | - |
| `bundle_id` | `integer` | Yes | - |
| `product_id` | `integer` | Yes | - |
| `quantity` | `integer` | Yes | - |
| `display_order` | `integer` | Yes | - |
| `product` | `ProductList` | Yes | - |

### `BundleItemUpdate`

_Schema pour mise a jour d'un item du bundle._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `quantity` | `integer | null` | No | - |
| `display_order` | `integer | null` | No | - |

### `BundlePriceResponse`

_Schema de reponse pour le calcul de prix._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `bundle_price_cents` | `integer` | Yes | - |
| `individual_price_cents` | `integer` | Yes | - |
| `savings_cents` | `integer` | Yes | - |
| `savings_percent` | `number` | Yes | - |
| `items` | `object[]` | Yes | - |

### `BundleResponse`

_Schema de reponse pour un bundle (sans items)._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `is_active` | `boolean` | No | `True` |
| `tenant_id` | `integer` | Yes | - |
| `created_at` | `datetime` | Yes | - |
| `updated_at` | `datetime` | Yes | - |
| `id` | `integer` | Yes | - |
| `name` | `string` | Yes | - |
| `slug` | `string` | Yes | - |
| `description` | `string | null` | No | - |
| `short_description` | `string | null` | No | - |
| `bundle_price_cents` | `integer` | Yes | - |
| `cleaning_fee_cents` | `integer` | Yes | - |
| `featured` | `boolean` | Yes | - |
| `display_order` | `integer` | Yes | - |
| `image_url` | `string | null` | No | - |
| `bundle_price_euros` | `number` | Yes | - |
| `cleaning_fee_euros` | `number` | Yes | - |

### `BundleUpdate`

_Schema pour mise a jour d'un bundle (PATCH partiel)._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `name` | `string | null` | No | - |
| `slug` | `string | null` | No | - |
| `description` | `string | null` | No | - |
| `short_description` | `string | null` | No | - |
| `bundle_price_cents` | `integer | null` | No | - |
| `cleaning_fee_cents` | `integer | null` | No | - |
| `featured` | `boolean | null` | No | - |
| `display_order` | `integer | null` | No | - |
| `image_url` | `string | null` | No | - |
| `is_active` | `boolean | null` | No | - |

### `BundleWithItems`

_Schema de reponse pour un bundle avec ses items._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `is_active` | `boolean` | No | `True` |
| `tenant_id` | `integer` | Yes | - |
| `created_at` | `datetime` | Yes | - |
| `updated_at` | `datetime` | Yes | - |
| `id` | `integer` | Yes | - |
| `name` | `string` | Yes | - |
| `slug` | `string` | Yes | - |
| `description` | `string | null` | No | - |
| `short_description` | `string | null` | No | - |
| `bundle_price_cents` | `integer` | Yes | - |
| `cleaning_fee_cents` | `integer` | Yes | - |
| `featured` | `boolean` | Yes | - |
| `display_order` | `integer` | Yes | - |
| `image_url` | `string | null` | No | - |
| `items` | `BundleItemResponse[]` | No | `[]` |
| `bundle_price_euros` | `number` | Yes | - |
| `cleaning_fee_euros` | `number` | Yes | - |
| `total_items` | `integer` | Yes | - |
| `individual_price_cents` | `integer` | Yes | - |
| `savings_cents` | `integer` | Yes | - |
| `individual_price_euros` | `number` | Yes | - |
| `savings_euros` | `number` | Yes | - |

### `CSRFTokenResponse`

_Schema pour réponse de génération de token CSRF.

Example:
    GET /auth/csrf
    Response:
    {
        "csrf_token": "abc123xyz789...",
        "expires_in": 900
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `csrf_token` | `string` | Yes | - |
| `expires_in` | `integer` | No | `900` |

### `CategoryCreate`

_Schema pour creation d'une nouvelle categorie._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `name` | `string` | Yes | - |
| `slug` | `string | null` | No | - |
| `description` | `string | null` | No | - |
| `parent_id` | `integer | null` | No | - |
| `image_url` | `string | null` | No | - |
| `display_order` | `integer` | No | `0` |

### `CategoryResponse`

_Schema de reponse pour une categorie._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `is_active` | `boolean` | No | `True` |
| `tenant_id` | `integer` | Yes | - |
| `created_at` | `datetime` | Yes | - |
| `updated_at` | `datetime` | Yes | - |
| `id` | `integer` | Yes | - |
| `name` | `string` | Yes | - |
| `slug` | `string` | Yes | - |
| `description` | `string | null` | No | - |
| `parent_id` | `integer | null` | No | - |
| `image_url` | `string | null` | No | - |
| `display_order` | `integer` | Yes | - |

### `CategoryTreeNode`

_Schema pour un noeud d'arbre hierarchique de categories._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `is_active` | `boolean` | No | `True` |
| `tenant_id` | `integer` | Yes | - |
| `created_at` | `datetime` | Yes | - |
| `updated_at` | `datetime` | Yes | - |
| `id` | `integer` | Yes | - |
| `name` | `string` | Yes | - |
| `slug` | `string` | Yes | - |
| `description` | `string | null` | No | - |
| `parent_id` | `integer | null` | No | - |
| `image_url` | `string | null` | No | - |
| `display_order` | `integer` | Yes | - |
| `children` | `CategoryTreeNode[]` | No | `[]` |
| `product_count` | `integer` | No | `0` |

### `CategoryUpdate`

_Schema pour mise a jour d'une categorie (PATCH partiel)._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `name` | `string | null` | No | - |
| `slug` | `string | null` | No | - |
| `description` | `string | null` | No | - |
| `parent_id` | `integer | null` | No | - |
| `image_url` | `string | null` | No | - |
| `display_order` | `integer | null` | No | - |
| `is_active` | `boolean | null` | No | - |

### `CustomerCreate`

_Schema pour création d'un nouveau client.

Le tenant_id sera automatiquement ajouté depuis le JWT du user connecté.

Example:
    {
        "customer_type": "individual",
        "first_name": "Jean",
        "last_name": "Dupont",
        "email": "jean.dupont@example.com",
        "phone": "+33612345678",
        "address": "123 Rue de la Paix",
        "city": "Paris",
        "postal_code": "75001",
        "country": "France"
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `customer_type` | `CustomerType` | Yes | - |
| `email` | `email` | Yes | - |
| `phone` | `string | null` | No | - |
| `first_name` | `string | null` | No | - |
| `last_name` | `string | null` | No | - |
| `company_name` | `string | null` | No | - |
| `address` | `string | null` | No | - |
| `city` | `string | null` | No | - |
| `postal_code` | `string | null` | No | - |
| `country` | `string` | No | `France` |

### `CustomerList`

_Schema simplifié pour listes de clients (sans relations)._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `is_active` | `boolean` | No | `True` |
| `tenant_id` | `integer` | Yes | - |
| `created_at` | `datetime` | Yes | - |
| `updated_at` | `datetime` | Yes | - |
| `id` | `integer` | Yes | - |
| `customer_type` | `string` | Yes | - |
| `email` | `string` | Yes | - |
| `phone` | `string | null` | No | - |
| `first_name` | `string | null` | No | - |
| `last_name` | `string | null` | No | - |
| `company_name` | `string | null` | No | - |
| `city` | `string | null` | No | - |
| `country` | `string` | Yes | - |

### `CustomerResponse`

_Schema complet pour réponse détaillée d'un client._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `is_active` | `boolean` | No | `True` |
| `tenant_id` | `integer` | Yes | - |
| `created_at` | `datetime` | Yes | - |
| `updated_at` | `datetime` | Yes | - |
| `id` | `integer` | Yes | - |
| `customer_type` | `string` | Yes | - |
| `email` | `string` | Yes | - |
| `phone` | `string | null` | No | - |
| `first_name` | `string | null` | No | - |
| `last_name` | `string | null` | No | - |
| `company_name` | `string | null` | No | - |
| `address` | `string | null` | No | - |
| `city` | `string | null` | No | - |
| `postal_code` | `string | null` | No | - |
| `country` | `string` | Yes | - |

### `CustomerType`

_Type de client (particulier ou entreprise).

Utilisé dans :
    - models.Customer.customer_type
    - schemas.CustomerCreate.customer_type
    - Logique de validation (SIRET obligatoire si COMPANY)_

**Values:** `individual`, `company`

### `CustomerUpdate`

_Schema pour mise à jour d'un client existant.

Tous les champs sont optionnels (PATCH partiel).
customer_type est immutable (ne peut pas être changé après création).

Example:
    {
        "phone": "+33698765432",
        "address": "456 Avenue des Champs",
        "city": "Lyon"
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `email` | `email | null` | No | - |
| `phone` | `string | null` | No | - |
| `first_name` | `string | null` | No | - |
| `last_name` | `string | null` | No | - |
| `company_name` | `string | null` | No | - |
| `address` | `string | null` | No | - |
| `city` | `string | null` | No | - |
| `postal_code` | `string | null` | No | - |
| `country` | `string | null` | No | - |

### `FeatureFlagCreate`

_Schema pour creation d'un feature flag.

Example:
    POST /api/v1/features
    {
        "name": "stripe_payments",
        "description": "Active Stripe Checkout pour le tenant",
        "is_enabled": true,
        "target_tenants": [1, 2],
        "rollout_pct": 100
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `name` | `string` | Yes | - |
| `description` | `string | null` | No | - |
| `is_enabled` | `boolean` | No | `False` |
| `target_tenants` | `integer[] | null` | No | - |
| `rollout_pct` | `integer` | No | `100` |
| `metadata_json` | `object | null` | No | - |

### `FeatureFlagEvaluated`

_Schema pour resultat d'evaluation d'un flag pour un tenant.

Example:
    GET /api/v1/features/check/stripe_payments?tenant_id=1
    {
        "name": "stripe_payments",
        "enabled": true,
        "reason": "whitelist"
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `name` | `string` | Yes | - |
| `enabled` | `boolean` | Yes | - |
| `reason` | `string` | Yes | - |

### `FeatureFlagList`

_Schema simplifie pour listing des feature flags._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `id` | `integer` | Yes | - |
| `name` | `string` | Yes | - |
| `description` | `string | null` | No | - |
| `is_enabled` | `boolean` | Yes | - |
| `target_tenants` | `integer[] | null` | No | - |
| `rollout_pct` | `integer` | Yes | - |
| `created_at` | `datetime` | Yes | - |

### `FeatureFlagResponse`

_Schema pour reponse complete d'un feature flag.

Example:
    {
        "id": 1,
        "name": "stripe_payments",
        "description": "Active Stripe Checkout",
        "is_enabled": true,
        "target_tenants": [1, 2],
        "rollout_pct": 100,
        "metadata_json": {"tier": "premium"},
        "created_at": "2026-02-15T10:00:00Z",
        "updated_at": "2026-02-15T10:00:00Z"
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `created_at` | `datetime` | Yes | - |
| `updated_at` | `datetime` | Yes | - |
| `id` | `integer` | Yes | - |
| `name` | `string` | Yes | - |
| `description` | `string | null` | No | - |
| `is_enabled` | `boolean` | Yes | - |
| `target_tenants` | `integer[] | null` | No | - |
| `rollout_pct` | `integer` | Yes | - |
| `metadata_json` | `object | null` | No | - |

### `FeatureFlagUpdate`

_Schema pour mise a jour partielle d'un feature flag.

Example:
    PATCH /api/v1/features/1
    {
        "is_enabled": false,
        "rollout_pct": 50
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `description` | `string | null` | No | - |
| `is_enabled` | `boolean | null` | No | - |
| `target_tenants` | `integer[] | null` | No | - |
| `rollout_pct` | `integer | null` | No | - |
| `metadata_json` | `object | null` | No | - |

### `InvoiceCreate`

_Schema pour création d'une facture.

Le invoice_number sera généré automatiquement (Redis INCR).
Le total_amount sera copié depuis la réservation.
Le status sera initialisé à 'draft'.

Example:
    {
        "reservation_id": 1,
        "issue_date": "2026-01-15",
        "due_date": "2026-01-30"
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `issue_date` | `string` | Yes | - |
| `due_date` | `string` | Yes | - |
| `reservation_id` | `integer` | Yes | - |

### `InvoiceList`

_Schema simplifié pour listes de factures._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `is_active` | `boolean` | No | `True` |
| `tenant_id` | `integer` | Yes | - |
| `created_at` | `datetime` | Yes | - |
| `updated_at` | `datetime` | Yes | - |
| `id` | `integer` | Yes | - |
| `reservation_id` | `integer` | Yes | - |
| `invoice_number` | `string` | Yes | - |
| `issue_date` | `string` | Yes | - |
| `due_date` | `string` | Yes | - |
| `status` | `string` | Yes | - |
| `total_amount_cents` | `integer` | Yes | - |
| `paid_amount_cents` | `integer` | Yes | - |
| `total_amount_euros` | `number` | Yes | - |
| `paid_amount_euros` | `number` | Yes | - |
| `is_paid` | `boolean` | Yes | - |
| `is_overdue` | `boolean` | Yes | - |

### `InvoiceResponse`

_Schema complet pour réponse détaillée d'une facture._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `is_active` | `boolean` | No | `True` |
| `tenant_id` | `integer` | Yes | - |
| `created_at` | `datetime` | Yes | - |
| `updated_at` | `datetime` | Yes | - |
| `id` | `integer` | Yes | - |
| `reservation_id` | `integer` | Yes | - |
| `invoice_number` | `string` | Yes | - |
| `issue_date` | `string` | Yes | - |
| `due_date` | `string` | Yes | - |
| `total_amount_cents` | `integer` | Yes | - |
| `paid_amount_cents` | `integer` | Yes | - |
| `status` | `InvoiceStatus` | Yes | - |
| `payment_method` | `string | null` | No | - |
| `payment_date` | `string | null` | No | - |
| `reservation` | `ReservationList | null` | No | - |
| `total_amount_euros` | `number` | Yes | - |
| `paid_amount_euros` | `number` | Yes | - |
| `remaining_amount_cents` | `integer` | Yes | - |
| `remaining_amount_euros` | `number` | Yes | - |
| `is_paid` | `boolean` | Yes | - |
| `is_overdue` | `boolean` | Yes | - |
| `payment_completion_percentage` | `number` | Yes | - |

### `InvoiceStatus`

_Statut du cycle de vie d'une facture.

Workflow :
    DRAFT → SENT → PAID
                ↘ OVERDUE
    Tout statut → CANCELLED

Utilisé dans :
    - models.Invoice.status
    - services.InvoiceService (calcul auto-overdue)
    - Filtres API GET /invoices?status=..._

**Values:** `draft`, `sent`, `paid`, `overdue`, `cancelled`

### `InvoiceUpdate`

_Schema pour mise à jour d'une facture.

Tous les champs sont optionnels (PATCH partiel).
reservation_id et invoice_number sont immutables.

Example:
    {
        "status": "sent",
        "due_date": "2026-02-15"
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `issue_date` | `string | null` | No | - |
| `due_date` | `string | null` | No | - |
| `status` | `InvoiceStatus | null` | No | - |

### `LogoutRequest`

_Schema pour requête de logout.

Example:
    POST /auth/logout
    {
        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `refresh_token` | `string` | No | - |

### `LogoutResponse`

_Schema pour réponse de logout.

Example:
    {
        "message": "Logged out successfully",
        "tokens_revoked": true
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `message` | `string` | No | `Logged out successfully` |
| `tokens_revoked` | `boolean` | No | `True` |

### `MFADisableResponse`

_Réponse après désactivation du MFA._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `disabled` | `boolean` | No | `True` |
| `message` | `string` | No | `MFA disabled successfully` |

### `MFASetupResponse`

_Réponse du setup MFA — contient le secret et l'URI QR code._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `secret` | `string` | Yes | - |
| `provisioning_uri` | `string` | Yes | - |
| `recovery_codes` | `string[]` | Yes | - |

### `MFAStatusResponse`

_Réponse pour le statut MFA d'un utilisateur._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `mfa_enabled` | `boolean` | Yes | - |
| `recovery_codes_remaining` | `integer` | No | `0` |

### `MFAVerifyRequest`

_Requête pour vérifier un code MFA lors du login (step 2)._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `mfa_session_token` | `string` | Yes | - |
| `totp_code` | `string | null` | No | - |
| `recovery_code` | `string | null` | No | - |

### `MFAVerifySetupRequest`

_Requête pour valider le setup MFA (premier code TOTP)._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `totp_code` | `string` | Yes | - |

### `MFAVerifySetupResponse`

_Réponse après validation du setup MFA._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `enabled` | `boolean` | No | `True` |
| `message` | `string` | No | `MFA enabled successfully` |

### `PaginatedResponse_ApiKeyList_`

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `items` | `ApiKeyList[]` | Yes | - |
| `total` | `integer` | Yes | - |
| `skip` | `integer` | Yes | - |
| `limit` | `integer` | Yes | - |

### `PaginatedResponse_BundleResponse_`

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `items` | `BundleResponse[]` | Yes | - |
| `total` | `integer` | Yes | - |
| `skip` | `integer` | Yes | - |
| `limit` | `integer` | Yes | - |

### `PaginatedResponse_CategoryResponse_`

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `items` | `CategoryResponse[]` | Yes | - |
| `total` | `integer` | Yes | - |
| `skip` | `integer` | Yes | - |
| `limit` | `integer` | Yes | - |

### `PaginatedResponse_CustomerList_`

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `items` | `CustomerList[]` | Yes | - |
| `total` | `integer` | Yes | - |
| `skip` | `integer` | Yes | - |
| `limit` | `integer` | Yes | - |

### `PaginatedResponse_FeatureFlagList_`

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `items` | `FeatureFlagList[]` | Yes | - |
| `total` | `integer` | Yes | - |
| `skip` | `integer` | Yes | - |
| `limit` | `integer` | Yes | - |

### `PaginatedResponse_InvoiceList_`

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `items` | `InvoiceList[]` | Yes | - |
| `total` | `integer` | Yes | - |
| `skip` | `integer` | Yes | - |
| `limit` | `integer` | Yes | - |

### `PaginatedResponse_ProductList_`

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `items` | `ProductList[]` | Yes | - |
| `total` | `integer` | Yes | - |
| `skip` | `integer` | Yes | - |
| `limit` | `integer` | Yes | - |

### `PaginatedResponse_ReservationList_`

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `items` | `ReservationList[]` | Yes | - |
| `total` | `integer` | Yes | - |
| `skip` | `integer` | Yes | - |
| `limit` | `integer` | Yes | - |

### `PaymentMethod`

_Méthodes de paiement acceptées.

Utilisé dans :
    - models.Payment.payment_method
    - schemas.AddPaymentRequest.payment_method
    - Rapports comptables par méthode_

**Values:** `cash`, `card`, `transfer`, `check`

### `ProductCategory`

_Catégories de produits disponibles à la location.

Correspond aux 20 catégories du catalogue Marveline.

Utilisé dans :
    - models.Product.category
    - schemas.ProductCreate.category
    - Filtres API GET /products?category=..._

**Values:** `accessoires_transport`, `assiettes`, `bancs`, `candy_bar`, `chaises`, `couverts`, `decorations`, `housses`, `machines`, `mange_debout`, `mobilier`, `nappages`, `nappes`, `porcelaine`, `serviettes`, `tables`, `vaisselle`, `vaisselle_service`, `vaisselle_enfants`, `verres`

### `ProductCondition`

_État physique d'un produit.

Utilisé dans :
    - models.Product.condition
    - schemas.ProductCreate.condition
    - Filtres de qualité pour réservations_

**Values:** `neuf`, `bon`, `use`, `hors_service`

### `ProductCreate`

_Schema pour création d'un nouveau produit.

Le tenant_id sera automatiquement ajouté depuis le JWT du user connecté.

Example:
    {
        "name": "Assiette plate blanche 28cm",
        "sku": "ASS-PLATE-28-WHI",
        "category": "assiette",
        "price_per_day_cents": 250,
        "deposit_amount_cents": 500,
        "stock_quantity": 100,
        "available_quantity": 100,
        "condition": "neuf",
        "image_url": "https://cdn.carocorp.com/products/assiette-plate-28.jpg"
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `name` | `string` | Yes | - |
| `sku` | `string` | Yes | - |
| `category` | `ProductCategory` | Yes | - |
| `price_per_day_cents` | `integer` | Yes | - |
| `deposit_amount_cents` | `integer` | No | `0` |
| `stock_quantity` | `integer` | No | `0` |
| `available_quantity` | `integer` | No | `0` |
| `condition` | `ProductCondition` | No | `bon` |
| `image_url` | `string | null` | No | - |

### `ProductList`

_Schema simplifié pour listes de produits._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `is_active` | `boolean` | No | `True` |
| `tenant_id` | `integer` | Yes | - |
| `created_at` | `datetime` | Yes | - |
| `updated_at` | `datetime` | Yes | - |
| `id` | `integer` | Yes | - |
| `name` | `string` | Yes | - |
| `sku` | `string` | Yes | - |
| `category` | `string` | Yes | - |
| `price_per_day_cents` | `integer` | Yes | - |
| `stock_quantity` | `integer` | Yes | - |
| `available_quantity` | `integer` | Yes | - |
| `condition` | `string` | Yes | - |
| `price_per_day_euros` | `number` | Yes | - |
| `is_available` | `boolean` | Yes | - |

### `ProductResponse`

_Schema complet pour réponse détaillée d'un produit._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `is_active` | `boolean` | No | `True` |
| `tenant_id` | `integer` | Yes | - |
| `created_at` | `datetime` | Yes | - |
| `updated_at` | `datetime` | Yes | - |
| `id` | `integer` | Yes | - |
| `name` | `string` | Yes | - |
| `sku` | `string` | Yes | - |
| `category` | `string` | Yes | - |
| `price_per_day_cents` | `integer` | Yes | - |
| `deposit_amount_cents` | `integer` | Yes | - |
| `stock_quantity` | `integer` | Yes | - |
| `available_quantity` | `integer` | Yes | - |
| `condition` | `string` | Yes | - |
| `image_url` | `string | null` | No | - |
| `price_per_day_euros` | `number` | Yes | - |
| `deposit_amount_euros` | `number` | Yes | - |
| `is_available` | `boolean` | Yes | - |
| `is_out_of_stock` | `boolean` | Yes | - |

### `ProductUpdate`

_Schema pour mise à jour d'un produit existant.

Tous les champs sont optionnels (PATCH partiel).
SKU est immutable (ne peut pas être changé après création).

Example:
    {
        "price_per_day_cents": 300,
        "stock_quantity": 150,
        "available_quantity": 120,
        "condition": "bon"
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `name` | `string | null` | No | - |
| `category` | `ProductCategory | null` | No | - |
| `price_per_day_cents` | `integer | null` | No | - |
| `deposit_amount_cents` | `integer | null` | No | - |
| `stock_quantity` | `integer | null` | No | - |
| `available_quantity` | `integer | null` | No | - |
| `condition` | `ProductCondition | null` | No | - |
| `image_url` | `string | null` | No | - |

### `RefreshTokenRequest`

_Schema pour requête de refresh token.

Example:
    POST /auth/refresh
    {
        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `refresh_token` | `string` | Yes | - |

### `ReservationCreate`

_Schema pour création d'une réservation.

Le reference sera généré automatiquement côté service (Redis INCR).
Le status sera initialisé à 'draft'.
Les montants seront calculés depuis les lignes.

Example:
    {
        "customer_id": 1,
        "event_date": "2026-06-15",
        "delivery_date": "2026-06-14",
        "return_date": "2026-06-16",
        "event_location": "Château de Versailles",
        "lines": [
            {"product_id": 1, "quantity": 50},
            {"product_id": 2, "quantity": 100}
        ]
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `customer_id` | `integer` | Yes | - |
| `event_date` | `string` | Yes | - |
| `delivery_date` | `string` | Yes | - |
| `return_date` | `string` | Yes | - |
| `event_location` | `string | null` | No | - |
| `lines` | `ReservationLineCreate[]` | Yes | - |

### `ReservationLineCreate`

_Schema pour création d'une ligne de réservation.

Note: unit_price_cents sera automatiquement récupéré depuis le produit.

Example:
    {
        "product_id": 1,
        "quantity": 50
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `product_id` | `integer` | Yes | - |
| `quantity` | `integer` | Yes | - |

### `ReservationLineResponse`

_Schema complet pour réponse d'une ligne de réservation._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `is_active` | `boolean` | No | `True` |
| `tenant_id` | `integer` | Yes | - |
| `created_at` | `datetime` | Yes | - |
| `updated_at` | `datetime` | Yes | - |
| `id` | `integer` | Yes | - |
| `reservation_id` | `integer` | Yes | - |
| `product_id` | `integer` | Yes | - |
| `quantity` | `integer` | Yes | - |
| `unit_price_cents` | `integer` | Yes | - |
| `subtotal_cents` | `integer` | Yes | - |
| `product` | `ProductList | null` | No | - |
| `unit_price_euros` | `number` | Yes | - |
| `subtotal_euros` | `number` | Yes | - |

### `ReservationList`

_Schema simplifié pour listes de réservations._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `is_active` | `boolean` | No | `True` |
| `tenant_id` | `integer` | Yes | - |
| `created_at` | `datetime` | Yes | - |
| `updated_at` | `datetime` | Yes | - |
| `id` | `integer` | Yes | - |
| `customer_id` | `integer` | Yes | - |
| `reference` | `string` | Yes | - |
| `event_date` | `string` | Yes | - |
| `status` | `string` | Yes | - |
| `total_amount_cents` | `integer` | Yes | - |
| `total_amount_euros` | `number` | Yes | - |

### `ReservationResponse`

_Schema complet pour réponse détaillée d'une réservation._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `is_active` | `boolean` | No | `True` |
| `tenant_id` | `integer` | Yes | - |
| `created_at` | `datetime` | Yes | - |
| `updated_at` | `datetime` | Yes | - |
| `id` | `integer` | Yes | - |
| `customer_id` | `integer` | Yes | - |
| `reference` | `string` | Yes | - |
| `event_date` | `string` | Yes | - |
| `delivery_date` | `string` | Yes | - |
| `return_date` | `string` | Yes | - |
| `event_location` | `string | null` | No | - |
| `status` | `ReservationStatus` | Yes | - |
| `total_amount_cents` | `integer` | Yes | - |
| `deposit_amount_cents` | `integer` | Yes | - |
| `deposit_paid` | `boolean` | Yes | - |
| `customer` | `CustomerList | null` | No | - |
| `lines` | `ReservationLineResponse[]` | No | - |
| `total_amount_euros` | `number` | Yes | - |
| `deposit_amount_euros` | `number` | Yes | - |
| `rental_days` | `integer` | Yes | - |
| `is_confirmed` | `boolean` | Yes | - |
| `is_cancelled` | `boolean` | Yes | - |

### `ReservationStatus`

_Statut du cycle de vie d'une réservation.

Workflow :
    DRAFT → CONFIRMED → DELIVERED → RETURNED
                     ↘ CANCELLED

Utilisé dans :
    - models.Reservation.status
    - services.ReservationService (transitions de statut)
    - Filtres API GET /reservations?status=..._

**Values:** `draft`, `confirmed`, `delivered`, `returned`, `cancelled`

### `ReservationUpdate`

_Schema pour mise à jour d'une réservation.

Tous les champs sont optionnels (PATCH partiel).
customer_id et reference sont immutables.
Les lignes ne peuvent pas être modifiées via update (utiliser endpoints dédiés).

Example:
    {
        "event_date": "2026-06-20",
        "delivery_date": "2026-06-19",
        "event_location": "Palais de Tokyo"
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `event_date` | `string | null` | No | - |
| `delivery_date` | `string | null` | No | - |
| `return_date` | `string | null` | No | - |
| `event_location` | `string | null` | No | - |
| `deposit_paid` | `boolean | null` | No | - |

### `SessionListResponse`

_Schema pour la liste des sessions actives.

Example:
    {
        "sessions": [...],
        "count": 3
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `sessions` | `SessionResponse[]` | No | - |
| `count` | `integer` | Yes | - |

### `SessionResponse`

_Schema pour une session active.

Example:
    {
        "session_id": "a1b2c3d4-...",
        "ip_address": "192.168.1.1",
        "user_agent": "Mozilla/5.0 ...",
        "created_at": "2026-02-13T10:00:00+00:00",
        "last_activity": "2026-02-13T14:30:00+00:00"
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `session_id` | `string` | Yes | - |
| `ip_address` | `string` | Yes | - |
| `user_agent` | `string` | Yes | - |
| `created_at` | `string` | Yes | - |
| `last_activity` | `string` | Yes | - |

### `SessionRevokeAllResponse`

_Schema pour la reponse de revocation de toutes les sessions.

Example:
    {
        "message": "All sessions revoked",
        "count": 3
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `message` | `string` | Yes | - |
| `count` | `integer` | Yes | - |

### `SessionRevokeResponse`

_Schema pour la reponse de revocation de session.

Example:
    {
        "message": "Session revoked",
        "session_id": "a1b2c3d4-..."
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `message` | `string` | Yes | - |
| `session_id` | `string | null` | No | - |

### `TokenResponse`

_Schema pour réponse de login avec tokens JWT.

Example:
    {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "token_type": "bearer",
        "expires_in": 1800
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `access_token` | `string` | Yes | - |
| `refresh_token` | `string` | Yes | - |
| `token_type` | `string` | No | `bearer` |
| `expires_in` | `integer` | Yes | - |

### `UserInfo`

_Schema pour informations utilisateur (dans claims JWT).

Example:
    {
        "id": 1,
        "email": "user@example.com",
        "full_name": "Jean Dupont",
        "role": "manager",
        "tenant_id": 1
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `id` | `integer` | Yes | - |
| `email` | `email` | Yes | - |
| `full_name` | `string` | Yes | - |
| `role` | `UserRole` | Yes | - |
| `tenant_id` | `integer` | Yes | - |
| `is_active` | `boolean` | No | `True` |
| `permissions` | `string[]` | No | - |
| `created_at` | `string | null` | No | - |

### `UserProfileResponse`

_Schema pour réponse profil utilisateur.

Example:
    {
        "id": 1,
        "email": "user@example.com",
        "first_name": "Jean",
        "last_name": "Dupont",
        "full_name": "Jean Dupont",
        "role": "manager",
        "tenant_id": 1,
        "is_active": true,
        "created_at": "2026-01-15T10:00:00Z",
        "updated_at": "2026-02-15T14:30:00Z"
    }_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `id` | `integer` | Yes | - |
| `email` | `email` | Yes | - |
| `first_name` | `string` | Yes | - |
| `last_name` | `string` | Yes | - |
| `full_name` | `string` | Yes | - |
| `role` | `UserRole` | Yes | - |
| `tenant_id` | `integer` | Yes | - |
| `is_active` | `boolean` | No | `True` |
| `created_at` | `string` | Yes | - |
| `updated_at` | `string` | Yes | - |

### `UserProfileUpdate`

_Schema pour mise à jour du profil utilisateur.

Permet de modifier email, first_name, last_name, et optionnellement le password.
Tous les champs sont optionnels (PATCH partiel).

Example:
    PATCH /api/v1/users/me
    {
        "email": "newemail@example.com",
        "first_name": "Jean",
        "last_name": "Dupont"
    }

Security:
    - Email doit être unique par tenant
    - Password doit respecter la password policy si fourni
    - Validation XSS/SQL injection sur first_name/last_name_

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `email` | `email | null` | No | - |
| `first_name` | `string | null` | No | - |
| `last_name` | `string | null` | No | - |
| `password` | `string | null` | No | - |

### `UserRole`

_Rôles utilisateur pour contrôle d'accès (RBAC).

Hiérarchie :
    ADMIN > MANAGER > STAFF

Permissions :
    - ADMIN : Tous droits + gestion users
    - MANAGER : CRUD réservations/factures/clients
    - STAFF : Read-only

Utilisé dans :
    - models.User.role
    - core.deps.require_role (décorateur endpoints)
    - Middleware RBAC_

**Values:** `admin`, `manager`, `staff`

### `VpnConfigResponse`

_Configuration WireGuard d'un peer._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `peer_name` | `string` | Yes | - |
| `config_text` | `string` | Yes | - |
| `filename` | `string` | Yes | - |

### `VpnIpPoolCreate`

_Creation d'un pool IP._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `subnet` | `string` | Yes | - |
| `gateway_ip` | `string` | Yes | - |
| `description` | `string | null` | No | - |

### `VpnIpPoolListResponse`

_Liste des pools IP._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `items` | `VpnIpPoolResponse[]` | Yes | - |
| `total` | `integer` | Yes | - |

### `VpnIpPoolResponse`

_Reponse pool IP._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `id` | `integer` | Yes | - |
| `tenant_id` | `integer` | Yes | - |
| `subnet` | `string` | Yes | - |
| `gateway_ip` | `string` | Yes | - |
| `next_ip` | `string` | Yes | - |
| `subnet_mask` | `integer` | Yes | - |
| `description` | `string | null` | No | - |
| `created_at` | `datetime` | Yes | - |
| `updated_at` | `datetime` | Yes | - |

### `VpnPeerCreate`

_Donnees de creation d'un peer VPN._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `name` | `string` | Yes | - |
| `peer_type` | `string` | No | `client` |
| `allowed_ips` | `string | null` | No | - |
| `dns` | `string | null` | No | - |
| `persistent_keepalive` | `integer` | No | `25` |
| `expires_at` | `datetime | null` | No | - |

### `VpnPeerListResponse`

_Liste paginee de peers VPN._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `items` | `VpnPeerResponse[]` | Yes | - |
| `total` | `integer` | Yes | - |

### `VpnPeerResponse`

_Reponse peer VPN (passthrough du WG service)._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `id` | `string` | Yes | - |
| `tenant_id` | `integer` | Yes | - |
| `name` | `string` | Yes | - |
| `public_key` | `string` | Yes | - |
| `assigned_ip` | `string | null` | No | - |
| `allowed_ips` | `string` | No | `0.0.0.0/0` |
| `dns` | `string | null` | No | - |
| `persistent_keepalive` | `integer` | No | `25` |
| `peer_type` | `string` | No | `client` |
| `is_enabled` | `boolean` | No | `True` |
| `is_active` | `boolean` | No | `True` |
| `expires_at` | `datetime | null` | No | - |
| `created_by` | `string | null` | No | - |
| `created_at` | `datetime` | Yes | - |
| `updated_at` | `datetime` | Yes | - |

### `VpnPeerStatusResponse`

_Statut temps reel d'un peer WireGuard._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `public_key` | `string` | Yes | - |
| `latest_handshake` | `integer` | No | `0` |
| `transfer_rx` | `integer` | No | `0` |
| `transfer_tx` | `integer` | No | `0` |
| `endpoint` | `string` | No | `` |
| `allowed_ips` | `string` | No | `` |

### `VpnPeerUpdate`

_Donnees de mise a jour d'un peer VPN._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `name` | `string | null` | No | - |
| `allowed_ips` | `string | null` | No | - |
| `dns` | `string | null` | No | - |
| `persistent_keepalive` | `integer | null` | No | - |
| `expires_at` | `datetime | null` | No | - |
| `is_enabled` | `boolean | null` | No | - |

### `VpnServerStatusResponse`

_Statut du serveur WireGuard._

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `backend_available` | `boolean` | Yes | - |
| `interface` | `string` | Yes | - |
| `active_peers_count` | `integer` | Yes | - |
| `peers` | `VpnPeerStatusResponse[]` | Yes | - |

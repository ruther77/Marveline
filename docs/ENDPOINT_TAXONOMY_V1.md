# Endpoint Taxonomy V1

Date: 2026-03-05
Status: Locked V1.0
Source: `docs/endpoint_taxonomy_v1.csv`

## Ratified decisions
1. `GET /audit/user/{id}` and `GET /audit/entity/{type}/{id}` are in `product-required` (admin UI scope).
2. OAuth endpoints (`/oauth/providers`, `/oauth/{provider}/authorize`) are in `product-required`.
3. Devis advanced transition endpoints (`/devis/{id}/negotiation/start`, `/devis/{id}/version-pending`) are in `product-required`.

## Rules
1. `platform/system`: endpoints infra/securite (`/.well-known/*`, `/health*`).
2. `admin/internal`: endpoints d'ops internes tenant lifecycle (`/admin/provision*`, `/admin/tenants/*`).
3. `product-required`: tout endpoint requis par les parcours produit/admin UI (`U1..U12`).

## Counts
- Total endpoints: **330**
- `product-required`: **314**
- `admin/internal`: **11**
- `platform/system`: **5**

## Platform/System endpoints
- `GET /.well-known/jwks.json`
- `GET /health`
- `GET /health/live`
- `GET /health/ready`
- `GET /health/status`

## Admin/Internal endpoints
- `POST /admin/provision`
- `POST /admin/provision/degraded/disable`
- `POST /admin/provision/degraded/enable`
- `GET /admin/provision/degraded/status`
- `POST /admin/provision/{tenant_id}/activate`
- `POST /admin/provision/{tenant_id}/offboard`
- `POST /admin/provision/{tenant_id}/suspend`
- `GET /admin/tenants/{tenant_id}/sessions`
- `DELETE /admin/tenants/{tenant_id}/sessions/{session_id}`
- `DELETE /admin/tenants/{tenant_id}/users/{user_id}/sessions`
- `GET /admin/tenants/{tenant_id}/users/{user_id}/sessions`

## Next governance step
- Use V1.0 taxonomy as baseline for CI coverage gate (`G0-04`).

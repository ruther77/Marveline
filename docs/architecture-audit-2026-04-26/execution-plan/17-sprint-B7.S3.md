# Sprint B7.S3 — Refonte AppSelector frontend (Q44=A+C)

> **STATUT** : ⏳ À démarrer après B7.S2
> **DURÉE MAX** : 2 semaines
> **OWNER** : Frontend
> **BLOQUE** : B7.S4 (provisioning crée des entrées AppSelector)
> **DÉPEND DE** : B7.S1 (Tenant.vertical + brand_*), B7.S2 (drop brand_code)
> **OBJECTIF** : Livrer page racine `/` AppSelector listant les `TenantMembership` du user, groupés par vertical, avec header DEVUP admin (Q44=A) et UI client white-label per-tenant + footer "Powered by DEVUP" discret (Q44=C). Cookie SSO `devup_session` cross-tenant + `devup_active_tenant_id` pin. Frontend monorepo : 1 module React par vertical (pas par app_code).

## Vue d'ensemble

| Story | Description | Estimation | Bloque |
|---|---|---|---|
| **B7.S3.T1** | Endpoint backend `GET /me/tenants` retourne TenantMembership groupés par vertical + branding | 1 j | T2 |
| **B7.S3.T2** | Composant React `<AppSelector>` page racine `/` post-login | 2 j | T3 |
| **B7.S3.T3** | Cookie `devup_session` SSO cross-tenant + `devup_active_tenant_id` pin | 1.5 j | T4 |
| **B7.S3.T4** | Routing dynamique `/{tenant_app_code}/...` selon `tenant.vertical` → load module React | 2 j | aucun |
| **B7.S3.T5** | Header admin DEVUP (superadmin seulement) + footer "Powered by DEVUP" discret client | 1 j | aucun |
| **B7.S3.T6** | Single tenant fastpath : 1 membership → redirect direct au tenant | 0.5 j | aucun |
| **B7.S3.T7** | Tests E2E Cypress + Vitest + Storybook AppSelector | 1.5 j | aucun |

**Total effort** : 9.5 jours-homme.

---

# Story B7.S3.T1 — Endpoint `GET /me/tenants`

## Contexte

**Sévérité** : P0 — frontend doit pouvoir lister les tenants du user pour l'AppSelector

### Description

Cible : endpoint retourne `[{tenant_id, app_code, vertical, brand_display_name, brand_logo_url, brand_primary_color, role}]` pour chaque membership du user authentifié.

## Solution

```python
# app/api/v1/endpoints/me.py
@router.get("/me/tenants")
async def list_my_tenants(user: Account = Depends(require_authenticated)):
    memberships = await db.scalars(
        select(TenantMembership)
        .where(TenantMembership.account_id == user.id)
        .options(selectinload(TenantMembership.tenant))
    )
    
    return [
        TenantMembershipRead(
            tenant_id=m.tenant_id,
            app_code=m.tenant.app_code,
            vertical=m.tenant.vertical,
            brand_display_name=m.tenant.brand_display_name,
            brand_logo_url=m.tenant.brand_logo_url,
            brand_primary_color=m.tenant.brand_primary_color,
            role=m.role,
        )
        for m in memberships.all()
        if m.tenant.is_active
    ]
```

### Schema

```python
class TenantMembershipRead(BaseSchema):
    tenant_id: int
    app_code: str
    vertical: Literal["location", "epicerie", "restaurant", "autour_de_table"]
    brand_display_name: str
    brand_logo_url: str | None
    brand_primary_color: str | None
    role: str
```

## DoD

- [ ] Endpoint `GET /me/tenants`
- [ ] Retourne uniquement tenants actifs
- [ ] Schema typé
- [ ] Test : user 3 memberships → 3 entrées

---

# Story B7.S3.T2 — Composant `<AppSelector>`

## Contexte

Page racine `/` post-login affiche les tenants groupés par vertical avec design DEVUP.

## Solution

```tsx
// frontend/packages/devup-shell/src/AppSelector.tsx
import { useQuery } from "@tanstack/react-query";

const VERTICAL_LABELS = {
  location: { icon: "📍", label: "Location" },
  epicerie: { icon: "🏪", label: "Épicerie" },
  restaurant: { icon: "🍽️", label: "Restaurant" },
  autour_de_table: { icon: "🪑", label: "Autour de Table" },
};

export function AppSelector() {
  const { data: tenants, isLoading } = useQuery({
    queryKey: ["my-tenants"],
    queryFn: () => api.get("/me/tenants"),
  });

  if (isLoading) return <Skeleton />;
  if (!tenants?.length) return <EmptyState message="Aucun tenant accessible" />;

  // Single tenant fastpath (T6)
  if (tenants.length === 1) {
    return <Navigate to={`/${tenants[0].app_code}`} replace />;
  }

  const grouped = groupBy(tenants, "vertical");

  return (
    <div className="app-selector">
      <header className="devup-header">
        <h1>DEVUP — Plateforme SaaS</h1>
        <p>Bonjour {user.first_name}</p>
      </header>

      <main>
        <h2>Vos tenants accessibles :</h2>
        {Object.entries(grouped).map(([vertical, items]) => (
          <section key={vertical}>
            <h3>{VERTICAL_LABELS[vertical].icon} {VERTICAL_LABELS[vertical].label}</h3>
            <ul>
              {items.map((t) => (
                <li key={t.tenant_id}>
                  <button onClick={() => selectTenant(t)}>
                    <img src={t.brand_logo_url} alt={t.brand_display_name} />
                    {t.brand_display_name}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </main>
    </div>
  );
}

function selectTenant(tenant: TenantMembership) {
  // Set cookie devup_active_tenant_id (T3)
  document.cookie = `devup_active_tenant_id=${tenant.tenant_id}; Path=/; SameSite=Strict; Secure`;
  // Navigate
  window.location.href = `/${tenant.app_code}`;
}
```

## DoD

- [ ] Composant `<AppSelector>` rendu
- [ ] Groupement par vertical
- [ ] Logos + brand colors
- [ ] Empty state si 0 tenant
- [ ] Test Vitest + snapshot

---

# Story B7.S3.T3 — Cookie SSO `devup_session` + pin tenant

## Contexte

Cookie `devup_session` cross-tenant (auth) + cookie `devup_active_tenant_id` (tenant courant)

## Solution

```python
# app/api/v1/endpoints/auth.py — login
@router.post("/auth/login")
async def login(...):
    # ... auth logic
    response.set_cookie(
        "devup_session",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="strict",
        domain=".devup.fr",  # cross-subdomain
        max_age=86400 * 30,
    )
    return {"user_id": user.id, "tenants_count": memberships_count}
```

```typescript
// frontend/packages/devup-shell/src/api-client.ts
client.interceptors.request.use((config) => {
  const tenantId = getCookie("devup_active_tenant_id");
  if (tenantId) {
    config.headers["X-Tenant-Id"] = tenantId;  // backend valide membership
  }
  return config;
});
```

```python
# Backend valide
@app.middleware("http")
async def tenant_context_middleware(request: Request, call_next):
    tenant_id = request.headers.get("X-Tenant-Id")
    if tenant_id and request.state.user:
        # Vérifier membership
        membership = await db.scalar(
            select(TenantMembership).where(
                TenantMembership.account_id == request.state.user.id,
                TenantMembership.tenant_id == int(tenant_id),
            )
        )
        if membership is None:
            raise HTTPException(403, "Not a member of this tenant")
        request.state.tenant_id = int(tenant_id)
        request.state.tenant_role = membership.role
    return await call_next(request)
```

## DoD

- [ ] Cookie `devup_session` httponly+secure+samesite
- [ ] Cookie `devup_active_tenant_id` pin
- [ ] Header `X-Tenant-Id` propagé
- [ ] Middleware valide membership
- [ ] Test : cross-tenant access → 403

---

# Story B7.S3.T4 — Routing `/{tenant_app_code}/...`

## Solution

```typescript
// frontend/packages/devup-shell/src/router.ts
import { Outlet, createRootRoute, createRoute } from "@tanstack/react-router";

const rootRoute = createRootRoute({ component: () => <Outlet /> });

const tenantRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/$tenantAppCode",
  loader: async ({ params }) => {
    const tenant = await api.get(`/tenants/by-code/${params.tenantAppCode}`);
    if (!tenant) throw redirect({ to: "/" });
    
    // Set active tenant
    document.cookie = `devup_active_tenant_id=${tenant.tenant_id}; ...`;
    
    // Lazy load vertical module
    const verticalModule = await import(`@devup/vertical-${tenant.vertical}`);
    return { tenant, verticalModule };
  },
});

const verticalRoute = createRoute({
  getParentRoute: () => tenantRoute,
  path: "$",  // catch-all
  component: ({ useLoaderData }) => {
    const { tenant, verticalModule } = useLoaderData();
    return <verticalModule.AppRoot tenant={tenant} />;
  },
});
```

## DoD

- [ ] Route `/{app_code}/...` lazy-load module vertical
- [ ] Tenant context propagé
- [ ] Test : `/marveline/reservations` charge module location
- [ ] Test : `/massacorp_resto/commandes` charge module restaurant

---

# Story B7.S3.T5 — Header admin DEVUP + footer client

## Solution

```tsx
// frontend/packages/vertical-shared/src/Layout.tsx
export function VerticalLayout({ tenant, children }) {
  const isSuperadmin = useUser().role === "superadmin";

  return (
    <>
      {isSuperadmin && (
        <div className="devup-admin-header">
          DEVUP — {tenant.vertical.toUpperCase()}
        </div>
      )}
      <header className="tenant-header" style={{ "--brand-color": tenant.brand_primary_color }}>
        <img src={tenant.brand_logo_url} alt={tenant.brand_display_name} />
        <h1>{tenant.brand_display_name}</h1>
      </header>
      <main>{children}</main>
      <footer className="powered-by">
        <a href="https://devup.fr" target="_blank">Powered by DEVUP</a>
      </footer>
    </>
  );
}
```

## DoD

- [ ] Bandeau admin visible superadmin only
- [ ] Header tenant white-label
- [ ] Footer "Powered by DEVUP" discret
- [ ] Test : superadmin voit bandeau, user normal non

---

# Story B7.S3.T6 — Single tenant fastpath

## Solution

Couvert par T2 — `if (tenants.length === 1) return <Navigate ...>`. Story dédiée pour test edge case.

### Test

```typescript
test("user with 1 tenant redirects directly", () => {
  mockApi.get("/me/tenants").reply([{ tenant_id: 1, app_code: "marveline", vertical: "location", ... }]);
  render(<AppSelector />);
  expect(mockNavigate).toHaveBeenCalledWith("/marveline");
});
```

## DoD

- [ ] Single membership → redirect direct
- [ ] Multi membership → AppSelector affiché
- [ ] Test E2E

---

# Story B7.S3.T7 — Tests E2E + Vitest + Storybook

## Solution

```typescript
// e2e/app-selector.cy.ts
describe("AppSelector", () => {
  it("login + select tenant Marveline → redirect /marveline", () => {
    cy.login("user@example.com", "password");
    cy.contains("Marveline").click();
    cy.url().should("include", "/marveline");
  });
});

// stories/AppSelector.stories.tsx
export default { component: AppSelector };
export const ThreeTenants = { args: { tenants: [...3 mock] } };
export const SingleTenant = { args: { tenants: [...1 mock] } };
export const NoTenants = { args: { tenants: [] } };
```

## DoD

- [ ] E2E Cypress login + select
- [ ] Vitest unit tests sur composants
- [ ] Storybook : 3 variantes (multi/single/empty)

---

## Critères de succès Sprint B7.S3

- [ ] **Q44=A+C livré** : DEVUP admin header + white-label client + footer
- [ ] AppSelector page racine
- [ ] Cookie SSO + pin tenant
- [ ] Routing `/{app_code}/...` dynamic
- [ ] Single tenant fastpath
- [ ] Tests E2E + Storybook complets
- [ ] User Marveline + Splendid voit 2 cards location ; user CaroCorp voit 1 card épi + 1 card resto

---

**Fin du document — 17-sprint-B7.S3.md**

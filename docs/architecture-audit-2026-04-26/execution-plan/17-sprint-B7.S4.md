# Sprint B7.S4 — Provisioning workflow tenant

> **STATUT** : ⏳ À démarrer après B7.S3
> **DURÉE MAX** : 1 semaine
> **OWNER** : Dev2
> **BLOQUE** : aucun (sprint final Bloc 7 = sprint final du plan)
> **DÉPEND DE** : B7.S1 (Tenant.vertical), B7.S3 (AppSelector pour tester)
> **OBJECTIF** : Livrer le workflow `POST /admin/devup/tenants/provision` qui crée un nouveau tenant DEVUP en 10 min via API : creation Tenant + seed vertical-specific (Categories, scopes, settings) + admin user initial + welcome email avec lien setup. Cohérent B2.S2.T1 atomicité.

## Vue d'ensemble

| Story | Description | Estimation | Bloque |
|---|---|---|---|
| **B7.S4.T1** | Endpoint `POST /admin/devup/tenants/provision` orchestre création atomique | P0 | T2-T4 |
| **B7.S4.T2** | Seed vertical-specific (Categories + ScopeMappings + Settings) per vertical | P0 | aucun |
| **B7.S4.T3** | Admin user initial + welcome email avec lien setup password (TTL 7j) | P0 | aucun |
| **B7.S4.T4** | Sequences PostgreSQL (B3.S1.T1 reservation_seq, devis_seq, etc.) per nouveau tenant | P1 | aucun |
| **B7.S4.T5** | Tests E2E provisioning : créer tenant complet, verify isolation, login admin | P1 | aucun |

**Total effort** : 5 jours-homme.

---

# Story B7.S4.T1 — Endpoint `POST /admin/devup/tenants/provision`

## Contexte

**Sévérité** : P0 — sans endpoint, provisioning manuel = 1 jour ops par tenant ; cible : 10 min via API

### Description

Cible : endpoint admin DEVUP (scope `superadmin:tenant_provision`) qui :
1. Crée Tenant en 1 TX atomique
2. Seed vertical-specific (T2)
3. Crée admin user initial (T3)
4. Crée sequences PostgreSQL (T4)
5. Audit log + Outbox event `TenantProvisioned`
6. Send welcome email (T3)

## Solution

```python
# app/api/v1/endpoints/admin_devup.py
@router.post(
    "/admin/devup/tenants/provision",
    dependencies=[Depends(require_scope(Scope.SUPERADMIN_TENANT_PROVISION))],
)
async def provision_tenant(
    payload: ProvisionTenantPayload,
    user: User = Depends(get_current_user),
):
    return await provisioning_service.provision(payload, actor_id=user.id)


class ProvisionTenantPayload(BaseSchema):
    app_code: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    vertical: Literal["location", "epicerie", "restaurant", "autour_de_table"]
    legal_name: str
    siret: str | None = None
    vat_number: str | None = None
    brand_display_name: str
    brand_email_from: EmailStr
    brand_dkim_domain: str
    brand_primary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    admin_email: EmailStr
    admin_first_name: str
    admin_last_name: str


# app/services/provisioning.py
class ProvisioningService:
    async def provision(
        self,
        payload: ProvisionTenantPayload,
        actor_id: UUID,
    ) -> ProvisionResult:
        async with self.db.begin():
            # 1. Create Tenant
            tenant = Tenant(
                app_code=payload.app_code,
                vertical=payload.vertical,
                legal_name=payload.legal_name,
                siret=payload.siret,
                vat_number=payload.vat_number,
                brand_display_name=payload.brand_display_name,
                brand_email_from=payload.brand_email_from,
                brand_dkim_domain=payload.brand_dkim_domain,
                brand_primary_color=payload.brand_primary_color,
                country_code="FR",
                default_deposit_pct=Decimal("0.30"),
                devis_default_expiry_days=30,
                incident_sla_hours=24,
                einvoicing_enabled=False,
                einvoicing_mode="none",
            )
            self.db.add(tenant)
            await self.db.flush()

            # 2. Seed vertical (T2)
            await self._seed_vertical(tenant)

            # 3. Create sequences PostgreSQL (T4)
            await self._create_sequences(tenant.id)

            # 4. Create admin user + welcome email (T3)
            admin_account = await self._create_admin_user(tenant.id, payload, actor_id)

            # 5. Audit + Outbox
            await audit_service.log(
                action="tenant.provisioned",
                entity_type="Tenant",
                entity_id=str(tenant.id),
                description=f"Tenant {payload.app_code} provisioned ({payload.vertical})",
                account_id=actor_id,
                tenant_id=tenant.id,
            )
            self.db.add(OutboxEvent(
                event_type="TenantProvisioned",
                aggregate_id=str(tenant.id),
                tenant_id=tenant.id,
                payload={
                    "app_code": payload.app_code,
                    "vertical": payload.vertical,
                    "admin_email": payload.admin_email,
                },
            ))

            return ProvisionResult(
                tenant_id=tenant.id,
                app_code=payload.app_code,
                admin_email=payload.admin_email,
                setup_url=f"https://{payload.app_code}.devup.fr/setup?token={admin_account.setup_token}",
            )
```

## DoD

- [ ] Endpoint `POST /admin/devup/tenants/provision` opérationnel
- [ ] 1 TX atomique : tout passe ou rien
- [ ] Test : provisioning client_x_resto → Tenant + admin + Categories + sequences + audit + Outbox
- [ ] Test : payload invalide (app_code malformé) → 422
- [ ] Test : rollback : si email envoi échoue → tenant non créé (Outbox handler async pour email)

---

# Story B7.S4.T2 — Seed vertical-specific

## Contexte

Chaque vertical a ses propres seed Categories, scope mappings, settings.

### Description

```python
# app/services/provisioning/seed.py
SEED_CATEGORIES = {
    "location": [
        ("assiettes", "Assiettes", Decimal("0.20"), 0),
        ("verres", "Verres", Decimal("0.20"), 0),
        ("nappes", "Nappes", Decimal("0.20"), 90),
        # ... 20 categories
    ],
    "epicerie": [
        ("legumes", "Légumes", Decimal("0.055"), 0),
        ("fruits", "Fruits", Decimal("0.055"), 0),
        # ... ~91 categories M00 seed
    ],
    "restaurant": [
        ("entree", "Entrée", Decimal("0.10"), 0),
        ("plat", "Plat", Decimal("0.10"), 0),
        # ... 15 categories
    ],
    "autour_de_table": [
        # ... à définir
    ],
}

SEED_SCOPES = {
    "location": [
        Scope.LOCATION_READ, Scope.LOCATION_WRITE,
        Scope.RESERVATIONS_READ, Scope.RESERVATIONS_WRITE,
        # ...
    ],
    "epicerie": [
        Scope.EPICERIE_READ, Scope.EPICERIE_WRITE,
        Scope.PRODUCTS_READ, Scope.PRODUCTS_WRITE,
        # ...
    ],
    # ...
}


class ProvisioningService:
    async def _seed_vertical(self, tenant: Tenant):
        # Categories
        for code, name, tva, advance in SEED_CATEGORIES[tenant.vertical]:
            self.db.add(Category(
                tenant_id=tenant.id,
                code=code, name=name,
                tva_rate=tva,
                advance_booking_days=advance,
            ))
        # auth_vertical_scopes mapping
        for scope in SEED_SCOPES[tenant.vertical]:
            self.db.add(AuthVerticalScope(
                vertical_code=tenant.vertical,
                scope=scope.value,
            ))
        # CategorieProduit seed M00 si épicerie/restaurant
        if tenant.vertical in ("epicerie", "restaurant"):
            seed = await self.db.scalars(select(CategorieProduitSeed))
            for s in seed.all():
                self.db.add(CategorieProduit(
                    tenant_id=tenant.id, code=s.code, libelle=s.libelle,
                ))
```

## DoD

- [ ] Seed Categories per vertical
- [ ] Seed scopes per vertical
- [ ] Seed CategorieProduit M00 pour épicerie/resto
- [ ] Test : provision Marveline → 20 Categories ; provision épi → 91 Categories

---

# Story B7.S4.T3 — Admin user + welcome email

## Solution

```python
class ProvisioningService:
    async def _create_admin_user(self, tenant_id: int, payload: ProvisionTenantPayload, actor_id: UUID) -> Account:
        # Generate setup token (TTL 7j)
        setup_token = secrets.token_urlsafe(32)
        
        account = Account(
            email=payload.admin_email,
            first_name=payload.admin_first_name,
            last_name=payload.admin_last_name,
            tenant_id=tenant_id,
            hashed_password=None,  # set by user via setup
            setup_token=setup_token,
            setup_token_expires_at=datetime.now(UTC) + timedelta(days=7),
            is_active=False,  # activated after setup
        )
        self.db.add(account)
        await self.db.flush()
        
        # TenantMembership avec role=admin
        self.db.add(TenantMembership(
            account_id=account.id,
            tenant_id=tenant_id,
            role="admin",
        ))
        
        # Welcome email (Outbox-based pour ne pas bloquer la TX)
        self.db.add(OutboxEvent(
            event_type="WelcomeEmailRequested",
            aggregate_id=str(account.id),
            tenant_id=tenant_id,
            payload={
                "to": payload.admin_email,
                "first_name": payload.admin_first_name,
                "setup_url": f"https://{payload.app_code}.devup.fr/setup?token={setup_token}",
            },
        ))
        
        return account
```

### Endpoint setup password

```python
@router.post("/setup")
async def setup_password(payload: SetupPayload):
    account = await db.scalar(
        select(Account).where(
            Account.setup_token == payload.token,
            Account.setup_token_expires_at > datetime.now(UTC),
        )
    )
    if account is None:
        raise HTTPException(404, "Invalid or expired setup token")
    
    account.hashed_password = hash_password(payload.password)
    account.is_active = True
    account.setup_token = None
    await db.commit()
    return {"status": "activated"}
```

## DoD

- [ ] Admin account créé inactif
- [ ] Setup token TTL 7j
- [ ] Welcome email via Outbox (handler async)
- [ ] Endpoint `/setup` activate
- [ ] Test : setup token expiré → 404

---

# Story B7.S4.T4 — Sequences PostgreSQL per tenant

## Contexte

Cohérent B3.S1.T1 (sequences per-tenant pour reservation_number, devis_number, invoice_number, vente_number)

## Solution

```python
class ProvisioningService:
    async def _create_sequences(self, tenant_id: int):
        for seq_name in ("reservation", "devis", "invoice", "vente", "supplier_order", "evenement"):
            await self.db.execute(text(f"""
                CREATE SEQUENCE IF NOT EXISTS seq_{seq_name}_{tenant_id} START 1
            """))
```

## DoD

- [ ] 6 sequences créées par tenant
- [ ] Test : nextval(seq_reservation_X) retourne 1

---

# Story B7.S4.T5 — Tests E2E

## Solution

```python
async def test_e2e_provision_tenant_full(client_superadmin):
    response = await client_superadmin.post("/api/v1/admin/devup/tenants/provision", json={
        "app_code": "client_test_resto",
        "vertical": "restaurant",
        "legal_name": "Client Test SARL",
        "brand_display_name": "Client Test",
        "brand_email_from": "noreply@client-test.fr",
        "brand_dkim_domain": "client-test.fr",
        "brand_primary_color": "#A52A2A",
        "admin_email": "admin@client-test.fr",
        "admin_first_name": "John",
        "admin_last_name": "Doe",
    })
    assert response.status_code == 200
    result = response.json()
    
    # Verify Tenant créé
    tenant = await db.scalar(select(Tenant).where(Tenant.app_code == "client_test_resto"))
    assert tenant.vertical == "restaurant"
    
    # Verify Categories seedées (15 pour restaurant)
    cats = await db.scalars(select(Category).where(Category.tenant_id == tenant.id))
    assert len(cats.all()) >= 15
    
    # Verify admin créé inactif
    admin = await db.scalar(select(Account).where(Account.email == "admin@client-test.fr"))
    assert not admin.is_active
    assert admin.setup_token is not None
    
    # Verify sequences
    seq_val = await db.scalar(text("SELECT nextval('seq_reservation_' || :tid)"), {"tid": tenant.id})
    assert seq_val == 1
    
    # Verify Outbox events publiés
    events = await db.scalars(select(OutboxEvent).where(OutboxEvent.tenant_id == tenant.id))
    event_types = {e.event_type for e in events.all()}
    assert "TenantProvisioned" in event_types
    assert "WelcomeEmailRequested" in event_types
```

### Test isolation cross-tenant

```python
async def test_provisioned_tenant_isolated(client, new_tenant_provisioned):
    """Le nouveau tenant ne voit pas les data des autres."""
    # User admin du new tenant
    other_customer = Customer(tenant_id=other_tenant.id, ...)
    db.add(other_customer); await db.commit()
    
    response = await client_new_admin.get("/api/v1/customers")
    assert other_customer.id not in [c["id"] for c in response.json()]
```

## DoD

- [ ] Test E2E provisioning complet
- [ ] Test isolation cross-tenant
- [ ] Test rollback si erreur mid-provisioning
- [ ] Documentation runbook DEVUP "comment provisionner un client"

---

## Critères de succès Sprint B7.S4

- [ ] Endpoint provisioning opérationnel
- [ ] Seed vertical-specific complet (Categories, scopes, M00)
- [ ] Admin user + welcome email via Outbox
- [ ] Sequences PostgreSQL per tenant
- [ ] Tests E2E + isolation
- [ ] **Bloc 7 verrouillé** : 4 sprints livrés (B7.S1 → B7.S4), DEVUP multi-tenant multi-vertical opérationnel
- [ ] **Plan d'exécution Phase 2 complet** : 35/35 sprints rédigés

---

**Fin du document — 17-sprint-B7.S4.md**

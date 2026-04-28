# Sprint B2.S2 — Provisioning atomique + table verticals

> **STATUT** : ⏳ À démarrer après B2.S1
> **DURÉE MAX** : 1.5 semaines
> **OWNER** : Dev2
> **BLOQUE** : B7.S1 (vertical=FK verticals.code), B7.S4 (provisioning workflow)
> **DÉPEND DE** : B1.S2 (RLS), B1.S3 (KMS), Sprint 1 T5 F255 (await provisioning)
> **OBJECTIF** : Créer la table `verticals` (Q44/Q45 modèle DEVUP), refondre `TenantService.provision()` en transaction atomique avec backfill TenantSettings race-free (F265), fixer F256 atomicité.

## Vue d'ensemble

| Story | Description | Estimation | Bloque |
|---|---|---|---|
| **B2.S2.T1** | Migration table `verticals` + seed (4 codes : location, epicerie, restaurant, autour_de_table) | 0.5 j | T2 |
| **B2.S2.T2** | `TenantService.provision()` atomique (F256 + F265) | 2 j | B7.S4 |
| **B2.S2.T3** | Backfill `tenant_settings` pour tenants existants (F265 race) | 0.5 j | B2.S2.T2 |
| **B2.S2.T4** | F1015/F1016 préparation (export RGPD + purge audit 7 ans) | 1.5 j | B6.S2 |

**Total effort** : 4.5 jours-homme.

---

# Story B2.S2.T1 — Table `verticals` + seed

## Contexte

**Décision** : Phase 1 §7.2 + Q44=A+C, Q45=A+C (modèle DEVUP plateforme N tenants × 4 verticals)
**Migration** : `c4d5e6f7a8bb` (cf. `51-alembic-migrations.md`)

### Description

Cf. `50-sql-schema.md §1.1` pour le DDL complet de `verticals`. 4 valeurs seed :
- `location` (Marveline, Splendid Events, futurs)
- `epicerie` (MassaCorp Épicerie)
- `restaurant` (MassaCorp Restaurant)
- `autour_de_table` (futur — service repas livré)

## Solution

```python
# alembic/versions/c4d5e6f7a8bb_create_verticals_table.py
"""Bloc 7 §7.2 : création table verticals + seed 4 codes.

Revision ID: c4d5e6f7a8bb
"""
from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "verticals",
        sa.Column("code", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("default_categories", sa.JSON),  # Liste catégories produits seed
        sa.Column("default_pricing_strategy", sa.String(50)),  # 'cumulative' | 'first_match'
        sa.Column("loyalty_template", sa.JSON),  # Template programme fidélité
        sa.Column("default_settings", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # Seed
    op.execute("""
        INSERT INTO verticals (code, name, description, default_settings) VALUES
        ('location', 'Location événementielle', 'Marveline, Splendid Events',
         '{"default_tva_rate": "0.20", "default_deposit_pct": "0.30"}'::jsonb),
        ('epicerie', 'Épicerie alimentaire', 'MassaCorp Épicerie',
         '{"default_tva_rate": "0.055"}'::jsonb),
        ('restaurant', 'Restaurant', 'MassaCorp Restaurant',
         '{"default_tva_rate": "0.10"}'::jsonb),
        ('autour_de_table', 'Service repas livré', 'Service futur',
         '{"default_tva_rate": "0.10"}'::jsonb);
    """)


def downgrade() -> None:
    op.drop_table("verticals")
```

## DoD

- [ ] Migration `c4d5e6f7a8bb` appliquée
- [ ] 4 verticals seed présents
- [ ] Test : `SELECT * FROM verticals` retourne 4 rows
- [ ] B7.S1 peut migrer `tenants.app_code` → FK `tenants.vertical = verticals.code`

---

# Story B2.S2.T2 — `TenantService.provision()` atomique

## Contexte

**Frictions** : F256 atomicité (vague 3 V3-P0-06), F265 race TenantSettings (vague 3 V3-P1-05)
**Diagramme** : `56-sequence-diagrams.md §9` Provisioning DEVUP

### Description

Provisioning d'un nouveau tenant doit créer atomiquement (1 TX) :
1. `Tenant` (slug=app_code unique, vertical, deposit_policy)
2. `TenantBrand` (palette + frontend_url + dkim_domain) — F295 fix
3. `TenantSettings` (default_tva_rate, devis_default_expiry_days) — F265 fix
4. `Account` initial admin (email, hashed_password=temp_password)
5. `TenantMembership` (account_id, tenant_id, role='admin')
6. Outbox event `TenantProvisioned`

Si une étape échoue → rollback complet (pas de tenant à moitié créé).

## Solution

```python
# app/services/tenant.py
class TenantService:
    async def provision(
        self,
        db: AsyncSession,
        slug: str,
        name: str,
        vertical_code: str,
        admin_email: str,
        rp_id: Optional[str] = None,
        frontend_url: Optional[str] = None,
        deposit_policy_pct: Decimal = Decimal("0.30"),
        actor_account_id: Optional[int] = None,
    ) -> ProvisionResult:
        """F256 fix : provisioning atomique en 1 transaction.

        Tous les artefacts créés dans le même `async with db.begin()`.
        Si quoi que ce soit échoue → rollback complet, aucun tenant à moitié créé.
        """
        async with db.begin():
            # 1. Vérifier unicité slug
            existing = await db.execute(
                select(Tenant).filter_by(app_code=slug)
            )
            if existing.scalar_one_or_none():
                raise ConflictError(f"Slug '{slug}' already taken")

            # 2. Vérifier vertical existe
            vertical = await db.execute(
                select(Vertical).filter_by(code=vertical_code)
            )
            vertical = vertical.scalar_one_or_none()
            if not vertical:
                raise NotFoundError(f"Vertical '{vertical_code}' unknown")

            # 3. Créer Tenant (F256 — vertical=string, F368 — rp_id per-tenant)
            tenant = Tenant(
                app_code=slug,
                nom=name,
                vertical=vertical_code,  # FK string verticals.code
                rp_id=rp_id,  # F368 — WebAuthn per-tenant
                frontend_url=frontend_url,  # F295 — emails per-tenant
                deposit_policy_pct=deposit_policy_pct,
                is_active=True,
            )
            db.add(tenant)
            await db.flush()

            # 4. Créer TenantBrand (palette obligatoire — pas de NULL)
            brand = TenantBrand(
                tenant_id=tenant.id,
                primary_color="#1E40AF",  # Default DEVUP — surchargeable post-creation
                logo_url=None,
                email_from=f"noreply@{frontend_url or 'devup.fr'}",
                dkim_domain=None,
            )
            db.add(brand)

            # 5. Créer TenantSettings — F265 fix : créé immédiatement (pas race)
            settings_data = {
                **vertical.default_settings,  # JSONB depuis seed
                "rfm_thresholds": {"R": [30, 60], "F": [3, 10], "M": [10000, 50000]},
                "incident_sla_hours": 24,
            }
            tenant_settings = TenantSettings(
                tenant_id=tenant.id,
                settings_json=settings_data,
            )
            db.add(tenant_settings)

            # 6. Créer Account admin initial (post-Bloc 2 = Account, pas User)
            from app.core.security import generate_temp_password, hash_password_argon2
            temp_password = generate_temp_password()
            admin_account = Account(
                email=admin_email,
                hashed_password=await hash_password_argon2(temp_password),
                must_change_password=True,
                is_active=True,
            )
            db.add(admin_account)
            await db.flush()

            # 7. Créer TenantMembership (RBAC v3)
            membership = TenantMembership(
                account_id=admin_account.id,
                tenant_id=tenant.id,
                role="admin",
                status="active",
            )
            db.add(membership)

            # 8. Outbox event (transactionnel)
            await outbox_service.enqueue(
                db,
                event_type="TenantProvisioned",
                aggregate_type="Tenant",
                aggregate_id=tenant.id,
                payload={
                    "tenant_id": tenant.id,
                    "slug": slug,
                    "vertical": vertical_code,
                    "admin_email": admin_email,
                },
                actor_account_id=actor_account_id,
                actor_type="account" if actor_account_id else "system",
            )

            # 9. Audit explicite DEVUP
            await audit_service.log_db(
                db,
                action="devup.tenant.provision",
                entity_type="Tenant",
                entity_id=tenant.id,
                payload={"slug": slug, "vertical": vertical_code},
            )

        # Commit happens at end of async with db.begin()

        return ProvisionResult(
            tenant_id=tenant.id,
            admin_account_id=admin_account.id,
            temp_password=temp_password,  # Returned to ops, never logged
        )
```

## Tests

```python
@pytest.mark.asyncio
async def test_provision__atomic_rollback_on_settings_failure(db, mocked_kms):
    """F256 fix : si une étape échoue, tenant n'est PAS créé partiellement."""
    # Mock TenantSettings création pour échouer
    with patch("app.repositories.tenant_settings.create", side_effect=IntegrityError("FK fail")):
        with pytest.raises(IntegrityError):
            await tenant_service.provision(
                db, slug="testfail", name="Test", vertical_code="location",
                admin_email="admin@test.fr",
            )

    # Vérifier que rien n'a été créé
    result = await db.execute(select(Tenant).filter_by(app_code="testfail"))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_provision__creates_all_artifacts_in_one_tx(db, mocked_kms):
    """Provisioning successful → 6 artefacts créés (Tenant + Brand + Settings + Account + Membership + Outbox)."""
    result = await tenant_service.provision(
        db, slug="splendid", name="Splendid Events", vertical_code="location",
        admin_email="admin@splendid.events",
        rp_id="splendid.events", frontend_url="https://splendid.events",
    )

    tenant = await db.get(Tenant, result.tenant_id)
    assert tenant.app_code == "splendid"
    assert tenant.vertical == "location"
    assert tenant.rp_id == "splendid.events"  # F368 fix vérifié

    brand = await db.execute(select(TenantBrand).filter_by(tenant_id=tenant.id))
    assert brand.scalar_one().primary_color == "#1E40AF"

    settings = await db.execute(select(TenantSettings).filter_by(tenant_id=tenant.id))
    assert settings.scalar_one() is not None  # F265 fix vérifié

    membership = await db.execute(
        select(TenantMembership).filter_by(tenant_id=tenant.id, role="admin")
    )
    assert membership.scalar_one().account_id == result.admin_account_id

    # Outbox event présent
    outbox = await db.execute(
        select(OutboxEvent).filter_by(event_type="TenantProvisioned", aggregate_id=tenant.id)
    )
    assert outbox.scalar_one().status == "pending"
```

## DoD

- [ ] `TenantService.provision()` refondu en 1 TX atomique
- [ ] 4 tests E2E verts (atomic rollback, all artifacts created, slug unique, vertical exists)
- [ ] Diagramme `56-sequence-diagrams.md §9` cohérent (déjà mis à jour vague 3)
- [ ] F256 + F265 marqués résolus

## Risque

- Probabilité 2, impact 4 → score 8 MEDIUM

---

# Story B2.S2.T3 — Backfill `tenant_settings` race-free (F265)

## Contexte

**Friction** : F265 (vague 3 V3-P1-05) — `TenantSettingsRepository.get()` lazy-create avec `INSERT ... ON CONFLICT DO NOTHING` → IntegrityError sur 2 requêtes concurrentes au premier accès

### Description

Pour les tenants existants (avant B2.S2.T2), pas de TenantSettings → race au premier accès concurrent. Migration de backfill qui crée les settings manquants.

## Solution

```python
# alembic/versions/c4d5e6f7a8bc_backfill_tenant_settings.py
"""F265 fix : backfill TenantSettings pour tenants existants.

Revision ID: c4d5e6f7a8bc
"""
def upgrade() -> None:
    # Crée settings vides pour tous tenants qui n'en ont pas
    op.execute("""
        INSERT INTO tenant_settings (tenant_id, settings_json)
        SELECT t.id, '{}'::jsonb
        FROM tenants t
        WHERE NOT EXISTS (
            SELECT 1 FROM tenant_settings ts WHERE ts.tenant_id = t.id
        );
    """)
```

## DoD

- [ ] Migration appliquée + backfill 100% tenants ont settings
- [ ] Test : 2 requêtes concurrentes sur même tenant → 0 IntegrityError

---

# Story B2.S2.T4 — F1015/F1016 préparation (export RGPD + purge audit 7 ans)

## Contexte

**Frictions** : F1015 (RGPD Art.15 export user), F1016 (purge audit_logs > 7 ans)
**Diagramme** : `56-sequence-diagrams.md §10` Export RGPD

### Description

Préparation des artefacts pour B6.S2 (sprint où la fonctionnalité est livrée). Cette story crée :
- Endpoint `POST /me/export` avec retour task_id (Celery)
- Task `rgpd_export_user_data` (génère ZIP signé chiffré)
- Task cron `purge_audit_logs_older_than_7_years` (B6.S2 active la cron)

## Solution

```python
# app/api/v1/endpoints/me.py
@router.post("/me/export")
async def request_data_export(
    current_account: Account = Depends(get_current_principal),
    db: AsyncSession = Depends(get_async_db),
):
    """RGPD Article 15 : Right of access — export complet des données utilisateur.

    Async via Celery task (export peut prendre 1-30 min selon volume).
    Le client poll `/me/export/{task_id}/status` pour récupérer le download URL.
    """
    task = rgpd_export_user_data.delay(account_id=current_account.id)
    return {"task_id": task.id, "status": "queued"}


@router.get("/me/export/{task_id}/status")
async def export_status(task_id: str, current_account: Account = Depends(get_current_principal)):
    """Retourne status du task (PENDING/RUNNING/SUCCESS/FAILURE) + download_url si SUCCESS."""
    result = AsyncResult(task_id)
    if result.state == "SUCCESS":
        return {"status": "success", "download_url": result.result["url"], "expires_at": result.result["expires_at"]}
    return {"status": result.state.lower()}


# app/tasks/rgpd.py
@celery_app.task(name="app.tasks.rgpd.export_user_data", queue="rgpd")
async def rgpd_export_user_data(account_id: int) -> dict:
    """Génère un ZIP avec toutes les données de l'account (réservations, factures, fidélité, audit, ...).

    Signed download URL via S3 presigned (24h expiry).
    """
    # ... implémentation B6.S2
    pass


@celery_app.task(name="app.tasks.rgpd.purge_audit_logs", queue="maintenance")
async def purge_audit_logs_older_than_7_years() -> dict:
    """RGPD Article 5(1)(e) : storage limitation — supprime audit_logs > 7 ans."""
    # ... implémentation B6.S2
    pass


# Celery beat schedule (préparation B6.S2)
beat_schedule = {
    "purge-audit-logs-weekly": {
        "task": "app.tasks.rgpd.purge_audit_logs",
        "schedule": crontab(day_of_week=0, hour=3, minute=0),  # Dimanche 3h
    },
}
```

## DoD

- [ ] Endpoints `/me/export` + `/me/export/{task_id}/status` implémentés (skeleton)
- [ ] Celery tasks `rgpd_export_user_data` + `purge_audit_logs_older_than_7_years` créées (skeleton)
- [ ] Beat schedule documenté (active en B6.S2 quand audit chain HMAC prêt)
- [ ] OpenAPI `52-api-contracts.openapi.yml` matche (déjà rédigé Phase 3)

## Risque

- Probabilité 2, impact 3 → score 6 MEDIUM (skeleton uniquement, B6.S2 active)

---

## Critères de succès Sprint B2.S2

- [ ] Table `verticals` + 4 codes seed
- [ ] `TenantService.provision()` atomique (F256 + F265 résolus)
- [ ] Backfill TenantSettings 100% tenants existants
- [ ] Endpoints + tasks RGPD skeleton (pour B6.S2)
- [ ] B7.S1 (vertical FK) débloqué

---

**Fin du document — 12-sprint-B2.S2.md**

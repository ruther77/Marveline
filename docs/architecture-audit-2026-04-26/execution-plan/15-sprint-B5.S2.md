# Sprint B5.S2 — tenant_id ETL + EAN UNIQUE per-tenant + lignes_data versioning

> **STATUT** : ⏳ À démarrer après B5.S1
> **DURÉE MAX** : 2 semaines
> **OWNER** : Dev3
> **BLOQUE** : B5.S3 (FSM cascade), B5.S4 (Celery tenant-aware), B7.S2 (drop brand_code utilise même pattern)
> **DÉPEND DE** : B1.S2 (RLS), B2.S2 (table verticals)
> **OBJECTIF** : Rompre le référentiel ETL cross-tenant (TR-39, TR-40) — `tenant_id NOT NULL` sur `CatalogueProduit`, `CategorieProduit`, `EtlCorrectionHistory`, `IngredientEpicerieMapping`. Livrer `UNIQUE(tenant_id, ean)` sur `epicerie_produits` (F869). Versionner `lignes_data JSONB` (F875, TR-47) avec migrator. Ajouter tenant guard `peer_id` VPN (F1110).

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B5.S2.T1** | TR-39 — `tenant_id NOT NULL` sur `CatalogueProduit`, `CategorieProduit`, `EtlCorrectionHistory` | P0 | 2 j | T2, T3 |
| **B5.S2.T2** | TR-40 — Trigger DB cross-tenant FK validation (`IngredientEpicerieMapping.produit_id`, `InternalTransfer.dest_tenant_id`, `TransferRequest.target_tenant_id`) | P0 | 1.5 j | aucun |
| **B5.S2.T3** | F869 — `UNIQUE(tenant_id, ean)` sur `epicerie_produits` | P0 | 0.5 j | aucun |
| **B5.S2.T4** | TR-47 — `lignes_data_schema_version INT` + migrator service | P1 | 1 j | aucun |
| **B5.S2.T5** | TR-46 — `CatalogueProduitPriceHistory` audit prix overwrite ETL | P1 | 1 j | aucun |
| **B5.S2.T6** | F1110 — Tenant guard `peer_id` VPN avant retour côté WG service | P1 | 0.5 j | aucun |
| **B5.S2.T7** | TR-61 — `EtlImport` statut `ECHEC` explicit (vs `PARTIEL` mensonger) | P1 | 0.5 j | aucun |
| **B5.S2.T8** | **Q29=A** — Création table `categorie_produit_seed` M00 read-only + seed 91 codes canoniques + helper provisioning | P0 | 0.5 j | B7.S4.T2 |

**Total effort** : 7.5 jours-homme.

---

# Story B5.S2.T1 — `tenant_id NOT NULL` sur référentiel ETL (TR-39)

## Contexte

**Friction** : TR-39 (cf. `architecture-cible.md §5.2.1`)
**Sévérité** : P0 — fuite de données métier cross-tenant : Marveline modifie un prix → impacte Épicerie+Restaurant
**Code source** : `app/models/catalogue.py`, `app/models/categorie_produit.py`, `app/models/etl_correction_history.py`

### Description

Référentiel ETL actuel sans `tenant_id` :
- `CatalogueProduit` : produit fournisseur (METRO/TAIYAT/EUROCIEL) commun à tous les tenants
- `CategorieProduit` : catégorie produit cross-tenant
- `EtlCorrectionHistory` : apprentissage des corrections — **fuite cross-SaaS** (un concurrent voit les corrections de l'autre)

Conséquences :
- Marveline modifie `CatalogueProduit{ean='123', prix=10€}` → CaroCorp Épicerie reçoit le changement silencieusement
- Admin désactive `CategorieProduit{code='legumes'}` cross-tenant → tous les tenants cassés
- Apprentissage `EtlCorrectionHistory` partagé = données concurrents visibles

## Solution

### Migration backward-compatible 4 étapes

```python
# alembic/versions/g1a2b3c4d5eb_etl_tenant_id_step1_add_nullable.py
"""Étape 1 : ajouter colonne nullable + index."""
def upgrade() -> None:
    for table in ("catalogue_produit", "categorie_produit", "etl_correction_history"):
        op.add_column(table, sa.Column("tenant_id", sa.Integer, nullable=True))
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])
        op.create_foreign_key(
            f"fk_{table}_tenant_id", table, "tenants",
            ["tenant_id"], ["id"], ondelete="CASCADE",
        )

# alembic/versions/g1a2b3c4d5ec_etl_tenant_id_step2_backfill.py
"""Étape 2 : backfill — déduire tenant_id depuis EtlImport.target_tenant_id."""
def upgrade() -> None:
    op.execute(text("""
        -- CatalogueProduit : déduit du dernier EtlImport l'ayant touché
        UPDATE catalogue_produit cp
        SET tenant_id = (
            SELECT ei.target_tenant_id
            FROM etl_import ei
            JOIN etl_import_line eil ON eil.import_id = ei.id
            WHERE eil.catalogue_produit_id = cp.id
            ORDER BY ei.created_at DESC LIMIT 1
        );
        -- Si NULL résiduel → tenant Marveline (tenant id 1) par défaut + audit
        UPDATE catalogue_produit SET tenant_id = 1 WHERE tenant_id IS NULL;
        -- Idem categorie_produit + etl_correction_history
    """))

# alembic/versions/g1a2b3c4d5ed_etl_tenant_id_step3_not_null.py
"""Étape 3 : NOT NULL + UNIQUE per-tenant + RLS."""
def upgrade() -> None:
    for table in ("catalogue_produit", "categorie_produit", "etl_correction_history"):
        op.alter_column(table, "tenant_id", nullable=False)
        op.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(text(f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            FOR ALL TO carocorp_app
            USING (tenant_id = current_setting('app.current_tenant_id', true)::int)
        """))
    # UNIQUE per-tenant
    op.drop_constraint("uq_catalogue_produit_ean", "catalogue_produit", type_="unique")
    op.create_unique_constraint(
        "uq_catalogue_produit_tenant_ean", "catalogue_produit", ["tenant_id", "ean"]
    )

# alembic/versions/g1a2b3c4d5ee_etl_tenant_id_step4_drop_global_index.py
"""Étape 4 : drop index globaux résiduels qui empêchent partition logique."""
```

### Modèles

```python
# app/models/catalogue.py
class CatalogueProduit(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "catalogue_produit"
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    ean: Mapped[str | None]
    # ... existing
    __table_args__ = (
        UniqueConstraint("tenant_id", "ean", name="uq_catalogue_produit_tenant_ean"),
    )

class CategorieProduit(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str]
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_categorie_produit_tenant_code"),
    )

class EtlCorrectionHistory(Base, TimestampMixin, TenantMixin):
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    # ... idem
```

### Tests

```python
async def test_catalogue_produit_isolation_per_tenant(db, tenant_a, tenant_b):
    cp_a = CatalogueProduit(tenant_id=tenant_a.id, ean="3033710080014", prix_unitaire_cts=500)
    cp_b = CatalogueProduit(tenant_id=tenant_b.id, ean="3033710080014", prix_unitaire_cts=600)
    db.add_all([cp_a, cp_b]); await db.commit()  # OK — UNIQUE per-tenant

    # Sous RLS context tenant_a, ne voit que cp_a
    await db.execute(text("SET LOCAL app.current_tenant_id = :tid"), {"tid": tenant_a.id})
    visible = await db.scalars(select(CatalogueProduit).where(CatalogueProduit.ean == "3033710080014"))
    assert len(visible.all()) == 1
    assert visible.first().prix_unitaire_cts == 500

async def test_etl_correction_history_no_cross_tenant_learning(db, tenant_a, tenant_b):
    """Tenant A apprend une correction → Tenant B ne la voit jamais."""
    correction = EtlCorrectionHistory(
        tenant_id=tenant_a.id,
        original_text="POMMES GLUNEX",
        corrected_categorie_code="legumes",
    )
    db.add(correction); await db.commit()

    await db.execute(text("SET LOCAL app.current_tenant_id = :tid"), {"tid": tenant_b.id})
    leaked = await db.scalars(
        select(EtlCorrectionHistory).where(EtlCorrectionHistory.original_text == "POMMES GLUNEX")
    )
    assert len(leaked.all()) == 0
```

## DoD

- [ ] Migration 4 étapes (add nullable → backfill → NOT NULL + RLS → drop globals)
- [ ] `tenant_id NOT NULL` sur les 3 tables référentiel ETL
- [ ] `UNIQUE(tenant_id, ean)` sur catalogue_produit
- [ ] `UNIQUE(tenant_id, code)` sur categorie_produit
- [ ] RLS policies actives
- [ ] Tests : isolation cross-tenant + apprentissage isolé

---

# Story B5.S2.T2 — Cross-tenant FK validation (TR-40)

## Contexte

**Friction** : TR-40 (cf. `architecture-cible.md §5.1`)
**Sévérité** : P0 — fuite stock : `IngredientEpicerieMapping.produit_id` peut pointer vers tenant tiers ; idem `InternalTransfer.dest_tenant_id`, `TransferRequest.target_tenant_id`

### Description

Cible : trigger DB qui valide que `produit_id.tenant_id == ingredient.tenant_id` à l'INSERT/UPDATE.

## Solution

### Trigger DB

```python
# alembic/versions/g1a2b3c4d5ef_cross_tenant_fk_validation.py
def upgrade() -> None:
    op.execute(text("""
        CREATE OR REPLACE FUNCTION ingredient_mapping_tenant_check()
        RETURNS TRIGGER AS $$
        DECLARE
            ingredient_tenant INT;
            produit_tenant INT;
        BEGIN
            SELECT tenant_id INTO ingredient_tenant FROM ingredients WHERE id = NEW.ingredient_id;
            SELECT tenant_id INTO produit_tenant FROM epicerie_produits WHERE id = NEW.produit_id;
            IF ingredient_tenant != produit_tenant THEN
                RAISE EXCEPTION 'cross_tenant_mapping_forbidden: ingredient.tenant=% != produit.tenant=%',
                    ingredient_tenant, produit_tenant;
            END IF;
            RETURN NEW;
        END $$ LANGUAGE plpgsql;
    """))
    op.execute(text("""
        CREATE TRIGGER trg_ingredient_mapping_tenant_check
        BEFORE INSERT OR UPDATE ON ingredient_epicerie_mapping
        FOR EACH ROW EXECUTE FUNCTION ingredient_mapping_tenant_check()
    """))

    # Idem pour InternalTransfer.dest_tenant_id et TransferRequest.target_tenant_id :
    # Ces colonnes sont CROSS-tenant *valides* (ex: resto demande à épicerie même groupe).
    # Le check est : src_tenant et dest_tenant doivent appartenir au même `tenant_group_id` 
    # (à introduire si pas déjà — sinon : check cross_tenant flag autorisé seulement entre tenants liés).
```

### Test

```python
async def test_ingredient_mapping_cross_tenant_refused(db, tenant_resto, tenant_epi_other):
    ingredient = Ingredient(tenant_id=tenant_resto.id, nom="Tomate")
    produit_other = EpicerieProduit(tenant_id=tenant_epi_other.id, nom="Tomate")
    db.add_all([ingredient, produit_other]); await db.commit()

    mapping = IngredientEpicerieMapping(ingredient_id=ingredient.id, produit_id=produit_other.id)
    db.add(mapping)
    with pytest.raises(IntegrityError, match="cross_tenant_mapping_forbidden"):
        await db.commit()
```

## DoD

- [ ] Trigger `ingredient_mapping_tenant_check` actif
- [ ] Test : mapping cross-tenant → IntegrityError
- [ ] Audit `InternalTransfer` / `TransferRequest` : valider que cross-tenant entre tenants liés (groupe) seulement

---

# Story B5.S2.T3 — `UNIQUE(tenant_id, ean)` sur epicerie_produits (F869)

## Contexte

**Friction** : F869 (vague 5)
**Sévérité** : P0 — doublons EAN dans même tenant épicerie → ETL pollué silencieusement

## Solution

```python
# alembic/versions/g1a2b3c4d5f0_epicerie_produits_unique_ean.py
def upgrade() -> None:
    # Drop UNIQUE global existant si présent
    with contextlib.suppress(Exception):
        op.drop_constraint("uq_epicerie_produits_ean", "epicerie_produits", type_="unique")
    # Créer UNIQUE per-tenant (ignore NULL ean — soft EAN optionnel)
    op.create_index(
        "uq_epicerie_produits_tenant_ean",
        "epicerie_produits",
        ["tenant_id", "ean"],
        unique=True,
        postgresql_where=sa.text("ean IS NOT NULL"),
    )
```

### Test

```python
async def test_epicerie_produits_unique_ean_per_tenant(db, tenant_a, tenant_b):
    p_a = EpicerieProduit(tenant_id=tenant_a.id, ean="3033710080014", nom="Lait")
    p_b = EpicerieProduit(tenant_id=tenant_b.id, ean="3033710080014", nom="Milk")
    db.add_all([p_a, p_b]); await db.commit()  # OK cross-tenant

    p_dup = EpicerieProduit(tenant_id=tenant_a.id, ean="3033710080014", nom="dup")
    db.add(p_dup)
    with pytest.raises(IntegrityError):
        await db.commit()
```

## DoD

- [ ] Index UNIQUE partiel `(tenant_id, ean) WHERE ean IS NOT NULL`
- [ ] Test cross-tenant OK ; intra-tenant refusé
- [ ] Test EAN NULL : 2 produits NULL sur même tenant → OK (soft EAN)

---

# Story B5.S2.T4 — `lignes_data_schema_version` + migrator (TR-47)

## Contexte

**Friction** : F875, TR-47 (cf. `architecture-cible.md §5.2.7`)
**Sévérité** : P1 — schema `LigneParsee` change → imports historiques cassés à la re-validation

### Description

Cible :
1. `EtlImport.lignes_data_schema_version: int` (1, 2, 3...)
2. Service `LignesDataMigrator.migrate_to_current(lignes_data: dict, from_version: int) -> dict`
3. Au load `EtlImport.lignes_data` → if version < CURRENT → migrate in-memory

## Solution

### Migration

```python
def upgrade() -> None:
    op.add_column("etl_import", sa.Column(
        "lignes_data_schema_version", sa.Integer, nullable=False, server_default="1"
    ))
```

### Service migrator

```python
# app/services/catalogue/lignes_data_migrator.py (NEW)
CURRENT_LIGNES_DATA_VERSION = 2  # incrémenter à chaque breaking change

class LignesDataMigrator:
    @staticmethod
    def migrate_to_current(lignes_data: dict, from_version: int) -> dict:
        data = lignes_data
        for v in range(from_version, CURRENT_LIGNES_DATA_VERSION):
            migrate_fn = MIGRATIONS[v]  # 1→2, 2→3, etc.
            data = migrate_fn(data)
        return data


def _migrate_v1_to_v2(data: dict) -> dict:
    """V1 stockait `qty` int ; V2 stocke `qty_cents` BigInteger."""
    return {
        **data,
        "lines": [
            {**l, "qty_cents": l.pop("qty") * 100} for l in data.get("lines", [])
        ],
    }


MIGRATIONS = {1: _migrate_v1_to_v2}
```

### Hook au load

```python
# app/services/etl/import_loader.py
async def load_etl_import(import_id: int) -> EtlImport:
    imp = await db.get(EtlImport, import_id)
    if imp.lignes_data_schema_version < CURRENT_LIGNES_DATA_VERSION:
        imp.lignes_data = LignesDataMigrator.migrate_to_current(
            imp.lignes_data, imp.lignes_data_schema_version,
        )
        # Optionnel : persister la version migrée pour cache
    return imp
```

## DoD

- [ ] Colonne `lignes_data_schema_version` migration
- [ ] Service migrator avec test V1→V2
- [ ] Hook au load fonctionnel
- [ ] Test : import V1 historique re-validé → migré transparent

---

# Story B5.S2.T5 — `CatalogueProduitPriceHistory` audit (TR-46)

## Contexte

**Friction** : TR-46, F874 (cf. `architecture-cible.md §5.1`)
**Sévérité** : P1 — `_handle_ean_match` update `prix_unitaire_cts` du dernier import sans audit

### Description

Cible : table append-only `catalogue_produit_price_history` avec trigger AFTER UPDATE qui logue toute modification de `prix_unitaire_cts`.

## Solution

```python
def upgrade() -> None:
    op.create_table(
        "catalogue_produit_price_history",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("catalogue_produit_id", sa.Integer, ForeignKey("catalogue_produit.id")),
        sa.Column("tenant_id", sa.Integer, nullable=False),
        sa.Column("old_prix_cts", sa.BigInteger, nullable=True),
        sa.Column("new_prix_cts", sa.BigInteger, nullable=False),
        sa.Column("changed_by_etl_import_id", sa.Integer, nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute(text("""
        CREATE OR REPLACE FUNCTION catalogue_produit_price_history_log()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.prix_unitaire_cts IS DISTINCT FROM OLD.prix_unitaire_cts THEN
                INSERT INTO catalogue_produit_price_history (
                    catalogue_produit_id, tenant_id, old_prix_cts, new_prix_cts, changed_at
                ) VALUES (
                    OLD.id, OLD.tenant_id, OLD.prix_unitaire_cts, NEW.prix_unitaire_cts, NOW()
                );
            END IF;
            RETURN NEW;
        END $$ LANGUAGE plpgsql;
    """))
    op.execute(text("""
        CREATE TRIGGER trg_catalogue_produit_price_history
        AFTER UPDATE OF prix_unitaire_cts ON catalogue_produit
        FOR EACH ROW EXECUTE FUNCTION catalogue_produit_price_history_log()
    """))
```

## DoD

- [ ] Table `catalogue_produit_price_history` créée
- [ ] Trigger AFTER UPDATE actif
- [ ] Test : update prix → 1 row history créée
- [ ] Test : update sans changement prix → 0 row

---

# Story B5.S2.T6 — Tenant guard `peer_id` VPN (F1110)

## Contexte

**Friction** : F1110 (vague 5)
**Sévérité** : P1 — User A peut consulter peer VPN User B (autre tenant)
**Code source** : `app/services/wireguard.py`

### Description

Cible : avant retour `peer = WgService.get_peer(peer_id)`, vérifier `peer.tenant_id == request.tenant_id`. Si pas garanti côté WG service → ajouter check côté app.

## Solution

```python
# app/services/wireguard.py
class WireguardService:
    async def get_peer(self, peer_id: UUID, tenant_id: int) -> WgPeer:
        peer = await self.db.scalar(
            select(WgPeer).where(WgPeer.id == peer_id, WgPeer.tenant_id == tenant_id)
        )
        if peer is None:
            raise NotFound(f"WgPeer {peer_id}")  # 404 — pas 403 (info disclosure)
        return peer

    async def list_peers_for_user(self, user_id: UUID, tenant_id: int) -> list[WgPeer]:
        return await self.db.scalars(
            select(WgPeer).where(WgPeer.tenant_id == tenant_id, WgPeer.user_id == user_id)
        )
```

### Test

```python
async def test_get_peer_cross_tenant_returns_404(db, tenant_a, tenant_b):
    peer_b = WgPeer(tenant_id=tenant_b.id, user_id=user_b.id, public_key="...")
    db.add(peer_b); await db.commit()

    # User dans tenant_a tente de GET peer du tenant_b
    with pytest.raises(NotFound):
        await wg_service.get_peer(peer_b.id, tenant_id=tenant_a.id)
```

## DoD

- [ ] `WireguardService.get_peer(id, tenant_id)` filtre WHERE tenant_id
- [ ] Cross-tenant retour `NotFound` (404) — pas 403 pour éviter info disclosure
- [ ] Test : tenant A → peer B = 404

---

# Story B5.S2.T7 — `EtlImport` statut `ECHEC` explicit (TR-61)

## Contexte

**Friction** : TR-61, F986 (vague 5)
**Sévérité** : P1 — UI affiche "partiellement importé" alors que rien n'est passé

### Description

Cible : ENUM `etl_import_status` avec valeur `ECHEC` distincte de `PARTIEL`. Logique : `100% lignes en erreur → ECHEC` ; `> 0 lignes valides → PARTIEL` ; `100% OK → SUCCES`.

## Solution

```python
def upgrade() -> None:
    op.execute(text("""
        ALTER TYPE etl_import_status ADD VALUE IF NOT EXISTS 'ECHEC'
    """))
```

```python
# app/services/etl/import_finalizer.py
class EtlImportFinalizer:
    async def finalize(self, import_id: int):
        imp = await self.db.get(EtlImport, import_id)
        nb_ok = imp.nb_lignes_valides
        nb_total = imp.nb_lignes_totales
        if nb_total == 0 or nb_ok == 0:
            imp.statut = "ECHEC"
        elif nb_ok < nb_total:
            imp.statut = "PARTIEL"
        else:
            imp.statut = "SUCCES"
```

### Test

```python
async def test_etl_import_zero_lines_valid_status_echec(db, tenant):
    imp = EtlImport(tenant_id=tenant.id, nb_lignes_totales=100, nb_lignes_valides=0)
    await finalizer.finalize(imp.id)
    assert imp.statut == "ECHEC"

async def test_etl_import_partial_status(db, tenant):
    imp = EtlImport(tenant_id=tenant.id, nb_lignes_totales=100, nb_lignes_valides=50)
    await finalizer.finalize(imp.id)
    assert imp.statut == "PARTIEL"
```

## DoD

- [ ] ENUM ajout `ECHEC`
- [ ] Logique `EtlImportFinalizer` avec 3 branches
- [ ] Test : 0 valides → ECHEC ; 50/100 → PARTIEL ; 100/100 → SUCCES
- [ ] Frontend : badge UI distingue ECHEC (rouge) de PARTIEL (orange)

---

# Story B5.S2.T8 — Table `categorie_produit_seed` M00 (Q29=A)

## Contexte

**Décision** : **Q29=A** (verrouillée 2026-04-27) — Split référentiel ETL per-tenant + seed M00 read-only `categorie_produit_seed` (91 codes canoniques) copié vers `categorie_produits` per-tenant au provisioning
**Référence** : `50-sql-schema.md §13.1` (DDL déjà rédigé), `51-alembic-migrations.md` ligne 66 (migration prévue B5.S2)
**Sévérité** : P0 — sans seed M00, le provisioning d'un nouveau tenant épicerie/restaurant (B7.S4.T2) n'a pas de référentiel de catégories canoniques à copier
**Code source** : `app/models/categorie_produit_seed.py` (NEW)

### Description

Cible (Q29=A) :
1. Table `categorie_produit_seed` (PAS de `tenant_id` — read-only global DEVUP)
2. Seed 91 catégories canoniques (legumes, fruits, viandes, ...) avec TVA défaut
3. Helper `seed_categorie_produits_for_tenant(tenant_id)` au provisioning B7.S4.T2

## Solution

### Migration

```python
# alembic/versions/a2b3c4d5e6f8_create_categorie_produit_seed.py
def upgrade() -> None:
    op.create_table(
        "categorie_produit_seed",
        sa.Column("code", sa.String(50), primary_key=True),
        sa.Column("parent_code", sa.String(50), sa.ForeignKey("categorie_produit_seed.code", ondelete="SET NULL"), nullable=True),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("tva_defaut", sa.Numeric(5, 4), nullable=False, server_default="0.20"),
        sa.Column("is_food", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute(text("""
        COMMENT ON TABLE categorie_produit_seed IS
        'Seed M00 read-only des catégories alimentaires (91 codes). Copié vers categorie_produits per-tenant au provisioning. Bloc 5 Q29=A.'
    """))
    # Seed 91 codes canoniques (extrait — full seed dans 50-sql-schema §13.1)
    op.execute(text("""
        INSERT INTO categorie_produit_seed (code, label, tva_defaut, is_food) VALUES
        ('legumes', 'Légumes', 0.055, true),
        ('fruits', 'Fruits', 0.055, true),
        ('viandes', 'Viandes', 0.055, true),
        ('poissons', 'Poissons', 0.055, true),
        ('produits_laitiers', 'Produits laitiers', 0.055, true),
        ('boulangerie', 'Boulangerie', 0.055, true),
        ('boissons_alcoolisees', 'Boissons alcoolisées', 0.20, true),
        ('boissons_non_alcoolisees', 'Boissons non alcoolisées', 0.10, true),
        ('epicerie_salee', 'Épicerie salée', 0.20, true),
        ('epicerie_sucree', 'Épicerie sucrée', 0.055, true),
        -- ... 81 autres codes (cf. 50-sql-schema §13.1 pour seed complet)
        ('autre', 'Autre', 0.20, false)
        ON CONFLICT (code) DO NOTHING
    """))


def downgrade() -> None:
    op.drop_table("categorie_produit_seed")
```

### Modèle ORM (read-only)

```python
# app/models/categorie_produit_seed.py (NEW)
class CategorieProduitSeed(Base):
    """Q29=A — read-only seed M00 des 91 catégories alimentaires canoniques.

    PAS de tenant_id : table globale DEVUP partagée comme template.
    Copiée vers categorie_produits per-tenant au provisioning (cf. B7.S4.T2).
    """
    __tablename__ = "categorie_produit_seed"
    __table_args__ = {"info": {"is_seed": True, "read_only": True}}

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    parent_code: Mapped[str | None] = mapped_column(ForeignKey("categorie_produit_seed.code", ondelete="SET NULL"), nullable=True)
    label: Mapped[str] = mapped_column(String(255))
    tva_defaut: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.20"))
    is_food: Mapped[bool] = mapped_column(default=True)
```

### Helper provisioning

```python
# app/services/provisioning/categorie_produit_seed.py (NEW)
async def copy_categorie_produit_seed_to_tenant(db: AsyncSession, tenant_id: int):
    """Q29=A — copier seed M00 vers categorie_produits du nouveau tenant.

    Appelé par B7.S4.T2 (ProvisioningService._seed_vertical) si vertical ∈ ('epicerie', 'restaurant').
    """
    seeds = await db.scalars(select(CategorieProduitSeed))
    for s in seeds.all():
        db.add(CategorieProduit(
            tenant_id=tenant_id,
            code=s.code,
            libelle=s.label,
            tva_defaut=s.tva_defaut,
            is_food=s.is_food,
            parent_code=s.parent_code,  # référence interne — préservée
        ))
    # Note : parent_code FK pointera vers categorie_produit du même tenant après commit
```

### CI invariant

```python
# tools/check_categorie_produit_seed_readonly.py (NEW)
"""Refuse INSERT/UPDATE/DELETE sur categorie_produit_seed depuis le code applicatif.

Migration alembic peut écrire (étape seed initiale + future ajout codes), mais pas le runtime.
"""
import re, sys
from pathlib import Path

PATTERN = re.compile(r"db\.add\(CategorieProduitSeed\(|delete\(CategorieProduitSeed\)|update\(CategorieProduitSeed\)")

violations = []
for py in Path("app").rglob("*.py"):
    if PATTERN.search(py.read_text()):
        violations.append(str(py))

if violations:
    print(f"❌ Q29=A — categorie_produit_seed est read-only runtime : {violations}")
    sys.exit(1)
print("✅ Q29=A — seed read-only respecté")
```

### Tests

```python
async def test_seed_91_codes_seeded(db):
    count = await db.scalar(select(func.count()).select_from(CategorieProduitSeed))
    assert count >= 91

async def test_seed_copy_to_new_tenant(db, tenant_new_epicerie):
    await copy_categorie_produit_seed_to_tenant(db, tenant_new_epicerie.id)
    count = await db.scalar(
        select(func.count()).select_from(CategorieProduit).where(CategorieProduit.tenant_id == tenant_new_epicerie.id)
    )
    assert count >= 91
    # Tva defaut copiée
    legumes = await db.scalar(
        select(CategorieProduit).where(
            CategorieProduit.tenant_id == tenant_new_epicerie.id,
            CategorieProduit.code == "legumes",
        )
    )
    assert legumes.tva_defaut == Decimal("0.055")

async def test_seed_readonly_runtime(db):
    """Tentative d'INSERT/UPDATE/DELETE depuis runtime → script CI fail."""
    # Test runtime : les ORM operations passent (pas de trigger), mais CI script bloque le merge
    result = subprocess.run(
        [sys.executable, "tools/check_categorie_produit_seed_readonly.py"],
        capture_output=True,
    )
    assert result.returncode == 0
```

## DoD

- [ ] **Q29=A livré** : table `categorie_produit_seed` créée + seed 91 codes
- [ ] Modèle ORM `CategorieProduitSeed` (read-only flag info)
- [ ] Helper `copy_categorie_produit_seed_to_tenant` opérationnel (sera appelé par B7.S4.T2)
- [ ] Script CI `check_categorie_produit_seed_readonly.py` actif
- [ ] Test : 91 codes seedés
- [ ] Test : copie helper crée 91 categorie_produit per nouveau tenant
- [ ] Cohérence avec `50-sql-schema.md §13.1` (DDL alignée)

---

## Critères de succès Sprint B5.S2

- [ ] **TR-39 résolu** : `tenant_id NOT NULL` sur `CatalogueProduit`, `CategorieProduit`, `EtlCorrectionHistory` + RLS
- [ ] **TR-40 résolu** : trigger DB cross-tenant validation `IngredientEpicerieMapping.produit_id`
- [ ] **F869 résolu** : `UNIQUE(tenant_id, ean)` sur `epicerie_produits`
- [ ] **TR-47 résolu** : `lignes_data_schema_version` + migrator V1→V2
- [ ] **TR-46 résolu** : `catalogue_produit_price_history` audit append-only
- [ ] **F1110 résolu** : tenant guard `peer_id` VPN
- [ ] **TR-61 résolu** : `ECHEC` distinct `PARTIEL`
- [ ] **Q29=A seed M00 livré** : `categorie_produit_seed` 91 codes + helper provisioning + CI invariant
- [ ] Test cross-tenant : Marveline ETL ne fuit pas vers CaroCorp

---

**Fin du document — 15-sprint-B5.S2.md**

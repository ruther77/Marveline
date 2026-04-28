# Conventions — Migrations Alembic

## Principe : Expand/Contract

Toute migration suit la stratégie expand/contract en 3 phases :

1. **Expand** : ajouter les nouvelles colonnes/tables (nullable ou avec default)
2. **Backfill** : migrer les données existantes
3. **Contract** : rendre NOT NULL, supprimer l'ancienne colonne/table

```
# Jamais de DROP COLUMN direct
# Jamais de ALTER COLUMN ... NOT NULL sans default ou backfill
```

## Exemple Expand/Contract

```python
# Migration 1 — Expand : ajout colonne nullable
def upgrade():
    op.add_column('products', sa.Column('external_ref', sa.String(100), nullable=True))

# (déploiement intermédiaire — code lit les deux colonnes)

# Migration 2 — Backfill (dans un script ou migration séparée)
# UPDATE products SET external_ref = 'LEGACY-' || id WHERE external_ref IS NULL

# Migration 3 — Contract : rendre NOT NULL
def upgrade():
    op.alter_column('products', 'external_ref', nullable=False)
```

## Création d'une Migration — Workflow Canonique

> ⚠️  **JAMAIS créer un fichier migration à la main** avec un `down_revision` inventé.
> Toujours utiliser `make new-migration` pour que le `down_revision` soit fixé automatiquement à la vraie head en base.

```bash
# 1. Créer la migration (down_revision correct automatiquement)
make new-migration MSG="add external_ref to products"

# 2. Ouvrir le fichier généré dans alembic/versions/
#    → ajuster upgrade() / downgrade() si autogenerate est insuffisant
#    → ajouter le docstring stratégie/rollback/impact

# 3. Valider la chaîne (détecte révisions orphelines + têtes multiples)
make migration-check

# 4. Appliquer
make migrate

# 5. Rollback si besoin
make rollback
```

### Têtes multiples (branches)

Si `make migration-check` détecte plusieurs têtes :

```bash
# Créer une migration de merge
make new-migration MSG="merge heads"
# Alembic génère automatiquement un merge commit avec les deux parents dans down_revision
make migrate
```

## Structure d'une Migration

```python
"""add_external_ref_to_products

Revision ID: abc123def456
Revises: prev_revision_id
Create Date: 2026-01-15 10:30:00

Strategy: expand/contract — phase 1/3 (add nullable column)
Rollback: safe — DROP COLUMN
Impact: no data loss
"""
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.add_column(
        'products',
        sa.Column('external_ref', sa.String(100), nullable=True)
    )
    # Index si colonne filtrée
    op.create_index('ix_products_external_ref', 'products', ['external_ref'])

def downgrade() -> None:
    op.drop_index('ix_products_external_ref', table_name='products')
    op.drop_column('products', 'external_ref')
```

## Timestamps Obligatoires

```python
# Toujours ajouter created_at + updated_at sur les nouvelles tables
op.create_table(
    'my_table',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('tenant_id', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
)
op.create_index('ix_my_table_tenant_id_id', 'my_table', ['tenant_id', 'id'])
```

## Dry-Run CI (Audit)

```bash
# Vérifier que la migration ne contient pas d'opérations destructives
alembic upgrade head --sql | grep -E "DROP TABLE|DROP COLUMN|ALTER.*NOT NULL"
# Si output non vide → bloquer le CI
```

## Test No-Destructive-Migration

```python
# tests/test_migrations.py
def test_no_destructive_migration(migration_sql: str):
    """Ensure migrations don't drop columns/tables directly"""
    forbidden = ["DROP TABLE", "DROP COLUMN", "TRUNCATE"]
    for keyword in forbidden:
        assert keyword not in migration_sql.upper(), \
            f"Destructive migration detected: {keyword}"
```

## Règles

- Toute migration = expand/contract uniquement
- Documenter la stratégie dans le docstring de la migration
- Jamais de `DROP TABLE` ou `DROP COLUMN` direct
- `tenant_id NOT NULL` + index composite sur toutes les nouvelles tables métier
- `created_at` + `updated_at` + `is_active` sur toutes les nouvelles tables
- Downgrade toujours implémenté (même si simple)
- Migration testée en CI avec dry-run `--sql`

## Checklist Nouvelle Migration

- ☐ Créée via `make new-migration MSG="..."` (jamais à la main)
- ☐ `make migration-check` passe (chaîne valide, 1 tête)
- ☐ Stratégie expand/contract documentée dans le docstring
- ☐ `tenant_id NOT NULL` + FK si table métier
- ☐ Index composite `(tenant_id, id)` créé
- ☐ `created_at` / `updated_at` / `is_active` présents
- ☐ `downgrade()` implémenté
- ☐ Dry-run `--sql` vérifié (pas de DROP)
- ☐ `make migrate` appliqué et validé localement avant commit

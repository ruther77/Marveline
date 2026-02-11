# Instructions pour Claude

## Règles de Documentation

### ❌ NE JAMAIS faire

- **Ne jamais mentionner "Claude" ou "Claude Sonnet 4.5" dans les fichiers du projet**
  - Pas dans les commits (pas de Co-Authored-By: Claude...)
  - Pas dans les fichiers markdown (PHASE_*.md, README.md, etc.)
  - Pas dans les commentaires de code
  - Pas dans la documentation

### ✅ À faire à la place

- Utiliser "Généré automatiquement" ou "Généré par IA"
- Omettre complètement l'auteur si non nécessaire
- Se concentrer sur le contenu technique, pas sur l'origine

---

## Architecture CaroCorp

### Base de données
- PostgreSQL 16 (port 5433)
- Multi-tenant avec tenant_id sur toutes les tables métier
- Montants en **BigInteger centimes** (cohérence avec MassaCorp)

### Stack technique
- Backend : FastAPI + SQLAlchemy 2.0
- ORM : Mapped types (SQLAlchemy 2.x)
- Migrations : Alembic
- Tests : pytest

### Patterns clés
- Soft delete : SoftDeleteMixin (is_active boolean)
- Timestamps : TimestampMixin (created_at, updated_at)
- Multi-tenant : TenantMixin (tenant_id)

---

## Conventions de code

### Migrations Alembic
- Messages descriptifs : "add_indexes_on_foreign_keys"
- Toujours implémenter upgrade() ET downgrade()
- Vérifier que les modèles sont importés dans app/models/__init__.py

### Tests
- Structure : tests/{unit,integration,e2e,security}/
- Fixtures dans conftest.py
- 100% des contraintes CHECK doivent être testées

### Commits
- Format : "feat:", "fix:", "docs:", "test:", "refactor:"
- Messages en français
- **Pas de Co-Authored-By mentionnant Claude**

---

## Décisions architecturales

### Montants en centimes
- Tous les montants monétaires : BigInteger
- 250 = 2.50€
- Évite les erreurs d'arrondi Float/Decimal
- Cohérence avec MassaCorp

### Foreign Keys
- RESTRICT : Protéger données (Customer → Reservation, Product → ReservationLine)
- CASCADE : Nettoyer automatiquement (Reservation → ReservationLine, Reservation → Invoice)
- passive_deletes=True dans relationships SQLAlchemy si RESTRICT

### Indexes
- Tous les tenant_id doivent avoir un index
- Toutes les foreign keys doivent avoir un index (performance)
- Unique composés : (tenant_id, colonne_unique)

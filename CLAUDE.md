# CLAUDE.md — CaroCorp_new

## Context Engine (OBLIGATOIRE)

Au demarrage de chaque session, appeler `mcp__context-engine__bootstrap()`.
Avant d'editer un fichier Python, appeler `mcp__context-engine__prepare(file_path="chemin/relatif")`.
Le hook PreToolUse bloquera toute edition non preparee.

## Stack

FastAPI + SQLAlchemy 2.0 + Pydantic 2.x + PostgreSQL 16 + Alembic + Celery + Redis.
Frontend: React + TypeScript. Docker Compose pour tous les services.

## Conventions critiques

- Montants monetaires: BigInteger centimes (250 = 2.50 EUR)
- Multi-tenant: `tenant_id NOT NULL` sur toute table metier, index composite `(tenant_id, id)`, filtre obligatoire. Violation = P0.
- Soft delete: `is_active BOOLEAN` via SoftDeleteMixin
- Timestamps: `created_at`, `updated_at` obligatoires via TimestampMixin
- Migrations: expand/contract uniquement, jamais destructive directe
- Exceptions: `NotFound` (pas `NotFoundError`) depuis `app.core.exceptions`
- Pas de secret hardcode, pas de strings magiques, pas d'endpoint sans auth
- Constantes: utiliser `app/constants/` (business.py, errors.py, security.py, http.py, limits.py). Jamais de strings hardcodees pour concepts metier.

## Tests

Commande Docker: `docker compose run --rm --entrypoint "" api python -m pytest tests/ -v`
pytest-asyncio mode strict: `@pytest.mark.asyncio` obligatoire.
Minimum de mocks, implementations reelles preferees.

## Regles globales

Les regles completes (securite, CI/CD, RGPD, observabilite, workflow Git) sont dans `~/.claude/CLAUDE.md`.

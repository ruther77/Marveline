# CLAUDE.md — CaroCorp / FUTUR PROJ

## Context Engine
Avant d'éditer un fichier Python : `mcp__context-engine__prepare(file_path="chemin/relatif")` OBLIGATOIRE.
Le hook PreToolUse bloquera toute édition non préparée.
`explore(module)` pour orientation ciblée. `bootstrap()` seulement si refactoring >5 fichiers inconnus.

## Stack
- Backend : FastAPI + SQLAlchemy 2.0 + Pydantic 2.x + PostgreSQL 16 + Alembic + Celery + Redis
- Frontend : React + TypeScript + TanStack Router v1 + TanStack Query + Zustand + Vitest
- Infra : Docker Compose, 3 apps frontend (Marveline, Restaurant, Épicerie)

## Conventions critiques
- Montants : BigInteger centimes (250 = 2,50€)
- Multi-tenant : `tenant_id NOT NULL`, filtre repository, violation = P0
- Soft delete : `is_active` via SoftDeleteMixin
- Exceptions : `NotFound` depuis `app.core.exceptions`
- Constantes : `app/constants/` (jamais de strings hardcodées)
- Conventions détaillées : `docs/conventions/INDEX.md`

## Definition of Done
Code conforme · Tests passés · Schemas/types/__init__ cohérents · Auth+RBAC+tenant vérifié · Migration non-destructive · Preuve (commande + résultat) rapportée.

## Compact instructions
Préserver : bugs ouverts, fichiers modifiés, décisions utilisateur, erreurs et fix.
Supprimer : outputs verbeux, contenus de fichiers explorés, pistes abandonnées.

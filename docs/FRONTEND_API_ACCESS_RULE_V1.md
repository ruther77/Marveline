# Frontend API Access Rule V1

Date: 2026-03-05
Status: Locked V1.0
Decision reference: `docs/PHASE1_FRONTEND_BACKEND_ALIGNMENT.md` (Decisions ratifiees)

## Rule
- Les imports `@/api/*` sont autorisés uniquement dans:
  - `frontend/src/api/**`
  - `frontend/src/api/queries/**`
- Toute page/composant/store/hook hors ces dossiers doit consommer l'API via hooks query (ou un adaptateur validé).

## Transitional policy
- La dette existante est tolérée temporairement via allowlist:
  - `frontend/config/api-access-allowlist.json`
- Aucune nouvelle violation hors allowlist n'est autorisée.

## Enforcement
- Checker: `frontend/scripts/check-api-access.mjs`
- Commande: `cd frontend && npm run check:api-access`
- Exit code:
  - `0` si aucune nouvelle violation
  - `1` si nouvelle violation détectée

## Removal strategy (debt burn-down)
1. Retirer des fichiers de l'allowlist lot par lot (par usage U1..U12).
2. Quand l'allowlist est vide: convertir la règle en hard gate CI bloquant.

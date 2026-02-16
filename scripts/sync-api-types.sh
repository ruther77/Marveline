#!/usr/bin/env bash
# sync-api-types.sh — Export OpenAPI schema + generate TypeScript types
#
# Usage:
#   ./scripts/sync-api-types.sh          # Run via Docker (default)
#   ./scripts/sync-api-types.sh --local  # Run locally (needs FastAPI installed)
#
# Outputs:
#   docs/openapi.json                         — OpenAPI 3.x JSON schema
#   docs/API_CONTRACT.md                      — Human-readable API contract
#   frontend/openapi.json                     — Copy for openapi-typescript
#   frontend/src/api/generated/schema.ts      — TypeScript types

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo "=== Sync API Types ==="
echo ""

# Step 1: Export OpenAPI schema
echo "[1/3] Exporting OpenAPI schema from FastAPI..."
if [[ "${1:-}" == "--local" ]]; then
    cd "$PROJECT_ROOT"
    python3 scripts/export_openapi.py
else
    cd "$PROJECT_ROOT"
    docker compose run --rm --no-deps --entrypoint "" api python scripts/export_openapi.py
fi
echo ""

# Step 2: Generate TypeScript types
echo "[2/3] Generating TypeScript types..."
cd "$FRONTEND_DIR"

# Ensure generated directory exists
mkdir -p src/api/generated

# Run openapi-typescript
npx openapi-typescript ./openapi.json -o src/api/generated/schema.ts
echo "  schema.ts -> frontend/src/api/generated/schema.ts"
echo ""

# Step 3: Type check
echo "[3/3] Verifying TypeScript compilation..."
npx tsc --noEmit
echo "  TypeScript: OK"
echo ""

# Summary
ENDPOINTS=$(grep -c '"/' "$FRONTEND_DIR/openapi.json" 2>/dev/null || echo "?")
echo "=== Done ==="
echo "  docs/openapi.json           — OpenAPI schema"
echo "  docs/API_CONTRACT.md        — Human-readable contract"
echo "  frontend/src/api/generated/ — TypeScript types"
echo ""
echo "Run this after any backend schema change (model, endpoint, response)."

# Makefile — CaroCorp_new
# Commandes courantes pour le développement

.PHONY: help sync-api-types export-openapi generate-ts test test-unit test-security build lint

help: ## Afficher cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# === API Contract Sync ===

sync-api-types: ## Export OpenAPI + generate TypeScript types (Docker)
	@./scripts/sync-api-types.sh

sync-api-types-local: ## Export OpenAPI + generate TypeScript types (local)
	@./scripts/sync-api-types.sh --local

export-openapi: ## Export OpenAPI schema only (Docker)
	@docker compose run --rm --no-deps --entrypoint "" api python scripts/export_openapi.py

generate-ts: ## Generate TypeScript types from existing openapi.json
	@cd frontend && npx openapi-typescript ./openapi.json -o src/api/generated/schema.ts

# === Tests ===

test: ## Run all backend tests (Docker)
	@docker compose run --rm --no-deps --entrypoint "" api python -m pytest tests/ -v

test-unit: ## Run unit tests only (Docker)
	@docker compose run --rm --no-deps --entrypoint "" api python -m pytest tests/unit/ -v --override-ini="addopts="

test-security: ## Run security tests only (Docker)
	@docker compose run --rm --no-deps --entrypoint "" api python -m pytest tests/security/ -v

test-frontend: ## Run frontend tests
	@cd frontend && npx vitest run

# === Build & Lint ===

build: ## Build frontend for production
	@cd frontend && npx vite build

lint: ## Lint frontend
	@cd frontend && npx eslint . --ext ts,tsx

typecheck: ## TypeScript type check
	@cd frontend && npx tsc --noEmit

# === Docker ===

up: ## Start all services
	@docker compose up -d

down: ## Stop all services
	@docker compose down

logs: ## Follow API logs
	@docker compose logs -f api

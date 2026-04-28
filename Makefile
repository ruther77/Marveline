# Makefile — CaroCorp_new
# Commandes courantes pour le développement

.PHONY: help \
	sync-api-types sync-api-types-local export-openapi generate-ts \
	test test-unit test-security test-frontend test-cov test-e2e test-e2e-ui \
	quality-gate quality-gate-fast \
	build lint typecheck \
	up down watch status restart restart-api restart-frontend \
	dev-up dev-down dev-watch \
	rebuild rebuild-api rebuild-frontend \
	migrate rollback new-migration migration-check \
	shell-api shell-db shell-frontend \
	logs logs-all logs-frontend logs-worker logs-beat logs-db \
	seed seed-demo \
	celery-purge celery-inspect \
	db-backup db-reset

help: ## Afficher cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

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

DEV_RUN = docker compose run --rm --entrypoint ""

test: ## Run all backend tests (Docker — bind-mount src)
	@$(DEV_RUN) api python -m pytest tests/ -v

test-unit: ## Run unit tests only (Docker)
	@$(DEV_RUN) api python -m pytest tests/unit/ -v --override-ini="addopts="

test-security: ## Run security tests only (Docker)
	@$(DEV_RUN) api python -m pytest tests/security/ -v

test-frontend: ## Run frontend Vitest tests
	@cd frontend && npx vitest run

test-e2e: ## Run Playwright E2E tests
	@cd frontend && npx playwright test

test-e2e-ui: ## Run Playwright E2E avec interface graphique
	@cd frontend && npx playwright test --ui

test-e2e-demo: ## Lancer le pipeline de démonstration (record mobile)
	@bash scripts/demo/run_demo.sh

test-cov: ## Run backend tests with HTML coverage report
	@$(DEV_RUN) api \
		python -m pytest tests/ -v --cov=app --cov-report=html --cov-report=term-missing
	@echo "Coverage report: htmlcov/index.html"

quality-gate-fast: ## Senior gate rapide: lint + typecheck + unit tests + frontend tests
	@$(MAKE) lint
	@$(MAKE) typecheck
	@$(MAKE) test-unit
	@$(MAKE) test-frontend

quality-gate: ## Senior gate complet: lint + typecheck + tests backend + security + frontend
	@$(MAKE) lint
	@$(MAKE) typecheck
	@$(MAKE) test
	@$(MAKE) test-security
	@$(MAKE) test-frontend

# === Build & Lint ===

build: ## Build frontend for production (local)
	@cd frontend && npx vite build

lint: ## Lint frontend TypeScript
	@cd frontend && npx eslint . --ext ts,tsx

typecheck: ## TypeScript type check (no emit)
	@cd frontend && npx tsc --noEmit

# === Docker — Lifecycle ===

up: ## Start all services in background (mode prod)
	@docker compose up -d

down: ## Stop and remove all containers
	@docker compose down

watch: ## Start with auto-rebuild on package.json change and sync on source change
	@docker compose up -d --wait
	@docker compose watch

dev-up: up ## Alias — docker compose up lit .env automatiquement

dev-down: down ## Alias

dev-watch: ## Compose Watch (auto-sync + rebuild)
	@docker compose up -d --wait
	@docker compose watch

status: ## Show status of all containers
	@docker compose ps

restart: ## Restart all services
	@docker compose restart

restart-api: ## Restart API + reverse-proxy
	@docker compose restart api reverse-proxy

restart-frontend: ## Restart frontend + reverse-proxy
	@docker compose restart frontend-marveline frontend-epicerie frontend-restaurant reverse-proxy

# === Docker — Rebuild ===

rebuild: ## Rebuild all images (no cache)
	@docker compose build --no-cache

rebuild-api: ## Rebuild + restart API
	@docker compose build api && docker compose up -d api

rebuild-frontend: ## Rebuild + restart frontend Marveline
	@docker compose build frontend-marveline && docker compose up -d frontend-marveline

rebuild-all-frontends: ## Rebuild les 3 frontends
	@docker compose build frontend-marveline frontend-epicerie frontend-restaurant \
		&& docker compose up -d frontend-marveline frontend-epicerie frontend-restaurant

deploy-dev: ## Rebuild API + frontend + restart tout
	@docker compose build api frontend-marveline \
		&& docker compose up -d api frontend-marveline

# === Database ===

migrate: ## Run pending Alembic migrations (bind-mount src — garantit code à jour)
	@$(DEV_RUN) api alembic upgrade head

rollback: ## Rollback last Alembic migration
	@$(DEV_RUN) api alembic downgrade -1

new-migration: ## Créer une migration (MSG obligatoire — ex: make new-migration MSG="add foo to bar")
	@test -n "$(MSG)" || (echo "❌  MSG requis — ex: make new-migration MSG=\"add foo to bar\""; exit 1)
	@$(DEV_RUN) api alembic revision --autogenerate -m "$(MSG)"
	@echo "✅  Migration créée. Vérifiez upgrade()/downgrade() avant make migrate."

migration-check: ## Valider la chaîne Alembic (1 tête, base à jour)
	@echo "🔍  Vérification chaîne Alembic..."
	@HEAD_COUNT=$$($(DEV_RUN) api alembic heads 2>/dev/null | grep -c "(head)" || echo 0); \
	if [ "$$HEAD_COUNT" -ne 1 ]; then \
		echo "❌  $$HEAD_COUNT têtes détectées (attendu: 1). Créez un merge : make new-migration MSG=\"merge heads\""; \
		exit 1; \
	fi
	@$(DEV_RUN) api alembic current 2>/dev/null | grep -q "(head)" \
		&& echo "✅  Chaîne Alembic valide — 1 tête, base à jour." \
		|| (echo "⚠️   Base non à jour — lancez: make migrate" && exit 1)

# === Shells ===

shell-api: ## Open bash shell in API container
	@docker compose exec api bash

shell-db: ## Open psql in database container
	@docker compose exec db psql -U $${POSTGRES_USER:-caro} -d $${POSTGRES_DB:-CaroCorp}

shell-frontend: ## Open sh shell in frontend container
	@docker compose exec frontend sh

# === Logs ===

logs: ## Follow API logs
	@docker compose logs -f api

logs-all: ## Follow logs for all services
	@docker compose logs -f

logs-frontend: ## Follow frontend logs
	@docker compose logs -f frontend

logs-worker: ## Follow Celery worker logs
	@docker compose logs -f celery-worker

logs-beat: ## Follow Celery beat logs
	@docker compose logs -f celery-beat

logs-db: ## Follow PostgreSQL logs
	@docker compose logs -f db

# === Data ===

seed: ## Seed données de développement
	@docker compose run --rm --entrypoint "" api python scripts/seed_data.py

seed-demo: ## Seed données de démonstration commerciale
	@docker compose run --rm --entrypoint "" api python scripts/demo/seed_marveline_demo.py

# === Celery ===

celery-purge: ## Vider toutes les queues Celery
	@docker compose exec celery-worker celery -A app.tasks.celery_app:celery_app purge -f

celery-inspect: ## Inspecter les workers Celery actifs
	@docker compose exec celery-worker celery -A app.tasks.celery_app:celery_app inspect active

# === Database (dev uniquement) ===

db-backup: ## Dump PostgreSQL → backups/marveline_YYYYMMDD_HHMMSS.sql
	@mkdir -p backups
	@docker compose exec db pg_dump -U $${POSTGRES_USER:-marveline} $${POSTGRES_DB:-marveline} \
		> backups/marveline_$$(date +%Y%m%d_%H%M%S).sql
	@echo "Backup créé dans backups/"

db-reset: ## ⚠️  DROP + recreate + migrate — DEV UNIQUEMENT
	@echo "⚠️  Cette commande détruit la base. Ctrl+C pour annuler (3s)..."
	@sleep 3
	@docker compose exec db psql -U $${POSTGRES_USER:-marveline} -c "DROP DATABASE IF EXISTS $${POSTGRES_DB:-marveline};"
	@docker compose exec db psql -U $${POSTGRES_USER:-marveline} -c "CREATE DATABASE $${POSTGRES_DB:-marveline};"
	@docker compose exec api alembic upgrade head

# === Ngrok tunnel ===

ngrok-up: ## Lance le tunnel ngrok (expose le reverse proxy en HTTPS public)
	@docker compose --profile tunnel up ngrok -d
	@sleep 3
	@./scripts/ngrok-url.sh

ngrok-down: ## Arrête le tunnel ngrok
	@docker compose --profile tunnel stop ngrok && docker compose --profile tunnel rm -f ngrok

ngrok-url: ## Affiche l'URL publique ngrok (statique si NGROK_DOMAIN défini)
	@./scripts/ngrok-url.sh

ngrok-logs: ## Suit les logs du tunnel ngrok
	@docker compose --profile tunnel logs -f ngrok

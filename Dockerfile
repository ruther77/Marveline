# ===================================================================
# STAGE 1 : builder — toutes les dépendances (dev + prod)
# Utilisé en CI pour exécuter pytest, lint, etc.
# ===================================================================
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc postgresql-client curl \
    libpango-1.0-0 libpangoft2-1.0-0 libcairo2 \
    libgdk-pixbuf-xlib-2.0-0 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

RUN pip install poetry==1.8.3

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

COPY . .

RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ===================================================================
# STAGE 2 : deps — installe les dépendances prod (avec gcc)
# ===================================================================
FROM python:3.11-slim AS deps

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install poetry==1.8.3

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi

# ===================================================================
# STAGE 3 : production — image légère sans gcc/poetry/tests
# Copie uniquement les packages installés depuis le stage deps
# ===================================================================
FROM python:3.11-slim AS production

WORKDIR /app

# Runtime deps uniquement (pas gcc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client curl \
    libpango-1.0-0 libpangoft2-1.0-0 libcairo2 \
    libgdk-pixbuf-xlib-2.0-0 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copier les packages Python installés depuis le stage deps
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

COPY . .

# Répertoires runtime
RUN mkdir -p /app/uploads /app/keys \
    && useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Décisions — Pre-commit Hooks

## Configuration

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.9.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, sqlalchemy, fastapi]
        args: [--strict, --ignore-missing-imports]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-merge-conflict
      - id: detect-private-key   # Bloque les secrets accidentels
      - id: no-commit-to-branch
        args: [--branch, main, --branch, production]

  - repo: https://github.com/zricethezav/gitleaks
    rev: v8.18.2
    hooks:
      - id: gitleaks  # Scan secrets dans les diffs
```

## Installation

```bash
pip install pre-commit
pre-commit install
pre-commit install --hook-type commit-msg  # Pour conventional commits

# Tester sans commit
pre-commit run --all-files
```

## Conventional Commits (commitlint)

```json
// commitlint.config.js
module.exports = {
    extends: ['@commitlint/config-conventional'],
    rules: {
        'type-enum': [2, 'always', [
            'feat', 'fix', 'docs', 'style', 'refactor',
            'test', 'chore', 'perf', 'ci', 'revert',
        ]],
        'subject-max-length': [2, 'always', 100],
        'body-max-line-length': [2, 'always', 200],
    },
};
```

```bash
# .husky/commit-msg
#!/bin/sh
npx --no -- commitlint --edit "$1"
```

## Ruff Configuration

```toml
# pyproject.toml
[tool.ruff]
target-version = "py312"
line-length = 100
select = [
    "E", "F", "W",  # pycodestyle + pyflakes
    "I",             # isort
    "N",             # pep8-naming
    "UP",            # pyupgrade
    "B",             # flake8-bugbear
    "S",             # flake8-bandit (sécurité)
    "ANN",           # annotations
]
ignore = ["ANN101", "ANN102", "S101"]  # S101 = assert OK en tests

[tool.ruff.per-file-ignores]
"tests/**/*.py" = ["S", "ANN"]  # Désactiver sécurité + annotations en tests
```

## mypy Configuration

```toml
# pyproject.toml
[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy", "sqlalchemy.ext.mypy.plugin"]
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
```

## Makefile Targets

```makefile
# Makefile
.PHONY: lint typecheck test quality-gate quality-gate-fast

lint:
	ruff check . --fix
	ruff format .

typecheck:
	mypy app/ --strict

test:
	docker compose run --rm --entrypoint "" api python -m pytest tests/ -v --cov=app --cov-fail-under=80

test-fast:
	python -m pytest tests/unit/ -v

quality-gate: lint typecheck test

quality-gate-fast: lint typecheck test-fast
```

## Règles

- `pre-commit install` exécuté sur chaque nouveau clone
- `ruff` + `mypy` obligatoires en CI (bloquants)
- `gitleaks` pour détecter les secrets accidentels
- `no-commit-to-branch` sur `main` et `production`
- Conventional Commits vérifiés par `commitlint`
- `make quality-gate-fast` avant tout push (lint + typecheck + tests unitaires)

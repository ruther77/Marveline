# Erreurs et Oublis Détectés - CaroCorp

**Date** : 2026-02-11  
**Statut** : 🔴 7 erreurs critiques + 5 oublis mineurs

---

## 🔴 ERREURS CRITIQUES

### 1. Docker Compose - Mauvais chemin Celery
**Fichier** : `docker-compose.yml:73`  
**Erreur** : Pointe vers `app.core.celery:celery_app`  
**Réalité** : Le fichier est `app/tasks/celery_app.py`  
**Correction** :
```yaml
command: >
  celery -A app.tasks.celery_app:celery_app worker
  --loglevel=info
  --queues=default,reservations,invoicing,notifications
```

### 2. pyproject.toml - Dépendances manquantes pour CI/CD
**Fichier** : `pyproject.toml:18-23`  
**Erreur** : Le pipeline CI/CD référence des outils absents de pyproject.toml  
**Manque** :
- `black` (formatage - utilisé dans .github/workflows/ci.yml:37)
- `flake8` (linting - utilisé dans .github/workflows/ci.yml:40)
- `bandit` (sécurité - utilisé dans .github/workflows/ci.yml:62)
- `safety` (sécurité - utilisé dans .github/workflows/ci.yml:65)
- `httpx` (nécessaire pour TestClient FastAPI)
- `pytest-asyncio` (tests async)

**Correction** :
```toml
[tool.poetry.group.dev.dependencies]
pytest = "^8.3.0"
pytest-cov = "^6.0.0"
pytest-asyncio = "^0.24.0"
httpx = "^0.27.0"
black = "^24.10.0"
flake8 = "^7.1.0"
mypy = "^1.13.0"
bandit = "^1.7.10"
safety = "^3.2.0"
ruff = "^0.7.0"
```

### 3. Configuration - Secrets requis sans fallback
**Fichier** : `app/core/config.py:20,38`  
**Erreur** : `JWT_SECRET` et `CSRF_SECRET` marqués comme requis sans valeur par défaut  
**Impact** : Import échoue si .env absent ou incomplet  
**Correction** :
```python
# Option 1 : Valeur par défaut dev (seulement si DEBUG=True)
JWT_SECRET: str = "dev_jwt_secret_INSECURE_32chars_MIN"
CSRF_SECRET: str = "dev_csrf_secret_INSECURE_32chars_MIN"

# Option 2 : Validation conditionnelle
@field_validator('JWT_SECRET', 'CSRF_SECRET')
def validate_secrets(cls, v, values):
    if not values.get('DEBUG', False) and (not v or len(v) < 32):
        raise ValueError("SECRET doit faire au moins 32 caractères en production")
    return v
```

### 4. Frontend - Dockerfile manquant
**Fichier** : `docker-compose.yml:51`  
**Erreur** : Référence `build: ./frontend` mais aucun Dockerfile dans frontend/  
**Correction** : Créer `frontend/Dockerfile` :
```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE 80
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "80"]
```

### 5. .env - Redis URL incorrecte
**Fichier** : `.env:10` et `app/core/config.py:26`  
**Erreur** : Format Redis URL incohérent avec docker-compose.yml  
**docker-compose.yml** : `redis-server --requirepass ${REDIS_PASSWORD}`  
**.env** : `redis://:password@localhost:6380/0` (mot de passe hardcodé)  
**Correction** :
```env
REDIS_PASSWORD=mon_mot_de_passe_redis_securise
REDIS_URL=redis://:${REDIS_PASSWORD}@localhost:6380/0
```

### 6. Scripts - Dépendance nc non garantie
**Fichier** : `scripts/init_project.sh:32,37` et `scripts/run_tests.sh:15,19`  
**Erreur** : Utilise `nc` (netcat) sans vérifier qu'il est installé  
**Correction** : Ajouter vérification ou utiliser Python :
```bash
# Vérifier avec Python au lieu de nc
python3 -c "import socket; s=socket.socket(); s.connect(('localhost',5433)); s.close()" 2>/dev/null
```

### 7. Alembic - Import models manquant
**Fichier** : `alembic/env.py:9`  
**Erreur** : Importe `Base` mais aucun modèle métier → autogenerate ne détectera rien  
**Correction** : Quand modèles créés, ajouter :
```python
# Import ALL models here for autogenerate
from app.models.base import Base
from app.models.product import Product
from app.models.reservation import Reservation
# ... etc
```

---

## ⚠️ OUBLIS MINEURS

### 8. pytest.ini - Flag --cov-fail-under manquant
**Fichier** : `pytest.ini:6`  
**Suggestion** : Ajouter threshold coverage :
```ini
addopts = 
    --cov-fail-under=80
```

### 9. .gitignore - Fichiers Python temporaires
**Fichier** : `.gitignore`  
**Manque** : Patterns coverage, pytest cache  
**Ajout** :
```
htmlcov/
.coverage
.pytest_cache/
*.egg-info/
```

### 10. docker-compose.yml - Pas de health check pour Celery
**Fichier** : `docker-compose.yml:60`  
**Suggestion** : Ajouter health check :
```yaml
celery-worker:
  healthcheck:
    test: ["CMD-SHELL", "celery -A app.tasks.celery_app inspect ping"]
    interval: 30s
    timeout: 10s
    retries: 3
```

### 11. README.md - Commande Poetry manquante
**Suggestion** : Ajouter dans README :
```bash
# Générer poetry.lock
poetry lock --no-update
```

### 12. GitHub Actions - Cache Poetry incomplet
**Fichier** : `.github/workflows/ci.yml:31`  
**Suggestion** : Ajouter cache virtualenv :
```yaml
- name: Cache Poetry virtualenv
  uses: actions/cache@v4
  with:
    path: ~/.cache/pypoetry/virtualenvs
    key: poetry-${{ hashFiles('**/poetry.lock') }}
```

---

## 📊 Résumé

| Catégorie | Critique | Mineur | Total |
|-----------|----------|--------|-------|
| Configuration | 3 | 2 | 5 |
| Docker | 2 | 1 | 3 |
| Dépendances | 1 | 1 | 2 |
| Scripts | 1 | 0 | 1 |
| Alembic | 1 | 0 | 1 |

**TOTAL** : 🔴 7 erreurs critiques + ⚠️ 5 oublis mineurs = **12 corrections**

---

## ✅ Priorités de Correction

### P0 - Bloquer (avant premier lancement)
1. ✅ Corriger chemin Celery dans docker-compose.yml
2. ✅ Ajouter dépendances manquantes dans pyproject.toml
3. ✅ Créer frontend/Dockerfile ou retirer service frontend
4. ✅ Corriger Redis URL dans .env

### P1 - Important (avant tests CI/CD)
5. ✅ Gérer secrets requis dans config.py
6. ✅ Remplacer `nc` dans scripts

### P2 - Nice to have (amélioration qualité)
7. ⚠️ Ajouter --cov-fail-under dans pytest.ini
8. ⚠️ Compléter .gitignore
9. ⚠️ Health check Celery
10. ⚠️ Cache Poetry dans CI/CD

---

## 🛠️ Script de Correction Automatique

Voir `scripts/fix_all_errors.sh` (à créer)

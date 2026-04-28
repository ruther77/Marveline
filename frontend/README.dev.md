# Frontend Development Setup

Ce document explique comment développer le frontend avec **hot reload** (rechargement automatique sans rebuild Docker).

## Mode Production vs Mode Dev

### Mode Production (build statique)
```bash
# Build statique servi par nginx
docker compose up -d frontend

# Après chaque modification de code:
docker compose build frontend && docker compose up -d frontend
```

**Inconvénient** : Rebuild complet (~30s) à chaque modification.

### Mode Dev (hot reload) ✅ RECOMMANDÉ
```bash
# Dev server Vite avec hot reload
./scripts/dev-frontend.sh

# OU manuellement:
docker compose -f docker-compose.yml -f docker-compose.dev.yml up frontend
```

**Avantages** :
- ✅ Hot reload automatique (<1s)
- ✅ Pas de rebuild Docker
- ✅ Modifications de code instantanément visibles
- ✅ Source maps pour debugging
- ✅ Messages d'erreur détaillés

## Ports

- **Mode production** : `http://localhost:3002` (nginx port 80 mappé à 3002)
- **Mode dev** : `http://localhost:3002` (Vite port 5173 mappé à 3002)

Les deux modes utilisent le même port externe pour cohérence.

## Configuration

### docker-compose.dev.yml
Override le service `frontend` pour :
- Monter le code source en volume (`./frontend:/app`)
- Utiliser `Dockerfile.dev` au lieu de `Dockerfile`
- Lancer `npm run dev` au lieu de nginx
- Exposer port Vite 5173

### Dockerfile.dev
- Base image : `node:20-alpine`
- Installe dependencies avec `npm ci`
- N'utilise PAS `COPY . .` (code monté via volume)
- Lance Vite dev server avec `--host 0.0.0.0`

### vite.config.ts
- `host: '0.0.0.0'` : Écoute sur toutes interfaces (requis Docker)
- `port: 5173` : Port standard Vite
- `strictPort: true` : Fail si port occupé
- `proxy: /api` : Proxie vers conteneur `api` (ou `localhost:8001` en local)

## Workflow Développement

### Démarrage
```bash
# 1. Démarrer backend et services (DB, Redis)
docker compose up -d db redis api

# 2. Démarrer frontend en mode dev
./scripts/dev-frontend.sh
```

### Modification de code
1. Éditer fichiers dans `frontend/src/`
2. Vite détecte les changements automatiquement
3. Browser rafraîchit la page (<1s)
4. Pas de rebuild Docker ✅

### Debugging
- Console navigateur : messages d'erreur détaillés
- Logs Vite : `docker compose logs -f frontend`
- Network tab : inspecter requêtes API

### Revenir au mode production
```bash
# Arrêter frontend dev
Ctrl+C (dans terminal du script)

# Redémarrer frontend prod
docker compose up -d frontend
```

## Tests E2E

Les tests Playwright utilisent `http://localhost:3002` qui fonctionne avec **les deux modes**.

### Avec mode production (build statique)
```bash
# Frontend prod en cours sur :3002
npx playwright test
```

**Problème** : Tests utilisent old code si pas rebuild.

### Avec mode dev (hot reload) ✅ RECOMMANDÉ
```bash
# Frontend dev en cours sur :3002
npx playwright test
```

**Avantage** : Tests utilisent toujours le code le plus récent.

## Troubleshooting

### Port 5173 déjà utilisé
```bash
# Trouver processus sur port 5173
lsof -i :5173
kill -9 <PID>
```

### Hot reload ne fonctionne pas
```bash
# Vérifier que le volume est monté
docker compose -f docker-compose.yml -f docker-compose.dev.yml ps

# Vérifier logs Vite
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs frontend
```

### Modifications non visibles
1. Hard refresh navigateur : `Ctrl+Shift+R`
2. Vider cache : DevTools → Network → Disable cache
3. Redémarrer container dev :
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.dev.yml restart frontend
   ```

## Performance

### Mode Dev
- **Premier démarrage** : ~20s (install deps)
- **Rebuild après modif** : <1s (hot reload)
- **Taille image** : ~500MB (node_modules)

### Mode Production
- **Build** : ~30s (tsc + vite build)
- **Image** : ~50MB (nginx + dist static)
- **Runtime** : nginx (très rapide)

## Recommandations

### Développement quotidien
- ✅ Utiliser **mode dev** pour itérations rapides
- ✅ Laisser terminal ouvert pour voir logs Vite
- ✅ Tests E2E avec frontend dev pour code frais

### Tests CI/CD
- ✅ Utiliser **mode production** pour tests finaux
- ✅ Simuler environnement de production
- ✅ Vérifier bundle size et optimisations

### Avant commit
- ✅ Tester avec mode production (au moins une fois)
- ✅ Vérifier que build passe sans erreurs
- ✅ Lancer tests E2E en mode production

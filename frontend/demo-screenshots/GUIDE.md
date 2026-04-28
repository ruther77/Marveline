# Guide — Maquette Facebook Marveline

## Exécuter les captures

```bash
# 1. Seed les données démo
docker compose exec -T api python scripts/demo/seed_marveline_demo.py

# 2. S'assurer que le frontend tourne
cd frontend && pnpm dev  # port 3002

# 3. Lancer les captures (headless = rapide)
npx playwright test --config=playwright.screenshots.config.ts

# Ou en mode visible pour vérifier :
npx playwright test --config=playwright.screenshots.config.ts --headed
```

## Fichiers produits (~25 screenshots)

Les PNG sont dans `frontend/demo-screenshots/` :

| # | Fichier | Écran | Message clé |
|---|---------|-------|-------------|
| 01 | `login_vide` | Connexion | Interface sécurisée |
| 02 | `login_rempli` | Connexion remplie | Accès rapide |
| 03 | `dashboard_top` | Tableau de bord | KPIs en temps réel |
| 04 | `dashboard_scroll` | Dashboard scroll | Activité récente |
| 05 | `planning_calendrier` | Calendrier | Vision globale des réservations |
| 06 | `planning_semaine` | Vue semaine | Livraisons et retours |
| 07 | `planning_aujourdhui` | Aujourd'hui | Actions du jour |
| 08 | `reservations_liste` | Liste réservations | Filtres par statut |
| 09 | `reservation_detail_hero` | Détail (en-tête) | Statut + progression |
| 10 | `reservation_detail_infos` | Détail (infos) | Client, événement, dates |
| 11 | `reservation_detail_produits` | Détail (produits) | Lignes et montants |
| 12 | `reservation_creation` | Nouvelle réservation | Formulaire rapide |
| 13 | `catalogue_produits` | Catalogue | Articles en location |
| 14 | `produit_detail` | Fiche produit | Stock et disponibilité |
| 15 | `stock_items` | Stock unitaire | Badges statut colorés |
| 16 | `stock_overview` | Stock overview | Alertes et mouvements |
| 17 | `clients_liste` | Clients | Répertoire complet |
| 18 | `client_detail` | Fiche client | Historique et stats |
| 19 | `factures_liste` | Factures | Suivi paiements |
| 20 | `facture_detail` | Détail facture | Lignes et progression |
| 21 | `facture_detail_paiements` | Paiements facture | Historique et dommages |
| 22 | `devis_liste` | Devis | Propositions commerciales |
| 23 | `operations_dashboard` | Opérations | Départs et retours |
| 24 | `operations_depart` | Départ | Checklist livraison |
| 25 | `operations_retour` | Retour | Contrôle dommages |
| 26 | `operations_scan` | Scanner | QR code / code-barres |
| 27 | `recherche_globale` | Recherche | Trouver en un instant |
| 28 | `menu_plus` | Menu complet | Toutes les fonctionnalités |
| 29 | `notifications` | Notifications | Alertes temps réel |

## Assembler la maquette

### Option carrousel Facebook (recommandé)
Sélectionner 8-10 screenshots les plus impactants :
1. `dashboard_top` — accroche visuelle (KPIs)
2. `reservations_liste` — gestion centralisée
3. `reservation_detail_hero` — suivi par étape
4. `catalogue_produits` — inventaire complet
5. `stock_items` — suivi unitaire
6. `planning_calendrier` — vision calendrier
7. `factures_liste` — facturation intégrée
8. `operations_dashboard` — terrain simplifié
9. `clients_liste` — base clients
10. `operations_scan` — scanner mobile

### Option story/reel
Utiliser les screenshots dans l'ordre 01→29 pour un défilement rapide (2-3 sec/image).

### Dimensions
- Screenshots natifs : 1179×2556 px (iPhone 14 Pro @3x)
- Facebook carrousel : redimensionner à 1080×1080 (carré) ou 1080×1350 (portrait)
- Facebook couverture : 1200×630

## Post Facebook suggéré

Voir le fichier `POST_FACEBOOK.md` dans ce dossier.

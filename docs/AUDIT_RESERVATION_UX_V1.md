# Audit UX Réservations — Frontend :3000 vs LAYER.html

**Date** : 2026-03-18
**Scope** : Module réservations complet (14 réservations en base, 6 statuts actifs)

---

## I. État réel de la base de données

| Statut | Count | Réservations |
|--------|-------|-------------|
| draft | 7 | RES-0003, 0004, 0007, 0008, 0009, 0014, + |
| confirmed | 1 | RES-0002 |
| pre_check | 2 | RES-0011, 0012 |
| delivered | 1 | RES-0006 (return_date 2026-03-06 = **12 jours de retard**) |
| returned | 1 | RES-0010 |
| completed | 2 | RES-0005, 0013 |
| confirmed_risk | 0 | — |
| extended | 0 | — |
| returned_dispute | 0 | — |
| cancelled | 0 | — |

---

## II. Cartographie de chaque écran frontend — état réel

### A. LISTE `/reservations` (EventsPage)

**Ce qui marche :**
- Liste paginée avec 14 réservations
- Filtres par statut (chips scrollables)
- KPI cards : 4 compteurs (Livrées, Confirmées, Retournées, Annulées)
- Menu contextuel par rangée (voir/modifier/confirmer/annuler)
- Navigation vers détail au clic
- Skeleton loader

**Ce qui manque vs LAYER :**
- Pas de barre de recherche intégrée (client, ref, facture, article)
- Pas de FAB (+) flottant pour créer rapidement
- KPI cards statiques — LAYER a des KPI colorés par sémantique (vert=OK, rouge=retard)
- Pas de badge retard/urgence sur les lignes
- Pas de swipe actions mobile (LAYER a swipe-to-delete)
- Pas de compteur "En retard" visible (RES-0006 a 12j de retard, invisible dans la liste)
- Chips statut : rose uniforme — LAYER colore par statut
- Pas de tri par date/montant/client

**Problèmes détectés :**
- Le filtre `status_filter` dans l'URL n'est pas toujours synchronisé avec les chips
- Menu contextuel "Annuler" visible sur des statuts où l'annulation est impossible (delivered)

---

### B. CRÉATION `/reservations/new` (ReservationCreatePage)

**Ce qui marche :**
- Sélection client (ComboboxAsync avec recherche)
- 3 dates (événement, livraison, retour) avec calcul durée auto
- Type d'événement (select : mariage/anniversaire/entreprise/autre)
- Nom événement, invités, lieu, notes
- Catalogue picker modal (produits + catégories + stock dispo)
- Ajout produit avec quantité modifiable
- Calcul total estimé en temps réel
- Récapitulatif (lignes, durée, total)
- Soumission → création 201 + redirect vers liste

**Ce qui manque vs LAYER :**
- Pas de wizard steps (LAYER a une barre de progression : Client → Dates → Produits → Récap)
- Pas de validation inline des dates (livraison < retour non vérifié côté client)
- Pas de warning stock faible lors de la sélection produit
- Pas de sauvegarde brouillon automatique (perdu si refresh)
- Pas de pré-sélection depuis un devis existant
- Pas de variantes visibles dans le picker (dropdown séparé)

**Problèmes détectés :**
- Le formulaire ne valide pas que delivery_date ≤ event_date côté client
- Pas de confirmation avant soumission (submit direct)

---

### C. DÉTAIL `/reservations/$id` (EventDetailPage)

**Ce qui marche :**
- Header avec ref, statut badge, bouton action principal
- Timeline 5 étapes (Créée → Départ → Événement → Retour → Clôture)
- 6-8 hub cards cliquables (Lignes, Pre-check, Caution, Factures, Mouvements, Risques, Extension, Historique)
- Notes éditables inline
- 8 modales fonctionnelles
- Menu contextuel (confirmer, annuler, archiver, supprimer, close-dispute)

**Ce qui manque vs LAYER :**
- **Pas de Hero Card coloré par statut** — c'est LE changement le plus visible
  - LAYER : fond coloré (muted=brouillon, yellow=attente caution, green=prêt, blue=en cours, orange=retourné, purple=terminé, red=risque)
  - Actuel : fond blanc uniforme, petit badge
- **Pas de barre de progression paiement** (payé vs reste)
- **Pas de Focus Strip** (KPI horizontaux : date, stock, caution, acompte)
- **Pas de message guide** contextuel ("Le départ doit rester bloqué tant que caution non validée")
- **Actions pas contextuelles par état** — le bouton principal est le même look pour tous les statuts
- **Pas de quick links** en bas (devis, paiement, pré-check, édition)
- **Pas d'info grid 2×2** (date sorti, retour prévu, caution, solde restant)
- **Pas d'alert box** contextuelle (info/warn/ok) selon l'état

**Problèmes détectés :**
- La timeline est horizontale minimaliste (5 dots) — LAYER a une timeline verticale avec actions inline
- Les hub cards sont toutes grises — pas de coloration par état (pre-check rouge si incomplet, caution jaune si en attente)
- Le bouton "Procéder au départ" est affiché même si caution non payée (le blocage se fait côté opérations)
- Pas de vue "Brouillon incomplet" (checklist des champs manquants)

---

### D. ÉDITION `/reservations/$id/edit` (ReservationEditPage)

**Ce qui marche :**
- 6 champs éditables (dates, lieu, type, nom, invités, deposit_paid)
- Read-only si statut ≠ draft
- Sauvegarde via PATCH

**Ce qui manque :**
- Pas d'édition des lignes (renvoi vers `/lines`)
- Pas de validation dates côté client
- Navigation de retour pointe vers `/phases` (route alias) au lieu de `/reservations/$id`

---

### E. LIGNES `/reservations/$id/lines` (ReservationLinesPage)

**Ce qui marche :**
- Liste produits existants
- Recherche dans le catalogue
- Ajout produit avec variant
- Suppression ligne (draft only)

**Ce qui manque :**
- Pas de modification de quantité inline (doit supprimer + ré-ajouter)
- Pas de swipe-to-delete (LAYER)
- Pas d'affichage prix/sous-total par ligne
- Read-only badge pas visible si statut ≠ draft

---

### F. SIGNATURE `/reservations/$id/signature` (SignaturePage)

**Ce qui marche :**
- Canvas de dessin tactile
- Effacer + Valider
- Upload POST vers backend

**Ce qui manque :**
- Pas de preview après validation
- Pas d'intégration dans le flow départ (page isolée)
- Canvas taille fixe (pas responsive)

---

### G. OPÉRATIONS DASHBOARD `/operations` (OperationsDashboardPage)

**Ce qui marche :**
- 3 sections : Départs à préparer, Retours attendus, En retard
- Navigation vers scan QR
- Cards par réservation

**Problèmes détectés :**
- Bug P1 sur `/operations/summary` (Reservation.is_active) — **semble résolu** après rebuild mais à confirmer
- Pas de compteur urgent visible
- Les cards ne montrent pas le nombre de jours de retard

---

### H. DÉPART `/operations/departure/$id` (DepartureInventoryPage)

**Ce qui marche :**
- Grille items avec quantité chargée et état
- Scanner QR par item
- Zone signature
- Bouton "Valider le départ" / "Bloquer"
- Lien vers vérification article par article

**Ce qui manque vs LAYER :**
- **Pas de wizard steps** (LAYER a : Inventaire → Vérification → Signature → Validation)
- Pas de split entre "Article par article" et "Contrôle légal" (LAYER les sépare)
- Pas de barre de progression (X/Y articles vérifiés)
- Pas de condition select visuel (LAYER a des boutons : Bon état / Rayé / Cassé / Perdu avec couleurs)
- L'alerte "Pré-vérifications incomplètes" bloque sans explication claire

**Problèmes détectés :**
- Pre-check article-par-article ne persiste pas (bug P2 identifié lors du monitoring)
- Le compteur reste "0/1 articles chargés" après vérification → state local perdu au retour
- Pas de photo dommage lors du départ
- Signature canvas mal capturée (points au lieu de tracé)

---

### I. ARTICLE CHECK `/operations/departure/$id/check` (ArticleCheckPage)

**Ce qui marche :**
- Navigation article par article (prev/next)
- Quantité avec +/-
- État physique (bon/rayé/cassé/perdu)
- Barre de progression
- Notes optionnelles

**Ce qui manque :**
- Pas de photo par article
- Pas de scanner QR dans cette vue
- État physique pas persisté correctement au retour vers DepartureInventoryPage

---

### J. DÉPART BLOQUÉ `/operations/departure/$id/blocked` (DepartureBlockedPage)

**Ce qui marche :**
- Affiche la raison du blocage (caution, pré-check)
- Hero rouge "Départ refusé"

**Problèmes :**
- Page cul-de-sac : seul lien = retour vers `/reservations/$id`
- Pas de bouton "Encaisser caution" ou "Compléter pré-check" directement
- L'utilisateur doit comprendre seul comment débloquer

---

### K. RETOUR `/operations/return/$id` (ReturnInventoryPage)

**Ce qui marche :**
- Grille items avec quantité retournée et condition (5 états)
- Déclaration dommages via modal
- Signature
- Soumission retour

**Ce qui manque vs LAYER :**
- Pas de **résultat contrôle par article** (LAYER affiche ✅ OK vert / ❌ Dommage rouge par article)
- Pas de **calcul retenue caution** en temps réel
- Pas de **compteur caution à restituer vs retenue**
- Pas de confirmation avant soumission si dommages
- Pas de lien vers inventaire retour détaillé

---

### L. DOMMAGES `/operations/return/$id/damage` (DamageDeclareFullPage)

**Statut :** Page existe dans les routes mais contenu non vérifié en profondeur. Probablement fonctionnelle mais peu testée.

---

## III. Écrans LAYER.html qui n'existent PAS dans le frontend

| Écran LAYER | ID | Existe frontend ? | Notes |
|-------------|----|--------------------|-------|
| Brouillon incomplet | `s-resa-brouillon-incomplet` | **NON** | Checklist des champs manquants (date retour, acompte, mode retrait) |
| Confirmée risque | `s-resa-confirmee-risque` | **NON** | Alertes caution+acompte en retard, relances, countdown |
| Prête départ | `s-resa-confirmee-prete` | **NON** | Résumé pré-check validé (stock OK, caution OK, docs signés) |
| Pré-check légal | `s-resa-precheck-legal` | **NON** | Documents contractuels, CGV, identité, garanties |
| En cours prolongée | `s-resa-en-cours-prolongee` | **NON** | Détail prolongation avec countdown retour |
| Retournée litige | `s-resa-retournee-litige` | **PARTIEL** | Existe en modal, pas en page dédiée |
| Terminée archive | `s-resa-terminee-archive` | **NON** | Vue lecture seule avec historique complet |
| Départ bloqué (détaillé) | `s-depart-bloque` | **PARTIEL** | Existe mais cul-de-sac sans actions |
| Retour inventaire | `s-retour-inventaire` | **OUI** | Existe dans /operations/return/$id |

---

## IV. Composants LAYER.html absents du frontend

| Composant | Usage LAYER | Priorité |
|-----------|------------|----------|
| `detail-hero` coloré par statut | Fond gradient + ref + client + montant + barre progression | **P0** |
| `focus-strip` (KPI pills) | Date/Stock/Caution/Acompte en scroll horizontal | **P0** |
| `section-note` (message guide) | Texte contextuel sous la strip | **P0** |
| `caution-box` (jaune/vert) | Encart caution dédié avec bouton action | **P1** |
| `state-flow` (timeline verticale) | Timeline avec dots done/curr/next + actions inline | **P1** |
| `alert-box` (info/warn/ok) | Bannière contextuelle par état | **P1** |
| `info-grid` (2×2) | Grille 4 KPI (sorti le, retour prévu, caution, solde) | **P1** |
| `countdown-chip` | Timer deadline (J/H/M avant retour) | **P2** |
| `swipe-wrap` (swipe-to-delete) | Geste natif mobile sur produits | **P2** |
| `quick-links` | Liens rapides bas de page (devis, paiement, pré-check) | **P2** |
| `wizard-steps` | Barre progression multi-étapes | **P2** |
| `split-btn` (action + dropdown) | Bouton principal + chevron dropdown | **P3** |
| `photo-grid` | Galerie photos dommages | **P3** |
| `sig-canvas-wrap` (amélioré) | Signature avec placeholder + border animée | **P3** |

---

## V. Bugs et culs-de-sac identifiés

| # | Sévérité | Description | Fichier |
|---|----------|-------------|---------|
| 1 | **P1** | `operations/summary` → 500 (Reservation.is_active inexistant) | `operations.py:209` |
| 2 | **P1** | Pre-check article-par-article ne persiste pas (0/1 après vérif) | ArticleCheckPage + DepartureInventoryPage |
| 3 | **P1** | RES-0002 (confirmed) a 0 pre-check items — auto-génération cassée ? | ReservationService.confirm |
| 4 | **P2** | DepartureBlockedPage = cul-de-sac (pas d'action pour débloquer) | DepartureBlockedPage.tsx |
| 5 | **P2** | Bouton "Procéder au départ" visible même si caution non payée | EventDetailPage.tsx |
| 6 | **P2** | ReservationEditPage back link → `/phases` au lieu de `/$id` | ReservationEditPage.tsx |
| 7 | **P2** | Lignes : pas de modification qty inline (suppr + ré-add) | ReservationLinesPage.tsx |
| 8 | **P2** | RES-0006 en retard 12 jours — aucune alerte visible dans la liste | EventsPage.tsx |
| 9 | **P3** | Menu annuler visible sur statuts post-départ (impossible) | EventsPage.tsx menu |
| 10 | **P3** | Signature canvas taille fixe (pas responsive) | SignaturePage.tsx |
| 11 | **P3** | Pas de confirmation avant submit retour avec dommages | ReturnInventoryPage.tsx |

---

## VI. Résumé : ce qui fonctionne bien

1. **Machine à états backend** : complète, toutes les transitions marchent (testé via API)
2. **API frontend** : 38 endpoints, tous alignés avec le backend, aucun mismatch
3. **React Query** : 30 hooks avec invalidation cache correcte
4. **Création réservation** : flow complet fonctionnel (client → dates → produits → submit)
5. **Cycle complet** : Brouillon → Pre-check → Delivered → Returned → Completed (testé E2E)
6. **Modales** : 8 modales fonctionnelles sur la page détail
7. **Types TypeScript** : exhaustifs, alignés avec les schémas Pydantic
8. **Sécurité** : CSRF, auth, RBAC, multi-tenant — tout en place

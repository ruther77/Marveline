# Inventaire UX Réservations — État des lieux complet

**Date** : 2026-03-18
**Objectif** : Décortiquer tout ce qu'on a, tout ce qu'il manque, tout ce qui est cassé ou en cul-de-sac — avant de décider quoi refaire.

---

## Chiffres clés

| | LAYER.html | Frontend :3000 |
|---|---|---|
| **Écrans total** | 132 | 128 routes |
| **Écrans réservation** | 18 | 7 routes + 1 modal riche |
| **Écrans événements** | 9 | 3 routes |
| **Écrans opérations terrain** | 8 | 8 routes |
| **Écrans planning** | 5 | 9 routes |

---

## I. RÉSERVATIONS — Mapping écran par écran

### Ce qu'on a (frontend :3000)

| Route | Composant | Rôle | Qualité |
|-------|-----------|------|---------|
| `/reservations` | EventsPage | Liste + filtres + KPI + menu contextuel | **Correct** — manque recherche, badge retard, FAB |
| `/reservations/new` | ReservationCreatePage | Création avec catalogue picker | **Correct** — manque wizard steps, validation dates client |
| `/reservations/$id` | EventDetailPage | Hub cards + 8 modales | **Faible** — hub cards plates, pas de hero coloré, pas de focus pills |
| `/reservations/$id/edit` | ReservationEditPage | Édition dates/événement | **Correct** — back link cassé (→ /phases) |
| `/reservations/$id/lines` | ReservationLinesPage | Gestion lignes produits | **Faible** — pas de modif qty, pas de swipe |
| `/reservations/$id/phases` | EventDetailPage (alias) | Même page que /$id | **Doublon inutile** |
| `/reservations/$id/signature` | SignaturePage | Canvas signature | **Basique** — isolé du flow, taille fixe |

**+ 1 composant riche non-route :**

| Composant | Utilisé dans | Rôle | Qualité |
|-----------|-------------|------|---------|
| `ReservationDetailsModal` (685 lignes) | AgendaPage (calendrier) | Détail complet : hero coloré, focus pills, timeline, actions CTA, deposits, precheck, risks, factures, audit | **Le plus avancé** — mais c'est un modal, pas une page, et il est lourd/monolithique |

### Ce que LAYER.html a et qu'on n'a PAS (ou différemment)

| Écran LAYER | ID | Existe :3000 ? | Écart |
|-------------|-----|----------------|-------|
| Création résa | `s-resa-create` | `/reservations/new` ✅ | LAYER a wizard steps |
| Création lignes | `s-resa-nouvelle-lignes` | Intégré dans `/new` | LAYER sépare en 2 pages |
| Brouillon | `s-resa-brouillon` | `/reservations/$id` ⚠️ | LAYER : hero muted + swipe produits + actions (modifier/confirmer/supprimer) + quick links (devis, manquants) |
| Brouillon incomplet | `s-resa-brouillon-incomplet` | **NON** ❌ | Checklist bloquants (date retour, acompte, mode retrait) — aide à compléter avant confirmation |
| Confirmée sans caution | `s-resa-confirmee-sans-caution` | `/reservations/$id` ⚠️ | LAYER : hero yellow + barre paiement + pills (caution en attente, acompte 0/66€) + actions (encaisser, relancer, risque) |
| Confirmée avec caution | `s-resa-confirmee-avec-caution` | `/reservations/$id` ⚠️ | LAYER : hero green + barre paiement 40% + actions (lancer départ, pré-check, pré-check légal, suivi paiement, devis) |
| Confirmée risque | `s-resa-confirmee-risque` | **NON** ❌ | Hero rouge + alertes (caution+acompte en retard, relances envoyées) + actions (encaisser, relancer, annuler) |
| Prête départ | `s-resa-confirmee-prete` | **NON** ❌ | Résumé pré-check validé (stock ✓, caution ✓, docs ✓) + bouton "Démarrer la sortie" |
| Pré-check légal | `s-resa-precheck-legal` | **NON** ❌ | Documents contractuels (CGV, bon résa, engagement caution, clause casse) + identité (CNI, adresse, contact J) |
| En cours (delivered) | `s-resa-en-cours` | `/reservations/$id` ⚠️ | LAYER : hero blue + alert info "matériel sorti" + info-grid (sorti le, retour prévu, caution, solde) + produits "En loc." + actions (frais supp, retour, prolonger, paiement) |
| En cours prolongée | `s-resa-en-cours-prolongee` | **NON** ❌ | Détail prolongation avec new return_date + frais supp + historique prolongations |
| Retournée (contrôle) | `s-resa-retournee` | `/reservations/$id` ⚠️ | LAYER : hero orange + alert warn (2 verres manquants) + résultat contrôle par article (✅OK / ❌Dommage) + retenue vs restitution caution + actions (dommage, clôturer, inventaire détaillé, litige) |
| Retournée litige | `s-resa-retournee-litige` | **NON** ❌ | Détail dommages déclarés + photos + facture dommages + actions (régler litige, ajouter dommage) |
| Terminée | `s-resa-terminee` | `/reservations/$id` ⚠️ | LAYER : hero purple + alert ok "clôturée, caution restituée" + info-grid (total encaissé, caution, dommages, facture) + actions (facture, PDF) |
| Terminée archive | `s-resa-terminee-archive` | **NON** ❌ | Vue lecture seule réduite avec résumé compact |
| Annulée | `s-resa-annulee` | **NON** ❌ | Hero muted + raison annulation + actions (archives) |
| Détail générique | `s-resa-detail` | `/reservations/$id` ✅ | LAYER a aussi un écran détail générique (doublon ?) |
| Nouvelle + lignes | `s-resa-nouvelle` + `s-resa-nouvelle-lignes` | `/reservations/new` ✅ | LAYER sépare en 2 étapes distinctes |

### Résumé écarts réservations

| | LAYER | :3000 |
|---|---|---|
| Pages dédiées par état | **13** (brouillon, brouillon-incomplet, confirmée×3, risque, prête, légal, en-cours, prolongée, retournée, litige, terminée, archive, annulée) | **1** (EventDetailPage gère tous les états dans la même page) |
| Composant riche par état | Chaque état a son hero, ses pills, ses actions, son message guide | Un seul hub cards identique pour tous les états |
| Le modal du calendrier | — | A le hero coloré + pills + actions mais **n'est pas utilisé comme page** |

---

## II. ÉVÉNEMENTS — Mapping

### Ce qu'on a (frontend :3000)

| Route | Rôle | Qualité |
|-------|------|---------|
| `/evenements/` | Liste événements | **Correct** |
| `/evenements/$id` | Détail événement | **Correct** |
| `/evenements/$id/incidents` | Incidents liés | **Basique** |

### Ce que LAYER a

| Écran LAYER | Existe :3000 ? |
|-------------|----------------|
| `s-event-prevu` | `/evenements/$id` ⚠️ (pas de vue "prévu" dédiée) |
| `s-event-en-cours` | **NON** ❌ |
| `s-event-retourne` | **NON** ❌ |
| `s-event-termine` | **NON** ❌ |
| `s-event-prevu-risque` | **NON** ❌ |
| `s-event-en-cours-incident` | `/evenements/$id/incidents` ⚠️ |
| `s-event-action-plan` | **NON** ❌ (plan d'action incident) |
| `s-event-retourne-casse` | **NON** ❌ |
| `s-event-annule` | **NON** ❌ |

---

## III. OPÉRATIONS TERRAIN — Mapping

### Ce qu'on a (frontend :3000)

| Route | Rôle | Qualité |
|-------|------|---------|
| `/operations/` | Dashboard (départs, retours, retards) | **Correct** — bug P1 summary (is_active) |
| `/operations/scan` | Scanner QR | **Correct** |
| `/operations/departure/` | Liste départs | **Basique** |
| `/operations/departure/$id` | Inventaire départ | **Correct** — pre-check ne persiste pas |
| `/operations/departure/$id/check` | Article par article | **Correct** — pas de photo |
| `/operations/departure/$id/blocked` | Départ bloqué | **Cul-de-sac** — pas d'action pour débloquer |
| `/operations/return/` | Liste retours | **Basique** |
| `/operations/return/$id` | Inventaire retour | **Correct** — pas de résultat contrôle par article |
| `/operations/return/$id/damage` | Déclaration dommages | **Existe** — peu testé |

### Ce que LAYER a

| Écran LAYER | Existe :3000 ? | Écart |
|-------------|----------------|-------|
| `s-depart-from-resa` | `/operations/departure/$id` ✅ | |
| `s-depart-bloque` | `/operations/departure/$id/blocked` ⚠️ | LAYER : raisons détaillées + CTA pour résoudre |
| `s-depart-inventaire` | `/operations/departure/$id` ✅ | |
| `s-retour-inventaire` | `/operations/return/$id` ✅ | |
| `s-dommage-declare` | `/operations/return/$id/damage` ✅ | LAYER : plus détaillé (photo grid, rating, catégorie) |
| `s-check-article` | `/operations/departure/$id/check` ✅ | |
| `s-scan-qr` | `/operations/scan` ✅ | |
| `s-signature-contrat` | `/reservations/$id/signature` ✅ | LAYER : intégré dans le flow départ, pas page isolée |

---

## IV. PAGES LAYER QUI N'EXISTENT PAS DU TOUT DANS :3000

| Écran LAYER | Domaine | Importance |
|-------------|---------|-----------|
| `s-caution-suivi` | Finance | Page dédiée suivi caution (encaissement, restitution, retenue) |
| `s-paiement-nouveau` | Finance | Formulaire enregistrement paiement |
| `s-casse-declaration` | Stock | Déclaration casse hors réservation |
| `s-inventaire-physique` | Stock | Inventaire physique (comptage terrain) |
| `s-maintenance-produit` | Catalogue | Planification maintenance produit |
| `s-relances-planifiees` | Clients | Planning des relances auto |
| `s-rapport-mensuel` | Finance | Rapport mensuel détaillé |
| `s-tarification` | Finance | Règles de tarification |
| `s-planning-ressources` | Planning | Affectation ressources/équipes |
| `s-planning-affectation` | Planning | Affectation par événement |
| `s-ligne-edit` | Réservation | Édition inline d'une ligne de réservation |

---

## V. PROBLÈMES STRUCTURELS IDENTIFIÉS

### A. Le "mono-page" de détail réservation

**Problème central** : `/reservations/$id` (EventDetailPage) essaie de tout faire dans une seule page avec 8 modales. Résultat :
- Pas de contexte visuel par état (tout est gris/plat)
- L'utilisateur doit cliquer sur des cartes puis naviguer dans des modales
- Les actions sont cachées dans un menu dropdown
- Pas de message guide, pas de focus sur l'action suivante

**LAYER résout ça** avec 13 pages dédiées — chaque état a son hero, ses actions, son message. L'utilisateur sait immédiatement où il en est et quoi faire.

### B. Le modal riche du calendrier orphelin

`ReservationDetailsModal` (685 lignes) est le composant le plus complet :
- Hero coloré par statut ✅
- Focus pills contextuels ✅
- Alertes par état ✅
- Timeline terrain ✅
- Actions CTA par statut ✅
- Sections deposits/precheck/risks ✅
- Factures avec barre paiement ✅
- Audit historique ✅

Mais il est :
- Seulement accessible via le calendrier (`/planning/calendar`)
- Un modal (pas une page) → pas d'URL, pas de bookmark, pas de partage
- Monolithique (685 lignes dans un seul composant)
- **Non utilisé par la page principale `/reservations/$id`**

### C. Doublons et alias inutiles

| Route | Problème |
|-------|---------|
| `/reservations/$id/phases` | Alias exact de `/$id` — aucune différence |
| `/reservations/$id` vs modal calendrier | Deux implémentations du même écran, incompatibles |
| `EventsPage` vs `s-reservations` vs `s-reservations-list` | LAYER a aussi des doublons (2 listes) |

### D. Culs-de-sac et navigations cassées

| Page | Problème |
|------|---------|
| `/operations/departure/$id/blocked` | Lecture seule, aucun bouton pour résoudre (encaisser caution, compléter pre-check) |
| `/reservations/$id/edit` | Back link → `/phases` au lieu de `/$id` |
| `/reservations/$id/lines` | Back link → `/reservations` (liste) au lieu de `/$id` (détail) |
| `/reservations/$id/signature` | Page isolée, non intégrée au flow départ |
| Pre-check article-par-article | L'état ne persiste pas au retour vers DepartureInventoryPage |

### E. Données incohérentes en base

| Donnée | Problème |
|--------|---------|
| RES-0002 (confirmed) | 0 pre-check items — l'auto-génération à la confirmation ne fonctionne pas ? |
| RES-0006 (delivered) | return_date 2026-03-06 = **12 jours de retard** — aucune alerte nulle part |
| RES-0014 (completed) | deposit_paid = False mais status = completed — incohérence métier |

---

## VI. CE QUI FONCTIONNE BIEN

| Domaine | Détail |
|---------|--------|
| **Machine à états backend** | 10 statuts, toutes transitions testées via API, CSRF, multi-tenant |
| **API frontend** | 38 endpoints, tous alignés avec le backend, 0 mismatch |
| **React Query** | 30 hooks, invalidation cache correcte, optimistic updates |
| **Création réservation** | Flow complet : client → dates → produits → submit |
| **Cycle complet API** | Brouillon → Pre-check → Delivered → Returned → Completed (testé E2E) |
| **Calendrier agenda** | 3 vues (mois/semaine/jour), événements par type, modal riche |
| **Operations terrain** | Départ, retour, scan QR, article check — fonctionnels |
| **Sécurité** | CSRF, refresh token, guards, HTTP-only cookies, RBAC |

---

## VII. QUESTIONS OUVERTES POUR DÉCISIONS

1. **Pages dédiées vs page unique** : Faut-il 13 pages comme LAYER, ou un compromis avec 5-6 pages clés + sections conditionnelles ?
2. **Le modal calendrier** : On le garde comme modal ? On le transforme en page ? On le démonte en composants réutilisables ?
3. **Le hub cards EventDetailPage** : On le supprime, on le garde comme vue résumé, ou on le remplace ?
4. **Événements vs Réservations** : LAYER a 9 écrans événements séparés. On unifie avec les réservations ou on garde deux domaines ?
5. **Le flow départ** : Signature intégrée au flow (LAYER) ou page séparée (actuel) ?
6. **Les sous-états** : Confirmée-sans-caution vs Confirmée-avec-caution sont deux écrans LAYER. Un seul avec condition dans :3000 ?

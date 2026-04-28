# Refonte UX Marveline — Document de conception V2

> Statut : EN DISCUSSION — Rien ne se code tant qu'on n'a pas validé ensemble chaque section.

---

## 1. Contexte et contraintes

### Utilisateurs
- **Propriétaire** : voit tout, fait tout (commercial + prépa + terrain + finance)
- **Équipiers** : opérations terrain (départ/retour) + réservations en lecture seule
- **Deux contextes d'usage** : desktop (bureau, gestion) ET mobile (terrain, opérations)

### Flux métier réel
```
Client appelle
  → Devis (TOUJOURS systématique)
    → Négociation / signature
      → Conversion en réservation
        → Confirmation + caution
          → Pre-check stock
            → DÉPART (scan article par article, signature)
              → Événement
                → RETOUR (scan article par article, constats dégâts, signature)
                  → Facturation (+ facture dégâts si besoin)
                    → Paiement / relance
                      → Clôture
```

### Principes de conception
- **1 entité = 1 page avec URL** (bookmarkable, partageable, retour navigateur)
- **Chaque élément cliquable mène à la bonne destination** (jamais vers une liste générale)
- **L'action suivante est toujours visible** (pas besoin de chercher quoi faire)
- **Mobile-first pour les opérations terrain** (scan, checklist, signature)
- **Desktop-first pour la gestion** (devis, facturation, pilotage)

---

## 2. Navigation principale

### Barre de navigation (5 onglets)

```
Dashboard | Planning | Réservations | Opérations | Plus
```

> Pas de changement de structure. La page "Commandes" (vue unifiée) est supprimée.

### Menu "Plus" (modules secondaires)

```
MODULES PRINCIPAUX
  Catalogue ........... Produits, bundles, catégories
  Clients ............. Base client, relances, analyse RFM
  Parc matériel ....... Stock, inventaire, mouvements
  Finances ............ Factures, paiements, avoirs, cautions

AUTRES MODULES
  Devis ............... Gestion des devis (accès direct)
  Tarification ........ Règles de prix et formules
  Fournisseurs ........ Commandes fournisseurs
```

---

## 3. Pages — Redesign page par page

### 3.1 DASHBOARD (`/dashboard`)

**Rôle** : En 10 secondes, savoir ce qui se passe et agir.

```
┌─────────────────────────────────────────────────────────┐
│  Bonjour, [Prénom]                    [date du jour]    │
│                                                         │
│  ┌─ ALERTES (bandeau rouge si retard/urgence) ────────┐ │
│  │ ⚠ Retour en retard — RES-2026-0010 Combo SARL     │ │
│  │   → clic = /reservations/$id (PAS la liste)        │ │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
│  ┌─ AUJOURD'HUI ─────────────────────────────────────┐ │
│  │                                                     │ │
│  │  DÉPARTS (2)                 RETOURS (1)           │ │
│  │  ┌──────────────────┐       ┌──────────────────┐   │ │
│  │  │ RES-2026-0011    │       │ RES-2026-0008    │   │ │
│  │  │ Test Audit       │       │ Alice Test       │   │ │
│  │  │ 2 articles  9:00 │       │ 5 articles 14:00 │   │ │
│  │  │ → clic = fiche   │       │ → clic = fiche   │   │ │
│  │  └──────────────────┘       └──────────────────┘   │ │
│  │                                                     │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                         │
│  ┌─ RACCOURCIS ───────────────────────────────────────┐ │
│  │  [+ Devis]   [Planning]   [Scanner QR]            │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                         │
│  ┌─ KPIS ─────────────────────────────────────────────┐ │
│  │  Résa actives: 5 | En retard: 142€ | Stock bas: 22 │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                         │
│  ┌─ ACTIVITÉ RÉCENTE ────────────────────────────────┐ │
│  │  • Facture payée INV-2026-0004  → clic = facture  │ │
│  │  • Retour RES-2026-0010        → clic = fiche résa│ │
│  │  • Stock faible — Housse       → clic = fiche prod│ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Changements vs actuel :**
- [ ] Alertes : lien vers `/reservations/$id` au lieu de `/reservations`
- [ ] Aujourd'hui : séparer départs et retours en 2 colonnes cliquables
- [ ] Chaque item d'activité : lien vers l'entité concernée (pas la liste)
- [ ] Raccourci "+ Devis" au lieu de "+ Réservation" (le devis est toujours en premier)
- [ ] Raccourci "Scanner QR" (accès direct au scan depuis le dashboard)

---

### 3.2 RÉSERVATIONS LISTE (`/reservations`)

**Rôle** : Trouver une réservation et aller sur sa fiche.

```
┌─────────────────────────────────────────────────────────┐
│  Réservations          [+ Nouveau devis]  [Scanner QR]  │
│  11 réservations                                        │
│                                                         │
│  ┌─ COMPTEURS ────────────────────────────────────────┐ │
│  │  1 Livrées | 1 Confirmées | 1 Retournées | 0 Ann. │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                         │
│  [Toutes] [Brouillon] [Confirmées] ... [Retards ⚠]     │
│                                                         │
│  ┌─ TABLEAU ──────────────────────────────────────────┐ │
│  │ Client    Réf         Dates       Statut   Montant │ │
│  │ ─────────────────────────────────────────────────── │ │
│  │ Alice T.  RES-0006    5→6 mars    Livré    98,80€  │ │
│  │   → CLIC SUR LA LIGNE = /reservations/7            │ │
│  │                                                     │ │
│  │ Combo     RES-0010    9→10 mars   Retourné  22,60€ │ │
│  │   → CLIC SUR LA LIGNE = /reservations/10           │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Changements vs actuel :**
- [ ] Clic sur une ligne → navigation vers `/reservations/$id` (PAS une modale)
- [ ] Bouton "+ Nouveau devis" (pas "+ Réservation" car devis systématique)
- [ ] Bouton "Scanner QR" accessible depuis la liste

---

### 3.3 FICHE RÉSERVATION (`/reservations/$id`) — PAGE HUB

**Rôle** : Tableau de bord d'une réservation. Page compacte, cartes-résumé cliquables
qui ouvrent des modales ciblées pour agir.

> Architecture : HUB + MODALES SMART
> - La page montre l'essentiel en un coup d'œil (pas de scroll infini)
> - Chaque carte affiche un résumé (statut, compteur, indicateur clé)
> - Clic sur une carte → modale dédiée avec le détail + actions
> - L'ancienne `EventDetailsModal` monolithique est supprimée

```
┌─────────────────────────────────────────────────────────┐
│  ← Réservations                                         │
│                                                         │
│  RES-2026-0006  [Livré]              Alice Test         │
│  Anniversaire · 5 mars 2026 · vvv   98,80 € HT        │
│  Devis source: DEV-2026-0015        Assigné: Admin     │
│                                                         │
│  ┌─ BANDEAU ACTION (contextuel selon statut) ────────┐ │
│  │                                                     │ │
│  │  Si draft     → [Confirmer]  [Modifier]  [Suppr.]  │ │
│  │  Si confirmé  → [Lancer pre-check]  [Relancer]     │ │
│  │  Si pre_check → [▶ Procéder au départ]             │ │
│  │  Si livré     → [↩ Enregistrer le retour]          │ │
│  │  Si retourné  → [Clôturer]  [Ouvrir litige]       │ │
│  │  Si litige    → [Clôturer le litige]               │ │
│  │  Si terminé   → [Archiver]                          │ │
│  │                                                     │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                         │
│  ┌─ Timeline terrain ────────────────────────────────┐ │
│  │ ●━━━●━━━●━━━○━━━○                                │ │
│  │ Créée  Départ  Event  Retour  Clôture             │ │
│  │        5 mars  5 mars 6 mars                       │ │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
│  ┌─ GRILLE DE CARTES CLIQUABLES ─────────────────────┐ │
│  │                                                     │ │
│  │  ┌──────────────┐  ┌──────────────┐                │ │
│  │  │ 📦 Lignes    │  │ ✓ Pre-check  │                │ │
│  │  │ 2 articles   │  │ 2/2 validé   │                │ │
│  │  │ → modale     │  │ → modale     │                │ │
│  │  └──────────────┘  └──────────────┘                │ │
│  │                                                     │ │
│  │  ┌──────────────┐  ┌──────────────┐                │ │
│  │  │ 💰 Caution   │  │ 🧾 Facture   │                │ │
│  │  │ ⚠ En attente │  │ INV-0005 80% │                │ │
│  │  │ → modale     │  │ → modale     │                │ │
│  │  └──────────────┘  └──────────────┘                │ │
│  │                                                     │ │
│  │  ┌──────────────┐  ┌──────────────┐                │ │
│  │  │ 📋 Mouvements│  │ ⚠ Risques    │                │ │
│  │  │ Départ #3    │  │ 1 actif      │                │ │
│  │  │ → modale     │  │ → modale     │                │ │
│  │  └──────────────┘  └──────────────┘                │ │
│  │                                                     │ │
│  │  ┌──────────────┐  ┌──────────────┐                │ │
│  │  │ ↔ Prolonger  │  │ 📜 Historique │                │ │
│  │  │ (si livré)   │  │ 12 entrées   │                │ │
│  │  │ → modale     │  │ → modale     │                │ │
│  │  └──────────────┘  └──────────────┘                │ │
│  │                                                     │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                         │
│  ┌─ Notes ───────────────────────────────────────────┐ │
│  │ (inline, éditable directement)                    │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘

MODALES SMART (chacune s'ouvre depuis sa carte) :

  📦 LignesModal
     Tableau produits complet (variante, qté, prix/j, jours, sous-total)
     [Modifier les lignes] si brouillon
     Total estimé en footer

  ✓ PreCheckModal
     Checklist avec cases à cocher
     [+ Ajouter item]
     [Valider pre-check] si tout coché et statut pre_check

  💰 CautionModal
     Montant attendu (CGV 3×)
     Statut (en attente / reçue / restituée / retenue)
     [Enregistrer caution] [Restituer] [Retenir (partiel)]
     [Relancer client]

  🧾 FacturationModal
     Liste factures liées (avec badge statut, montant, progression paiement)
     [Enregistrer paiement] par facture
     [+ Générer facture] si pas de facture
     [Voir facture] → lien vers /finance/invoices/$id

  📋 MouvementsModal
     Liste départ/retour avec dates et statuts
     Clic sur un mouvement → /operations/departure/$id ou /operations/return/$id

  ⚠ RisquesModal
     Liste risques (type, sévérité, résolu/actif)
     [+ Signaler un risque]
     [Supprimer] par risque

  ↔ ProlongerModal
     Formulaire : nouvelle date retour, raison, supplément optionnel
     [Confirmer la prolongation]

  📜 HistoriqueModal
     Timeline audit trail complet (date, utilisateur, action, description)
```

**Changements vs actuel :**
- [ ] Supprimer `EventDetailsModal` (modale monolithique de 400+ lignes)
- [ ] Réécrire `EventDetailPage` en page hub avec grille de cartes
- [ ] Créer 8 modales smart ciblées (Lignes, PreCheck, Caution, Facturation, Mouvements, Risques, Prolonger, Historique)
- [ ] Réutiliser les sections existantes (`PreCheckSection`, `DepositSection`, `ExtendSection`, `RisksSection`) comme contenu des modales
- [ ] Bandeau action contextuel en haut (l'action suivante est toujours visible)
- [ ] Header riche : référence, statut, client (lien), devis source (lien), assigné
- [ ] Timeline terrain compacte (barre de progression horizontale)
- [ ] Tous les liens sortants pointent vers les bonnes entités

---

### 3.4 PAGE OPÉRATIONS (`/operations`)

**Rôle** : Tableau de bord opérationnel — qu'est-ce que je dois faire maintenant ?

```
┌─────────────────────────────────────────────────────────┐
│  Opérations                              [Scanner QR]   │
│                                                         │
│  ┌─ DÉPARTS À FAIRE ─────────────────────────────────┐ │
│  │ RES-2026-0011  Test Audit   2 art.  Confirmé      │ │
│  │   → clic = /operations/departure/$id              │ │
│  │                                                     │ │
│  │ RES-2026-0003  Import Test  3 art.  Pre-check     │ │
│  │   → clic = /operations/departure/$id              │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                         │
│  ┌─ RETOURS ATTENDUS ────────────────────────────────┐ │
│  │ RES-2026-0006  Alice Test   2 art.  Retour: 6 mars│ │
│  │   → clic = /operations/return/$id                 │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                         │
│  ┌─ EN RETARD ⚠ ─────────────────────────────────────┐ │
│  │ RES-2026-0002  Import Test  Retour prévu: 5 mars  │ │
│  │   → clic = /reservations/$id                      │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                         │
│  ┌─ SCANS RÉCENTS ───────────────────────────────────┐ │
│  │ departure:11  21:48 | reservation:12  21:48       │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Changements vs actuel :**
- [ ] Nouvelle page `/operations/` = tableau de bord (pas le scanner)
- [ ] Scanner QR déplacé en bouton d'accès rapide (coin haut droit)
- [ ] `/operations/scan` reste accessible mais n'est plus le landing
- [ ] Chaque ligne est cliquable vers la bonne opération

---

### 3.5 FLUX DEVIS → RÉSERVATION

**Rôle** : Parcours linéaire, le devis mène naturellement à la réservation.

```
/devis/new
  → Formulaire création devis
  → Enregistrer → /devis/$id

/devis/$id
  → Fiche devis complète (lignes, versions, négociation)
  → Bouton [Envoyer au client] → statut "envoyé"
  → Bouton [Accepter] → statut "accepté"
  → Bouton [Convertir en réservation →]
      → Crée la réservation avec les données du devis
      → Navigue automatiquement vers /reservations/$newId
      → La fiche réservation affiche "Source: DEV-2026-XXXX" (lien retour)

/reservations/$id
  → "Devis source: DEV-2026-XXXX" (lien cliquable vers le devis)
  → Le devis passe en statut "converti"
```

**Changements vs actuel :**
- [ ] Le bouton "+ Nouveau" dans la liste réservations → crée un devis (pas une résa directe)
- [ ] Le bouton de conversion dans le devis → navigue vers la fiche résa créée
- [ ] Lien bidirectionnel devis ↔ réservation visible dans les deux fiches

---

### 3.6 FLOW DÉPART (`/operations/departure/$id`)

**Rôle** : Checklist terrain, article par article, avec scan QR et signature.

```
Page actuelle : OK dans l'ensemble
Améliorations à discuter :
- [ ] Bouton retour → /reservations/$id (pas /reservations liste)
- [ ] Après validation → naviguer vers /reservations/$id (confirmé OK)
- [ ] Header : afficher référence réservation + client + date
```

---

### 3.7 FLOW RETOUR (`/operations/return/$id`)

**Rôle** : Contrôle retour article par article, déclaration dégâts, signature.

```
Page actuelle : OK dans l'ensemble
Améliorations à discuter :
- [ ] Bouton retour → /reservations/$id
- [ ] Après validation → naviguer vers /reservations/$id
- [ ] Lien direct "Créer facture dégâts" → pré-rempli depuis les constats
```

---

### 3.8 PLANNING (`/planning/today`)

**Rôle** : Vue calendrier des opérations.

```
Améliorations :
- [ ] Chaque ligne de départ/retour/retard = lien cliquable vers /reservations/$id
- [ ] Bouton d'action rapide sur chaque ligne (→ départ ou → retour)
```

---

## 4. Audit des gaps Backend / Frontend

### 4.1 DASHBOARD — Gaps

| Feature | Backend | Frontend | Gap | Priorité |
|---|---|---|---|---|
| Alertes deep link | ✅ retourne `reservation_id` | ❌ navigue vers `/reservations` (liste) | Changer 1 ligne : `navigate → /reservations/${id}` | **P0** |
| Aujourd'hui deep link | ✅ départs/retours avec IDs | ❌ navigue vers `/reservations` (liste) | Changer 1 ligne | **P0** |
| Activité deep link | ✅ retourne liens complets | ❌ regex `.replace(/\/\d+$/, '')` supprime l'ID | Supprimer la regex, utiliser `item.link` directement | **P0** |
| Raccourci "+ Devis" | — | ❌ bouton "+ Réservation" actuellement | Changer label + destination vers `/devis/new` | **P1** |
| Raccourci Scanner QR | — | ❌ inexistant | Ajouter bouton vers `/operations/scan` | **P1** |
| KPIs supplémentaires | ✅ 11 métriques retournées | ⚠️ 5 affichées sur 11 | Afficher CA mois, retours programmés | **P2** |

### 4.2 LISTE RÉSERVATIONS — Gaps

| Feature | Backend | Frontend | Gap | Priorité |
|---|---|---|---|---|
| Clic ligne → page détail | — | ❌ ouvre modale au lieu de naviguer | Changer onClick → `navigate(/reservations/$id)` | **P0** |
| Bouton "+ Nouveau devis" | — | ❌ label "+ Nouveau" crée résa directe | Changer label + destination vers `/devis/new` | **P1** |
| Supprimer page Commandes | — | ✅ existe | Retirer route `/commandes`, retirer du menu Plus | **P1** |

### 4.3 FICHE RÉSERVATION HUB — Gaps

| Carte | Backend | Frontend | Gap | Priorité |
|---|---|---|---|---|
| Header assigned_user | ✅ `assigned_user_id` retourné | ❌ nom non affiché | Ajouter nested user ou fetch séparé | **P2** |
| Timeline | ⚠️ pas de timestamps complétion | ❌ composant inexistant | Créer composant, dériver dates des mouvements | **P1** |
| Lignes | ✅ `lines[]` dans response | ❌ modale manquante | Créer `LignesModal` | **P1** |
| Pre-check | ✅ endpoint + mutations | ⚠️ existe inline (PreCheckSection) | Wrapper en modale | **P1** |
| Caution | ✅ endpoint + mutations | ❌ modale manquante | Créer `CautionModal` (réutiliser DepositSection) | **P1** |
| Facture | ✅ endpoint + mutations | ❌ modale manquante | Créer `FacturesModal` | **P1** |
| Mouvements | ✅ endpoint | ❌ modale manquante | Créer `MouvementsModal` | **P1** |
| Risques | ✅ endpoint + mutations | ❌ modale manquante | Créer `RisquesModal` (réutiliser RisksSection) | **P1** |
| Prolonger | ✅ mutation | ❌ modale manquante | Créer `ExtensionModal` (réutiliser ExtendSection) | **P1** |
| Historique | ⚠️ endpoint audit à vérifier | ❌ hook + modale manquants | Vérifier endpoint + créer `HistoriqueModal` | **P2** |
| Actions | ✅ toutes mutations existent | ✅ boutons existent | Consolider dans header (action + menu ⋮) | **P1** |
| Notes | ❌ champ absent du modèle backend | ⚠️ affiché si présent mais pas éditable | Ajouter colonne `notes` + migration + mutation PATCH | **P2** |
| Supprimer EventDetailsModal | — | ✅ 400+ lignes | Supprimer après migration contenu vers hub + modales | **P1** |

### 4.4 PAGE OPÉRATIONS — Gaps

| Feature | Backend | Frontend | Gap | Priorité |
|---|---|---|---|---|
| Dashboard opérations | ❌ pas d'endpoint dédié | ❌ page inexistante (landing = scanner) | Créer `GET /operations/summary` + `OperationsDashboardPage` | **P1** |
| Départs à faire | ⚠️ `/planning/today` incomplet | ❌ | Endpoint : filtrer `confirmed, pre_check, confirmed_risk` | **P1** |
| Retours attendus | ⚠️ seulement retours du jour | ❌ | Endpoint : inclure `delivered, extended` avec `return_date >= today` | **P1** |
| En retard | ✅ | ✅ dans Planning | Réutiliser dans dashboard opérations | **P1** |
| Bug ACTIVE_STATUSES | ❌ contient `in_progress` (n'existe pas) | — | Corriger → `pre_check, confirmed_risk, extended` | **P0** |
| Header client départ/retour | ✅ données disponibles | ❌ nom client non affiché | Ajouter `customer_name` dans header pages | **P2** |

### 4.5 FLOW DÉPART/RETOUR — Gaps

| Feature | Backend | Frontend | Gap | Priorité |
|---|---|---|---|---|
| Retour nav après validation | — | ✅ navigue vers `/reservations/$id` | OK | — |
| Bouton retour page | — | ❌ pas de lien retour visible | Ajouter `← RES-2026-XXXX` en header | **P2** |

### 4.6 PLANNING — Gaps

| Feature | Backend | Frontend | Gap | Priorité |
|---|---|---|---|---|
| Lignes cliquables | ✅ `reservation_id` retourné | ❌ lignes non cliquables | Ajouter `onClick → /reservations/$id` | **P1** |

---

## 5. Résumé des décisions actées

| # | Question | Décision |
|---|----------|----------|
| D1 | Fiche résa : page ou modale ? | **PAGE UNIQUE** `/reservations/$id` avec URL |
| D2 | Organisation fiche résa | **HUB + MODALES SMART** : page compacte avec cartes-résumé, clic → modale ciblée par section |
| D3 | Modale actuelle `EventDetailsModal` | **SUPPRIMER** — contenu migré dans la page hub |
| D4 | Landing Opérations | **DASHBOARD OPÉRATIONNEL** (départs/retours/retards), scanner = bouton accès rapide |
| D5 | Bouton "+ Nouveau" sur liste résa | **CRÉE UN DEVIS** (devis toujours systématique avant réservation) |
| D6 | Navigation retour après départ/retour | **VERS LA FICHE RÉSA** `/reservations/$id` |
| D7 | Mobile : fiche résa | **VERSION MOBILE DÉDIÉE** |
| D8 | Page Commandes | **SUPPRIMÉE** — Réservations reprend sa place dans la nav principale |
| D9 | Menu Plus priorité | **Catalogue** monté en tête des modules principaux |

---

## 6. Plan d'implémentation

### Phase 0 — Quick fixes (30 min)
- [ ] Dashboard : deep links alertes, aujourd'hui, activité (3 lignes)
- [ ] Bugfix `ACTIVE_STATUSES` dans planning (1 ligne)

### Phase 1 — Fiche Réservation Hub (le gros chantier)
- [ ] Réécrire `EventDetailPage` → page hub avec grille de cartes
- [ ] Créer composant `ReservationTimeline`
- [ ] Créer 8 modales smart (Lignes, PreCheck, Caution, Factures, Mouvements, Risques, Extension, Historique)
- [ ] Réutiliser `PreCheckSection`, `DepositSection`, `ExtendSection`, `RisksSection` comme contenu
- [ ] Actions contextuelles dans le header (bouton principal + menu ⋮)
- [ ] Supprimer `EventDetailsModal`

### Phase 2 — Navigation et pages
- [ ] Liste réservations : clic ligne → `/reservations/$id` (plus de modale)
- [ ] Liste réservations : bouton "+ Nouveau devis" → `/devis/new`
- [ ] Page opérations : créer `OperationsDashboardPage` (landing)
- [ ] Backend : créer endpoint `GET /operations/summary`
- [ ] Planning : lignes cliquables vers `/reservations/$id`
- [ ] Supprimer page Commandes + retirer de la nav

### Phase 3 — Polish
- [ ] Backend : ajouter champ `notes` sur Reservation + migration
- [ ] Header départ/retour : afficher nom client
- [ ] Historique : vérifier endpoint audit + créer hook
- [ ] KPIs dashboard supplémentaires
- [ ] Assigned user dans header fiche résa
- [ ] Version mobile dédiée fiche résa

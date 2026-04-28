# DECISIONS REFONTE MARVELINE — Modules metier

> Date : 2026-03-26
> Statut : Decide, en attente d'execution

---

## RESERVATIONS

### R1 — Supprimer ReservationDetailPage (ancienne page)
- Supprimer `pages/reservations/ReservationDetailPage.tsx`
- Decabler de `routes/_app/reservations/$id/index.lazy.tsx`
- Le routeur `ReservationRouter` devient le seul point d'entree
- Supprime le bug litige (complete au lieu de close-dispute)

### R2 — Completer derivePhase
- `confirmed` + conditions incompletes (caution OU acompte OU signature manquant) → `'legal'`
- `confirmed` + tout OK → `'prete'`
- Conditions = caution encaissee + acompte paye + signature contrat

### R3 — Workflow souple (pas de blocage rigide)
- Toutes les transitions sont possibles, le systeme avertit mais ne bloque pas
- Confirmations graduees selon le risque :
  - `pre_check` OK → bouton direct
  - `confirmed` → confirmation simple "Lancer sans caution ?"
  - `confirmed_risk` → double confirmation
- Les stats tracent les departs sans caution (donnees justes)

### R4 — Machine d'etats dans le store
- Garder `reservationStore.transition()` et `canTransition()`
- Corriger les transitions pour coller au backend
- Cabler dans chaque page phase (boutons conditionnes par canTransition)

### R5 — Corriger les pages phases
- ConfirmeePage : ajouter CTA "Lancer pre-check" + "Depart direct" (avec confirmation)
- RisquePage : ajouter "Lever le risque" + "Pre-check malgre risque" + "Depart direct"
- FocusPills completed : lire vrais depots/dommages au lieu de hardcode
- RetourneePage : ouvrir DamageDeclarationModal directement (pas re-flow retour)

### R6 — Supprimer code mort reservations
- Route `/$id/phases` (alias EventDetailPage)
- `useReservationDeposits` dans ReservationRouter (fetch inutile si derivePhase utilise les depots, sinon supprimer)
- `useReservationFull` (hook non consomme)

---

## DEVIS

### D1 — Supprimer DevisDetailPage (ancienne page)
- Supprimer `pages/devis/DevisDetailPage.tsx`
- `DevisIdLayout` seul point d'entree

### D2 — Fusionner modules + source + couverture → "Prestations"
- Une seule page : modules depliables avec items de couverture imbriques
- Supprimer `DevisModulesPage`, `DevisSourcePage`, `DevisCouverturePage`
- Creer `DevisPrestationsPage`

### D3 — Supprimer DevisPhasesPage
- Dates du projet dans infos generales (DevisEditPage)
- Evolution du devis = systeme de versions

### D4 — SubNav devis 5 onglets
```
Details | Prestations | Negociation | Versions | Demandes
```

### D5 — Machine d'etats dans le store
- Garder et corriger devisStore.transition()/canTransition()
- Cabler le stepper creation via le store (pas useState)

### D6 — Bugs devis a corriger
- TVA x100 dans DevisLinesTable → supprimer multiplication
- RefuseModal contexte vide → passer les props
- Diff versions lignes libres → cle par index/UUID
- Upload attachments → passer par client API
- canSend → autoriser draft + version_pending
- Signature → backend autoriser sent + accepted
- variant_label → ajouter selectinload backend
- Suppression fichier → commit DB avant, fichier apres
- Subtitles JSX non evalues (5 fichiers) → corriger en expressions

---

## OPERATIONS

### O1 — Double dommages retour
- Submit final exclut les dommages deja declares via le modal standalone
- Garder declaration au fil de l'eau (modal)

### O2 — Raison blocage depart
- Ajouter champ `blocked_reason` sur la reservation (ou mouvement) cote backend
- Passer `data.reason` dans `ops_svc.block_departure()`
- Afficher la raison sur la page reservation

### O3 — Comptage articles vs pre-checks
- Backend `get_departure_state` : compter les DepartureItem, pas les PreCheckItem

### O4 — Article endommage au depart
- Autoriser le depart avec article endommage
- Creer une declaration de dommage automatiquement
- Supprimer le blocage 400 pour condition damaged/missing

### O5 — QR scan via backend
- ScanPage appelle `GET /qr/{code}` au lieu de parser localement
- Resultat (product_id + stock_item_id) → coche l'article dans la checklist

### O6 — Fixes techniques operations
- Cle item : `${line_id}-${product_id}` (pas addition)
- Redirect post-retour : vers `/reservations/$id`
- Boutons : "Article par article" → check inventaire, "Controle legal" → page legal reservation
- Photo + note article : implementer (backend POST /damage/photo + champ note dans payload)
- operationsStore : utiliser partout (remplacer useState local)
- Pre-check persistant : sauvegarder chaque coche en base immediatement

### O7 — Departs : statuts visibles avec confirmations graduees
- Liste departs : confirmed + confirmed_risk + pre_check
- pre_check → bouton direct
- confirmed → confirmation simple
- confirmed_risk → double confirmation

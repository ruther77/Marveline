# AUDIT MARVELINE — Frontend x Backend — Verifie

> Date : 2026-03-26
> Scope : App Marveline (frontend/apps/marveline) + API backend (app/api/v1)
> Methode : Cartographie + verification exhaustive dans le code + lecture reelle des pages

---

## PARTIE 1 — CHIFFRES

| Dimension | Count |
|---|---|
| Routes frontend | 179 fichiers |
| Endpoints backend | ~494 |
| Hooks useQuery/useMutation | 250+ |
| Stores Zustand | 13 (dont 3 persistes localStorage) |
| SubNav | 8 lieux |
| Pages orphelines confirmees | 9 |
| Code mort confirme | 15 routes/pages |
| Hooks backend sans frontend | 2 (planning/block, planning/forecast) |

---

## PARTIE 2 — FLOW PRINCIPAL (ce que l'utilisateur vit)

### Flow metier : Devis -> Reservation -> Depart -> Retour -> Facture -> Paiement

#### Etape 1 — Creer un devis (`/devis/new`)

Stepper 3 etapes :
1. **Client/Dates** : combobox client async, date evenement, date validite, lieu, conditions paiement (4 options : 30/70, 50/50, comptant, fin event), notes
2. **Articles** : composant `DevisLineEditor` — ajout/suppression lignes, label, qty, prix unitaire, sous-total
3. **Recap** : grille infos + detail lignes + total HT + message accompagnement + 2 boutons ("Brouillon" / "Creer et envoyer")

Donnees viennent du CartStore (persist localStorage, mode 'devis' ou 'reservation').

#### Etape 2 — Gerer le devis (`/devis/$id`)

Page detail riche :
- Hero statut avec message contextuel + montant TTC + dates
- **Bouton primaire change selon statut** : Draft → "Envoyer", Sent → "Accepter", Accepted → "Convertir en reservation"
- Sections collapsibles : Infos, Articles (avec detail bundle imbrique), Negociation, Signature, Versions, Pieces jointes, Historique lignes
- Actions secondaires dropdown : Refuser, Negocier, Passer en revision, Dupliquer, Annuler, PDF

#### Etape 3 — Convertir en reservation

Depuis `/devis/$id` → bouton "Convertir" → modal `DevisConvertModal` (choix dates livraison/retour) → POST /devis/{id}/convert → cree reservation → redirect `/reservations/$id`

#### Etape 4 — Reservation par phase (`/reservations/$id/$phase`)

`ReservationRouter` charge le detail + depots → `derivePhase()` → redirect vers la page phase appropriee.

**derivePhase() — mapping status backend → phase UI :**

| Status backend | Phase UI |
|---|---|
| cancelled | annulee |
| completed | terminee |
| returned_dispute | litige |
| returned | retournee |
| extended | prolongee |
| delivered | en-cours |
| confirmed_risk | risque |
| pre_check | precheck |
| confirmed | confirmee |
| draft (sans lignes) | brouillon-incomplet |
| draft (avec lignes) | brouillon |

**Phases jamais atteintes par derivePhase() :** `prete` et `legal` — ces pages existent mais ne peuvent pas etre affichees via le routeur actuel. Piste : transitions manuelles ou conditions supplementaires non implementees.

**Page confirmee** — l'utilisateur voit :
- ReservationHero (header colore + barre progression)
- StatusAlert ("Caution et acompte valides")
- ReservationInfoGrid (client, evenement, livraison, lieu)
- DepositSection (depot courant + barre paiement + boutons Encaisser/Relancer)
- ProductLines (articles reserves)
- InvoiceSection (factures liees)
- AssignSection (affectation staff)

**Page prete** — l'utilisateur voit :
- Meme layout que confirmee
- StatusAlert "Le depart peut etre lance"
- 2 CTA : "Lancer le depart" (→ /operations/departure/$id) + "Marquer livree" (bypass)
- PreCheckSection (checklist pre-depart)

#### Etape 5 — Depart (`/operations/departure/$reservationId`)

Page inventaire depart detaillee :
- Compteur "N / M articles charges" + badge autorise/preparation
- **Alerte blocage** si caution non encaissee ou pre-verifs incompletes
- **Checklist articles** groupes par bundle :
  - Image, nom, SKU, quantite attendue
  - Badge "Scanne" si QR OK
  - Inputs : quantite chargee (number) + etat (Neuf/Bon/Correct/Endommage/Manquant)
  - Scanner QR (active camera)
- **Bouton bloquer depart** avec raison (textarea)
- **Signature** pad numerique
- **Bouton "Valider le depart"** → cree inventory_movements, transition → delivered

#### Etape 6 — Retour (`/operations/return/$reservationId`)

Page inventaire retour :
- Barre progression "N / M articles verifies" + "K endommages"
- **Resume dommages** si existants (alerte + cout estime)
- **Checklist articles** groupes par bundle :
  - Image, nom, quantite attendue vs retournee
  - Etat constante (chip colore)
  - Liste dommages par article (description, severite, cout)
- **Bouton "Declarer un dommage"** → modal (produit, description, severite, cout, photos)
- **Boutons facture** : "Creer facture dommage" (si couts > 0) ou "Creer facture" ou "Lier existante"
- **Signature** pad
- **Bouton "Valider le retour"** → transition → returned

#### Etape 7 — Facture (`/finance/invoices/new`)

Stepper 3 etapes :
1. **Selection reservation** : search + liste reservations (confirmed/completed), clic = selection
2. **Parametrage** : type facture (radio : 100% complete, 40% acompte, 60% solde) + dates emission/echeance + preview montant
3. **Recap** : infos resa + lignes + total calcule selon type → bouton "Creer facture"

Liste factures (`/finance/invoices`) :
- KPI bar (total, payees, en attente, retard)
- Status chips filtres
- Cartes avec : N°, statut badge, montant TTC, client, dates, PaymentProgressBar
- Swipe actions : Annuler, Envoyer/Relancer, Payer

---

## PARTIE 3 — FLOWS SECONDAIRES

### Dashboard (`/dashboard`)

L'utilisateur voit :
- Greeting "Bonjour, {name}" + date
- **Alerte urgente** (banner danger) : "Retour a controler" + ref + client → clic = detail reservation
- **Search bar** clickable → `/search`
- **Today cards** (horizontal scroll) : Departs + Retours du jour, chaque card = ref + client → clic = detail
- **Quick actions** grid : Nouvelle reservation, Nouvelle facture, etc.
- **Activity feed** vertical scrollable

**Manques :** Pas de KPI globaux (CA jour, reservations en cours). Activity feed peut etre vide sans fallback.

### Clients (`/customers`)

Liste : cartes en grille, avatar par type (individual/company/professional/association), search + chips type + toggle "A relancer", swipe (appeler, email, modifier, supprimer), import CSV.

Detail client :
- Avatar + infos contact + note interne
- 3 KPI : Total reservations, CA total, Derniere prestation
- 3 tables : Reservations, Factures, Relances planifiees
- Actions : Message, Nouveau devis (→ /devis/new?customer_id=X), Planifier relance, Modifier

**Manques :** Quick-links sont des anchors HTML (pas des routes, ne scrollent pas). Pas de timeline interaction. Pas d'export fiche PDF.

### Catalogue (`/catalogue/products`)

Liste : search bar (→ /catalogue/search), chips categories, cartes produit (image, badge categorie, nom, SKU, prix/jour, stock dispo colore vert/orange/rouge), swipe (modifier, supprimer).

Detail produit : sections collapsibles — Photos (upload, set primary), Stock (level bar, qty), Variantes (tableau), Disponibilite (mini calendrier mois : gris libre, orange partiel, rouge complet), Historique/Audit (timeline), Maintenance (planning reparations).

**Manques :** Pas d'edition directe produit depuis cette page (prix, description). Mini calendrier n'affiche pas les maintenances. Pas de lien fournisseurs.

### Hub Parc (`/parc` via ParcHubPage)

3 sections de cards :
- **CATALOGUE** (5 cards) : Produits, Recherche, Collections, Formules, QR Codes
- **STOCK** (5 cards) : Stock, Operations, Reparations, Inventaire physique, Types dommages
- **FOURNISSEURS** (2 cards) : Fournisseurs, Pilotage

**Manques :** Pas de KPI sur le hub (ex: "8 produits en stock critique"). Pas de raccourcis recents.

### Finance synthese (`/finance`)

Selector annee + 4 KPI cards (CA encaisse, variation % vs N-1) + 2 graphiques (bar+area comparaison N/N-1, area CA cumulatif) + tableau mois a mois (CA, factures payees, factures en retard, delta %).

**Manques :** Pas de drill-down (clic mois → factures du mois). Pas d'export rapport. Pas de projection.

---

## PARTIE 4 — MACHINES D'ETATS

### Reservation (10 statuts, 15 transitions)

```
draft → confirmed → confirmed_risk → pre_check → delivered → extended → returned → returned_dispute → completed
                                                                                                      (terminal)
* → cancelled (depuis la plupart des etats)
```

### Devis (8 statuts, 13 transitions + stepper 3 etapes)

```
draft → sent → { negotiation, version_pending } → accepted → converted (terminal)
                         ↓
                      refused (terminal)
                      expired → draft (recyclage)
* → cancelled (terminal)
```

Stepper creation : `client → articles → recap`

### Facture (5 statuts, 7 transitions)

```
draft → sent → { paid (terminal), overdue } → cancelled (terminal)
```

PaymentDraft dans le store : amount_euros (saisie) → amount_cents (auto-calcule Math.round * 100)

### Vente (7 statuts, 11 transitions)

```
draft → pending → { deposit_paid, overdue } → fully_paid → refunded (terminal)
* → cancelled (terminal)
```

### Evenement (8 statuts, 11 transitions)

```
planned ↔ risk ↔ in_progress → incident ↔ in_progress
                     ↓
                  returned → damage → closed (terminal)
* → cancelled (terminal)
```

Note : ce store est actif mais les pages frontend sont mortes (redirect /evenements → /reservations).

### Stores persistes (localStorage)

| Store | Cle | Ce qu'il garde |
|---|---|---|
| CartStore | marveline-cart | mode (devis/reservation), lignes (product_id, qty, unit_price_cents, subtotal auto), customer_id, dates, notes |
| OperationsStore | marveline-operations | activeReservationId, scannedCodes[], damageDeclarations[], signature base64, inventaire depart/retour |
| FilterStore | (partiel) | Seulement pageSizes. Filtres reinitialises a chaque mount. |

### Gotchas verifies

1. **derivePhase() ne produit jamais 'prete' ni 'legal'** — ces pages existent mais sont inatteignables
2. **CartStore persist** — risque de pollution croisee devis/reservation si l'utilisateur change de mode sans vider
3. **OperationsStore persist** — session fantome possible si fermeture navigateur en milieu d'operation terrain
4. **Store.transition() ne mutate pas** — validation seulement, la vraie mutation est backend

---

## PARTIE 5 — NAVIGATION

### Bottom Nav (5 entrees)

```
Dashboard (/dashboard)  |  Planning (/planning/calendar)  |  Reservations (/reservations)  |  Operations (/operations)  |  Plus (/plus)
```

Plus = 12 liens heterogenes (Catalogue, Clients, Parc, Finances, Devis, Stats, Tarification, Fournisseurs, Equipe, Parametres, Audit, Cles API).

### SubNav par module

| Module | Items | Probleme |
|---|---|---|
| Admin | 7 (Users, Sessions, API Keys, Features, Audit, VPN, Settings) | OK |
| Profile | 4 (Infos, Securite, 2FA, Sessions) | OK |
| Finance | 5 (Synthese, Factures, Tresorerie, TVA, Rapports) | TVA et Rapports = sous-pages /finance/invoices/ presentees au meme rang |
| Stock | 5 (<- Catalogue, Articles, Inventaire, Ajustements, Reparations) | Ping-pong circulaire avec Catalogue |
| Catalogue | 7 (<- Stock, Produits, Bundles, Categories, Collections, Contenants, Recherche) | Ping-pong circulaire avec Stock |
| Produit detail | 5 (<- Catalogue, Fiche, Editeur, Variantes, Maintenance) | OK |
| Devis detail | 3 (Details, Negociation, Versions) | 6 sous-pages existent en code mais pas cablees |
| Commandes hub | 4 (Tout, Devis, Reservations, Ventes) | Liens sortants sans retour |

### Hubs intermediaires decouverts

- **ParcHubPage** : 12 cards vers sous-modules catalogue/stock/fournisseurs
- **ProductToolsPage** : 6 cards vers outils catalogue (comparator, availability, import, builder, formulas, qr)

Ces hubs rendent accessibles des pages qui ne sont pas dans les SubNav.

### Planning — navigation reelle

AgendaPage avec **2 onglets internes** (useState, pas de route) : "Calendrier" + "Jour J". Les 7 routes /planning/day, /week, /month, /today, /affectation, /resources, /conflicts sont du **code mort**.

### Evenements — navigation reelle

`/evenements/` fait un **hard redirect** vers `/reservations`. Pages `EvenementsListPage` et `EvenementDetailPage` existent mais ne sont **jamais importees**. Code mort. Backend 14 endpoints + store actifs.

---

## PARTIE 6 — PAGES ORPHELINES CONFIRMEES (9)

Verifiees par grep exhaustif dans tout le code frontend — aucun lien, navigate, href ne pointe vers ces pages.

| Route | Module |
|---|---|
| `/catalogue/supplier-orders` | Catalogue |
| `/catalogue/delivery-zones` | Catalogue |
| `/finance/period` | Finance |
| `/finance/export` | Finance |
| `/finance/invoices/cautions` | Finance |
| `/finance/invoices/rapprochement` | Finance |
| `/stock/alerts/$id` | Stock |
| `/customers/rfm` | Clients |
| `/notifications/settings` | Notifications (pas d'endpoint backend non plus) |

---

## PARTIE 7 — CODE MORT CONFIRME

| Element | Module | Detail |
|---|---|---|
| 7 routes planning | Planning | /day, /week, /month, /today, /affectation, /resources, /conflicts |
| 2 pages evenements | Evenements | EvenementsListPage, EvenementDetailPage — jamais importees |
| 6 stubs devis | Devis | Routes $id/modules, couverture, phases, source, change-requests, edit — pages existent mais pas cablees au SubNav |
| 2 phases reservation | Reservations | PretePage et LegalPage — derivePhase() ne les produit jamais |

---

## PARTIE 8 — VRAIS PROBLEMES UX IDENTIFIES

### P1 — Phases reservation inatteignables

`PretePage` et `LegalPage` existent, sont codees, mais `derivePhase()` ne retourne jamais ces valeurs. L'utilisateur ne peut pas les voir. Soit la logique derivePhase doit etre completee, soit ces pages sont du code mort.

### P2 — Devis 6 sous-pages mortes

Routes `/devis/$id/modules`, `/couverture`, `/phases`, `/source`, `/change-requests` existent comme stubs. Les composants pages existent (`DevisModulesPage`, etc.) mais ne sont jamais importes ni lies. SubNav affiche seulement 3/9. Le code a ete ecrit mais jamais cable.

### P3 — Stock <-> Catalogue navigation circulaire

Les deux SubNav se pointent mutuellement avec `<- Stock` et `<- Catalogue`. C'est un seul domaine metier (parc materiel) coupe en deux avec un ping-pong. Le ParcHubPage existe comme hub unifie mais n'est pas le point d'entree standard.

### P4 — Finance fausse hierarchie

SubNav Finance met TVA (`/finance/invoices/tva-report`) et Rapports (`/finance/invoices/rapport-mensuel`) au meme rang que Factures. Ce sont des sous-pages de factures. 5 pages finance orphelines en plus.

### P5 — Plus = fourre-tout

12 modules ranges derriere un bouton "Plus". Clients et Devis — modules quotidiens — necessitent 2 taps. Pas de personnalisation, pas de favoris, pas de raccourcis.

### P6 — Commandes hub sans retour

SubNav `/commandes` pointe vers /devis, /reservations, /ventes qui sont des modules independants. Clic sur une ligne → navigate hors du hub. Pas de breadcrumb retour.

### P7 — Evenements = code mort complet

Hard redirect vers /reservations. 2 pages, 5 modals, 1 store, 9 hooks, 14 endpoints — tout actif sauf l'UI. Decision a prendre : supprimer ou restaurer.

### P8 — Loyalty = module fantome

17 endpoints + 9 hooks + 0 pages. Pret a cabler mais invisible.

### P9 — Dashboard sans KPI globaux

Greeting + alerte urgente + today cards + quick actions. Mais pas de CA du jour, pas de reservations en cours, pas de factures en retard. Activity feed peut etre vide sans message fallback.

### P10 — Detail client : quick-links = anchors HTML

Les liens "Reservations | Factures | Devis" sur la fiche client sont des `<a href="#">` qui ne scrollent pas et ne naviguent pas. Fonctionnellement casses.

### P11 — Catalogue : pas d'edition directe produit

La page detail produit n'a pas de bouton modifier (prix, description, categorie). Il faut passer par la liste et son swipe "Modifier" qui ouvre un modal.

### P12 — CartStore pollution croisee

Le CartStore persiste en localStorage avec mode 'devis' ou 'reservation'. Si l'utilisateur commence un devis puis bascule sur une reservation sans vider, les lignes polluent le nouveau contexte.

---

## PARTIE 9 — CORRECTIONS AUDIT INITIAL

L'audit initial (premiere passe) contenait 83% de faux positifs sur les hooks manquants et 53% sur les pages orphelines. Causes : les agents avaient cherche les routes et hooks par nom sans lire le code reel (pages intermediaires, hubs, noms de fonctions differents des endpoints).

### Hooks declares "manquants" qui EXISTENT

| Endpoint | Hook reel |
|---|---|
| POST /operations/departure/{id}/block | useBlockDeparture() — operations.ts:34 |
| POST /operations/return/{id}/damage | useDeclareCasse() — operations.ts:54 |
| GET /operations/qr/{code} | useResolveQr() — operations.ts:61 |
| POST /ventes/{id}/refund | useVenteRefund() — ventes.ts:74 |
| POST /ventes/{id}/cancel | useCancelVente() — ventes.ts:81 |
| POST /reservations/{id}/extend | useExtendReservation() — reservations.ts:114 |
| POST /reservations/{id}/assign | useAssignReservationUser() — reservations.ts:151 |
| Disputes close | useCloseReservationDispute() — reservations.ts:145 |
| POST /devis/{id}/sign | useSignDevis() — devis.ts:132 |
| POST /devis/{id}/refuse | useDevisMutations().refuse — devis.ts:81 |

### Pages declarees "orphelines" qui ont des liens

| Route | Lie depuis |
|---|---|
| /catalogue/formulas | ParcHubPage:79 + ProductToolsPage:65 |
| /catalogue/comparator | ProductToolsPage:43 + BundlesPage:144 |
| /catalogue/availability | ProductToolsPage:41 |
| /catalogue/qr | ParcHubPage:86 + ProductToolsPage:53 + ProductStatesPage:226 + CatalogueSearchPage:97 |
| /catalogue/import | ProductToolsPage:52 |
| /catalogue/tools | ProductsPage:267 + BundlesPage:192 |
| /catalogue/builder | ProductToolsPage:63 |
| /finance/pricing | PlusPage:70 |
| /stock/damage-types | ParcHubPage:125 |
| /stock/repairs | ReturnCheckModal:217 + ParcHubPage:110 |
| /customers/relances | CustomersPage:261 (filtre ?relances=true) |

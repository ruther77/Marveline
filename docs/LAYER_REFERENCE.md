# Reference LAYER

## Objectif
Document de pilotage pour `docs/LAYER.html`.
Il sert a:
- garder une vue globale des ecrans/modales/flux,
- eviter les oublis quand on ajoute des scenarios,
- tracer ce qui manque encore dans l'existant.

Date de reference: 19 fevrier 2026.
Source fonctionnelle principale: `/home/ruuuzer/Téléchargements/Devis MarvelineCorp.pdf`.

## Chiffres Actuels
- Ecrans: `55`
- Modales: `58`
- Filtres actifs: `9`
- Groupes nav bas: `5` (`Accueil`, `Agenda`, `Ventes`, `Stock`, `Factures`)

## Conventions Techniques
- Ecrans: `id="s-*"`
- Modales: `id="m-*"`
- Navigation ecrans: `go(id)`
- Ouverture modales: `openModal(id)`
- Fermeture modales: `closeModal(id)` / `closeOnBg(...)`
- Filtres: `apply*Filter(...)` + `data-state` sur les lignes
- Mapping nav: `NAV_GROUP_BY_SCREEN` (obligatoire pour tout nouvel ecran)

## Cartographie Ecrans

### Groupe `s-home`
- `s-home` - Accueil
- `s-recherche-globale` - Recherche transverse
- `s-resa-brouillon` - Reservation brouillon
- `s-resa-brouillon-incomplet` - Brouillon incomplet
- `s-resa-confirmee-sans-caution` - Confirmee sans caution
- `s-resa-confirmee-risque` - Confirmee risque
- `s-resa-confirmee-avec-caution` - Confirmee avec caution
- `s-resa-confirmee-prete` - Confirmee prete depart
- `s-resa-precheck-legal` - Pre-check legal pre-depart
- `s-depart-from-resa` - Preparation depart
- `s-depart-bloque` - Depart bloque
- `s-depart-inventaire` - Inventaire de sortie
- `s-resa-en-cours` - En cours
- `s-resa-en-cours-prolongee` - En cours prolongee
- `s-resa-retournee` - Retournee
- `s-retour-inventaire` - Inventaire de retour
- `s-resa-retournee-litige` - Retournee litige
- `s-resa-terminee` - Terminee
- `s-resa-terminee-archive` - Archive

### Groupe `s-events-list`
- `s-events-list` - Liste evenements
- `s-planning-semaine` - Planning semaine
- `s-planning-mois` - Planning mois
- `s-planning-affectation` - Affectation equipe/vehicule
- `s-event-prevu` - Evenement prevu
- `s-event-prevu-risque` - Prevu risque depart
- `s-event-en-cours` - Evenement en cours
- `s-event-en-cours-incident` - En cours incident
- `s-event-retourne` - Evenement retourne
- `s-event-retourne-casse` - Retourne casse
- `s-event-termine` - Evenement termine
- `s-event-annule` - Evenement annule

### Groupe `s-ventes`
- `s-ventes` - Liste ventes
- `s-vente-acompte` - Acompte
- `s-vente-multi` - Paiements multi-moyens
- `s-vente-solde` - Soldee
- `s-vente-retard` - Retard
- `s-vente-brouillon` - Brouillon

### Groupe `s-stock`
- `s-stock` - Vue stock
- `s-stock-item` - Critique
- `s-stock-faible` - Faible
- `s-stock-reassort` - Reassort en cours
- `s-stock-resolu` - Rupture resolue
- `s-stock-historique` - Historique complet des mouvements
- `s-stock-etats` - Etats article (endommage/reparation)

### Groupe `s-factures`
- `s-factures` - Liste factures
- `s-facture-detail` - Detail facture envoyee
- `s-facture-casse` - Facture dommages
- `s-facture-brouillon` - Facture brouillon
- `s-facture-retard` - Facture retard
- `s-facture-payee` - Facture payee
- `s-facture-create` - Creation facture
- `s-facture-audit` - Piste d'audit facture
- `s-devis-list` - Liste devis
- `s-devis-detail` - Detail devis
- `s-devis-expire` - Devis expire / versionning
- `s-devis-source` - Devis source (PDF)

## Filtres Disponibles
- `home-filter`: Toutes / Brouillon / Confirmee / En cours / Retournee / Terminee
- `events-filter`: Tous / Prevu / En cours / Retourne / Termine / Annule
- `ventes-filter`: Toutes / Acompte / Solde / Multi-moyens / Retard
- `stock-filter`: Tout / Alertes / Verres / Mobilier / Vaisselle
- `factures-filter`: Toutes / Brouillon / Envoyee / Payee / Retard
- `devis-filter`: Tous / Brouillon / Envoye / Accepte / Expire / Refuse
- `search-global-filter`: Tout / Reservations / Evenements / Factures / Stock / Clients
- `stock-history-filter`: Tout / Sorties / Retours / Ajustements / Dommages / Reassorts
- `invoice-audit-filter`: Tout / Envoi / Ouverture / Relances / Paiements / Actions internes

## Index Modales

### Reservation / Operationnel
- `m-creer-resa`, `m-modifier-resa`, `m-supprimer-resa`
- `m-confirmer-resa`, `m-encaisser-caution`, `m-relancer-caution`
- `m-ajouter-produit`, `m-supprimer-produit`
- `m-valider-depart`, `m-photo-depart`
- `m-bloquer-depart`, `m-valider-inventaire-sortie`, `m-valider-inventaire-retour`
- `m-frais-supp`, `m-prolonger-resa`
- `m-declarer-casse`, `m-cloturer-retour`, `m-clore-litige-resa`
- `m-archiver-resa`

### Evenements
- `m-creer-event`, `m-modifier-event`, `m-annuler-event`
- `m-affecter-ressources`
- `m-reprogrammer-event`, `m-plan-action-incident`
- `m-cloturer-event`, `m-rapport-event`, `m-remboursement-event`

### Stock
- `m-lancer-reassort`, `m-reception-reassort`
- `m-contact-fournisseur`, `m-cloturer-reassort`
- `m-ajuster-stock`

### Ventes / Factures
- `m-encaisser-solde`, `m-relancer-vente`
- `m-ajouter-paiement-multi`
- `m-marquer-payee`, `m-relancer-facture`, `m-avoir-facture`
- `m-facturer-casse`
- `m-supprimer-facture`, `m-recu-paiement`
- `m-export-factures`, `m-pdf-document`

### Devis
- `m-creer-devis`, `m-export-devis`, `m-pdf-devis`
- `m-envoyer-devis`, `m-accepter-devis`, `m-refuser-devis`, `m-devis-refuse`, `m-dupliquer-devis`
- `m-renouveler-devis`, `m-versionner-devis`
- `m-import-devis`, `m-ajouter-ligne-facture`, `m-facture-brouillon`, `m-envoyer-facture`

## Flux Scenario Couverts
- Reservation: brouillon -> confirmee -> depart (ok/bloque) -> en cours -> retournee -> terminee (+ variantes risque/litige/prolongation/archive)
- Evenement: prevu -> affectation ressources -> en cours -> retourne -> termine (+ variantes risque/incident/casse/annule)
- Vente: brouillon / acompte / multi-moyens / retard / soldee
- Stock: critique / faible / reassort / resolu + historique + etats
- Facture: brouillon / envoyee / retard / payee + piste audit
- Devis: brouillon / envoye / expire (renouvellement/versionning) / accepte / refuse + conversion facture

## Manques Connus Dans L'Existant (Priorite Interne)
- `s-home`: recherche globale maquettee, mais pas encore de scoring/tri de pertinence.
- `s-events-list`: affectation equipe/vehicule maquettee, mais pas encore de moteur anti-conflit ressources.
- `s-resa-precheck-legal`: checklist maquettee, mais pas de signature electronique certifiee.
- Depart/retour: inventaire detaille present, mais pas encore de mode scan code-barres/QR.
- Ventes: multi-moyens maquette, mais sans schema d'imputation comptable detaille.
- Devis: expiration/renouvellement/versionning maquettes, mais sans comparaison de diff automatisee par ligne.

## Regles D'Evolution (Obligatoire)
Quand on ajoute un nouveau scenario:
1. Ajouter l'ecran `s-*`.
2. Ajouter la/les entree(s) de navigation vers cet ecran.
3. Ajouter le mapping dans `NAV_GROUP_BY_SCREEN`.
4. Ajouter les modales `m-*` necessaires.
5. Si filtre: ajouter `data-state` + pill + fonction `apply*Filter`.
6. Mettre a jour ce fichier `docs/LAYER_REFERENCE.md`.

## Controle Qualite Minimal Avant Validation
- Toutes les actions `go/openModal/closeModal` pointent vers un `id` existant.
- Tous les boutons `btn-main` ont un `onclick`.
- Aucun `id` duplique.
- HTML parse sans erreur.
- Filtres fonctionnels sur les listes ciblees.

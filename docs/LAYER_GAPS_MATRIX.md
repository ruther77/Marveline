# Matrice Des Manques LAYER

Date: 19 fevrier 2026
Perimetre: ecrans deja presents dans `docs/LAYER.html`
Reference fonctionnelle: `/home/ruuuzer/Téléchargements/Devis MarvelineCorp.pdf`

## Legende
- `P0`: manque bloquant pour coherence du flux
- `P1`: manque important pour solidite produit
- `P2`: manque de confort ou de lisibilite

## 1) Manques Sur L'Existant (Priorite Haute)

| Zone | Ecran(s) Existant(s) | Manque Concret | Impact | Priorite | Statut |
|---|---|---|---|---|---|
| Accueil | `s-home` | Pas de recherche globale (client/resa/facture/stock) | Navigation lente quand volume augmente | P1 | Fait (maquette) |
| Accueil | `s-home` | Pas de mini planning visuel jour/semaine | Devis couvre planning, manque de vision operationnelle | P1 | Fait (maquette) |
| Reservations | `s-resa-brouillon` | Pas de versionning brouillon (v1/v2) | Risque d'erreur sur modifications | P2 | A faire |
| Reservations | `s-resa-confirmee-sans-caution` | Blocage depart non force (logique visuelle seulement) | Risque sortie materiel sans garantie | P0 | Fait (maquette) |
| Reservations | `s-resa-confirmee-avec-caution` | Pas de check legal/documents signes detaille | Validation incomplete pre-depart | P1 | Fait (maquette) |
| Reservations | `s-resa-en-cours` | Pas de timeline terrain (checkpoints sortie/livraison/retour) | Suivi logistique incomplet | P1 | Fait (2026-02-24) — EventDetailsModal timeline 5 etapes |
| Reservations | `s-resa-retournee` | Controle retour sans mode inventaire detaille (scan/qt prevu/reel) | Coeur du module depart/retour incomplet | P0 | Fait (maquette) |
| Reservations | `s-resa-terminee` | Archive sans verrou fort lecture seule + piste d'audit | Tracabilite faible | P1 | Fait (2026-02-24) — status=completed = readonly dans EventDetailsModal |
| Evenements | `s-events-list` | Liste uniquement, pas de vrai calendrier semaine/mois | Ecart avec module planning du devis | P0 | Fait (maquette) |
| Evenements | `s-event-prevu` | Pas d'affectation equipe/vehicule/ressources | Pilotage operationnel partiel | P1 | Fait (maquette) |
| Evenements | `s-event-en-cours` | Incident non normalise (severity/SLA/proprietaire) | Traitement incident fragile | P1 | Fait (2026-02-24) — EvenementDetailPage SLA+severity+owner |
| Evenements | `s-event-retourne` | Casse non reliee explicitement a facturation | Lien finance incomplet | P1 | Fait (maquette) |
| Ventes | `s-ventes` | Pas de recherche/tri/periodisation (jour, semaine, mois) | Lecture business limitee | P1 | Fait (2026-02-24) — VentesListPage search+status+date |
| Ventes | `s-vente-acompte`, `s-vente-retard` | Pas de scenario multi-moyens sur un meme dossier | Ecart avec suivi paiements devis | P1 | Fait (maquette) |
| Ventes | `s-vente-solde` | Pas de rapprochement automatique facture/paiement | Controle comptable incomplet | P1 | Fait (2026-02-24) — RapprochementPage paiement inline |
| Stock | `s-stock` | Pas de vue "historique mouvements complet" (filtres type/date/article) | Exigence devis non couverte | P0 | Fait (maquette) |
| Stock | `s-stock-item` | Pas d'etat detaille "endommage" / "en reparation" | Etats stock incomplets vs devis | P0 | Fait (maquette) |
| Stock | `s-stock-reassort` | Pas de cycle commande complet (commande, reception partielle, reliquat) | Reassort simplifie | P1 | Fait (2026-02-24) — SuppliersPage + SupplierOrdersPage complets |
| Factures | `s-factures` | Pas de numerotation/fuite de sequence visible | Governance facturation faible | P1 | Fait (2026-02-24) — InvoicesPage bandeau trous de sequence |
| Factures | `s-facture-detail`, `s-facture-retard` | Pas de timeline audit (envoi, ouverture, relances, actions) | Tracabilite legale/metier limitee | P1 | Fait (maquette) |
| Factures | `s-facture-create` | Pas de gestion TVA/profil fiscal detaille | Limite de realisme metier | P1 | Fait (2026-02-24) — TvaReportPage + taux TVA par ligne produit |
| Devis | `s-devis-list`, `s-devis-detail` | Pas de scenario devis expire + renouvellement validite | Cycle devis incomplet | P1 | Fait (maquette) |
| Devis | `s-devis-detail` | Pas de versionning devis (v1/v2/v3 diff) | Perte de lisibilite commerciale | P2 | Fait (maquette) |

## 2) Manques Hors Existant (Modules Du Devis Pas Encore Ecranes)

| Module Devis | Etat Dans LAYER | Priorite |
|---|---|---|
| Catalogue produits (categories, attributs, images, bundles) | Non demarre | P0 |
| Gestion clients (fiches + historique) | Non demarre | P0 |
| Stats/KPI avancees (CA, panier moyen, saisonnalite, top produits) | Non demarre | P1 |
| Analyse clients RFM | Non demarre | P2 |
| Auth securisee / MFA / sessions | Non demarre | P1 |
| Utilisateurs & roles | Non demarre | P1 |
| Import donnees CSV/Excel | Non demarre | P1 |

## 3) Ordre Recommande (Un Par Un)

1. Depart/retour operationnel complet (`P0`): blocage depart, inventaire retour detaille, lien casse -> facture. `Etat: fait (maquette)`
2. Planning calendrier (`P0`): semaine/mois avec navigation par date + affectation equipe/vehicule. `Etat: fait (maquette)`
3. Stock historique complet + etats endommage/reparation (`P0`). `Etat: fait (maquette)`
4. Ventes/factures: multi-moyens + timeline audit (`P1`). `Etat: fait (maquette)`
5. Devis: expiration + versionning (`P1/P2`). `Etat: fait (maquette)`
6. Puis modules non demarres (catalogue, clients, stats, auth, import).

## 4) Definition De Fait Pour Chaque Gap

- Ecran(s) scenario ajoutes
- Actions boutons et modales connectees
- Mapping `NAV_GROUP_BY_SCREEN` mis a jour
- Filtre(s) operationnels si liste
- Verification: aucune cible manquante `go/openModal/closeModal`
- Verification: aucun `id` duplique
- Verification: parse HTML OK

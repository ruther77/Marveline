# Arborescence LAYER.html — Marveline

> Maquette interactive : `docs/LAYER.html`
> Navigation JS : `go('s-xxx')` pour un écran, `openModal('m-xxx')` pour un modal
> Total : **108 écrans** (`s-*`) · **86 modals** (`m-*`)

---

## Navigation principale (bottom nav)

| ID | Titre |
|----|-------|
| `s-home` | Accueil / Dashboard |
| `s-planning-mois` | Planning · Mois |
| `s-reservations` | Réservations |
| `s-catalogue-picker` | Catalogue (picker) |
| `s-plus` | Menu Plus |

---

## 📋 Réservations

### Création
| ID | Titre |
|----|-------|
| `s-resa-create` | Nouvelle réservation |
| `s-client-edit` | Modifier le client |

### États de réservation
| ID | Titre |
|----|-------|
| `s-resa-brouillon` | Réservation · Brouillon |
| `s-resa-brouillon-incomplet` | Réservation · Brouillon incomplet |
| `s-resa-confirmee-sans-caution` | Réservation · Confirmée (sans caution) |
| `s-resa-confirmee-avec-caution` | Réservation · Confirmée (avec caution) |
| `s-resa-confirmee-risque` | Réservation · Risque |
| `s-resa-confirmee-prete` | Réservation · Prête départ |
| `s-resa-precheck-legal` | Réservation · Pré-check légal |
| `s-resa-en-cours` | Réservation · En cours |
| `s-resa-en-cours-prolongee` | Réservation · Prolongée |
| `s-resa-retournee` | Réservation · Retournée |
| `s-resa-retournee-litige` | Réservation · Litige |
| `s-resa-terminee` | Réservation · Terminée |
| `s-resa-terminee-archive` | Réservation · Archive |
| `s-resa-annulee` | Réservation · Annulée |

### Listes
| ID | Titre |
|----|-------|
| `s-reservations-list` | Réservations (liste) |

### Modals réservation
| ID | Action |
|----|--------|
| `m-creer-resa` | Créer une réservation |
| `m-confirmer-resa` | Confirmer la réservation |
| `m-modifier-resa` | Modifier la réservation |
| `m-supprimer-resa` | Supprimer la réservation |
| `m-archiver-resa` | Archiver la réservation |
| `m-prolonger-resa` | Prolonger la réservation |
| `m-clore-litige-resa` | Clore le litige |
| `m-encaisser-caution` | Encaisser la caution |
| `m-relancer-caution` | Relancer la caution |
| `m-ajouter-produit` | Ajouter un produit |
| `m-supprimer-produit` | Supprimer un produit |
| `m-frais-supp` | Frais supplémentaires |
| `m-filter-reservations` | Filtrer les réservations |

---

## 📅 Planning / Événements

### Planning
| ID | Titre |
|----|-------|
| `s-planning-jour` | Planning · Jour |
| `s-planning-semaine` | Planning · Semaine |
| `s-planning-mois` | Planning · Mois |
| `s-planning-affectation` | Planning · Affectations |

### Liste événements
| ID | Titre |
|----|-------|
| `s-events-list` | Événements |

### États d'événement
| ID | Titre |
|----|-------|
| `s-event-prevu` | Événement · Prévu |
| `s-event-prevu-risque` | Événement · Risque départ |
| `s-event-en-cours` | Événement · En cours |
| `s-event-en-cours-incident` | Événement · Incident |
| `s-event-action-plan` | Plan d'action |
| `s-event-retourne` | Événement · Retourné |
| `s-event-retourne-casse` | Événement · Casse |
| `s-event-termine` | Événement · Terminé |
| `s-event-annule` | Événement · Annulé |

### Modals événement
| ID | Action |
|----|--------|
| `m-creer-event` | Créer un événement |
| `m-modifier-event` | Modifier l'événement |
| `m-annuler-event` | Annuler l'événement |
| `m-reprogrammer-event` | Reprogrammer l'événement |
| `m-affecter-ressources` | Affecter des ressources |
| `m-cloturer-event` | Clôturer l'événement |
| `m-plan-action-incident` | Plan d'action incident |
| `m-remboursement-event` | Remboursement événement |
| `m-rapport-event` | Rapport événement |

---

## 🚚 Logistique — Départ / Retour

### Écrans
| ID | Titre |
|----|-------|
| `s-depart-from-resa` | Préparer le départ |
| `s-depart-bloque` | Départ · Bloqué |
| `s-depart-inventaire` | Inventaire de sortie |
| `s-retour-inventaire` | Inventaire de retour |
| `s-dommage-declare` | Déclarer un dommage |
| `s-check-article` | Vérifier l'article *(titre dynamique)* |

### Modals logistique
| ID | Action |
|----|--------|
| `m-valider-depart` | Valider le départ |
| `m-bloquer-depart` | Bloquer le départ |
| `m-valider-inventaire-sortie` | Valider inventaire sortie |
| `m-valider-inventaire-retour` | Valider inventaire retour |
| `m-verifier-retour-produit` | Vérifier retour produit |
| `m-declarer-casse` | Déclarer une casse |
| `m-facturer-casse` | Facturer la casse |
| `m-cloturer-retour` | Clôturer le retour |
| `m-photo-depart` | Photo départ |

---

## 📦 Catalogue

### Navigation catalogue
| ID | Titre |
|----|-------|
| `s-catalogue-picker` | Choisir un produit |
| `s-catalogue-categorie` | Catalogue · Catégorie |
| `s-catalogue-produit` | Fiche produit |
| `s-catalogue-photos` | Galerie produit |
| `s-catalogue-packs` | Catalogue · Packs |
| `s-catalogue-variantes` | Produit · Variantes |
| `s-catalogue-etats` | Produit · États matériel |
| `s-catalogue-disponibilite` | Produit · Disponibilité |
| `s-catalogue-collections` | Catalogue · Collections |
| `s-catalogue-builder` | Catalogue · Builder pack |
| `s-catalogue-comparateur` | Catalogue · Comparateur |

### Outils catalogue
| ID | Titre |
|----|-------|
| `s-catalogue-outils` | Catalogue · Options avancées |
| `s-catalogue-outils-produit` | Options · Produit |
| `s-catalogue-outils-media` | Options · Médias |
| `s-catalogue-outils-pilotage` | Options · Pilotage |
| `s-catalogue-recherche` | Catalogue · Recherche avancée |
| `s-catalogue-upload` | Catalogue · Upload photo |
| `s-catalogue-qr` | Catalogue · QR produit |
| `s-catalogue-audit` | Catalogue · Audit produit |
| `s-catalogue-fournisseurs` | Catalogue · Fournisseurs |

---

## 🗃️ Stock

### Écrans stock
| ID | Titre |
|----|-------|
| `s-stock` | Stock |
| `s-stock-item-detail` | Article · Détail unité |
| `s-stock-faible` | Stock · Faible |
| `s-stock-reassort` | Stock · Réassort |
| `s-stock-resolu` | Stock · Résolu |
| `s-stock-historique` | Stock · Historique |
| `s-stock-etats` | Stock · États article |

### Modals stock
| ID | Action |
|----|--------|
| `m-ajuster-stock` | Ajuster le stock |
| `m-lancer-reassort` | Lancer le réassort |
| `m-reception-reassort` | Réception réassort |
| `m-contact-fournisseur` | Contacter le fournisseur |
| `m-cloturer-reassort` | Clôturer le réassort |
| `m-filter-stock` | Filtrer le stock |

---

## 💰 Ventes

### Écrans ventes
| ID | Titre |
|----|-------|
| `s-ventes` | Ventes |
| `s-vente-brouillon` | Vente · Brouillon |
| `s-vente-acompte` | Vente · Acompte |
| `s-vente-multi` | Vente · Multi-moyens |
| `s-vente-solde` | Vente · Soldée |
| `s-vente-retard` | Vente · Retard |

### Modals ventes
| ID | Action |
|----|--------|
| `m-encaisser-solde` | Encaisser le solde |
| `m-ajouter-paiement-multi` | Ajouter un paiement |
| `m-relancer-vente` | Relancer la vente |

---

## 🧾 Factures

### Écrans factures
| ID | Titre |
|----|-------|
| `s-factures` | Factures |
| `s-facture-create` | Nouvelle facture |
| `s-facture-detail` | Détail facture |
| `s-facture-brouillon` | Facture · Brouillon |
| `s-facture-emise` | Facture · Émise |
| `s-facture-retard` | Facture · Retard |
| `s-facture-payee` | Facture · Payée |
| `s-facture-casse` | Facture · Dommages |
| `s-facture-audit` | Facture · Audit |
| `s-facture-avoir` | Avoir · Note de crédit |

### Modals factures
| ID | Action |
|----|--------|
| `m-marquer-payee` | Marquer payée |
| `m-relancer-facture` | Relancer la facture |
| `m-avoir-facture` | Créer un avoir |
| `m-supprimer-facture` | Supprimer la facture |
| `m-recu-paiement` | Reçu de paiement |
| `m-ajouter-ligne-facture` | Ajouter une ligne |
| `m-facture-brouillon` | Passer en brouillon |
| `m-envoyer-facture` | Envoyer la facture |
| `m-export-factures` | Exporter les factures |
| `m-pdf-document` | Aperçu PDF |

---

## 📄 Devis

### Écrans devis
| ID | Titre |
|----|-------|
| `s-devis-list` | Devis |
| `s-devis-create` | Nouveau devis |
| `s-devis-detail` | Détail devis |
| `s-devis-brouillon` | Devis · Brouillon |
| `s-devis-expire` | Devis · Expiré |
| `s-devis-refuse` | Devis · Refusé |
| `s-devis-source` | Devis développement |
| `s-devis-couverture` | Devis · Couverture |
| `s-devis-change-request` | Hors devis · Change Requests |
| `s-devis-phases` | Devis · Phases projet |
| `s-ligne-edit` | Modifier la ligne |

### Modules devis (configurateur)
| ID | Titre |
|----|-------|
| `s-devis-module-socle` | Module · Socle |
| `s-devis-module-stock` | Module · Stock |
| `s-devis-module-facturation` | Module · Facturation |
| `s-devis-module-securite` | Module · Sécurité |
| `s-devis-module-services` | Module · Services |

### Modals devis
| ID | Action |
|----|--------|
| `m-creer-devis` | Créer un devis |
| `m-envoyer-devis` | Envoyer le devis |
| `m-accepter-devis` | Accepter le devis |
| `m-refuser-devis` | Refuser le devis |
| `m-devis-refuse` | Confirmer refus |
| `m-dupliquer-devis` | Dupliquer le devis |
| `m-renouveler-devis` | Renouveler le devis |
| `m-versionner-devis` | Créer une version |
| `m-ajouter-ligne-devis` | Ajouter une ligne |
| `m-modifier-ligne-devis` | Modifier la ligne |
| `m-export-devis` | Exporter le devis |
| `m-import-devis` | Importer un devis |
| `m-pdf-devis` | Aperçu PDF devis |

---

## 👥 Clients

### Écrans clients
| ID | Titre |
|----|-------|
| `s-clients-list` | Clients |
| `s-client-detail` | Fiche client *(titre dynamique)* |
| `s-client-nouveau` | Nouveau client |
| `s-client-relance` | Client · À relancer |

### Modals clients
| ID | Action |
|----|--------|
| `m-modifier-client` | Modifier le client |
| `m-supprimer-client` | Supprimer le client |
| `m-relancer-client` | Relancer le client |
| `m-filter-clients` | Filtrer les clients |
| `m-date-range` | Sélection période |

---

## 💹 Finances

| ID | Titre |
|----|-------|
| `s-finances` | Finances |

---

## 🔍 Transversal

| ID | Titre |
|----|-------|
| `s-recherche-globale` | Recherche globale |

---

## 👤 Profil

### Écrans
| ID | Titre |
|----|-------|
| `s-profil` | Mon profil |
| `s-parametres` | Paramètres |
| `s-notifications` | Notifications |

### Modals profil
| ID | Action |
|----|--------|
| `m-profil-nom` | Modifier le nom |
| `m-profil-email` | Modifier l'email |
| `m-profil-mdp` | Changer le mot de passe |
| `m-profil-theme` | Changer le thème |
| `m-profil-deconnexion` | Se déconnecter |
| `m-param-color` | Couleur paramètre |
| `m-param-edit` | Éditer un paramètre |
| `m-param-text` | Éditer texte paramètre |
| `m-notif-detail` | Détail notification |
| `m-changer-photo` | Changer la photo |

---

## ⚙️ Administration

### Écrans admin
| ID | Titre |
|----|-------|
| `s-admin-utilisateurs` | Utilisateurs |
| `s-admin-audit` | Journal d'audit |
| `s-admin-apikeys` | Clés API |
| `s-admin-parametres` | Admin · Système |

### Modals admin
| ID | Action |
|----|--------|
| `m-admin-user` | Fiche utilisateur |
| `m-admin-inviter` | Inviter un utilisateur |
| `m-audit-detail` | Détail événement audit |
| `m-audit-export` | Exporter les logs |
| `m-apikey-detail` | Détail / actions clé API |
| `m-apikey-create` | Créer une clé API |
| `m-apikey-new-reveal` | Révéler la clé créée |

---

## 🔧 Modals système (génériques)

| ID | Usage |
|----|-------|
| `m-sys-confirm` | Confirmation générique |
| `m-sys-danger` | Action destructive |
| `m-sys-param` | Paramètre système |
| `m-sys-text` | Saisie texte générique |

---

## Récapitulatif

| Section | Écrans | Modals |
|---------|--------|--------|
| Réservations | 16 | 13 |
| Planning / Événements | 13 | 9 |
| Logistique | 6 | 9 |
| Catalogue | 19 | — |
| Stock | 7 | 6 |
| Ventes | 5 | 3 |
| Factures | 10 | 10 |
| Devis | 13 | 13 |
| Clients | 4 | 5 |
| Finances | 1 | — |
| Transversal | 1 | — |
| Profil / Paramètres | 3 | 10 |
| Administration | 4 | 7 |
| Modals système | — | 4 |
| Navigation | 5 | — |
| **Total** | **108** | **86** |

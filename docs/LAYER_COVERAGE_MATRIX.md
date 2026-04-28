# Matrice de couverture LAYER.html ↔ Frontend
# Date : 2026-02-25 | Audit de fidélité contenu — révision approfondie post-comparaison réelle

> **Source LAYER** : `docs/LAYER.html` — 132 écrans `s-*`, 100 modals `m-*`
> **Source frontend** : `frontend/src/pages/` + `frontend/src/routes/_app/`
> **Légende** : ✅ fidèle au LAYER | ⚠️ partiel (sections UI significatives absentes) | ❌ absent ou manque fonctionnel majeur
>
> **Méthode** : Lecture directe LAYER.html bloc par bloc + lecture page frontend. Route existante ≠ contenu fidèle.

---

## 1. Administration

| ID LAYER | Titre | Route | Page | Statut |
|----------|-------|-------|------|--------|
| `s-admin-apikeys` | Clés API | `/admin/api-keys` | `ApiKeysPage.tsx` | ✅ |
| `s-admin-audit` | Journal d'audit | `/admin/audit-logs` | `AuditLogsPage.tsx` | ✅ |
| `s-admin-parametres` | Admin · Système | `/admin/settings` | `AdminSettingsPage.tsx` | ✅ |
| `s-admin-utilisateurs` | Utilisateurs | `/admin/users` | `UsersPage.tsx` | ✅ |

---

## 2. Catalogue / Produits

| ID LAYER | Titre | Route | Page | Statut |
|----------|-------|-------|------|--------|
| `s-catalogue` | Liste produits | `/products` | `ProductsPage.tsx` | ✅ |
| `s-catalogue-audit` | Audit produit | `/products/$id/audit` | `ProductAuditPage.tsx` | ✅ |
| `s-catalogue-builder` | Builder pack | `/catalogue/builder` | `CatalogueBuilderPage.tsx` | ✅ |
| `s-catalogue-categorie` | Catégories | `/products/categories` | `CategoriesPage.tsx` | ✅ |
| `s-catalogue-collections` | Collections | `/products/collections` | `CollectionsPage.tsx` | ✅ |
| `s-catalogue-comparateur` | Comparateur | `/products/comparateur` | `ComparateurPage.tsx` | ✅ |
| `s-catalogue-disponibilite` | Disponibilité | `/products/availability` | `CatalogueAvailabilityPage.tsx` | ✅ |
| `s-catalogue-etats` | États matériel | `/products/$id/states` | `ProductStatesPage.tsx` | ✅ |
| `s-catalogue-fournisseurs` | Fournisseurs | `/products/suppliers` | `SuppliersPage.tsx` | ✅ |
| `s-catalogue-outils` | Options avancées | `/products/tools` | `ProductToolsPage.tsx` | ✅ |
| `s-catalogue-outils-media` | Options · Médias | `/products/media` | `MediaPage.tsx` | ✅ |
| `s-catalogue-outils-pilotage` | Options · Pilotage | `/products/pilotage` | `CataloguePilotagePage.tsx` | ✅ |
| `s-catalogue-outils-produit` | Options · Produit | `/products/$id/editor` | `ProductEditorPage.tsx` | ✅ |
| `s-catalogue-packs` | Packs / Formules | `/products/bundles` | `BundlesPage.tsx` | ✅ |
| `s-catalogue-photos` | Galerie produit | `/products/$id/photos` | `ProductPhotosPage.tsx` | ✅ |
| `s-catalogue-picker` | Choisir un produit | composant modal | `CataloguePickerModal.tsx` | ✅ |
| `s-catalogue-produit` | Fiche produit | `/products/$id` | layout `$id.tsx` sans page index fiche publique | ⚠️ |
| `s-catalogue-qr` | QR produit | `/products/qr` | `CatalogueQRPage.tsx` | ✅ |
| `s-catalogue-recherche` | Recherche avancée | `/search` | `SearchPage.tsx` | ✅ |
| `s-catalogue-upload` | Upload photo | `/products/import` | `ProductImportPage.tsx` | ✅ |
| `s-catalogue-variantes` | Variantes | `/products/$id/variants` | `ProductVariantsPage.tsx` | ✅ |
| `s-maintenance-produit` | Maintenance | `/products/$id/maintenance` | `MaintenancePage.tsx` | ✅ |

---

## 3. Clients

| ID LAYER | Titre | Route | Page | Statut | Écart |
|----------|-------|-------|------|--------|-------|
| `s-clients-list` | Liste clients | `/customers` | `CustomersPage.tsx` | ✅ | — |
| `s-client-detail` | Fiche client | `/customers/$id` | `CustomerDetailPage.tsx` | ⚠️ | Note interne absente ; btn "Nouvelle réservation" + "Envoyer un message" absents ; quick links (Factures/Devis/Réservations) intégrés en sections vs liens haut de page |
| `s-client-nouveau` | Nouveau client | modal | `CustomerFormModal.tsx` | ⚠️ | Note interne absente ; types = 2 (Particulier/Entreprise) vs 4 LAYER (Particulier/Professionnel/Association/Comité des fêtes) |
| `s-client-edit` | Modifier client | modal | `CustomerFormModal.tsx` | ⚠️ | Mêmes écarts que `s-client-nouveau` |
| `s-client-relance` | À relancer | `/customers/relances` | `ClientsRelancesPage.tsx` | ✅ | — |
| `s-clients-rfm` | Analyse RFM | `/customers/rfm` | `ClientsRFMPage.tsx` | ✅ | Bouton "Lancer campagne" absent (mineur) |

---

## 4. Devis

| ID LAYER | Titre | Route | Page | Statut | Écart |
|----------|-------|-------|------|--------|-------|
| `s-devis-list` | Liste devis | `/devis` | `DevisListPage.tsx` | ⚠️ | `info-grid` 4 KPIs (Total/Acceptés/En attente/Expirés) absent en haut de page |
| `s-devis-create` | Nouveau devis | `/devis/new` | `DevisCreatePage.tsx` | ✅ | — |
| `s-devis-detail` | Détail devis | `/devis/$id` | `DevisDetailPage.tsx` | ⚠️ | `detail-hero` avec barre progression absente ; `workflow-strip` 3 étapes absent ; `focus-strip` 4 pills KPIs absent ; quick links (Couverture/CR/Phases/PDF) absents |
| `s-devis-brouillon` | Brouillon | état dans `DevisDetailPage` | — | ✅ | — |
| `s-devis-expire` | Expiré | état dans `DevisDetailPage` | — | ✅ | — |
| `s-devis-refuse` | Refusé | `DevisRefuseModal` | — | ⚠️ | LAYER prévoit écran complet `s-devis-refuse` avec hero rouge, focus-strip, liste lignes refusées, btns Dupliquer/Relancer → implémentation = modal simple |
| `s-devis-module-socle` | Module Socle | `/devis/$id/modules` | `DevisModulesPage.tsx` | ✅ | — |
| `s-devis-module-stock` | Module Stock | `/devis/$id/modules` | `DevisModulesPage.tsx` | ✅ | — |
| `s-devis-module-facturation` | Module Facturation | `/devis/$id/modules` | `DevisModulesPage.tsx` | ✅ | — |
| `s-devis-module-securite` | Module Sécurité | `/devis/$id/modules` | `DevisModulesPage.tsx` | ✅ | — |
| `s-devis-module-services` | Module Services | `/devis/$id/modules` | `DevisModulesPage.tsx` | ✅ | — |
| `s-devis-phases` | Phases projet | `/devis/$id/phases` | `DevisPhasesPage.tsx` | ✅ | — |
| `s-devis-couverture` | Couverture | `/devis/$id/couverture` | `DevisCouverturePage.tsx` | ⚠️ | Filtres pills (Tout/Livré/En cours/À cadrer) absents ; onglets navigation absents |
| `s-devis-change-request` | Change Requests | `/devis/$id/change-requests` | `DevisChangeRequestPage.tsx` | ⚠️ | Filtres pills (Tout/À chiffrer/Validé/Refusé) absents |
| `s-devis-source` | Devis source | `/devis/$id/source` | `DevisSourcePage.tsx` | ⚠️ | Boutons raccourcis (Couverture/CR/Phases) absents ; info box contexte absente ; grille TVA (HT/TVA/TTC/Phases) absente |
| `s-ligne-edit` | Modifier ligne | composant `DevisLineEditor` | — | ✅ | — |

---

## 5. Événements terrain

| ID LAYER | Titre | Route | Page | Statut |
|----------|-------|-------|------|--------|
| `s-events-list` | Liste événements | `/evenements` | `EvenementsListPage.tsx` | ✅ |
| `s-event-prevu` | Prévu | état/filtre | — | ✅ |
| `s-event-prevu-risque` | Risque départ | état/filtre | — | ✅ |
| `s-event-en-cours` | En cours | `/evenements/$id` | `EvenementDetailPage.tsx` | ✅ |
| `s-event-en-cours-incident` | Incident | modal `DeclareIncidentModal` | — | ✅ |
| `s-event-action-plan` | Plan d'action | modal `CreateActionPlanModal` | — | ✅ |
| `s-event-retourne` | Retourné | modal `MarkReturnedModal` + état | — | ✅ |
| `s-event-retourne-casse` | Casse | état/filtre | — | ✅ |
| `s-event-termine` | Terminé | état/filtre | — | ✅ |
| `s-event-annule` | Annulé | état/filtre | — | ✅ |

---

## 6. Factures & Avoirs

| ID LAYER | Titre | Route | Page | Statut | Écart |
|----------|-------|-------|------|--------|-------|
| `s-factures` | Liste factures | `/invoices` | `InvoicesPage.tsx` | ✅ | — |
| `s-facture-create` | Nouvelle facture | `/invoices/new` | `InvoiceCreatePage.tsx` | ⚠️ | Champ "Objet" absent ; lignes de facture éditables absentes (liste statique) ; bouton "Importer devis" absent |
| `s-facture-detail` | Détail facture | modal `InvoiceDetailModal` | — | ✅ | — |
| `s-facture-brouillon` | Brouillon | état/filtre dans `InvoicesPage` | — | ✅ | — |
| `s-facture-emise` | Émise | état/filtre dans `InvoicesPage` | — | ✅ | — |
| `s-facture-envoi` | Envoi facture | `InvoiceSendModal` + `InvoiceMarkSentModal` | — | ⚠️ | Preview PDF miniature intégrée absente |
| `s-facture-retard` | Retard | état/filtre dans `InvoicesPage` | — | ✅ | — |
| `s-facture-payee` | Payée | état/filtre dans `InvoicesPage` | — | ✅ | — |
| `s-facture-casse` | Dommages | état/filtre dans `InvoicesPage` | — | ✅ | — |
| `s-facture-audit` | Audit facture | `/invoices/$id/audit` | `InvoiceAuditPage.tsx` | ⚠️ | Filtres d'audit (Tout/Envoi/Ouverture/Relances/Paiements/Actions internes) absents |
| `s-facture-avoir` | Avoir / Note crédit | `/invoices/$id/avoir` | `AvoirsPage.tsx` | ⚠️ | Boutons "Rembourser maintenant" et "Imputer sur prochaine facture" absents |
| `s-caution-suivi` | Suivi cautions | `/invoices/cautions` | `CautionsPage.tsx` | ✅ | — |
| `s-rapport-mensuel` | Rapport mensuel | `/invoices/rapport-mensuel` | `RapportMensuelPage.tsx` | ⚠️ | Notation clients avec étoiles absente ; top produits loués absent ; avis clients récents absents ; bouton export PDF absent |
| `s-paiement-nouveau` | Enregistrer paiement | `InvoicePaymentForm` inline | — | ⚠️ | Récap facture (total/déjà payé/reste) absent ; grille visuelle 6 modes paiement (💳CB/🏦Virement/📝Chèque/💵Espèces/📱Lydia/⋯Autre) absente → select texte uniquement |

---

## 7. Finances & Dashboard

| ID LAYER | Titre | Route | Page | Statut |
|----------|-------|-------|------|--------|
| `s-home` | Accueil / Dashboard | `/dashboard` | `DashboardPage.tsx` | ✅ |
| `s-finances` | Finances | `/finances` | `FinancesPage.tsx` | ✅ |
| `s-notifications` | Notifications | `/notifications` | `NotificationsPage.tsx` | ✅ |
| `s-recherche-globale` | Recherche globale | `/search` | `SearchPage.tsx` | ✅ |

---

## 8. Opérations terrain (départ / retour)

| ID LAYER | Titre | Route | Page | Statut | Écart |
|----------|-------|-------|------|--------|-------|
| `s-scan-qr` | Scanner QR | `/operations/scan` | `ScanPage.tsx` | ⚠️ | Viewfinder QR élaboré (grid overlay, coins, laser rouge) absent ; "Scans récents" absent ; modal résultat scan absent ; modal saisie manuelle absent ; bouton Flash absent |
| `s-depart-from-resa` | Préparer le départ | `/operations/departure/$id` | `DepartureInventoryPage.tsx` | ⚠️ | Hero orange (`detail-hero h-orange`) absent ; alerte "Caution OK" verte absente ; lien "Vérifier article par article →" absent ; bouton Photo absent ; bouton "Contrôle légal pré-départ" absent |
| `s-depart-bloque` | Départ bloqué | `/operations/departure-blocked/$id` | `DepartureBlockedPage.tsx` | ⚠️ | Montants EUR absents (texte "Non encaissée"/"Non reçu" au lieu de "49,50 EUR non encaissée") ; boutons sans action fonctionnelle |
| `s-retour-inventaire` | Inventaire de retour | `/operations/return/$id` | `ReturnInventoryPage.tsx` | ⚠️ | Chip "Contrôle" orange absent ; bouton "Lier à une facture" → `s-facture-casse` absent |
| `s-dommage-declare` | Déclarer dommage (retour) | `/operations/return-damage/$id` | `DamageDeclareFullPage.tsx` | ⚠️ | Prix unitaire absent dans section "Écart détecté" ; section caution totale/restitution estimée absente (LAYER : "Caution encaissée 49,50€ / Retenue −0€ / Restitution estimée 49,50€") |
| `s-signature-contrat` | Signature contrat | `/events/signature/$id` | `SignaturePage.tsx` | ✅ | — |
| `s-depart-inventaire` | Inventaire de sortie | vue dans `DepartureInventoryPage` | — | ⚠️ | Navigation stepper "article par article →" absente ; liste avec selects seulement |
| `s-check-article` | Vérifier article | `/operations/departure-check/$id` | `ArticleCheckPage.tsx` | ⚠️ | Pastilles emoji (🍷/🪑/🍽) au lieu de barres colorées dans la progression article (écart mineur) |
| `s-casse-declaration` | Déclarer casse | modal simplifié | — | ⚠️ | Photos (upload 2/5 max) et section "Impact sur la caution" absentes |

---

## 9. Planning

| ID LAYER | Titre | Route | Page | Statut |
|----------|-------|-------|------|--------|
| `s-planning-jour` | Jour | `/planning/day` | `PlanningDayPage.tsx` | ✅ |
| `s-planning-semaine` | Semaine | `/planning/week` | `PlanningWeekPage.tsx` | ✅ |
| `s-planning-mois` | Mois | `/planning/month` | `PlanningMonthPage.tsx` | ✅ |
| `s-planning-affectation` | Affectations | `/planning/affectation` | `PlanningAffectationPage.tsx` | ✅ |
| `s-planning-ressources` | Ressources | `/planning/resources` | `PlanningResourcesPage.tsx` | ✅ |

---

## 10. Profil & Paramètres

| ID LAYER | Titre | Route | Page | Statut |
|----------|-------|-------|------|--------|
| `s-profil` | Mon profil | `/profile` | `ProfilePage.tsx` | ✅ |
| `s-parametres` | Paramètres | `/admin/settings` ou `/profile/security` | `AdminSettingsPage` / `SecurityPage` | ✅ |
| `s-plus` | Menu Plus | `/more` | `MorePage.tsx` | ✅ |
| `s-login` | Connexion | `/login` | `LoginPage.tsx` | ✅ |

---

## 11. Réservations

| ID LAYER | Titre | Route | Page | Statut | Écart |
|----------|-------|-------|------|--------|-------|
| `s-reservations` | Réservations (liste) | `/events` | `EventsPage.tsx` | ⚠️ | KPIs chips en haut de page absents (LAYER : "En cours / Cette semaine / Litige / Prêtes" pills) |
| `s-reservations-list` | Liste réservations | `/events` | `EventsPage.tsx` | ⚠️ | Idem `s-reservations` |
| `s-resa-create` | Nouvelle réservation | `/events/new` | `ReservationCreatePage.tsx` | ✅ | — |
| `s-resa-nouvelle` | Nouvelle réservation | `/events/new` | `ReservationCreatePage.tsx` | ✅ | — |
| `s-resa-nouvelle-lignes` | Lignes réservation | `/events/$id/lines` | `ReservationLinesPage.tsx` | ✅ | — |
| `s-resa-detail` | Détail réservation | modal `EventDetailsModal` | — | ✅ | — |
| `s-resa-brouillon` | Brouillon | état dans `EventsPage` | — | ✅ | — |
| `s-resa-brouillon-incomplet` | Brouillon incomplet | état dans `EventsPage` | — | ✅ | — |
| `s-resa-confirmee-sans-caution` | Confirmée sans caution | état dans `EventsPage` | — | ✅ | — |
| `s-resa-confirmee-avec-caution` | Confirmée avec caution | état dans `EventsPage` | — | ✅ | — |
| `s-resa-confirmee-risque` | Risque | état dans `EventsPage` | — | ✅ | — |
| `s-resa-confirmee-prete` | Prête départ | état dans `EventsPage` | — | ✅ | — |
| `s-resa-precheck-legal` | Pré-check légal | état/modal dans `EventDetailsModal` | — | ✅ | — |
| `s-resa-en-cours` | En cours | état dans `EventsPage` | — | ✅ | — |
| `s-resa-en-cours-prolongee` | Prolongée | état dans `EventsPage` | — | ✅ | — |
| `s-resa-retournee` | Retournée | état dans `EventsPage` | — | ✅ | — |
| `s-resa-retournee-litige` | Litige | état dans `EventsPage` | — | ✅ | — |
| `s-resa-terminee` | Terminée | état dans `EventsPage` | — | ✅ | — |
| `s-resa-terminee-archive` | Archive | état dans `EventsPage` | — | ✅ | — |
| `s-resa-annulee` | Annulée | état dans `EventsPage` | — | ✅ | — |

---

## 12. Stock & Inventaire

| ID LAYER | Titre | Route | Page | Statut | Écart |
|----------|-------|-------|------|--------|-------|
| `s-stock` | Stock | `/inventory/stock` | `InventoryPage.tsx` | ⚠️ | Filtres pills par catégorie (Verres/Mobilier/Vaisselle) absents ; boutons rapides (Réassorts/Historique/États) absents |
| `s-stock-item-detail` | Détail unité | `/inventory/stock/$id` | `StockItemDetailPage.tsx` | ✅ | — |
| `s-stock-historique` | Historique mouvements | `/inventory/movements` | `MovementsPage.tsx` | ✅ | — |
| `s-stock-reassort` | Réassort | `/inventory/reorder` | `StockReorderPage.tsx` | ✅ | — |
| `s-ajustement-stock` | Ajustement stock | `/inventory/adjustments` | `StockAdjustmentsPage.tsx` | ✅ | — |
| `s-inventaire-physique` | Inventaire physique | `/inventory/inventaire` | `PhysicalInventoryPage.tsx` | ✅ | — |
| `s-stock-etats` | États article | `/products/$id/states` | `ProductStatesPage.tsx` | ⚠️ | Sous `products/`, pas `inventory/` — accès indirect |
| `s-stock-critique` | Stock critique | `/inventory/stock-alert/$id?level=critical` | `StockAlertPage.tsx` | ✅ | — |
| `s-stock-faible` | Stock faible | `/inventory/stock-alert/$id?level=low` | `StockAlertPage.tsx` | ✅ | — |
| `s-stock-resolu` | Rupture résolue | état dans `StockReorderPage` | — | ⚠️ | Pas de vue dédiée post-réassort avec confirmation de résolution |

---

## 13. Tarification & Relances

| ID LAYER | Titre | Route | Page | Statut |
|----------|-------|-------|------|--------|
| `s-tarification` | Tarification | `/tarification` | `TarificationPage.tsx` | ✅ |
| `s-relances-planifiees` | Relances planifiées | `/relances` | `RelancesPlanifieesPage.tsx` | ✅ |

---

## 14. Ventes

| ID LAYER | Titre | Route | Page | Statut | Écart |
|----------|-------|-------|------|--------|-------|
| `s-ventes` | Liste ventes | `/ventes` | `VentesListPage.tsx` | ✅ | — |
| `s-vente-brouillon` | Brouillon | `/ventes/$id` | `VenteDetailPage.tsx` | ✅ | — |
| `s-vente-acompte` | Acompte | `/ventes/$id` | `VenteDetailPage.tsx` | ✅ | — |
| `s-vente-multi` | Multi-moyens | `/ventes/$id` + modal paiement | — | ✅ | — |
| `s-vente-retard` | Retard | `/ventes/$id` | `VenteDetailPage.tsx` | ✅ | — |
| `s-vente-solde` | Soldée | `/ventes/$id` | `VenteDetailPage.tsx` | ✅ | — |

---

## Récapitulatif révisé (audit fidélité contenu — 2026-02-25)

> Méthode : lecture directe LAYER.html bloc par bloc + lecture page frontend. Route existante ≠ contenu fidèle.

### ❌ Absents — manque fonctionnel majeur (0)

Aucun — tous les écrans ont une page ou un état implémenté.

### ⚠️ Partiels — sections UI manquantes vs LAYER (29)

| ID | Page | Priorité | Écart principal |
|----|------|----------|-----------------|
| `s-devis-detail` | `DevisDetailPage` | **P0** | `detail-hero` + `workflow-strip` + `focus-strip` + quick links entièrement absents |
| `s-scan-qr` | `ScanPage` | **P0** | Viewfinder QR complet absent ; scans récents + modals résultat/saisie absents |
| `s-client-nouveau/edit` | `CustomerFormModal` | **P0** | Types clients 2 vs 4 (Professionnel/Association/Comité absents) ; note interne absente |
| `s-depart-from-resa` | `DepartureInventoryPage` | **P1** | Hero orange + alerte caution + btn "Vérifier article par article" + btn "Contrôle légal" absents |
| `s-retour-inventaire` | `ReturnInventoryPage` | **P1** | Chip "Contrôle" + btn "Lier à une facture" absents |
| `s-dommage-declare` | `DamageDeclareFullPage` | **P1** | Prix unitaire + section caution/restitution estimée absents |
| `s-devis-source` | `DevisSourcePage` | **P1** | Grille TVA (HT/TVA/TTC/Phases) + info box + raccourcis absents |
| `s-paiement-nouveau` | `InvoicePaymentForm` | **P1** | Récap facture + tuiles visuelles 6 modes paiement absents |
| `s-facture-create` | `InvoiceCreatePage` | **P1** | Champ Objet + lignes éditables + import devis absents |
| `s-client-detail` | `CustomerDetailPage` | **P1** | Note interne + btn Nouvelle resa/Message + quick links absents |
| `s-devis-list` | `DevisListPage` | **P1** | `info-grid` 4 KPIs (Total/Acceptés/En attente/Expirés) absent |
| `s-depart-bloque` | `DepartureBlockedPage` | **P1** | Montants EUR absents (texte générique vs valeurs réelles) |
| `s-rapport-mensuel` | `RapportMensuelPage` | **P1** | Notation clients + top produits + avis clients + export PDF absents |
| `s-stock` | `InventoryPage` | **P1** | Filtres pills catégorie + boutons rapides (Réassorts/Historique/États) absents |
| `s-devis-refuse` | `DevisRefuseModal` | **P2** | Modal simple vs écran complet avec hero + focus-strip + btns Dupliquer/Relancer |
| `s-devis-couverture` | `DevisCouverturePage` | **P2** | Filtres pills (Tout/Livré/En cours/À cadrer) absents |
| `s-devis-change-request` | `DevisChangeRequestPage` | **P2** | Filtres pills (Tout/À chiffrer/Validé/Refusé) absents |
| `s-facture-envoi` | `InvoiceSendModal` | **P2** | Preview PDF miniature intégrée absente |
| `s-facture-audit` | `InvoiceAuditPage` | **P2** | Filtres d'audit (Tout/Envoi/Ouverture/Relances/Paiements) absents |
| `s-facture-avoir` | `AvoirsPage` | **P2** | Boutons "Rembourser maintenant" et "Imputer sur prochaine facture" absents |
| `s-depart-inventaire` | `DepartureInventoryPage` | **P2** | Navigation stepper vers article-par-article absente |
| `s-casse-declaration` | modal casse | **P2** | Upload photos + section impact caution absents |
| `s-check-article` | `ArticleCheckPage` | **P2** | Pastilles emoji vs barres colorées (écart mineur) |
| `s-reservations` | `EventsPage` | **P2** | KPIs chips haut de page absents |
| `s-catalogue-produit` | layout `$id.tsx` | **P2** | Page index fiche produit publique absente |
| `s-stock-etats` | `ProductStatesPage` | **P2** | Route sous `products/` au lieu de `inventory/` |
| `s-stock-resolu` | `StockReorderPage` | **P2** | Pas de vue dédiée post-réassort confirmé |
| `s-clients-rfm` | `ClientsRFMPage` | **P3** | Bouton "Lancer campagne" absent (cosmétique) |

### 📊 Score global (audit fidélité contenu — 2026-02-25)

| Statut | Nb | % |
|--------|----|---|
| ✅ Fidèles au LAYER | 103 | 78% |
| ⚠️ Partiels (sections UI manquantes) | 29 | 22% |
| ❌ Absents | 0 | 0% |
| **TOTAL** | **132** | — |

---

## Plan d'action (corrections UI/UX)

### P0 — Impact fort, bloquant usage (3 écrans)

| Écran | Fix |
|-------|-----|
| `s-devis-detail` | Ajouter `detail-hero` coloré + `workflow-strip` 3 étapes + `focus-strip` 4 pills + quick links |
| `s-scan-qr` | Ajouter viewfinder QR élaboré (corners + laser) + section "Scans récents" + modals résultat/saisie |
| `s-client-nouveau/edit` | Étendre types clients à 4 + ajouter champ "Note interne" |

### P1 — Manques significatifs (12 écrans)

| Écran | Fix |
|-------|-----|
| `s-depart-from-resa` | Hero orange + alert caution OK + lien stepper + btn contrôle légal |
| `s-retour-inventaire` | Chip "Contrôle" + btn "Lier à une facture" |
| `s-dommage-declare` | Prix unitaire dans diff + section caution/restitution estimée |
| `s-devis-source` | Grille TVA + info box contexte + raccourcis Couverture/CR/Phases |
| `s-paiement-nouveau` | Récap facture + tuiles 6 modes paiement visuels |
| `s-facture-create` | Champ Objet + lignes éditables + btn importer devis |
| `s-client-detail` | Note interne + btns Nouvelle resa/Message + quick links |
| `s-devis-list` | `info-grid` 4 KPIs en haut |
| `s-depart-bloque` | Montants EUR réels (caution/montant restant) |
| `s-rapport-mensuel` | Notation étoiles + top produits + avis clients + export PDF |
| `s-vente-detail` | `focus-strip` 4 KPIs |
| `s-stock` | Filtres pills catégorie + boutons rapides |

### P2 — Améliorations UX (14 écrans)

Filtres pills Devis (couverture/CR), modal refusé complet, preview PDF envoi, filtres audit,
boutons avoir, stepper départ article-par-article, modal casse avec photos, chips réservations,
fiche produit index, route stock-états, vue réassort confirmé, pastilles ArticleCheck.

### ✅ FAIT — historique

| Sprint | Date | Résultat |
|--------|------|----------|
| Devis : 3 tabs (couverture/CR/phases) | 2026-02-25 | ✅ backend + frontend complets |
| Opérations + Stock : 5 écrans terrain | 2026-02-25 | ✅ routes plates TanStack Router v1 |
| SubNav layouts 15 modules | 2026-02-25 | ✅ double padding retiré |
| Skeletons P0 (9 pages) | 2026-02-25 | ✅ Loader2 → animate-pulse |

---

> `docs/LAYER_REFERENCE.md` est obsolète (fév 19, 55 écrans). Ce fichier est la référence unique de couverture.

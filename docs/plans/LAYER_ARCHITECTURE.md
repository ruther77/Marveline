# Architecture LAYER.html — Carte complète L1→L5

> Document de référence avant toute réécriture.
> Principe : un `id` = un écran mockup. Les états d'une même entité (ex: resa brouillon / confirmée / en cours) restent des écrans distincts dans le mockup statique, mais appartiennent au même **slot logique** L2.

---

## Navigation principale — 5 onglets fixes

```
🏠 Accueil   📅 Planning   📋 Réservations   📦 Stock   ⋯ Plus
```

| Onglet nav | `data-nav` | Hub |
|---|---|---|
| Accueil | `s-home` | Feed du jour |
| Planning | `s-planning-mois` | Mois → Semaine → Jour |
| Réservations | `s-reservations` | Locations + Ventes |
| Stock | `s-catalogue` | Catalogue + Inventaire |
| Plus | `s-plus` | Clients · Factures · Finances · Admin · Profil |

---

## 0 · Cross-domaine

| ID | Niveau logique | Description | Statut |
|---|---|---|---|
| `s-home` | L1 | Feed du jour — alertes urgentes + activité récente + 3 quick-actions | ✅ existe (à refactorer) |
| `s-plus` | L1 | Hub secondaire — liens Clients/Factures/Finances/Admin/Profil | 🆕 nouveau |
| `s-notifications` | L1 | Centre notifications — liste alertes | ✅ existe |
| `s-recherche-globale` | L1 | Recherche globale cross-domaine | ✅ existe |

---

## 1 · Planning (onglet 2)

> **Principe** : navigation temporelle par drill-down. Le planning est l'unique endroit où on visualise la densité. On ne sort PAS du planning pour voir un événement — panneau L4 overlay.

| ID | Niveau | Description | Statut |
|---|---|---|---|
| `s-planning-mois` | L1 | Vue mois — densité calendrier, tap jour → L3 | ✅ existe |
| `s-planning-semaine` | L2 | Vue semaine — colonnes jours, départs/retours | ✅ existe |
| `s-planning-jour` | L3 | Vue jour — timeline horaire, créneaux, conflits visibles | ✅ existe |
| `s-planning-evenement-panel` | L4 | Panneau événement pushé depuis planning — résumé + actions rapides sans quitter | 🆕 nouveau |
| `s-planning-conflit` | L5 | Résolution conflit ressource — 2 créneaux en vis-à-vis, actions de résolution | 🆕 nouveau |
| `s-planning-affectation` | L3 | Affecter équipe/véhicule à un événement | ✅ existe |

---

## 2 · Réservations (onglet 3)

> **Principe** : `s-reservations` = liste unifiée. `s-resa-[état]` = slot L2 (même écran logique, contenu adapté au statut). L3 = écrans de workflow. L4 = étapes opérationnelles. L5 = granularité article.

### L1 — Liste

| ID | Niveau | Description | Statut |
|---|---|---|---|
| `s-reservations` | L1 | Liste unifiée — filtres pills statut + search + swipe-to-reveal | 🆕 nouveau (remplace s-home liste) |

### L2 — Détail réservation (états = même slot logique)

| ID | Niveau | État | Statut |
|---|---|---|---|
| `s-resa-brouillon` | L2 | Brouillon — incomplet, à compléter | ✅ existe |
| `s-resa-brouillon-incomplet` | L2 | Brouillon incomplet — champs manquants | ✅ existe |
| `s-resa-confirmee-sans-caution` | L2 | Confirmée — caution à encaisser | ✅ existe |
| `s-resa-confirmee-risque` | L2 | Confirmée — signaux de risque détectés | ✅ existe |
| `s-resa-confirmee-avec-caution` | L2 | Confirmée — caution reçue, stock réservé | ✅ existe |
| `s-resa-confirmee-prete` | L2 | Confirmée — prête au départ | ✅ existe |
| `s-resa-precheck-legal` | L2 | Pré-check légal — documents à valider | ✅ existe |
| `s-resa-en-cours` | L2 | En cours — matériel sorti | ✅ existe |
| `s-resa-en-cours-prolongee` | L2 | En cours — prolongation active | ✅ existe |
| `s-resa-retournee` | L2 | Retournée — en attente de contrôle | ✅ existe |
| `s-resa-retournee-litige` | L2 | Retournée — litige ouvert | ✅ existe |
| `s-resa-terminee` | L2 | Terminée — clôturée normalement | ✅ existe |
| `s-resa-terminee-archive` | L2 | Terminée — archivée | ✅ existe |
| `s-resa-annulee` | L2 | Annulée | ✅ existe (P2) |

### L3 — Workflows et formulaires

| ID | Niveau | Description | Statut |
|---|---|---|---|
| `s-resa-create` | L3 | Créer une réservation — formulaire complet multi-sections | 🆕 nouveau (remplace m-creer-reservation) |
| `s-resa-edit` | L3 | Modifier une réservation — formulaire pré-rempli | 🆕 nouveau (remplace m-modifier-reservation) |
| `s-resa-depart-brief` | L3 | Briefing départ — récap resa + checklist globale avant inventaire | ✅ existe (`s-depart-from-resa`, à renommer) |
| `s-resa-retour-brief` | L3 | Briefing retour — état attendu + checklist globale | ✅ partiellement (`s-retour-inventaire`) |
| `s-resa-facturation` | L3 | Créer/lier facture depuis réservation — contexte préchargé | ✅ existe (`s-facture-create`) |
| `s-depart-bloque` | L3 | Départ bloqué — motif + actions de déblocage | ✅ existe |

### L4 — Étapes opérationnelles

| ID | Niveau | Description | Statut |
|---|---|---|---|
| `s-inventaire-depart` | L4 | Inventaire départ — check article par article (progress stepper) | ✅ existe (`s-depart-inventaire`, à renommer) |
| `s-inventaire-retour` | L4 | Inventaire retour — vérification état par article | ✅ existe (`s-retour-inventaire`) |
| `s-devis-from-resa` | L4 | Créer devis depuis réservation — contexte resa préchargé | 🆕 nouveau |
| `s-vente-paiement` | L4 | Encaissement vente — multi-moyens step by step | 🆕 nouveau |

### L5 — Granularité article

| ID | Niveau | Description | Statut |
|---|---|---|---|
| `s-check-article` | L5 | État d'un article — photo + condition picker (OK/rayé/cassé) + notes | 🆕 nouveau |
| `s-dommage-declare` | L5 | Déclarer dommage — type + coût estimé + lier facture + photo | 🆕 nouveau (remplace m-declarer-casse + m-facturer-dommages) |

---

## 3 · Ventes (sous onglet Réservations)

> Ventes directes = flux distinct des locations mais même onglet nav.

| ID | Niveau | Description | Statut |
|---|---|---|---|
| `s-ventes` | L1 | Liste ventes — filtres statut | ✅ existe |
| `s-vente-brouillon` | L2 | Vente brouillon | ✅ existe |
| `s-vente-acompte` | L2 | Vente avec acompte | ✅ existe |
| `s-vente-multi` | L2 | Vente multi-moyens | ✅ existe |
| `s-vente-solde` | L2 | Vente soldée | ✅ existe |
| `s-vente-retard` | L2 | Vente en retard de paiement | ✅ existe |
| `s-vente-edit` | L3 | Modifier une vente | 🆕 nouveau |

---

## 4 · Agenda / Événements (sous onglet Planning)

> Un événement = une occurrence d'une réservation dans le planning. Navigation depuis s-planning-* ou s-reservations.

| ID | Niveau | Description | Statut |
|---|---|---|---|
| `s-events-list` | L1 | Liste événements — vue opérationnelle du jour/semaine | ✅ existe |
| `s-event-prevu` | L2 | Événement prévu | ✅ existe |
| `s-event-prevu-risque` | L2 | Événement prévu — signaux risque | ✅ existe |
| `s-event-en-cours` | L2 | Événement en cours | ✅ existe |
| `s-event-en-cours-incident` | L2 | Événement en cours — incident déclaré | ✅ existe |
| `s-event-retourne` | L2 | Événement retourné | ✅ existe |
| `s-event-retourne-casse` | L2 | Événement retourné — casse constatée | ✅ existe |
| `s-event-termine` | L2 | Événement terminé | ✅ existe |
| `s-event-annule` | L2 | Événement annulé | ✅ existe |
| `s-event-action-plan` | L4 | Plan d'action incident — étapes + responsables + suivi | 🆕 nouveau (remplace m-plan-action-incident) |

---

## 5 · Stock / Catalogue (onglet 4)

> **Principe** : switcher pills en haut — "Catalogue" (vue client) / "Stock" (vue opérations). Même onglet, deux lectures différentes du même domaine.

### L1 — Entrées domaine

| ID | Niveau | Description | Statut |
|---|---|---|---|
| `s-catalogue` | L1 | Catalogue — liste produits avec photos, disponibilité, catégories | ✅ existe |
| `s-stock` | L1 | Stock — vue opérationnelle, alertes, états globaux | ✅ existe |

### L2 — Fiches

| ID | Niveau | Description | Statut |
|---|---|---|---|
| `s-catalogue-produit` | L2 | Fiche produit — planning dispo mini-calendrier + stock items résumé | ✅ existe |
| `s-catalogue-packs` | L2 | Liste packs/bundles | ✅ existe |
| `s-pack-detail` | L2 | Fiche pack — articles inclus, prix, disponibilité | 🆕 nouveau |
| `s-stock-faible` | L2 | Stock faible — produit sous seuil | ✅ existe |
| `s-stock-reassort` | L2 | Réassort en cours | ✅ existe |
| `s-stock-resolu` | L2 | Rupture résolue | ✅ existe |
| `s-stock-historique` | L2 | Historique mouvements produit | ✅ existe |
| `s-stock-etats` | L2 | États détaillés stock produit | ✅ existe |

### L3 — Édition / Sous-listes

| ID | Niveau | Description | Statut |
|---|---|---|---|
| `s-produit-create` | L3 | Créer un produit — formulaire multi-sections | 🆕 nouveau |
| `s-produit-edit` | L3 | Modifier un produit | 🆕 nouveau |
| `s-stock-items-liste` | L3 | Liste tous les articles physiques d'un produit — n° séries, états | 🆕 nouveau |
| `s-catalogue-categorie` | L3 | Parcourir une catégorie — liste filtrée | ✅ existe |
| `s-stock-reassort-flow` | L3 | Flux réassort — fournisseur + commande + réception (multi-step) | ✅ partiellement |
| `s-catalogue-etats` | L3 | États catalogue produit | ✅ existe |
| `s-catalogue-variantes` | L3 | Variantes d'un produit | ✅ existe |

### L4 — Article individuel

| ID | Niveau | Description | Statut |
|---|---|---|---|
| `s-stock-item-detail` | L4 | Fiche article individuel — n° série, condition, localisation actuelle, resa en cours | ✅ existe (P2) |
| `s-stock-item-edit` | L4 | Modifier un article — condition, notes, localisation | 🆕 nouveau |

### L5 — Granularité maximale

| ID | Niveau | Description | Statut |
|---|---|---|---|
| `s-stock-item-historique` | L5 | Historique complet d'un article — tous mouvements chronologiques | 🆕 nouveau |
| `s-stock-mouvement-detail` | L5 | Détail d'un mouvement — réservation liée, photos état avant/après, signataire | 🆕 nouveau (remplace partiellement s-stock-historique) |

---

## 6 · Factures & Devis (dans Plus)

> Devis et Factures partagent le même onglet avec switcher pills "Factures / Devis".
> L4/L5 partagé : l'éditeur de ligne et le catalogue picker sont les mêmes composants.

### L1 — Listes

| ID | Niveau | Description | Statut |
|---|---|---|---|
| `s-factures` | L1 | Liste factures — filtres pills statut + onglet Devis | ✅ existe |
| `s-devis-list` | L1 | Liste devis — accessible depuis pills onglet | ✅ existe |

### L2 — Détail (états)

| ID | Niveau | État | Statut |
|---|---|---|---|
| `s-facture-detail` | L2 | Facture standard | ✅ existe |
| `s-facture-brouillon` | L2 | Facture brouillon | ✅ existe |
| `s-facture-emise` | L2 | Facture émise — envoyée, impayée | ✅ existe (P2) |
| `s-facture-retard` | L2 | Facture en retard | ✅ existe |
| `s-facture-payee` | L2 | Facture payée | ✅ existe |
| `s-facture-avoir` | L2 | Note de crédit / avoir | ✅ existe (P2) |
| `s-facture-audit` | L2 | Audit trail facture | ✅ existe |
| `s-facture-casse` | L2 | Facture dommages/casse | ✅ existe |
| `s-devis-detail` | L2 | Devis standard — présentation client | ✅ existe |
| `s-devis-brouillon` | L2 | Devis brouillon (non envoyé) | ✅ existe |
| `s-devis-expire` | L2 | Devis expiré / versionné | ✅ existe |
| `s-devis-refuse` | L2 | Devis refusé | ✅ existe (P2) |
| `s-devis-couverture` | L2 | Devis — vue couverture client | ✅ existe |
| `s-devis-change-request` | L2 | Devis — demandes de modification | ✅ existe |
| `s-devis-phases` | L2 | Devis — découpage en phases | ✅ existe |

### L3 — Édition

| ID | Niveau | Description | Statut |
|---|---|---|---|
| `s-facture-create` | L3 | Créer une facture | ✅ existe |
| `s-facture-edit` | L3 | Éditer une facture — lignes modifiables inline, totaux live | 🆕 nouveau |
| `s-devis-create` | L3 | Créer un devis | 🆕 nouveau (remplace m-nouveau-devis) |
| `s-devis-edit` | L3 | Éditer un devis — lignes modifiables inline, totaux live | 🆕 nouveau (remplace m-modifier-ligne-devis) |
| `s-devis-source` | L3 | Devis développement Marveline (méta) | ✅ existe |

### L3 — Modules devis (spécifiques au devis Marveline)

| ID | Niveau | Description | Statut |
|---|---|---|---|
| `s-devis-module-socle` | L3 | Module socle | ✅ existe |
| `s-devis-module-stock` | L3 | Module stock | ✅ existe |
| `s-devis-module-facturation` | L3 | Module facturation | ✅ existe |
| `s-devis-module-securite` | L3 | Module sécurité | ✅ existe |
| `s-devis-module-services` | L3 | Module services | ✅ existe |

### L4 — Éditeur de ligne (partagé Facture + Devis)

| ID | Niveau | Description | Statut |
|---|---|---|---|
| `s-ligne-edit` | L4 | Éditeur ligne — produit + qté + durée + remise % + total recalculé live | 🆕 nouveau (remplace m-ajouter-ligne-devis + m-modifier-ligne-devis + m-ajouter-ligne-facture) |

### L5 — Catalogue picker (partagé)

| ID | Niveau | Description | Statut |
|---|---|---|---|
| `s-catalogue-picker` | L5 | Sélecteur produit depuis éditeur — search + disponibilité + prix suggéré + aperçu | 🆕 nouveau |

---

## 7 · Clients (dans Plus)

| ID | Niveau | Description | Statut |
|---|---|---|---|
| `s-clients` | L1 | Liste clients — search + filtres (type, solde retard) + swipe-reveal | ✅ existe (`s-clients-list`, à renommer) |
| `s-client-detail` | L2 | Fiche client — infos + 3 KPIs + onglets Résa/Factures/Devis | ✅ existe |
| `s-client-relance` | L2 | Client avec facture en retard — actions de relance | ✅ existe |
| `s-client-create` | L3 | Créer un client — formulaire | ✅ existe (`s-client-nouveau`, à renommer) |
| `s-client-edit` | L3 | Modifier un client | 🆕 nouveau (remplace m-modifier-client) |
| `s-client-historique` | L3 | Historique étendu — filtres période, pagination | 🆕 nouveau |
| `s-client-transaction` | L4 | Transaction dans contexte client — breadcrumb "← Client" | 🆕 nouveau |
| `s-client-litige` | L5 | Fil de litige — thread chronologique + notes internes + actions | 🆕 nouveau |

---

## 8 · Finances (dans Plus)

| ID | Niveau | Description | Statut |
|---|---|---|---|
| `s-finances` | L1 | Dashboard KPIs + graphe mensuel + tableau | ✅ existe |
| `s-finances-periode` | L2 | Détail d'une période — liste transactions filtrées, totaux | 🆕 nouveau |
| `s-finances-export` | L3 | Paramètres export comptable — format, période, bilan | 🆕 nouveau |

---

## 9 · Profil & Paramètres (dans Plus)

| ID | Niveau | Description | Statut |
|---|---|---|---|
| `s-profil` | L2 | Profil utilisateur — infos + liens admin | ✅ existe |
| `s-parametres` | L2 | Paramètres app — TVA, caution %, délais, entreprise | ✅ existe |
| `s-securite` | L2 | Sécurité — MFA, sessions actives | 🆕 nouveau |
| `s-notifications-settings` | L3 | Préférences notifications — canaux, fréquences | 🆕 nouveau |

---

## 10 · Admin (dans Plus, role:admin)

| ID | Niveau | Description | Statut |
|---|---|---|---|
| `s-admin` | L1 | Hub admin — liens vers sections | 🆕 nouveau |
| `s-admin-utilisateurs` | L2 | Liste membres + rôles | ✅ existe (P4) |
| `s-admin-audit` | L2 | Audit logs — timeline actions | ✅ existe (P4) |
| `s-admin-apikeys` | L2 | Clés API — actives/révoquées + permissions | ✅ existe (P4) |
| `s-admin-parametres` | L2 | Config système — feature flags + maintenance + danger zone | ✅ existe (P4) |
| `s-admin-user-detail` | L3 | Fiche utilisateur — rôles, sessions, historique actions | 🆕 nouveau |

---

## Modales conservées (bottom-sheets légitimes)

> Règle : action ponctuelle sans besoin de contexte visuel. ≤ 3 champs ou confirmation pure.

### Confirmations destructives
- `m-annuler-resa`, `m-supprimer-brouillon`, `m-archiver-resa`, `m-supprimer-client`, `m-supprimer-facture`, `m-annuler-devis`, `m-supprimer-produit`

### Actions rapides (≤ 3 champs)
- `m-encaisser-caution`, `m-relancer-caution`, `m-prolonger-resa`
- `m-marquer-payee`, `m-ajouter-paiement`, `m-ajouter-frais`, `m-emettre-avoir`
- `m-relancer-client`, `m-relancer-facture`
- `m-affecter-ressources`, `m-cloture-retour`, `m-cloture-evenement`
- `m-ajuster-stock`, `m-reception-reassort`

### Feedback / output
- `m-pdf-facture`, `m-pdf-devis`, `m-photo`, `m-export-factures`, `m-export-devis`
- `m-date-range`, `m-notif-detail`, `m-changer-photo`
- `m-rapport-evenement`, `m-recu-paiement`

---

## Modales supprimées → converties en pages

| Modale supprimée | Remplacée par | Niveau |
|---|---|---|
| `m-creer-reservation` / `m-m6b` | `s-resa-create` | L3 |
| `m-modifier-reservation` / `m-m6` | `s-resa-edit` | L3 |
| `m-nouveau-devis` / `m17b` | `s-devis-create` | L3 |
| `m-creer-client` | `s-client-create` | L3 |
| `m-modifier-client` | `s-client-edit` | L3 |
| `m-ajouter-ligne-devis` / `m-modifier-ligne-devis` / `m22` | `s-ligne-edit` | L4 |
| `m-declarer-casse` + `m11a4` | `s-dommage-declare` | L5 |
| `m-plan-action-incident` / `m13d` | `s-event-action-plan` | L4 |
| `m-filter-clients` / `m-filter-reservations` / `m-filter-stock` | pills inline + `s-filter-[domain]` si besoin | L1 |

---

## Patterns interactifs à implémenter

| Pattern | Niveau | Écrans concernés |
|---|---|---|
| Swipe-to-reveal actions | L1 | Toutes les listes |
| Long press → mode sélection | L1 | Listes avec bulkactions |
| Pull-to-refresh visual | L1 | Toutes les listes |
| Stepper de progression | L3/L4 | `s-resa-create`, `s-inventaire-depart`, `s-inventaire-retour`, `s-stock-reassort-flow` |
| Inline edit (tap field) | L3 | `s-facture-edit`, `s-devis-edit` |
| Totaux live | L3/L4 | `s-facture-edit`, `s-devis-edit`, `s-ligne-edit` |
| Drag to reorder | L3 | Lignes devis/facture |
| Bottom sheet contextuel | L4/L5 | Depuis `s-check-article`, `s-stock-item-detail` |
| Breadcrumb contextuel | L4 | `s-client-transaction`, `s-devis-from-resa` |
| Snapping scroll horizontal | L2/L3 | `s-planning-semaine` (jours) |
| Skeleton loading | L1 | Toutes les listes |
| Empty states | L1 | Toutes les listes |

---

## Résumé chiffré

| Catégorie | Existant | Nouveau | Total |
|---|---|---|---|
| Écrans L1 | 8 | 3 | 11 |
| Écrans L2 (états inclus) | 52 | 4 | 56 |
| Écrans L3 | 18 | 15 | 33 |
| Écrans L4 | 6 | 6 | 12 |
| Écrans L5 | 3 | 6 | 9 |
| **Total écrans** | **87** | **34** | **121** |
| Modales conservées | ~30 | — | ~30 |
| Modales supprimées | ~20 | → pages | — |

---

## Ordre d'implémentation suggéré

1. **Nav** — refactorer bottom-nav (5 onglets + hub `s-plus`)
2. **Home** — réécrire `s-home` (feed, pas dashboard)
3. **L3 manquants critiques** — `s-resa-create`, `s-devis-create`, `s-facture-edit`, `s-devis-edit`, `s-client-edit`
4. **L4 manquants** — `s-ligne-edit`, `s-event-action-plan`, `s-inventaire-depart` (renommage + enrichissement)
5. **L5 manquants** — `s-check-article`, `s-dommage-declare`, `s-catalogue-picker`, `s-client-litige`
6. **Patterns interactifs** — swipe, stepper, inline-edit, totaux live

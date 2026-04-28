# Module 29 — Restaurant (L'Incontournable / TAIYAT)

> **Phase D.** Audit du domaine restaurant : ingrédients, recettes, marmites (InstancePreparation), commandes, lignes (cuisine + bar), tables, sides, transferts demande, ETL TAIYAT, dashboard.

---

## 1. Inventaire — lecture intégrale

| Fichier | LoC |
|---|---|
| `app/models/restaurant/ingredient_restaurant.py` | 100 |
| `app/models/restaurant/categorie_ingredient.py` | 56 |
| `app/models/restaurant/type_preparation.py` | 74 |
| `app/models/restaurant/recette_type_preparation.py` | 81 |
| `app/models/restaurant/instance_preparation.py` | 101 |
| `app/models/restaurant/variante_plat.py` | 123 |
| `app/models/restaurant/variante_side.py` | 54 |
| `app/models/restaurant/side_restaurant.py` | 80 |
| `app/models/restaurant/table_restaurant.py` | 50 |
| `app/models/restaurant/commande_restaurant.py` | 127 |
| `app/models/restaurant/ligne_commande_restaurant.py` | 120 |
| `app/models/restaurant/mouvement_stock_restaurant.py` | 114 |
| `app/models/restaurant/alerte_stock_restaurant.py` | 101 |
| `app/models/restaurant/transfer_request.py` | 158 |
| `app/models/restaurant/ingredient_epicerie_mapping.py` | 117 |
| `app/services/restaurant/ligne_commande.py` | 500 |
| `app/services/restaurant/commande.py` | 313 |
| `app/services/restaurant/instance_preparation.py` | 239 |
| `app/services/restaurant/dashboard.py` | 226 |
| `app/services/restaurant/reception_etl.py` | 426 |
| `app/services/restaurant/ingredient_sourcing.py` | 248 |
| `app/services/restaurant/mouvement_stock.py` | 136 |
| `app/services/restaurant/transfer_request.py` | 88 |
| `app/services/restaurant/exceptions.py` | 64 |
| Repositories restaurant (parcours) | ~1 100 |
| Endpoints + schemas restaurant (parcours) | ~1 300 |

**Volume total** : ~6 200 LoC.

---

## 2. Architecture observée

```
IngredientRestaurant (Niveau 2 stock kg, NUMERIC(10,3))
  ↑
  RecetteTypePreparation (M:N → ingredient × type)
  ↑
TypePreparation (recette template) — portions_par_batch / seuil_alerte_portions
  ↓ 1:N
InstancePreparation (marmite réelle, Niveau 1 stock portions)
  portions_initiales / portions_restantes (atomic ADR-14)
  ↓ référencée par
LigneCommandeRestaurant (instance_preparation_id décrémenté)

CommandeRestaurant (FSM 4 statuts : OUVERTE → SERVIE → PAYEE | ANNULEE)
  ├── nb_couverts, sous_total / tva / total NULL tant que OUVERTE
  └── 1:N LigneCommandeRestaurant
        statut_plat (FSM 4 : ENVOYEE → LANCEE → PRETE → SERVIE)
        prix_unitaire_cts snapshot
        ↓ FK SET NULL
        SideRestaurant (avec ingredient_id consommé au service)
        VarianteSide (M:N supplément cts)

VariantePlat (plat | boisson | formule)
  taux_tva centièmes de % (ADR-06-BIS)
  ingredient_proteine_id + quantite_proteine (consommation au service)
  type_preparation_id (lien marmite pour plats)

MouvementStockRestaurant (immuable journal ingrédients, signe SQL)
  5 types : entree | consommation | transfert_entrant | inventaire | perte
  stock_apres dénormalisé
  etl_import_id pour traçabilité revert

AlerteStockRestaurant (entité polymorphe ingredient | instance_preparation)
  resolu_at NULL = active

TransferRequest (BACK-TRANSFER-RESTO-01)
  PENDING → APPROVED → FULFILLED | REJECTED | CANCELLED
  target_tenant_id épicerie cross-tenant (CHECK self != target)

IngredientEpicerieMapping (résolveur cascade ADR 2026-04-21)
  cross-tenant : tenant_id resto, produit_id épicerie
  ordre + facteur_conv pour cumul prélèvements multi-produits
```

---

## 3. Frictions identifiées — module 29

> Compteur cumulé (mod. 01-28) ≈ 905. Module 29 ouvre à **F906**.

### 3.1 P0

#### F906 — `_verifier_et_consommer_recette` accède à `ligne.quantite_par_portion` **inexistant** (AttributeError runtime)

**Constat.** `services/restaurant/instance_preparation.py:118` :
```python
qtite_requise = Decimal(str(ligne.quantite_par_portion)) * nb_portions
```

Mais le modèle `RecetteTypePreparation` (l. 49) ne déclare que **`quantite_par_batch`**. Les autres callers (`services/restaurant/type_preparation.py:90,115,133,139`) utilisent correctement `quantite_par_batch`.

→ Tout `POST /instances` (lancement de marmite) avec une recette définie lève `AttributeError` immédiatement → **500 Internal Server Error systémique**, le restaurant ne peut PAS lancer une marmite tant que la recette a au moins une ligne.

**Sémantique** : le commentaire l. 50 du modèle dit "quantité de l'ingrédient pour un batch complet". Le service multiplie ensuite `× nb_portions`. Si l'attribut existait avec ce nom, la formule serait fausse aussi — il faudrait `(quantite_par_batch / portions_par_batch) * nb_portions` ou simplement `quantite_par_batch` si on cuit un batch entier.

**Action immédiate** : (1) renommer en `quantite_par_batch` ; (2) corriger la formule : `qte = quantite_par_batch * (nb_portions / tp.portions_par_batch)`.

---

#### F907 — `_consommer_ingredient` ne lève pas l'alerte `bas` si stock_alerte == 0

**Constat.** `services/restaurant/ligne_commande.py:317-327` : `_gerer_alertes_ingredient` exige `stock_alerte > _ZERO` pour créer l'alerte `bas`. Ingrédients avec `stock_alerte = 0` (default model l. 64) ne déclencheront jamais d'alerte tant que `stock_actuel > 0`. Combiné à l'ETL TAIYAT (`reception_etl.py:138` qui crée tous les ingrédients avec `stock_alerte=0`), aucune alerte ne déclenche jamais.

→ Le badge "alerte" UI (FC_RESTAURANT_INGREDIENTS.md §4) ne fonctionne que si un humain saisit explicitement un seuil >0 dans l'UI ; aucune politique de seuil par défaut.

**Action** : seuil par défaut dérivé du stock historique (rolling p10 conso) ou via `categorie_ingredient` (catégorie = seuil indicatif).

---

#### F908 — `LigneCommande.delete` (annulation) **ne crée AUCUN mouvement de réintégration stock**

**Constat.** `services/restaurant/ligne_commande.py:167-173` :
```python
async def delete(self, ligne_id: int) -> None:
    ligne = await self._ligne_repo.get_by_id(ligne_id)
    if ligne.statut_plat in _STATUTS_NON_ANNULABLES:
        raise LigneNonAnnulable(...)
    await self._ligne_repo.delete(ligne_id)
```

Les statuts annulables sont `ENVOYEE` et `LANCEE`. Mais `_consommer_stocks` a déjà été exécuté à la création (l. 88) : protéine + side ingrédient consommés, et si `instance_preparation_id` non null portions décrémentées. La suppression de la ligne **NE RESTITUE NI les portions NI le stock ingrédient**.

→ Drift garanti : un client demande un plat puis change d'avis → la portion de marmite est définitivement perdue, le stock ingrédient consommé.

**Action** : générer mouvements compensatoires (`type='inventaire'` avec quantite positive) + incrémenter `portions_restantes` avant DELETE, dans la même transaction. Idéalement, transformer `delete` en `cancel_ligne` qui INSERT un mouvement de retour.

---

#### F909 — `CommandeService.annuler` n'appelle pas non plus la réintégration stock

**Constat.** `services/restaurant/commande.py:83-92`. Annule la commande mais ne touche ni les portions ni le stock ingrédients. Si la commande était OUVERTE avec déjà N lignes consommatrices, leurs effets stock persistent. Compose F908 — un cancel de table avec 10 lignes en cuisine = 10 portions + 10× stock ingrédient perdus.

**Action** : itérer sur les lignes de statut `ENVOYEE`/`LANCEE` et appeler la logique de réintégration F908.

---

#### F910 — `CommandeRestaurant.payer` **n'enregistre PAS d'audit log finance** ni d'écriture dans `FinanceInvoice`

**Constat.** `services/restaurant/commande.py:94-121`. Set status PAYEE + dénormalise sous_total/tva/total/pourboire/mode_paiement/fractionnement et c'est tout. Aucune création d'objet finance (`FinanceInvoice` ou `JournalEntry`). 

→ Le CA restaurant existe **uniquement dans `restaurant_commandes`**. Il n'y a pas de symétrie avec l'épicerie (`EpicerieVente` → FinanceInvoice CLIENT) auditée mod. 28. 
→ La compta côté restaurant repose sur l'agrégation `_cmd_repo.sum_ca_date` du dashboard, pas sur un livre comptable. Un audit fiscal échoue.

**Action** : à chaque `payer()`, créer une `FinanceInvoice(type='CLIENT_RESTAURANT')` ou écriture journal dédiée — avec ref `CMD-RESTO-{id}`, lien vers la commande.

---

#### F911 — `payer` écrit `pourboire_cts` **sans Numeric/Decimal** — fractions non gérées

`services/restaurant/commande.py:116`. Si l'UI envoie un pourboire de 1,50 EUR = 150 cts, OK. Mais `total_cts` ne sert pas à valider que `total_cts == sum(fractions.montant_cts)`. Si `payload.fractions` total ≠ `total_ttc + pourboire`, aucune contrainte. → Drift fractionnement vs ticket. Cf. F424 invoice mod. 21.

---

#### F912 — `MouvementStockService.create` accepte `payload.quantite` négatif sans validation explicite

**Constat.** `services/restaurant/mouvement_stock.py:33-40` `_appliquer_signe`. Pour `inventaire`, `payload.quantite` représente le **stock cible** (cf. commentaire l. 5-7). Si payload.quantite est négatif, `delta = quantite - stock_actuel` peut produire un nouveau_stock négatif → CHECK `stock_apres >= 0` fait échouer en SQL avec IntegrityError 500 au lieu de 422.

**Action** : valider en service `if payload.quantite < 0 and type='inventaire': raise StockInvalide` avant d'appliquer.

---

#### F913 — `_consommer_stocks` consomme protéine *avant* d'avoir vérifié `instance_preparation_id` valide

**Constat.** `services/restaurant/ligne_commande.py:75-88` : `create_ligne` appelle `_decrire_instance` puis `_consommer_stocks`. Mais l'instance et la protéine peuvent référencer des ingrédients différents → on consomme la protéine **en plus** des ingrédients de la recette de la marmite (déjà consommés au lancement). Double comptabilisation potentielle si la marmite "Carry poulet" contient déjà 0,2kg poulet par batch ET la `VariantePlat.ingredient_proteine_id` pointe vers le même ingrédient poulet avec `quantite_proteine=0.2`.

→ Confusion sémantique : la protéine est consommée 2 fois (au lancement marmite + au service de la ligne) si l'admin remplit naïvement les deux.

**Action** : règle métier explicite — soit la protéine est dans la recette du TypePreparation (consommée au lancement), soit dans la VariantePlat (consommée au service), pas les deux. Une CHECK invariant ou validation service.

---

### 3.2 P1

#### F914 — `commande.payer` n'a **pas** de `with_for_update` sur la commande

`services/restaurant/commande.py:95`. Deux serveurs cliquant simultanément "Payer" sur le même ticket → race : les deux passent par le check `cmd.statut != "OUVERTE"`, double UPDATE statut PAYEE possible. Le repo `update` ne re-vérifie pas le statut. Conséquence rare mais possible : double comptabilisation CA.

---

#### F915 — `_decrire_instance` lock OK mais `_consommer_stocks` exécuté **après** flush — pas dans la même unité atomique

`services/restaurant/ligne_commande.py:86-88`. `flush()` à l. 247 dans `_decrire_instance`. Si `_consommer_stocks` lève (stock insuffisant), la décrémentation portions n'est PAS rollback automatiquement (même session, mais flush ≠ commit). Le commit final se fait au niveau endpoint. **OK si exception → rollback session entière**, mais mérite vérification.

---

#### F916 — `MouvementStockRestaurant` immuable promise comment-only (pattern F795)

L. 38-44 du modèle. Pas de trigger DB.

---

#### F917 — `IngredientRestaurant.cout_unitaire_cts` **écrasé** silently à chaque ETL sans audit historique

`services/restaurant/reception_etl.py:127`. Si TAIYAT modifie le prix d'achat à chaque facture, on perd l'historique. Pas de table `IngredientPriceHistory`. Cf. F874 catalogue épicerie. Drift PMP impossible à reconstruire.

---

#### F918 — `_find_ingredient_by_nom` charge **TOUS** les ingrédients du tenant à chaque appel (N×O(n))

`services/restaurant/reception_etl.py:95-103`. Pour chaque ligne TAIYAT, scan complet de la table puis Python loop. Pour 200 ingrédients × 30 lignes facture = 6000 comparaisons Python par import.

**Action** : index fonctionnel `LOWER(unaccent(nom))` + WHERE direct.

---

#### F919 — `_normalize_nom` regex `[^a-z0-9]+` perd les caractères significatifs (`-`, `'`)

L. 85. "rougail-tomates" et "rougail tomates" matchent comme égaux mais "L'Incontournable" et "lincontournable" aussi. Acceptable mais documenter.

---

#### F920 — `recevoir_facture_etl_restaurant` **ne déclenche pas la résolution alerte** sur les ingrédients réapprovisionnés

Une livraison TAIYAT remplit le stock mais les alertes actives existantes ne sont pas résolues (cf. ligne_commande.py:_gerer_alertes_ingredient qui ferait le travail). → Alertes fantômes persistent jusqu'au prochain mouvement de consommation.

---

#### F921 — `revert_import_restaurant` `if new_stock < 0: new_stock = Decimal("0")` **clamp silencieux**

`reception_etl.py:380`. Si la livraison a été partiellement consommée puis revert, le stock devient incohérent (réel = 5, théorique = -3, clampé à 0). Le delta `quantite` du compensating mvt n'est pas ajusté → `stock_apres` enregistre 0 mais `quantite = -original`, donc ledger replay donnerait -3.

---

#### F922 — `TransferRequest.lignes` (TransferRequestLine) **ne possède pas de `tenant_id`** (heritage par FK uniquement)

`models/restaurant/transfer_request.py:98-99`. `class TransferRequestLine(Base, TimestampMixin)` — pas TenantMixin. Filtre tenant repose sur la JOIN avec `request.tenant_id`. Pattern fragile : un repo qui oublie le JOIN expose cross-tenant.

---

#### F923 — `TransferRequest` workflow MVP : pas de transition `APPROVED → FULFILLED` côté backend

Le service expose seulement `create / list / cancel`. Le statut FULFILLED n'a pas d'endpoint et `fulfilled_transfer_id` n'est jamais rempli côté code. → Le workflow est cassé en plein milieu : l'épicerie ne peut pas confirmer fulfillement via API.

---

#### F924 — `IngredientEpicerieMapping` cross-tenant produit_id **sans validation** que produit appartient au tenant épicerie jumelé

`models/restaurant/ingredient_epicerie_mapping.py:23-26` : "Contrôle métier : le service valide que le produit appartient au tenant épicerie jumelé". Mais `services/restaurant/ingredient_sourcing.py:_assert_produit_exists` (l. 174-179) vérifie seulement l'existence, pas le tenant. → Un mapping peut référencer un produit d'un tenant épicerie tiers (ex: SPLENDID).

---

#### F925 — `_load_mappings_with_stock` outerjoin `EpicerieStock` **sans filtre tenant épicerie** sur le stock

`services/restaurant/ingredient_sourcing.py:67-79`. Le stock épicerie n'a pas de filtre `EpicerieStock.tenant_id == tenant_epicerie_jumelé`. Un produit cross-tenant pourrait voir son stock d'un autre tenant. Combinaison F924+F925 = fuite cross-tenant.

---

#### F926 — `payer` sans recalculer `total_cts` côté serveur si `payload.fractions` divergent

L. 107-117. La somme des fractions n'est jamais vérifiée vs total. Cf. F911.

---

#### F927 — `VariantePlat.taux_tva default=550` (5,5%) hardcoded

L. 62. La valeur par défaut est restaurant-spécifique (TVA réduite alimentaire France métropolitaine, mais 0% à La Réunion sur certains alimentaires). Pas configurable per tenant.

---

#### F928 — `CommandeRestaurant.fractionnement JSONB` sans schema validation

L. 78-81. Pydantic le valide à l'entrée, mais une lecture directe DB peut renvoyer du JSON malformé.

---

#### F929 — `appliquer_formule` ne vérifie pas que les 3 boissons concernées sont **encore présentes** dans la commande

`services/restaurant/ligne_commande.py:210-232`. Crée la ligne formule sans réconcilier avec les boissons existantes (ne supprime pas les 3 lignes boisson, ne marque pas la formule comme remplaçant). → Double facturation : 3 boissons + 1 formule.

---

#### F930 — `_suggestion_formule` ne tient pas compte des annulations partielles

L. 329-353. `count_by_commande_variante` compte les lignes existantes. Si on annule 1 sur 6, total devient 5 — pas multiple de 3 → suggestion disparaît, mais la ligne formule éventuellement déjà créée demeure. F929 + F930 = drift facturation.

---

#### F931 — `marquer_servi` n'enregistre **pas** `served_at` ni qui a marqué servi

`services/restaurant/ligne_commande.py:145-165`. Updated `statut_plat=SERVIE` mais aucun champ horodatage spécifique sur la ligne. `updated_at` du TimestampMixin est trop générique.

---

#### F932 — `LigneCommandeRestaurant.statut_plat` enum String(20) avec 4 valeurs OK, mais pas de matrice FSM enforcée

Dans le repo `update_statut(ligne_id, statut)` accepte n'importe quelle transition. ENVOYEE → SERVIE direct possible (skip LANCEE+PRETE). Pas de gardien transition.

---

#### F933 — `Side.quantite_par_portion` not coupled with FSM service start

CHECK couple `(ingredient_id IS NULL) = (quantite_par_portion IS NULL)` (model l. 68) bien fait. Mais si un side a `quantite_par_portion=0.0`, le check `if side.quantite_par_portion:` (l. 290) en service est falsy → consommation skippée silencieusement.

---

### 3.3 P2

#### F934 — `CommandeRestaurant` pas de SoftDeleteMixin (commentaire l. 36) — discutable mais OK statut ANNULEE

#### F935 — `LigneCommandeRestaurant` `commande_id ondelete="RESTRICT"` bloque suppression commande mais cohérent

#### F936 — `instance_preparation_id ondelete="SET NULL"` dans LigneCommandeRestaurant : si un admin supprime une instance, les lignes perdent leur traçabilité marmite

#### F937 — `MouvementStockRestaurant.ingredient_id ondelete="SET NULL"` casse audit (mvt sans ingrédient)

#### F938 — `IngredientRestaurant.unite_stock String(10)` libre (`kg/L/piece` mais pas de CHECK enum)

#### F939 — `IngredientRestaurant.cout_unitaire_cts BigInteger nullable` — mais default None peut donner CA cost calculations à 0

#### F940 — `_calculer_tva_ligne` ROUND_HALF_UP sur chaque ligne → erreur arrondi cumulative

`services/restaurant/commande.py:53`. Pour 100 lignes à 9,99€ (5,5% TVA), la somme des arrondis ligne par ligne diffère de la TVA calculée sur le total. Cf. F423 invoice.

---

#### F941 — `payer` ne pose pas le commit fractions json en dénormalisé schemas validé

#### F942 — `dashboard.get_stats` ca_cts inclut un "uplift" `tenant_settings.reservation_uplift_pct` qui peut être abusé pour gonfler le CA UI sans impact compta

`services/restaurant/dashboard.py:60`. CA affiché ≠ CA réel. UI utilisateur croit voir une vérité, mais c'est une projection.

---

#### F943 — `TransferRequestLine.designation String(200)` libre — pas de FK catalog

Conscient (commentaire model l. 100-107) mais limite traceability mappings.

---

#### F944 — `_load_uplift_pct` ne lit pas tenant_id dynamique — hardcoded `_TENANT_RESTAURANT = 3`

Service singleton tenant unique. Si l'app se généralise multi-restaurants, refacto nécessaire.

---

#### F945 — `recevoir_facture_etl_restaurant` impose `tenant_id == 3` (l. 229) — même problème

#### F946 — `IngredientEpicerieMapping.facteur_conv Numeric(10,4)` peut overflow pour gros packs (> 999999.9999)

#### F947 — Pas d'index `(tenant_id, statut)` sur `restaurant_commandes` ? Vérification : oui présent (`idx_commandes_resto_tenant_statut`). OK.

#### F948 — `MouvementStockRestaurant.date_mouvement` provided by frontend — peut être falsifié (timestamp passé)

L. 71. Le frontend pourrait passer un timestamp 1970 → audit incohérent.

---

#### F949 — `appliquer_formule` lazy import `CommandeService` (l. 214) — symptôme d'un cycle de dépendance non résolu architecturalement

---

#### F950 — Pas de cap journalier sur `MouvementStockService.create(type='perte')` — un employé malveillant peut écouler tout le stock en perte

---

### 3.4 P3

#### F951 — `IngredientRestaurant.image_url String(500)` — magic number

#### F952 — Comments mix anglais/français

#### F953 — `MAX_INSTANCES_PER_DAY = 100` magic number `services/restaurant/dashboard.py:34`

#### F954 — `unite_stock="kg"` default sur ingrédient mais ETL TAIYAT mappe en `colis|piece|kg|L` → drift

#### F955 — `_calculer_tva_ligne` `_DIV_TVA = Decimal("10000")` magic — pas dans constants

---

## 4. Synthèse module 29

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 8 | F906 (AttributeError quantite_par_portion), F907 (alerte stock_alerte=0), F908 (annuler ligne sans réintégration), F909 (annuler commande idem), F910 (no FinanceInvoice), F911 (fractions vs total), F912 (inventaire negatif 500), F913 (double conso protéine) |
| P1 | 20 | F914 → F933 |
| P2 | 17 | F934 → F950 |
| P3 | 5 | F951 → F955 |
| **Total** | **50** | F906 → F955 |

**Compteur cumulé après module 29** : ≈ 905 + 50 = **955 frictions**.

---

## 5. Décision architecturale

> **P0 immédiat** : (1) Fix AttributeError `quantite_par_portion` → `quantite_par_batch` + corriger formule (F906) ; (2) réintégration stock sur annulation ligne+commande (F908+F909) ; (3) FinanceInvoice CLIENT_RESTAURANT à payer (F910) ; (4) règle métier protéine recette XOR variante (F913) ; (5) validation stock cible inventaire (F912) ; (6) seuil_alerte par défaut intelligent (F907) ; (7) cohérence fractions=total (F911).
>
> **Phase suivante** : workflow APPROVED→FULFILLED transfer_request (F923) ; enforcement tenant produit_id mapping (F924+F925) ; FSM matrice statut_plat (F932) ; resolution alerte sur reception (F920) ; trigger DB immutability mvt (F916).

---

# Module 30 (suivant) — Catalogue partagé / Transferts cross-domain

> Synthèse architecturale ETL alimentaire + transferts (F906 → F999 prévus).

# Module 17 — Devis (Marveline)

> **Phase C.** Audit du domaine devis : modèle (`Devis` + 9 sous-entités), FSM 9 statuts, lignes, modules/phases/coverage, versions/négociations/change_requests, attachments, conversion en réservation, signature.
>
> **Forward-références :** F485/F487 (Product.category, tva_rate par produit), F530/F532 (PricingEngine vs simulate divergent).

---

## 1. Inventaire — lecture intégrale

| Fichier | LoC |
|---|---|
| `app/models/devis.py` | 689 (10 classes : Devis + DevisLine + DevisLineHistory + DevisModule + DevisPhase + DevisVersion + DevisNegotiation + DevisChangeRequest + DevisCoverageItem + DevisAttachment) |
| `app/services/devis.py` | 1068 (parcouru, sections clés intégralement) |
| `app/repositories/devis.py` | 453 (parcours) |
| `app/api/v1/endpoints/devis.py` | 1000 (parcours headers) |
| `app/services/devis_pdf.py` | 127 (parcours) |
| `app/schemas/devis.py` | 512 (parcours) |

**Volume total** : ~3 850 LoC.

---

## 2. Architecture observée

```
Devis (FSM 9 statuts)
  ├── DevisLine (cascade) — product_id | bundle_id | variant_id | label libre
  │     └── DevisLineHistory (append-only)
  ├── DevisModule (cascade) — socle/stock/facturation/securite/services
  ├── DevisPhase (cascade) — date_start, date_end
  ├── DevisVersion (cascade) — snapshot JSON immutable
  ├── DevisNegotiation (cascade) — message + proposed_amount
  ├── DevisChangeRequest (cascade) — pending/accepted/refused
  ├── DevisCoverageItem (cascade) — a_cadrer/en_cours/livre
  └── DevisAttachment (cascade) — file_path local 10MB max

FSM:
  draft → sent | cancelled
  sent → negotiation | accepted | refused | expired
  negotiation → accepted | refused | expired | version_pending
  version_pending → sent | negotiation | accepted | refused | cancelled
  accepted → converted | cancelled
  refused → draft (via duplicate)
  expired → draft (via renew)
  converted → ∅ (terminal)
  cancelled → ∅ (terminal)
```

---

## 3. Frictions identifiées — module 17

> Compteur cumulé (mod. 01-16) ≈ 557. Module 17 ouvre à **F558**.

### 3.1 P0

#### F558 — `convert_to_reservation` ne **réserve pas le stock** (pas de call `ProductService.reserve_stock`)

**Constat.** `services/devis.py:626-680` crée la `Reservation` `status=DRAFT` + `ReservationLine` mais **aucun appel** à `reserve_stock` ni `check_availability` sur produits/bundles/variants. Donc :

1. Devis A converti → Reservation A en DRAFT, stock non décrémenté.
2. Devis B (même produit, même date) converti → Reservation B en DRAFT, stock non décrémenté.
3. Les deux passent en `confirmed` → stock négatif au moment livraison.

**Cf. F500 mod. 15** (no `check_bundle_availability`) — bug aggravé : pas même de check au niveau produit individuel.

**Action** : appeler `ProductService.reserve_stock(product_id, qty, tenant_id, variant_id)` pour chaque ligne dans une transaction unique avec rollback si échec.

---

#### F559 — `convert_to_reservation` n'a pas `SELECT FOR UPDATE` sur Devis → double-conversion possible

**Constat.** `services/devis.py:517-525` :
```python
stmt = select(Devis).options(...).where(Devis.id == devis_id, ...)
result = await self.db.execute(stmt)
devis = result.unique().scalar_one_or_none()
```

Pas de `with_for_update()`. Deux clics rapides ou deux onglets ouverts → deux exécutions concurrentes :
- Les deux passent `_assert_transition(devis, CONVERTED)` (statut `accepted` accepté).
- Les deux créent une Reservation avec une référence (race + retry l. 622).
- Les deux mettent `devis.status = CONVERTED` → write conflict côté SQLAlchemy.

Selon l'isolation level (READ COMMITTED par défaut PostgreSQL), au moins une réservation reste créée, l'autre commit + override status. **Idempotency violée** : la seconde réservation existe sans devis source cohérent.

**Action** : `select(Devis).where(...).with_for_update()` + check status post-lock.

---

#### F560 — `convert_to_reservation` n'utilise **pas** `PricingEngine` → règles tiered/seasonal ignorées

**Constat.** Le service recalcule les subtotaux ligne-par-ligne (l. 596-604) avec `unit_price_cents` × `discount_pct` × `rental_days`. **Aucun appel** à `PricingEngine.apply_rules`. Si l'admin a configuré une règle "saisonnier -15% en juillet", elle ne s'applique **pas** à la conversion devis→réservation.

**Conséquence** : drift business : la simulation `/pricing/simulate` au moment de l'édition devis montre un prix avec règles, mais le devis stocke `unit_price_cents` après simulation manuelle. Si admin n'a pas re-simulé après ajout de règle, le devis garde l'ancien prix.

**Action** : appeler `PricingEngine.apply_rules` à `convert_to_reservation` ou à minima au moment de `accept` pour figer le prix avec règles.

---

#### F561 — `tva_rate / 10000 if devis.tva_rate else 0.20` hardcoded fallback Marveline

**Constat.** `services/devis.py:679` :
```python
tva_rate=devis.tva_rate / 10000 if devis.tva_rate else 0.20,
```

Si `devis.tva_rate=0` (admin oublié, NULL, valeur 0), fallback **20%**. Pour Restaurant (10%) ou Épicerie (5.5%), facturation erronée silencieuse.

Pattern récurrent : cf. F196 (mod. 07), F487 (mod. 15).

**Action** : exiger `tva_rate NOT NULL > 0` au schema validation + supprimer le fallback magique.

---

#### F562 — Statut `expired` jamais auto-déclenché (pas de Celery `expire_old_devis`)

**Constat.** `DevisStatus.EXPIRED` est référencé dans la FSM (transitions depuis `sent` et `negotiation`). Le service expose `expire(devis_id)` (l. 357-364) appelé manuellement. **Aucun job périodique** ne scanne `WHERE valid_until < today AND status IN (sent, negotiation)`.

**Conséquence** : un devis avec `valid_until=2025-01-01` reste en `sent` indéfiniment. Le client peut "accepter" un devis expiré.

**Action** : Celery beat job quotidien `expire_devis_task` qui flip status + envoi email "votre devis a expiré".

---

#### F563 — `add_signature` ne transite **pas** auto vers `accepted` → devis signé reste `sent`

**Constat.** `services/devis.py:1008-1031` :
```python
if devis.status != DevisStatus.SENT:
    raise HTTPException(400, ...)
devis.signature_url = signature_data
devis.signed_at = datetime.now()
# ⚠ Pas de devis.status = DevisStatus.ACCEPTED
```

Le client signe → frontend reçoit OK 200 → admin voit devis encore `sent` → confusion : "le client a-t-il signé ?". Pour confirmer, l'admin doit cliquer "Marquer comme accepté" séparément.

**Action** : `devis.status = DevisStatus.ACCEPTED` après `signed_at` set, avec validation FSM.

---

#### F564 — `_generate_res_reference` race + retry max 3 (anti-pattern)

**Constat.** `services/devis.py:537-553, 622-667` : SELECT max counter → +1, retry sur IntegrityError. Pour 4+ conversions simultanées, échec 409. Anti-pattern : utiliser `SEQUENCE` PostgreSQL ou `UPDATE counter_table FOR UPDATE`.

---

#### F565 — `discount_pct` ligne et global appliqués **multiplicativement** (non documenté)

**Constat.** `services/devis.py:599-602` :
```python
if line_discount:
    subtotal = subtotal * (10000 - line_discount) // 10000
if global_discount:
    subtotal = subtotal * (10000 - global_discount) // 10000
```

Ligne `discount_pct=5000` (50%) + global `5000` (50%) = subtotal × 0.5 × 0.5 = **0.25** (75% remise). Si l'admin pense additivement (50% + 50% = 100%), drift business surprenant.

**Action** : décision et docs explicites : multiplicatif vs additif vs prend-le-max.

---

### 3.2 P1

#### F566 — Comment l. 36 vs code l. 253 — convention `tva_rate` ambiguë

Le commentaire model dit `tva_rate=2000` = "20.00%". Mais le code utilise `// 10000` → 2000/10000 = 0.20 = 20%. Cohérent en effet, mais le comment "centièmes de %" est trompeur (en réalité dix-millièmes).

---

#### F567 — `Devis.tva_rate` vs `Product.tva_rate` (drift potentiel)

`Devis.tva_rate` (par devis) vs `Product.tva_rate` (par produit, mod. 15). Quel prime ? Le code utilise `devis.tva_rate` pour la facturation (l. 253). Donc `Product.tva_rate` est ignoré.

**Conséquence** : un devis avec un produit Restaurant (TVA 10%) et un produit Marveline (TVA 20%) → un seul taux global appliqué. **Multi-TVA par devis impossible**.

---

#### F568 — `update` n'inclut pas `delivery_fee_cents` dans le total quand pas de `lines_data`

`services/devis.py:257-259` : si seulement `discount_pct/tva_rate` modifiés sans `lines`, `recalculate_amounts` est appelée — vérifier qu'elle inclut `delivery_fee_cents` (à confirmer).

---

#### F569 — `Devis.converted_reservation_id` Integer **sans FK SQL** (orphelin possible)

Cf. model l. 184-189 : "FK sans contrainte ORM pour éviter dépendance circulaire". Une réservation supprimée (ou jamais créée à cause de F559) laisse `converted_reservation_id` pointant dans le vide.

**Action** : FK SQL avec `ondelete="SET NULL"` + résoudre la circular import autrement (lazy string ref SQLAlchemy supporte).

---

#### F570 — `signature_url` String(500) stocke **base64 PNG inline** → tronquage

`models/devis.py:129-132` "URL du fichier de signature électronique (base64 PNG stocké)". Un PNG signature 200×80px = 4-8 KB base64 = 6-12 KB. **String(500) tronqué silencieusement à 500 chars**.

**Action** : Text colonne ou stockage filesystem dédié.

---

#### F571 — `DevisAttachment.file_path` storage local `/uploads/devis/{id}/` (pas S3)

**Constat.** Bloque scaling horizontal multi-replicas (chaque worker FastAPI doit accéder au même filesystem). Marveline = VPS unique → OK. SaaS = bloquant.

---

#### F572 — `DevisModule.module_type` enum 5 valeurs Marveline-spécifique

`socle, stock, facturation, securite, services` — tous événementiels. Restaurant/Épicerie/Splendid n'auront pas ces "modules".

---

#### F573 — `convert_to_reservation` ne valide pas que `delivery_date >= today`

Conversion d'un vieux devis avec dates passées → réservation rétroactive — incohérent avec FSM Reservation.

---

#### F574 — Notification email auto au `send` à confirmer mod. 27 (probablement absente)

---

#### F575 — `DevisLineHistory.old_values/new_values` JSON non chiffrés (PII labels)

---

#### F576 — `Devis.notes` + `message_accompagnement` Text non chiffrés (PII commercial)

---

#### F577 — `DevisVersion.snapshot_json` peut excéder MB pour gros devis (50+ lignes)

Pas d'index GIN sur le champ JSONB. Recherches "trouver tous les devis ayant contenu produit X" impossible.

---

#### F578 — Pas de pagination sur `list_versions`, `list_negotiations`

Pour un devis avec 20+ versions ou 50+ messages négociation, chargement complet → lag UI.

---

#### F579 — `DevisLine.product_id ondelete=SET NULL` → ligne devient orpheline

Si l'admin supprime un produit, toutes les lignes de devis qui le référencent perdent leur `product_id` mais conservent `label` + `unit_price_cents` → reporting "ventes par produit" cassé.

**Action** : `RESTRICT` au lieu de `SET NULL` ; soft-delete only sur Product.

---

#### F580 — `DevisLine.bundle_id` SET NULL idem

---

#### F581 — `DevisLine.variant_id RESTRICT` → impossible de soft-delete une variant si jamais utilisée

---

#### F582 — Pas d'audit log structurel sur `convert_to_reservation`, `accept`, `refuse` (juste `logger.info`)

---

#### F583 — Pas de CHECK `caution_amount_cents IS NULL OR caution_amount_cents >= 0`

---

### 3.3 P2

#### F584 — Pas de validation `valid_until >= today` à la création

#### F585 — `event_date` Optional → devis sans date événement OK (acceptable pour brouillon)

#### F586 — Pas de CHECK `return_date >= delivery_date` au niveau Devis (existe sur DevisPhase)

#### F587 — `DevisLineHistory.devis_line_id Integer nullable` vs convention BigInteger

#### F588 — `signature_url` set sans `signed_at` cohérent — pas de CHECK couplant les deux

#### F589 — `DevisVersion.created_at` Mapped sans `server_default=func.now()`

#### F590 — `delivery_status` 3 valeurs avec mélange `a_cadrer/en_cours/livre` (français sans accents)

#### F591 — `module_type` valeurs sans accents (`securite` au lieu de `sécurité`)

#### F592 — Pas de schéma `DevisLineHistoryResponse` (historique non exposé)

#### F593 — Docstring `update` dit "brouillon uniquement" mais code accepte aussi `version_pending` (l. 188)

#### F594 — Pas de rate limit sur `add_signature` (anti-fraude / replay)

---

### 3.4 P3

#### F595 — Format reference `DEV-YYYY-NNNN` hardcoded

#### F596 — `create_version_snapshot` non exposée en endpoint admin séparé

#### F597 — `DevisChangeRequest.author_id` BigInteger sans FK accounts

---

## 4. Synthèse module 17

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 8 | F558 (no reserve_stock), F559 (no FOR UPDATE), F560 (no PricingEngine), F561 (tva fallback 0.20), F562 (no expire job), F563 (signature ne transite pas), F564 (race reference), F565 (discount cumul multiplicatif) |
| P1 | 18 | F566 → F583 |
| P2 | 11 | F584 → F594 |
| P3 | 3 | F595 → F597 |
| **Total** | **40** | F558 → F597 |

**Compteur cumulé après module 17** : ≈ 557 + 40 = **597 frictions**.

---

## 5. Décision architecturale

> **P0 immédiat** : (1) appeler `reserve_stock` à `convert_to_reservation` (F558) ; (2) `FOR UPDATE` (F559) ; (3) intégrer PricingEngine à la conversion (F560) ; (4) supprimer fallback tva 0.20 (F561) ; (5) Celery `expire_devis_task` (F562) ; (6) auto-transition `signed → accepted` (F563).
>
> **Refactor** : SEQUENCE PostgreSQL pour reference (F564) ; storage signature en Text/S3 (F570) ; FK explicite `converted_reservation_id` (F569).

# AUDIT PROFOND — Modules metier Marveline

> Date : 2026-03-26
> Methode : Lecture integrale de chaque fichier (pages, composants, API, backend, stores)
> Zero supposition — chaque point est reference par fichier:ligne

---

## SYNTHESE DES BUGS

| Module | Bugs P1-P2 | Bugs P3 | Code mort | Gaps F/B |
|---|---|---|---|---|
| Operations | 6 | 8 | 4 | 8 |
| Reservations | 5 | 4 | 9 | 7 |
| Devis | 10 | 12 | 4 | 3 |
| **Total** | **21** | **24** | **17** | **18** |

---

## MODULE 1 — OPERATIONS (depart / retour / scan)

### Bugs P1-P2

**OPS-BUG-1 (P2)** — Cle d'item par addition arithmetique
`DepartureInventoryPage.tsx:96`
```
const itemKey = (item) => item.line_id + item.product_id
```
Addition numerique, pas concatenation. line_id=1 + product_id=10 = 11, identique a line_id=5 + product_id=6. Collision → deux items partagent le meme state local. `ReturnInventoryPage` utilise correctement `` `${item.line_id}-${item.product_id}` ``.

**OPS-BUG-2 (P2)** — Subtitle template literal non evalue
`DepartureInventoryPage.tsx:256`
```
subtitle="{data.reference ?? `Reservation #${resId}`}"
```
String JSX entre guillemets, pas une expression. Affiche les accolades comme texte.

**OPS-BUG-3 (P2)** — Raison de blocage depart ignoree par le backend
`app/api/v1/endpoints/operations.py:72` — recoit `DepartureBlockRequest.reason` mais appelle `ops_svc.block_departure(reservation_id, tenant_id, db)` sans passer `data.reason`. La raison saisie par l'operateur est perdue silencieusement.

**OPS-BUG-4 (P1)** — Double creation de dommages au retour
`ReturnInventoryPage.tsx` + `DamageDeclarationModal.tsx`
1. Operateur ouvre le modal → `POST /return/{id}/damage` → dommage cree en base
2. Callback `onDeclared` ajoute le dommage a `itemStates`
3. Operateur valide le retour → `POST /return/{id}` avec `items[].damages` contenant le meme dommage
4. `_process_return_items` cree a nouveau le dommage
Resultat : dommage en double, double InvoiceCharge sur la facture.

**OPS-BUG-5 (P2)** — "X/Y articles charges" affiche des pre-checks
`app/services/operations.py` `get_departure_state` — `total` et `checked` comptent les `ReservationPreCheckItem`, pas les articles. Le hero card affiche "articles charges" avec des chiffres de pre-checks. Libelle trompeur.

**OPS-BUG-6 (P2)** — Alerte mensongere ArticleCheckPage
`ArticleCheckPage.tsx:229`
```
"Dommage detecte. Une declaration sera creee automatiquement a la validation."
```
Faux. `_validate_departure_items` bloque la validation (400) si condition = `damaged` ou `missing`. Aucune declaration automatique.

### Bugs P3

**OPS-BUG-7** — Redirect post-retour vers `/stock/items` au lieu de `/reservations/$id` ou `/operations`
`ReturnInventoryPage.tsx:246`

**OPS-BUG-8** — `DepartureBlockedPage.tsx` = page orpheline (jamais montee sur une route)

**OPS-BUG-9** — Deux boutons identiques "Article par article" et "Controle legal" (meme `to`, memes params)
`DepartureInventoryPage.tsx:321-339`

**OPS-BUG-10** — `note` dans ArticleCheckPage perdu silencieusement (state local, pas envoye dans `updateDepartureItem`)

**OPS-BUG-11** — Bouton "Prendre une photo" sans onClick (stub sans ticket)
`ArticleCheckPage.tsx:206`

**OPS-BUG-12** — `useResolveQr` defini mais jamais appele. Backend `GET /qr/{code}` implemente. ScanPage parse le QR localement.

**OPS-BUG-13** — `operationsStore` persiste en localStorage mais quasi-inutilise. Les pages principales utilisent `useState` local. Seul `ArticleCheckPage` utilise `updateDepartureItem`.

**OPS-BUG-14** — `can_depart` toujours false pour statuts `confirmed` et `confirmed_risk` (prechecks_ok exige `status == pre_check`). L'item s'affiche dans la liste des departs mais la validation est impossible.

### Gaps frontend/backend

| Gap | Detail |
|---|---|
| QR scan deconnecte | Frontend parse QR localement (format `departure:42`). Backend resout par `serial_number` (StockItem). Si QR imprimes = serial numbers, le scan ne fonctionne pas. |
| Photo ArticleCheck | Bouton present, endpoint `POST /damage/photo` implemente, connexion manquante |
| Signature optionnelle | Backend stocke si fourni, aucune regle metier ne l'exige |
| ReturnState sans dommages precedents | `GET /return/{id}` ne retourne pas les dommages deja declares via le flux standalone |
| `quantity_returned` non persistee | `_process_return_items` recoit la quantite mais ne met a jour aucun champ de stock avec |
| `staleTime: 0` sur queries depart/retour | Refetch a chaque montage (navigation entre pages) |
| Navigation incoherente | Dashboard OpCard → `/reservations/$id` (pas `/operations/departure/$id`). ScanPage retour → `/reservations` (pas `/operations`) |
| Statut `confirmed_risk` dans departs | Apparait dans la liste mais validation impossible (can_depart = false) |

---

## MODULE 2 — RESERVATIONS

### Probleme architectural majeur

**Deux systemes de detail coexistent :**
- `/reservations/$id/` → `ReservationDetailPage.tsx` (ancienne page monolithique)
- `/reservations/$id/$phase` → 13 pages phases (nouveau systeme)

`ReservationRouter` redirige depuis `/$id/index` vers `/$id/$phase`, mais la route `$id/index.lazy.tsx` cable `ReservationDetailPage`. Acceder directement a `/reservations/42` charge l'ancienne page.

### Bugs P1-P2

**RES-BUG-1 (P1)** — Ancienne page : litige appelle le mauvais endpoint
`ReservationDetailPage.tsx` PhaseCTA pour `dispute` appelle `complete.mutate(resId)` → `POST /complete`. La transition correcte est `close-dispute` → `POST /close-dispute` (returned_dispute → returned). L'ancienne page court-circuite la machine d'etats.

**RES-BUG-2 (P1)** — Phases `prete` et `legal` inatteignables
`derivePhase()` dans `ReservationRouter.tsx` ne retourne jamais `'prete'` ni `'legal'`. Ces pages existent, sont codees, mais ne peuvent pas etre affichees via le routeur automatique. `PretePage` et `LegalPage` = code mort fonctionnel.

**RES-BUG-3 (P2)** — `deliver` bypass le workflow inventaire
`PretePage` et `PrecheckPage` proposent "Marquer livree" (mutation directe `POST /deliver`) ET "Depart operationnel" (navigate vers `/operations/departure`). L'utilisateur peut passer en `delivered` sans mouvement d'inventaire.

**RES-BUG-4 (P2)** — LegalPage : "Contact jour J" toujours false
`LegalPage.tsx:31` — `ok: false` hardcode. Ce champ est toujours en rouge quelle que soit la reservation.

**RES-BUG-5 (P2)** — FocusPills completed : donnees hardcodees
Pour `completed` : affiche "Caution: Restituee" et "Dommages: Aucun" sans verifier les depots ou les mouvements de dommages. Donnees presentees comme factuelles alors qu'elles sont statiques.

### Bugs P3

**RES-BUG-6** — `hasNavigated` ref empeche la re-navigation apres mutation dans ReservationRouter. Changement de statut via mutation → pas de navigation vers la nouvelle phase.

**RES-BUG-7** — `useReservationDeposits` charge dans ReservationRouter mais `_deposits` n'est jamais utilise dans `derivePhase()`. Fetch inutile.

**RES-BUG-8** — Double import `useRemindReservationDeposit` dans `ConfirmeePage.tsx:5-6`.

**RES-BUG-9** — DepositSection sur `terminee` permet encore "Enregistrer caution" meme si reservation completed.

### Code mort

| Element | Detail |
|---|---|
| `PretePage.tsx` | Phase jamais produite par derivePhase |
| `LegalPage.tsx` | Phase jamais produite par derivePhase |
| `allOk` dans BrouillonIncompletPage | Calcule, jamais utilise dans le rendu |
| `reservationStore.transition()` | Machine d'etats non appelee par aucune page |
| `reservationStore.canTransition()` | Idem |
| `reservationStore.setDetail/setList/etc` | Non utilises par les pages phases |
| `useReservationFull` | Hook existant, aucune page ne le consomme |
| `completed: action: () => {}` dans ReservationDetailPage | Bouton Archiver = stub vide |
| Route `/$id/phases` → EventDetailPage | Alias ancien systeme |

### Incoherences machine d'etats

| Situation | Store | Backend | Frontend |
|---|---|---|---|
| confirmed → delivered | Autorise | Autorise | Via operations OU bypass direct |
| confirmed_risk → delivered | Non liste | Autorise (deliver accepte confirmed_risk) | Aucun CTA ne le propose |
| returned_dispute → completed | Non autorise | Non autorise | Ancienne page le fait (BUG-1) |
| confirmed_risk → pre_check | Autorise | Autorise | Pas de CTA depuis RisquePage |

### Gaps

| Gap | Detail |
|---|---|
| RisquePage sans progression | Pas de bouton pour avancer vers pre_check ou delivered depuis confirmed_risk. Seules options : relancer ou annuler |
| RetourneePage → retour redondant | "Signaler dommage" navigue vers `/operations/return/$id` qui est le flow de retour initial. Peut creer des doublons |
| assigned_to_me = string | Frontend envoie `'true'` (string), backend attend `bool`. FastAPI cast correctement mais fragile |
| ConfirmeePage sans CTA avancer | Pas de bouton pre-check ou depart. L'utilisateur doit utiliser QuickLinks |

---

## MODULE 3 — DEVIS

### Bugs P2

**DEV-BUG-1 (P2)** — TVA affichee x100
`DevisLinesTable.tsx:51` — `tva_rate * 100`. Backend stocke 20 (pour 20%). Affiche `2000%`.

**DEV-BUG-2 (P2)** — DevisSourcePage : champs financiers toujours `—`
`DevisSourcePage.tsx:107-108` — lit `total_ht_cents` et `tva_amount_cents`. Backend renvoie `subtotal_cents` et `tva_cents`. Les casts `as` masquent l'erreur.

**DEV-BUG-3 (P2)** — DevisRefuseModal : contexte toujours vide
Props `devisNumber`, `totalAmountCents`, `customerName` declarees mais jamais transmises par le parent. Modal affiche des champs vides.

**DEV-BUG-4 (P2)** — Diff versions casse pour lignes libres
`DevisVersionsTab.tsx` `toLineKey()` : lignes sans product_id ni bundle_id → cle `p:undefined`. Toutes les lignes libres collapsent sous la meme cle.

**DEV-BUG-5 (P2)** — Upload attachments bypass le client API
`api/devis.ts` `uploadAttachment` utilise `fetch()` natif sans refresh token, sans gestion erreur coherente, URL hardcodee `/api/v1/`.

**DEV-BUG-6 (P2)** — `canSend` bloque l'envoi sur `version_pending`
`DevisActions.tsx` : `canSend = status === 'draft'`. `DevisDetailPage.getPrimaryAction()` : `status === 'draft' || status === 'version_pending'` → retourne 'send'. Incoherence entre le layout et le composant d'actions.

**DEV-BUG-7 (P2)** — Signature : frontend l'expose sur `accepted`, backend l'exige sur `sent`
`DevisDetailsTab.tsx` affiche le pad sans verifier le statut. Signer un devis `accepted` → erreur backend 400 non geree.

**DEV-BUG-8 (P2)** — `variant_label` toujours null dans BundlePreviewPanel
Backend `preview_bundle_items` : `variant_label=None` hardcode, pas de `selectinload` pour variant.

**DEV-BUG-9 (P2)** — Suppression fichier attachments avant commit DB
`devis.py:962` — `os.remove(file_path)` puis commit. Si commit echoue, fichier perdu mais entree DB reste.

**DEV-BUG-10 (P2)** — `conclude_negotiation` backend sans page frontend
`POST /{id}/negotiation/conclude` existe cote backend mais n'est appele nulle part cote frontend. Transition formelle non exposee.

### Bugs P3

**DEV-BUG-11** — 5 subtitles affichent les accolades JSX comme texte
`DevisListPage:159`, `DevisCreatePage:123`, `DevisNegotiationPage:69`, `DevisModulesPage:128`, `DevisPhasesPage:136`

**DEV-BUG-12** — BundlePreviewPanel : prix formate a la main (pas `formatCents`)

**DEV-BUG-13** — `renew` : `date.today()` dependance fuseau serveur

**DEV-BUG-14** — Modules : DevisSourcePage lit `devis.modules` embedded, DevisModulesPage appelle GET separe. Desync cache possible.

**DEV-BUG-15** — 4 champs editables a la creation mais pas a l'edition (`conditions_paiement`, `message_accompagnement`, `tva_rate`, `discount_pct`)

**DEV-BUG-16** — `action: 'convert'` navigate mais jamais consomme par la page cible

**DEV-BUG-17** — `addNegotiationEntry` perd la reponse backend (retourne void au lieu de DevisNegotiationResponse)

### Code mort

| Element | Detail |
|---|---|
| `devisStore.ts` ~90% | transition, canTransition, setList, setStep, nextStep, prevStep — jamais appeles |
| `formatCents` import dans DevisRefuseModal | Jamais appele |
| `devisId` prop dans DevisNegotiationSummary | Declaree, jamais utilisee |
| `Loader2` import dans DevisLineHistory | Jamais utilise dans le JSX |

### Architecture — double implementation

`DevisDetailPage.tsx` et `DevisIdLayout.tsx` sont deux implementations paralleles de la meme page (chargent les memes hooks, gerent les memes modals, calculent les memes actions). SubNav de `DevisIdLayout` expose 3/9 pages.

---

## RESUME GLOBAL — Les vrais problemes

### Architecture (a trancher)

1. **Reservations : double systeme actif** — ancienne page monolithique + nouveau systeme 13 phases. L'ancienne page a un bug metier actif (litige → mauvais endpoint).
2. **Devis : double implementation** — DevisDetailPage + DevisIdLayout. SubNav 3/9 pages.
3. **Stores machines d'etats = code mort** — Les 3 stores (reservation, devis, vente) definissent des transitions jamais appelees.

### Bugs metier (impact utilisateur direct)

4. **Double creation dommages au retour** (OPS-BUG-4) — facture incorrecte
5. **Litige appelle le mauvais endpoint** (RES-BUG-1) — transition illegale
6. **TVA affichee x100** (DEV-BUG-1) — donnees financieres fausses
7. **Champs financiers source toujours vides** (DEV-BUG-2)
8. **deliver bypass inventaire** (RES-BUG-3) — stock non mis a jour
9. **Raison blocage depart perdue** (OPS-BUG-3)

### UX (confusion utilisateur)

10. **Phases prete/legal inatteignables** — pages codees mais jamais affichees
11. **ConfirmeePage et RisquePage sans CTA avancer** — l'utilisateur est bloque
12. **"Articles charges" affiche des pre-checks** (OPS-BUG-5)
13. **QR scan deconnecte du backend** — parse local vs resolution serial_number
14. **Redirect post-retour vers /stock/items** au lieu de la reservation
15. **FocusPills completed = donnees fictives** — "Caution restituee" sans verification

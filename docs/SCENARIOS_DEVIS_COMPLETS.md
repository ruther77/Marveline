# Marveline — Scenarios complets : du Devis au Retour

> Deux parcours reels, tous les etats, tous les flux, rien d'oublie.
> Chaque action est mappee sur son endpoint backend et son hook frontend.

---

## Table des matieres

1. [Scenario A — Best Case (le mariage parfait)](#scenario-a--best-case)
2. [Scenario B — Worst Case (l'enfer logistique)](#scenario-b--worst-case)
3. [Reference : tous les etats et transitions](#reference--etats-et-transitions)
4. [Reference : tous les flux annexes](#reference--flux-annexes)
5. [Mapping Endpoint → Hook Frontend](#mapping-endpoint--hook-frontend)
6. [Matrice des declencheurs automatiques](#matrice-des-declencheurs-automatiques)
7. [Checklist "rien oublie"](#checklist-rien-oublie)

---

## Scenario A — Best Case

**Contexte** : Mariage de Claire & Thomas, 120 invites, domaine en campagne, date dans 4 mois.

### Etape 1 — Premier contact & Devis

| # | Action | Endpoint | Hook Frontend | Etat |
|---|--------|----------|---------------|------|
| 1.1 | Creation devis | `POST /api/v1/devis` | `useCreateDevis()` | → `draft` |
| 1.2 | Ajout lignes (produits) | via body `DevisCreate.lines[]` | inclus dans `useCreateDevis()` | `draft` |
| 1.3 | Ajout infos evenement | `PATCH /api/v1/devis/{id}` | `useUpdateDevis()` | `draft` |
| 1.4 | Lecture recap | `GET /api/v1/devis/{id}` | `useDevisDetail(id)` | `draft` |
| 1.5 | Envoi au client | `POST /api/v1/devis/{id}/send` | `useSendDevis()` | → `sent` |

### Etape 2 — Acceptation directe

| # | Action | Endpoint | Hook Frontend | Etat |
|---|--------|----------|---------------|------|
| 2.1 | Signature electronique | `POST /api/v1/devis/{id}/signature` | `useSignDevis()` | `sent` |
| 2.2 | Acceptation | `POST /api/v1/devis/{id}/accept` | `useAcceptDevis()` | → `accepted` |
| 2.3 | Versions snapshot | `GET /api/v1/devis/{id}/versions` | `useDevisVersions(id)` | — |

### Etape 3 — Conversion en Reservation

| # | Action | Endpoint | Hook Frontend | Etat Devis → Reservation |
|---|--------|----------|---------------|--------------------------|
| 3.1 | Conversion | `POST /api/v1/devis/{id}/convert` | `useConvertDevis()` | `converted` → RES `draft` |

### Etape 4 — Confirmation & Facturation

| # | Action | Endpoint | Hook Frontend | Detail |
|---|--------|----------|---------------|--------|
| 4.1 | Confirmation reservation | `POST /api/v1/reservations/{id}/confirm` | `useConfirmReservation()` | → `pre_check` |
| 4.2 | (auto) Facture acompte creee | — (side-effect du confirm) | — | INV type=advance, 40% |
| 4.3 | (auto) Facture solde creee | — (side-effect du confirm) | — | INV type=balance, 60% |
| 4.4 | (auto) Depot/Caution | — (side-effect du confirm) | — | Deposit status=held, 3x TTC |
| 4.5 | (auto) Mouvement DEPART | — (side-effect du confirm) | — | Movement type=departure, scheduled |
| 4.6 | Lecture pre-check items | `GET /api/v1/reservations/{id}/pre-check` | `useReservationPreCheck(id)` | — |
| 4.7 | Valider items pre-check | `PATCH /api/v1/reservations/{id}/pre-check/{item_id}` | `useUpdatePreCheckItem()` | checked=true |
| 4.8 | Lecture factures | `GET /api/v1/invoices?reservation_id={id}` | `useInvoices({ reservation_id })` | — |
| 4.9 | Envoi facture acompte | `POST /api/v1/invoices/{id}/mark-sent` | `useMarkInvoiceSent()` | INV → `sent` |
| 4.10 | Paiement acompte | `POST /api/v1/invoices/{id}/payments` | `useAddInvoicePayment()` | method=transfer |
| 4.11 | Lecture cautions | `GET /api/v1/reservations/{id}/deposits` | `useReservationDeposits(id)` | — |

### Etape 5 — Depart materiel

| # | Action | Endpoint | Hook Frontend | Detail |
|---|--------|----------|---------------|--------|
| 5.1 | Lecture etat depart | `GET /api/v1/operations/departure/{res_id}` | `useDepartureState(id)` | — |
| 5.2 | Valider depart | `POST /api/v1/operations/departure/{res_id}` | `useValidateDeparture()` | → reservation `delivered` |
| 5.3 | (auto) Stock → on_location | — (side-effect) | — | StockItem: reserved → on_location |

### Etape 6 — Evenement

Rien cote systeme.

### Etape 7 — Retour materiel (OK)

| # | Action | Endpoint | Hook Frontend | Detail |
|---|--------|----------|---------------|--------|
| 7.1 | Lecture etat retour | `GET /api/v1/operations/return/{res_id}` | `useReturnState(id)` | — |
| 7.2 | Valider retour (tout OK) | `POST /api/v1/operations/return/{res_id}` | `useValidateReturn()` | → reservation `returned` |
| 7.3 | (auto) Stock → available | — (side-effect) | — | StockItem: on_location → available |

### Etape 8 — Cloture

| # | Action | Endpoint | Hook Frontend | Detail |
|---|--------|----------|---------------|--------|
| 8.1 | Envoi facture solde | `POST /api/v1/invoices/{id}/mark-sent` | `useMarkInvoiceSent()` | INV balance → `sent` |
| 8.2 | Paiement solde | `POST /api/v1/invoices/{id}/payments` | `useAddInvoicePayment()` | → INV `paid` |
| 8.3 | Restitution caution | `PATCH /api/v1/reservations/{id}/deposits/{dep_id}` | `useUpdateDeposit()` | held → released |
| 8.4 | Completion | `POST /api/v1/reservations/{id}/complete` | `useCompleteReservation()` | → `completed` |

**Timeline** : ~4 mois. **Endpoints utilises** : 18 appels API distincts.

---

## Scenario B — Worst Case

**Contexte** : Entreprise EventPro, seminaire corporate 80 personnes, demande urgente (3 semaines), interlocuteur indecis, budget serre.

### Etape 1 — Devis et negociations multiples

| # | Action | Endpoint | Hook Frontend | Etat |
|---|--------|----------|---------------|------|
| 1.1 | Creation devis | `POST /api/v1/devis` | `useCreateDevis()` | → `draft` |
| 1.2 | Envoi V1 | `POST /api/v1/devis/{id}/send` | `useSendDevis()` | → `sent` |
| 1.3 | Debut negociation | `POST /api/v1/devis/{id}/negotiation/start` | `useStartNegotiation()` | → `negotiation` |
| 1.4 | Message negociation | `POST /api/v1/devis/{id}/negotiation` | `useAddNegotiationEntry()` | — |
| 1.5 | Demande modification | `POST /api/v1/devis/{id}/change-request` | `useRequestChange()` | — |
| 1.6 | Passer en version_pending | `POST /api/v1/devis/{id}/version-pending` | `useVersionPendingDevis()` | → `version_pending` |
| 1.7 | Mise a jour lignes V2 | `PATCH /api/v1/devis/{id}` | `useUpdateDevis()` | `version_pending` |
| 1.8 | Envoi V2 | `POST /api/v1/devis/{id}/send` | `useSendDevis()` | → `sent` |
| 1.9 | Re-negociation | `POST /api/v1/devis/{id}/negotiation/start` | `useStartNegotiation()` | → `negotiation` |
| 1.10 | V3 : update + send | `PATCH` + `POST .../send` | `useUpdateDevis()` + `useSendDevis()` | → `sent` |
| 1.11 | Lecture versions | `GET /api/v1/devis/{id}/versions` | `useDevisVersions(id)` | 3 snapshots |
| 1.12 | Signature + accept | `POST .../signature` + `POST .../accept` | `useSignDevis()` + `useAcceptDevis()` | → `accepted` |

### Etape 2 — Conversion tardive + Risques

| # | Action | Endpoint | Hook Frontend | Detail |
|---|--------|----------|---------------|--------|
| 2.1 | Conversion | `POST /api/v1/devis/{id}/convert` | `useConvertDevis()` | → RES `draft` |
| 2.2 | Confirmation | `POST /api/v1/reservations/{id}/confirm` | `useConfirmReservation()` | → `pre_check` |
| 2.3 | (auto) Risque delai cree | — (side-effect) | — | blocking=true |
| 2.4 | Lecture risques | `GET /api/v1/reservations/{id}/risks` | `useReservationRisks(id)` | — |
| 2.5 | Bloquer depart | `POST /api/v1/operations/departure/{id}/block` | `useBlockDeparture()` | → `confirmed_risk` |
| 2.6 | Modifier lignes reservation | `POST /api/v1/reservations/{id}/lines` | `useAddReservationLine()` | remplacement nappes |
| 2.7 | Supprimer ligne initiale | `DELETE /api/v1/reservations/{id}/lines/{line_id}` | `useRemoveReservationLine()` | — |
| 2.8 | Resoudre risque | `PATCH /api/v1/reservations/{id}/risks/{risk_id}` | `useUpdateReservationRisk()` | resolved_at=now |
| 2.9 | Creer depot caution | `POST /api/v1/reservations/{id}/deposits` | `useCreateDeposit()` | 3x TTC, held |
| 2.10 | Resoudre 2eme risque | `PATCH /api/v1/reservations/{id}/risks/{risk_id}` | `useUpdateReservationRisk()` | → retour `pre_check` |

### Etape 3 — Facture acompte + retard paiement

| # | Action | Endpoint | Hook Frontend | Detail |
|---|--------|----------|---------------|--------|
| 3.1 | Envoi facture acompte | `POST /api/v1/invoices/{id}/mark-sent` | `useMarkInvoiceSent()` | → `sent` |
| 3.2 | (auto) Overdue | detection cron / `GET /api/v1/invoices/overdue` | `useOverdueInvoices()` | → `overdue` |
| 3.3 | Planifier relance email | `POST /api/v1/relances/schedule` | `useScheduleRelance()` | channel=email |
| 3.4 | Marquer relance envoyee | `POST /api/v1/relances/mark-sent/{id}` | `useMarkRelanceSent()` | — |
| 3.5 | Planifier relance SMS | `POST /api/v1/relances/schedule` | `useScheduleRelance()` | channel=sms |
| 3.6 | Paiement tardif | `POST /api/v1/invoices/{id}/payments` | `useAddInvoicePayment()` | method=card, → `paid` |

### Etape 4 — Depart chaotique

| # | Action | Endpoint | Hook Frontend | Detail |
|---|--------|----------|---------------|--------|
| 4.1 | Lecture pre-check | `GET /api/v1/reservations/{id}/pre-check` | `useReservationPreCheck(id)` | 2 items non-coches |
| 4.2 | Force depart | `POST /api/v1/operations/departure/{id}` | `useValidateDeparture()` | → `delivered` |
| 4.3 | Lecture mouvements | `GET /api/v1/inventory-movements?reservation_id={id}` | `useMovements({ reservation_id })` | — |
| 4.4 | MaJ quantite effective | `PATCH /api/v1/inventory-movements/{id}/items/{item_id}` | `useUpdateMovementItem()` | qty_actual=8 (vs 10) |
| 4.5 | Completer mouvement | `PATCH /api/v1/inventory-movements/{id}/complete` | `useCompleteMovement()` | → `completed` |

### Etape 5 — Prolongation (Extension)

| # | Action | Endpoint | Hook Frontend | Detail |
|---|--------|----------|---------------|--------|
| 5.1 | Creer extension | `POST /api/v1/reservations/{id}/extend` | `useExtendReservation()` | +1 jour, extra_charge |
| 5.2 | (auto) Charge LABOR | — (side-effect de extend) | — | InvoiceCharge ajoutee |
| 5.3 | Lecture detail complet | `GET /api/v1/reservations/{id}/full` | `useReservationFull(id)` | risks+precheck+ext |

### Etape 6 — Retour avec degats

| # | Action | Endpoint | Hook Frontend | Detail |
|---|--------|----------|---------------|--------|
| 6.1 | Lecture etat retour | `GET /api/v1/operations/return/{id}` | `useReturnState(id)` | — |
| 6.2 | Declarer degat 1 (assiettes) | `POST /api/v1/operations/return/{id}/damage` | `useDeclareCasse()` | 5 assiettes, type="Assiette cassee" |
| 6.3 | Upload photo degat | `POST /api/v1/operations/damage/photo` | `useUploadDamagePhoto()` | multipart file |
| 6.4 | Declarer degat 2 (nappe) | `POST /api/v1/operations/return/{id}/damage` | `useDeclareCasse()` | 1 nappe tachee |
| 6.5 | Declarer manque (verres) | `POST /api/v1/operations/return/{id}/damage` | `useDeclareCasse()` | 3 verres missing |
| 6.6 | Valider retour (avec dispute) | `POST /api/v1/operations/return/{id}` | `useValidateReturn()` | → `returned_dispute` |
| 6.7 | (auto) InvoiceCharge DAMAGE | — (side-effect) | — | 75€ + 45€ + 24€ = 144€ |
| 6.8 | (auto) Stock → damaged/retired | — (side-effect) | — | 5 assiettes + 1 nappe → damaged, 3 verres → retired |
| 6.9 | Resoudre litige | `POST /api/v1/reservations/{id}/close-dispute` | `useCloseReservationDispute()` | → `returned` |

### Etape 7 — Facturation finale penible

| # | Action | Endpoint | Hook Frontend | Detail |
|---|--------|----------|---------------|--------|
| 7.1 | Lecture facture avec charges | `GET /api/v1/invoices/{id}/full` | `useInvoiceFull(id)` | balance + charges |
| 7.2 | Envoi facture solde | `POST /api/v1/invoices/{id}/mark-sent` | `useMarkInvoiceSent()` | → `sent` |
| 7.3 | Creer avoir partiel | `POST /api/v1/invoices/{id}/credit-note` | `useCreateCreditNote()` | 37.50€, 2 assiettes |
| 7.4 | Appliquer avoir | `POST /api/v1/invoices/{id}/credit-notes/{cn_id}/apply` | `useApplyCreditNote()` | issued → applied |
| 7.5 | Lecture avoirs | `GET /api/v1/invoices/{id}/credit-notes` | `useInvoiceCreditNotes(id)` | — |
| 7.6 | (auto) Overdue | `GET /api/v1/invoices/overdue` | `useOverdueInvoices()` | → `overdue` |
| 7.7 | Planifier relance 1 | `POST /api/v1/relances/schedule` | `useScheduleRelance()` | email |
| 7.8 | Planifier relance 2 | `POST /api/v1/relances/schedule` | `useScheduleRelance()` | sms |
| 7.9 | Paiement partiel 1 | `POST /api/v1/invoices/{id}/payments` | `useAddInvoicePayment()` | 800€ |
| 7.10 | Relance 3 manuelle | `POST /api/v1/relances/schedule` | `useScheduleRelance()` | telephone |
| 7.11 | Liste relances facture | `GET /api/v1/relances?invoice_id={id}` | `useRelances({ invoice_id })` | — |
| 7.12 | Paiement final | `POST /api/v1/invoices/{id}/payments` | `useAddInvoicePayment()` | 763.50€, → `paid` |
| 7.13 | Liste paiements | `GET /api/v1/invoices/{id}/payments` | `useInvoicePayments(id)` | — |

### Etape 8 — Caution et cloture

| # | Action | Endpoint | Hook Frontend | Detail |
|---|--------|----------|---------------|--------|
| 8.1 | Retenue partielle caution | `PATCH /api/v1/reservations/{id}/deposits/{dep_id}` | `useUpdateDeposit()` | held → retained, 144€ |
| 8.2 | Rappel depot client | `POST /api/v1/reservations/{id}/remind-deposit` | `useRemindReservationDeposit()` | email rappel |
| 8.3 | Completion | `POST /api/v1/reservations/{id}/complete` | `useCompleteReservation()` | → `completed` |
| 8.4 | Archivage | `POST /api/v1/reservations/{id}/archive` | `useArchiveReservation()` | is_archived=true |

**Timeline** : ~6 semaines. **Endpoints utilises** : 38 appels API distincts.

---

## Reference : Etats et Transitions

### Devis — Machine a etats

```
                    ┌──────────┐
                    │  draft   │
                    └────┬─────┘
                         │ send
                    ┌────▼─────┐
              ┌─────│   sent   │─────┐
              │     └────┬─────┘     │
              │          │           │
         refuse     negotiate    expire
              │          │           │
         ┌────▼───┐ ┌───▼────────┐ ┌▼───────┐
         │refused │ │negotiation │ │expired │
         └────────┘ └───┬────────┘ └────────┘
                        │
                   version_pending
                        │
                   ┌────▼─────┐
                   │  sent    │ (nouvelle version)
                   └────┬─────┘
                        │ accept
                   ┌────▼─────┐
                   │ accepted │
                   └────┬─────┘
                        │ convert
                   ┌────▼─────┐
                   │converted │ (TERMINAL)
                   └──────────┘

     * ──cancel──▶ cancelled (TERMINAL, depuis draft/sent/negotiation/version_pending/accepted)
```

### Reservation — Machine a etats

```
     ┌──────────┐
     │  draft   │
     └────┬─────┘
          │ confirm
     ┌────▼──────┐
     │ pre_check │◄────────────────────────┐
     └────┬──────┘                         │
          │                                │
     ┌────▼──────────┐  resolve_risks ─────┘
     │confirmed_risk │
     └────┬──────────┘
          │ depart
     ┌────▼─────┐
     │delivered │
     └────┬─────┘
          │              ┌───────────┐
          ├──extend────▶│ extended  │
          │              └─────┬─────┘
          │                    │
          │◄───────────────────┘
          │
          ├──return_ok────────┐
          │                    │
          ├──return_dispute──┐ │
          │                  │ │
          │  ┌───────────────▼─┤
          │  │returned_dispute │
          │  └───────┬─────────┘
          │          │ resolve
          │  ┌───────▼──┐
          └─▶│ returned  │
             └─────┬─────┘
                   │ complete
             ┌─────▼─────┐
             │ completed  │ (TERMINAL)
             └────────────┘

     * ──cancel──▶ cancelled (TERMINAL, depuis draft/pre_check/confirmed_risk)
```

### Facture — Machine a etats

```
     ┌──────┐
     │draft │
     └──┬───┘
        │ mark-sent
     ┌──▼───┐
     │ sent │
     └──┬───┘
        │         ┌────────┐
        ├─pay───▶│  paid  │ (TERMINAL)
        │         └────────┘
        │ due_date_passed
     ┌──▼─────┐
     │overdue │
     └──┬─────┘
        │         ┌────────┐
        ├─pay───▶│  paid  │ (TERMINAL)
        │         └────────┘

     * ──cancel──▶ cancelled (TERMINAL, depuis draft/sent/overdue)
```

### Vente — Machine a etats

```
     ┌──────┐
     │draft │
     └──┬───┘
        │
     ┌──▼─────┐
     │pending │
     └──┬─────┘
        │
        ├──deposit_pay──▶ deposit_paid ──▶ fully_paid (TERMINAL)
        │                       │
        │                  overdue ──▶ fully_paid | refunded
        │
        ├──full_pay─────▶ fully_paid (TERMINAL)
        │
        ├──overdue──────▶ overdue ──▶ fully_paid | refunded

     * ──cancel──▶ cancelled (TERMINAL)
```

### Depot/Caution — Etats

```
     ┌──────┐
     │ held │
     └──┬───┘
        │
        ├──release──▶ released  (restitution integrale)
        │
        └──retain───▶ retained  (retenue partielle/totale, retained_amount_cents > 0)
```

### Stock Item — Etats

```
     ┌───────────┐
     │ available │◄──────────────────────────┐
     └─────┬─────┘                           │
           │ reserve                    return_ok
     ┌─────▼─────┐                           │
     │ reserved  │                           │
     └─────┬─────┘                           │
           │ depart                          │
     ┌─────▼───────┐                         │
     │ on_location │─────────────────────────┘
     └─────┬───────┘
           │
           ├──return_damaged──▶ damaged ──▶ in_repair ──▶ available
           │                                         └──▶ retired
           │
           └──return_missing──▶ retired (TERMINAL)
```

### Mouvement Inventaire — Etats

```
     ┌───────────┐
     │ scheduled │
     └─────┬─────┘
           │
     ┌─────▼──────┐
     │ in_transit │
     └─────┬──────┘
           │
     ┌─────▼──────┐
     │ completed  │ (TERMINAL)
     └────────────┘

     scheduled ──late──▶ late ──▶ completed
     * ──cancel──▶ cancelled (TERMINAL)
```

### Avoir (Credit Note) — Etats

```
     ┌───────┐
     │ draft │
     └───┬───┘
         │
     ┌───▼────┐
     │ issued │
     └───┬────┘
         │
         ├──apply───▶ applied  (deduit de la facture)
         │
         └──refund──▶ refunded (rembourse directement)
```

### Relance — Etats

```
     ┌───────────┐
     │ scheduled │
     └─────┬─────┘
           │
           ├──send─────▶ sent
           │
           └──cancel───▶ cancelled
```

---

## Reference : Flux Annexes

### Flux 1 — Devis simple (sans negociation)

```
draft → sent → accepted → converted
```

### Flux 2 — Devis avec negociation

```
draft → sent → negotiation → version_pending → sent (V2) → negotiation → sent (V3) → accepted → converted
```

### Flux 3 — Devis refuse puis duplication

```
draft → sent → refused
     ↓
POST /devis/{id}/duplicate → useDevisDuplicate()
     ↓
draft (nouveau DEV-XXXX) → sent → accepted → converted
```

### Flux 4 — Devis expire puis renouvele

```
draft → sent → expired
     ↓
POST /devis/{id}/renew → useRenewDevis()
     ↓
draft → sent → accepted → converted
```

### Flux 5 — Reservation sans devis

```
POST /reservations (creation directe) → draft → pre_check → delivered → returned → completed
```

### Flux 6 — Reservation avec risque bloquant

```
draft → pre_check → confirmed_risk (via POST /operations/departure/{id}/block)
     → PATCH /reservations/{id}/risks/{risk_id} (resolved_at)
     → pre_check → delivered → ...
```

### Flux 7 — Retour avec litige resolu

```
delivered → returned_dispute (via POST /operations/return/{id} avec damages)
     → POST /reservations/{id}/close-dispute
     → returned → completed
```

### Flux 8 — Retour avec extension

```
delivered → extended (via POST /reservations/{id}/extend)
     → POST /operations/return/{id}
     → returned → completed
```

### Flux 9 — Facturation split 40/60

```
POST /reservations/{id}/confirm
  ├─▶ INV-advance (40%) : draft → mark-sent → sent → payments → paid
  └─▶ INV-balance (60%) : draft → mark-sent → sent → payments → paid
```

### Flux 10 — Facture avec charges degats + avoir

```
POST /operations/return/{id}/damage (declare casse)
     → InvoiceCharge DAMAGE auto-creee
POST /invoices/{id}/credit-note (avoir partiel)
POST /invoices/{id}/credit-notes/{cn_id}/apply (imputation)
POST /invoices/{id}/payments (paiement net)
```

### Flux 11 — Facture impayee → Relances

```
GET /invoices/overdue (detection)
POST /relances/schedule (email J+7)
POST /relances/schedule (sms J+14)
POST /relances/schedule (telephone J+21)
POST /invoices/{id}/payments (paiement partiel)
POST /invoices/{id}/payments (paiement final) → paid
```

### Flux 12 — Annulation (differents moments)

```
A. Sur devis    : POST /devis/{id}/cancel
B. Pre-depart   : POST /reservations/{id}/cancel (libere stock + annule factures)
C. Post-depart  : IMPOSSIBLE — retour anticipe via POST /operations/return/{id}
```

### Flux 13 — Caution / Depot

```
POST /reservations/{id}/deposits (held)
     → PATCH .../deposits/{dep_id} status=released (restitution)
     → PATCH .../deposits/{dep_id} status=retained, retained_amount_cents=X (retenue)
```

### Flux 14 — Vente directe (hors location)

```
POST /ventes → draft
POST /ventes/{id}/payments (acompte) → deposit_paid
POST /ventes/{id}/payments (solde) → fully_paid
```

---

## Mapping Endpoint → Hook Frontend

### Devis

| Endpoint | Methode | Hook Frontend | Notes |
|----------|---------|---------------|-------|
| `/devis` | GET | `useDevisList()` | pagination + filtres |
| `/devis/stats` | GET | `useDevisStats()` | compteurs par statut |
| `/devis/{id}` | GET | `useDevisDetail(id)` | — |
| `/devis` | POST | `useCreateDevis()` | body: DevisCreate |
| `/devis/{id}` | PATCH | `useUpdateDevis()` | draft uniquement |
| `/devis/{id}/send` | POST | `useSendDevis()` | draft → sent |
| `/devis/{id}/accept` | POST | `useAcceptDevis()` | → accepted |
| `/devis/{id}/negotiation/start` | POST | `useStartNegotiation()` | → negotiation |
| `/devis/{id}/version-pending` | POST | `useVersionPendingDevis()` | → version_pending |
| `/devis/{id}/refuse` | POST | `useRefuseDevis()` | → refused |
| `/devis/{id}/cancel` | POST | `useCancelDevis()` | → cancelled |
| `/devis/{id}/renew` | POST | `useRenewDevis()` | → draft (validite+30j) |
| `/devis/{id}/convert` | POST | `useConvertDevis()` | → converted, cree reservation |
| `/devis/{id}/duplicate` | POST | `useDevisDuplicate()` | nouveau draft |
| `/devis/{id}/versions` | GET | `useDevisVersions(id)` | snapshots |
| `/devis/{id}/negotiation` | POST | `useAddNegotiationEntry()` | message |
| `/devis/{id}/negotiation/conclude` | POST | `useConcludeNegotiation()` | accept/refuse |
| `/devis/{id}/change-request` | POST | `useRequestChange()` | demande modif |
| `/devis/{id}/change-requests` | GET | `useDevisChangeRequests(id)` | — |
| `/devis/{id}/change-request/{cr_id}` | PATCH | `useUpdateChangeRequest()` | — |
| `/devis/{id}/modules` | GET | `useDevisModules(id)` | — |
| `/devis/{id}/modules` | POST | `useAddDevisModule()` | — |
| `/devis/{id}/modules/{mid}` | PATCH | `useUpdateDevisModule()` | — |
| `/devis/{id}/modules/{mid}` | DELETE | `useDeleteDevisModule()` | — |
| `/devis/{id}/phases` | GET | `useDevisPhases(id)` | — |
| `/devis/{id}/phases` | POST | `useAddDevisPhase()` | — |
| `/devis/{id}/phases/{pid}` | PATCH | `useUpdateDevisPhase()` | — |
| `/devis/{id}/phases/{pid}` | DELETE | `useDeleteDevisPhase()` | — |
| `/devis/{id}/coverage` | GET | `useDevisCoverage(id)` | % couverture |
| `/devis/{id}/coverage-items` | GET | `useDevisCoverageItems(id)` | matrice |
| `/devis/{id}/coverage-items` | POST | `useAddCoverageItem()` | — |
| `/devis/{id}/coverage-items/{cid}` | PATCH | `useUpdateCoverageItem()` | — |
| `/devis/{id}/coverage-items/{cid}` | DELETE | `useDeleteCoverageItem()` | — |
| `/devis/{id}/pdf` | GET | `useDevisPdf(id)` | — |
| `/devis/{id}/signature` | POST | `useSignDevis()` | signature electronique |

### Reservations

| Endpoint | Methode | Hook Frontend | Notes |
|----------|---------|---------------|-------|
| `/reservations` | GET | `useReservations()` | pagination + filtres |
| `/reservations/stats` | GET | `useReservationsStats()` | compteurs |
| `/reservations/{id}` | GET | `useReservationDetail(id)` | — |
| `/reservations/{id}/full` | GET | `useReservationFull(id)` | avec risks, precheck, ext |
| `/reservations` | POST | `useCreateReservation()` | — |
| `/reservations/{id}` | PATCH | `useUpdateReservation()` | draft |
| `/reservations/{id}` | DELETE | `useDeleteReservation()` | draft uniquement |
| `/reservations/{id}/lines` | GET | `useReservationLines(id)` | — |
| `/reservations/{id}/lines` | POST | `useAddReservationLine()` | — |
| `/reservations/{id}/lines/{lid}` | DELETE | `useRemoveReservationLine()` | — |
| `/reservations/{id}/confirm` | POST | `useConfirmReservation()` | → pre_check |
| `/reservations/{id}/deliver` | POST | `useDeliverReservation()` | → delivered |
| `/reservations/{id}/cancel` | POST | `useCancelReservation()` | → cancelled |
| `/reservations/{id}/complete` | POST | `useCompleteReservation()` | → completed |
| `/reservations/{id}/archive` | POST | `useArchiveReservation()` | is_archived |
| `/reservations/{id}/extend` | POST | `useExtendReservation()` | → extended |
| `/reservations/{id}/close-dispute` | POST | `useCloseReservationDispute()` | → returned |
| `/reservations/{id}/assign` | PATCH | `useAssignReservationUser()` | — |
| `/reservations/{id}/signature` | POST | `useUploadReservationSignature()` | — |
| `/reservations/{id}/remind-deposit` | POST | `useRemindReservationDeposit()` | — |
| `/reservations/{id}/pre-check` | GET | `useReservationPreCheck(id)` | — |
| `/reservations/{id}/pre-check` | POST | `useCreatePreCheckItem()` | — |
| `/reservations/{id}/pre-check/{pid}` | PATCH | `useUpdatePreCheckItem()` | checked |
| `/reservations/{id}/pre-check/complete` | POST | `useCompletePreCheck()` | — |
| `/reservations/{id}/deposits` | GET | `useReservationDeposits(id)` | — |
| `/reservations/{id}/deposits` | POST | `useCreateDeposit()` | held |
| `/reservations/{id}/deposits/{did}` | GET | `useDepositDetail(id)` | — |
| `/reservations/{id}/deposits/{did}` | PATCH | `useUpdateDeposit()` | released/retained |
| `/reservations/{id}/risks` | GET | `useReservationRisks(id)` | — |
| `/reservations/{id}/risks` | POST | `useCreateReservationRisk()` | — |
| `/reservations/{id}/risks/{rid}` | PATCH | `useUpdateReservationRisk()` | — |
| `/reservations/{id}/risks/{rid}` | DELETE | `useDeleteReservationRisk()` | — |

### Factures

| Endpoint | Methode | Hook Frontend | Notes |
|----------|---------|---------------|-------|
| `/invoices` | GET | `useInvoices()` | filtres: status, reservation_id |
| `/invoices/overdue` | GET | `useOverdueInvoices()` | auto-detect overdue |
| `/invoices/tva-report` | GET | `useInvoiceTvaReport()` | rapport mensuel |
| `/invoices/payments` | GET | `useAllPayments()` | global tenant |
| `/invoices/sequence/gaps` | GET | `useInvoiceSequenceGaps()` | audit |
| `/invoices/{id}` | GET | `useInvoiceDetail(id)` | — |
| `/invoices/{id}/full` | GET | `useInvoiceFull(id)` | complet |
| `/invoices/{id}/pdf` | GET | `useInvoicePdf(id)` | — |
| `/invoices/{id}/audit` | GET | `useInvoiceAudit(id)` | journal |
| `/invoices` | POST | `useCreateInvoice()` | depuis reservation |
| `/invoices/{id}` | PATCH | `useUpdateInvoice()` | — |
| `/invoices/{id}/cancel` | POST | `useCancelInvoice()` | → cancelled |
| `/invoices/{id}/mark-sent` | POST | `useMarkInvoiceSent()` | → sent |
| `/invoices/{id}/remind` | POST | `useRemindInvoice()` | enregistre relance |
| `/invoices/{id}/add-charge` | POST | `useAddCharge()` | DAMAGE/LABOR |
| `/invoices/{id}/payments` | POST | `useAddInvoicePayment()` | — |
| `/invoices/{id}/payments` | GET | `useInvoicePayments(id)` | — |
| `/invoices/{id}/credit-note` | POST | `useCreateCreditNote()` | — |
| `/invoices/{id}/credit-notes` | GET | `useInvoiceCreditNotes(id)` | — |
| `/invoices/{id}/credit-notes/{cn_id}/apply` | POST | `useApplyCreditNote()` | → applied |
| `/invoices/{id}/credit-notes/{cn_id}/refund` | POST | `useRefundCreditNote()` | → refunded |
| `/invoices/damage` | POST | `useCreateDamageInvoice()` | facture degats |

### Operations (Terrain)

| Endpoint | Methode | Hook Frontend | Notes |
|----------|---------|---------------|-------|
| `/operations/departure/{id}` | GET | `useDepartureState(id)` | etat checklist |
| `/operations/departure/{id}` | POST | `useValidateDeparture()` | → delivered |
| `/operations/departure/{id}/block` | POST | `useBlockDeparture()` | → confirmed_risk |
| `/operations/return/{id}` | GET | `useReturnState(id)` | etat retour |
| `/operations/return/{id}` | POST | `useValidateReturn()` | → returned/dispute |
| `/operations/return/{id}/damage` | POST | `useDeclareCasse()` | declare degat |
| `/operations/qr/{code}` | GET | `useResolveQr()` | scan QR |
| `/operations/damage/photo` | POST | `useUploadDamagePhoto()` | upload multipart |
| `/operations/summary` | GET | `useOperationsSummary()` | dashboard ops |

### Mouvements Inventaire

| Endpoint | Methode | Hook Frontend | Notes |
|----------|---------|---------------|-------|
| `/inventory-movements` | GET | `useMovements()` | filtres |
| `/inventory-movements/late` | GET | `useLateMovements()` | en retard |
| `/inventory-movements/pending-inspections` | GET | `usePendingInspections()` | — |
| `/inventory-movements/statistics` | GET | `useMovementStatistics()` | stats |
| `/inventory-movements/{id}` | GET | `useMovementDetail(id)` | — |
| `/inventory-movements` | POST | `useCreateMovement()` | avec items |
| `/inventory-movements/{id}` | PATCH | `useUpdateMovement()` | — |
| `/inventory-movements/{id}` | DELETE | `useDeleteMovement()` | soft delete |
| `/inventory-movements/{id}/complete` | PATCH | `useCompleteMovement()` | → completed |
| `/inventory-movements/{id}/items` | GET | `useMovementItems(id)` | — |
| `/inventory-movements/{id}/items` | POST | `useAddMovementItem()` | — |
| `/inventory-movements/{id}/items/{iid}` | PATCH | `useUpdateMovementItem()` | qty_actual, condition |
| `/inventory-movements/{id}/items/{iid}` | DELETE | `useDeleteMovementItem()` | — |

### Ventes

| Endpoint | Methode | Hook Frontend | Notes |
|----------|---------|---------------|-------|
| `/ventes` | GET | `useVentes()` | filtres |
| `/ventes/overdue` | GET | `useVentesOverdue()` | — |
| `/ventes/{id}` | GET | `useVenteDetail(id)` | — |
| `/ventes/{id}/pdf` | GET | `useVentePdf(id)` | — |
| `/ventes` | POST | `useCreateVente()` | — |
| `/ventes/{id}` | PATCH | `useUpdateVente()` | — |
| `/ventes/{id}/payments` | POST | `useAddVentePayment()` | — |
| `/ventes/{id}/payments` | GET | `useVentePayments(id)` | — |
| `/ventes/{id}/refund` | POST | `useRefundVente()` | → refunded |
| `/ventes/{id}/cancel` | POST | `useCancelVente()` | → cancelled |

### Relances

| Endpoint | Methode | Hook Frontend | Notes |
|----------|---------|---------------|-------|
| `/relances` | GET | `useRelances()` | filtres: invoice_id, customer_id |
| `/relances/schedule` | POST | `useScheduleRelance()` | planifie |
| `/relances/cancel/{id}` | POST | `useCancelRelance()` | → cancelled |
| `/relances/mark-sent/{id}` | POST | `useMarkRelanceSent()` | → sent |

### Stock Management

| Endpoint | Methode | Hook Frontend | Notes |
|----------|---------|---------------|-------|
| `/stock/inventaire` | POST | `useStartInventaire()` | session |
| `/stock/inventaire/{id}` | GET | `useInventaireSession(id)` | — |
| `/stock/inventaire/{id}` | PATCH | `useUpdateInventaire()` | comptages |
| `/stock/inventaire/{id}/complete` | POST | `useCompleteInventaire()` | applique variances |
| `/stock/adjustments` | POST | `useCreateAdjustment()` | ajustement manuel |
| `/stock/adjustments` | GET | `useStockAdjustments()` | historique |
| `/stock/levels` | GET | `useStockLevels()` | niveaux |
| `/stock/reorder` | GET | `useReorderList()` | sous seuil |
| `/stock/reorder` | POST | `useCreateReorder()` | commande |
| `/stock/coverage` | GET | `useStockCoverage()` | couverture 30j |

### Damage Types

| Endpoint | Methode | Hook Frontend | Notes |
|----------|---------|---------------|-------|
| `/damage-types` | GET | `useDamageTypesList()` | catalogue |
| `/damage-types/{id}` | GET | `useDamageTypeDetail(id)` | — |
| `/damage-types` | POST | `useCreateDamageType()` | — |
| `/damage-types/{id}` | PATCH | `useUpdateDamageType()` | — |
| `/damage-types/{id}` | DELETE | `useDeleteDamageType()` | soft delete |

---

## Matrice des Declencheurs Automatiques

| Evenement declencheur | Action automatique | Entite creee/modifiee |
|----------------------|--------------------|-----------------------|
| Devis → `converted` | Creation reservation + copie lignes + copie dates | Reservation + ReservationLines |
| Reservation → `pre_check` | Creation facture(s) | Invoice (advance + balance ou full) |
| Reservation → `pre_check` | Creation depot | Deposit (held) |
| Reservation → `pre_check` | Creation mouvement depart | InventoryMovement (departure, scheduled) |
| Reservation → `pre_check` | Creation checklist | ReservationPreCheckItem[] |
| Reservation → `delivered` | Stock items → on_location | StockItem.status update |
| Reservation → `extended` | Charge supplementaire | InvoiceCharge (LABOR) |
| Mouvement retour `completed` + damage | Creation dommage | InventoryMovementDamage |
| Dommage avec fee_cents > 0 | Creation charge facture | InvoiceCharge (DAMAGE) |
| Facture due_date depassee | Transition overdue | Invoice.status |
| Facture `overdue` | Planification relance | Relance (scheduled) |
| Relance scheduled_at atteint | Envoi notification | Notification + Relance.status=sent |
| Devis valid_until depasse | Transition expired | Devis.status |
| Stock item retour damaged | Stock → damaged | StockItem.status |
| Stock item retour missing | Stock → retired | StockItem.status |

---

## Checklist "Rien Oublie"

### Entites metier

- [x] Devis (+ lignes, modules, phases, versions, negociations, change requests, coverage items)
- [x] Reservation (+ lignes, risques, pre-check items, extensions)
- [x] Mouvement inventaire (+ items, item units, dommages)
- [x] Facture (+ charges, paiements, avoirs, relances)
- [x] Depot / Caution
- [x] Vente directe (+ lignes, paiements)
- [x] Produit / Variante
- [x] Stock Item (tracking unitaire)
- [x] Type de dommage (catalogue)
- [x] Notification

### Etats terminaux

- [x] Devis : converted, cancelled, refused, expired
- [x] Reservation : completed, cancelled
- [x] Facture : paid, cancelled
- [x] Mouvement : completed, cancelled
- [x] Depot : released, retained
- [x] Vente : fully_paid, refunded, cancelled
- [x] Stock Item : retired
- [x] Avoir : applied, refunded
- [x] Relance : sent, cancelled

### Cas limites couverts

- [x] Negociation multi-versions devis
- [x] Devis refuse → duplication (`POST /devis/{id}/duplicate`)
- [x] Devis expire → renouvellement (`POST /devis/{id}/renew`)
- [x] Risque bloquant (delai nappage, caution impayee)
- [x] Livraison partielle (qty_actual < qty_expected)
- [x] Extension de location (`POST /reservations/{id}/extend`)
- [x] Retour avec degats multiples (casse, tache, manquant)
- [x] Avoir partiel (contestation client) + apply/refund
- [x] Paiements partiels multiples
- [x] Relances multi-canal (email, sms, telephone)
- [x] Retenue sur caution (held → retained)
- [x] Caution non encaissable (cheque refuse)
- [x] Facture split 40/60 (advance + balance)
- [x] Charges LABOR (main d'oeuvre weekend — 60€/h)
- [x] Charges DAMAGE (auto-creees depuis inspection)
- [x] Annulation a differents stades
- [x] Reservation sans devis (creation directe)
- [x] Scan QR code stock (`GET /operations/qr/{code}`)
- [x] Upload photo degat (`POST /operations/damage/photo`)
- [x] Inventaire physique (`POST /stock/inventaire`)
- [x] Rapport TVA (`GET /invoices/tva-report`)
- [x] Audit facture (`GET /invoices/{id}/audit`)

### Constantes metier cles

| Constante | Valeur | Usage |
|-----------|--------|-------|
| Taux TVA | 20% | Toutes factures |
| Acompte | 40% | Split facturation |
| Caution | 3x TTC | Depot standard |
| Caution Selfie Booth | 3 000€ fixe | Exception |
| Echeance solde | J-7 | Avant evenement |
| Penalite retard retour | 20%/jour | Sur montant journalier |
| Delai nappages | 90 jours | Reservation minimum |
| Tarif MO semaine | 30€ HT/h | Charges LABOR |
| Tarif MO weekend/nuit | 60€ HT/h | Charges LABOR |
| Seuil stock bas | 5 unites | Alerte |

### Couverture Frontend → Backend

| Domaine | Endpoints Backend | Hooks Frontend | Couverture |
|---------|------------------|----------------|------------|
| Devis | 35 | 35 | 100% |
| Reservations | 32 | 32 | 100% |
| Factures | 22 | 22 | 100% |
| Operations | 9 | 9 | 100% |
| Mouvements | 13 | 13 | 100% |
| Ventes | 10 | 10 | 100% |
| Relances | 4 | 4 | 100% |
| Stock | 10 | 10 | 100% |
| Damage Types | 5 | 5 | 100% |
| **Total** | **140** | **140** | **100%** |

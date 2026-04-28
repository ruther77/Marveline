# Canonical State Machines V1 (Devis, Reservation, Invoice, Vente)

Date: 2026-03-05
Scope: contrat Frontend-Backend pour les transitions d'etat metier critiques
Sources: `app/models/*`, `app/services/*`, `app/api/v1/endpoints/*`

## 1) Regle globale
- Toute transition non listee explicitement ci-dessous est interdite.
- Toute transition interdite doit retourner une erreur explicite (`400` ou `422`), jamais un changement silencieux.

## 2) Devis

### Etats canoniques
`draft`, `sent`, `negotiation`, `version_pending`, `accepted`, `refused`, `expired`, `converted`, `cancelled`

### Transitions autorisees (V1)
| From | To | Trigger | Endpoint/Source | Guards principaux | Side effects |
|---|---|---|---|---|---|
| `-` | `draft` | creation | `POST /devis` | client valide | reference `DEV-*` |
| `draft` | `sent` | envoi | `POST /devis/{id}/send` | transition map service | snapshot version |
| `sent` | `accepted` | acceptation | `POST /devis/{id}/accept` | transition map service | - |
| `negotiation` | `accepted` | acceptation | `POST /devis/{id}/accept` | transition map service | - |
| `version_pending` | `accepted` | acceptation | `POST /devis/{id}/accept` | transition map service | - |
| `sent` | `refused` | refus | `POST /devis/{id}/refuse` | transition map service | refusal_reason |
| `negotiation` | `refused` | refus | `POST /devis/{id}/refuse` | transition map service | refusal_reason |
| `version_pending` | `refused` | refus | `POST /devis/{id}/refuse` | transition map service | refusal_reason |
| `draft` | `cancelled` | annulation | `POST /devis/{id}/cancel` | transition map service | - |
| `accepted` | `cancelled` | annulation | `POST /devis/{id}/cancel` | transition map service | - |
| `accepted` | `converted` | conversion | `POST /devis/{id}/convert` | dates valides + lignes referencees | creation reservation |
| `expired` | `draft` | renouvellement | `POST /devis/{id}/renew` | transition map service | clone en nouveau devis `draft` |

### Ecarts critiques a traiter
- `sent -> negotiation` et `negotiation <-> version_pending` existent dans la map service, mais aucun endpoint de transition explicite.
- `expired` est gere en service (`expire`) mais sans endpoint public.

## 3) Reservation

### Etats canoniques
`draft`, `confirmed`, `pre_check`, `confirmed_risk`, `delivered`, `extended`, `returned`, `returned_dispute`, `completed`, `cancelled`

### Transitions cibles (contrat metier)
| From | To | Trigger | Endpoint/Source | Guards principaux | Side effects |
|---|---|---|---|---|---|
| `-` | `draft` | creation | `POST /reservations` | payload valide | lignes + montants |
| `draft` | `pre_check` | confirmation | `POST /reservations/{id}/confirm` | stock reservable | facture auto + checklist |
| `confirmed`,`pre_check` | `confirmed_risk` | blocage depart | `POST /operations/departure/{id}/block` | risque bloquant | depart bloque |
| `pre_check` | `delivered` | validation depart | `POST /operations/departure/{id}` | checklist 100% cochee | mouvement depart complete |
| `delivered` | `extended` | prolongation | `POST /reservations/{id}/extend` | nouvelle date > actuelle | extension enregistree |
| `delivered`,`extended` | `returned` | validation retour | `POST /operations/return/{id}` | sans dommages | mouvement retour complete |
| `delivered`,`extended` | `returned_dispute` | validation retour | `POST /operations/return/{id}` | dommages constates | charge dommage possible |
| `returned` | `returned_dispute` | declaration dommage | `POST /operations/return/{id}/damage` | dommage valide | litige ouvert |
| `returned_dispute` | `returned` | cloture litige | `POST /reservations/{id}/close-dispute` | resolution_notes | litige clos |
| `returned` | `completed` | cloture finale | `POST /reservations/{id}/complete` | statut exact `returned` | cycle termine |
| `draft`,`pre_check`,`confirmed`,`confirmed_risk` | `cancelled` | annulation pre-delivery | `POST /reservations/{id}/cancel` | non livre/non termine | liberation stock si reserve |

### Ecarts critiques observes (code actuel)
- Endpoint `POST /reservations/{id}/deliver` attend `confirmed`, mais `confirm` auto-transitionne vers `pre_check`; chemin concurrent et incoherent.
- `POST /reservations/{id}/pre-check/complete` force `pre_check` sans verifier le statut source (risque de regression d'etat).
- `POST /reservations/{id}/extend` passe en `extended`, mais `POST /operations/return/{id}` n'accepte que `delivered` (retour bloque).
- `POST /reservations/{id}/cancel` n'interdit pas `completed` ni `returned_dispute`.

## 4) Invoice

### Etats canoniques
`draft`, `sent`, `paid`, `overdue`, `cancelled`

### Transitions autorisees (V1)
| From | To | Trigger | Endpoint/Source | Guards principaux | Side effects |
|---|---|---|---|---|---|
| `-` | `draft` | generation | `POST /invoices` | reservation existante | numerotation facture |
| `draft` | `sent` | envoi manuel | `POST /invoices/{id}/mark-sent` | statut draft/sent | `sent_at` |
| `sent` | `overdue` | controle echeance | `GET /invoices/overdue` (service overdue) | due_date depassee | statut maj |
| `draft`,`sent`,`overdue` | `paid` | encaissement complet | `POST /invoices/{id}/payments` ou `/{id}/add-payment` | total regle | `paid_amount` |
| `draft`,`sent`,`overdue` | `cancelled` | annulation | `POST /invoices/{id}/cancel` | non payee + `paid_amount=0` | `cancelled_at` |

### Transitions non-status mais metier
- `POST /invoices/{id}/remind`: autorise seulement `sent`/`overdue`, met a jour timeline relance.

### Ecarts critiques a traiter
- `POST /invoices/{id}/payments` (PaymentService) ne bloque pas explicitement les factures `cancelled` alors que `/{id}/add-payment` les bloque.

## 5) Vente

### Etats canoniques
`draft`, `pending`, `deposit_paid`, `fully_paid`, `overdue`, `refunded`, `cancelled`

### Transitions autorisees (V1)
| From | To | Trigger | Endpoint/Source | Guards principaux | Side effects |
|---|---|---|---|---|---|
| `-` | `draft` | creation | `POST /ventes` | payload valide | reference `VTE-*` |
| `draft` | `pending` | 1er paiement | `POST /ventes/{id}/payments` | montant valide | `paid_cents` |
| `pending` | `deposit_paid` | acompte | `POST /ventes/{id}/payments` (`is_deposit=true`) | statut pending | acompte enregistre |
| `pending`,`deposit_paid`,`overdue`,`draft` | `fully_paid` | paiement complet | `POST /ventes/{id}/payments` | `paid_cents >= total_cents` | solde a zero |
| `draft`,`pending`,`deposit_paid`,`fully_paid`,`overdue` | `refunded` | remboursement | `POST /ventes/{id}/refund` | map transitions | - |
| `draft`,`pending`,`deposit_paid`,`overdue` | `cancelled` | annulation | `POST /ventes/{id}/cancel` | map transitions | - |

### Ecarts critiques a traiter
- Aucune transition metier active vers `overdue` n'est implementee (etat present mais non alimente).
- Contrat FE/BE derive: frontend envoie un payload sur `POST /ventes/{id}/refund`, backend n'en consomme pas.

## 6) Backlog priorise derive (state-machine first)

### P0 - Integrite workflow
1. Reservation: unifier depart (`/deliver` legacy vs `/operations/departure/{id}`) et verrouiller les guards de transitions.
2. Reservation: corriger `pre-check/complete` pour interdire tout retour arriere d'etat.
3. Reservation: aligner `extend` et `return` (autoriser retour depuis `extended` ou revoir usage du statut).
4. Invoice: unifier invariants de paiement entre `/{id}/payments` et `/{id}/add-payment`.

### P1 - Completeness API/hook
1. Devis: ajouter transitions explicites `sent->negotiation` et `negotiation<->version_pending` (ou retirer ces etats du contrat).
2. Vente: implementer transition automatique `pending/deposit_paid -> overdue` (job ou endpoint metier).
3. Frontend hooks prioritaires: lot "coverage critique" implemente (reservations/invoices/ventes/devis). Prochaine etape: brancher ces hooks sur les pages restantes et retirer les appels directs legacy.

## 7) Test matrix minimale (Definition of Done)

### Devis
- Positif: `draft->sent->accepted->converted`.
- Negatif: conversion hors `accepted`.
- Contrat: `renew` uniquement depuis `expired`.

### Reservation
- Positif: `draft->pre_check->delivered->returned->completed`.
- Positif: branche litige `returned_dispute->returned->completed`.
- Negatif: `cancel` interdit apres `completed`.
- Negatif: `return` possible depuis `extended` (test de non-regression apres fix).

### Invoice
- Positif: `draft->sent->overdue->paid`.
- Negatif: paiement sur `cancelled`.
- Negatif: `cancel` si montant deja encaisse.

### Vente
- Positif: `draft->pending->deposit_paid->fully_paid`.
- Positif: `pending->overdue` (apres implementation job/trigger).
- Negatif: transitions interdites depuis `cancelled`/`refunded`.

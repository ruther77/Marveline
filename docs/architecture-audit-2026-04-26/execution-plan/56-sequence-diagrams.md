# 56 — Diagrammes de séquence — Flux critiques

> **Objectif** : Documenter sous forme exécutable (Mermaid) les 8 flux les plus critiques du système, dans leur état cible post-refonte. Chaque diagramme inclut les composants impliqués, les transactions, les invariants à respecter, et les points de basculement (commit, rollback, audit, outbox).
>
> **Audience** : Devs implémentant les blocs, reviewers PR, ops debug prod, audits sécurité.
>
> **Convention** : Tous les diagrammes utilisent les mêmes acteurs/composants. Voir [§Légende](#légende).

---

## Sommaire

1. [Login + MFA + scope resolution](#1-login--mfa--scope-resolution)
2. [Conversion Devis → Réservation atomique](#2-conversion-devis--réservation-atomique)
3. [Annulation réservation cascade](#3-annulation-réservation-cascade)
4. [Vente épicerie atomique avec stock + loyalty](#4-vente-épicerie-atomique-avec-stock--loyalty)
5. [Marmite — préparation, consommation, audit](#5-marmite--préparation-consommation-audit)
6. [ETL routing TAIYAT/METRO/EUROCIEL](#6-etl-routing-taiyatmetroeurociel)
7. [Audit Outbox dispatching](#7-audit-outbox-dispatching)
8. [Réception fournisseur → stock_items](#8-réception-fournisseur--stock_items)
9. [Provisioning tenant DEVUP](#9-provisioning-tenant-devup)
10. [Export RGPD utilisateur](#10-export-rgpd-utilisateur)

---

## Légende

```
Acteurs / composants standards :
- C       = Client (frontend ou API consumer)
- API     = Endpoint FastAPI
- Auth    = Service authentification + scope resolver
- Svc     = Service métier (pricing, conversion, etc.)
- Repo    = Repository (accès SQLAlchemy)
- DB      = PostgreSQL
- Cache   = Redis
- Outbox  = Table outbox + dispatcher
- Audit   = Service audit (chain HMAC)
- Broker  = RabbitMQ (Celery)
- Worker  = Celery worker
- KMS     = Service de chiffrement enveloppe
- Notif   = Service notifications (email, SMS, push)

Conventions :
- Couleur rouge : transaction commit/rollback
- Couleur verte : succès / réponse positive
- Couleur orange : événement asynchrone
- Notes : invariants à vérifier à chaque étape
```

---

## 1. Login + MFA + scope resolution

> **Spec source** : Bloc 2 §2.3 (Auth Flow) + §2.5 (RBAC v3 scope resolution)
>
> **Endpoints impliqués** : `POST /auth/login`, `POST /auth/mfa/verify`
>
> **Invariants** :
> - I1 : JWT signé par clé privée KMS, vérifiable par JWKS public
> - I2 : Scope du JWT = intersection (rôles user × scopes vertical du tenant)
> - I3 : Audit log créé pour chaque login (succès ET échec)
> - I4 : Rate limiting par IP + par email (Redis sliding window)

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant API as API /auth/login
    participant RL as RateLimiter (Redis)
    participant Auth as AuthService
    participant Repo as AccountRepository
    participant DB as PostgreSQL
    participant KMS as KMS Service
    participant Cache as Redis (sessions)
    participant Audit as AuditService

    C->>API: POST /auth/login {email, password}
    API->>RL: check_rate_limit(ip, email)
    alt rate limit exceeded
        RL-->>API: 429 Too Many Requests
        API->>Audit: log("login.rate_limited", email, ip)
        API-->>C: 429
    else within limit
        RL-->>API: ok
        API->>Repo: find_account_by_email(email)
        Repo->>DB: SELECT * FROM accounts WHERE email = ?
        DB-->>Repo: account_row OR null

        alt account not found OR is_active=false
            Note over API,Audit: F1002 fix — audit explicite côté endpoint<br/>(/auth/login retiré de EXCLUDED_PATHS en B6.S2)<br/>Sprint 1 patch tactique : audit avant raise 401
            API->>Audit: log("auth.login.failed", actor_email=email, ip, reason="account_not_found")
            Note right of Audit: NEVER log password (masked)<br/>Stored: email + ip + user_agent + reason
            API-->>C: 401 Invalid credentials
        else account found
            Repo-->>API: Account entity

            API->>Auth: verify_password_argon2(password, account.password_hash)
            alt password invalide
                Auth-->>API: false
                API->>RL: increment_failure_count(ip, email)
                Note over API,Audit: F1002 fix — audit explicite branche échec<br/>(retrait /auth/login de EXCLUDED_PATHS en B6.S2 ; Sprint 1 = patch endpoint)
                API->>Audit: log("auth.login.failed", actor_email=email, account_id=account.id, ip, reason="invalid_password")
                Note right of Audit: NEVER log password (masked)
                API-->>C: 401 Invalid credentials
            else password valide
                Auth-->>API: true

                alt password needs rehash (params outdated)
                    API->>Auth: rehash(password) → new_hash
                    API->>Repo: update_password_hash(account.id, new_hash)
                end

                Note over API,Repo: MFA enrolement = présence d'au moins 1 auth_factor actif<br/>sur un membership de l'account (Bloc 2 Q6=B)
                API->>Repo: account_has_mfa(account.id)
                Repo->>DB: SELECT 1 FROM auth_factors af<br/>JOIN tenant_memberships tm ON tm.id = af.membership_id<br/>WHERE tm.account_id = ? AND af.is_active = true LIMIT 1

                alt MFA enrôlée
                    API->>Auth: create_mfa_pending_token(account.id)
                    Auth->>Cache: SET mfa_pending:{token} = account.id, EX 300
                    API->>Audit: log("login.mfa_required", account.id)
                    API-->>C: 200 {"mfa_required": true, "pending_token": "..."}
                    Note over C,Cache: Client appelle ensuite POST /auth/mfa/verify

                    C->>API: POST /auth/mfa/verify {pending_token, totp_code}
                    API->>Cache: GET mfa_pending:{token}
                    Cache-->>API: account_id

                    API->>Repo: find_active_totp_factor(account.id)
                    Repo->>DB: SELECT af.* FROM auth_factors af<br/>JOIN tenant_memberships tm ON tm.id = af.membership_id<br/>WHERE tm.account_id = ? AND af.type='TOTP' AND af.is_active=true
                    Repo-->>API: auth_factor (encrypted_secret)
                    API->>KMS: decrypt(encrypted_secret, context={auth_factor_id})
                    KMS-->>API: clear_secret

                    API->>Auth: verify_totp(clear_secret, totp_code)
                    alt TOTP invalide
                        Auth-->>API: false
                        API->>Audit: log("mfa.failed", account.id)
                        API-->>C: 401 Invalid MFA code
                    else TOTP valide
                        Auth-->>API: true
                    end
                end

                Note over API,Cache: Scope resolution — Bloc 2 §2.5

                API->>Auth: resolve_scopes(account, tenant)
                Auth->>Cache: GET scopes:{account.id}:{tenant.id}
                alt cache hit
                    Cache-->>Auth: cached_scopes
                else cache miss
                    Note over Auth,DB: user_role est mort (F339) — RBAC v3<br/>= TenantMembership.role + auth_vertical_scopes
                    Auth->>Repo: get_membership_role(account.id, tenant.id)
                    Repo->>DB: SELECT role FROM tenant_memberships<br/>WHERE account_id = ? AND tenant_id = ?
                    Auth->>Repo: get_vertical_scopes(tenant.vertical)
                    Repo->>DB: SELECT scope_name FROM auth_vertical_scopes<br/>WHERE vertical_code = ?
                    Auth->>Auth: scopes = intersection(role_scopes, vertical_scopes)
                    Auth->>Cache: SET scopes:{account.id}:{tenant.id} EX 300
                end
                Auth-->>API: scopes (list)

                API->>KMS: sign_jwt({sub, tenant_id, scopes, vertical, exp})
                KMS-->>API: jwt_token (signé EdDSA)

                API->>Cache: SET session:{jti} = account.id, EX 3600
                API->>Audit: log("login.success", account.id, ip, fingerprint)
                Note over Audit: chain HMAC : prev_hmac = last_hmac<br/>current_hmac = HMAC(secret, payload + prev_hmac)

                API-->>C: 200 {"access_token": jwt, "refresh_token": ..., "expires_in": 3600}
            end
        end
    end
```

### Détails critiques

| Étape | Détail | Justification |
|-------|--------|---------------|
| 3 | Rate limit double : IP (50/min) + email (5/min) | Anti-credential-stuffing + anti-brute-force ciblé |
| 9 | Hash systématique même si user inexistant | Empêche user enumeration par timing |
| 14 | Argon2 cost vérifié à chaque login | Migration progressive si params durcis |
| 21 | MFA pending token TTL 5min | Limite fenêtre attaque inter-étapes |
| 33 | Scope intersection rôles × vertical | Empêche fuite scopes inter-verticals |
| 41 | Cache TTL 5min, invalidé sur changement RBAC | Compromis perf/cohérence |

---

## 2. Conversion Devis → Réservation atomique

> **Spec source** : Bloc 3 §3.4 (Conversion atomique)
>
> **Endpoint** : `POST /devis/{id}/convert`
>
> **Invariants** :
> - I1 : Conversion atomique — soit tout réussit, soit tout est rollback
> - I2 : `devis.statut` passe `valide → converti` UNIQUEMENT après commit complet
> - I3 : Caution créée avec montant calculé selon `deposit_policy` du tenant
> - I4 : **Q12=A** — Invoice émise (`status='emitted'`, pas `draft`) dans la même TX que Réservation. Cf. architecture-cible.md §3.2.6.
> - I5 : Audit + Outbox dans la même transaction

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant API as POST /devis/{id}/convert
    participant Auth as Authz
    participant Svc as ConversionService
    participant FSM as FSMHelper
    participant Repo as Repositories
    participant Pricing as PricingEngine
    participant Inv as InvoiceService
    participant DB as PostgreSQL
    participant Outbox as Outbox
    participant Audit as AuditService

    C->>API: POST /devis/{id}/convert (JWT)
    API->>Auth: require_scope(Scope.DEVIS_WRITE)
    Note right of Auth: Format Phase 1 §2.3 : 'devis:write'<br/>(domain:action — pas de dot ni underscore)
    Auth-->>API: ok

    API->>Svc: convert_devis_to_reservation(devis_id, actor)

    Note over Svc,DB: BEGIN TRANSACTION

    Svc->>Repo: get_devis(devis_id, FOR UPDATE)
    Repo->>DB: SELECT devis WHERE id = ? FOR UPDATE
    DB-->>Repo: devis (lock acquired)
    Repo-->>Svc: devis

    Svc->>FSM: assert_transition("devis", devis.statut, "converti")
    alt transition invalide (ex: déjà converti)
        FSM-->>Svc: raise InvalidTransition
        Svc-->>API: 409 Conflict
        API-->>C: 409 {detail: "Devis already converted"}
        Note over Svc,DB: ROLLBACK
    else transition valide
        FSM-->>Svc: ok

        Svc->>Repo: get_devis_lines(devis_id)
        Repo->>DB: SELECT devis_line WHERE devis_id = ?
        DB-->>Repo: lines

        Svc->>Pricing: recalculate_for_reservation(lines, customer, date_evenement)
        Note over Pricing: Vérifie que prix devis = prix actuel (sinon warning)
        Pricing-->>Svc: pricing_breakdown

        Note over Svc: Q12=A — Reservation status='confirmed' direct (pas pending)

        Svc->>Repo: create_reservation(devis.tenant_id, customer_id, lines, pricing, status='confirmed')
        Repo->>DB: INSERT INTO reservation (status='confirmed', ...)
        DB-->>Repo: reservation_id

        loop Pour chaque ligne devis
            Svc->>Repo: create_reservation_line(reservation_id, line)
            Repo->>DB: INSERT INTO reservation_line (...)
        end

        Note over Svc,Inv: Q12=A — Invoice émise IMMÉDIATEMENT dans la même TX<br/>(architecture-cible.md §3.2.6 : confirmed → invoice.status='emitted', PAS draft)

        Svc->>Inv: create_emitted_from_reservation(reservation_id, lines, pricing)
        Inv->>Repo: create_invoice(reservation_id, lines, pricing, status='emitted', issued_at=NOW())
        Repo->>DB: INSERT INTO invoice (status='emitted', issued_at=NOW(), ...)
        DB-->>Inv: invoice_id

        loop Pour chaque ligne devis
            Inv->>Repo: create_invoice_line(invoice_id, line, tva_rate_snapshot)
            Repo->>DB: INSERT INTO invoice_line (...)
        end

        Inv-->>Svc: invoice_id

        Note over Svc: Calcul caution selon deposit_policy

        Svc->>Pricing: calculate_caution(pricing, tenant.deposit_policy, customer.requires_deposit)
        Note right of Pricing: Q14=C — DepositPolicyService.resolve(customer, tenant)<br/>Customer.requires_deposit + override_pct
        Pricing-->>Svc: caution_centimes (0 si requires_deposit=False)

        alt caution_centimes > 0
            Svc->>Repo: create_deposit(reservation_id, caution_centimes)
            Repo->>DB: INSERT INTO deposit (status='pending', amount_centimes=?, ...)
        end

        Svc->>Repo: update_devis_statut(devis_id, "converti")
        Repo->>DB: UPDATE devis SET statut = 'converti', converted_at = NOW(), reservation_id = ?

        Note over Svc: FSM transition log

        Svc->>Repo: log_fsm_transition("devis", devis_id, "valide", "converti")
        Repo->>DB: INSERT INTO fsm_transitions (...)

        Note over Svc,Audit: Audit chained HMAC

        Svc->>Audit: log("devis.convert", actor, {devis_id, reservation_id})
        Audit->>Repo: get_last_hmac()
        Repo->>DB: SELECT hmac FROM audit_log ORDER BY id DESC LIMIT 1
        Audit->>Audit: current_hmac = HMAC(secret, payload + prev_hmac)
        Audit->>Repo: insert_audit_log(action, actor, payload, current_hmac, prev_hmac)
        Repo->>DB: INSERT INTO audit_log (...)

        Svc->>Audit: log("reservation.create", actor, {reservation_id})
        Audit->>Repo: insert_audit_log(...)
        Repo->>DB: INSERT INTO audit_log (...)

        Svc->>Audit: log("invoice.emit", actor, {invoice_id, reservation_id})
        Audit->>Repo: insert_audit_log(...)
        Repo->>DB: INSERT INTO audit_log (...)

        Note over Svc,Outbox: Outbox events (transactionnel — committed avec le reste)

        Svc->>Outbox: enqueue("DevisConverted", {devis_id, reservation_id})
        Outbox->>DB: INSERT INTO outbox_events (event_type, payload, status='pending')

        Svc->>Outbox: enqueue("ReservationCreated", {reservation_id})
        Outbox->>DB: INSERT INTO outbox_events (...)

        Svc->>Outbox: enqueue("InvoiceEmitted", {invoice_id, reservation_id})
        Outbox->>DB: INSERT INTO outbox_events (...)

        Note over Svc,DB: COMMIT

        Svc-->>API: ConversionResult{reservation_id, invoice_id, deposit_id?}
        API-->>C: 201 Created {reservation_id, invoice_id, ...}

        Note over Outbox: Dispatcher async va publier les events vers RabbitMQ
    end
```

### Points critiques

| Étape | Détail | Conséquence si oublié |
|-------|--------|------------------------|
| `FOR UPDATE` lock sur devis | Race condition double-conversion possible |
| FSM transition matrix | Conversion en chaîne incohérente |
| Recalcul prix actuel | Devis stale → réservation à prix incorrect |
| **Q12=A — Invoice émise dans la même TX** | Réservation `confirmed` sans facture → IntegrityError ou facture orpheline si appel hors TX |
| **Q14=C — DepositPolicyService.resolve(customer, tenant)** | Faux montant caution (Customer.requires_deposit ignoré) |
| Audit chain prev_hmac | Tampering détectable |
| Outbox dans la même TX | Event publié sans commit DB → état incohérent |

---

## 3. Annulation réservation cascade

> **Spec source** : Bloc 3 §3.6 (Cancellation cascade)
>
> **Endpoint** : `POST /reservations/{id}/cancel`
>
> **Invariants** :
> - I1 : Annulation libère stock réservé (cascade vers stock_movements)
> - I2 : Caution remboursée selon politique (full / partial / none)
> - I3 : Notifications client envoyées via Outbox (pas synchrone)
> - I4 : Statut fenêtre H-72 : refus avec 409 si politique restrictive

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant API as POST /reservations/{id}/cancel
    participant Svc as CancellationService
    participant Repo as Repositories
    participant FSM as FSMHelper
    participant DB as PostgreSQL
    participant Outbox as Outbox
    participant Audit as AuditService

    C->>API: POST /reservations/{id}/cancel {reason}
    API->>Svc: cancel_reservation(resa_id, actor, reason)

    Note over Svc,DB: BEGIN TRANSACTION

    Svc->>Repo: get_reservation(resa_id, FOR UPDATE)
    Repo->>DB: SELECT reservation WHERE id = ? FOR UPDATE
    DB-->>Svc: reservation

    Svc->>FSM: assert_transition("reservation", reservation.statut, "cancelled")
    FSM-->>Svc: ok

    Note over Svc: Vérification politique annulation tenant

    Svc->>Svc: compute_cancellation_policy(reservation.date_evenement, now)
    alt H-72 dépassé ET politique restrictive
        Svc-->>API: raise PolicyViolation
        API-->>C: 409 {detail: "Cannot cancel < 72h before event"}
        Note over Svc,DB: ROLLBACK
    else annulation autorisée
        Note over Svc: Libération lignes réservation et stock

        Svc->>Repo: get_reservation_lines(resa_id)
        Repo->>DB: SELECT * FROM reservation_line WHERE reservation_id = ?

        loop Pour chaque ligne
            Svc->>Repo: release_stock(line.product_id, line.qty, reservation_id)
            Note over Repo: release_n propagates reservation_id<br/>(fix STOCK-RELEASE-BLIND-01)
            Repo->>DB: UPDATE stock_item SET qty_reserved = qty_reserved - ?<br/>WHERE product_id = ? AND tenant_id = ?
            Repo->>DB: INSERT INTO stock_movement (type='release', reservation_id=?, ...)
        end

        Note over Svc: Calcul remboursement caution

        Svc->>Repo: get_caution(resa_id)
        Repo->>DB: SELECT * FROM caution WHERE reservation_id = ?
        Repo-->>Svc: caution

        alt caution.status = 'paid'
            Svc->>Svc: compute_refund_amount(caution, cancellation_policy)
            Svc->>Repo: update_caution_status(caution.id, "refund_pending", refund_amount)
            Repo->>DB: UPDATE caution SET status='refund_pending', ...

            Svc->>Outbox: enqueue("CautionRefundRequested", {caution_id, amount})
            Outbox->>DB: INSERT INTO outbox_events (...)
        else caution.status = 'pending'
            Svc->>Repo: update_caution_status(caution.id, "cancelled")
            Repo->>DB: UPDATE caution SET status='cancelled'
        end

        Svc->>Repo: update_reservation_statut(resa_id, "cancelled")
        Repo->>DB: UPDATE reservation SET statut='cancelled', cancelled_at=NOW(), cancellation_reason=?

        Svc->>Repo: log_fsm_transition("reservation", resa_id, prev, "cancelled")
        Repo->>DB: INSERT INTO fsm_transitions (...)

        Svc->>Audit: log("reservation.cancel", actor, {resa_id, reason, refund_amount})
        Audit->>DB: INSERT INTO audit_log (... + chain_hmac)

        Note over Svc,Outbox: Notifications via Outbox

        Svc->>Outbox: enqueue("ReservationCancelled", {resa_id, customer_id, refund_amount})

        Note over Svc,DB: COMMIT

        Svc-->>API: ok
        API-->>C: 200 {refund_amount: ..., refund_status: "pending"}

        Note over Outbox: Dispatcher async :<br/>- Notif email client<br/>- Trigger paiement refund (Stripe/etc)
    end
```

---

## 4. Vente épicerie atomique avec stock + loyalty

> **Spec source** : Bloc 5 §5.4 (Encaissement épicerie)
>
> **Endpoint** : `POST /epicerie/ventes/encaisser`
>
> **Invariants** :
> - I1 : Stock decrement atomique avec advisory lock par stock_item
> - I2 : Loyalty points accordés UNIQUEMENT après paiement validé
> - I3 : Audit + Outbox dans même transaction
> - I4 : Si stock insuffisant, 409 — pas de partial

```mermaid
sequenceDiagram
    autonumber
    participant C as Client (POS)
    participant API as POST /epicerie/ventes/encaisser
    participant Svc as VenteService
    participant Pricing as PricingEngine
    participant Repo as Repositories
    participant DB as PostgreSQL
    participant Outbox as Outbox
    participant Audit as AuditService

    C->>API: POST /epicerie/ventes/encaisser {lines, payment_method, customer_id?}
    API->>Svc: encaisser_vente(payload, actor)

    Note over Svc,DB: BEGIN TRANSACTION

    Note over Svc: Locks advisory par produit pour éviter race

    loop Pour chaque ligne (triée par product_id)
        Svc->>DB: SELECT pg_advisory_xact_lock(hashtext(line.product_id))
    end

    Note over Svc: Vérification stock disponible

    loop Pour chaque ligne
        Svc->>Repo: get_stock_item(product_id, tenant_id)
        Repo->>DB: SELECT * FROM stock_item WHERE product_id = ? AND tenant_id = ?
        DB-->>Svc: stock_item

        alt stock_item.qty_disponible < line.qty
            Svc-->>API: raise InsufficientStock
            API-->>C: 409 {detail: "Stock insuffisant pour {product_id}"}
            Note over Svc,DB: ROLLBACK
        end
    end

    Note over Svc: Calcul prix avec PricingEngine

    Svc->>Pricing: calculate_total(lines, customer, tenant)
    Pricing->>Repo: get_pricing_rules(tenant_id, products)
    Pricing->>Pricing: apply_discounts (loyalty, promo, bundle)
    Pricing-->>Svc: pricing_breakdown {ht, tva, ttc, discounts, points_earned}

    alt customer fourni
        Svc->>Repo: get_loyalty_card(customer_id)
        Repo->>DB: SELECT * FROM loyalty_card WHERE customer_id = ?
        Repo-->>Svc: loyalty_card OR null
    end

    Note over Svc: Création vente

    Svc->>Repo: create_vente(tenant_id, lines, pricing, payment_method, customer_id?)
    Repo->>DB: INSERT INTO vente (statut='paid', total_ttc_centimes=?, ...)
    DB-->>Repo: vente_id

    loop Pour chaque ligne
        Svc->>Repo: create_vente_line(vente_id, line)
        Repo->>DB: INSERT INTO vente_line (...)
    end

    Note over Svc: Stock decrement avec mouvement

    loop Pour chaque ligne
        Svc->>Repo: decrement_stock(product_id, qty, vente_id)
        Repo->>DB: UPDATE stock_item SET qty_disponible = qty_disponible - ? WHERE product_id = ?
        Repo->>DB: INSERT INTO stock_movement (type='vente', vente_id=?, qty=-?, ...)
    end

    Note over Svc: Ledger financier

    Svc->>Repo: append_revenue_ledger(tenant_id, vente_id, ttc_centimes)
    Repo->>DB: INSERT INTO revenue_ledger (...)

    Svc->>Repo: append_payment_ledger(tenant_id, vente_id, payment_method, ttc_centimes)
    Repo->>DB: INSERT INTO payment_ledger (...)

    Note over Svc: Loyalty — UNIQUEMENT si paiement validé

    alt loyalty_card existe
        Svc->>Svc: compute_points_earned(pricing, tenant.loyalty_program)
        Svc->>Repo: append_points_ledger(loyalty_card.id, +points, vente_id)
        Repo->>DB: INSERT INTO points_ledger (...)
        Note over DB: Trigger: update loyalty_card.balance_points
    end

    Note over Svc,Audit: Audit chained

    Svc->>Audit: log("vente.encaisser", actor, {vente_id, total_ttc})
    Audit->>DB: INSERT INTO audit_log (... + chain_hmac)

    Note over Svc,Outbox: Outbox events

    Svc->>Outbox: enqueue("VenteEncaissee", {vente_id, customer_id?})
    Outbox->>DB: INSERT INTO outbox_events (...)

    alt facture demandée
        Svc->>Outbox: enqueue("FactureRequested", {vente_id})
    end

    Note over Svc,DB: COMMIT

    Svc-->>API: VenteResult{vente_id, total, points_earned}
    API-->>C: 201 {vente_id, total_ttc: ..., ticket_url: ...}

    Note over Outbox: Dispatcher async :<br/>- Génération PDF facture<br/>- Update RFM customer<br/>- Push notif app cliente si applicable
```

---

## 5. Marmite — préparation, consommation, audit

> **Spec source** : Bloc 5 §5.7 (Restaurant marmite)
>
> **Endpoint** : `POST /restaurant/instances` puis consommation à la commande
>
> **Invariants** :
> - I1 : Lancement marmite décrémente ingrédients selon recette × portions_max
> - I2 : Consommation à la commande utilise `qte_par_portion` (PAS `quantite_par_portion` — fix F906)
> - I3 : Pertes capturées en fin de service via mouvement stock dédié
> - I4 : Audit pour chaque étape

```mermaid
sequenceDiagram
    autonumber
    participant C as Client (cuisine)
    participant API as POST /restaurant/instances
    participant Svc as InstancePreparationService
    participant Repo as Repositories
    participant DB as PostgreSQL
    participant Audit as AuditService

    Note over C,DB: ÉTAPE 1 — LANCEMENT MARMITE

    C->>API: POST /restaurant/instances {recette_id, portions_max}
    API->>Svc: lancer_marmite(recette_id, portions_max, actor)

    Note over Svc,DB: BEGIN TRANSACTION

    Svc->>Repo: get_recette(recette_id) (with ingredients)
    Repo->>DB: SELECT recette + recette_ingredient JOIN ingredient
    DB-->>Svc: recette + ingredients

    Note over Svc: Vérification stock ingrédients

    loop Pour chaque ingredient
        Svc->>Svc: required_qty = ingredient.qte_par_portion * portions_max
        Note right of Svc: ⚠️ Champ correct = qte_par_portion<br/>(F906 P0 si quantite_par_portion utilisé)

        Svc->>Repo: get_stock_for_ingredient(ingredient.id, tenant_id)
        Repo->>DB: SELECT stock_item via ingredient_sourcing resolver
        DB-->>Svc: stock_item

        alt stock < required_qty
            Svc-->>API: raise InsufficientIngredient
            API-->>C: 409 {detail: "Stock {ingredient.nom} insuffisant"}
            Note over Svc,DB: ROLLBACK
        end
    end

    Note over Svc: Création instance marmite

    Svc->>Repo: create_instance_preparation(recette_id, portions_max, statut='active')
    Repo->>DB: INSERT INTO instance_preparation (...)
    DB-->>Svc: instance_id

    Note over Svc: Decrement stock ingrédients

    loop Pour chaque ingredient
        Svc->>Repo: decrement_stock(ingredient_stock_item, required_qty, instance_id)
        Repo->>DB: UPDATE stock_item SET qty = qty - ?
        Repo->>DB: INSERT INTO stock_movement (type='marmite_prep', instance_id=?, qty=-?)
    end

    Svc->>Audit: log("marmite.lancer", actor, {instance_id, recette_id, portions_max})
    Audit->>DB: INSERT INTO audit_log (... + chain_hmac)

    Note over Svc,DB: COMMIT

    Svc-->>API: InstanceResponse{instance_id, portions_max, portions_consommees:0}
    API-->>C: 201 Created

    Note over C,DB: ÉTAPE 2 — CONSOMMATION À LA COMMANDE

    C->>API: POST /restaurant/commandes {lines: [{recette_id, qty}, ...]}
    API->>Svc: create_commande(payload, actor)

    Note over Svc,DB: BEGIN TRANSACTION

    Svc->>Repo: create_commande(...)
    Repo->>DB: INSERT INTO commande (...)

    loop Pour chaque ligne (recette × qty)
        Svc->>Repo: get_active_instance(recette_id, tenant_id)
        Repo->>DB: SELECT instance_preparation WHERE recette_id = ? AND statut='active'<br/>AND portions_consommees < portions_max<br/>ORDER BY created_at LIMIT 1 FOR UPDATE
        DB-->>Svc: instance OR null

        alt no active instance OR portions épuisées
            Svc-->>API: raise NoActiveMarmite
            API-->>C: 409 {detail: "Aucune marmite active pour {recette}"}
            Note over Svc,DB: ROLLBACK
        else instance disponible
            Svc->>Repo: increment_portions_consommees(instance.id, line.qty)
            Repo->>DB: UPDATE instance_preparation SET portions_consommees = portions_consommees + ?
            Repo->>DB: INSERT INTO commande_line (instance_id=?, ...)

            alt instance.portions_consommees == portions_max
                Svc->>Repo: update_instance_statut(instance.id, "consumed")
                Repo->>DB: UPDATE instance_preparation SET statut='consumed', closed_at=NOW()
            end
        end
    end

    Svc->>Audit: log("commande.create", actor, {commande_id})

    Note over Svc,DB: COMMIT

    Svc-->>API: ok
    API-->>C: 201

    Note over C,DB: ÉTAPE 3 — FIN SERVICE — CAPTURE PERTES

    C->>API: POST /restaurant/instances/{id}/cloturer {portions_perdues}
    API->>Svc: cloturer_instance(instance_id, portions_perdues)

    Note over Svc,DB: BEGIN TRANSACTION

    Svc->>Repo: get_instance(instance_id, FOR UPDATE)
    Svc->>Svc: validate (statut == 'active' OR 'consumed', perte cohérente)

    Svc->>Repo: update_instance(statut='closed', portions_perdues)
    Repo->>DB: UPDATE instance_preparation SET statut='closed', portions_perdues=?, closed_at=NOW()

    alt portions_perdues > 0
        Svc->>Repo: log_perte_movement(instance_id, ingredients × portions_perdues)
        Repo->>DB: INSERT INTO stock_movement (type='marmite_perte', ...)
    end

    Svc->>Audit: log("marmite.cloturer", actor, {instance_id, portions_perdues})

    Note over Svc,DB: COMMIT

    Svc-->>API: ok
    API-->>C: 200
```

### Bug F906 prévention

```python
# app/services/restaurant/instance_preparation.py
# AVANT (bug F906) :
required_qty = ingredient.quantite_par_portion * portions_max  # ❌ AttributeError

# APRÈS (fix Sprint 1) :
required_qty = ingredient.qte_par_portion * portions_max  # ✅
```

---

## 6. ETL routing TAIYAT/METRO/EUROCIEL

> **Spec source** : Bloc 5 §5.2 (ETL strategy)
>
> **Endpoint** : `POST /etl/imports` puis `POST /etl/imports/{id}/validate`
>
> **Invariants** :
> - I1 : Routing parser basé sur `vendor_code` détecté ou imposé par utilisateur
> - I2 : Idempotence garantie — `validate_import` n'introduit pas de doublons (fix ETL-DUPE-01)
> - I3 : Échec parser doit être actionnable (message clair, ligne, champ)
> - I4 : Création produit catalogue automatique si vendor reconnu et produit nouveau

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant API as POST /etl/imports
    participant Svc as ETLService
    participant Router as ParserRouter
    participant Parser as ParserMETRO/TAIYAT/EUROCIEL
    participant Resolver as IngredientSourcingResolver
    participant Repo as Repositories
    participant DB as PostgreSQL
    participant Broker as RabbitMQ

    C->>API: POST /etl/imports {file, vendor_code?}
    API->>Svc: create_import(file, vendor_code, actor)

    Note over Svc,DB: BEGIN TRANSACTION

    Svc->>Repo: create_import_record(tenant_id, status='pending', file_hash)
    Repo->>DB: INSERT INTO etl_import (status='pending', file_hash, ...)
    DB-->>Svc: import_id

    Note over Svc,DB: COMMIT

    Svc->>Broker: publish("etl.parse", {import_id})
    Svc-->>API: 202 Accepted {import_id}
    API-->>C: 202 {import_id, status: "pending"}

    Note over C,Broker: ÉTAPE ASYNC — Worker Celery

    Broker->>Parser: deliver task etl.parse(import_id)

    Note over Parser,DB: BEGIN TRANSACTION (worker)

    Parser->>Repo: get_import(import_id, FOR UPDATE)
    Parser->>Repo: update_import_status(import_id, "parsing")

    Parser->>Router: detect_vendor(file_content)
    alt vendor_code fourni explicitement
        Router-->>Parser: vendor_code
    else vendor_code inconnu
        Router->>Router: try fingerprints (header signature, format)
        alt match
            Router-->>Parser: detected_vendor
        else no match
            Router-->>Parser: VendorUnknown
            Parser->>Repo: update_import(status='vendor_unknown')
            Parser-->>Broker: ack
            Note over C: Client doit appeler<br/>POST /etl/imports/{id}/resolve-vendor
        end
    end

    Note over Parser: Routing vers parser dédié

    alt vendor = METRO
        Parser->>Parser: ParserMetroV2.parse(file)
        Note right of Parser: Soft TF-IDF brand match<br/>97% champs enrichis
    else vendor = TAIYAT
        Parser->>Parser: ParserTaiyatV2.parse(file)
    else vendor = EUROCIEL
        Parser->>Parser: ParserEurociel.parse(file)
        Note right of Parser: ⚠️ EUROCIEL n'a pas prix → fail si missing<br/>(EUROCIEL-PRIX-NULL-01 P2)
    end

    alt parsing fail
        Parser->>Repo: update_import(status='parse_failed', error)
        Parser-->>Broker: ack (no retry — données invalides)
        Note over C: Client voit status=parse_failed via polling
    else parsing ok
        Parser-->>Parser: parsed_lines (List[ETLLine])

        loop Pour chaque parsed_line
            Parser->>Resolver: resolve_or_create_product(parsed_line, tenant_id)
            Resolver->>Repo: find_product_by_ean OR fuzzy_match(name, brand)
            Repo->>DB: SELECT product WHERE ean = ? OR (name ILIKE ? AND brand = ?)

            alt produit existant
                Repo-->>Resolver: product
            else produit inconnu
                Resolver->>Repo: create_product(parsed_line, tenant_id, status='draft')
                Repo->>DB: INSERT INTO product (...)
            end

            Resolver-->>Parser: product

            Parser->>Repo: create_etl_import_line(import_id, parsed_line, product_id, status='pending')
            Repo->>DB: INSERT INTO etl_import_line (...)
        end

        Parser->>Repo: update_import(status='ready_for_validation')
    end

    Note over Parser,DB: COMMIT

    Parser-->>Broker: ack

    Note over C,DB: ÉTAPE 3 — VALIDATION (idempotente)

    C->>API: POST /etl/imports/{id}/validate
    API->>Svc: validate_import(import_id, actor)

    Note over Svc,DB: BEGIN TRANSACTION + advisory lock import_id

    Svc->>DB: SELECT pg_advisory_xact_lock(hashtext('etl_validate:' || import_id))

    Svc->>Repo: get_import(import_id, FOR UPDATE)

    alt import.status == 'validated'
        Note over Svc: Idempotence : déjà validé, no-op<br/>(fix ETL-DUPE-01)
        Svc-->>API: 200 {already_validated: true}
        API-->>C: 200
        Note over Svc,DB: COMMIT
    else import.status != 'ready_for_validation'
        Svc-->>API: 409 Conflict
        API-->>C: 409
    else status valide
        Svc->>Repo: get_import_lines(import_id, status='pending')

        loop Pour chaque ligne
            Svc->>Repo: create_stock_movement(product_id, qty, type='etl_import')
            Repo->>DB: INSERT INTO stock_movement (...)
            Repo->>DB: UPDATE stock_item SET qty = qty + line.qty
            Note right of DB: Net stock guard : CHECK qty >= 0
        end

        Svc->>Repo: update_import(import_id, status='validated', validated_at=NOW())
        Svc->>Repo: update_lines_status(import_id, 'committed')

        Svc->>Audit: log("etl.import.validate", actor, {import_id, lines_count})

        Note over Svc,DB: COMMIT

        Svc-->>API: 200 {validated: true, lines_committed: N}
        API-->>C: 200
    end
```

---

## 7. Audit Outbox dispatching

> **Spec source** : Bloc 1 §1.4 (Outbox pattern)
>
> **Tâche** : Worker Celery `outbox_dispatcher` (poll 5s)
>
> **Invariants** :
> - I1 : Exactement-une-fois delivery via dedup_key + idempotence broker
> - I2 : Failed events retry exponential backoff, max 5 retries → DLQ
> - I3 : Audit chain integrity vérifiable nightly

```mermaid
sequenceDiagram
    autonumber
    participant Cron as Cron (every 5s)
    participant Worker as Celery Worker
    participant DB as PostgreSQL
    participant Broker as RabbitMQ
    participant Sub as Subscribers

    Cron->>Worker: trigger outbox_dispatcher

    Note over Worker,DB: BEGIN TRANSACTION (poll batch)

    Worker->>DB: SELECT * FROM outbox_events<br/>WHERE status = 'pending'<br/>AND (next_retry_at IS NULL OR next_retry_at <= NOW())<br/>ORDER BY created_at<br/>LIMIT 100<br/>FOR UPDATE SKIP LOCKED
    DB-->>Worker: events (max 100)

    alt no events
        Note over Worker: Nothing to do
        Worker-->>Cron: done
    else events found
        loop Pour chaque event
            Worker->>Worker: build_message(event)
            Note right of Worker: Headers: dedup_key=event.id<br/>Routing key based on event_type

            Worker->>Broker: publish(exchange, routing_key, payload, headers)

            alt publish ok
                Broker-->>Worker: ack
                Worker->>DB: UPDATE outbox_events SET status='dispatched', dispatched_at=NOW()<br/>WHERE id = ?
            else publish fail (broker down, network)
                Worker->>Worker: compute next_retry_at (exponential backoff)
                Worker->>Worker: retry_count += 1

                alt retry_count >= 5
                    Worker->>DB: UPDATE outbox_events SET status='failed', error=?
                    Worker->>Broker: publish to DLQ (dlx.outbox)
                    Note over Worker: Alert ops via Slack #ops-alerts
                else retry_count < 5
                    Worker->>DB: UPDATE outbox_events SET retry_count=?, next_retry_at=?
                end
            end
        end

        Note over Worker,DB: COMMIT (batch)

        Worker-->>Cron: dispatched={N}, failed={M}
    end

    Note over Broker,Sub: Subscribers pickup async

    Broker->>Sub: deliver event (with dedup_key header)

    Sub->>Sub: check_idempotence(dedup_key) (Redis SET IF NOT EXISTS, TTL 24h)
    alt already processed
        Sub-->>Broker: ack (no-op)
    else first time
        Sub->>Sub: process_event(payload)
        Sub-->>Broker: ack
    end

    Note over Cron,Sub: NIGHTLY — Audit chain integrity

    rect rgba(255, 230, 200)
        Cron->>Worker: trigger audit_chain_verify (02:00 UTC)
        Worker->>DB: SELECT * FROM audit_log ORDER BY id

        loop Pour chaque log (sequential walk)
            Worker->>Worker: expected_hmac = HMAC(secret, log.payload + log.prev_hmac)
            alt expected_hmac == log.hmac
                Note right of Worker: chain valid for this entry
            else mismatch
                Worker->>Worker: PagerDuty CRITICAL "Audit chain break at log_id={log.id}"
                Note over Worker: Tampering détecté !
            end
        end

        Worker-->>Cron: chain_valid=true OR break_detected=log_id
    end
```

---

## 8. Réception fournisseur → stock_items

> **Spec source** : Bloc 5 §5.3 (Réception fournisseur)
>
> **Endpoint** : `POST /receptions/{id}/valider`
>
> **Invariants** :
> - I1 : Réception valide crée mouvements stock + update CMP/PMP
> - I2 : `stock_items` agrégés : un par (product_id, tenant_id) avec qty et CMP
> - I3 : Trigger DB met à jour `product_stock_view` (materialized)

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant API as POST /receptions/{id}/valider
    participant Svc as ReceptionService
    participant Repo as Repositories
    participant DB as PostgreSQL
    participant Trigger as DB Triggers
    participant Audit as AuditService

    C->>API: POST /receptions/{id}/valider
    API->>Svc: valider_reception(reception_id, actor)

    Note over Svc,DB: BEGIN TRANSACTION

    Svc->>Repo: get_reception(reception_id, FOR UPDATE) (with lines)
    Repo->>DB: SELECT reception JOIN reception_line WHERE id = ? FOR UPDATE
    DB-->>Svc: reception + lines

    Svc->>Svc: validate_state(statut == 'pending')

    loop Pour chaque ligne réception
        Svc->>Repo: get_stock_item(product_id, tenant_id)
        Repo->>DB: SELECT stock_item WHERE product_id = ? AND tenant_id = ?

        alt stock_item existe
            Repo-->>Svc: existing_stock_item

            Note over Svc: Calcul nouveau CMP

            Svc->>Svc: new_cmp = (existing_qty * existing_cmp + line.qty * line.prix_achat_unitaire) / (existing_qty + line.qty)
            Svc->>Svc: new_pmp = max(existing_pmp, line.prix_achat_unitaire)  # plus haut atteint

            Svc->>Repo: update_stock_item(qty += line.qty, cmp = new_cmp, pmp = new_pmp)
            Repo->>DB: UPDATE stock_item SET qty = qty + ?, cmp_centimes = ?, pmp_centimes = ?
        else stock_item inexistant
            Svc->>Repo: create_stock_item(product_id, tenant_id, qty=line.qty, cmp=line.prix_achat_unitaire, pmp=line.prix_achat_unitaire)
            Repo->>DB: INSERT INTO stock_item (...)
        end

        Svc->>Repo: create_stock_movement(type='reception', reception_id=?, qty=+line.qty, cost=line.prix_achat_unitaire)
        Repo->>DB: INSERT INTO stock_movement (...)

        Note over Trigger: Trigger after_insert_stock_movement<br/>NOTIFY 'product_stock_view_refresh'
        Trigger->>DB: NOTIFY product_stock_view_refresh, payload={product_id}
    end

    Svc->>Repo: update_reception(reception_id, statut='validated', validated_at=NOW())
    Repo->>DB: UPDATE reception SET statut='validated', validated_at=NOW(), validated_by=?

    Svc->>Audit: log("reception.valider", actor, {reception_id, lines_count, total_centimes})
    Audit->>DB: INSERT INTO audit_log (... + chain_hmac)

    Note over Svc,DB: COMMIT

    Note over Trigger,DB: Async — listener materialized view refresh
    Trigger->>DB: REFRESH MATERIALIZED VIEW CONCURRENTLY product_stock_view

    Svc-->>API: ReceptionResult{lines_processed, total_value_centimes}
    API-->>C: 200 {validated: true, ...}
```

### Calcul CMP/PMP

```
CMP (Coût Moyen Pondéré) :
  CMP_new = (qty_old * CMP_old + qty_recue * prix_achat_unitaire) / (qty_old + qty_recue)

PMP (Prix Moyen Pondéré le plus haut) :
  PMP_new = max(PMP_old, prix_achat_unitaire)

Utilisé pour :
- Valorisation stock comptable
- Marge théorique vente (prix_vente - CMP)
- Alerte achat plus cher que d'habitude (line.prix > PMP * 1.20)
```

---

## 9. Provisioning tenant DEVUP

> **Spec source** : Bloc 7 §7.4 (Provisioning workflow)
>
> **Endpoint** : `POST /admin/devup/tenants/provision`
>
> **Invariants** :
> - I1 : Atomique — TOUTE la séquence (Tenant + TenantBrand + TenantSettings + Membership initial + Outbox) est dans **un seul `async with session.begin():`**. Échec partiel impossible (F256 fix vague 3).
> - I2 : Vertical détermine seed data (rôles, scopes, configs)
> - I3 : Premier admin user créé avec password temporaire envoyé par email
> - I4 : Audit log spécifique DEVUP émis via Outbox (reste atomique avec le reste)

```mermaid
sequenceDiagram
    autonumber
    participant C as DEVUP Admin
    participant API as POST /admin/devup/tenants/provision
    participant Svc as ProvisioningService
    participant Repo as Repositories
    participant Seed as SeedDataService
    participant DB as PostgreSQL
    participant KMS as KMS
    participant Outbox as Outbox

    C->>API: POST /admin/devup/tenants/provision<br/>{slug, name, vertical_code, admin_email, ...}
    API->>API: require_scope("devup.tenant.provision")

    Note over Svc,DB: BEGIN TRANSACTION

    Svc->>Repo: check_slug_unique(slug)
    Repo->>DB: SELECT 1 FROM tenant WHERE slug = ?
    alt slug existe
        Svc-->>API: 409 Conflict
        API-->>C: 409 {detail: "Slug already taken"}
        Note over Svc,DB: ROLLBACK
    else slug libre
        Svc->>Repo: get_vertical(vertical_code)
        Repo->>DB: SELECT * FROM verticals WHERE code = ?
        alt vertical inconnu
            Svc-->>API: 400 Bad Request
            API-->>C: 400 {detail: "Unknown vertical"}
            Note over Svc,DB: ROLLBACK
        end

        Note over Svc: Création tenant + entités obligatoires (Phase 1 §09.l.317)<br/>F256 fix : TenantBrand + TenantSettings DOIVENT être créés ici<br/>(rollback partiel impossible car même TX `async with session.begin()`)

        Note over Svc: Bloc 7 §7.2 — Tenant.vertical = FK string verticals(code)<br/>(pas vertical_id int)

        Svc->>Repo: create_tenant(slug, name, vertical=vertical.code, deposit_policy, rfm_thresholds, ...)
        Repo->>DB: INSERT INTO tenants (vertical='location', ...)
        DB-->>Svc: tenant_id

        Svc->>Repo: create_tenant_brand(tenant_id, brand_palette, brand_dkim_domain, frontend_url)
        Repo->>DB: INSERT INTO tenant_brands (tenant_id, primary_color, ...)
        Note right of Repo: Palette obligatoire (F-01 prevention)<br/>+ frontend_url NOT NULL (login renvoi)

        Svc->>Repo: create_tenant_settings(tenant_id, vertical.default_settings)
        Repo->>DB: INSERT INTO tenant_settings (tenant_id, devis_default_expiry_days=30, default_tva_rate=0.20, ...)
        Note right of Repo: F265 fix : settings créés à provisioning<br/>→ pas de race condition à la 1ère lecture

        Note over Svc,Seed: Seed data selon vertical

        Svc->>Seed: provision_seed(tenant_id, vertical)

        Note over Seed: Pour vertical = location

        Seed->>Repo: create_default_categories(tenant_id, vertical.default_categories)
        Repo->>DB: INSERT INTO category (parent='Vaisselle'), (parent='Mobilier'), ...

        Seed->>Repo: create_default_loyalty_program(tenant_id, vertical.loyalty_template)
        Repo->>DB: INSERT INTO loyalty_program (...)

        Seed->>Repo: create_default_pricing_rules(tenant_id, vertical.default_pricing)
        Repo->>DB: INSERT INTO pricing_rule (...)

        Seed->>Repo: create_default_email_templates(tenant_id, vertical.email_templates)
        Repo->>DB: INSERT INTO email_template (...)

        Note over Svc: Création premier Account + TenantMembership<br/>(Bloc 2 §2.1 — User mort F339, RBAC v3 = Account + TenantMembership)

        Svc->>Svc: generate_temp_password() (24 chars cryptographic random)
        Svc->>KMS: hash_password_argon2(temp_password)
        KMS-->>Svc: hash

        Svc->>Repo: create_account(admin_email, hash, must_change_password=true)
        Repo->>DB: INSERT INTO accounts (email, password_hash, must_change_password, ...)
        DB-->>Repo: account_id

        Svc->>Repo: create_membership(account_id, tenant_id, role='admin')
        Repo->>DB: INSERT INTO tenant_memberships (account_id, tenant_id, role='admin', ...)

        Note over Svc: Feature flags par défaut

        Svc->>Repo: enable_default_feature_flags(tenant_id, vertical.default_flags)
        Repo->>DB: INSERT INTO feature_flag_tenants (...)

        Note over Svc: Audit DEVUP-spécifique

        Svc->>Repo: log_audit("devup.tenant.provision", actor=devup_admin, target=tenant_id)
        Repo->>DB: INSERT INTO audit_log (... + chain_hmac)

        Note over Svc,Outbox: Outbox events

        Svc->>Outbox: enqueue("TenantProvisioned", {tenant_id, admin_email, temp_password})
        Outbox->>DB: INSERT INTO outbox_events (...)

        Note over Svc,DB: COMMIT

        Svc-->>API: ProvisionResult{tenant_id, admin_user_id, temp_password (last time visible)}
        API-->>C: 201 {tenant_id, status: "provisioned", admin_temp_password: "..."}

        Note over Outbox: Async :<br/>- Email admin avec lien activation<br/>- Webhook DEVUP CRM<br/>- Slack #onboarding
    end
```

---

## 10. Export RGPD utilisateur

> **Spec source** : Bloc 6 §6.3 (RGPD Article 15)
>
> **Endpoints** : `POST /me/export`, `GET /me/exports/{task_id}/status`
>
> **Invariants** :
> - I1 : Export async — réponse immédiate avec task_id
> - I2 : PII déchiffrées au moment de l'export, contenu signé
> - I3 : Lien téléchargement TTL 24h, à usage unique
> - I4 : Audit log avec actor=user (auto-export)

```mermaid
sequenceDiagram
    autonumber
    participant C as User
    participant API as POST /me/export
    participant Svc as RGPDExportService
    participant Repo as Repositories
    participant Broker as RabbitMQ
    participant Worker as Celery Worker
    participant KMS as KMS
    participant Storage as Object Storage (S3/MinIO)
    participant Notif as Notification Service
    participant Audit as AuditService

    C->>API: POST /me/export
    API->>API: require_scope("me.export")
    API->>Svc: request_export(user_id)

    Note over Svc,Repo: Vérif rate limit (1 export / 30 jours / user)
    Svc->>Repo: count_recent_exports(user_id, days=30)
    alt > 0 export récent
        Svc-->>API: 429 Too Many Requests
        API-->>C: 429 {detail: "Already exported in last 30 days, next available: ..."}
    else ok
        Svc->>Repo: create_export_request(user_id, status='queued')
        Repo->>DB: INSERT INTO rgpd_export (status='queued', requested_at=NOW(), ...)
        DB-->>Svc: task_id

        Svc->>Broker: publish("rgpd.export", {task_id, user_id})

        Svc->>Audit: log("me.export.requested", actor=user_id, {task_id})

        Svc-->>API: 202 Accepted {task_id}
        API-->>C: 202 {"task_id": "...", "status": "queued"}
    end

    Note over Worker,Storage: ÉTAPE ASYNC — Worker

    Broker->>Worker: deliver rgpd.export(task_id, user_id)

    Worker->>Repo: update_export(task_id, status='processing', started_at=NOW())

    Note over Worker: Collecte données utilisateur

    Worker->>Repo: get_user(user_id) (PII chiffrées)
    Worker->>KMS: decrypt_user_pii(user, context={user_id, purpose='rgpd_export'})
    KMS-->>Worker: clear_pii

    Worker->>Repo: get_all_user_data(user_id)
    Note right of Repo: Récupère :<br/>- Profil + adresses<br/>- Réservations + lignes<br/>- Devis<br/>- Commandes<br/>- Loyalty card + transactions<br/>- Audit logs (own actions)<br/>- Sessions (truncated)<br/>- Email logs

    Repo-->>Worker: dataset (chiffré au repos, déchiffré ici)

    Worker->>Worker: serialize_to_json(dataset, indent=2)
    Worker->>Worker: generate_pdf_summary(dataset)

    Worker->>Worker: bundle = ZIP({data.json, summary.pdf, README.txt})

    Worker->>Worker: signature = sign_with_devup_key(bundle)
    Worker->>Worker: bundle.add("signature.sig", signature)

    Worker->>Storage: upload(path=f"rgpd-exports/{task_id}.zip", expires=24h)
    Storage-->>Worker: signed_download_url

    Worker->>Repo: update_export(task_id, status='ready', download_url=signed_url, expires_at=NOW()+24h)

    Worker->>Audit: log("me.export.completed", actor=user_id, {task_id, size_bytes})

    Worker->>Notif: send_email(user.email, template='rgpd_export_ready', {download_url})
    Note over Notif: Email contient lien direct vers /me/exports/{task_id}/download

    Worker-->>Broker: ack

    Note over C,API: ÉTAPE 3 — POLLING ou clic email

    C->>API: GET /me/exports/{task_id}/status
    API->>Repo: get_export(task_id, user_id)
    Repo->>DB: SELECT * FROM rgpd_export WHERE id = ? AND user_id = ?
    DB-->>API: export_record

    alt status = 'queued' OR 'processing'
        API-->>C: 200 {status: "processing"}
    else status = 'ready'
        API-->>C: 200 {status: "ready", download_url: "...", expires_at: "..."}
    else status = 'failed'
        API-->>C: 200 {status: "failed", error: "..."}
    end

    Note over C,Storage: Téléchargement

    C->>Storage: GET signed_url
    Storage->>Storage: verify signature (TTL not expired)
    Storage-->>C: bundle.zip

    Note over Audit: Le téléchargement est aussi loggé via webhook S3 → audit
```

---

## Annexes

### A. Convention rendu Mermaid

Tous les diagrammes ci-dessus sont valides Mermaid v10+ et rendus automatiquement par GitHub, GitLab, et la plupart des plateformes de doc (Notion, Confluence avec plugin).

Pour valider en local :
```bash
npm install -g @mermaid-js/mermaid-cli
mmdc -i 56-sequence-diagrams.md -o /tmp/diagrams/
```

### B. Mise à jour

Tout changement de flux critique impose :
1. Mise à jour du diagramme dans ce fichier
2. Update commit `docs(seq): update flow X for Y`
3. Review obligatoire par Lead Architect

### C. Diagrammes additionnels possibles (post-Phase 3)

Si nécessaire, ajouter :
- Workflow transfer-request (B5.S6)
- Audit chain verification nightly détail
- mTLS handshake /metrics scrape
- ETL EUROCIEL fuzzy match flow (post-fix EUROCIEL-PRIX-NULL-01)
- Rotation clés JWT (KMS)
- Rolling deployment zero-downtime

---

## 11. OAuth callback avec MFA gate (F404 — vague 5)

> **Spec source** : `13-apikey-oauth-passwordreset.md` §F404 + correction Sprint 1 T10
>
> **Endpoint** : `GET /auth/oauth/{provider}/callback`
>
> **Invariants** :
> - I1 : Si l'account a au moins 1 `auth_factor` actif → MFA challenge obligatoire (pas de bypass via Google/MS)
> - I2 : `mfa_verified` flag de session reflète l'état réel (pas `False` hardcodé)
> - I3 : Audit explicite des flows OAuth (success + mfa_required + failed)

```mermaid
sequenceDiagram
    autonumber
    participant C as Client (browser)
    participant API as POST /auth/oauth/{provider}/callback
    participant Provider as Google / Microsoft
    participant Svc as OAuthService
    participant Repo as AccountRepository
    participant MFA as MFAService
    participant DB as PostgreSQL
    participant Cache as Redis (mfa_pending)
    participant Audit as AuditService

    C->>API: GET /callback?code=...&state=...
    API->>Provider: exchange_code(code) → access_token + id_token
    Provider-->>API: id_token (claims: email, sub, email_verified)

    API->>Svc: handle_callback(provider, id_token)

    alt id_token invalide ou email_verified=false
        Svc->>Audit: log("oauth.callback.failed", reason="invalid_token_or_email")
        Svc-->>API: raise InvalidOAuthToken
        API-->>C: 401 Invalid OAuth response
    else id_token valide
        Svc->>Repo: find_account_by_email_or_oauth_link(email, provider, sub)
        Repo->>DB: SELECT account JOIN account_oauth_identities

        alt account inexistant + auto-link policy
            Note over Svc: F405 fix : auto-link uniquement si email_verified=true<br/>(prévention account takeover)
            Svc->>Repo: create_account_oauth_only(email, provider, sub)
            Repo->>DB: INSERT INTO accounts (email, hashed_password=NULL, ...)
            Repo->>DB: INSERT INTO account_oauth_identities (...)
            Repo-->>Svc: new account
        end

        Repo-->>Svc: account

        Note over Svc,MFA: F404 fix — vérifier MFA enrôlement AVANT émission tokens

        Svc->>MFA: is_enrolled(account.id)
        MFA->>Repo: query auth_factors actifs sur memberships(account.id)
        Repo->>DB: SELECT 1 FROM auth_factors af<br/>JOIN tenant_memberships tm ON tm.id = af.membership_id<br/>WHERE tm.account_id = ? AND af.is_active = true LIMIT 1

        alt account a au moins 1 auth_factor actif
            MFA-->>Svc: True

            Svc->>MFA: create_mfa_pending_token(account.id)
            MFA->>Cache: SET mfa_pending:{token} = account.id, EX 300
            MFA-->>Svc: pending_token

            Svc->>Audit: log("oauth.callback.mfa_required", account.id, provider)

            Svc-->>API: MFARequiredResponse{pending_token, challenge_url}
            API-->>C: 200 {"mfa_required": true, "pending_token": "...", "challenge_url": "/api/v1/auth/mfa/verify"}

            Note over C: Client redirige vers challenge MFA<br/>(TOTP/WebAuthn selon enrôlement)
        else account sans MFA enrôlé
            MFA-->>Svc: False

            Note over Svc: Pas de MFA → émission directe (compte sans MFA)
            Svc->>Repo: create_session(account.id, mfa_verified=False, oauth_provider=provider)
            Repo->>DB: INSERT INTO account_sessions (...)

            Svc->>Audit: log("oauth.callback.success", account.id, provider, mfa=false)

            Svc-->>API: TokenOut{access_token, refresh_token, expires_in}
            API-->>C: 200 {"access_token": "...", "refresh_token": "..."}
        end
    end
```

### Invariant CI associé

`check_no_mfa_bypass_oauth.py` (54-ci-invariants §20) — refuse le merge si une fonction
`_issue_oauth_tokens` ou `_open_session_and_issue` émet TokenOut sans appeler
`mfa_service.is_enrolled()` ou équivalent dans son corps.

---

## 12. WebAuthn enregistrement avec RP_ID per-tenant (F368 — vague 4)

> **Spec source** : `12-mfa-webauthn-pin.md` §F368 + correction Sprint 1 T11
>
> **Endpoints** : `POST /auth/webauthn/register/options`, `POST /auth/webauthn/register/verify`
>
> **Invariants** :
> - I1 : `rp_id` lu depuis `tenants.rp_id` (per-tenant), pas constante globale
> - I2 : `expected_origin` lu depuis `tenants.frontend_url` (per-tenant)
> - I3 : Démo Splendid 28/04 : enrôlement WebAuthn fonctionnel sur `splendid.events`

```mermaid
sequenceDiagram
    autonumber
    participant C as Client (browser splendid.events)
    participant API as POST /auth/webauthn/register/options
    participant MW as RequestContextMiddleware
    participant Svc as WebAuthnService(tenant)
    participant DB as PostgreSQL
    participant Browser as navigator.credentials

    C->>API: POST /register/options (cookie session)
    API->>MW: extract X-Tenant-ID OR cookie tenant_id

    Note over MW,DB: F295 + F368 fix — lecture tenant complet

    MW->>DB: SELECT id, rp_id, frontend_url, brand_display_name<br/>FROM tenants WHERE app_code = :app_code
    DB-->>MW: tenant{rp_id="splendid.events", frontend_url="https://splendid.events", ...}
    MW-->>API: request.state.tenant = tenant

    API->>Svc: WebAuthnService(db, tenant=request.state.tenant)
    Note right of Svc: rp_id = tenant.rp_id OR settings.JWT_ISSUER<br/>rp_name = tenant.brand_display_name OR "DEVUP"<br/>expected_origin = tenant.frontend_url OR settings.FRONTEND_URL

    Svc->>Svc: register_options(account)
    Svc-->>API: PublicKeyCredentialCreationOptions{<br/>  rp: {id: "splendid.events", name: "Splendid Events"},<br/>  challenge: ...,<br/>  user: {id, name, displayName},<br/>  pubKeyCredParams: [...]<br/>}

    API-->>C: 200 (options JSON)

    C->>Browser: navigator.credentials.create(options)
    Note over Browser: Authentificateur (YubiKey, Touch ID, ...)<br/>signe la challenge avec `rp_id="splendid.events"`<br/>→ credential bound au domaine
    Browser-->>C: PublicKeyCredential{id, response: {attestationObject, clientDataJSON}}

    C->>API: POST /register/verify (credential)
    API->>Svc: register_verify(credential, expected_origin="https://splendid.events", expected_rp_id="splendid.events")

    Note over Svc: F368 fix — verify avec RP_ID du TENANT, pas globalement Marveline
    Svc->>Svc: verify_registration_response(<br/>  credential, expected_rp_id=self.rp_id,<br/>  expected_origin=self.expected_origin<br/>)

    alt verify OK
        Svc->>DB: INSERT INTO auth_factors (membership_id, type='FIDO', credential_id, public_key, aaguid, ...)
        Svc-->>API: success
        API-->>C: 200 {"enrolled": true, "credential_id": "..."}
    else verify fail (mauvais rp_id, signature invalide, etc.)
        Svc-->>API: raise InvalidRpIdError
        API-->>C: 400 Invalid attestation
    end
```

### Régression bloquée

Si un dev hardcode `RP_ID = "marveline.com"` à la place de `tenant.rp_id` :
- INV-13 (53-tests-strategy §8.13) `test_invariant_webauthn_register_options__uses_tenant_rp_id` détecte → CI rouge
- Démo Splendid 28/04 reste protégée car le test E2E inclut un setup `tenant.rp_id="splendid.events"`

---

**Fin du document — 56-sequence-diagrams.md**

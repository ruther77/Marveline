# Stakeholders Validation — Legal / CFO / DPO

> **Objectif** : pour chaque stakeholder externe au dev, valider les engagements pris dans la refonte.
> **Format** : checklist + rendez-vous validation pré-démarrage Bloc concerné.

---

## 1. Legal / Compliance

### Engagements pris

| Engagement | Sprint | Article réglementaire |
|---|---|---|
| Audit log immutable HMAC blockchain | B6.S2 | SOC2 §10, ISO 27001 A.12.4 |
| Export RGPD Article 15 (download personal data) | B6.S2.T5 | RGPD Art. 15, 20 |
| Purge audit logs >7 ans | B6.S2.T6 | RGPD Art. 5.1.e (limitation conservation) |
| Login échec audité avec masking password | B6.S2.T3 | RGPD Art. 30 (registre activités) |
| `auto_suspend_uncertified` réel (pas placebo) | B6.S1.T5 | SOC2 §10 |
| PII envelope encryption (Customer + audit changes) | B4.S5.T1, B6.S2.T4 | RGPD Art. 32 |
| `tva_rate_snapshot` immutable post-emit | B3.S2 + B3.S3 | Article 289 CGI |
| Invoice immutable (CreditNote pour rectif) | B3.S1.T2 + B3.S2 | Article 289 CGI |
| `reference` UNIQUE per-tenant + séquence non régressive | B3.S1.T1 + B3.S1.T4 | Article 289 CGI (numérotation continue) |
| e-invoicing schema prep France 2026 | B3.S6 | Loi Finances 2024 + ordonnance e-invoicing |

### Validation requise

**RDV legal** : 1× avant démarrage Bloc 6 (audit refondu).

Documents à fournir :
- Description HMAC chain + verify nightly
- Description PII encryption (algorithme + KMS provider)
- Description retention 7 ans + procédure purge
- Description export Art.15 (formats CSV/JSON, TTL S3 24h)

### Risques legal résiduels

⚠️ **e-invoicing France** : activation différée 2026-09-01 — vérifier que tous les tenants sont prêts (PEPPOL ou ChorusPro selon B2B/B2G).

⚠️ **Audit chain** : si rupture détectée (verify_chain alert), procédure forensic à définir avec legal.

---

## 2. CFO / Finance

### Engagements pris (budget infra)

| Coût | Sprint | Estimation /mois |
|---|---|---|
| AWS KMS (envelope encryption) | B1.S3 | ~30€ (par 100k operations) |
| Postmark (email transactionnel) | B3.S5 | ~150€ (50k emails/mois) |
| Kubernetes (passage prod) | B6.S6 | ~500€-1000€ selon nodes |
| RabbitMQ HA cluster | B6.S7 | ~150€ (3 nodes) |
| OpenTelemetry (Tempo self-hosted ou Datadog) | B6.S6 | 0€ (Tempo) ou ~500€ (Datadog) |
| Prometheus + Grafana + Loki | continuous | ~100€ self-hosted |
| Cert-manager + Let's Encrypt | B6.S6 | 0€ |
| S3 export RGPD + audit archive | B6.S2 | ~50€ (Glacier après 1 an) |
| Sentry (error tracking) | continuous | ~30€ |
| **Total estimé** | | **~1000€-2000€/mois** |

### Validation requise

**RDV CFO** : 1× avant démarrage Bloc 6 (passage K8s + RabbitMQ + Postmark prod).

Présenter :
- Budget infra mensuel
- ROI : réduction ops time (auto-recovery, monitoring proactif)
- Comparaison vs status quo (Postmark vs SMTP custom = +120€/mois mais déliverabilité B2B)
- Plan progressif : self-hosted d'abord, managed si scale

### KPI à suivre

- Coût mensuel infra
- Coût par tenant (target < 50€/mois pour CaroCorp)
- Email gateway success rate (Postmark target > 99%)

---

## 3. DPO (Data Protection Officer)

### Engagements PII

| PII | Stockage | Encryption | Scope read |
|---|---|---|---|
| Customer.first_name, last_name | DB | KMS envelope (B4.S5.T1) | `customers:read_pii` |
| Customer.phone | DB | KMS envelope | `customers:read_pii` |
| Customer.address_line1/2 | DB | KMS envelope | `customers:read_pii` |
| Customer.email | DB clear | NON (lookup login) | `customers:read` |
| Customer.notes (allergies, etc.) | DB | KMS envelope | `customers:read_pii` |
| Supplier.contact_name | DB | KMS envelope | `suppliers:read_pii` |
| EventIncident.description | DB | KMS envelope | `incidents:read_pii` |
| Account.hashed_password | DB | Argon2id | N/A (pas exposé) |
| Audit.changes (peut contenir PII) | DB | KMS envelope (B6.S2.T4) | `audit:read_pii` |
| TOTP secret | DB | KMS envelope | N/A |
| WebAuthn credentials | DB | clear (public key) | N/A |
| Postmark token tenant | DB | KMS envelope | N/A |
| Wireguard private keys | DB | KMS envelope | N/A |

### Validation requise

**RDV DPO** : 1× avant démarrage Bloc 4 (PII chiffrement complet).

Documents :
- DPIA (Data Protection Impact Assessment)
- Liste exhaustive PII + classification
- Procédures retention + purge
- Procédure réponse demande Article 15 (export) + Article 17 (effacement)
- Sub-processors (Postmark, AWS KMS, S3 archive) + DPA signés

### Procédure DPO bug PII

Si PII leak détecté :
1. Contention immédiate (flag → false, désactiver endpoint)
2. Audit chain verify (HMAC) — détecter scope leak
3. Notification CNIL si breach > 72h (Art. 33)
4. Notification users impactés (Art. 34) si risque élevé

---

## 4. Sub-processors (DPA)

DEVUP utilise les sub-processors suivants (DPA signé requis) :

| Provider | Service | Données traitées | DPA |
|---|---|---|---|
| AWS | KMS, S3 (audit archive, RGPD export) | PII chiffrée | ✅ AWS Customer Agreement |
| Postmark (Wildbit LLC) | Email transactional | Email + nom destinataire | ⏳ À signer pré-Bloc 3.S5 |
| Cloudflare | CDN, DDoS | IP + headers | ✅ |
| Sentry (Functional Software, Inc) | Error tracking | Stack traces (peuvent contenir PII) | ⏳ À auditer pour PII scrubbing |
| Datadog (si choisi B6.S6) | APM, traces | trace data (potentiellement PII) | ⏳ À signer si choisi |

**À mettre à jour** : page CGV `/legal/sub-processors`.

---

## 5. Sales / Customer Success

### Communication client

| Sprint | Communication client |
|---|---|
| B3.S1 | Email "endpoint /charges déprécié, utiliser /credit-note" |
| B6.S2 | Banner UI "Export de vos données disponible (Art. 15)" |
| B7.S3 | Email "Nouvelle interface — AppSelector" |
| Démo Splendid 28/04 | Préparation démo WebAuthn fonctionnel (B2.S4 livré J-1) |

### Validation requise

**RDV CS** : Hebdo pendant rollout pour synchro communication.

---

## 6. Calendrier validation stakeholders

```
T+0   ──┬── RDV Legal (Bloc 6 audit)
        ├── RDV CFO (budget infra)
        ├── RDV DPO (PII Bloc 4)
        └── RDV CS (calendrier rollout)

T+5   ──── Bloc 1+2 démarrage (no validation requise)

T+10  ──── Bloc 3 démarrage : RDV Legal #2 (article 289 + e-invoicing)

T+15  ──── Bloc 4 démarrage : RDV DPO #2 (PII migration backfill)

T+20  ──── Bloc 6 démarrage : RDV Legal #3 (HMAC + export RGPD live test)

T+22  ──── Bloc 7 démarrage : RDV CS #2 (UX AppSelector communication)

T+24  ──── Go-live : RDV final tous stakeholders
```

---

## 7. Documents à produire pour stakeholders

- [ ] DPIA (Data Protection Impact Assessment)
- [ ] Procédure réponse droits RGPD (Art. 15-22)
- [ ] Liste sub-processors + DPA signés
- [ ] Budget infra detailed
- [ ] Plan rollout commercial (communication client)
- [ ] Runbook ops post-Bloc 6
- [ ] Audit log retention policy
- [ ] PII inventory + classification

---

**Fin du document — 70-stakeholders-validation.md**

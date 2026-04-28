# Analyse dette technique — 2026-04-16

**Contexte** : audit complet backend + frontend suite refactor dual-brand Marveline/Splendid. Objectif : modéliser la meilleure solution pour chaque dette, proposer un ordre d'implémentation avec ROI.

**Méthode** : pour chaque dette → état actuel + impact + options + recommandation + effort.

---

## D1 — Invoice.advance_rate : schéma Pydantic vs modèle SQLAlchemy désynchronisés

### État actuel
- `app/schemas/invoice.py:204` déclare `advance_rate: float = Field(default=0.4)` sur `InvoiceList` et `InvoiceResponse`
- `app/models/invoice.py` n'a PAS de colonne `advance_rate`
- Au runtime, la sérialisation lit `invoice.advance_rate` → `AttributeError`
- Fix QA : `getattr(invoice, "advance_rate", None) or 0.40` dans `invoice_pdf.py:75`

### Impact
- **PDF factures cassées** avant le fix QA
- **Sérialisation API** `/invoices/{id}` retournait probablement une erreur 500 silencieuse (capturée par FastAPI)
- **Convention violée** : CLAUDE.md dit "BigInteger centimes, schema et modèle doivent être cohérents"

### Options

**A. Ajouter la colonne au modèle + migration**
- Type : `advance_rate: float NOT NULL DEFAULT 0.40`
- Migration Alembic non-destructive : `ADD COLUMN` avec default
- Pro : respect de la convention schéma/modèle, traçabilité par facture
- Con : toutes les factures legacy auront 0.40 même si CGV différentes à l'époque (non-critique)

**B. Lire depuis `tenant_settings.advance_rate`**
- Le champ existe déjà en DB (`TenantSettings.advance_rate`)
- Supprimer le champ du schéma, calculer à la volée dans les services
- Pro : zéro migration, unique source de vérité (tenant_settings)
- Con : refactor des schémas + services + frontend (qui lit peut-être `invoice.advance_rate`)

**C. Laisser le fix `getattr` actuel**
- Pro : zéro effort
- Con : dette permanente, future régression garantie

### Recommandation : **Option A** (effort 30min)
Migration Alembic + default 0.40 + populate les factures existantes. Schéma/modèle alignés, historique conservé.

---

## D2 — Isolation des tests unitaires : 360 fails / 1782

### État actuel
- 20% des tests cassés (memory/tech-debt-tests.md 2026-04-14)
- Catégorisation en 8 causes root :
  - **Cat A** — IAM v2 refactor (`user_id` → `account_id`) : ~20 tests
  - **Cat B** — KMS signature élargie : ~13 tests
  - **Cat C** — Services async, mocks sync : ~60+ tests
  - **Cat D** — Attributs `_cents` legacy : ~15 tests
  - **Cat E** — Régression batch sed ISO-APP-01 : ~25 tests (déclencheur : `deposit_amount` undefined)
  - **Cat F** — Refactors constantes/méthodes : ~10 tests
  - **Cat G** — Assertions métier cassées : ~20+ tests
  - **Cat H** — Inconnues (test_redis 51, test_mfa 41) : variable

### Impact
- **CI rouge permanente** → personne ne trust plus les tests
- **Risque de régression silencieuse** : on pourrait casser un comportement critique sans que ça apparaisse dans la baseline déjà rouge
- **Coût cognitif dev** : quand un test fail, on ne sait pas si c'est nous ou la dette

### Options

**A. Sprint complet 25-40h**
- Traiter Cat E → A → B → D → C → F → G → H dans cet ordre (memory:rec 2026-04-14)
- Pro : CI verte à nouveau, baseline propre
- Con : 3-5 jours de dev, zéro valeur business visible

**B. Sprint ciblé 1 journée : Cat E + A + B (15-20% des fails)**
- Fix régressions batch sed + IAM v2 + KMS crypto
- Pro : ~45 tests récupérés en 4-6h, plus représentatif
- Con : reste 300+ fails

**C. Nouveau baseline : split tests en `legacy_broken/` skip par défaut**
- Move fails into a quarantine dir, tag as xfail
- CI check only passes
- Pro : CI verte immédiate
- Con : laisse la dette pourrir, risque de ne jamais y revenir

**D. Approche hybride**
- Semaine 1 : Option C (quarantine)
- Semaine 2-4 : progressive reintegration 5-10 tests/jour
- Pro : CI verte + roadmap réaliste
- Con : discipline requise, risque de dérive

### Recommandation : **Option B** (1j) puis plan pour C→B reste (sprint dédié plus tard)
Prio B immédiat car Cat E est une régression introduite lors d'un refactor précédent (on crée pas de nouvelle fonctionnalité, on répare). Le reste est un **vrai sprint dédié**, à planifier quand le rythme démo ralentit.

---

## D3 — Legacy attribute access : `.price_per_day`, `.deposit_amount`, `.paid_amount`

### État actuel
- Plusieurs tests (~15) accèdent à des attributs qui n'existent plus
- Le modèle a `price_per_day_cents`, `deposit_amount_cents`, etc.
- Les tests legacy n'ont pas été mis à jour lors du refactor cents

### Impact
- Tests cassés → Cat D dans la dette tests
- Pas d'impact prod (le code prod utilise `_cents`)

### Options

**A. Fix les tests (renommer accès attribut)**
- sed `\.price_per_day\b` → `.price_per_day_cents` sur les fixtures/tests
- Pro : simple, bien bordé
- Con : ~2h de fix mécanique

**B. Ajouter des `@property` backwards-compatible dans les modèles**
- `Product.price_per_day` renvoie `self.price_per_day_cents / 100`
- Pro : zéro changement dans les tests
- Con : **ajoute de la complexité à ajouter 5 properties** + tests deviennent ambigus (quelle unité est retournée ?). Anti-pattern.

### Recommandation : **Option A** (2h, inclus dans D2)

---

## D4 — Celery tasks (`app/tasks/notifications.py`) ne propagent pas le brand

### État actuel
- Les méthodes `NotificationService.send_*` acceptent `brand: dict | None = None` (ajouté aujourd'hui)
- Mais les tâches Celery `app/tasks/notifications.py::send_reservation_confirmed_email` sont appelées sans brand
- Source appel : `app/services/reservation.py:685` → `send_reservation_confirmed_email.delay(email=..., customer_name=..., ...)` — pas de `brand`
- Conséquence : emails générés par Celery utilisent le fallback Marveline, même pour Splendid

### Impact
- **Splendid client reçoit un email "Marveline"** lors de la confirmation de sa réservation
- Surface visible mais peu fréquente (hors démo)

### Options

**A. Propager brand dict à travers Celery**
- Modifier les 6 tasks Celery pour accepter `brand_dict=None`
- Modifier les 6 callers dans `app/services/{reservation,invoice,...}.py` pour loader brand et le passer
- Sérialiser le dict dans la queue Redis/RabbitMQ (déjà supporté par Celery)
- Pro : explicite, traçable
- Con : touche 6 tasks + 6 call sites, couplage

**B. Celery task charge le tenant via `tenant_id` déjà passé**
- Actuellement beaucoup de tasks ont le `reservation_id` ou `tenant_id` en param
- Dans la task, `brand = load_brand_for_tenant_sync(db, tenant_id)` (helper sync déjà écrit)
- Pro : pas de sérialisation du dict, single source of truth
- Con : chaque task fait 1 DB round-trip pour le tenant_settings → pas dramatique, c'est en background

**C. Middleware Celery avec contextvar du tenant_id**
- `@before_task_publish` → extract tenant_id du caller → inject dans task context
- Pro : transparent, zéro changement dans les callers
- Con : magie implicite, difficile à débugger

### Recommandation : **Option B** (2h)
Task charge le brand depuis la DB via le `tenant_id` déjà présent (ou déduit depuis la réservation/facture). Pas de sérialisation, pas de couplage aux callers.

---

## D5 — Brand identity : `tenant_settings` vs table `Brand` dédiée

### État actuel
- `TenantSettings` a `company_name`, `company_email`, `company_phone`, `company_address`
- Ces champs servent de **proxy pour l'identité marque** dans les templates
- Utilisés aussi pour factures, tickets ESC/POS, métadonnées commerciales
- `colors.primary`, `logo`, `shortName` restent **frontend-only** (`src/brand/*.ts`)

### Impact
- **Identité marque éclatée** entre backend (tenant_settings.company_*) et frontend (brand/*.ts)
- Impossible pour un admin de changer logo/couleur sans redéployer
- Pas de "white-label self-service" possible

### Options

**A. Laisser tel quel (MVP)**
- `tenant_settings.company_*` pour backend, `brand/*.ts` pour frontend
- Pro : zéro changement
- Con : 2 sources à garder synchronisées, évolution future bloquée

**B. Table dédiée `tenant_brand`**
- Nouvelle table `tenant_brands(tenant_id, display_name, legal_name, primary_color, logo_url, logo_square_url, favicon_url, tagline, contact_email, contact_phone, address)`
- Endpoint `GET /api/v1/tenant/brand` (public, avant login) → retourne le brand du tenant cible
- Frontend au boot : `fetch('/api/v1/tenant/brand?host=splendid.yourdomain.com')` → applique dynamiquement
- Pro : white-label self-service possible, évolution clean
- Con : migration + endpoint + refactor brand/select.ts (lit API au lieu de const), charge réseau initiale

**C. Élargir `tenant_settings` avec colonnes brand**
- Ajouter `brand_display_name`, `brand_logo_url`, `brand_primary_color`, etc.
- Reuse le modèle existant
- Pro : peu de migration, garde l'agrégation business+brand ensemble
- Con : `tenant_settings` devient énorme, mélange concerns (CGV + tarifs + identité + imprimante + brand)

### Recommandation : **Option B** (4-6h) **pour la roadmap**, **pas maintenant**
- Pour 2 tenants (Marveline + Splendid) : option A suffit
- Dès 3-5 tenants : option B devient indispensable
- Skip option C (mélange concerns)

---

## D6 — Row-Level Security (RLS) Postgres pour isolation tenant dure

### État actuel
- Isolation tenant = application-level (`BaseRepository._apply_tenant_filter()`)
- Si une requête oublie le filtre → fuite cross-tenant potentielle
- Postgres RLS non activée
- Doc `docs/carocorp-auth/10-MULTI-TENANT-OPS.md` décrit RLS comme prévu

### Impact
- **Risque P0** : un bug côté repo qui oublie `filter(tenant_id=...)` = fuite data
- **Défense en profondeur manquante** : une seule couche de protection

### Options

**A. Activer RLS sur tables sensibles (customers, invoices, reservations, audit_logs)**
- `ALTER TABLE customers ENABLE ROW LEVEL SECURITY`
- `CREATE POLICY tenant_isolation ON customers USING (tenant_id = current_setting('app.current_tenant_id')::int)`
- Dans `get_async_db()` : `SET LOCAL app.current_tenant_id = <tid>` au début de chaque requête
- Pro : défense en profondeur, même un bug repo ne fuite pas
- Con : 1h config + test + subtilités FK cross-tenant (ex : delivery_zones cross-tenant catalogue) à gérer

**B. Audit / linter qui détecte les requêtes sans `tenant_id` filter**
- Hook mypy ou règle CI
- Pro : prévention statique
- Con : complexe à écrire, faux positifs

**C. Ne rien faire**
- Accepter le risque application-level
- Pro : zéro effort
- Con : P0 latent

### Recommandation : **Option A** (2h) **avant de signer un contrat avec un 3e tenant**
- Marveline + Splendid en démo : risque acceptable
- Production multi-tenant réel : RLS indispensable

---

## D7 — MFA_ISSUER_NAME hardcodé + FRONTEND_URL single-valued

### État actuel
- `app/core/config.py:114` : `MFA_ISSUER_NAME: str = "Marveline"`
- `settings.FRONTEND_URL` : une seule URL pour toute l'app
- Utilisé dans emails (liens "Accéder à votre espace"), dans QR code MFA

### Impact
- **QR code MFA** pour Splendid user affiche "Marveline" dans leur authenticator app → confusion
- **Liens email** Splendid pointent vers marveline.fr au lieu de leur propre URL

### Options

**A. Paramétrer par tenant via `tenant_settings`**
- Ajouter `frontend_url` + `mfa_issuer_name` dans tenant_settings
- Les services MFA et emails lisent par tenant
- Pro : pragmatique, peu de code
- Con : encore un ajout à tenant_settings

**B. Table `tenant_brand` (option D5-B)**
- Inclus dans la solution D5
- Pro : cohérent
- Con : couplé à D5

**C. Multi-sub-tenant par subdomain en nginx**
- `marveline.fr` vs `app.le-splendid.events` → Host header → backend detecte tenant
- Pro : URL "belle" par client
- Con : infra complexe, DNS à gérer par client

### Recommandation : **Option A** maintenant (2h), migration vers B quand D5-B fait

---

## D8 — PWA manifest.json + Service Worker statiques

### État actuel
- `frontend/apps/marveline/public/manifest.json` hardcode "Marveline", `#d940a8`, icônes rose
- Service Worker généré au build avec VITE_BRAND baked in
- Splendid build produit un SW spécifique à Splendid, mais si un utilisateur revient sur le même container/URL avec un autre brand → stale SW

### Impact
- **Client installe Splendid en PWA** → nom "Marveline" dans son lanceur (démo = dégradation image marque)
- **Splendid SW cache des URL Marveline** si l'utilisateur a visité Marveline avant (cas observé pendant la QA)
- **Theme-color initial** dans la barre d'adresse mobile = Marveline rose avant que JS ne corrige → FOUC

### Options

**A. Vite plugin qui génère manifest par brand au build**
- `vite-plugin-pwa` supporte `manifestFilename` et `injectRegister`
- Générer `manifest.lesplendid.json` / `manifest.marveline.json` selon `VITE_BRAND`
- Pro : bon UX utilisateur final (PWA correctement brandée)
- Con : ~2h de config + test cross-browser

**B. Manifest dynamique servi par backend**
- Nginx / FastAPI sert `/manifest.json` en lisant brand depuis Host header
- Pro : totalement dynamique, pas de rebuild
- Con : complexité, moins courant en PWA land

**C. Désactiver PWA pour Splendid en dev**
- Laisser seulement Marveline en PWA prod
- Pro : zéro effort
- Con : Splendid installable en PWA génère du "Marveline" dans le lanceur

**D. Désenregistrer SW au boot si brand mismatch**
- Au boot, comparer `BRAND.code` avec un marqueur dans localStorage/IDB
- Si mismatch → unregister + reload
- Pro : robuste, protège contre stale cache
- Con : 20 lignes dans main.tsx, reload forcé un peu brutal

### Recommandation : **A + D** (3-4h)
- A pour l'installation PWA correcte
- D pour le cas "même browser, 2 domaines" qui nous a frappé pendant la QA

---

## D9 — 2 tunnels (ngrok + cloudflared) + URLs éphémères

### État actuel
- ngrok free → `*.ngrok-free.dev` avec interstitiel
- cloudflared quick tunnel → `*.trycloudflare.com` sans interstitiel
- Les 2 URLs changent à chaque restart container
- Setup actuel : ngrok Marveline + cloudflared Splendid

### Impact
- **Fragilité démo** : si un container tunnel crash samedi matin, nouvelle URL et bit.ly est cassé
- **Ops overhead** : 2 systèmes à maintenir
- **Experience client** : ngrok free impose un clic pour la démo Marveline

### Options

**A. Cloudflare Named Tunnel (stable URL)**
- Requires : compte CF gratuit + domaine sur CF
- `cloudflared tunnel create splendid-demo` + route `splendid.yourdomain.com → frontend-splendid:80`
- Pro : URL stable, pas d'interstitiel, gratuit
- Con : 30min setup, besoin d'un domaine

**B. Tunnelto / LocalTunnel / Serveo**
- Alternatives ngrok
- Pro : bonnes alternatives
- Con : pas de stabilité garantie

**C. Passer ngrok en payant ($8/mois)**
- URL stable + pas d'interstitiel
- Pro : zéro changement codebase
- Con : coût récurrent pour dev

**D. VPS + reverse proxy prod-like**
- Louer un VPS à 5€/mois, déployer via docker compose, nginx + Letsencrypt
- Pro : infrastructure "propre", démo = production-ready URL
- Con : 2-3h de setup, maintenance

### Recommandation : **Option A** (1h) avant samedi
DEVUP a probablement un domaine déjà (devup.fr ?). Créer des sous-domaines `marveline.demo.devup.fr` + `splendid.demo.devup.fr`.

---

## D10 — Initial HTML fallback Marveline-only dans `index.html`

### État actuel
- `frontend/apps/marveline/index.html` contient `<style>:root { --brand-primary-rgb: 185 108 196; ... }</style>` hardcodé Marveline
- Même `<title>Marveline</title>`, `<meta theme-color="#d940a8">`
- Au boot Splendid, FOUC : rose visible → JS charge → doré

### Impact
- **Flash of wrong brand** (200-500ms) au boot — visible en démo, pas professionnel
- **Theme-color mobile** affiche rose pendant ce temps sur la status bar iOS

### Options

**A. Vite plugin de substitution build-time**
- `define: { __BRAND_CSS_VARS__: JSON.stringify(brandCssVarsFor(VITE_BRAND)) }`
- `index.html` : `<style>{__BRAND_CSS_VARS__}</style>`
- Pro : HTML servi au browser contient déjà les bonnes valeurs
- Con : 30min de config Vite

**B. 2 fichiers index.html, un par brand**
- `vite.config.ts` copie `index.marveline.html` ou `index.lesplendid.html` → `index.html` selon env
- Pro : simple à comprendre
- Con : duplication de fichier, divergence possible

**C. Nginx sub_filter au vol**
- Nginx remplace les CSS vars dans le HTML au serve
- Pro : totalement dynamique runtime
- Con : couplage proxy, perf légère

### Recommandation : **Option A** (30min)
Vite plugin custom qui lit `VITE_BRAND` et injecte le bon snippet dans index.html.

---

## D11 — `tenants.app_code` n'a pas de valeur "lesplendid"

### État actuel
- Check constraint `app_code IN ('marveline', 'epicerie', 'restaurant')`
- Splendid tenant setté à `app_code='marveline'` (pour cohabiter avec le frontend marveline)
- ISO-APP-01 middleware vérifie `JWT.tid tenant.app_code === X-App-Code header`

### Impact
- **Confusion sémantique** : Splendid n'est pas Marveline mais hérite du code app Marveline
- **Si on voulait ajouter** un tenant "wedding-planner" ou autre → même problème
- **Implicite** : "app" = bundle front+backend, "brand" = habillage → ils sont conflés aujourd'hui

### Options

**A. Laisser tel quel**
- Pro : zéro changement
- Con : dette sémantique permanente, accumulation

**B. Séparer `app_code` et `brand_code` dans `tenants`**
- `app_code='marveline'` (quel bundle de features) + `brand_code='lesplendid'` (habillage)
- Migration : add column `brand_code NOT NULL DEFAULT app_code`
- ISO-APP-01 continue sur `app_code`, brand system lit `brand_code`
- Pro : propre, extensible
- Con : migration + refactor middleware

**C. Élargir la check constraint**
- `app_code IN ('marveline', 'epicerie', 'restaurant', 'lesplendid', ...)`
- Mais `lesplendid` n'est pas un app, c'est un brand → faux sens
- Con : confusion amplifiée

### Recommandation : **Option B** (2h)
Propre, extensible pour futurs clients white-label. À planifier dès qu'on a 3+ tenants.

---

## D12 — TS errors pré-existantes (AuditLogsPage, AgendaPage, routing)

### État actuel
- `tsc --noEmit` : ~20 erreurs pré-existantes
- Principales :
  - `AuditLogsPage.tsx:317,402` : `Type 'null' cannot be used as an index type`
  - `AgendaPage.tsx` : TanStack Router typing mismatch
  - Plusieurs `searchParams` avec mauvais type inference

### Impact
- **Dev blind** : on ignore les TS errors car toujours rouges, on peut louper une vraie erreur introduite
- **CI TypeScript** probablement désactivée ou noémit

### Options

**A. Fix à la volée chacune (~1h par erreur)**
- Traiter file-par-file
- Pro : baseline verte
- Con : 20h

**B. Snapshot baseline actuelle, bloquer les nouvelles erreurs uniquement**
- Tool : `tsc-baseline` ou script custom qui compare
- Pro : évite régression future, ne force pas à fixer maintenant
- Con : dette jamais remboursée

**C. Désactiver strict mode temporairement**
- `strictNullChecks: false`
- Pro : moins d'erreurs
- Con : perd la valeur de TS, anti-pattern

### Recommandation : **Option B** immédiatement + batch A en sprint dédié
Ajouter `tsc-baseline` dans le pipeline de CI. Progressive fix 2-3 errors/semaine.

---

## D13 — Brand fallback duplicates (index.html, select.ts, notification.py)

### État actuel
- 3 endroits hardcodent la palette Marveline :
  - `index.html` inline `<style>`
  - `src/brand/select.ts` — fallback si env manquant
  - `src/brand/marveline.ts` — source of truth
- Backend hardcode "Marveline SAS" dans :
  - `invoice_pdf.py::_DEFAULT_BRAND`
  - `notification.py::_render_and_send` setdefault
  - 6 send_* methods

### Impact
- **Changer la palette Marveline** = modifier 3 fichiers
- **Risque de divergence** (couleurs qui drift)

### Options

**A. Générer `index.html` CSS vars depuis `marveline.ts` au build**
- Vite plugin (même que D10)
- Backend : centraliser le fallback Marveline dans `invoice_pdf.py::_DEFAULT_BRAND`, les autres l'importent
- Pro : une seule source par stack
- Con : Vite plugin custom

**B. Code generator** : un script qui lit `brand/marveline.ts` et crache les fallbacks où nécessaire
- Pro : DRY strict
- Con : build-time complexe

### Recommandation : **Option A** (1h, à faire en même temps que D10)

---

## Synthèse & priorisation

| # | Dette | Effort | Impact | Urgence |
|---|---|---|---|---|
| D1 | `Invoice.advance_rate` schéma vs modèle | 30min | Moyen | Haut (PDF) |
| D2 | Tests cassés 360/1782 | 25-40h | Haut | Moyen (sprint dédié) |
| D3 | Attributs `.price_per_day` legacy | 2h | Bas | Moyen |
| D4 | Celery tasks sans brand | 2h | Moyen | Moyen |
| D5 | `tenant_settings` vs table `Brand` | 4-6h | Haut (scalabilité) | Bas (pour 2 tenants) |
| D6 | Postgres RLS | 2h | Haut (sécurité) | Haut (3e tenant) |
| D7 | MFA_ISSUER + FRONTEND_URL hardcodés | 2h | Moyen | Moyen |
| D8 | PWA manifest + SW statiques | 3-4h | Haut (UX client) | Moyen |
| D9 | Tunnels ngrok+CF éphémères | 1h | Haut (démo) | **Critique** (samedi) |
| D10 | FOUC index.html | 30min | Moyen (UX) | Moyen |
| D11 | `tenants.app_code` hérité | 2h | Bas (cosmétique) | Bas |
| D12 | 20 TS errors | 20h+ | Bas (pas de régression prod) | Bas |
| D13 | Duplicate fallbacks | 1h | Bas | Bas |

### Roadmap recommandée

**Sprint 1 (avant samedi, ~4h)**
- D9 : Cloudflare Named Tunnel pour stabilité démo
- D1 : fix `advance_rate` proprement avec migration
- D4 : brand dans Celery tasks (si emails testés)
- D10 + D13 : Vite plugin index.html dynamique

**Sprint 2 (semaine prochaine, ~1 jour)**
- D8 : PWA manifest per-brand + SW unregister au mismatch
- D7 : MFA + FRONTEND_URL par tenant
- D2 partiel (Cat E + A + B) : ~6h de fix

**Sprint 3 (à planifier)**
- D5 : table `tenant_brand` (préparer white-label)
- D6 : RLS Postgres
- D11 : séparer `app_code` / `brand_code`

**Sprint 4 (dette test)**
- D2 reste (Cat C, D, F, G, H)
- D3 : legacy attributes
- D12 : TS errors

---

## Anti-patterns à ne PAS faire

- ❌ **Patcher avec des @property** pour garder la backward compat attributs (complexité cachée, ambiguïté unités)
- ❌ **sed global** sur les tests (on sait maintenant que ça casse les fixtures internes)
- ❌ **Désactiver les tests** sans les mettre en quarantaine tracée
- ❌ **Accepter la dette "temporairement"** sans date de traitement inscrite dans le backlog

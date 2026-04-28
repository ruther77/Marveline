# Sprint B2.S1 — Hotfixes IAM

> **STATUT** : ⏳ À démarrer après B1.S5
> **DURÉE MAX** : 1.5 semaines
> **OWNER** : Dev2 (lead Bloc 2)
> **BLOQUE** : B2.S2 → B2.S5 + tout B3 (auth fonctionnel pré-requis)
> **DÉPEND DE** : Bloc 1 complet (RLS + KMS + Outbox)
> **OBJECTIF** : Corriger les frictions IAM qui ne sont pas P0 prod (déjà dans Sprint 1) mais bloquent la consolidation Bloc 2 — token refresh rotation, password policies, session fingerprint, audit log enrichments.

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B2.S1.T1** | Token refresh rotation enforcement (F306) | P1 | 1 j | B2.S4 |
| **B2.S1.T2** | Password complexity policy + breach check (F310) | P1 | 1 j | aucun |
| **B2.S1.T3** | Session fingerprint device tracking (F311) | P1 | 1.5 j | B2.S4 sessions cascade |
| **B2.S1.T4** | Audit log enrichments (actor_type, ip, user_agent) | P1 | 0.5 j | B6.S2 |
| **B2.S1.T5** | Rate-limit endpoints sensibles (login/forgot/reset) | P0 | 0.5 j | aucun |
| **B2.S1.T6** | F388 backup codes existence + chiffrement KMS | P1 | 1 j | B2.S5 |
| **B2.S1.T7** | **TR-64 / Vague 2** — Templates email i18n FR (`password_reset`, `mfa_setup`, `welcome`, `email_change_verify`) avec Jinja2 + assets brand_logo per-tenant | P1 | 0.5 j | B6.S1.T8 |

**Total effort** : 5.5 jours-homme.

---

# Story B2.S1.T1 — Token refresh rotation enforcement

## Contexte

**Friction** : F306 (cf. `02-core-security.md`)
**Sévérité** : P1 — refresh tokens ré-utilisables en cas de fuite
**Code source** : `app/services/token.py`

### Description

Pattern OAuth 2.0 RFC 8252 § 4.1 : les refresh tokens doivent **tourner à chaque utilisation** (ancien révoqué quand le nouveau est émis). Si un refresh token fuite (logs, capture réseau), il devient utilisable jusqu'à expiration. Avec rotation, l'usage par l'attaquant invalide le token légitime de l'utilisateur → détection automatique.

```python
# app/services/token.py (état actuel — pas de rotation)
async def refresh_access_token(refresh_token: str) -> TokenPair:
    payload = decode_token(refresh_token, expected_audience="...:refresh")
    new_access = create_access_token(...)
    # ❌ MANQUE : pas de revoke + emit nouveau refresh
    return TokenPair(access=new_access, refresh=refresh_token)  # même refresh réutilisable
```

## Solution

```python
# app/services/token.py (refacto)
async def refresh_access_token(refresh_token: str, db: AsyncSession) -> TokenPair:
    """Rotation : ancien refresh révoqué, nouveau émis.

    Si l'ancien refresh est utilisé deux fois (replay attack ou fuite),
    le second usage est rejeté → audit alert "refresh_token_replay_detected".
    """
    payload = decode_token(refresh_token, expected_audience="...:refresh")
    jti = payload["jti"]

    # 1. Vérifier que le jti n'est pas déjà révoqué (replay detection)
    if await refresh_token_repo.is_revoked(db, jti):
        await audit_service.log(
            "auth.refresh.replay_detected",
            account_id=payload["sub"],
            metadata={"jti": jti}
        )
        raise TokenInvalid("Refresh token already used (replay detected)")

    # 2. Révoquer l'ancien
    await refresh_token_repo.revoke(db, jti, reason="rotated")

    # 3. Émettre nouveau pair
    new_jti = str(uuid.uuid4())
    new_access = create_access_token(sub=payload["sub"], ...)
    new_refresh = create_refresh_token(sub=payload["sub"], jti=new_jti, ...)
    await refresh_token_repo.create(db, jti=new_jti, account_id=payload["sub"], ...)

    return TokenPair(access=new_access, refresh=new_refresh)
```

## Tests

```python
@pytest.mark.asyncio
async def test_refresh__rotation__old_token_revoked(client, account):
    """F306 fix : ancien refresh révoqué après usage."""
    tokens1 = await login_helper(client, account)
    tokens2 = await client.post("/auth/refresh", json={"refresh_token": tokens1.refresh})
    assert tokens2.status_code == 200

    # Réutiliser l'ancien refresh → 401 + audit
    response = await client.post("/auth/refresh", json={"refresh_token": tokens1.refresh})
    assert response.status_code == 401
    # Replay alert audit présent
```

## DoD

- [ ] Rotation implémentée (ancien révoqué + nouveau émis)
- [ ] Replay detection + audit `auth.refresh.replay_detected`
- [ ] 2 tests E2E verts

---

# Story B2.S1.T2 — Password complexity policy + breach check

## Contexte

**Friction** : F310 (cf. `02-core-security.md`)
**Sévérité** : P1 — comptes compromettables via mots de passe faibles

### Description

Policy actuelle : minimum 8 caractères. Manque :
1. Complexité (3 sur 4 catégories : maj/min/chiffre/spécial)
2. Vérification HaveIBeenPwned k-anonymity (les 5 premiers chars du SHA1, lookup API publique pas de leak)
3. Liste interdite top 10000 (memory check, pas API)

## Solution

```python
# app/services/password_policy.py
import re
import hashlib
import httpx


class PasswordPolicy:
    MIN_LENGTH = 12
    MIN_CATEGORIES = 3  # sur {lower, upper, digit, special}

    async def validate(self, password: str) -> None:
        if len(password) < self.MIN_LENGTH:
            raise WeakPasswordError(f"Min {self.MIN_LENGTH} chars")

        categories = sum([
            bool(re.search(r"[a-z]", password)),
            bool(re.search(r"[A-Z]", password)),
            bool(re.search(r"[0-9]", password)),
            bool(re.search(r"[^a-zA-Z0-9]", password)),
        ])
        if categories < self.MIN_CATEGORIES:
            raise WeakPasswordError(f"Min {self.MIN_CATEGORIES} categories required")

        # HIBP k-anonymity check
        sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
        prefix, suffix = sha1[:5], sha1[5:]
        async with httpx.AsyncClient(timeout=2) as client:
            resp = await client.get(f"https://api.pwnedpasswords.com/range/{prefix}")
            if suffix in resp.text:
                raise WeakPasswordError("Password found in known breaches (HaveIBeenPwned)")

        # Top 10000 list locale
        if password.lower() in TOP_10000_PASSWORDS:
            raise WeakPasswordError("Password too common")
```

## DoD

- [ ] Policy validée à login + change_password + register
- [ ] HIBP timeout 2s + fail-open (si API down, on laisse passer + log warning)
- [ ] Liste top 10000 chargée au boot

---

# Story B2.S1.T3 — Session fingerprint device tracking

## Contexte

**Friction** : F311 (cf. `02-core-security.md`) — couplage avec F370 (Sprint 1) sur stepup device_id

### Description

Aujourd'hui, `AccountSession` ne stocke pas de fingerprint device. Conséquence : impossible de détecter "session ouverte depuis appareil suspect" (autre IP, autre user-agent). Fix : `device_fingerprint` calculé depuis `user-agent + ip` (hash), stocké au login.

## Solution

```python
# app/services/session.py
import hashlib

def generate_device_id(user_agent: str, ip_address: str) -> str:
    """Hash stable d'un device fingerprint."""
    raw = f"{user_agent}|{ip_address}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


class SessionService:
    async def create(self, db, account_id, ip, user_agent, ...) -> AccountSession:
        device_id = generate_device_id(user_agent, ip)
        session = AccountSession(
            account_id=account_id,
            device_fingerprint=device_id,
            ip_address=ip,
            user_agent=user_agent,
            ...
        )
        # ...

    async def detect_anomaly(self, db, account_id, current_device_id) -> bool:
        """Détecte si le device_id courant n'a jamais été vu pour cet account."""
        known = await self.repo.list_device_fingerprints(db, account_id, days=90)
        return current_device_id not in known
```

## DoD

- [ ] DDL `account_sessions.device_fingerprint VARCHAR(32)` + migration
- [ ] `generate_device_id` factorisée (réutilisée par WebAuthn stepup F370)
- [ ] Anomaly detection : login depuis nouveau device → audit `auth.login.new_device` + email user

---

# Story B2.S1.T4 — Audit log enrichments

## Contexte

**Pré-requis pour B6.S2** : audit logs doivent contenir actor_type (account/api_key/system), ip, user_agent, fingerprint pour permettre forensics RGPD.

### Description

Aujourd'hui : `AuditLog` minimal (action, actor_id, timestamp). Manque les champs forensics.

## Solution

```python
# Migration ALTER TABLE audit_logs (B6.S2 le complétera avec HMAC chain)
ALTER TABLE audit_logs
    ADD COLUMN actor_type VARCHAR(20) NOT NULL DEFAULT 'system',
    ADD COLUMN actor_account_id BIGINT REFERENCES accounts(id),
    ADD COLUMN actor_api_key_id BIGINT REFERENCES api_keys(id),
    ADD COLUMN ip_address INET,
    ADD COLUMN user_agent VARCHAR(500),
    ADD COLUMN device_fingerprint VARCHAR(32);

ALTER TABLE audit_logs ADD CONSTRAINT ck_audit_actor_type
    CHECK (actor_type IN ('account', 'api_key', 'system', 'cron'));

-- Drop ancienne colonne actor_id générique
ALTER TABLE audit_logs DROP COLUMN actor_id;
```

## DoD

- [ ] Migration appliquée
- [ ] `audit_service.log()` API enrichie (lit `request.state` automatiquement)
- [ ] Backfill pour logs existants : `actor_type='system'` par défaut

---

# Story B2.S1.T5 — Rate-limit endpoints sensibles

## Contexte

**Sévérité** : P0 — anti-brute-force email + phone reset
**Endpoints** : `/auth/login`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/mfa/verify`

### Description

Aujourd'hui : rate-limit global par IP. Manque : par-email (5/min) et par-phone (3/h pour reset SMS si activé).

## Solution

```python
# app/middleware/security.py — RateLimitMiddleware enrichi
LOGIN_LIMITS = {
    "ip": (50, 60),      # 50 req/min par IP (anti-DDoS)
    "email": (5, 60),    # 5 req/min par email (anti-bruteforce ciblé)
}

PASSWORD_RESET_LIMITS = {
    "ip": (10, 60),
    "email": (3, 3600),  # 3 req/h par email (anti-spam reset)
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path == "/api/v1/auth/login":
            # Multi-key check : IP + email
            email = getattr(request.state, "parsed_login_email", None)
            await self._check("login_ip", request.client.host, *LOGIN_LIMITS["ip"])
            if email:
                await self._check("login_email", email, *LOGIN_LIMITS["email"])
        # ... idem pour autres endpoints
        return await call_next(request)
```

## DoD

- [ ] 4 endpoints rate-limités multi-key
- [ ] Tests : 6 tentatives login email X depuis 6 IPs différentes → 6e bloquée (rate-limit email)
- [ ] Métriques `rate_limit_exceeded_total{scope, tenant_bucket}` exposées

---

# Story B2.S1.T6 — F388 backup codes chiffrés KMS

## Contexte

**Friction** : F388 (cf. `12-mfa-webauthn-pin.md`)
**Sévérité** : P1 — backup codes MFA stockés en plain text (ou hashés sans salt déterministe)

### Description

Les backup codes MFA (10 codes single-use générés à l'enrôlement TOTP/WebAuthn) sont stockés actuellement en hash bcrypt sans contexte tenant. Si fuite DB, attaquant peut rejouer offline. Fix : chiffrement KMS avec context AAD = `{tenant_id, account_id}`.

## Solution

```python
# app/models/auth_factor.py (déjà créé B2.S5 — préparation)
class BackupCode(Base, TimestampMixin):
    __tablename__ = "auth_backup_codes"
    id: Mapped[int] = mapped_column(primary_key=True)
    membership_id: Mapped[int] = mapped_column(ForeignKey("tenant_memberships.id"))
    code_hash_encrypted: Mapped[bytes] = mapped_column(  # KMS-encrypted SHA-256
        EncryptedField(context_entity="backup_code", context_field="code_hash"),
        nullable=False,
    )
    used_at: Mapped[Optional[datetime]]
```

Génération : 64 bits entropy (NIST SP 800-63B — vague 4 V4-P2-02) :

```python
import secrets

def generate_backup_codes(count: int = 10) -> list[str]:
    """Génère N codes recovery 64-bit base32 (NIST SP 800-63B compliant)."""
    return [secrets.token_urlsafe(12) for _ in range(count)]  # ~96 bits
```

## DoD

- [ ] Modèle `BackupCode` créé avec `EncryptedField`
- [ ] Génération codes 64 bits min (vague 4 V4-P2-02)
- [ ] Tests : verify backup code utilise correctement AAD context tenant
- [ ] Single-use enforcement (used_at NOT NULL = invalide)

---

# Story B2.S1.T7 — Templates email i18n FR (TR-64 / Vague 2)

## Contexte

**Friction** : TR-64 — `send_password_reset_email` HTML inline anglais hardcoded
**Sévérité** : P1 — Marveline / Splendid / CaroCorp = clients **français** → email reset password en anglais = UX cassée + perception non-pro
**Code source** : `app/services/notification.py` (multiple call-sites avec HTML inline)

### Description

État actuel : chaque email construit son HTML par concaténation de strings dans le code Python, en anglais. Pas de séparation contenu/présentation, pas d'i18n, pas de réutilisation de styles.

Cible :
1. Système de templates Jinja2 dans `app/templates/email/fr/`
2. 4 templates initiaux (Q41=B FR strict — pas d'i18n multi-pays maintenant) :
   - `password_reset.html.j2`
   - `mfa_setup.html.j2`
   - `welcome.html.j2`
   - `email_change_verify.html.j2`
3. Layout commun `_base.html.j2` avec brand_logo + brand_primary_color depuis Tenant
4. Helper `render_email(template_key, context, tenant) -> str`

## Solution

### Structure templates

```
app/templates/email/fr/
├── _base.html.j2           # Layout commun (header logo, footer "Powered by DEVUP")
├── password_reset.html.j2
├── mfa_setup.html.j2
├── welcome.html.j2
├── email_change_verify.html.j2
└── partials/
    ├── _button.html.j2     # CTA stylé
    └── _footer.html.j2     # Mention légale + désabonnement
```

### Template `_base.html.j2`

```jinja2
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>{{ subject }}</title>
    <style>
        body { font-family: -apple-system, sans-serif; max-width: 600px; margin: 0 auto; }
        .header { background: {{ tenant.brand_primary_color or "#1a1a1a" }}; padding: 24px; text-align: center; }
        .logo { max-height: 60px; }
        .content { padding: 32px 24px; color: #333; line-height: 1.6; }
        .button {
            display: inline-block; padding: 12px 24px; background: {{ tenant.brand_primary_color or "#1a1a1a" }};
            color: white; text-decoration: none; border-radius: 4px; font-weight: 600;
        }
        .footer { padding: 24px; text-align: center; color: #888; font-size: 12px; }
    </style>
</head>
<body>
    <div class="header">
        {% if tenant.brand_logo_url %}
        <img class="logo" src="{{ tenant.brand_logo_url }}" alt="{{ tenant.brand_display_name }}">
        {% else %}
        <h1 style="color: white;">{{ tenant.brand_display_name }}</h1>
        {% endif %}
    </div>
    <div class="content">
        {% block content %}{% endblock %}
    </div>
    {% include "email/fr/partials/_footer.html.j2" %}
</body>
</html>
```

### Template `password_reset.html.j2`

```jinja2
{% extends "email/fr/_base.html.j2" %}
{% block content %}
<h2>Réinitialisation de votre mot de passe</h2>
<p>Bonjour {{ user.first_name }},</p>
<p>Vous avez demandé la réinitialisation de votre mot de passe sur <strong>{{ tenant.brand_display_name }}</strong>.</p>
<p>Cliquez sur le bouton ci-dessous pour choisir un nouveau mot de passe :</p>
<p style="text-align: center; margin: 32px 0;">
    <a href="{{ reset_url }}" class="button">Réinitialiser mon mot de passe</a>
</p>
<p style="color: #888; font-size: 13px;">
    Ce lien est valide pendant {{ expiry_minutes }} minutes.<br>
    Si vous n'avez pas fait cette demande, ignorez cet email — votre mot de passe restera inchangé.
</p>
<p style="color: #888; font-size: 13px;">
    Pour toute question, contactez-nous à <a href="mailto:{{ tenant.brand_email_from }}">{{ tenant.brand_email_from }}</a>.
</p>
{% endblock %}
```

### Helper `render_email`

```python
# app/services/email/templates.py (NEW)
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path

_jinja_env = Environment(
    loader=FileSystemLoader(Path("app/templates")),
    autoescape=select_autoescape(["html", "xml", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_email(
    template_key: str,
    context: dict,
    tenant: Tenant,
    locale: str = "fr",
) -> tuple[str, str]:
    """Render le template HTML + extrait le subject depuis le frontmatter.
    
    Q41=B : pour l'instant locale='fr' uniquement.
    """
    template = _jinja_env.get_template(f"email/{locale}/{template_key}.html.j2")
    enriched_context = {
        **context,
        "tenant": tenant,
        "subject": _SUBJECTS.get(template_key, "Notification"),
    }
    html = template.render(**enriched_context)
    return html, enriched_context["subject"]


_SUBJECTS = {
    "password_reset": "Réinitialisation de votre mot de passe",
    "mfa_setup": "Configuration de l'authentification à deux facteurs",
    "welcome": "Bienvenue sur {{ tenant.brand_display_name }}",
    "email_change_verify": "Vérification de votre nouvelle adresse email",
}
```

### Refonte `forgot_password` endpoint

```python
# app/api/v1/endpoints/auth.py
@router.post("/auth/forgot-password")
async def forgot_password(payload: ForgotPasswordPayload, request: Request):
    account = await db.scalar(select(Account).where(Account.email == payload.email))
    if account is None:
        return {"status": "ok"}  # Toujours 200 (anti-enumeration)
    
    token = generate_reset_token()
    await db.execute(insert(PasswordResetToken).values(
        account_id=account.id, token=hash_token(token),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    ))
    
    tenant = await db.get(Tenant, account.tenant_id)
    reset_url = f"{tenant.frontend_url}/reset-password?token={token}"
    
    html, subject = render_email(
        template_key="password_reset",
        context={"user": account, "reset_url": reset_url, "expiry_minutes": 15},
        tenant=tenant,
    )
    
    # Send via EmailGateway + log notification_log (B6.S1.T8)
    await email_gateway.send(
        to=account.email,
        subject=subject,
        body_html=html,
        tenant_id=tenant.id,
        template_key="password_reset",
    )
    return {"status": "ok"}
```

### Tests

```python
async def test_password_reset_email_in_french(monkeypatch, gateway_capture, tenant_marveline, account):
    """TR-64 — email reset password en français."""
    await client.post("/api/v1/auth/forgot-password", json={"email": account.email})
    
    sent = gateway_capture.last_send
    assert "Réinitialisation de votre mot de passe" in sent.subject
    assert "Bonjour" in sent.body_html
    assert "Réinitialiser mon mot de passe" in sent.body_html
    assert "Cliquez sur le bouton" in sent.body_html
    # No English left
    assert "Click here" not in sent.body_html
    assert "Reset your password" not in sent.body_html

async def test_email_uses_tenant_branding(gateway_capture, tenant_splendid, account_splendid):
    tenant_splendid.brand_primary_color = "#A52A2A"
    tenant_splendid.brand_logo_url = "https://splendid-events.fr/logo.png"
    await client.post("/api/v1/auth/forgot-password", json={"email": account_splendid.email})
    
    body = gateway_capture.last_send.body_html
    assert "#A52A2A" in body
    assert "splendid-events.fr/logo.png" in body
    assert "Splendid" in body  # brand_display_name
```

## DoD

- [ ] 4 templates Jinja2 livrés (`password_reset`, `mfa_setup`, `welcome`, `email_change_verify`)
- [ ] Layout `_base.html.j2` + footer commun avec brand_*
- [ ] Helper `render_email(template_key, context, tenant)` opérationnel
- [ ] Refonte `forgot_password` endpoint utilise `render_email`
- [ ] Test FR : aucun mot anglais dans subject/body
- [ ] Test branding : brand_logo_url + brand_primary_color appliqués
- [ ] Cohérence Q41=B : `locale='fr'` hardcoded (pas d'i18n multi-pays maintenant)

---

## Critères de succès Sprint B2.S1

- [ ] Token refresh rotation active (F306)
- [ ] Password policy renforcée (F310 + HIBP check)
- [ ] Session fingerprint stocké (F311 — réutilisé par F370 stepup)
- [ ] Audit logs enrichis (pré-requis B6.S2)
- [ ] Rate-limit multi-key sur 4 endpoints sensibles
- [ ] Backup codes chiffrés KMS (F388)
- [ ] **TR-64 / Vague 2** : templates email Jinja2 FR + branding tenant
- [ ] CI 100% verte

---

**Fin du document — 12-sprint-B2.S1.md**

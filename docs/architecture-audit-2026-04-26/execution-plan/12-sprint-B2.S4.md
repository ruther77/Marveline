# Sprint B2.S4 — MFA enforcement + sessions cascade

> **STATUT** : ⏳ À démarrer après B2.S3
> **DURÉE MAX** : 2 semaines
> **OWNER** : Dev2 — collaboration Lead pour validation sécurité
> **BLOQUE** : aucun (mais réduit la dette sécurité avant prod)
> **DÉPEND DE** : B2.S3 (Scope v3 + RBAC), B1.S3 (KMS pour TOTP secret)
> **OBJECTIF** : Activer MFA enforcement réel (lecture `auth_roles.mfa_required`), refondre OAuth flows pour passer par MFA gate (F404 follow-up Sprint 1), cascade sessions revocation post-suspend (F259), optimiser session.touch() (F303).

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B2.S4.T1** | F371 lire `auth_roles.mfa_required` au login + force challenge | P0 | 1 j | aucun |
| **B2.S4.T2** | F372 audit MFA skip si 0 device + alert email | P0 | 0.5 j | aucun |
| **B2.S4.T3** | F368 RP_ID per-tenant — refacto WebAuthnService (Sprint 1 follow-up) | P0 | 1 j | aucun |
| **B2.S4.T4** | F404/F405/F406 OAuth dual-flow consolidation + email_verified guard | P0 | 1.5 j | aucun |
| **B2.S4.T5** | F259 cascade sessions revoke post-membership.suspend | P0 | 1 j | aucun |
| **B2.S4.T6** | F303 session.touch() Redis flush batch optimisation | P1 | 0.75 j | aucun |
| **B2.S4.T7** | F380 `valid_for_seconds` bind dynamique au `STEPUP_TTL` | P1 | 0.25 j | aucun |
| **B2.S4.T8** | **Q11=A** F411 — `OAuthRelinkBlocked` exception si `provider_subject` change pour account déjà lié | P0 | 0.5 j | aucun |

**Total effort** : 6.5 jours-homme.

---

# Story B2.S4.T1 — F371 `auth_roles.mfa_required` lecture au login

## Contexte

**Friction** : F371 (vague 4 V4-P0-05)
**Sévérité** : **P0** — colonne fantôme : politique MFA per-role définie en DB mais ignorée
**Code source** : `app/services/auth_v2.py:89-120`

### Description

```python
# auth_v2.py (état actuel)
async def authenticate(self, email, password):
    account = await self._account_svc.verify_credentials(email, password)
    devices = await self._mfa_svc.get_active_devices(account.id)
    if not devices:
        return tokens  # ← MFA non requise (F372 skip silencieux)
    return mfa_required(account.id)
```

`auth_roles.mfa_required` BOOLEAN n'est jamais consulté → impossible d'avoir un rôle qui force MFA même si user n'a pas enrôlé (= "tu DOIS enrôler MFA pour ce rôle").

## Solution

```python
# app/services/auth_v2.py (refacto)
async def authenticate(self, email: str, password: str, db: AsyncSession):
    account = await self._account_svc.verify_credentials(db, email, password)
    if not account:
        return None

    # Récupérer le rôle actif de l'account sur ce tenant
    membership = await self._membership_svc.get_active(db, account.id, request.state.tenant_id)
    if not membership:
        raise NoMembershipError("Account has no active membership for this tenant")

    role = await db.execute(select(AuthRole).filter_by(name=membership.role))
    role = role.scalar_one()

    # F371 fix : check politique MFA du rôle
    devices = await self._mfa_svc.get_active_factors(db, membership.id)

    if role.mfa_required and not devices:
        # Utilisateur DOIT enrôler MFA avant d'accéder
        return MFASetupRequired(
            account_id=account.id,
            role=role.name,
            setup_url="/api/v1/auth/mfa/enroll",
        )

    if devices:
        # User a MFA enrôlée → challenge obligatoire
        pending_token = await self._mfa_svc.create_pending(db, account.id)
        return MFAChallengeRequired(pending_token=pending_token)

    # F372 fix : audit explicite si MFA skipped (politique flexible mais traçable)
    await audit_service.log(
        db, "auth.login.mfa_skipped",
        account_id=account.id, metadata={"role": role.name},
    )

    return tokens  # MFA non requise + non enrôlée → tokens directs
```

## DoD

- [ ] `auth_roles.mfa_required` lu à chaque login
- [ ] Si `mfa_required=True` + `devices=[]` → réponse `MFASetupRequired`
- [ ] Si `mfa_required=False` + skip MFA → audit `auth.login.mfa_skipped`
- [ ] Test E2E : créer rôle `admin_finance` avec `mfa_required=True` → user sans MFA bloqué

---

# Story B2.S4.T2 — F372 audit MFA skip + alert

## Contexte

**Friction** : F372 (vague 4 V4-P0-06)
**Sévérité** : P0 — chain attack possible : DELETE /mfa → relogin sans MFA → tokens accès complet sans alerte

### Description

Aujourd'hui : si user supprime tous ses MFA factors, login suivant ne déclenche aucun signal. Risque attack chain.

## Solution

```python
# app/services/mfa.py
class MFAService:
    async def deactivate_factor(self, db, account_id, factor_id):
        """Désactivation d'un MFA factor — audit + alert si dernier factor."""
        factor = await db.get(AuthFactor, factor_id)
        factor.is_active = False
        await db.flush()

        remaining = await self._count_active(db, account_id)
        if remaining == 0:
            # F372 alert : utilisateur sans aucun MFA (état dégradé sécurité)
            await audit_service.log(
                db, "auth.mfa.last_factor_removed",
                account_id=account_id,
                metadata={"factor_id": factor_id, "factor_type": factor.type},
            )
            # Email warning à l'utilisateur (notification fail-open si email down)
            try:
                await email_gateway.send(
                    template="mfa_last_factor_removed",
                    to=account.email,
                    data={"removed_at": datetime.now(UTC), "device_label": factor.label},
                )
            except EmailError:
                logger.warning("Failed to send MFA alert email — F372 audit kept")

        return remaining
```

## DoD

- [ ] Audit `auth.mfa.last_factor_removed` émis quand passage à 0 factor actif
- [ ] Email alert envoyé (fail-open si SMTP down)
- [ ] Test : DELETE last MFA → audit + email présents

---

# Story B2.S4.T3 — F368 RP_ID per-tenant (refacto WebAuthnService)

## Contexte

**Friction** : F368 (vague 4 V4-P0-03)
**Sévérité** : P0 — Sprint 1 T11 a fait le hotfix DDL + endpoints. Cette story consolide en refacto class.

### Description

Sprint 1 T11 a appliqué :
- DDL `tenants.rp_id` + `tenants.frontend_url`
- Backfill tenants existants
- Hotfix endpoints `/auth/webauthn/*` lisant `request.state.tenant.rp_id`

Cette story consolide :
- `WebAuthnService` instancié avec `tenant` (pas constantes globales)
- Migration tous endpoints WebAuthn (4 endpoints) vers nouvelle API
- Tests E2E démo Splendid post-Sprint 1

## Solution

Cf. `56-sequence-diagrams.md §12` WebAuthn enregistrement avec RP_ID per-tenant — diagramme cible déjà rédigé vague 6.

```python
# app/services/webauthn.py (consolidation post-Sprint 1)
class WebAuthnService:
    def __init__(self, db: AsyncSession, tenant: Tenant):
        self.db = db
        self.tenant = tenant
        self.rp_id = tenant.rp_id or settings.JWT_ISSUER.replace("www.", "")
        self.rp_name = tenant.brand_display_name or settings.APP_NAME
        self.expected_origin = tenant.frontend_url or settings.FRONTEND_URL

    async def register_options(self, account: Account):
        return {
            "rp": {"id": self.rp_id, "name": self.rp_name},
            "user": {"id": str(account.id), "name": account.email, "displayName": account.email},
            "challenge": secrets.token_urlsafe(32),
            "pubKeyCredParams": [{"type": "public-key", "alg": -7}, {"type": "public-key", "alg": -257}],
            "timeout": 60000,
            "attestation": "none",
        }

    async def register_verify(self, account: Account, credential):
        return verify_registration_response(
            credential=credential,
            expected_rp_id=self.rp_id,
            expected_origin=self.expected_origin,
        )
```

## DoD

- [ ] `WebAuthnService(db, tenant)` instancié partout (4 endpoints)
- [ ] CI invariant `check_webauthn_uses_tenant_rp_id.py` (NEW) — refuse merge si RP_ID hardcodé
- [ ] Test E2E démo Splendid validée
- [ ] R24 marqué résolu

---

# Story B2.S4.T4 — F404/F405/F406 OAuth flows consolidation

## Contexte

**Frictions** :
- F404 OAuth `mfa_verified=False` hardcodé (Sprint 1 T10 patch tactique — cette story consolide)
- F405 auto-link sans `email_verified` guard → account takeover
- F406 dual-flow (`endpoints/oauth.py` legacy + `services/oauth_v2.py`) → divergence

**Diagramme** : `56-sequence-diagrams.md §11` OAuth callback avec MFA gate (vague 6)

### Description

Sprint 1 T10 a posé un patch dans `_issue_oauth_tokens` (vérif MFA enrôlée → `MFARequiredResponse`). Cette story consolide :

1. **F405** : auto-link uniquement si `id_token.email_verified=True`
2. **F406** : drop `endpoints/oauth.py` (legacy), garder `services/oauth_v2.py:OAuthV2Service`
3. **F404** : refacto consolidé avec MFA gate dans le service v2

## Solution

```python
# app/services/oauth_v2.py (consolidation finale)
class OAuthV2Service:
    async def handle_callback(
        self,
        db: AsyncSession,
        provider: str,
        id_token: dict,
    ) -> Union[TokenOut, MFAChallengeRequired]:
        """F404 + F405 + F406 fix : flow OAuth unifié avec MFA gate.

        F405 : auto-link uniquement si id_token.email_verified == True
        F404 : MFA gate avant émission tokens
        F406 : seul flow OAuth (endpoints/oauth.py legacy supprimé)
        """
        email = id_token["email"]
        sub = id_token["sub"]
        email_verified = id_token.get("email_verified", False)

        # 1. Find or auto-link
        account = await self._find_or_link(db, provider, sub, email, email_verified)

        # 2. F404 fix : MFA gate
        if await self._mfa_svc.is_enrolled(db, account.id):
            pending = await self._mfa_svc.create_pending(db, account.id)
            await audit_service.log(db, "oauth.callback.mfa_required",
                                     account_id=account.id, metadata={"provider": provider})
            return MFAChallengeRequired(pending_token=pending)

        # 3. Pas de MFA → tokens
        return await self._issue_tokens(db, account, provider)

    async def _find_or_link(self, db, provider, sub, email, email_verified) -> Account:
        # Try OAuth identity lookup
        identity = await db.execute(
            select(AccountOAuthIdentity).filter_by(provider=provider, sub=sub)
        )
        identity = identity.scalar_one_or_none()
        if identity:
            return await db.get(Account, identity.account_id)

        # F405 fix : auto-link uniquement si email_verified
        if not email_verified:
            raise OAuthEmailNotVerified(
                "Cannot auto-link account : email not verified by OAuth provider"
            )

        # Auto-link safe
        existing = await db.execute(select(Account).filter_by(email=email))
        existing = existing.scalar_one_or_none()
        if existing:
            await db.add(AccountOAuthIdentity(
                account_id=existing.id, provider=provider, sub=sub
            ))
            return existing

        # New account OAuth-only (F296 timing-safe traité dans Sprint 1 T9)
        account = Account(
            email=email,
            hashed_password=None,  # OAuth-only
            is_active=True,
        )
        db.add(account)
        await db.flush()
        db.add(AccountOAuthIdentity(account_id=account.id, provider=provider, sub=sub))
        return account
```

## DoD

- [ ] `endpoints/oauth.py` legacy supprimé (drop fichier)
- [ ] `OAuthV2Service.handle_callback()` seul flow restant
- [ ] F405 : auto-link refusé si `email_verified=False`
- [ ] F404 : MFA gate appelé systématiquement
- [ ] CI invariant `check_no_mfa_bypass_oauth.py` (54 §20) vert
- [ ] 5 tests E2E (auto-link verified, auto-link unverified rejected, MFA gate Google, MFA gate MS, no MFA → tokens directs)

---

# Story B2.S4.T5 — F259 cascade sessions revoke post-membership.suspend

## Contexte

**Friction** : F259 (vague 3 V3-P2-04)
**Sévérité** : P0 — fenêtre 15 min entre suspend membership et invalidation sessions

### Description

`MembershipService.suspend()` aujourd'hui :
- Update `tenant_memberships.status = 'suspended'`
- ❌ Pas de cascade sur `account_sessions`
- ❌ Pas de DEL Redis cache JWT

Conséquence : user suspendu reste connecté jusqu'à expiration token (15 min access, 7j refresh).

## Solution

```python
# app/services/membership.py
class MembershipService:
    async def suspend(self, db, membership_id, reason: str):
        async with db.begin_nested():
            membership = await db.get(TenantMembership, membership_id)
            membership.status = "suspended"
            membership.suspended_at = datetime.now(UTC)
            membership.suspended_reason = reason

            # F259 fix : cascade sessions revoke
            await self._revoke_sessions(db, membership.account_id, membership.tenant_id)

            await audit_service.log(
                db, "membership.suspend",
                account_id=membership.account_id,
                metadata={"membership_id": membership_id, "reason": reason},
            )

    async def _revoke_sessions(self, db, account_id, tenant_id):
        """Révoque toutes sessions actives de l'account sur ce tenant."""
        # 1. DB : marquer sessions inactives
        sessions = await db.execute(
            select(AccountSession).filter_by(
                account_id=account_id, tenant_id=tenant_id, is_active=True
            )
        )
        sessions = sessions.scalars().all()
        for s in sessions:
            s.is_active = False
            s.revoked_at = datetime.now(UTC)
            s.revoked_reason = "membership_suspended"

        # 2. Redis : DEL session cache
        for s in sessions:
            await redis_sec.delete(f"session:{s.jti}")

        await db.flush()
        return len(sessions)
```

## DoD

- [ ] `MembershipService.suspend()` cascade sessions DB + Redis
- [ ] CI invariant test INV-10 (53 §8.10) vert : suspend → sessions inactives + cache vidé
- [ ] Test E2E : user logged-in, suspend membership, prochain appel API → 401

---

# Story B2.S4.T6 — F303 session.touch() Redis flush batch

## Contexte

**Friction** : F303 (vague 5 V5-P2-03)
**Sévérité** : P1 — `touch()` fait UPDATE DB à chaque requête authentifiée → goulot perf sous charge

### Description

Sous charge (N requêtes authentifiées/sec), N UPDATE `account_sessions.last_active_at = NOW()` par seconde → contention DB.

## Solution

```python
# app/services/session.py
class SessionService:
    async def touch(self, db, jti: str):
        """F303 fix : write Redis (TTL court), flush DB batch via Celery cron."""
        # Hot path : write Redis seulement (~0.5ms)
        await redis_sec.set(f"session:touch:{jti}", str(time.time()), ex=300)


# app/tasks/sessions.py
@celery_app.task(name="app.tasks.sessions.flush_activity", queue="default")
async def flush_session_activity():
    """Worker cron 60s : flush Redis touched sessions vers DB.

    Réduit la pression DB de N writes/sec à 1 batch/min.
    """
    async with AsyncSessionLocal() as db:
        # Scan Redis pour sessions touchées
        keys = await redis_sec.keys("session:touch:*")
        if not keys:
            return

        updates = []
        for key in keys:
            jti = key.split(":")[-1]
            ts = float(await redis_sec.get(key))
            updates.append({"jti": jti, "last_active_at": datetime.fromtimestamp(ts, UTC)})

        # Batch UPDATE
        await db.execute(
            update(AccountSession).where(
                AccountSession.jti.in_([u["jti"] for u in updates])
            ),
            updates,
        )
        await db.commit()

        # Cleanup Redis
        await redis_sec.delete(*keys)
```

```python
# Celery beat
beat_schedule = {
    "flush-session-activity-1min": {
        "task": "app.tasks.sessions.flush_activity",
        "schedule": 60.0,  # toutes les 60s
    },
}
```

## DoD

- [ ] `touch()` écrit Redis uniquement
- [ ] Worker `flush_session_activity` cron 60s
- [ ] Bench : avant 1500 req/s touchait DB, après 1500 req/s Redis only → DB UPDATE batch toutes les 60s

---

# Story B2.S4.T7 — F380 `valid_for_seconds` bind dynamique

## Contexte

**Friction** : F380 (vague 4 V4-P1-01) — `StepUpVerifyResponse.valid_for_seconds=900` hardcodé vs `STEPUP_TTL=300`

### Description

```python
# app/schemas/mfa.py:174 (état actuel)
class StepUpVerifyResponse(BaseModel):
    valid_for_seconds: int = Field(default=900)  # ← incohérent avec MFAConfig.STEPUP_TTL=300
```

## Solution

```python
# app/schemas/mfa.py (corrigé)
from app.constants.security import MFAConfig

class StepUpVerifyResponse(BaseSchema):
    valid_for_seconds: int = Field(default=MFAConfig.STEPUP_TTL)
```

CI invariant `check_schema_constants_coherence.py` (mentionné vague 4) — créé en B6.S6.

## DoD

- [ ] Bind dynamique `MFAConfig.STEPUP_TTL`
- [ ] Test : response.valid_for_seconds == 300

---

# Story B2.S4.T8 — F411 `OAuthRelinkBlocked` (Q11=A)

## Contexte

**Friction** : F411 (re-link silent OAuth — vecteur account takeover)
**Décision** : **Q11=A** — Refuser re-link automatique, exiger unlink explicite si `provider_subject` change pour un account déjà lié (anti-account-takeover)
**Sévérité** : **P0 SEC** — vecteur account takeover via OAuth provider compromise (attaquant prend le compte chez Google/MS, retente OAuth → re-link silent → take over compte DEVUP)
**Code source** : `app/services/oauth_v2.py:link_or_create_account`

### Description

Aujourd'hui : si `AccountOAuthIdentity{provider='google', email='user@example.com'}` existe avec `provider_subject='abc-123'`, et qu'un nouveau callback OAuth arrive avec même email mais `provider_subject='xyz-789'` → re-link silent.

**Scénario attaque** :
1. Attaquant compromet compte Google `victime@example.com` (phishing, fuite mdp)
2. Attaquant initie OAuth login DEVUP → callback avec `provider_subject` différent (anciennes données invalidées chez Google)
3. Code legacy : re-link automatique → attaquant prend le compte DEVUP

Cible Q11=A : raise `OAuthRelinkBlocked` au lieu de re-lier silencieusement.

## Solution

```python
# app/services/oauth_v2.py
from app.core.exceptions import OAuthRelinkBlocked

class OAuthV2Service:
    async def link_or_create_account(
        self,
        provider: str,
        provider_subject: str,
        email: str,
        email_verified: bool,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> Account:
        # 1. Cas existant : identité OAuth déjà liée avec provider_subject identique
        existing_identity = await self.db.scalar(
            select(AccountOAuthIdentity).where(
                AccountOAuthIdentity.provider == provider,
                AccountOAuthIdentity.provider_subject == provider_subject,
            )
        )
        if existing_identity:
            return existing_identity.account  # login OK

        # 2. Q11=A : provider_subject DIFFÉRENT pour cette identité OAuth ?
        # Vérifier s'il existe une AccountOAuthIdentity même provider+email mais subject différent
        conflicting = await self.db.scalar(
            select(AccountOAuthIdentity).join(Account).where(
                AccountOAuthIdentity.provider == provider,
                Account.email == email,
                AccountOAuthIdentity.provider_subject != provider_subject,
            )
        )
        if conflicting:
            # Audit pour traçabilité forensic
            await audit_service.log(
                action="OAUTH_RELINK_BLOCKED",
                entity_type="Account",
                entity_id=str(conflicting.account_id),
                description=(
                    f"OAuth re-link refused: provider={provider}, email={email}, "
                    f"old_subject={conflicting.provider_subject}, new_subject={provider_subject}"
                ),
                account_id=conflicting.account_id,
                tenant_id=conflicting.account.tenant_id,
            )
            raise OAuthRelinkBlocked(
                f"OAuth identity for {provider}/{email} already linked with different subject. "
                "Contact admin to unlink the existing identity before re-linking. "
                "If you didn't initiate this action, your account may be at risk."
            )

        # 3. Cas normal : nouvelle account ou link première fois
        # ... (logique existante)


# app/core/exceptions.py
class OAuthRelinkBlocked(SecurityError):
    """Q11=A — refus re-link OAuth automatique (anti-account-takeover)."""
    status_code = 409  # Conflict — conscient + explicite, pas 500
```

### Endpoint behavior

```python
# app/api/v1/endpoints/oauth.py (v2)
@router.get("/auth/v2/oauth/{provider}/callback")
async def oauth_callback(provider: str, code: str, ...):
    try:
        account = await oauth_service.link_or_create_account(...)
    except OAuthRelinkBlocked as e:
        return JSONResponse(
            status_code=409,
            content={
                "error": "OAUTH_RELINK_BLOCKED",
                "message": str(e),
                "action": "Contact your admin to unlink the existing OAuth identity first.",
            },
        )
    # ... issue tokens
```

### Endpoint admin unlink explicite

```python
# app/api/v1/endpoints/admin/oauth.py (NEW)
@router.delete(
    "/admin/accounts/{account_id}/oauth-identities/{provider}",
    dependencies=[Depends(require_scope(Scope.ADMIN_OAUTH_UNLINK))],
)
async def admin_unlink_oauth(account_id: UUID, provider: str, user: User = Depends(...)):
    """Q11=A — admin unlink explicite avant re-link possible."""
    identity = await db.scalar(
        select(AccountOAuthIdentity).where(
            AccountOAuthIdentity.account_id == account_id,
            AccountOAuthIdentity.provider == provider,
        )
    )
    if identity is None:
        raise NotFound(f"OAuth identity {provider} not found for account")
    await db.delete(identity)
    await audit_service.log(
        action="OAUTH_IDENTITY_UNLINKED",
        entity_type="Account",
        entity_id=str(account_id),
        description=f"Admin {user.id} unlinked {provider} for account {account_id}",
        account_id=user.id,
        tenant_id=identity.account.tenant_id,
    )
    await db.commit()
```

### Tests

```python
async def test_oauth_relink_blocked_when_subject_changes(db, account_with_google_link):
    """Q11=A — provider_subject change → OAuthRelinkBlocked."""
    # account_with_google_link : provider_subject='abc-123'
    with pytest.raises(OAuthRelinkBlocked):
        await oauth_service.link_or_create_account(
            provider="google",
            provider_subject="xyz-789",  # DIFFERENT
            email=account_with_google_link.email,
            email_verified=True,
        )
    # Audit log créé
    log = await db.scalar(
        select(AuditLog).where(AuditLog.action == "OAUTH_RELINK_BLOCKED")
    )
    assert log is not None

async def test_oauth_relink_works_after_admin_unlink(client_admin, account_with_google_link):
    # Admin unlink
    response = await client_admin.delete(
        f"/api/v1/admin/accounts/{account_with_google_link.id}/oauth-identities/google"
    )
    assert response.status_code == 200
    # Maintenant re-link OK
    new_account = await oauth_service.link_or_create_account(
        provider="google", provider_subject="xyz-789",
        email=account_with_google_link.email, email_verified=True,
    )
    assert new_account.id == account_with_google_link.id

async def test_oauth_login_normal_same_subject_still_works(db, account_with_google_link):
    """Re-login OAuth avec même provider_subject → login OK (pas re-link)."""
    account = await oauth_service.link_or_create_account(
        provider="google",
        provider_subject=account_with_google_link.oauth_identities[0].provider_subject,
        email=account_with_google_link.email,
        email_verified=True,
    )
    assert account.id == account_with_google_link.id
```

## DoD

- [ ] **Q11=A livré** : `OAuthRelinkBlocked` exception (status 409)
- [ ] `link_or_create_account` détecte conflict `provider_subject` ≠ + raise
- [ ] Audit `OAUTH_RELINK_BLOCKED` créé pour forensic
- [ ] Endpoint admin `DELETE /admin/accounts/{id}/oauth-identities/{provider}` + scope `admin:oauth_unlink`
- [ ] Test : provider_subject change → blocked
- [ ] Test : admin unlink → re-link OK ensuite
- [ ] Test : same provider_subject → login normal préservé

---

## Critères de succès Sprint B2.S4

- [ ] **F371** politique MFA per-role appliquée (rôle `admin_finance` force MFA)
- [ ] **F372** audit MFA skip + alert email
- [ ] **F368** RP_ID per-tenant consolidé (R24 résolu post-Sprint 1)
- [ ] **F404/F405/F406** OAuth flows unifiés (CI invariant 54 §20 vert)
- [ ] **F259** sessions cascade revoke (INV-10 vert)
- [ ] **F303** session.touch() Redis batch (perf bench ok)
- [ ] **F380** valid_for_seconds cohérent
- [ ] **F411 / Q11=A** OAuthRelinkBlocked (anti-account-takeover) + admin unlink endpoint

---

**Fin du document — 12-sprint-B2.S4.md**

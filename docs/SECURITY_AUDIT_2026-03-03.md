# Audit Sécurité — Socle Auth CaroCorp
**Date** : 2026-03-03
**Méthode** : lecture exhaustive fichier par fichier, comparaison croisée
**Sources lues** : `deps.py`, `middleware/security.py`, `services/auth.py`, `core/config.py`, `constants/http.py`

---

## SECTION 1 — `get_current_user` vs `get_current_user_async` : divergences

### INC-01 — Vérification device révoqué absente dans la version sync
**Sévérité : P1**
**Fichier** : `app/core/deps.py:88-177`

La version **async** (L428-434) vérifie si le `device_id` est révoqué via `_handle_revoked_device()` :
```python
device_id = payload.get("did", "")
if device_id and _handle_revoked_device(device_id) is not None:
    raise HTTPException(403, DEVICE_REVOKED)
```
La version **sync** (L88-177) ne le fait **pas**.

**Impact** : Un appareil révoqué peut continuer à appeler les endpoints synchrones (si un endpoint utilise `get_current_user` sync plutôt qu'async). En pratique, les endpoints FastAPI modernes utilisent quasi tous la version async, mais le vecteur existe.

**Correction** : Ajouter le check device dans la version sync, même logique.

---

### INC-02 — Docstring de `get_current_user_async` non mise à jour
**Sévérité : P3**
**Fichier** : `app/core/deps.py:375`

La docstring dit :
```
Raises:
    HTTPException 403: Si compte inactif
```
Mais après notre ajout de `password_change_required`, elle devrait dire :
```
Raises:
    HTTPException 403: Si compte inactif ou password_change_required
```
La version sync (L97) a bien la docstring mise à jour.

---

### INC-03 — Query DB différente entre les deux versions
**Sévérité : P2**
**Fichier** : `app/core/deps.py:142` vs `L415`

Version sync :
```python
user = db.query(User).filter(User.id == user_id).first()
```
Version async :
```python
result = await db.execute(select(User).where(User.id == user_id))
user = result.scalar_one_or_none()
```

La version sync n'utilise pas `select()` — elle utilise l'API legacy SQLAlchemy 1.x (`db.query()`). Ce n'est pas seulement un style : **la version sync ne filtre pas sur `tenant_id`**, contrairement à la version async. Un user_id partagé entre tenants (collision théorique d'id séquentiel) pourrait retourner le mauvais user.

En pratique les IDs sont globaux et uniques, mais c'est une divergence de pattern.

---

## SECTION 2 — Middleware CSRF : incohérences avec `PASSWORD_CHANGE_ALLOWED`

### INC-04 — `CHANGE_PASSWORD` dans `PASSWORD_CHANGE_ALLOWED` mais **pas** dans la whitelist CSRF
**Sévérité : P1**
**Fichiers** : `app/middleware/security.py:37-47` vs `app/constants/http.py:75-79`

La whitelist CSRF du middleware exempte :
```python
{LOGIN, REFRESH, LOGOUT, MFA_VERIFY}
```

`CHANGE_PASSWORD = "/api/v1/auth/change-password"` n'est **pas** dans cette liste.

`PASSWORD_CHANGE_ALLOWED` (dans `deps.py`) autorise `/auth/change-password` pour les users avec `password_change_required=True`. Mais un tel user, qui n'avait jamais établi de session (ex: token créé avant la colonne), n'a **pas de CSRF token valide**.

**Scénario concret** :
1. Admin force `password_change_required = True` hors session (script direct DB)
2. User se reconnecte → login réussi → session + CSRF token émis (OK)
3. User appelle `POST /auth/change-password` avec CSRF → passe (OK)

Scénario sans session :
1. User avec token valide (AT non expiré) mais dont la session Redis a expiré (>7j)
2. `csrf:{sid}` n'existe plus dans Redis (TTL expiré)
3. CSRF validation échoue → 403 `CSRF token invalide` → user bloqué, **ne peut pas changer son MDP**

**Correction** : Ajouter `AuthEndpoints.CHANGE_PASSWORD` dans la whitelist CSRF du middleware si `password_change_required` est détecté, OU documenter que l'invariant "session Redis valide requise" est une contrainte assumée.

---

### INC-05 — `CSRF_SECRET` dans `config.py` non utilisé
**Sévérité : P2**
**Fichier** : `app/core/config.py:64`

```python
CSRF_SECRET: str = "dev_csrf_secret_CHANGER_EN_PROD_min32chars"
```

Cette variable est dans la liste de validation prod (`validate_production_secrets`), mais elle n'est **pas utilisée dans le code**. La CSRF validation utilise `redis_sec.validate_csrf_token()` (timing-safe Redis), pas un secret HMAC local.

**Impact** : Deux effets :
1. Fausse sécurité — l'admin croit avoir à configurer ce secret alors qu'il ne sert à rien
2. Si quelqu'un essaie de construire un système de CSRF via HMAC(CSRF_SECRET, ...), il sera déçu

**Vérifier** : Est-ce un vestige d'une ancienne implémentation CSRF HMAC ? Si oui, supprimer.

---

## SECTION 3 — Login flow : états non gérés

### INC-06 — Commit audit log AVANT création session (atomicité brisée)
**Sévérité : P2**
**Fichier** : `app/services/auth.py:213-234`

```python
# ── Pas de MFA — émettre tokens directement ──
await audit_service.log_login(...)
await self.db.commit()                    # ← COMMIT #1

session_id = await session_service.create_session(...)
await self.db.commit()                    # ← COMMIT #2

access_token, refresh_token, ... = token_service.issue_tokens(...)
```

Si `create_session()` lève une exception après `COMMIT #1` (ex: DB down, contrainte), le login est loggé comme succès en audit **mais aucun token n'est émis**. L'utilisateur voit une erreur 500, mais l'audit dit "LOGIN_SUCCESS".

**Correction** : Regrouper les deux commits en un seul, ou utiliser des savepoints.

---

### INC-07 — HIBP check non bloquant, mais `password_change_required` n'est pas communiqué au client au login
**Sévérité : P2**
**Fichier** : `app/services/auth.py:194-197`

```python
if is_password_compromised(password):
    user.password_change_required = True
    await self.db.flush()
```

Le login réussit normalement (tokens émis), mais `password_change_required = True` vient d'être activé. Le frontend ne sait pas qu'il doit rediriger vers le changement de mot de passe.

La réponse de login retourne `(access_token, refresh_token, expires_in)` — pas de champ `password_change_required`.

**Impact** : Le frontend redirige vers `/dashboard`. L'utilisateur navigue normalement jusqu'à ce qu'un endpoint le bloque avec `403 PASSWORD_CHANGE_REQUIRED`. Expérience utilisateur dégradée (redirect après coup, pas au login).

**Correction** : Ajouter `password_change_required: bool` dans `LoginResponse` et le retourner si la valeur est True.

---

### INC-08 — `change_password()` ne remet pas `password_change_required = False`
**Sévérité : P1**
**Fichier** : `app/services/auth.py:455-458`

```python
user.hashed_password = get_password_hash(new_password)
await self.db.flush()
redis_sec.reset_brute_force(brute_key)
return True
```

Après un changement de mot de passe réussi (déclenché par `password_change_required = True`), **le flag n'est pas remis à False**. L'utilisateur continuera à être bloqué sur tous les endpoints métier même après avoir changé son mot de passe.

**Correction** : `user.password_change_required = False` avant `flush()`.

---

## SECTION 4 — Refresh token : resilience Redis

### INC-09 — `refresh_access_token()` ne vérifie pas `password_change_required`
**Sévérité : P2**
**Fichier** : `app/services/auth.py:266-333`

Le refresh vérifie `user.is_active` (L307-311) mais **pas** `user.password_change_required`.

**Impact** : Un user avec `password_change_required = True` dont l'access token expire peut le renouveler indéfiniment via refresh sans jamais être forcé à changer son mot de passe. Le blocage `403 PASSWORD_CHANGE_REQUIRED` s'applique aux endpoints métier, mais l'AT reste renouvelable.

---

### INC-10 — `reset_password()` ne remet pas `password_change_required = False`
**Sévérité : P1**
**Fichier** : `app/services/auth.py:579-580`

Même problème qu'INC-08. Après `reset_password()` (flow forgot password), le flag `password_change_required` n'est pas remis à False.

---

## SECTION 5 — Config : secrets manquants en validation prod

### INC-11 — `HCAPTCHA_SECRET_KEY` absent de la validation prod
**Sévérité : P2**
**Fichier** : `app/core/config.py:115-143`

La validation prod vérifie 6 secrets mais **pas** `HCAPTCHA_SECRET_KEY`. En prod avec `DEBUG=False` et `HCAPTCHA_SECRET_KEY=""`, le CAPTCHA sera FAIL-CLOSED (rejette tout token) mais sans alerte lors du démarrage.

**Correction** : Ajouter `('HCAPTCHA_SECRET_KEY', '')` dans `dev_secrets`.

---

### INC-12 — `PASSWORD_CHANGE_ALLOWED` dupliqué vs `AuthEndpoints`
**Sévérité : P3**
**Fichier** : `app/constants/http.py:75-79`

```python
PASSWORD_CHANGE_ALLOWED: frozenset[str] = frozenset({
    "/api/v1/auth/change-password",   # ← string littérale
    "/api/v1/auth/logout",
    "/api/v1/auth/csrf",
})
```

Les valeurs sont des **string literals**, pas des références à `AuthEndpoints.CHANGE_PASSWORD`, `AuthEndpoints.LOGOUT`, `AuthEndpoints.CSRF`. Si l'un de ces chemins change un jour, `PASSWORD_CHANGE_ALLOWED` n'est pas mis à jour automatiquement.

**Correction** :
```python
PASSWORD_CHANGE_ALLOWED: frozenset[str] = frozenset({
    AuthEndpoints.CHANGE_PASSWORD,
    AuthEndpoints.LOGOUT,
    AuthEndpoints.CSRF,
})
```
Mais attention : crée une dépendance circulaire de classe sur elle-même (la classe référence ses propres attributs). Extraire dans une constante de module.

---

## SECTION 6 — ROLLBACK dans les logs après login réussi

### INC-13 — Double SELECT user + ROLLBACK côté API après login
**Sévérité : P2** (observé dans les logs)

Logs observés :
```
Session created: sid=a080ca7e ... user=1
COMMIT
BEGIN (implicit) request_id=752e7e7b
SELECT users WHERE id=1         ← fetchUser() depuis frontend
ROLLBACK request_id=752e7e7b   ← pourquoi ?
BEGIN (implicit) request_id=28030635
SELECT users WHERE id=1         ← deuxième appel
ROLLBACK request_id=28030635   ← idem
```

**Analyse** : Deux requêtes `GET /auth/me` sont émises simultanément par le frontend juste après le login (race condition dans `fetchUser()`). Ces requêtes utilisent `get_current_user_async` qui **ouvre une transaction implicite** mais ne fait que du SELECT — SQLAlchemy rollback la transaction en sortie si aucun flush/commit n'a été fait (comportement normal pour les transactions read-only).

**Ce n'est pas un bug** — le ROLLBACK sur une transaction read-only est le comportement attendu de SQLAlchemy async. Mais le double appel `GET /auth/me` côté frontend est un gaspillage. `fetchUser()` semble être appelé deux fois (une fois dans `useAuth.ts`, une autre dans un useEffect quelque part).

---

## RÉSUMÉ PAR PRIORITÉ

| ID | Sévérité | Description | Statut |
|----|----------|-------------|--------|
| INC-08 | **P1** | `change_password()` ne remet pas `password_change_required = False` | ❌ À corriger |
| INC-10 | **P1** | `reset_password()` idem | ❌ À corriger |
| INC-01 | **P1** | Device révoqué non vérifié dans `get_current_user` sync | ❌ À corriger |
| INC-04 | **P1** | `CHANGE_PASSWORD` absent de la whitelist CSRF middleware | ⚠️ À analyser |
| INC-06 | **P2** | Atomicité brisée login (commit audit avant commit session) | ❌ À corriger |
| INC-07 | **P2** | `password_change_required` non communiqué dans LoginResponse | ❌ À corriger |
| INC-09 | **P2** | Refresh token ne bloque pas `password_change_required` | ❌ À corriger |
| INC-03 | **P2** | Query sync legacy vs async select() — pattern divergent | ⚠️ Risque faible |
| INC-05 | **P2** | `CSRF_SECRET` configuré mais non utilisé | ❌ Vestige à supprimer |
| INC-11 | **P2** | `HCAPTCHA_SECRET_KEY` absent de la validation prod | ❌ À corriger |
| INC-13 | **P2** | Double `GET /auth/me` en frontend post-login | ⚠️ Perf, pas sécurité |
| INC-12 | **P3** | `PASSWORD_CHANGE_ALLOWED` strings littérales non typesafe | ❌ À corriger |
| INC-02 | **P3** | Docstring `get_current_user_async` incomplète | ❌ À corriger |

---

*Prochaine étape : lire `services/token.py`, `core/redis.py`, `services/session.py` pour auditer la partie token lifecycle et session management.*

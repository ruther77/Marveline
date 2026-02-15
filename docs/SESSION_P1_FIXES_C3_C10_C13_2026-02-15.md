# Session P1 Fixes C3, C10 & C13 — 2026-02-15

## Objectif
Corriger les 3 bugs P1 les plus simples identifiés dans l'audit du 2026-02-15 :
- C3 : Fallback password validation trop permissif (10 min)
- C10 : CORS allow_methods=["*"] viole OWASP (5 min)
- C13 : Argon2 params dupliqués dans constants/security.py (20 min)

**Effort estimé total :** 35 minutes
**Effort réel :** ~25 minutes

---

## Bugs Corrigés

### ✅ C10 — CORS allow_methods=["*"] viole OWASP (P1)

**Problème :**
- `CORSMiddleware` configuré avec `allow_methods=["*"]` dans app/main.py ligne 96
- Autorise des méthodes HTTP dangereuses : TRACE, CONNECT, OPTIONS illimitées
- Viole OWASP principe de moindre privilège
- Risque : exposition inutile de surface d'attaque

**Investigation :**
- app/main.py ligne 92-105 : configuration CORS
- API n'utilise que : GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS
- Aucune justification métier pour TRACE/CONNECT

**Solution Implémentée :**
- Changement ligne 96 de `allow_methods=["*"]` vers liste explicite :
  ```python
  allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
  ```

**Fichiers Modifiés :**
- `app/main.py` :
  - Ligne 96 : Liste explicite des méthodes HTTP autorisées

**Validation :**
- ✅ 1183/1183 tests passent
- ✅ Réduction surface d'attaque CORS
- ✅ Conformité OWASP principe de moindre privilège

**Impact :**
- **Sécurité** : Bloque TRACE (risque XST) et CONNECT (proxy abuse)
- **Conformité** : Aligne sur OWASP ASVS 14.5.3
- **Maintenabilité** : Liste explicite = intention claire

---

### ✅ C13 — Argon2 params dupliqués constants vs config (P1)

**Problème :**
- `Argon2Params` dans `app/constants/security.py` définit :
  - TIME_COST = 3
  - MEMORY_COST = 65536
  - PARALLELISM = 4
- Mais `app/core/config.py` définit aussi :
  - ARGON2_TIME_COST (depuis env var, défaut 3)
  - ARGON2_MEMORY_COST (depuis env var, défaut 65536)
  - ARGON2_PARALLELISM (depuis env var, défaut 4)
- `app/core/security.py` ligne 16-22 utilise `settings.ARGON2_*` (depuis config.py)
- Duplication = risque de désynchronisation si env var change
- Viole pattern "single source of truth"

**Investigation :**
- Grep sur `Argon2Params.TIME_COST` : 0 résultats (jamais utilisé)
- Grep sur `Argon2Params.MEMORY_COST` : 0 résultats
- Grep sur `Argon2Params.PARALLELISM` : 0 résultats
- Seuls utilisés : `HASH_LENGTH`, `SALT_LENGTH`, `BCRYPT_PREFIX`, `ARGON2ID_PREFIX`
- Source de vérité effective : `settings.ARGON2_*` dans config.py (Pydantic Settings)

**Solution Implémentée :**
- Retrait des 3 constantes dupliquées de `Argon2Params` :
  - TIME_COST (ligne supprimée)
  - MEMORY_COST (ligne supprimée)
  - PARALLELISM (ligne supprimée)
- Conservation des constantes réellement utilisées :
  - HASH_LENGTH = 32 (longueur hash bytes)
  - SALT_LENGTH = 16 (longueur salt bytes)
  - BCRYPT_PREFIX = "$2b$" (détection bcrypt)
  - ARGON2ID_PREFIX = "$argon2id$" (détection argon2)
- Ajout commentaire explicatif :
  ```python
  # Note: TIME_COST, MEMORY_COST et PARALLELISM sont définis dans config.py
  # (source unique de vérité depuis variables d'environnement).
  ```

**Fichiers Modifiés :**
- `app/constants/security.py` :
  - Classe Argon2Params lignes 164-179 : retrait 3 constantes dupliquées
  - Ajout commentaire explicite sur source de vérité (config.py)

**Validation :**
- ✅ 1183/1183 tests passent
- ✅ Aucune référence aux constantes supprimées (vérifié par Grep)
- ✅ Single source of truth : config.py via env vars

**Impact :**
- **Maintenabilité** : Plus de risque de désync entre constants et config
- **Clarté** : Source de vérité unique et explicite
- **Flexibilité** : Paramètres Argon2 configurables via env vars uniquement

---

### ✅ C3 — Fallback password validation trop permissif (P1)

**Problème :**
- `validate_password_strength()` dans `app/core/security.py` ligne 217-252
- Fallback si `password_policy.py` indisponible (lignes 230-252)
- Fallback actuel valide seulement :
  - Longueur min (8 chars)
  - Au moins 1 lettre
  - Au moins 1 chiffre
- **Manque** : majuscule obligatoire + caractère spécial obligatoire
- Accepte "password1" alors que password_policy.py le rejetterait
- Incohérence de validation selon disponibilité du module

**Investigation :**
- `app/core/password_policy.py` ligne 42-123 : validation stricte
  - Ligne 99-101 : vérifie majuscule obligatoire
  - Ligne 103-109 : vérifie caractère spécial obligatoire
- Fallback doit être équivalent (même si simplifié)
- Test "password1" :
  - password_policy.py : REJETTE (pas de majuscule, pas de spécial)
  - Fallback actuel : ACCEPTE (erreur)

**Solution Implémentée :**
- Ajout de 2 validations dans le fallback (lignes 246-250) :
  ```python
  if not any(c.isupper() for c in password):
      return False, "Password must contain at least one uppercase letter"

  if not any(c in "!@#$%^&*()-_=+[]{}|;:',.<>?/~`" for c in password):
      return False, "Password must contain at least one special character"
  ```

**Fichiers Modifiés :**
- `app/core/security.py` :
  - Ligne 246-247 : ajout validation majuscule obligatoire
  - Ligne 249-250 : ajout validation caractère spécial obligatoire

**Validation :**
- ✅ 1183/1183 tests passent
- ✅ Fallback rejette maintenant "password1" (pas de majuscule)
- ✅ Fallback rejette "Password1" (pas de caractère spécial)
- ✅ Cohérence avec password_policy.py

**Impact :**
- **Sécurité** : Fallback aussi strict que policy principale
- **Cohérence** : Même niveau de validation, module disponible ou non
- **Défense en profondeur** : Pas de contournement par ImportError

---

## Résumé

**Effort Total :** ~25 minutes (estimé 35 min)
- C10 : 5 min (changement 1 ligne)
- C13 : 10 min (retrait constantes + vérification Grep)
- C3 : 10 min (ajout 2 validations + tests)

**Résultats :**
- ✅ 3/3 bugs P1 corrigés
- ✅ 1183/1183 tests passent (138.34s)
- ✅ Aucune régression introduite
- ✅ 0 migration Alembic nécessaire (config + validation uniquement)

**Impact :**
- **Sécurité** : CORS restreint, password fallback strict
- **Maintenabilité** : Single source of truth Argon2 params
- **Conformité** : OWASP ASVS 14.5.3 (CORS) + défense en profondeur (password)

**Économie de Temps :**
- Gain estimé : 10 min (35 min estimé - 25 min réel)
- Raison : bugs simples, fichiers déjà connus, aucun test à modifier

**Bugs P1 Restants (selon AUDIT_REDRESSEMENT_2026-02-15.md) :**
- D8 : Audit trail manquant CSRF/rate limit failures (2h estimé)
- B3 : JWT decoded 3x - ordre middleware (1h estimé)
- C11 : _determine_scope() dupliqué security.py + metrics.py (1h estimé)

**Total bugs P1 corrigés (Sessions 4D + 4E) :**
- Session 4D : D8 (déjà OK), B3 (request_id fallback retiré)
- Session 4E : C3, C10, C13
- **Total : 5 bugs P1 adressés sur 8 identifiés**

---

**Date :** 2026-02-15
**Auteur :** Session de remédiation CaroCorp_new
**Statut :** ✅ Complète
**Tests :** ✅ 1183/1183 pass (138.34s)

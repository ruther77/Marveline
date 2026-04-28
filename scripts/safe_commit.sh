#!/usr/bin/env bash
# safe_commit.sh — wrapper git commit anti-race-condition pour la branche Page.
#
# Contexte : refonte DEVUP 2026 — un autre agent (Torvalds) commit en parallèle
# dans le même repo. Ses `git checkout Torvalds` peuvent survenir entre nos
# commandes git, faisant atterrir mes commits sur la mauvaise branche OU
# écrasant mes uncommitted edits via le checkout cross-branch.
#
# Ce wrapper :
#   1. flock : sérialise les invocations concurrentes du wrapper
#   2. Pre-flight : si pas sur la branche cible, stash les modifs, switch,
#      pop stash (recovery atomique des éditions en cours)
#   3. Auto-stage : tous les fichiers existants passés en argument sont
#      git add automatiquement (avant le -m)
#   4. Commit + vérification post-commit branche cible
#   5. Recovery automatique si race détectée :
#      - cherry-pick le commit sur la branche cible
#      - reset --hard la branche fautive à HEAD~1 si elle n'a pas bougé
#   6. Auto-push optionnel via --push
#
# Usage :
#   ./scripts/safe_commit.sh app/foo.py tests/test_foo.py -m "feat(X): msg"
#   ./scripts/safe_commit.sh app/foo.py -m "msg" --push
#   ./scripts/safe_commit.sh -m "msg only (legacy mode, pas d'auto-stage)"
#
# Variables d'environnement :
#   SAFE_COMMIT_BRANCH=Page       # branche cible (défaut Page)
#   SAFE_COMMIT_LOCK_TIMEOUT=30   # timeout flock en secondes (défaut 30)
#
# Exit codes :
#   0  : commit landé sur la branche cible (avec ou sans recovery)
#   >0 : échec (commit refusé, conflit cherry-pick, conflit stash pop, etc.)

set -uo pipefail

TARGET_BRANCH="${SAFE_COMMIT_BRANCH:-Page}"
LOCK_TIMEOUT="${SAFE_COMMIT_LOCK_TIMEOUT:-30}"

GIT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
    echo "[safe_commit] FATAL: pas dans un repo git" >&2
    exit 1
}
LOCK_FILE="$GIT_ROOT/.git/safe_commit.lock"

log() { echo "[safe_commit] $*" >&2; }
die() { log "FATAL: $*"; exit 1; }

# ── Parse args (2 passes) ────────────────────────────────────────────────────
# Pass 1 : extraire --push n'importe où dans la commande
PUSH=0
REMAINING=()
for arg in "$@"; do
    if [ "$arg" = "--push" ]; then
        PUSH=1
    else
        REMAINING+=("$arg")
    fi
done

# Pass 2 : séparer fichiers (préfixe) / args git commit (à partir du 1er flag)
FILES=()
COMMIT_ARGS=()
in_commit_args=0
for arg in "${REMAINING[@]}"; do
    if [ $in_commit_args -eq 1 ]; then
        COMMIT_ARGS+=("$arg")
        continue
    fi
    case "$arg" in
        -*)
            # Premier flag : tout ce qui reste va à git commit
            in_commit_args=1
            COMMIT_ARGS+=("$arg")
            ;;
        *)
            # Pas un flag : fichier existant → stage, sinon → arg positionnel
            if [ -e "$arg" ]; then
                FILES+=("$arg")
            else
                COMMIT_ARGS+=("$arg")
            fi
            ;;
    esac
done

# ── flock : sérialiser invocations concurrentes ──────────────────────────────
exec 200>"$LOCK_FILE"
if ! flock -w "$LOCK_TIMEOUT" 200; then
    die "flock timeout après ${LOCK_TIMEOUT}s sur $LOCK_FILE"
fi

# ── 1. Pre-flight : forcer la branche cible (avec stash si modifs en cours) ──
current=$(git branch --show-current)
needs_stash_pop=0

if [ "$current" != "$TARGET_BRANCH" ]; then
    log "branche courante = '$current' → switch vers '$TARGET_BRANCH'"

    # Détecter s'il y a des modifs/staged/untracked qui doivent traverser
    has_changes=0
    if ! git diff --quiet 2>/dev/null; then has_changes=1; fi
    if ! git diff --cached --quiet 2>/dev/null; then has_changes=1; fi
    if [ -n "$(git ls-files --others --exclude-standard 2>/dev/null)" ]; then has_changes=1; fi

    if [ $has_changes -eq 1 ]; then
        log "stash des modifs en cours (incluant untracked)"
        git stash push -u -m "safe_commit auto-stash from $current $(date -u +%FT%TZ)" 2>&1 | tail -2 \
            || die "stash échoué"
        needs_stash_pop=1
    fi

    git checkout "$TARGET_BRANCH" 2>&1 | tail -2 || die "checkout $TARGET_BRANCH échoué"

    if [ $needs_stash_pop -eq 1 ]; then
        log "pop stash sur $TARGET_BRANCH"
        git stash pop 2>&1 | tail -3 \
            || die "stash pop conflit — résolution manuelle requise (cf. git stash list)"
    fi
fi

# ── 2. Auto-stage des fichiers ───────────────────────────────────────────────
if [ ${#FILES[@]} -gt 0 ]; then
    log "auto-stage : ${FILES[*]}"
    git add "${FILES[@]}" || die "git add échoué"
fi

# ── 3. Commit ────────────────────────────────────────────────────────────────
if [ ${#COMMIT_ARGS[@]} -eq 0 ]; then
    die "aucun argument git commit fourni (au moins -m \"...\" requis)"
fi

git commit "${COMMIT_ARGS[@]}"
ce=$?
if [ $ce -ne 0 ]; then
    log "git commit a échoué (exit $ce)"
    exit $ce
fi

# ── 4. Vérification post-commit ──────────────────────────────────────────────
after=$(git branch --show-current)
orphan_hash=$(git rev-parse HEAD)
final_hash="$orphan_hash"

if [ "$after" = "$TARGET_BRANCH" ]; then
    log "OK : commit $orphan_hash sur $TARGET_BRANCH"
else
    # Race détectée — recovery
    log "RACE : commit $orphan_hash atterri sur '$after' (attendu '$TARGET_BRANCH')"
    log "recovery : cherry-pick → $TARGET_BRANCH + reset $after"

    git checkout "$TARGET_BRANCH" 2>&1 | tail -2 || die "recovery checkout échoué"
    git cherry-pick "$orphan_hash" 2>&1 | tail -3 \
        || die "cherry-pick conflit — manuel requis (orphan: $orphan_hash sur $after)"
    final_hash=$(git rev-parse HEAD)
    log "cherry-pick OK : commit $final_hash sur $TARGET_BRANCH"

    # Cleanup branche fautive si tip = orphan inchangé
    git checkout "$after" 2>&1 | tail -2 || die "retour $after échoué"
    after_tip=$(git rev-parse HEAD)
    if [ "$after_tip" = "$orphan_hash" ]; then
        git reset --hard HEAD^ 2>&1 | tail -2 || die "reset $after échoué"
        log "OK : orphan retiré de $after"
    else
        log "WARN : $after a bougé ($after_tip ≠ $orphan_hash), orphan reste — manuel requis"
    fi
    git checkout "$TARGET_BRANCH" 2>&1 | tail -2 || die "checkout final $TARGET_BRANCH échoué"
fi

# ── 5. Auto-push si --push ───────────────────────────────────────────────────
if [ $PUSH -eq 1 ]; then
    log "push origin $TARGET_BRANCH"
    git push origin "$TARGET_BRANCH" 2>&1 | tail -3 || die "push échoué"
fi

log "TERMINÉ : $TARGET_BRANCH = $final_hash$([ $PUSH -eq 1 ] && echo ' (pushed)')"
exit 0

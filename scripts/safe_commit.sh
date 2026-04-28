#!/usr/bin/env bash
# safe_commit.sh — wrapper git commit anti-race-condition pour la branche Page.
#
# Contexte : refonte DEVUP 2026 — un autre agent (Torvalds) commit en parallèle
# sur la branche Torvalds dans le même repo. Ses `git checkout Torvalds` peuvent
# survenir entre mon `git checkout Page` et mon `git commit`, faisant atterrir
# mon commit sur la mauvaise branche.
#
# Ce wrapper :
#   1. Vérifie/force la branche cible AVANT le commit (réduit la fenêtre race)
#   2. Vérifie la branche APRÈS le commit
#   3. Recovery automatique si race détectée :
#        a. Cherry-pick le commit sur la branche cible
#        b. Reset --hard la branche fautive à HEAD~1 (uniquement si elle n'a pas
#           bougé depuis — sinon laisse en place et alerte utilisateur)
#
# Usage :
#   ./scripts/safe_commit.sh -m "feat(B1.S1.T2): description"
#   ./scripts/safe_commit.sh -m "msg" -- file1 file2     # avec args git commit
#
# Override branche cible :
#   SAFE_COMMIT_BRANCH=AutreBranche ./scripts/safe_commit.sh -m "..."
#
# Exit codes :
#   0  : commit landé sur la branche cible (avec ou sans recovery)
#   >0 : échec (commit refusé, conflit cherry-pick, etc.) — état à inspecter

set -uo pipefail  # PAS de -e : on gère explicitement les codes de sortie

TARGET_BRANCH="${SAFE_COMMIT_BRANCH:-Page}"

log() { echo "[safe_commit] $*" >&2; }
die() { log "FATAL: $*"; exit 1; }

# ── 1. Pré-commit : forcer la branche cible ──────────────────────────────────
current=$(git branch --show-current)
if [ "$current" != "$TARGET_BRANCH" ]; then
    log "branche courante = '$current', switch vers '$TARGET_BRANCH'"
    git checkout "$TARGET_BRANCH" 2>&1 | tail -3 || die "checkout $TARGET_BRANCH échoué (changements non-commités ?)"
fi

# ── 2. Commit (capture exit, pas d'auto-exit) ────────────────────────────────
git commit "$@"
ce=$?
if [ $ce -ne 0 ]; then
    log "git commit a échoué (exit $ce) — pas de recovery à faire"
    exit $ce
fi

# ── 3. Vérification post-commit ──────────────────────────────────────────────
after=$(git branch --show-current)
new_hash=$(git rev-parse HEAD)

if [ "$after" = "$TARGET_BRANCH" ]; then
    log "OK : commit $new_hash sur $TARGET_BRANCH"
    exit 0
fi

# ── 4. Race détectée — recovery ──────────────────────────────────────────────
log "RACE détectée : commit $new_hash a atterri sur '$after' (attendu '$TARGET_BRANCH')"
log "recovery : cherry-pick vers $TARGET_BRANCH + reset $after"

git checkout "$TARGET_BRANCH" 2>&1 | tail -2 || die "recovery checkout $TARGET_BRANCH échoué"

git cherry-pick "$new_hash" 2>&1 | tail -3 || die "cherry-pick conflit — résolution manuelle requise (commit $new_hash sur $after)"

recovered=$(git rev-parse HEAD)
log "cherry-pick OK : commit $recovered sur $TARGET_BRANCH"

# Vérifier que la branche fautive n'a PAS bougé depuis (sinon refuser le reset)
git checkout "$after" 2>&1 | tail -2 || die "retour à $after échoué"
after_tip=$(git rev-parse HEAD)

if [ "$after_tip" = "$new_hash" ]; then
    git reset --hard "${new_hash}^" 2>&1 | tail -2 || die "reset $after à HEAD~1 échoué"
    log "OK : commit retiré de $after"
else
    log "WARN : $after a bougé depuis ($after_tip != $new_hash) — autre agent a commité"
    log "     mon commit $new_hash reste dans l'historique de $after"
    log "     manuel : interactive rebase requis pour le retirer si besoin"
fi

git checkout "$TARGET_BRANCH" 2>&1 | tail -2 || die "checkout final $TARGET_BRANCH échoué"
log "OK : recovered, $TARGET_BRANCH = $recovered"
exit 0

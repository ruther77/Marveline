#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# DEVUP Health Monitor — Surveillance auto des containers
# Usage: ./health-monitor.sh [--daemon]
# ─────────────────────────────────────────────────────────
set -euo pipefail

COMPOSE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
LOG_FILE="${COMPOSE_DIR}/logs/health-monitor.log"
CHECK_INTERVAL="${CHECK_INTERVAL:-30}"
MAX_RESTART_ATTEMPTS="${MAX_RESTART_ATTEMPTS:-3}"

# Containers critiques à surveiller
CRITICAL_SERVICES=(api frontend-marveline reverse-proxy)
WATCHED_SERVICES=(api frontend-marveline frontend-epicerie frontend-restaurant reverse-proxy redis_sec redis_cache db celery_worker celery_beat)

# Compteurs de restart par service
declare -A RESTART_COUNT

mkdir -p "$(dirname "$LOG_FILE")"

log() {
  local level="$1" msg="$2"
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[$ts] [$level] $msg" | tee -a "$LOG_FILE"
}

# Récupérer le statut d'un container
get_status() {
  local name="$1"
  docker inspect --format='{{.State.Status}}:{{.State.Health.Status}}' "futurproj_${name}" 2>/dev/null || echo "missing:none"
}

# Auto-restart d'un service
auto_restart() {
  local svc="$1"
  local count="${RESTART_COUNT[$svc]:-0}"

  if [ "$count" -ge "$MAX_RESTART_ATTEMPTS" ]; then
    log "CRITICAL" "[$svc] $MAX_RESTART_ATTEMPTS tentatives echouees — arret du monitoring pour ce service"
    return 1
  fi

  RESTART_COUNT[$svc]=$((count + 1))
  log "ACTION" "[$svc] Tentative de restart ${RESTART_COUNT[$svc]}/$MAX_RESTART_ATTEMPTS"

  cd "$COMPOSE_DIR"

  # Nettoyage cache si c'est un frontend (bug esbuild)
  if [[ "$svc" == frontend-* ]]; then
    log "ACTION" "[$svc] Nettoyage cache Vite/esbuild"
    docker compose run --rm --no-deps --entrypoint sh "$svc" -c \
      'rm -rf /app/node_modules/.cache /app/apps/*/node_modules/.vite /tmp/esbuild-* 2>/dev/null' 2>/dev/null || true
  fi

  docker compose restart "$svc" 2>/dev/null
  sleep 10

  local new_status
  new_status="$(get_status "$svc")"
  if [[ "$new_status" == *"healthy"* ]]; then
    log "OK" "[$svc] Restart reussi — healthy"
    RESTART_COUNT[$svc]=0
    return 0
  else
    log "WARN" "[$svc] Restart — statut: $new_status"
    return 1
  fi
}

# Check complet de tous les services
run_check() {
  local all_ok=true

  for svc in "${WATCHED_SERVICES[@]}"; do
    local status
    status="$(get_status "$svc")"
    local state="${status%%:*}"
    local health="${status##*:}"

    case "$state" in
      running)
        if [[ "$health" == "unhealthy" ]]; then
          log "WARN" "[$svc] UNHEALTHY"
          all_ok=false
          auto_restart "$svc" || true
        elif [[ "$health" == "healthy" ]]; then
          # Reset compteur si healthy
          RESTART_COUNT[$svc]=0
        fi
        ;;
      restarting)
        log "WARN" "[$svc] En boucle de restart"
        all_ok=false
        auto_restart "$svc" || true
        ;;
      exited|dead)
        log "ERROR" "[$svc] DOWN ($state)"
        all_ok=false
        auto_restart "$svc" || true
        ;;
      missing)
        # Container n'existe pas — peut-être un profil non actif
        ;;
      *)
        log "WARN" "[$svc] Statut inconnu: $status"
        ;;
    esac
  done

  if $all_ok; then
    # Log silencieux toutes les 5 minutes (pas chaque check)
    local minute
    minute="$(date '+%M')"
    if (( minute % 5 == 0 )); then
      log "OK" "Tous les services sont healthy"
    fi
  fi
}

# Surveillance des événements Docker (crashes temps réel)
watch_events() {
  log "INFO" "Demarrage surveillance evenements Docker"
  docker events --filter 'type=container' --filter 'event=die' --filter 'event=oom' --format '{{.Actor.Attributes.name}} {{.Action}}' 2>/dev/null | while read -r name event; do
    # Filtrer nos containers
    if [[ "$name" == futurproj_* ]]; then
      local svc="${name#futurproj_}"
      log "ALERT" "[$svc] Container $event"

      # Auto-restart si c'est un service critique
      for critical in "${CRITICAL_SERVICES[@]}"; do
        if [[ "$svc" == "$critical" ]]; then
          sleep 5  # Laisser Docker finir le cleanup
          auto_restart "$svc" || true
          break
        fi
      done
    fi
  done
}

# ─── Main ───
log "INFO" "=== DEVUP Health Monitor demarre ==="
log "INFO" "Interval: ${CHECK_INTERVAL}s | Services: ${#WATCHED_SERVICES[@]} | Max restarts: $MAX_RESTART_ATTEMPTS"

# Mode daemon : lancer le watch events en background + checks périodiques
if [[ "${1:-}" == "--daemon" ]]; then
  watch_events &
  EVENTS_PID=$!
  trap 'kill $EVENTS_PID 2>/dev/null; log "INFO" "Monitor arrete"; exit 0' SIGTERM SIGINT

  while true; do
    run_check
    sleep "$CHECK_INTERVAL"
  done
else
  # Mode one-shot : un seul check
  run_check
fi

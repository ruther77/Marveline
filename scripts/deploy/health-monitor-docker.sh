#!/bin/sh
# DEVUP Health Monitor — tourne dans un container docker:cli
# Surveille les containers, auto-restart les critiques

LOG="/logs/health-monitor.log"
INTERVAL=30
MAX_RESTARTS=3

CRITICAL="futurproj_api futurproj_frontend_marveline futurproj_reverse_proxy"
ALL="futurproj_api futurproj_frontend_marveline futurproj_frontend_epicerie futurproj_frontend_restaurant futurproj_reverse_proxy futurproj_redis_sec futurproj_redis_cache futurproj_db futurproj_celery_worker"

# Compteurs restart (fichiers car pas de tableaux en sh)
mkdir -p /tmp/restarts

log() {
  msg="[$(date '+%Y-%m-%d %H:%M:%S')] [$1] $2"
  echo "$msg" >> "$LOG"
  echo "$msg"
}

get_restart_count() {
  cat "/tmp/restarts/$1" 2>/dev/null || echo "0"
}

inc_restart_count() {
  count=$(get_restart_count "$1")
  count=$((count + 1))
  echo "$count" > "/tmp/restarts/$1"
  echo "$count"
}

reset_restart_count() {
  echo "0" > "/tmp/restarts/$1"
}

is_critical() {
  for c in $CRITICAL; do
    if [ "$1" = "$c" ]; then return 0; fi
  done
  return 1
}

check_service() {
  name="$1"
  status=$(docker inspect --format='{{.State.Status}}' "$name" 2>/dev/null || echo "missing")
  health=$(docker inspect --format='{{.State.Health.Status}}' "$name" 2>/dev/null || echo "none")

  # Healthy = OK
  if [ "$status" = "running" ] && [ "$health" = "healthy" ]; then
    reset_restart_count "$name"
    return 0
  fi

  # Running sans healthcheck = OK
  if [ "$status" = "running" ] && [ "$health" = "none" ]; then
    return 0
  fi

  # Missing = pas lancé, on ignore
  if [ "$status" = "missing" ]; then return 0; fi

  # Problem detected
  log "WARN" "$name status=$status health=$health"

  # Auto-restart si critique
  if is_critical "$name"; then
    count=$(get_restart_count "$name")
    if [ "$count" -ge "$MAX_RESTARTS" ]; then
      log "CRITICAL" "$name $MAX_RESTARTS restarts echoues — abandon"
      return 1
    fi

    new_count=$(inc_restart_count "$name")
    log "ACTION" "Restart $name (tentative $new_count/$MAX_RESTARTS)"
    docker restart "$name" >/dev/null 2>&1 || true
    sleep 15

    new_health=$(docker inspect --format='{{.State.Health.Status}}' "$name" 2>/dev/null || echo "none")
    new_status=$(docker inspect --format='{{.State.Status}}' "$name" 2>/dev/null || echo "dead")

    if [ "$new_status" = "running" ] && { [ "$new_health" = "healthy" ] || [ "$new_health" = "starting" ]; }; then
      log "OK" "$name restart reussi"
      reset_restart_count "$name"
    else
      log "ERROR" "$name toujours down ($new_status/$new_health)"
    fi
  fi
}

# ─── Main loop ───
log "INFO" "=== DEVUP Health Monitor demarre ==="
log "INFO" "Interval: ${INTERVAL}s | Critiques: $(echo $CRITICAL | wc -w) | Max restarts: $MAX_RESTARTS"

# Reset compteurs au demarrage
for svc in $ALL; do
  reset_restart_count "$svc"
done

while true; do
  for svc in $ALL; do
    check_service "$svc"
  done
  sleep "$INTERVAL"
done

#!/usr/bin/env bash
set -euo pipefail

# ── WireGuard interface init ──────────────────────────────────────────
# En mode live (WG_BACKEND=live), initialise l'interface wg0.
# En mode mock (defaut), on skip.

init_wireguard() {
    local iface="${WG_INTERFACE:-wg0}"
    local listen_port="${WG_LISTEN_PORT:-51820}"
    local address="${WG_ADDRESS:-10.10.0.1/24}"

    echo "[entrypoint] Initialisation WireGuard interface ${iface}..."

    # Creer l'interface si elle n'existe pas
    if ! ip link show "${iface}" &>/dev/null; then
        ip link add dev "${iface}" type wireguard
    fi

    # Configurer la cle privee serveur
    if [ -n "${WG_PRIVATE_KEY:-}" ]; then
        echo "${WG_PRIVATE_KEY}" | wg set "${iface}" listen-port "${listen_port}" private-key /dev/stdin
    else
        echo "[entrypoint] WARN: WG_PRIVATE_KEY non definie, interface non configuree"
        return 0
    fi

    # Assigner l'adresse IP
    ip address flush dev "${iface}" 2>/dev/null || true
    ip address add "${address}" dev "${iface}"

    # Activer l'interface
    ip link set up dev "${iface}"

    # PostUp rules (NAT, forwarding)
    if [ -n "${WG_POST_UP:-}" ]; then
        eval "${WG_POST_UP}"
    fi

    echo "[entrypoint] WireGuard ${iface} actif sur port ${listen_port}"
}

# ── Main ──────────────────────────────────────────────────────────────

echo "[entrypoint] WireGuard Service demarrage..."
echo "[entrypoint] ENV=${ENV:-dev} WG_BACKEND=${WG_BACKEND:-mock}"

# Init WG uniquement en mode live
if [ "${WG_BACKEND:-mock}" = "live" ]; then
    init_wireguard
else
    echo "[entrypoint] Mode mock — skip init WireGuard interface"
fi

# Migrations Alembic
echo "[entrypoint] Alembic upgrade..."
alembic upgrade head

echo "[entrypoint] Lancement: $*"
exec "$@"

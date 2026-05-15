#!/bin/bash
# List all homelab services with their IPs and ports.
# Queries each Tailscale-enabled container for its LAN IP and checks service ports.
#
# Usage: PVE1_HOST=<pve1-tailscale-ip> PVE2_HOST=<pve2-tailscale-ip> ./scripts/status.sh
#
# Requires: PVE1_HOST and PVE2_HOST env vars set to Tailscale IPs of each node.

set -euo pipefail

# --- Proxmox hosts (Tailscale IPs) ---
PVE1_TS="${PVE1_HOST:?Set PVE1_HOST to the Tailscale IP of pve1}"
PVE2_TS="${PVE2_HOST:?Set PVE2_HOST to the Tailscale IP of pve2}"

# --- Container definitions: name|vmid|pve_host|services (service:kind:port,...) ---
CONTAINERS=(
  "adguard|100|${PVE1_TS}|AdGuard Home:http:3000,DNS:dns:53"
  "immich|103|${PVE2_TS}|Immich:http:2283"
)

divider="----------------------------------------------------------------------"
SSH_OPTS=(
  -o BatchMode=yes
  -o ConnectionAttempts=1
  -o ConnectTimeout=5
  -o KbdInteractiveAuthentication=no
  -o PasswordAuthentication=no
  -o PreferredAuthentications=publickey
  -o ServerAliveInterval=3
  -o ServerAliveCountMax=1
  -o StrictHostKeyChecking=no
)
REMOTE_TIMEOUT=8s

get_container_ips() {
  local pve_host=$1 vmid=$2
  # Host-side LXC query avoids pct exec hangs in unhealthy containers.
  ssh "${SSH_OPTS[@]}" "root@${pve_host}" \
    "timeout ${REMOTE_TIMEOUT} lxc-info -n ${vmid} -iH 2>/dev/null" 2>/dev/null
}

select_lan_ip() {
  awk -F. '
    /^192\.168\./ { print; found=1; exit }
    /^[0-9.]+$/ && !($1 == 100 && $2 >= 64 && $2 <= 127) && !($1 == 172 && $2 >= 16 && $2 <= 31) { print; found=1; exit }
    END { if (!found) exit 1 }
  '
}

select_ts_ip() {
  awk -F. '$1 == 100 && $2 >= 64 && $2 <= 127 { print; exit }'
}

check_service() {
  local pve_host=$1 kind=$2 ip=$3 port=$4

  if [ "$ip" = "<unavailable>" ]; then
    echo "DOWN"
    return
  fi

  if [ "$kind" = "dns" ]; then
    ssh "${SSH_OPTS[@]}" "root@${pve_host}" \
      "timeout ${REMOTE_TIMEOUT} dig +time=2 +tries=1 @${ip} example.com A +short >/dev/null" 2>/dev/null \
      && echo "UP" || echo "DOWN"
    return
  fi

  ssh "${SSH_OPTS[@]}" "root@${pve_host}" \
    "timeout ${REMOTE_TIMEOUT} nc -z -w 2 ${ip} ${port}" 2>/dev/null \
    && echo "UP" || echo "DOWN"
}

service_url() {
  local kind=$1 ip=$2 port=$3

  if [ "$kind" = "dns" ]; then
    printf "dns://%s:%s" "$ip" "$port"
  else
    printf "http://%s:%s" "$ip" "$port"
  fi
}

printf "\n  Homelab Service Status\n"
printf "  %s\n\n" "$divider"

for entry in "${CONTAINERS[@]}"; do
  IFS='|' read -r name vmid pve_host services <<< "$entry"

  container_ips=$(get_container_ips "$pve_host" "$vmid" 2>/dev/null || true)
  lan_ip=$(printf "%s\n" "$container_ips" | select_lan_ip 2>/dev/null || true)
  ts_ip=$(printf "%s\n" "$container_ips" | select_ts_ip 2>/dev/null || true)
  lan_ip="${lan_ip:-<unavailable>}"
  ts_ip="${ts_ip:-<none>}"

  printf "  %-14s CT %s\n" "$name" "$vmid"
  printf "  LAN: %-18s Tailscale: %s\n" "$lan_ip" "$ts_ip"
  printf "  %s\n" "---"

  IFS=',' read -ra svc_list <<< "$services"
  for svc in "${svc_list[@]}"; do
    svc_name="${svc%%:*}"
    svc_rest="${svc#*:}"
    svc_kind="${svc_rest%%:*}"
    svc_port="${svc_rest##*:}"
    status=$(check_service "$pve_host" "$svc_kind" "$lan_ip" "$svc_port" 2>/dev/null || echo "DOWN")
    url=$(service_url "$svc_kind" "$lan_ip" "$svc_port")
    if [ "$status" = "UP" ]; then
      marker="*"
    else
      marker=" "
    fi
    printf "  [%s] %-18s %s\n" "$marker" "$svc_name" "$url"
  done
  printf "\n"
done

printf "  %s\n" "$divider"
printf "  [*] = port listening    [ ] = port not listening\n\n"

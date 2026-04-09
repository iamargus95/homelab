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

# --- Container definitions: name|vmid|pve_host|services (service:port,...) ---
CONTAINERS=(
  "adguard|100|${PVE2_TS}|AdGuard Home:3000,DNS:53"
  "jellyfin|101|${PVE1_TS}|Jellyfin:8096"
  "mediastack|102|${PVE1_TS}|Transmission:9091,Radarr:7878,Sonarr:8989,Prowlarr:9696,FlareSolverr:8191"
)

divider="----------------------------------------------------------------------"

get_container_ip() {
  local pve_host=$1 vmid=$2
  # Get the container's eth0 inet address via pct exec
  ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "root@${pve_host}" \
    "pct exec ${vmid} -- ip -4 -o addr show eth0 2>/dev/null" 2>/dev/null \
    | awk '{print $4}' | cut -d/ -f1
}

get_container_ts_ip() {
  local pve_host=$1 vmid=$2
  ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "root@${pve_host}" \
    "pct exec ${vmid} -- ip -4 -o addr show tailscale0 2>/dev/null" 2>/dev/null \
    | awk '{print $4}' | cut -d/ -f1
}

check_port() {
  local pve_host=$1 vmid=$2 port=$3
  ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "root@${pve_host}" \
    "pct exec ${vmid} -- ss -tlnp sport = :${port}" 2>/dev/null \
    | grep -q ":${port}" && echo "UP" || echo "DOWN"
}

printf "\n  Homelab Service Status\n"
printf "  %s\n\n" "$divider"

for entry in "${CONTAINERS[@]}"; do
  IFS='|' read -r name vmid pve_host services <<< "$entry"

  lan_ip=$(get_container_ip "$pve_host" "$vmid" 2>/dev/null || true)
  ts_ip=$(get_container_ts_ip "$pve_host" "$vmid" 2>/dev/null || true)
  lan_ip="${lan_ip:-<unavailable>}"
  ts_ip="${ts_ip:-<none>}"

  printf "  %-14s CT %s\n" "$name" "$vmid"
  printf "  LAN: %-18s Tailscale: %s\n" "$lan_ip" "$ts_ip"
  printf "  %s\n" "---"

  IFS=',' read -ra svc_list <<< "$services"
  for svc in "${svc_list[@]}"; do
    svc_name="${svc%%:*}"
    svc_port="${svc##*:}"
    status=$(check_port "$pve_host" "$vmid" "$svc_port" 2>/dev/null || echo "DOWN")
    if [ "$status" = "UP" ]; then
      marker="*"
    else
      marker=" "
    fi
    printf "  [%s] %-18s http://%s:%s\n" "$marker" "$svc_name" "$lan_ip" "$svc_port"
  done
  printf "\n"
done

printf "  %s\n" "$divider"
printf "  [*] = port listening    [ ] = port not listening\n\n"

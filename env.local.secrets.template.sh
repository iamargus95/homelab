#!/bin/bash
# env.local.secrets.sh
# Copy this file to env.local.secrets.sh and fill in your values.

# --- Infrastructure ---
STORAGE="zfs-pve-1"
TEMPLATE_STORAGE="local"
BRIDGE="vmbr0"
PASSWORD="changeme"

# --- IDs ---
ADGUARD_ID=100
IMMICH_ID=103

# --- Network ---
# Cloudflare (1.1.1.1) and Google (8.8.8.8) are safe defaults
DNS_SERVERS="1.1.1.1 8.8.8.8"

# --- Tailscale (Optional) ---
# If you leave this empty, you will have to run 'tailscale up' manually via console
TS_AUTH_KEY=""

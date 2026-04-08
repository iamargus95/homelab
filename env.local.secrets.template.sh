#!/bin/bash
# env.local.secrets.sh
# Copy this file to env.local.secrets.sh and fill in your values.

# --- Infrastructure ---
STORAGE="zfs-pve-1"
TEMPLATE_STORAGE="local"
BRIDGE="vmbr0"
PASSWORD="changeme"

# --- IDs ---
JELLYFIN_ID=101
MEDIA_ID=102

# --- Network ---
# Cloudflare (1.1.1.1) and Google (8.8.8.8) are safe defaults
DNS_SERVERS="1.1.1.1 8.8.8.8"

# --- Storage Paths ---
ZFS_POOL="zfs-pve-1"
MEDIA_DIR="/zfs-pve-1/media"

# --- App Credentials ---
TRANS_USER="admin"
TRANS_PASS="changeme"

# --- Versioning ---
FLARE_VER="v3.3.21"

# --- Tailscale (Optional) ---
# If you leave this empty, you will have to run 'tailscale up' manually via console
TS_AUTH_KEY=""

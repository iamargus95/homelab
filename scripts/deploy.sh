#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "======================================"
echo " Homelab Deploy"
echo "======================================"

# Phase 1: Host preparation
echo ""
echo "==> [1/3] Preparing Proxmox hosts (Ansible)..."
cd "$ROOT_DIR/ansible"
ansible-playbook playbooks/host-setup.yml --ask-vault-pass "$@"

# Phase 2: Infrastructure provisioning
echo ""
echo "==> [2/3] Provisioning containers (Terraform)..."
cd "$ROOT_DIR/terraform"
terraform init -input=false
terraform apply -auto-approve

# Phase 3: Configuration management
echo ""
echo "==> [3/3] Configuring containers (Ansible)..."
cd "$ROOT_DIR/ansible"
ansible-playbook playbooks/site.yml --ask-vault-pass "$@"

echo ""
echo "======================================"
echo " Deploy complete!"
echo "======================================"
echo ""
echo " Access your services:"
echo "   Jellyfin:     http://<jellyfin-ip>:8096"
echo "   Transmission: http://<mediastack-ip>:9091"
echo "   Radarr:       http://<mediastack-ip>:7878"
echo "   Sonarr:       http://<mediastack-ip>:8989"
echo "   Prowlarr:     http://<mediastack-ip>:9696"
echo "   FlareSolverr: http://<mediastack-ip>:8191"
echo "   AdGuard:      http://<adguard-ip>:3000"
echo ""
echo " Tip: Use 'terraform output' to see container details."

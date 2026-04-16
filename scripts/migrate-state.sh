#!/bin/bash
# One-shot Terraform state migration for homelab-v2 rename.
# Renames module.mediastack -> module.transmission in the remote state so
# Terraform doesn't try to destroy+recreate CT 102.
#
# Idempotent: if module.mediastack is not present, does nothing.
#
# Prereqs: backend env vars (GITHUB_TOKEN) exported so terraform init succeeds.

set -euo pipefail
cd "$(dirname "$0")/.."

cd terraform
terraform init -reconfigure >/dev/null

if terraform state list 2>/dev/null | grep -q "^module.mediastack\."; then
  echo "Moving module.mediastack -> module.transmission in state..."
  terraform state mv module.mediastack module.transmission
  echo "Done."
else
  echo "module.mediastack not present in state — nothing to do."
fi

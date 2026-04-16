# Homelab v2: Slim media stack + Immich with cross-node backup

**Date:** 2026-04-17
**Status:** Approved (pending user review of written spec)

## Goals

1. Remove the *arr apps (Sonarr, Radarr, Prowlarr, FlareSolverr) from the mediastack; keep only Jellyfin + Transmission.
2. Fix "downloads > 15GB fail" by setting a ZFS `reservation=200G` on the shared media dataset.
3. **Migrate AdGuard (CT 100) from pve2 → pve1** so pve2 becomes a dedicated Immich host. AdGuard's settings/config are preserved via one-time export+restore; runtime query logs and stats are not.
4. Add Immich as a new LXC on pve2, backed by a 100GB-reserved ZFS dataset, deployed via Docker Compose inside the LXC.
5. Daily cron on pve2 performs a ZFS-send-based backup of the Immich dataset to pve1, at 03:00 Asia/Kolkata (IST).

## Non-goals

- No arr-apps replacement. User has decided to acquire media manually.
- No Immich high-availability or live replication. Daily backup is sufficient.
- No change to AdGuard, Tailscale, CI/CD workflows, or the terraform-backend-git state store.
- No SSD migration. HDD performance is acceptable for both media and photo workloads.

## Current state summary

```
pve1 (192.168.1.36)  NVMe 256GB (Proxmox OS/LVM)    HDD 500GB (zfs-pve-1)
  ├─ CT 101 jellyfin   zfs-pve-1, 10GB root, iGPU passthrough, /zfs-pve-1/media → /media
  └─ CT 102 mediastack zfs-pve-1, 15GB root,         /zfs-pve-1/media → /data
        ├─ transmission-daemon (port 9091)
        ├─ radarr    (port 7878)     ← REMOVE
        ├─ sonarr    (port 8989)     ← REMOVE
        ├─ prowlarr  (port 9696)     ← REMOVE
        └─ flaresolverr (port 8191)  ← REMOVE

pve2 (192.168.1.41)  NVMe 256GB (Proxmox OS/LVM)    HDD 1TB (zfs-pve-2, mostly empty)
  └─ CT 100 adguard  local-lvm, 2GB root, 512MB RAM — MIGRATE to pve1
```

## Target state

```
pve1  zfs-pve-1 (500GB HDD) + local-lvm NVMe
  ├─ CT 100 adguard          MIGRATED from pve2, local-lvm (NVMe), config restored
  ├─ CT 101 jellyfin         unchanged
  ├─ CT 102 transmission     renamed from mediastack; only transmission-daemon
  ├─ zfs-pve-1/media         reservation=200G  (fixes large-download failures)
  └─ zfs-pve-1/immich-backup NEW dataset, backup target for pve2 → pve1 send

pve2  zfs-pve-2 (1TB HDD) — dedicated Immich host
  └─ CT 103 immich           NEW, Docker-in-LXC, /zfs-pve-2/immich → /data
      zfs-pve-2/immich       NEW dataset, reservation=100G
```

## Design details

### 1. ZFS datasets and reservations

Added to `ansible/roles/zfs-media/tasks/main.yml` (runs on pve1):
- Apply `reservation=200G` to `zfs-pve-1/media` (idempotent via `zfs set`).
- Create `zfs-pve-1/immich-backup` dataset (no reservation — receives incremental sends; pool has ~200GB free after media reservation + small OS overhead).

New role `ansible/roles/zfs-immich/tasks/main.yml` (runs on pve2 via `host-setup.yml`):
- Create `zfs-pve-2/immich` dataset with `reservation=100G`.
- Create subdirs `library/`, `postgres/`, `model-cache/` under `/zfs-pve-2/immich` with mode 0755 owned by root. Immich's postgres container initializes its own `data/` ownership on first boot; the other dirs are written by root-owned services.

Semantics: ZFS `reservation` guarantees space is always available for that dataset even if sibling datasets try to consume the pool. It does NOT cap growth. This is deliberately different from `quota` — we want headroom, not a lid.

### 2. Transmission-only container (CT 102 rename + gut)

**Terraform:**
- Rename `terraform/mediastack.tf` → `terraform/transmission.tf`.
- Module name `module.mediastack` → `module.transmission`.
- Keep `vmid = 102` to avoid destroy/recreate.
- `hostname` changes from `mediastack` to `transmission`.
- Memory lowered from 4096MB to 2048MB (arr apps were the heaviest consumers).
- Disk, storage_pool, mountpoints, idmap, TUN all unchanged.
- State migration: `terraform state mv module.mediastack module.transmission` (run once on the tf-state git branch; scripted in `scripts/migrate-state.sh`).

**Ansible:**
- Rename `ansible/roles/mediastack/` → `ansible/roles/transmission/`.
- Delete from the role's `tasks/main.yml`:
  - xvfb + browser lib dependencies block (was for FlareSolverr).
  - Entire FlareSolverr install / systemd section.
  - Entire `arr_apps` loop (radarr/sonarr/prowlarr download, systemd templates, start).
- Delete templates: `arr.service.j2`, `flaresolverr.service.j2`. Keep `transmission-override.conf.j2`.
- Keep transmission-daemon install, user/group config, override file, settings.json edits, `download-dir: /data/downloads`.
- Rename playbook `playbooks/mediastack.yml` → `playbooks/transmission.yml`; update `site.yml`.
- Rename `inventory/group_vars/mediastack.yml` → `transmission.yml`; drop `arr_apps` and `flaresolverr_version` vars.
- Rename inventory group `mediastack:` → `transmission:` in `hosts.yml.example` and users' real `hosts.yml`.

**Manual cleanup (inside CT 102, done by Ansible via apt/systemd tasks):**
- Stop + disable + remove systemd units: radarr, sonarr, prowlarr, flaresolverr.
- Remove installed directories: `/opt/radarr`, `/opt/sonarr`, `/opt/prowlarr`, `/opt/flaresolverr`, plus `/var/lib/{radarr,sonarr,prowlarr}`.
- Apt remove xvfb + related libs (optional, purely for cleanliness).

### 3. AdGuard migration (CT 100, pve2 → pve1)

**Pre-deploy: export config from pve2**
A one-shot Ansible play (`playbooks/adguard-migrate.yml`) runs against the current pve2 AdGuard container and uses the `fetch` module to pull:
- `/opt/AdGuardHome/AdGuardHome.yaml` (the runtime config: upstream servers, filters enabled, custom rules)
- `/opt/AdGuardHome/data/filters/*.txt` (downloaded filter lists — regenerable, optional)
- `/opt/AdGuardHome/data/sessions.db` (admin UI sessions — optional, will be recreated)

Output: a local `backups/adguard-config-<timestamp>.tar.gz` checked into neither git nor the repo (gitignored).

**Terraform changes (`terraform/adguard.tf`):**
- `target_node = "pve1"` (was `pve2`)
- `pve_ssh_host = var.pve1_ssh_host` (was `pve2_ssh_host`)
- `disk_size = 10` (was `2`) — more headroom for AdGuard query logs, stats, and filter list cache. Small fraction of the ~250GB NVMe LVM on pve1.
- Other fields unchanged: `vmid=100`, `cores=1`, `memory=512`, `storage_pool="local-lvm"` (NVMe on pve1 — DNS benefits from low latency, and it's not media data so the sda constraint doesn't apply).

Since `target_node` change is a ForceNew in the Proxmox provider, `terraform apply` will destroy CT 100 on pve2 and create a fresh CT 100 on pve1. Expected disruption: LAN-wide DNS outage for ~2–5 min during the destroy→create→Ansible-configure sequence. Plan to run the migration during the low-traffic window (also 03:00 IST).

**Restore path (post-create):**
- Updated `adguard` Ansible role includes a task that checks for the backup tarball on the control node and, if present, copies `AdGuardHome.yaml` into place before starting the AdGuard service. Idempotent: on re-runs, skips if target file exists and matches.
- The `adguard` role already installs AdGuard Home binary via Ansible; this is unchanged.

**IP/DHCP note:** the new CT 100 will get a new DHCP lease on pve1's bridge. If the user's router/DHCP is configured to point clients at the old CT 100 IP for DNS, that config needs updating — either update the router-level DNS setting, or configure a DHCP reservation on the bridge so the new container lands on a predictable IP. Flagged in README.

### 4. Immich container (CT 103 new)

**Terraform (`terraform/immich.tf`):**
- `module "immich"` using existing `./modules/lxc-container`.
- `vmid = 103`, `hostname = immich`, `target_node = pve2`.
- `cores = 4`, `memory = 4096`, `disk_size = 20`.
- `storage_pool = "zfs-pve-2"` (root disk lands on sda HDD, per user constraint).
- `mountpoints = [{ host_path = "/zfs-pve-2/immich", container_path = "/data" }]`.
- `extra_lxc_config`:
  - `lxc.cgroup2.devices.allow: c 10:200 rwm` + `lxc.mount.entry: /dev/net/tun …` (TUN for Tailscale).
  - `lxc.cgroup2.devices.allow: c 10:229 rwm` + `lxc.mount.entry: /dev/fuse …` (FUSE for fuse-overlayfs).
  - Default unprivileged UID/GID map (no shared-media UID bridging needed; Immich has no cross-container access needs).

**Ansible role `immich`:**
- Install Docker CE + `docker-compose-plugin` + `fuse-overlayfs` from Docker's apt repo.
- Write `/etc/docker/daemon.json` with `{"storage-driver": "fuse-overlayfs"}`.
- Template `/opt/immich/docker-compose.yml` from the official upstream release (pinned version in `group_vars/immich.yml`).
- Template `/opt/immich/.env` with:
  - `UPLOAD_LOCATION=/data/library`
  - `DB_DATA_LOCATION=/data/postgres`
  - `IMMICH_VERSION=release` (pinned tag in a variable)
  - `DB_PASSWORD={{ vault_immich_db_password }}`
- Deploy a systemd unit `immich.service` (`ExecStart=docker compose -f /opt/immich/docker-compose.yml up`, `ExecStop=docker compose down`) for boot persistence.
- Install Tailscale (already done by existing `tailscale` role — reuse).

**Compose file bind mounts all point at `/data/…`** so every piece of Immich state sits on the ZFS dataset that will be snapshotted:
- `${UPLOAD_LOCATION}:/usr/src/app/upload` (photo library)
- `${DB_DATA_LOCATION}:/var/lib/postgresql/data`
- `./model-cache:/cache` → `/data/model-cache`

### 5. Backup pipeline

**Script:** `/usr/local/bin/immich-backup.sh` on pve2 (deployed by new Ansible role `immich-backup` targeting pve2):

```bash
#!/bin/bash
set -euo pipefail
DATASET="zfs-pve-2/immich"
REMOTE="root@${PVE1_TS_IP}"
REMOTE_DATASET="zfs-pve-1/immich-backup"
TS=$(date +%Y%m%d-%H%M)
SNAP="${DATASET}@backup-${TS}"

pct exec 103 -- docker compose -f /opt/immich/docker-compose.yml stop
zfs snapshot "$SNAP"
pct exec 103 -- docker compose -f /opt/immich/docker-compose.yml start

PREV=$(zfs list -t snapshot -H -o name "$DATASET" | grep '@backup-' | tail -2 | head -1 || true)
if [ -n "$PREV" ] && [ "$PREV" != "$SNAP" ]; then
  zfs send -i "$PREV" "$SNAP" | ssh "$REMOTE" "zfs receive -F $REMOTE_DATASET"
else
  zfs send "$SNAP" | ssh "$REMOTE" "zfs receive -F $REMOTE_DATASET"
fi

zfs list -t snapshot -H -o name "$DATASET" | grep '@backup-' | sort | head -n -7 | xargs -r -n1 zfs destroy
ssh "$REMOTE" "zfs list -t snapshot -H -o name $REMOTE_DATASET | grep '@backup-' | sort | head -n -7 | xargs -r -n1 zfs destroy"
```

**Cron:** `/etc/cron.d/immich-backup` on pve2:
```
CRON_TZ=Asia/Kolkata
0 3 * * * root /usr/local/bin/immich-backup.sh >> /var/log/immich-backup.log 2>&1
```

Using `CRON_TZ` (supported by vixie-cron / systemd-cron on Debian/Ubuntu) keeps the schedule unambiguously at 03:00 IST without changing the Proxmox host's system timezone (which would affect journald/system logs).

**Prerequisites:**
- SSH keypair for `root@pve2 → root@pve1` over Tailscale IP. Deployed by Ansible `common` role additions (one-time generated per-host key, authorized on the remote).
- `PVE1_TS_IP` pulled from Ansible `group_vars/all.yml` (already exposed as `ansible_host` for pve1).
- Log rotation for `/var/log/immich-backup.log` via Ansible `logrotate` drop-in.

**Operational behavior:**
- Nightly downtime: ~30–60s while `docker compose stop/start` cycles.
- First send: full stream, ~15–30 min over LAN or Tailscale for a 100GB dataset.
- Subsequent sends: incremental — typically <1GB/day for an active photos user.
- Retention: 7 daily snapshots on both pve2 and pve1. No weekly/monthly tier — keep simple.
- Restore path (documented in README): `ssh pve1 "zfs send zfs-pve-1/immich-backup@<snap>" | zfs receive zfs-pve-2/immich-restore` on pve2, then swap dataset names and restart compose.

### 6. Documentation updates

- **README.md:** update the "Containers" and "Storage" sections: drop arr apps from the mediastack bullet, rename mediastack → transmission, move AdGuard to pve1, add CT 103 / Immich, add ZFS reservations note, add the backup pipeline section (cron schedule at 03:00 IST, restore procedure). Add a note that clients must point DNS at AdGuard's new IP on pve1.
- **architecture.drawio:** replace the "Mediastack" node's sub-services list (remove radarr/sonarr/prowlarr/flaresolverr; keep transmission). Move the "AdGuard (CT 100)" box from pve2 to pve1. Add a new "Immich (CT 103)" box on the pve2 side, shown as the sole container on pve2. Draw the nightly-backup arrow from pve2 zfs-pve-2/immich to pve1 zfs-pve-1/immich-backup, labeled "ZFS send @ 03:00 IST (Tailscale)". Update the shared ZFS pool caption on pve1 to show the 200G reservation and the new immich-backup dataset.
- **jellyfin.sh** (bootstrap script): no change expected, but verify it doesn't reference arr endpoints.
- **scripts/status.sh:** update the service list being pinged — drop arr app ports, add Immich (default 2283).

## File-by-file change list

### Terraform
- `terraform/mediastack.tf` → rename to `terraform/transmission.tf`, update hostname + module name + memory.
- `terraform/adguard.tf` — `target_node` pve2 → pve1, `pve_ssh_host` pve2 → pve1.
- `terraform/immich.tf` — new file.
- `terraform/outputs.tf` — add Immich IP output.
- No change: `main.tf`, `jellyfin.tf`, `variables.tf`, `terraform.tfvars.example`.

### Ansible
- `ansible/roles/mediastack/` → rename to `ansible/roles/transmission/`; gut arr/flaresolverr tasks + templates.
- `ansible/roles/adguard/tasks/main.yml` — add optional restore-from-backup task that copies a fetched `AdGuardHome.yaml` into place before service start.
- `ansible/roles/immich/` — new role (tasks + templates + handlers).
- `ansible/roles/immich-backup/` — new role (script + cron + SSH key + logrotate).
- `ansible/roles/zfs-media/tasks/main.yml` — add `zfs set reservation=200G zfs-pve-1/media` and create `zfs-pve-1/immich-backup`.
- `ansible/roles/zfs-immich/` — new role (dataset + subdirs on pve2).
- `ansible/roles/common/` — add SSH keygen + authorized_key exchange tasks for pve2 → pve1 root.
- `ansible/playbooks/mediastack.yml` → rename to `transmission.yml`.
- `ansible/playbooks/adguard-migrate.yml` — new one-shot play: fetch config from current pve2 CT 100 before destroy.
- `ansible/playbooks/immich.yml` — new.
- `ansible/playbooks/host-setup.yml` — add zfs-immich role on pve2 hosts.
- `ansible/playbooks/site.yml` — swap mediastack for transmission import; add immich + immich-backup imports.
- `ansible/inventory/group_vars/mediastack.yml` → rename to `transmission.yml`; prune arr vars.
- `ansible/inventory/group_vars/immich.yml` — new (IMMICH_VERSION pin, UPLOAD_LOCATION, etc.).
- `ansible/inventory/hosts.yml.example` — rename `mediastack` group to `transmission`; move adguard CT 100 under pve1; add `immich` group with CT 103 on pve2.
- `ansible/vault.yml` — add `vault_immich_db_password`.

### Scripts
- `scripts/status.sh` — swap service port list.
- `scripts/migrate-state.sh` — new one-shot script, runs `terraform state mv module.mediastack module.transmission`.

### Docs
- `README.md` — container table, storage table, backup section, restore runbook.
- `architecture.drawio` — as described above.

## Deploy order (to be detailed in the implementation plan)

1. On a branch: make Terraform + Ansible changes.
2. Run `adguard-migrate.yml` to fetch AdGuard config from the live pve2 CT 100 to the control node as a tarball.
3. Run `scripts/migrate-state.sh` to move terraform state (`module.mediastack` → `module.transmission`).
4. Apply Ansible host-setup (applies ZFS reservation on pve1, creates `zfs-pve-1/immich-backup`, creates `zfs-pve-2/immich`, generates cross-node SSH key pve2 → pve1).
5. Apply Terraform:
   - Destroys CT 100 on pve2, creates CT 100 on pve1.
   - Renames CT 102 hostname from `mediastack` to `transmission`.
   - Creates CT 103 immich on pve2.
6. Run Ansible `site.yml`:
   - `adguard` role reconfigures CT 100 and restores saved config.
   - `transmission` role (renamed) cleans up arr services inside CT 102.
   - `immich` role installs Docker + deploys compose stack in CT 103.
   - `immich-backup` role deploys script + cron on pve2.
7. Manually trigger first `immich-backup.sh` once to seed pve1 with the full send (so the first cron run just does an incremental).
8. Verify: Immich UI reachable on CT 103, Jellyfin/Transmission unaffected, AdGuard answering DNS at its new pve1 IP.
9. Update router/DHCP client-DNS setting to AdGuard's new IP.
10. Update README + drawio, commit, push.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| First `zfs send` takes too long or fails midway | Script exits with error; cron re-runs next day; can be triggered manually any time. `zfs receive -F` makes it resumable-on-replace. |
| fuse-overlayfs not loading inside unprivileged LXC | Fallback: mark LXC privileged (user choice), or switch Docker to `vfs` driver (slow but always works). |
| Immich DB migration failure after upgrade | Pinned `IMMICH_VERSION` in group_vars prevents surprise upgrades. Backups give rollback target. |
| Terraform state move applied before code merge | `migrate-state.sh` is idempotent (checks if source exists first). |
| 30s downtime unacceptable | Can switch to snapshot-without-stop (PG crash-recovery handles it); documented as an option. |
| AdGuard config lost during pve2 → pve1 destroy/recreate | Pre-deploy `adguard-migrate.yml` play fetches `AdGuardHome.yaml` to control node; `adguard` role restores it on new CT 100 before service start. |
| LAN DNS outage during AdGuard migration | Run migration during the same low-traffic window (03:00 IST). Have a fallback upstream DNS (e.g. `1.1.1.1`) configured on the router for the outage window. |
| DNS is now a single-node SPOF on pve1 | Accepted trade-off per user request. Router fallback DNS mitigates full outages; Proxmox/node-level failures remain the exposure. |
| AdGuard's IP changes on pve1, clients still query old IP | Flagged in README runbook; user updates router-level DNS setting or sets DHCP reservation for predictable IP. |

# Homelab

My playground for my homelab setup, running on a two-node Proxmox VE cluster. Infrastructure is managed with **OpenTofu** (container lifecycle) and **Ansible** (software configuration), deployed via **GitHub Actions**.

## Cluster Overview

| Property           | Value                          |
|--------------------|--------------------------------|
| Cluster Name       | pve-cluster                    |
| Proxmox VE Version | 8.4.17                         |
| Kernel             | Linux 6.8.12-20-pve            |
| Nodes              | 2 (pve1, pve2)                 |
| Total CPUs         | 8 cores (4 per node)           |
| Total Memory       | 23.17 GiB                      |
| Total Storage      | 1.73 TiB                       |

## Nodes

### pve1

| Property       | Value                                        |
|----------------|----------------------------------------------|
| IP Address     | 192.168.1.36                                 |
| CPU            | Intel Core i5-6500T @ 2.50GHz (4 cores)      |
| RAM            | 15.52 GiB                                    |
| Boot Mode      | EFI (Secure Boot)                            |
| OS Disk        | WDC PC SN730 NVMe 256 GB                     |
| Data Disk      | HGST HTS725050A7E630 HDD 500 GB (ZFS)        |

### pve2

| Property       | Value                                        |
|----------------|----------------------------------------------|
| IP Address     | 192.168.1.41                                 |
| CPU            | Intel Core i5-6500T @ 2.50GHz (4 cores)      |
| RAM            | 7.65 GiB                                     |
| Boot Mode      | EFI                                          |
| OS Disk        | WDC PC SN730 NVMe 256 GB                     |
| Data Disk      | HGST HTS541010A9E680 HDD 1 TB (ZFS)          |

## Storage

Each node has three storage backends:

| Storage        | Node  | Type      | Content                              | Total Size |
|----------------|-------|-----------|--------------------------------------|------------|
| local          | pve1  | Directory | Backups, ISO images, CT templates    | 72.72 GB   |
| local-lvm      | pve1  | LVM       | VM/CT disks                          | —          |
| zfs-pve-1      | pve1  | ZFS       | VM/CT disks, shared media            | —          |
| local          | pve2  | Directory | Backups, ISO images, CT templates    | —          |
| local-lvm      | pve2  | LVM       | VM/CT disks                          | —          |
| zfs-pve-2      | pve2  | ZFS       | VM/CT disks                          | —          |

The ZFS pool on pve1 (`zfs-pve-1`) hosts a shared `/zfs-pve-1/media` dataset (with a **200 GB reservation**) bind-mounted into both Jellyfin and Transmission so they share the same media library. pve1 also hosts `zfs-pve-1/immich-backup`, which receives nightly ZFS snapshots from pve2 for cross-node backup.

The ZFS pool on pve2 (`zfs-pve-2`) hosts `zfs-pve-2/immich` with a **100 GB reservation**, bind-mounted into the Immich container at `/data`.

## Disk Health

| Device         | Node  | Type  | Model                    | Serial          | Size     | RPM   | S.M.A.R.T. | Wearout (remaining) |
|----------------|-------|-------|--------------------------|-----------------|----------|-------|-------------|----------------------|
| /dev/nvme0n1   | pve1  | NVMe  | WDC PC SN730 SDBQNTY    | 21021U445008    | 256 GB   | —     | PASSED      | 20%                  |
| /dev/sda       | pve1  | HDD   | HGST HTS725050A7E630     | RCF50ACF04ZNWK  | 500 GB   | —     | PASSED      | N/A                  |
| /dev/nvme0n1   | pve2  | NVMe  | WDC PC SN730 SDBQNTY    | 21021N806941    | 256 GB   | —     | PASSED      | 92%                  |
| /dev/sda       | pve2  | HDD   | HGST HTS541010A9E680     | JD1009CC1G77TH  | 1 TB     | 5400  | PASSED      | N/A                  |

> **Note:** pve1's NVMe is at 20% remaining life — consider planning a replacement.

## Containers

### Media Stack (pve1)

The media stack runs on pve1 and provides automated media management and streaming.

| VMID | Name         | Type | OS     | Cores | RAM    | Root Disk | Start on Boot |
|------|--------------|------|--------|-------|--------|-----------|---------------|
| 101  | jellyfin     | LXC  | Ubuntu | 2     | 2 GiB  | 10 GB     | Yes           |
| 102  | transmission | LXC  | Ubuntu | 2     | 2 GiB  | 15 GB     | Yes           |

Both containers are unprivileged with nesting enabled, use DHCP for networking on `vmbr0`, and resolve DNS via `1.1.1.1` and `8.8.8.8`.

#### Jellyfin (CT 101)

Self-hosted media server for streaming movies and TV shows.

- **Media mount:** `/zfs-pve-1/media` → `/media`
- **GPU passthrough:** Intel iGPU (`/dev/dri/card0`, `/dev/dri/renderD128`) for hardware-accelerated transcoding
- **TUN device:** `/dev/net/tun` passed through for Tailscale
- **Port:** `8096` (HTTP)

#### Transmission (CT 102)

Lean BitTorrent-only container (the *arr suite was removed in v2).

| Service          | Port  | Purpose                                         |
|------------------|-------|--------------------------------------------------|
| **Transmission** | 9091  | BitTorrent client for downloading media          |

- **Media mount:** `/zfs-pve-1/media` → `/data`
- **TUN device:** `/dev/net/tun` passed through for Tailscale
- All services run as `mediauser:mediagroup` (UID/GID 1000, mapped to host 101000)

### DNS / Ad Blocking (pve1)

| VMID | Name     | Type | OS     | Cores | RAM     | Root Disk | Start on Boot |
|------|----------|------|--------|-------|---------|-----------|---------------|
| 100  | adguard  | LXC  | Ubuntu | 1     | 512 MB  | 10 GB     | Yes           |

**AdGuard Home** — Provides DNS-level ad and tracker blocking for the entire network. Relocated from pve2 → pve1 in v2 so pve2 can be a dedicated Immich host. A DHCP reservation is recommended to keep the AdGuard IP stable across reboots; update your router/DHCP server to advertise AdGuard's pve1 IP as the LAN DNS.

- **Storage:** Root disk on `local-lvm` (NVMe on pve1)
- **Network:** DHCP on `vmbr0`
- **Port:** `3000` (web UI)

### Photos / Immich (pve2)

| VMID | Name    | Type | OS     | Cores | RAM    | Root Disk | Start on Boot |
|------|---------|------|--------|-------|--------|-----------|---------------|
| 103  | immich  | LXC  | Ubuntu | 4     | 4 GiB  | 20 GB     | Yes           |

**Immich** — self-hosted photos backup (Google Photos alternative). Runs as a Docker Compose stack (server, machine-learning, Redis, PostgreSQL with pgvector) inside an unprivileged LXC, using the `fuse-overlayfs` Docker storage driver.

- **Storage:** Root disk on `zfs-pve-2` (HDD). Photo library + Postgres state live on the bind-mounted `/zfs-pve-2/immich` (100 GB ZFS reservation) → `/data`.
- **Network:** DHCP on `vmbr0`, plus Tailscale for remote access.
- **Port:** `2283` (web UI)

## Immich Backup

A nightly cron on **pve2 at 03:00 Asia/Kolkata (IST)** snapshots the Immich ZFS dataset and sends it incrementally to pve1:

1. `docker compose stop` inside CT 103 (~30s downtime)
2. `zfs snapshot zfs-pve-2/immich@backup-<timestamp>`
3. Restart Immich immediately
4. `zfs send -i <prev> <snap> | ssh pve1 "zfs receive zfs-pve-1/immich-backup"` (first run is a full send)
5. Prune to the 7 most recent snapshots on both sides

The cron uses `CRON_TZ=Asia/Kolkata` so the schedule is locale-explicit without changing the Proxmox host's system timezone. Logs land in `/var/log/immich-backup.log` (rotated weekly, 8 weeks kept).

### Manual trigger

```bash
ssh root@<pve2-tailscale-ip> /usr/local/bin/immich-backup.sh
```

### Restore (pve1 → pve2)

On pve2:

```bash
ssh pve1 "zfs send zfs-pve-1/immich-backup@<snap>" | zfs receive zfs-pve-2/immich-restore
# then: rename or re-mount immich-restore in place of immich, and restart the compose stack.
```

## Network

### Subnet

| Property       | Value            |
|----------------|------------------|
| Subnet         | 192.168.1.0/24   |
| Gateway        | 192.168.1.1      |

### Node Addresses

| Node   | IP Address     | Bridge | Physical NIC |
|--------|----------------|--------|--------------|
| pve1   | 192.168.1.36   | vmbr0  | enp1s0       |
| pve2   | 192.168.1.41   | vmbr0  | enp1s0       |

Both nodes use a Linux bridge (`vmbr0`) with STP disabled. Containers obtain IPs via DHCP on the same bridge.

### Tailscale (Remote Access)

All nodes and containers are connected via [Tailscale](https://tailscale.com) mesh VPN, enabling SSH access from anywhere without exposing ports to the public internet.

| Tailscale Node     | Tailscale IP              | Runs On         |
|--------------------|---------------------------|-----------------|
| pve1               | `100.68.132.46`           | pve1 (host)     |
| pve2               | `100.114.157.124`         | pve2 (host)     |
| jellyfin-1         | `100.100.253.127`         | CT 101          |
| transmission-1     | `100.125.84.44`           | CT 102          |
| immich-1           | `<IMMICH_TAILSCALE_IP>`   | CT 103 (fill in after first deploy) |

> Tailscale IPs are in the 100.64.0.0/10 CGNAT range and are only reachable from inside this tailnet — not from the public internet. Container IPs are assigned on first `tailscale up` and stable thereafter.

MagicDNS is enabled, so nodes are reachable by hostname:

```bash
ssh root@pve1    # access pve1 from anywhere on the tailnet
ssh root@pve2    # access pve2 from anywhere on the tailnet
```

## Repository Structure

```
homelab/
├── .github/workflows/             # CI/CD pipelines
│   ├── plan.yml                   # PR: OpenTofu plan + Ansible lint
│   └── deploy.yml                 # Main: full 3-phase deploy
│
├── terraform/                     # Infrastructure provisioning (Proxmox LXC containers)
│   ├── main.tf                    # Provider config (bpg/proxmox)
│   ├── variables.tf               # Variable declarations
│   ├── outputs.tf                 # Container IDs and hostnames
│   ├── jellyfin.tf                # CT 101 definition
│   ├── transmission.tf            # CT 102 definition
│   ├── adguard.tf                 # CT 100 definition (pve1)
│   ├── immich.tf                  # CT 103 definition (pve2)
│   ├── terraform.tfvars.example   # Example variables (copy to terraform.tfvars)
│   └── modules/lxc-container/     # Reusable LXC container module
│
├── ansible/                       # Configuration management (software inside containers)
│   ├── ansible.cfg
│   ├── inventory/
│   │   ├── hosts.yml              # Static inventory (PVE hosts + containers)
│   │   └── group_vars/            # Per-group variables
│   ├── playbooks/
│   │   ├── site.yml               # Master playbook (all containers)
│   │   ├── host-setup.yml         # ZFS datasets, subuid/subgid on PVE hosts
│   │   ├── jellyfin.yml           # Jellyfin container config
│   │   ├── transmission.yml       # Transmission container config
│   │   ├── adguard.yml            # AdGuard container config
│   │   ├── adguard-migrate.yml    # One-shot: export AdGuard config before pve2→pve1 move
│   │   ├── immich.yml             # Immich container config
│   │   ├── immich-backup.yml      # Install nightly backup cron on pve2
│   │   └── pve-cross-ssh.yml      # One-shot: pve2→pve1 SSH key for zfs-send
│   ├── roles/                     # common, jellyfin, transmission, adguard, tailscale, zfs-media, zfs-immich, immich, immich-backup
│   ├── vault.yml.example          # Example secrets (copy and encrypt with ansible-vault)
│   └── vault.yml                  # Encrypted secrets (gitignored)
│
├── scripts/
│   └── deploy.sh                  # Full deploy: host-setup → tofu apply → ansible site.yml
│
├── jellyfin.sh                    # Legacy bash setup script (reference only)
└── architecture.drawio            # Architecture diagram
```

## CI/CD

Deployments are automated via GitHub Actions. OpenTofu state is stored in the `tf-state` branch of this repo using [terraform-backend-git](https://github.com/plumber-cd/terraform-backend-git).

### Pipelines

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| **Plan** (`plan.yml`) | Pull request to `main` | Runs `tofu plan` and posts the output as a PR comment. Runs Ansible lint. |
| **Deploy** (`deploy.yml`) | Manual (`workflow_dispatch`) | Connects to Tailscale, then runs the full 3-phase deploy: host-setup → tofu apply → site.yml. |

### GitHub Setup

#### Repository Variables (Settings → Secrets and variables → Actions → Variables)

| Variable | Value |
|----------|-------|
| `PVE1_HOST` | Tailscale IP of pve1 |
| `PVE2_HOST` | Tailscale IP of pve2 |

#### Repository Secrets (Settings → Secrets and variables → Actions → Secrets)

| Secret | Description |
|--------|-------------|
| `PROXMOX_ENDPOINT` | Proxmox API URL (e.g. `https://192.168.1.36:8006`) |
| `PROXMOX_API_TOKEN` | Proxmox API token |
| `CONTAINER_PASSWORD` | Root password for LXC containers |
| `TS_OAUTH_CLIENT_ID` | Tailscale OAuth client ID |
| `TS_OAUTH_SECRET` | Tailscale OAuth secret |
| `TS_AUTH_KEY` | Tailscale auth key for container enrollment |
| `SSH_PRIVATE_KEY` | SSH private key for Proxmox hosts |
| `TRANSMISSION_USER` | Transmission RPC username |
| `TRANSMISSION_PASS` | Transmission RPC password |
| `IMMICH_DB_PASSWORD` | Password for Immich's internal PostgreSQL (alphanumeric only, long random string) |
| `IMMICH_USER` | Admin email used to sign into Immich (e.g. `you@example.com`) |
| `IMMICH_PASS` | Admin password for the Immich web UI |

> `GITHUB_TOKEN` is provided automatically by GitHub Actions and is used by terraform-backend-git to read/write state.

#### Tailscale OAuth

1. Go to Tailscale admin console → Settings → OAuth clients
2. Create an OAuth client with the `tag:ci` tag
3. In your Tailscale ACL policy, add `"tag:ci": ["autogroup:admin"]` to `tagOwners`

#### Production Environment (optional)

Create a `production` environment (Settings → Environments) to add a manual approval gate before deploys.

#### State Branch

The `tf-state` branch is created automatically on the first deploy. It stores the OpenTofu state file and uses git branches for state locking.

#### Running a deploy

1. Go to **Actions → Deploy → Run workflow** on GitHub.
2. Enter the Tailscale IPs: `pve1_host=100.68.132.46`, `pve2_host=100.114.157.124`.
3. (If `production` environment gate is configured) Approve the run.
4. Watch logs. Expected phases: host-setup → cross-ssh → tofu init → tofu apply → site.yml.

#### One-time v2 migration (run locally BEFORE the first GitHub Actions deploy of this branch)

This branch renames CT 102 in state and destroys/recreates CT 100 (AdGuard). The automated workflow doesn't know about either, so do these **once**, locally, before triggering `deploy.yml`:

```bash
# 1. Export AdGuard config from the live pve2 CT 100 (produces backups/adguard-config/AdGuardHome.yaml)
cd ansible && ansible-playbook -i inventory/hosts.yml playbooks/adguard-migrate.yml && cd ..

# 2. Rename module.mediastack -> module.transmission in the tf-state branch
GITHUB_TOKEN=<token> ./scripts/migrate-state.sh
```

Then trigger the GitHub Actions deploy as above. On subsequent deploys, skip the migration step — the workflow handles the normal flow.

## Local Deployment

### Prerequisites

- [OpenTofu](https://opentofu.org/) >= 1.6.0
- [Ansible](https://docs.ansible.com/) with `community.proxmox` and `community.general` collections
- SSH key access to both PVE hosts (via Tailscale)
- A Proxmox API token (Datacenter → Permissions → API Tokens)

### Setup

```bash
# 1. Configure OpenTofu variables
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
# Edit terraform.tfvars with your API token and passwords

# 2. Configure Ansible secrets
cp ansible/vault.yml.example ansible/vault.yml
ansible-vault encrypt ansible/vault.yml
# Enter a vault password, then edit with: ansible-vault edit ansible/vault.yml

# 3. Deploy everything
./scripts/deploy.sh
```

The deploy script runs three phases:
1. **Host setup** (Ansible) — ZFS datasets, permissions, LXC template download
2. **Infrastructure** (OpenTofu) — creates containers with LXC config (idmap, cgroup, device passthrough)
3. **Configuration** (Ansible) — installs and configures all software inside containers

All phases are idempotent and safe to re-run.

## Architecture

See [architecture.drawio](architecture.drawio) for the full diagram (open with [draw.io](https://app.diagrams.net) or the VS Code draw.io extension).

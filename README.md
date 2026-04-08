# Homelab

My playground for my homelab setup, running on a two-node Proxmox VE cluster.

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

The ZFS pool on pve1 (`zfs-pve-1`) hosts a shared `/zfs-pve-1/media` dataset that is bind-mounted into both the Jellyfin and Mediastack containers, allowing them to share the same media library.

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

| VMID | Name        | Type | OS     | Cores | RAM    | Root Disk | Swap   | Start on Boot |
|------|-------------|------|--------|-------|--------|-----------|--------|---------------|
| 101  | jellyfin    | LXC  | Ubuntu | 2     | 2 GiB  | 10 GB     | 512 MB | Yes           |
| 102  | mediastack  | LXC  | Ubuntu | 2     | 4 GiB  | 15 GB     | 512 MB | Yes           |

Both containers are unprivileged with nesting enabled, use DHCP for networking on `vmbr0`, and resolve DNS via `1.1.1.1` and `8.8.8.8`.

#### Jellyfin (CT 101)

Self-hosted media server for streaming movies and TV shows. HTTPS port configured as `8920`.

- **Media mount:** `/zfs-pve-1/media` → `/media`
- **GPU passthrough:** Intel iGPU (`/dev/dri/card0`, `/dev/dri/renderD128`) for hardware-accelerated transcoding
- **TUN device:** `/dev/net/tun` passed through

#### Mediastack (CT 102)

Bundles the *arr suite and Transmission into a single container:

| Service          | Purpose                                         |
|------------------|--------------------------------------------------|
| **Transmission** | BitTorrent client for downloading media          |
| **Prowlarr**     | Indexer manager integrating with Sonarr & Radarr |
| **Sonarr**       | Automated TV show management and downloading     |
| **Radarr**       | Automated movie management and downloading       |

- **Media mount:** `/zfs-pve-1/media` → `/data`
- **TUN device:** `/dev/net/tun` passed through (VPN support)

### DNS / Ad Blocking (pve2)

| VMID | Name     | Type | OS     | Cores | RAM     | Root Disk | Swap   | Start on Boot |
|------|----------|------|--------|-------|---------|-----------|--------|---------------|
| 100  | adguard  | LXC  | Debian | 1     | 512 MB  | 2 GB      | 512 MB | Yes           |

**AdGuard Home** — Provides DNS-level ad and tracker blocking for the entire network. Deployed via [Proxmox VE community scripts](https://github.com/community-scripts/ProxmoxVE).

- **Storage:** Root disk on `zfs-pve-2`
- **Network:** DHCP (IPv4) + auto (IPv6) on `vmbr0`
- **Tags:** `adblock`, `community-script`

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

A `localnetwork` SDN is configured on each node.

### Tailscale (Remote Access)

All nodes and containers are connected via [Tailscale](https://tailscale.com) mesh VPN, enabling SSH access from anywhere without exposing ports to the public internet.

| Tailscale Node     | Tailscale IP     | Runs On         |
|--------------------|------------------|-----------------|
| pve1               | 100.68.132.46    | pve1 (host)     |
| pve2               | 100.114.157.124  | pve2 (host)     |
| jellyfin-1         | 100.119.254.40   | CT 101          |
| mediastack-1       | 100.118.179.58   | CT 102          |
| adguard            | —                | CT 100 (not on tailnet) |

MagicDNS is enabled, so nodes are reachable by hostname:

```bash
ssh root@pve1    # access pve1 from anywhere on the tailnet
ssh root@pve2    # access pve2 from anywhere on the tailnet
```

## Architecture

See [architecture.drawio](architecture.drawio) for the full diagram (open with [draw.io](https://app.diagrams.net) or the VS Code draw.io extension).

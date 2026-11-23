# Resource allocation and observed use

[Documentation home](README.md) · [Architecture](architecture.md) · [Raw snapshot](snapshots/2026-11-22-resources.json)

## Hardware and configured allocation

The Alienware has an Intel i7-8750H with **6 physical cores / 12 logical CPUs**, 16 GB nominal installed RAM, and **14.91 GiB** reported usable RAM. The host has **4.00 GiB** swap.

**None of the ten containers is assigned dedicated cores or a hard CPU/memory cap.** Every runtime cgroup showed effective CPUs `0-11`, `cpu.max` equal to `max 100000` (no quota), `memory.max` equal to `max`, and a runtime PID/task ceiling of **18,242 per container** (`pids.max=18242`). Compose itself does not set `pids_limit`; the runtime ceiling was observed directly, and its origin was not audited. The [Compose source](../../ansible/roles/media_server/templates/compose.yml.j2) defines no `cpus`, CPU pinning, memory limit, resource reservation or GPU reservation. Shared availability is not reserved capacity; ten containers do not each own twelve CPUs or the full host RAM.

## Measurement window and interpretation

Sample start: **22 November 2026, 03:12:49 IST**. The collector sampled for **30.00 seconds**, taking **7 readings** at roughly five-second intervals. This was a short sample of the running stack after torrent downloads had started; it was not a stress test, playback benchmark or idle baseline.

The [collector](../../scripts/collect-media-resources.py) reads cgroup-v2 counters without sudo or Docker-socket access. It identifies app processes internally but does not emit process arguments, environment variables or credentials. The snapshot contains counters/limits, host capacity and directory sizes only.

- Average logical CPUs = change in cgroup CPU microseconds / elapsed microseconds. `1.0` means one logical CPU busy throughout the window; it does not mean one physical core was reserved. Multiply by 100 to compare with the usual one-CPU percentage convention.
- “Max interval” is the busiest approximately five-second interval in this sample, not an instantaneous or lifetime peak.
- Working memory is an **estimate**: `memory.current - memory.stat[inactive_file]`, clamped at zero. It excludes inactive file cache in the same style as Docker’s Linux CLI display. It is not process RSS. Raw charged memory includes additional cache/kernel charges and can be much larger during downloads.
- Config disk size is `du -s -B1` allocated bytes under each app’s config directory. It excludes shared media/downloads, images, writable container layers, Docker logs and Jellyfin’s separate cache.
- Block I/O reflects cgroup `io.stat` counter deltas. Buffered writes and cache can separate network download timing from physical write timing. It is not network bandwidth.

## Per-app measurements

| App | Avg logical CPUs | Max interval CPUs | Working RAM at end (MiB) | Max sampled working RAM (MiB) | Raw charged RAM at end (MiB) | Config disk (MiB) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| [Homarr](apps/homarr.md) | 0.0187 | 0.0857 | 282.7 | 282.7 | 290.0 | 7.62 |
| [Jellyfin](apps/jellyfin.md) | 0.0087 | 0.0503 | 226.5 | 228.2 | 230.6 | 4.79 |
| [Seerr](apps/seerr.md) | 0.0324 | 0.1798 | 197.5 | 198.3 | 201.5 | 4.57 |
| [Sonarr](apps/sonarr.md) | 0.0136 | 0.0628 | 157.4 | 157.9 | 162.5 | 6.00 |
| [Radarr](apps/radarr.md) | 0.0182 | 0.0923 | 151.2 | 156.5 | 152.3 | 2.06 |
| [Lidarr](apps/lidarr.md) | 0.0025 | 0.0063 | 137.4 | 137.4 | 139.0 | 2.18 |
| [Prowlarr](apps/prowlarr.md) | 0.0019 | 0.0054 | 154.0 | 154.0 | 159.5 | 5.61 |
| [Bazarr](apps/bazarr.md) | 0.0029 | 0.0045 | 174.0 | 175.2 | 174.9 | 0.92 |
| [qBittorrent](apps/qbittorrent.md) | 0.0721 | 0.0880 | 89.6 | 89.6 | 1238.4 | 8.37 |
| [SABnzbd](apps/sabnzbd.md) | 0.0004 | 0.0005 | 71.1 | 71.1 | 71.5 | 0.12 |

Combined app average: **0.1715 logical CPUs**, or **1.43% of twelve-CPU capacity**. Combined end-of-window working-memory estimate: **1.60 GiB**. These sums cover the sampled containers; Docker, containerd, the kernel and other host processes are outside them.

## Host totals

| Metric | Observed value |
| --- | ---: |
| Host CPU busy during the window | 2.43% across all 12 logical CPUs |
| Host CPU I/O wait | 0.24% |
| Host load average, 1 / 5 / 15 minutes | 0.28 / 0.25 / 0.27 |
| Host RAM used estimate, total minus available | 2.80 GiB |
| Host RAM available | 12.11 GiB |
| Swap in use | 0.00 GiB |
| Jellyfin cache allocated disk | 2.28 MiB |

Host RAM “available” includes reclaimable memory; Linux can use otherwise free RAM for file cache. It is more useful for headroom than the strictly free column. Host/container memory columns use different accounting and should not be treated as a reconciliation ledger.

## Physical disk occupancy

| Mount | Total filesystem (GiB) | Used (GiB) | Available (GiB) | Main use |
| --- | ---: | ---: | ---: | --- |
| `/` | 115.78 | 15.829 | 94.02 | Ubuntu, images, app state, cache |
| `/srv/media` | 915.82 | 1.123 | 914.68 | Media and downloads |
| `/srv/ssd` | 457.38 | 0.002 | 457.36 | Reserved empty; ext4 metadata only |

GiB uses 2^30 bytes; marketed disk capacities use decimal GB/TB. Used plus available can be below total because of filesystem metadata/reserved space. Torrent files can be sparse or partially allocated: directory/file logical sizes, expected download size and physical occupancy are different measurements. Downloads were still running; these values are not expected final media sizes.

## Per-app I/O and tasks

| App | Block read (KiB/s) | Block write (KiB/s) | Cgroup tasks at end | Swap at end (MiB) |
| --- | ---: | ---: | ---: | ---: |
| Homarr | 0.00 | 21.73 | 20 | 0.00 |
| Jellyfin | 0.00 | 0.00 | 18 | 0.00 |
| Seerr | 0.00 | 4.40 | 23 | 0.00 |
| Sonarr | 0.00 | 2.13 | 36 | 0.00 |
| Radarr | 0.00 | 4.53 | 24 | 0.00 |
| Lidarr | 0.00 | 1.33 | 24 | 0.00 |
| Prowlarr | 0.00 | 1.20 | 24 | 0.00 |
| Bazarr | 0.00 | 0.00 | 132 | 0.00 |
| qBittorrent | 0.00 | 3204.90 | 20 | 0.00 |
| SABnzbd | 0.00 | 0.00 | 32 | 0.00 |

Cgroup task counts include threads, not just application processes. Host network throughput, per-container network rates, GPU utilization, temperatures, power draw and storage latency were not measured. The presence of an Intel device and a passed encoder test is not a measurement of GPU load or maximum stream capacity.

## Repeat the measurement

From the repository root:

```bash
scp scripts/collect-media-resources.py alienware:/tmp/collect-media-resources.py
ssh alienware 'python3 /tmp/collect-media-resources.py --duration 30 --interval 5' \
  > /tmp/alienware-resources.json
```

The script requires the ten media containers and additionally recognizes the optional Uptime Kuma and Hermes containers. It fails on unidentified/missing containers rather than inventing labels. Hermes directory size covers its persistent data, excluding its image; Kuma directory size covers its persistent data. The original table above predates these two additions. If service process paths change in a future image, review the identification rules. Use `--allow-missing qbittorrent` to acknowledge the intentionally stopped downloader in a new sample; the omission is recorded explicitly in JSON. A restarted container during sampling can invalidate a window; rerun after the stack is stable. Run longer windows under a representative workload before choosing caps or sizing hardware. The command only collects readings; it does not change limits or restart services.

For Docker’s own view, run `ssh -t alienware 'sudo docker stats --no-stream'`. Runtime limits can also be inspected through Docker with sudo; the collector directly records the kernel-enforced cgroup values.

## Monitoring and Hermes deployment sample

A separate [raw snapshot](snapshots/2026-11-22-server-apps-resources.json) started at **22 November 2026, 21:42:44 IST**, with seven readings over 30 seconds. This is an initial post-deployment sample before ChatGPT/Codex sign-in and before enabling the Hermes Webapp, with monitor polling and no model inference. The server-apps playbook was also reapplied during this window and made zero changes. qBittorrent was intentionally stopped at the user's request; it is explicitly omitted in the snapshot. The original ten-app report above remains historical.

| Added app | Avg logical CPUs | Share of 12-CPU capacity | Working RAM at end (MiB) | Persistent data (MiB) |
| --- | ---: | ---: | ---: | ---: |
| Uptime Kuma | 0.0212 | 0.177% | 119.8 | 2.66 |
| Hermes Agent | 0.0199 | 0.166% | 264.6 | 16.16 |

Both containers reported CPUs `0-11`, unlimited CPU quota (`max 100000`) and memory (`max`), and `pids.max=18242`. No dedicated cores or GPU are assigned. Data size excludes Docker images, writable image layers and container logs. Host RAM available was **11.47 GiB**; the extra SSD remained at **2.03 MiB** used for filesystem metadata. These readings do not measure Hermes model inference, sustained load or maximum capacity.

## References

- [Docker runtime metrics](https://docs.docker.com/engine/containers/runmetrics/)
- [Docker CPU and memory constraints](https://docs.docker.com/engine/containers/resource_constraints/)
- [Linux cgroup v2 interface](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)

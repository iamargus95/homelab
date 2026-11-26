# qBittorrent

[Documentation home](../README.md) · [Setup](../setup.md) · [Resources](../resources.md)

Torrent data transfer for Sonarr, Radarr and Lidarr.

## Service configuration

| Setting | Value |
| --- | --- |
| Compose service | `qbittorrent` |
| Image in source | `lscr.io/linuxserver/qbittorrent:latest` |
| Browser URL | [http://192.168.1.243:8080](http://192.168.1.243:8080) |
| Container web port | `8080` |
| Persistent state | `/opt/media-stack/config/qbittorrent:/config` |
| Restart policy | `unless-stopped` |
| Docker logs | JSON, `10m` per file, three files |

Use `admin` and the `qbittorrent` password entry. Local/subnet authentication bypass was disabled and CSRF checks remain enabled.

## How it was set up

The bootstrap logs in with the container’s temporary first-run password, replaces it with a strong generated password, sets the default path `/data/downloads/torrents`, enables the incomplete path `/data/downloads/torrents/incomplete`, disables UPnP, excludes slow torrents from active-slot limits, and creates `movies`, `tv` and `music` categories with suggested subdirectories.

During the verified show download, torrents in category `tv` reported `/data/downloads/torrents` as their save path. The prepared category folders are not proof of a torrent’s effective location; inspect each torrent and automatic-management preferences. The observed path is still HDD-backed.

The owning service definition is in [`compose.yml.j2`](../../../ansible/roles/media_server/templates/compose.yml.j2); common deployment steps are in [`tasks/main.yml`](../../../ansible/roles/media_server/tasks/main.yml). See [Setup](../setup.md) for first-run script ownership and settings that require appdata restoration/manual follow-up.

## Connections and paths

`/srv/media:/data` supplies the HDD. Sonarr/Radarr/Lidarr reach `qbittorrent:8080` inside Compose. WebUI port 8080 is published to the LAN. Peer port 6881 is configured inside the image but is not published by Compose. No VPN routing was configured.

## Normal use

qBittorrent's global share ratio is **0** with the **Stop** action. Sonarr, Radarr, and Lidarr have Completed Download Handling and Remove Completed enabled, so they can remove managed torrents after a successful import. The global stop applies to downloads using the default share limits. A manual torrent outside an ARR-managed category will stop at completion and needs to be removed separately.

Watch Progress, State, Seeds/Peers and transfer speed. The first repaired request queued 13 torrents covering 40 Sonarr episode rows; three transfers were active and the others queued. This was a snapshot, not a configured concurrency guarantee or final completion report.

## Troubleshooting and limitations

Queued is different from stalled or metadata-fetching. Check active limits, peers and actual received bytes before assuming a failure. If a completed torrent remains in qBittorrent, check its ARR import status before touching the download files. Large memory.current readings can include downloaded-file cache; see the working-estimate column in Resources.

```bash
ssh -t alienware 'sudo docker compose -f /opt/media-stack/compose.yml logs --tail 100 qbittorrent'
```

## Download recovery on 22 November 2026

The service is running. Two metadata-only jobs with no reachable peers had occupied two of its three download slots. Enabled `dont_count_slow_torrents=true` while retaining the existing active limits, speed limits, DHT/PeX and slow thresholds. Season 3 and season 4 of the requested show then connected to seeds and began transferring; the movie also had reachable seeds and was left in place. Queued transfers with available sources follow the normal slot limits.

Stalled season 2 sources were replaced only after validating alternative metadata and actual received bytes. Existing imported episodes and the original partial payload were kept. See [operations](../operations.md#stalled-torrent-diagnosis) and the [change record](../changes.md) for the final selected sources and measurements.

The earlier “credentials rejected” diagnosis was incorrect: this v5.3.0 server uses HTTP `204` on successful login. Its saved credentials work. Cookie/session readback plus an authenticated API request is the correct verification.

## CPU, memory and disk use

No dedicated physical cores, CPU quota or per-container RAM cap is configured. This app shares all 12 logical CPUs and available host memory. Runtime cgroups confirmed `cpu.max=max 100000`, `memory.max=max` and effective CPU set `0-11`.

The snapshot beginning **2026-11-22 03:12:49 IST** measured an average **0.0721 logical CPUs** and **89.6 MiB** working-memory estimate at the end. App configuration occupies **8.37 MiB** allocated disk space, excluding images, media, Docker logs and separate cache.

These are observations during one 30-second window, not reservations or sizing requirements. Workload, file cache, scanning, unpacking, imports and transcoding can change them. See [Resources](../resources.md) for raw charged memory, sampled peaks, I/O, host totals and methodology.

## Upstream documentation

[qBittorrent documentation](https://docs.linuxserver.io/images/docker-qbittorrent/)

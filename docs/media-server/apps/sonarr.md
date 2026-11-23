# Sonarr

[Documentation home](../README.md) · [Setup](../setup.md) · [Resources](../resources.md)

TV series monitoring, release searches, download coordination and completed-file imports.

## Service configuration

| Setting | Value |
| --- | --- |
| Compose service | `sonarr` |
| Image in source | `lscr.io/linuxserver/sonarr:latest` |
| Browser URL | [http://192.168.1.243:8989](http://192.168.1.243:8989) |
| Container web port | `8989` |
| Persistent state | `/opt/media-stack/config/sonarr:/config` |
| Restart policy | `unless-stopped` |
| Docker logs | JSON, `10m` per file, three files |

Forms authentication is enabled. Use `admin` and the `sonarr` password entry.

## How it was set up

The first-run script creates `/data/library/tv`, registers qBittorrent at `qbittorrent:8080` with category `tv`, enables hardlink imports, and sets forms authentication. Prowlarr registers the Sonarr application with `fullSync` and stores its API key privately.

After public indexers were enabled, Knaben appeared as `Knaben (Prowlarr)` with RSS, automatic search and interactive search enabled. The first show’s existing series used quality profile ID 4; it was not overwritten when the stalled search was retried.

The owning service definition is in [`compose.yml.j2`](../../../ansible/roles/media_server/templates/compose.yml.j2); common deployment steps are in [`tasks/main.yml`](../../../ansible/roles/media_server/tasks/main.yml). See [Setup](../setup.md) for first-run script ownership and settings that require appdata restoration/manual follow-up.

## Connections and paths

`/srv/media:/data` gives Sonarr one common HDD filesystem for `/data/downloads/torrents` and `/data/library/tv`. It receives requests from Seerr, indexers from Prowlarr and reports from qBittorrent. Bazarr reads its series metadata/API.

## Normal use

Review monitored seasons/episodes and the quality profile on the series page. Activity shows pending imports and download progress; History records successful grabs/imports. Trigger a monitored-series or season search when fixing an old request that had no indexers.

## Troubleshooting and limitations

“No indexers” is configured in Prowlarr, not solved by changing a library path. Check rejected releases and quality requirements if a search finds results but grabs nothing. A single season-pack torrent may produce ten episode queue rows; episode-row count is not torrent count. Check import warnings after a transfer finishes.

```bash
ssh -t alienware 'sudo docker compose -f /opt/media-stack/compose.yml logs --tail 100 sonarr'
```

## CPU, memory and disk use

No dedicated physical cores, CPU quota or per-container RAM cap is configured. This app shares all 12 logical CPUs and available host memory. Runtime cgroups confirmed `cpu.max=max 100000`, `memory.max=max` and effective CPU set `0-11`.

The snapshot beginning **2026-11-22 03:12:49 IST** measured an average **0.0136 logical CPUs** and **157.4 MiB** working-memory estimate at the end. App configuration occupies **6.00 MiB** allocated disk space, excluding images, media, Docker logs and separate cache.

These are observations during one 30-second window, not reservations or sizing requirements. Workload, file cache, scanning, unpacking, imports and transcoding can change them. See [Resources](../resources.md) for raw charged memory, sampled peaks, I/O, host totals and methodology.

## Upstream documentation

[Sonarr documentation](https://docs.linuxserver.io/images/docker-sonarr/)


## Jellyfin import notification

The connection `Jellyfin library update` uses the built-in Emby / Jellyfin provider, host `jellyfin`, port `8096`, and a dedicated Jellyfin API key stored privately in Sonarr. Import, upgrade and rename events are enabled; Emby-only user notifications are disabled. Library updates map `/data/library/tv` to `/media/tv`, because the two containers expose the same HDD library at different paths. The connection test passed when added. This complements Jellyfin's real-time watcher and scheduled scans.

# Radarr

[Documentation home](../README.md) · [Setup](../setup.md) · [Resources](../resources.md)

Movie monitoring, release searches, download coordination and completed-file imports.

## Service configuration

| Setting | Value |
| --- | --- |
| Compose service | `radarr` |
| Image in source | `lscr.io/linuxserver/radarr:latest` |
| Browser URL | [http://192.168.1.243:7878](http://192.168.1.243:7878) |
| Container web port | `7878` |
| Persistent state | `/opt/media-stack/config/radarr:/config` |
| Restart policy | `unless-stopped` |
| Docker logs | JSON, `10m` per file, three files |

Forms authentication is enabled. Use `admin` and the `radarr` password entry.

## How it was set up

The bootstrap creates `/data/library/movies`, connects qBittorrent with category `movies`, enables hardlink imports and protects the UI with forms authentication. Seerr is configured to send movie requests to this server and root folder.

Prowlarr’s `fullSync` application connection exported Knaben and YTS to Radarr after their public-indexer tests passed.

The owning service definition is in [`compose.yml.j2`](../../../ansible/roles/media_server/templates/compose.yml.j2); common deployment steps are in [`tasks/main.yml`](../../../ansible/roles/media_server/tasks/main.yml). See [Setup](../setup.md) for first-run script ownership and settings that require appdata restoration/manual follow-up.

## Connections and paths

`/srv/media:/data` supplies both downloads and the movie library on the HDD. Seerr creates requests, Prowlarr supplies compatible sources, qBittorrent transfers files and Bazarr reads movie metadata.

## Normal use

Review the movie’s quality profile and minimum availability, then use Search or Interactive Search. Watch Activity for transfer and import status. Jellyfin reads the final `/data/library/movies` directory through its separate read-only `/media/movies` mount.

## Troubleshooting and limitations

An approved Seerr request still needs a matching release, live indexer and working downloader. Review rejection reasons rather than loosening all quality settings. Check file permissions and the common `/data` path if a download completes but does not import.

```bash
ssh -t alienware 'sudo docker compose -f /opt/media-stack/compose.yml logs --tail 100 radarr'
```

## CPU, memory and disk use

No dedicated physical cores, CPU quota or per-container RAM cap is configured. This app shares all 12 logical CPUs and available host memory. Runtime cgroups confirmed `cpu.max=max 100000`, `memory.max=max` and effective CPU set `0-11`.

The snapshot beginning **2026-11-22 03:12:49 IST** measured an average **0.0182 logical CPUs** and **151.2 MiB** working-memory estimate at the end. App configuration occupies **2.06 MiB** allocated disk space, excluding images, media, Docker logs and separate cache.

These are observations during one 30-second window, not reservations or sizing requirements. Workload, file cache, scanning, unpacking, imports and transcoding can change them. See [Resources](../resources.md) for raw charged memory, sampled peaks, I/O, host totals and methodology.

## Upstream documentation

[Radarr documentation](https://docs.linuxserver.io/images/docker-radarr/)

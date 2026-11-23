# Lidarr

[Documentation home](../README.md) · [Setup](../setup.md) · [Resources](../resources.md)

Music artist/album monitoring, searches and imports into the HDD music library.

## Service configuration

| Setting | Value |
| --- | --- |
| Compose service | `lidarr` |
| Image in source | `lscr.io/linuxserver/lidarr:latest` |
| Browser URL | [http://192.168.1.243:8686](http://192.168.1.243:8686) |
| Container web port | `8686` |
| Persistent state | `/opt/media-stack/config/lidarr:/config` |
| Restart policy | `unless-stopped` |
| Docker logs | JSON, `10m` per file, three files |

Forms authentication is enabled. Use `admin` and the `lidarr` password entry.

## How it was set up

The bootstrap adds `/data/library/music` as a root using the first available quality/metadata profiles, connects qBittorrent with category `music`, enables hardlink imports and configures authentication. Prowlarr’s Lidarr application uses `fullSync`; Knaben was exported as a compatible source.

The owning service definition is in [`compose.yml.j2`](../../../ansible/roles/media_server/templates/compose.yml.j2); common deployment steps are in [`tasks/main.yml`](../../../ansible/roles/media_server/tasks/main.yml). See [Setup](../setup.md) for first-run script ownership and settings that require appdata restoration/manual follow-up.

## Connections and paths

`/srv/media:/data` shares the HDD downloads and music root. Prowlarr supplies indexers and qBittorrent downloads. Jellyfin reads imported music at `/media/music`. Seerr was configured for TV and movies, not music requests.

## Normal use

Add artists/albums directly in Lidarr and choose appropriate quality, metadata and monitoring settings. Confirm the music root and run a search for the intended albums.

## Troubleshooting and limitations

An artist does not necessarily imply every album is monitored. Verify monitored releases, supported indexer categories and quality/metadata filters. A provider that works in Prowlarr may not advertise compatible music categories. No completed music acquisition/import test was established.

```bash
ssh -t alienware 'sudo docker compose -f /opt/media-stack/compose.yml logs --tail 100 lidarr'
```

## CPU, memory and disk use

No dedicated physical cores, CPU quota or per-container RAM cap is configured. This app shares all 12 logical CPUs and available host memory. Runtime cgroups confirmed `cpu.max=max 100000`, `memory.max=max` and effective CPU set `0-11`.

The snapshot beginning **2026-11-22 03:12:49 IST** measured an average **0.0025 logical CPUs** and **137.4 MiB** working-memory estimate at the end. App configuration occupies **2.18 MiB** allocated disk space, excluding images, media, Docker logs and separate cache.

These are observations during one 30-second window, not reservations or sizing requirements. Workload, file cache, scanning, unpacking, imports and transcoding can change them. See [Resources](../resources.md) for raw charged memory, sampled peaks, I/O, host totals and methodology.

## Upstream documentation

[Lidarr documentation](https://docs.linuxserver.io/images/docker-lidarr/)

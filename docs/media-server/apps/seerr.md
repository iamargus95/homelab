# Seerr

[Documentation home](../README.md) · [Setup](../setup.md) · [Resources](../resources.md)

Request interface that forwards TV requests to Sonarr and movie requests to Radarr.

## Service configuration

| Setting | Value |
| --- | --- |
| Compose service | `seerr` |
| Image in source | `ghcr.io/seerr-team/seerr:latest` |
| Browser URL | [http://192.168.1.243:5055](http://192.168.1.243:5055) |
| Container web port | `5055` |
| Persistent state | `/opt/media-stack/config/seerr:/app/config` |
| Restart policy | `unless-stopped` |
| Docker logs | JSON, `10m` per file, three files |

Sign in with the Jellyfin `admin` account. Seerr has no separate generated password entry.

## How it was set up

The initial API setup authenticates against `http://jellyfin:8096`, creates the first Seerr administrator and service token, configures Sonarr/Radarr servers and library roots, synchronizes Jellyfin libraries and completes onboarding. Both servers are defaults for standard (non-4K) requests, with automatic search allowed (`preventSearch=false`).

The inspected Sonarr server default in Seerr was `Any`; an existing series can use a different quality profile. Review the request’s quality/season choices rather than assuming that the server default and every existing item’s profile match.

The owning service definition is in [`compose.yml.j2`](../../../ansible/roles/media_server/templates/compose.yml.j2); common deployment steps are in [`tasks/main.yml`](../../../ansible/roles/media_server/tasks/main.yml). See [Setup](../setup.md) for first-run script ownership and settings that require appdata restoration/manual follow-up.

## Connections and paths

Sonarr: `http://sonarr:8989`, root `/data/library/tv`. Radarr: `http://radarr:7878`, root `/data/library/movies`. Jellyfin: `http://jellyfin:8096`. Homarr shows requests through the saved Seerr integration.

## Normal use

Request the intended seasons or movie, check approval and Processing status, then follow Sonarr/Radarr Activity and qBittorrent. Seerr does not transfer torrent data itself.

## Troubleshooting and limitations

The first approved request was already in Sonarr, but its initial search predated configured indexers. Rerunning the existing-series search started transfers. Recreating the request was unnecessary. Check approval, downstream monitoring/quality, indexers, queue and history in that order.

```bash
ssh -t alienware 'sudo docker compose -f /opt/media-stack/compose.yml logs --tail 100 seerr'
```

## CPU, memory and disk use

No dedicated physical cores, CPU quota or per-container RAM cap is configured. This app shares all 12 logical CPUs and available host memory. Runtime cgroups confirmed `cpu.max=max 100000`, `memory.max=max` and effective CPU set `0-11`.

The snapshot beginning **2026-11-22 03:12:49 IST** measured an average **0.0324 logical CPUs** and **197.5 MiB** working-memory estimate at the end. App configuration occupies **4.57 MiB** allocated disk space, excluding images, media, Docker logs and separate cache.

These are observations during one 30-second window, not reservations or sizing requirements. Workload, file cache, scanning, unpacking, imports and transcoding can change them. See [Resources](../resources.md) for raw charged memory, sampled peaks, I/O, host totals and methodology.

## Upstream documentation

[Seerr documentation](https://docs.seerr.dev/getting-started/docker/)

# Jellyfin

[Documentation home](../README.md) · [Setup](../setup.md) · [Resources](../resources.md)

Playback server for imported Movies, TV Shows and Music libraries.

## Service configuration

| Setting | Value |
| --- | --- |
| Compose service | `jellyfin` |
| Image in source | `jellyfin/jellyfin:latest` |
| Browser URL | [http://192.168.1.243:8096](http://192.168.1.243:8096) |
| Public HTTPS hostname | [jellyfin.surajkamath.dev](https://jellyfin.surajkamath.dev), currently blocked (`403`) |
| Container web port | `8096` |
| Persistent state | `/opt/media-stack/config/jellyfin:/config` |
| Restart policy | `unless-stopped` |
| Docker logs | JSON, `10m` per file, three files |

Use `admin` and the `jellyfin` password entry. This account also signs in to Seerr.

## How it was set up

`bootstrap.py` completes Jellyfin’s first-run configuration, creates the administrator and adds Movies (`/media/movies`), TV Shows (`/media/tv`) and Music (`/media/music`) libraries with real-time monitoring. It disables automatic router port mapping and remote access in Jellyfin’s initial configuration. The bootstrap now requests an initial library scan after creating the libraries, so discovery is initialized after their creation.

Compose runs Jellyfin as UID/GID 1000, adds the Intel render-device group, and maps `/dev/dri/renderD128`. A synthetic H.264 hardware encode passed before VA-API encoding was enabled. Supported older Intel decode codecs were selected; AV1 hardware decoding was not enabled.

The owning service definition is in [`compose.yml.j2`](../../../ansible/roles/media_server/templates/compose.yml.j2); common deployment steps are in [`tasks/main.yml`](../../../ansible/roles/media_server/tasks/main.yml). See [Setup](../setup.md) for first-run script ownership and settings that require appdata restoration/manual follow-up.

## Connections and paths

`/srv/media/library:/media:ro` provides the HDD libraries. General cache stays on the boot SSD under `/opt/media-stack/cache/jellyfin`. A separate bind mount maps `/srv/ssd/jellyfin/transcodes` on the NVMe to `/cache/transcodes` for temporary streaming segments. Seerr and Homarr connect to Jellyfin. The NVIDIA GPU is not passed through.

**Throttle Transcodes** and **Delete segments** are enabled in Dashboard → Playback → Transcoding. The settings use Jellyfin's existing 180-second throttle delay and 720-second segment retention. [Jellyfin segment deletion](https://jellyfin.org/posts/jellyfin-release-10.9.0/)

## Normal use

Add `http://192.168.1.243:8096` as the server in a Jellyfin client. Completed downloads must first import into the library; unfinished qBittorrent files are not a Jellyfin library. Open Dashboard to review libraries, scan activity and playback/transcoding settings.

## Troubleshooting and limitations

An empty library can mean downloads are unfinished or Sonarr/Radarr imports have not completed. Check the HDD mount and library paths before rescanning. Read-only media access is intentional; cache/config are writable. Real client playback and simultaneous-stream capacity have not been validated.

```bash
ssh -t alienware 'sudo docker compose -f /opt/media-stack/compose.yml logs --tail 100 jellyfin'
```

## CPU, memory and disk use

No dedicated physical cores, CPU quota or per-container RAM cap is configured. This app shares all 12 logical CPUs and available host memory. Runtime cgroups confirmed `cpu.max=max 100000`, `memory.max=max` and effective CPU set `0-11`.

The snapshot beginning **2026-11-22 03:12:49 IST** measured an average **0.0087 logical CPUs** and **226.5 MiB** working-memory estimate at the end. App configuration occupies **4.79 MiB** allocated disk space, excluding images, media, Docker logs and separate cache.

These are observations during one 30-second window, not reservations or sizing requirements. Workload, file cache, scanning, unpacking, imports and transcoding can change them. See [Resources](../resources.md) for raw charged memory, sampled peaks, I/O, host totals and methodology.

## Upstream documentation

[Jellyfin documentation](https://jellyfin.org/docs/general/installation/container/)


## Imported episodes not appearing: resolved

On 22 November 2026, Sonarr had imported 14 episode files but Jellyfin had no indexed TV items. Its last completed scan predated the media. A manual library refresh completed and exposed all 14 episodes (season 1 episodes 1–10 and season 2 episodes 6–9). The Jellyfin log then confirmed `Watching directory "/media/tv"`; the missing watcher/discovery initialization was observed before that refresh. This was a Jellyfin discovery problem, not a failed Sonarr import or missing HDD files.

A tested Sonarr `Emby / Jellyfin` connection named `Jellyfin library update` now updates the library on import, upgrade and rename. It translates `/data/library/tv` to `/media/tv` and uses a dedicated server-side API key. The bootstrap includes both the initial scan and connection for fresh installations. Existing `.configured-secure` deployments skip the first-run script; this running host was corrected through the APIs. A future automatic import event has not yet been independently observed after adding the connection.


## Public access

Jellyfin DNS and the existing remotely managed `homelab` Cloudflare Tunnel were configured for [https://jellyfin.surajkamath.dev](https://jellyfin.surajkamath.dev). The route currently returns `403`: validation found direct video requests return media without authentication, so an access-mode decision is pending. Remote access and the known proxy remain configured on Jellyfin; LAN access is available. See [Public access](../public-access.md) for proxy settings, exact resources, validation and rollback. The other media-app web interfaces were not published by this change.

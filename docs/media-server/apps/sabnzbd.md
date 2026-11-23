# SABnzbd

[Documentation home](../README.md) · [Setup](../setup.md) · [Resources](../resources.md)

Prepared Usenet downloader; currently awaiting a Usenet service configuration.

## Service configuration

| Setting | Value |
| --- | --- |
| Compose service | `sabnzbd` |
| Image in source | `lscr.io/linuxserver/sabnzbd:latest` |
| Browser URL | [http://192.168.1.243:8081](http://192.168.1.243:8081) |
| Container web port | `8080` |
| Persistent state | `/opt/media-stack/config/sabnzbd:/config` |
| Restart policy | `unless-stopped` |
| Docker logs | JSON, `10m` per file, three files |

Use `admin` and the `sabnzbd` password entry. The web login flow was verified after configuration.

## How it was set up

The first-run script initializes persistent configuration, sets the administrator login, and selects `/data/downloads/usenet/incomplete` and `/data/downloads/usenet/complete` on the HDD. Its allowed hostnames include `sabnzbd`, `alienware` and the current LAN IP.

No Usenet server/account was supplied, and SABnzbd was not added as an active download client in Sonarr/Radarr/Lidarr. qBittorrent is the configured active client. Installing SABnzbd alone does not enable Usenet downloads.

The owning service definition is in [`compose.yml.j2`](../../../ansible/roles/media_server/templates/compose.yml.j2); common deployment steps are in [`tasks/main.yml`](../../../ansible/roles/media_server/tasks/main.yml). See [Setup](../setup.md) for first-run script ownership and settings that require appdata restoration/manual follow-up.

## Connections and paths

Container port 8080 is published as host port 8081. Containers would use `http://sabnzbd:8080`, not `:8081`. It receives the same `/srv/media:/data` HDD bind mount. Homarr’s SABnzbd API integration passed.

## Normal use

If Usenet is desired later, enter and test server details in SABnzbd, then add it as a client to the relevant library managers using its API key, internal URL and categories. Keep secrets out of repository files.

## Troubleshooting and limitations

A healthy web UI/integration only proves the application API is reachable. It does not prove a Usenet account is configured or download-capable. This setup has no successful Usenet download/import test.

```bash
ssh -t alienware 'sudo docker compose -f /opt/media-stack/compose.yml logs --tail 100 sabnzbd'
```

## CPU, memory and disk use

No dedicated physical cores, CPU quota or per-container RAM cap is configured. This app shares all 12 logical CPUs and available host memory. Runtime cgroups confirmed `cpu.max=max 100000`, `memory.max=max` and effective CPU set `0-11`.

The snapshot beginning **2026-11-22 03:12:49 IST** measured an average **0.0004 logical CPUs** and **71.1 MiB** working-memory estimate at the end. App configuration occupies **0.12 MiB** allocated disk space, excluding images, media, Docker logs and separate cache.

These are observations during one 30-second window, not reservations or sizing requirements. Workload, file cache, scanning, unpacking, imports and transcoding can change them. See [Resources](../resources.md) for raw charged memory, sampled peaks, I/O, host totals and methodology.

## Upstream documentation

[SABnzbd documentation](https://docs.linuxserver.io/images/docker-sabnzbd/)

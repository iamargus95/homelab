# Bazarr

[Documentation home](../README.md) · [Setup](../setup.md) · [Resources](../resources.md)

Subtitle management for Sonarr TV series and Radarr movies.

## Service configuration

| Setting | Value |
| --- | --- |
| Compose service | `bazarr` |
| Image in source | `lscr.io/linuxserver/bazarr:latest` |
| Browser URL | [http://192.168.1.243:6767](http://192.168.1.243:6767) |
| Container web port | `6767` |
| Persistent state | `/opt/media-stack/config/bazarr:/config` |
| Restart policy | `unless-stopped` |
| Docker logs | JSON, `10m` per file, three files |

Forms authentication is enabled. Use `admin` and the `bazarr` password entry.

## How it was set up

The bootstrap connects Sonarr and Radarr using service names and privately read API keys, enables both integrations and sets a generated login. Both use the same `/data` filesystem paths, so no path translation was needed.

A later user-selected English profile (ID 1) was created through Bazarr’s settings API. English is enabled, this profile is the default for new movies and series, and it was assigned to the existing unassigned TV series. This cleared `Missing languages profile`; both Bazarr and Homarr then reported zero health issues. The language preference is a later appdata setting, not part of the current first-run bootstrap.

The owning service definition is in [`compose.yml.j2`](../../../ansible/roles/media_server/templates/compose.yml.j2); common deployment steps are in [`tasks/main.yml`](../../../ansible/roles/media_server/tasks/main.yml). See [Setup](../setup.md) for first-run script ownership and settings that require appdata restoration/manual follow-up.

## Connections and paths

Sonarr `http://sonarr:8989`; Radarr `http://radarr:7878`; common HDD `/srv/media:/data`. Homarr reads Bazarr missing-subtitle, provider and health counters through its API.

## Normal use

Review Settings → Languages for the English profile/defaults. Configure and test subtitle providers before expecting downloads. Profile assignment chooses desired languages; it does not supply a provider account or start a successful retrieval on its own.

## Troubleshooting and limitations

No subtitle providers are enabled yet. An empty health list does not mean subtitle downloads are fully configured. The earlier single Health Issues badge in Homarr came from Bazarr, not Homarr’s own database/Redis. Refresh upstream/widget status after fixing profile or provider problems.

```bash
ssh -t alienware 'sudo docker compose -f /opt/media-stack/compose.yml logs --tail 100 bazarr'
```

## CPU, memory and disk use

No dedicated physical cores, CPU quota or per-container RAM cap is configured. This app shares all 12 logical CPUs and available host memory. Runtime cgroups confirmed `cpu.max=max 100000`, `memory.max=max` and effective CPU set `0-11`.

The snapshot beginning **2026-11-22 03:12:49 IST** measured an average **0.0029 logical CPUs** and **174.0 MiB** working-memory estimate at the end. App configuration occupies **0.92 MiB** allocated disk space, excluding images, media, Docker logs and separate cache.

These are observations during one 30-second window, not reservations or sizing requirements. Workload, file cache, scanning, unpacking, imports and transcoding can change them. See [Resources](../resources.md) for raw charged memory, sampled peaks, I/O, host totals and methodology.

## Upstream documentation

[Bazarr documentation](https://docs.linuxserver.io/images/docker-bazarr/)

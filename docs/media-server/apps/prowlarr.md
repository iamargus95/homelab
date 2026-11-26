# Prowlarr

[Documentation home](../README.md) · [Setup](../setup.md) · [Resources](../resources.md)

Central indexer management and synchronization to Sonarr, Radarr and Lidarr.

## Service configuration

| Setting | Value |
| --- | --- |
| Compose service | `prowlarr` |
| Image in source | `lscr.io/linuxserver/prowlarr:latest` |
| Browser URL | [http://192.168.1.243:9696](http://192.168.1.243:9696) |
| Container web port | `9696` |
| Persistent state | `/opt/media-stack/config/prowlarr:/config` |
| Restart policy | `unless-stopped` |
| Docker logs | JSON, `10m` per file, three files |

Forms authentication is enabled. Use `admin` and the `prowlarr` password entry.

## How it was set up

The first-run script creates application connections for Sonarr, Radarr and Lidarr using service DNS, their private API keys and `fullSync`. Indexers were intentionally left empty initially, which caused the “No indexers enabled” health error.

After user approval, the built-in public definitions Knaben, TorrentsCSV and YTS passed their tests and were enabled using the Standard sync profile. Knaben synced to all three library managers; YTS synced to Radarr. TorrentsCSV remained available in Prowlarr only under the observed app/category compatibility rules. This later indexer selection is persisted in appdata, not recreated by `bootstrap.py`.

On 26 November 2026, five more public sources passed Prowlarr's connection
test and returned results after being enabled. Prowlarr synchronized the
following sources with RSS and automatic search enabled:

| App | New sources |
| --- | --- |
| Sonarr | The Pirate Bay, SubsPlease, Anime Tosho, Shana Project |
| Lidarr | The Pirate Bay, Nipponsei |
| Radarr | Existing Knaben and YTS sources |

A movie-title search on The Pirate Bay returned movie results in Prowlarr,
but Radarr's validation returned no results in the configured movie categories
and rejected the sync. Prowlarr also reported an existing TorrentsCSV
availability warning. These choices are stored in live Prowlarr appdata.

The owning service definition is in [`compose.yml.j2`](../../../ansible/roles/media_server/templates/compose.yml.j2); common deployment steps are in [`tasks/main.yml`](../../../ansible/roles/media_server/tasks/main.yml). See [Setup](../setup.md) for first-run script ownership and settings that require appdata restoration/manual follow-up.

## Connections and paths

Application URLs are `http://sonarr:8989`, `http://radarr:7878` and `http://lidarr:8686`; the Prowlarr URL supplied to applications is `http://prowlarr:9696`. Prowlarr does not mount media or download data itself.

## Normal use

Use Indexers to add and Test sources, then save enabled. Use Settings → Apps to test connections and synchronize. Indexer tests and application tests check different things. Search results alone do not start a download unless grabbed by an app or client workflow.

## Troubleshooting and limitations

The empty-indexer warning cleared after configuration. Internet Archive, EZTV, Uindex and TorrentDownload timed out; BT.etree was blocked by Cloudflare and none was saved. Current provider availability must be retested. Do not assume every Prowlarr indexer will export to every app; category and capability compatibility matter.

```bash
ssh -t alienware 'sudo docker compose -f /opt/media-stack/compose.yml logs --tail 100 prowlarr'
```

## Knaben magnet preference

On 22 November 2026, Knaben's upstream web download endpoint returned `501`, causing indexer backoff and failed grabs despite successful searches. Enabled **Prefer Magnet URL** (`torrentBaseSettings.preferMagnetUrl=true`) for Knaben. Both connection tests passed, a refreshed download redirected directly to a magnet, and new individual episode grabs through Sonarr succeeded. Preserve this setting when recreating the public indexer; advertised seeder counts still require a live client check.

## CPU, memory and disk use

No dedicated physical cores, CPU quota or per-container RAM cap is configured. This app shares all 12 logical CPUs and available host memory. Runtime cgroups confirmed `cpu.max=max 100000`, `memory.max=max` and effective CPU set `0-11`.

The snapshot beginning **2026-11-22 03:12:49 IST** measured an average **0.0019 logical CPUs** and **154.0 MiB** working-memory estimate at the end. App configuration occupies **5.61 MiB** allocated disk space, excluding images, media, Docker logs and separate cache.

These are observations during one 30-second window, not reservations or sizing requirements. Workload, file cache, scanning, unpacking, imports and transcoding can change them. See [Resources](../resources.md) for raw charged memory, sampled peaks, I/O, host totals and methodology.

## Upstream documentation

[Prowlarr documentation](https://docs.linuxserver.io/images/docker-prowlarr/)

# Homarr

[Documentation home](../README.md) · [Setup](../setup.md) · [Resources](../resources.md)

Private dashboard for the nine media services, Uptime Kuma and Hermes Agent, with application links and media-service widgets.

## Service configuration

| Setting | Value |
| --- | --- |
| Compose service | `homarr` |
| Image in source | `ghcr.io/homarr-labs/homarr:v2.14.0` |
| Browser URL | [http://192.168.1.243:7575](http://192.168.1.243:7575) |
| Container web port | `7575` |
| Persistent state | `/opt/media-stack/config/homarr:/appdata` |
| Restart policy | `unless-stopped` |
| Docker logs | JSON, `10m` per file, three files |

Use `admin` and the `homarr` password entry. The board is private; visiting it without a session requires login.

## How it was set up

Ansible creates `/opt/media-stack/config/homarr` and the one-time root-only `.homarr.env` encryption key. `bootstrap-homarr.py` claims onboarding, creates the administrator, disables onboarding analytics, sets dark appearance, and builds the `homelab` board. It saves integration secrets through Homarr’s encrypted integration flow and selects this board for desktop and mobile home views.

The board has eleven app tiles (nine media apps, Uptime Kuma and Hermes Agent) plus clock, playback, releases, requests, calendar, missing-media, indexer, subtitle and download widgets. Starter tiles and unconfigured sample widgets were removed. Four support/documentation app records remain in Management; they are not extra media-app tiles. All nine integration connection tests passed.

The owning service definition is in [`compose.yml.j2`](../../../ansible/roles/media_server/templates/compose.yml.j2); common deployment steps are in [`tasks/main.yml`](../../../ansible/roles/media_server/tasks/main.yml). See [Setup](../setup.md) for first-run script ownership and settings that require appdata restoration/manual follow-up.

## Connections and paths

Integration URLs use `http://192.168.1.243:PORT`, matching browser-facing app links. Docker management is disabled (`ENABLE_DOCKER=false`); no Docker socket is mounted. Seerr/Jellyfin widgets use their saved service connections.

## Added monitoring and agent shortcuts

[Uptime Kuma](http://192.168.1.243:3001) and [Hermes Agent](http://192.168.1.243:9120) were added as app bookmarks and placed on the existing private `homelab` board in both desktop and mobile layouts. The additive helper [`add-homarr-server-apps.py`](../../../ansible/roles/media_server/files/add-homarr-server-apps.py) uses Homarr's authenticated app/create and board/add-item APIs. It preserves existing items, positions and board privacy, and reruns without adding duplicate tiles. The server-apps playbook applies it after deploying the services when an existing Homarr board is present.

These two shortcuts do not add API integrations or expose service credentials in their URLs. Kuma opens its normal login. Hermes opens its separately password-protected Webapp; its model provider remains ChatGPT/Codex and its raw API remains private. After the administrative container recreation, the Webapp login gate was verified: anonymous configuration requests and invalid passwords return `401`, the saved password is accepted and an authenticated configuration request returns `200`.

## Normal use

Open [the homelab board](http://192.168.1.243:7575/boards/homelab). Edit mode lets you move widgets or change the layout. Manage apps and integrations separately: an app link is not itself an authenticated integration.

## Troubleshooting and limitations

A health count inside a widget belongs to that upstream service. The prior “1 Health Issues” tile was Bazarr’s missing language profile; Homarr’s own database/Redis checks were healthy. Refresh the widget after an upstream fix. Preserve the encryption key with appdata during recovery.

```bash
ssh -t alienware 'sudo docker compose -f /opt/media-stack/compose.yml logs --tail 100 homarr'
```

## CPU, memory and disk use

No dedicated physical cores, CPU quota or per-container RAM cap is configured. This app shares all 12 logical CPUs and available host memory. Runtime cgroups confirmed `cpu.max=max 100000`, `memory.max=max` and effective CPU set `0-11`.

The snapshot beginning **2026-11-22 03:12:49 IST** measured an average **0.0187 logical CPUs** and **282.7 MiB** working-memory estimate at the end. App configuration occupies **7.62 MiB** allocated disk space, excluding images, media, Docker logs and separate cache.

These are observations during one 30-second window, not reservations or sizing requirements. Workload, file cache, scanning, unpacking, imports and transcoding can change them. See [Resources](../resources.md) for raw charged memory, sampled peaks, I/O, host totals and methodology.

## Upstream documentation

[Homarr documentation](https://homarr.dev/docs/getting-started/installation/docker/)

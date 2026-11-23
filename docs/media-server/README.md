# Alienware media server

The standalone Alienware 15 R4 at `192.168.1.243` hosts ten media services, a separate Uptime Kuma container, and an official Hermes Agent container. Ansible installs and configures these applications.

| Read this | For |
| --- | --- |
| [Setup](setup.md) | Prerequisites, deployment order, first-run configuration and manual follow-up |
| [Architecture and storage](architecture.md) | Request flow, connections, filesystem layout and hardware access |
| [Resources](resources.md) | Configured limits, measured CPU/RAM/disk use and collection commands |
| [Public Jellyfin access](public-access.md) | Domain, Cloudflare Tunnel, authentication, validation and rollback |
| [Operations](operations.md) | Status, troubleshooting, updates, backup and recovery |
| [Changes](changes.md) | What was deployed, configured, verified and left outstanding |

## App guides

| App | Open on LAN | Purpose | Guide |
| --- | --- | --- | --- |
| Homarr | [Dashboard](http://192.168.1.243:7575/boards/homelab) | Private dashboard and service widgets | [Homarr](apps/homarr.md) |
| Jellyfin | [8096](http://192.168.1.243:8096) | Stream movies, TV and music | [Jellyfin](apps/jellyfin.md) |
| Seerr | [5055](http://192.168.1.243:5055) | Request content through Sonarr/Radarr | [Seerr](apps/seerr.md) |
| Sonarr | [8989](http://192.168.1.243:8989) | TV library, searches and imports | [Sonarr](apps/sonarr.md) |
| Radarr | [7878](http://192.168.1.243:7878) | Movie library, searches and imports | [Radarr](apps/radarr.md) |
| Lidarr | [8686](http://192.168.1.243:8686) | Music library | [Lidarr](apps/lidarr.md) |
| Prowlarr | [9696](http://192.168.1.243:9696) | Indexers and application synchronization | [Prowlarr](apps/prowlarr.md) |
| Bazarr | [6767](http://192.168.1.243:6767) | English subtitle profiles and downloads | [Bazarr](apps/bazarr.md) |
| qBittorrent | [8080](http://192.168.1.243:8080) | Active torrent download client | [qBittorrent](apps/qbittorrent.md) |
| SABnzbd | [8081](http://192.168.1.243:8081) | Usenet client, awaiting a provider | [SABnzbd](apps/sabnzbd.md) |
| Uptime Kuma | [3001](http://192.168.1.243:3001) | Twelve availability monitors | [Uptime Kuma](apps/uptime-kuma.md) |
| Hermes Agent | [9120](http://192.168.1.243:9120); private API on loopback `8642` | ChatGPT/Codex assistant with a password-protected Webapp and Slack | [Hermes](apps/hermes.md) |

## Current boundaries

- The HDD contains media and downloads. App state, images and Jellyfin cache use the Ubuntu boot SSD. The extra NVMe SSD is mounted and reserved empty.
- Each application shares the host's 6 physical cores / 12 logical CPUs. No per-app CPU quota, memory cap or dedicated core assignment is configured. See the measured table before interpreting resource use.
- Passwords and API keys are kept on the server, never in these docs. The main password file is `/opt/media-stack/admin-credentials.json`, including its `uptime-kuma` entry. Kuma also retains `/opt/uptime-kuma/admin-credentials.json`. Hermes has a separate private API key and requires the user's ChatGPT/Codex sign-in.
- Subtitle providers and a Usenet server are still unconfigured. No automatic media-server backup job is enabled.
- LAN HTTP endpoints are bound to the current DHCP address. Jellyfin DNS and the Cloudflare Tunnel route are configured for [jellyfin.surajkamath.dev](https://jellyfin.surajkamath.dev), currently blocked with `403` pending an access-mode decision. Router reservation and reboot recovery testing remain follow-up work.

The status above was reviewed on 22 November 2026. The resource snapshot is a short measurement of the running workload, not a capacity guarantee.

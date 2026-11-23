# Uptime Kuma

[Documentation home](../README.md) · [Setup](../setup.md)

Uptime Kuma monitors the media apps, Hermes Webapp and SSH on the Alienware. Open **[http://192.168.1.243:3001](http://192.168.1.243:3001)** on the home network, or use its tile on the private [Homarr board](http://192.168.1.243:7575/boards/homelab).

| Setting | Value |
| --- | --- |
| Version | `louislam/uptime-kuma:2.5.12` |
| Compose project | `/opt/uptime-kuma/compose.yml`, separate from the media project |
| Persistent SQLite database | `/opt/uptime-kuma/data/kuma.db` |
| Container user | UID/GID `1000:1000` |
| Account | `admin`; password also listed under `uptime-kuma` in `/opt/media-stack/admin-credentials.json` |
| Listener | LAN address only, TCP `3001` |
| Restart | `unless-stopped` |
| Docker socket | Not mounted |

Read the password privately in your own terminal:

```bash
ssh alienware 'cat /opt/uptime-kuma/admin-credentials.json'
```

The dedicated file remains `/opt/uptime-kuma/admin-credentials.json`. Its entry is also available as `uptime-kuma` in `/opt/media-stack/admin-credentials.json`, alongside the media accounts. Both files are owned by `argus`, mode `0600`; do not commit them. The role adds a missing central entry after account setup, preserves other applications and leaves an existing central Kuma entry unchanged. On an empty deployment, Ansible starts Kuma on loopback, creates the administrator through the Socket.IO API, logs in, adds monitors and only then publishes the LAN listener. The bootstrap waits for `loginRequired`, since a connected Socket.IO transport can precede registration of server handlers. `.configured-admin` preserves later UI changes and prevents first-run setup from being repeated.

## Configured monitors

HTTP checks run every 60 seconds with a 15-second timeout, two retries and a 20-second retry interval. The HTTP success range is `200–299`; redirects are followed up to five times.

| Monitor | Target |
| --- | --- |
| Jellyfin | `http://192.168.1.243:8096/health` |
| Sonarr | `http://192.168.1.243:8989/ping` |
| Radarr | `http://192.168.1.243:7878/ping` |
| Lidarr | `http://192.168.1.243:8686/ping` |
| Prowlarr | `http://192.168.1.243:9696/ping` |
| Bazarr | `http://192.168.1.243:6767/` |
| qBittorrent | `http://192.168.1.243:8080/` |
| SABnzbd | `http://192.168.1.243:8081/` |
| Seerr | `http://192.168.1.243:5055/api/v1/status` |
| Homarr | `http://192.168.1.243:7575/` |
| Hermes | `http://192.168.1.243:9120/` |
| Alienware SSH | TCP `192.168.1.243:22` |

The first-run role provisions the ten media checks and SSH. On a fresh deployment, add the Hermes monitor after enabling its Webapp. In Kuma, select **Add New Monitor**, choose **HTTP(s)**, name it **Hermes**, and use the URL above with a 60-second interval and the default redirect handling. The live Hermes monitor checks the Webapp login page. The user subsequently paused and then restarted qBittorrent. Its monitor reports DOWN while intentionally stopped; qBittorrent is running again. These are availability checks, not authenticated download/playback tests. Notification providers and public status pages are not configured. Because Kuma runs on the monitored host, it cannot report a complete host/power/network failure while offline; use an independent external monitor for that requirement.

## Operations

```bash
ssh -t alienware 'sudo docker compose --project-directory /opt/uptime-kuma ps'
ssh -t alienware 'sudo docker compose --project-directory /opt/uptime-kuma logs --tail 80'
```

The database, credentials and Compose file use the Ubuntu boot SSD. The additional 500 GB SSD remains empty. Preserve the entire `data` directory, including SQLite WAL files: stop Kuma for a consistent filesystem backup, or use SQLite's backup facility. No scheduled backup job was added.

Kuma shares the host's CPU and RAM without a dedicated core or hard memory quota. Container logs rotate at 10 MB with three retained files. See [resources](../resources.md) for measured use.

Sources: [official project](https://github.com/louislam/uptime-kuma), [pinned release](https://github.com/louislam/uptime-kuma/releases/tag/2.5.12).

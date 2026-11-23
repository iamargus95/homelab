# Alienware media server

The complete documentation now lives in **[Media server documentation](media-server/README.md)**.

| Guide | Contents |
| --- | --- |
| [Setup](media-server/setup.md) | Ansible sources, prerequisites, storage preparation, first-run configuration and manual follow-up |
| [Architecture](media-server/architecture.md) | App flow, HDD/SSD layout, shared paths, permissions and hardware acceleration |
| [Resources](media-server/resources.md) | Measured per-app CPU/RAM/disk/I/O, host totals and actual configured limits |
| [Public access](media-server/public-access.md) | Jellyfin domain, Cloudflare Tunnel, authentication and rollback |
| [Operations](media-server/operations.md) | Troubleshooting, updates, backups and recovery |
| [Changes](media-server/changes.md) | Deployment history, fixes, validation and outstanding work |
| [Individual app guides](media-server/README.md#app-guides) | Homarr, Jellyfin, Seerr, Sonarr, Radarr, Lidarr, Prowlarr, Bazarr, qBittorrent and SABnzbd |

## At a glance

- Host: standalone Ubuntu Alienware at `192.168.1.243`, managed through the dedicated Ansible `media_servers` inventory.
- Hardware: 6 physical CPU cores / 12 logical CPUs; 16 GB installed RAM. All ten containers share the host without dedicated cores or hard CPU/memory caps.
- Storage: 1 TB HDD mounted at `/srv/media` for media/downloads; boot SSD for Ubuntu, Docker, app state and cache; extra 500 GB NVMe mounted at `/srv/ssd` and reserved empty.
- Public Jellyfin hostname: [jellyfin.surajkamath.dev](https://jellyfin.surajkamath.dev). Currently blocked with `403` pending an access-mode decision; see the public-access guide.
- Dashboard: [Homarr](http://192.168.1.243:7575/boards/homelab). Passwords remain in `/opt/media-stack/admin-credentials.json` on the host; do not commit them.
- Public indexers are enabled, English subtitles are selected, and the first show search successfully reached qBittorrent. Subtitle providers and a Usenet server remain unconfigured. No daily backup job has been enabled.

## Normal deployment

From the repository root, with working SSH and the server's sudo password:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook \
  -i ansible/inventory/alienware.yml ansible/playbooks/media-server.yml -K
```

Do not add `media_initialize_disks=true` to routine reruns. Read [Setup](media-server/setup.md) for the distinction between initial disk initialization, application bootstrap, and later UI/API settings.

The timestamped [resource snapshot](media-server/snapshots/2026-11-22-resources.json) and [collection script](../scripts/collect-media-resources.py) make the utilization figures reviewable and repeatable. These are short-window observations, not capacity guarantees.

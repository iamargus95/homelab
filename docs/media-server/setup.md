# Setup and configuration

[Documentation home](README.md) · [Operations](operations.md) · [Changes](changes.md)

## Owning files

| Source | Responsibility |
| --- | --- |
| [`ansible/inventory/alienware.yml`](../../ansible/inventory/alienware.yml) | Standalone host, IP, SSH user and Python interpreter |
| [`ansible/playbooks/media-server.yml`](../../ansible/playbooks/media-server.yml) | Targets `media_servers`, escalates with sudo, applies the role |
| [`defaults/main.yml`](../../ansible/roles/media_server/defaults/main.yml) | Disk serial paths, mounts, UID/GID, timezone and addresses |
| [`tasks/main.yml`](../../ansible/roles/media_server/tasks/main.yml) | Storage, Docker installation, state directories, Compose deployment and first-run scripts |
| [`compose.yml.j2`](../../ansible/roles/media_server/templates/compose.yml.j2) | Ten services, images, ports, mounts and restart/logging settings |
| [`bootstrap.py`](../../ansible/roles/media_server/files/bootstrap.py) | Initial accounts, library roots, downloader/app connections, Jellyfin acceleration and Seerr setup |
| [`configure-jellyfin-public.py`](../../ansible/roles/media_server/files/configure-jellyfin-public.py) | Opt-in Jellyfin remote access and exact known proxy settings; Cloudflare resources are separate |
| [`bootstrap-homarr.py`](../../ansible/roles/media_server/files/bootstrap-homarr.py) | Homarr admin account, private board, integrations and starter-widget cleanup |

Start with the existing bare-metal Ubuntu installation and verify the Alienware SSH host key before deployment.

## Prerequisites

Use a local Ansible installation with `community.general`, `ansible.posix` and `community.docker` collections. SSH alias `alienware` resolves locally to `argus@192.168.1.243`; the inventory itself uses the address directly. The SSH key must work and `argus` must be able to sudo. Run commands from the repository root.

```bash
ssh alienware 'hostname; uptime'
ansible-galaxy collection list
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook \
  -i ansible/inventory/alienware.yml \
  ansible/playbooks/media-server.yml --syntax-check
```

Check the host IP, UID/GID, Intel render-device identity and data-disk serial paths before using this role on changed hardware. `bootstrap.py` assumes UID/GID 1000 and `/opt/media-stack`; Homarr bootstrap also hardcodes the current LAN IP. Editing only the inventory is not sufficient to migrate this setup to another address or directory.

## Disk preparation

The initial deployment was explicitly authorized to format both blank extra drives. They now have ext4 filesystems and must not be reinitialized. Normal deployment uses the default `media_initialize_disks: false`.

For a genuinely new blank target, first inspect `lsblk -f`, `wipefs --no-act` and `/dev/disk/by-id`, confirm the exact disks and obtain the owner's authorization to erase them. The explicit one-time variable `-e media_initialize_disks=true` allows initialization; it is not part of routine reruns. The filesystem module uses `force: false`. Keep this flag out of normal deployment commands.

## Deploy or reapply

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook \
  -i ansible/inventory/alienware.yml \
  ansible/playbooks/media-server.yml -K
```

`-K` asks for the remote sudo password. A temporary `/etc/sudoers.d/99-codex-setup` rule was used during interactive setup and removed afterward. Removal was verified. This temporary-rule cleanup is an operational step, not an automatic Ansible task.

The role performs these steps:

1. Inspect filesystem types, refuse unapproved blank/other-format disks, obtain UUIDs and persist/mount both data volumes.
2. Create HDD library/download directories, boot-SSD state/cache directories and the NVMe transcode directory.
3. Add Docker's official signing key and repository using Ubuntu's detected release codename; install Engine, containerd, Buildx and Compose.
4. Create Homarr's encryption-key file once, render Compose and install Docker's mount dependency override.
5. Start the initial stack with loopback-only web bindings until `.configured-secure` exists.
6. Run `bootstrap.py`: create strong passwords, set forms authentication, configure qBittorrent paths/categories, create library roots and Prowlarr application links, create Jellyfin libraries and request an initial scan, configure Bazarr/SABnzbd, test/enable Intel VA-API, create the Sonarr-to-Jellyfin import notification with path mapping, and initialize Seerr.
7. Render/apply the LAN bindings after first-run configuration succeeds.
8. Run `bootstrap-homarr.py` to claim onboarding, create an admin, connect the nine apps and create the private `homelab` board.
9. When `media_public_hostname` is explicitly configured, apply Jellyfin remote-access and known-proxy settings through its API. Cloudflare Tunnel/DNS provisioning is managed separately; see [Public access](public-access.md).

Completion markers preserve existing accounts and UI edits. Do not delete markers to force a reset: some steps create libraries or rewrite settings. They are not a general-purpose reconciliation system. Use app UIs for later configuration and preserve appdata for recovery.

## Follow-up settings applied through APIs

These changes persist in app databases/configuration and are **not recreated by the current first-run Ansible scripts on a fresh empty appdata directory**:

| Change | Current setting | How to reproduce |
| --- | --- | --- |
| Public indexers | Knaben, TorrentsCSV, YTS | In Prowlarr add each built-in public definition; enable Prefer Magnet URL for Knaben, Test, save enabled with the Standard sync profile, then sync applications. Availability must be retested. |
| Indexer application sync | Knaben to Sonarr/Radarr/Lidarr; YTS to Radarr | Prowlarr → Settings → Apps; connections use `fullSync`. Only compatible categories are exported. |
| English subtitles | Bazarr English profile ID 1; enabled by default for movies and series | Bazarr → Settings → Languages: enable English, create an English profile, choose it as both defaults, and assign it to existing unassigned content. |
| Initial show search | Reran Sonarr's existing-series search after indexers were added | On the series page trigger a search for monitored episodes/seasons. Monitor Activity and qBittorrent afterward. This is an action, not a permanent setting. |

Subtitle providers and Usenet service credentials remain unconfigured. Public Prowlarr indexers do not supply subtitle-provider or Usenet accounts.

## Credential handling

Read passwords privately over SSH when needed:

```bash
ssh alienware 'cat /opt/media-stack/admin-credentials.json'
```

The file is mode `0600`, owned by `argus`; Kuma is included under `uptime-kuma` and also retains its dedicated private credentials file. App config files also contain API keys. Homarr's `/opt/media-stack/.homarr.env` is root-owned mode `0600`; it contains the encryption key used for saved integrations. Do not print it into build logs, commit it, or regenerate it during updates. Backups of these files must be private.

## Monitoring and Hermes Agent

The [server-apps playbook](../../ansible/playbooks/server-apps.yml) adds applications without rerunning disk preparation or recreating the media stack:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook \
  -i ansible/inventory/alienware.yml \
  ansible/playbooks/server-apps.yml -K
```

Use `--tags uptime-kuma` or `--tags hermes` for one role. Docker must already be installed. These roles use the boot SSD and do not write to the extra SSD or alter media mounts.

The Kuma role pins `2.5.12`, creates a private admin password, starts on loopback, configures eleven monitors and then publishes LAN port 3001. The completion marker preserves existing account and monitor edits. The live instance also has the Hermes HTTP monitor, which you can recreate from the Kuma guide. See the [Kuma guide](apps/uptime-kuma.md).

The Hermes Docker role uses the official `nousresearch/hermes-agent:v0.23.3` image, maps the runtime user to UID/GID 1000, selects `openai-codex`, and configures a bearer-protected API on loopback using Linux host networking. The container is supervised by its upstream s6 image and restarted by Docker. Run `hermes model` over SSH for your own ChatGPT sign-in, as described in the [Hermes guide](apps/hermes.md). The host wrapper uses normal sudo authentication; no permanent passwordless rule is installed. A later rerun restores the role's configured provider/default model; update the role if you want another persistent default.


The Alienware also opts into `hermes_docker_webapp_enabled: true`. The role's separate Webapp helper prepares a home-network password login, retains the private raw API, and adds the UI account to the main credentials file under `hermes`. Container recreation loads new environment settings. The server-apps playbook then adds Kuma and the enabled Hermes Webapp to an existing private Homarr board through an additive API helper, preserving prior items and placement. If the Webapp opt-in is false, it adds only Kuma. These are bookmarks, not new authenticated Homarr integrations.

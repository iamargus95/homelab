# Alienware homelab

Ubuntu 26.04 LTS on an Alienware 15 R4 serves the homelab at `192.168.1.243`
over the home network. Ansible manages the Docker Compose deployments.
The Cloudflare Tunnel connector runs as a systemd user service.

| Deployment | Apps | Compose source |
| --- | --- | --- |
| Media stack | Jellyfin, Seerr, Sonarr, Radarr, Lidarr, Prowlarr, Bazarr, qBittorrent, SABnzbd, Homarr | [Media Compose template](ansible/roles/media_server/templates/compose.yml.j2) |
| Monitoring | Uptime Kuma | [Kuma Compose template](ansible/roles/uptime_kuma/templates/compose.yml.j2) |
| Personal assistant | Hermes Agent with the Webapp and Slack | [Hermes Compose template](ansible/roles/hermes_docker/templates/compose.yml.j2) |
| Personal assistant | Nod with private SSH-tunneled access | [Nod deployment guide](docs/media-server/apps/nod.md) |

- [App guides and LAN links](docs/media-server/README.md)
- [Setup and deployment](docs/media-server/setup.md)
- [Operations and backups](docs/media-server/operations.md)
- [Cloudflare Tunnel and Jellyfin ingress](docs/media-server/public-access.md)

## Deploy from the repository

Use the [setup guide](docs/media-server/setup.md) to check storage prerequisites and
SSH access before deployment. Install the Ansible collections, then run the
playbooks from the `ansible` directory. The inventory selects the Alienware and
its installed sudo executable.

```bash
ansible-galaxy collection install ansible.posix community.docker community.general
cd ansible
ansible-playbook playbooks/media-server.yml --ask-become-pass
ansible-playbook playbooks/server-apps.yml --ask-become-pass
ansible-playbook playbooks/hermes-ops.yml --ask-become-pass
ansible-playbook playbooks/nod.yml --ask-become-pass
ansible-playbook playbooks/arr-dashboard.yml --ask-become-pass
ansible-playbook playbooks/adguard-home.yml --ask-become-pass
ansible-playbook playbooks/internet-monitoring.yml --ask-become-pass
```

The media playbook manages storage mounts and the media stack. The server-apps
playbook deploys Kuma and Hermes. The Hermes operations playbook gives the Slack
assistant read-only diagnostics and an explicitly approved Jellyfin restart action.
The standalone app playbooks use the existing Kuma and Homarr deployments.
The [internet monitoring playbook](docs/media-server/apps/speedtest-tracker.md)
adds scheduled speed tests and WAN availability checks.

The rendered Compose files, credentials, app databases and media stay on the
server. The repository contains the deployment sources and operating guides.

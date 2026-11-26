# Arr Dashboard

[Documentation home](../README.md) · [Upstream documentation](https://github.com/Kha-kis/arr-dashboard)

The [Arr Dashboard playbook](../../../ansible/playbooks/arr-dashboard.yml) provisions a LAN-only admin dashboard at [http://192.168.1.243:3000](http://192.168.1.243:3000). It verifies connections to Sonarr, Radarr, Lidarr, Prowlarr, Jellyfin, and Seerr, adds a shortcut to the private Homarr board, and configures Uptime Kuma to check the unauthenticated `/health` endpoint.

The playbook saves its dedicated `admin` login under `arr-dashboard` in the shared `/opt/media-stack/admin-credentials.json` file with mode `0600`. Retrieve only that entry in a private terminal with `ssh alienware 'jq -r ".\"arr-dashboard\".password" /opt/media-stack/admin-credentials.json'`. Dashboard state and its encryption keys live under `/opt/arr-dashboard/config`.

Queue Cleaner runs in active mode for Sonarr, Radarr, and Lidarr and removes failed downloads. Stalled and slow downloads and items waiting for import are left to the download client and ARR apps. [qBittorrent](qbittorrent.md) stops at a share ratio of zero. Completed Download Handling in each ARR app removes its managed torrent once import succeeds.

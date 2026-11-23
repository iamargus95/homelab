# Operations and troubleshooting

[Documentation home](README.md) · [Setup](setup.md) · [Resources](resources.md)

## Routine checks

These commands prompt for the server sudo password in a terminal; passwordless sudo and Docker-group membership are not required.

```bash
ssh -t alienware 'sudo docker compose -f /opt/media-stack/compose.yml ps'
ssh -t alienware 'sudo docker stats --no-stream'
ssh -t alienware 'sudo docker compose -f /opt/media-stack/compose.yml logs --tail 100 sonarr'
ssh alienware 'df -h / /srv/media /srv/ssd'
```

Replace `sonarr` with any service name from the [app guides](README.md#app-guides). Application logs/configuration may include API keys; review locally and redact credentials before sharing.

Use the [resource collector](../../scripts/collect-media-resources.py) for an unprivileged cgroup sample and reproducible JSON output. Read [Resources](resources.md) before comparing it with Docker's memory display.

## A Seerr request does not download

1. Open Seerr's request and check approval status and the selected seasons. An approved request should appear in Sonarr/Radarr.
2. Check that the item is monitored and has a library root and suitable quality profile. Seerr's default profile for future requests can differ from an existing series' chosen profile.
3. Check Prowlarr's enabled indexers and application synchronization. A healthy app connection alone does not provide any search sources.
4. Open Sonarr/Radarr Activity and history. If a request predates indexer configuration, trigger a search for its monitored episodes/seasons/movie. Do not repeatedly resubmit the request in Seerr.
5. Open qBittorrent. Distinguish active transfers, queued downloads, metadata fetching and stalled torrents. Queueing behind active downloads is not itself a failure. Seed availability and current peer connectivity affect progress.
6. After download completion, check the ARR application's import result, then the corresponding Jellyfin library. An active download is not yet a playable imported episode.

The first show request reached Sonarr before public indexers were configured. A later series search queued all 40 monitored episode records across 13 torrents; three transfers were active and received data at verification. This was a successful request/search/downloader handoff, not evidence that the whole show had finished downloading or imported.

## Downloads finished but Jellyfin is empty

Check Sonarr/Radarr history for successful imports before inspecting Jellyfin. A completed torrent can still be awaiting an import, whereas an imported file under `/srv/media/library` should be discoverable in Jellyfin's matching `/media` library.

The observed TV issue was 14 successfully imported files with zero Jellyfin TV items. Jellyfin's last scan predated the files; a manual Scan Media Library completed and indexed all 14. The real-time watcher then attached to `/media/tv`. The first-run bootstrap now requests a scan after library creation, and Sonarr has a tested `Jellyfin library update` connection with `/data/library/tv` → `/media/tv` mapping for subsequent imports/upgrades/renames. See the [Jellyfin guide](apps/jellyfin.md#imported-episodes-not-appearing-resolved).

If items remain invisible after an import, compare the configured library Locations with container paths, check file permissions, inspect the scheduled scan state/result, and refresh the Jellyfin client. Do not point Jellyfin at the incomplete torrent directory or re-download already imported files to work around a stale index.

## Prowlarr: no indexers enabled

App connections under Settings → Apps are not indexers. Add/test an indexer, save it enabled, then sync applications. Current providers and category mapping are described in the [Prowlarr guide](apps/prowlarr.md). Sources that fail tests should not be forced into the configuration. Public-source availability can change.

## Homarr reports a health issue

Identify the widget first. Homarr's `/api/health/live` checks its own database and Redis, whereas a Bazarr or Prowlarr widget can report a separate upstream issue. Refresh the widget after correcting the upstream problem; cached widget data may lag.

The earlier single warning was Bazarr's `Missing languages profile`, not a failed Homarr container. Creating the English profile and assigning it cleared Bazarr's health list and Homarr's Bazarr status count to zero. [Bazarr](apps/bazarr.md) still needs subtitle providers before it can download subtitles.

## SSH or every web app times out

Check the laptop's LAN IP and Wi-Fi link before changing SSH authentication:

```bash
ssh -o ConnectTimeout=5 alienware 'hostname; uptime'
ping 192.168.1.243
```

From the laptop's console:

```bash
ip -br address
systemctl is-active ssh docker
journalctl -b -u systemd-networkd -u systemd-logind --no-pager -n 100
```

A prior outage affected SSH, ping and Jellyfin together. SSH returned after the lid was opened. Logs showed repeated Wi-Fi roaming/reconnections but no suspend event, so a definitive cause was not established. The existing `/etc/systemd/logind.conf.d/80-server-lid.conf` ignores lid closure on external power and permits suspend on battery; this media role did not create that file. An `snd_hda_intel` audio power-state warning was also visible, but it was not established as the SSH failure's cause.

Reserve the DHCP address on the router before relying on the current static port bindings. If the address changes, review inventory, defaults, bootstrap scripts and existing app URLs before redeploying.

## Updates

Most services use `latest`; Homarr is pinned to `v2.14.0`. Ansible uses `pull: missing`, so rerunning the playbook does not automatically refresh an already-present moving tag. Back up app state first and inspect upstream release/migration notes before pulling a new image.

```bash
ssh -t alienware 'sudo docker compose -f /opt/media-stack/compose.yml pull sonarr && sudo docker compose -f /opt/media-stack/compose.yml up -d sonarr'
```

Update one service at a time when practical, then check its logs, health and connections. Avoid `docker compose down` for routine updates; it stops the entire project. No automatic updater is installed.

## Backup and restore

There is no scheduled backup job for this stack.

For a consistent file-level app backup, stop the stack during the copy, preserve owners/modes, and include `/opt/media-stack/config`, `compose.yml`, `.homarr.env` and `admin-credentials.json`. Copy the backup privately off the laptop. Cache is disposable. HDD media/downloads require their own backup plan and are not included merely by backing up app configuration.

```bash
# Run on the server in an interactive terminal; choose a private backup destination.
sudo install -d -m 0700 /path/to/private
sudo docker compose -f /opt/media-stack/compose.yml stop
sudo tar -C /opt/media-stack -czf /path/to/private/media-stack-config.tar.gz \
  config compose.yml .homarr.env admin-credentials.json
sudo chmod 0600 /path/to/private/media-stack-config.tar.gz
sudo docker compose -f /opt/media-stack/compose.yml start
```

Do not leave the stack stopped if the archive command fails. Restore the matching Homarr encryption key with its database; generating another key will not decrypt existing saved integrations. Restoring appdata is also necessary to recover the public-indexer and English-profile changes, which are not fully recreated by the first-run scripts.

A container image rollback alone does not undo a database migration. A recovery rehearsal and host reboot test have not been performed.


## qBittorrent pause, restart and API authentication

The user requested a pause and then a restart on 22 November 2026. The pause was implemented by gracefully stopping the container, which also took its web interface offline. It is running again and downloads have resumed.

Correction to the earlier diagnostic: qBittorrent v5.3.0 returns HTTP `204` with an empty body and a session cookie on successful login. A script incorrectly required the legacy `Ok.` body and reported rejected credentials. The saved administrator password is valid and matches Sonarr's downloader settings. Check the returned session cookie and an authenticated API request instead of requiring a particular login response body. No password reset is needed.

For an explicit future restart request, use:

```bash
ssh -t alienware 'sudo docker start media-stack-qbittorrent-1'
```

The media-stack playbook requests that all its services run; the separate server-apps playbook does not restart qBittorrent. Avoid restarting a deliberately paused service during unrelated work.

## Stalled torrent diagnosis

On 22 November 2026, two long-running metadata-only torrents occupied two of three download slots. Enabled **Do not count slow torrents in these limits** (`dont_count_slow_torrents=true`), retaining the three-active-download limit, the existing 2 KiB/s slow threshold and 60-second inactivity timer. Working season packs then started downloading. The same preference is included in first-run bootstrap; the live change was applied through qBittorrent's authenticated API without restarting it.

A zero connected-seed count on a queued torrent does not establish that the source is dead. Check state, connected peers, availability, tracker results and byte counters after giving an active torrent a chance to connect. Tracker/indexer seeder numbers are advertisements, not proof of reachable peers.

Knaben's web download links also returned HTTP `501`, triggering temporary Prowlarr backoff and `429` responses to Sonarr. Enabled its **Prefer Magnet URL** setting and successfully tested both Prowlarr and Sonarr indexer connections. A refreshed download link returned a `301` to a magnet URI. These indexer settings persist in Prowlarr appdata and must be recreated manually after a clean state restore.

Replacement diagnostics, original source magnets/paths and rollback information are kept privately on the server in `/opt/media-stack/torrent-replacement-20261122.json`, `/opt/media-stack/qbittorrent-before-download-fix.json` and related probe/result files. Old torrent entries were removed with `deleteFiles=false`; the partial episode payload was verified still present on the HDD. Imported library files were preserved. Do not copy release-cache JSON into the repo: indexer download URLs can contain API credentials.

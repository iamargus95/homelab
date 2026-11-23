# Deployment and change record

[Documentation home](README.md) · [Setup](setup.md) · [Resources](resources.md)

Dates below use Asia/Kolkata. This records the work reviewed on 22 November 2026; it is not a claim of a Git commit or release.

## Initial host and storage setup

- Verified SSH as `argus`, Ubuntu Server 26.04.1 LTS, i7-8750H with 6 physical cores / 12 logical CPUs, and 16 GB installed RAM. Docker was initially absent.
- Inspected the two extra disks by model/serial and filesystem signatures. After explicit authorization, created whole-device ext4 filesystems on the 1 TB HGST HDD and 500 GB WD SN570 NVMe.
- Mounted them persistently by UUID at `/srv/media` and `/srv/ssd`. HDD folders hold downloads and final libraries; the extra NVMe remains reserved empty. The 128 GB Intel boot SSD was retained for Ubuntu, app state, container images and cache.
- Installed official Docker Engine and Compose packages. Added a dedicated `media_servers` inventory, playbook and `media_server` role.
- Added mount ordering/dependencies to Docker, guarded data bind mounts, automatic container restart policies and bounded Docker JSON logs.

## Media applications and connections

- Deployed Jellyfin, Sonarr, Radarr, Lidarr, Prowlarr, Bazarr, qBittorrent, SABnzbd and Seerr through one Compose project.
- Generated distinct admin passwords on the host, enabled app authentication, and configured the shared HDD paths/permissions.
- Connected Sonarr/Radarr/Lidarr to qBittorrent and Prowlarr (`fullSync`); configured movie/TV/music roots and hardlink imports.
- Initialized Jellyfin's Movies, TV Shows and Music libraries with read-only library access. Passed the Intel i915 render device, tested H.264 VA-API encoding, then enabled hardware acceleration.
- Connected Seerr to Jellyfin, Sonarr and Radarr; enabled automatic searches. SABnzbd remains deployed but has no Usenet provider or active ARR client integration.
- Verified app login/connection flows, library roots, writable HDD access as UID 1000, a hardlink operation, and Docker's mounted-storage dependencies. No full playback or import-completion test was established.

## Homarr dashboard

- Added Homarr `v2.14.0`, persistent appdata, a one-time encryption key, a private `homelab` board and a distinct admin account.
- Connected all nine media integrations and tested them successfully. Added app tiles, playback/release, request, calendar, missing-media, indexer, subtitle, download and clock widgets.
- Removed the starter app tiles and unconfigured placeholder widgets from the board. Four built-in support/documentation app records still exist in Homarr management; the board itself has nine media-app tiles.
- Disabled Docker management/socket access and anonymous onboarding analytics. No paid/AI provider was configured.

## Public indexers

- Diagnosed Prowlarr's empty indexer list; connected applications alone did not provide sources.
- At the user's request, tested account-free public definitions. Knaben, TorrentsCSV and YTS passed and were enabled. Internet Archive, EZTV, Uindex and TorrentDownload timed out; BT.etree was blocked by Cloudflare. Failed definitions were not saved.
- Verified completed application sync: Knaben appeared in Sonarr, Radarr and Lidarr; YTS appeared in Radarr. TorrentsCSV remained in Prowlarr only under the observed app/category compatibility rules.
- Verified an empty Prowlarr health list afterward. Detailed test results are on the host at `/opt/media-stack/public-indexer-results.json`.

## English subtitles and first download

- Traced the dashboard's single health warning to Bazarr's missing language profile.
- Created English profile ID 1, enabled English, set it as the default for new movies and series, and applied it to the existing unassigned series. Bazarr health became empty and Homarr's Bazarr health count became zero. Subtitle providers remain unconfigured.
- Traced the approved show request into Sonarr. All four seasons were monitored but the download queue was empty; the request predated configured indexers.
- Reran the existing-series search. It completed with 13 reports sent to qBittorrent and 40 queued episode records; data was received on three active transfers. Verified HDD-backed download storage and no Sonarr queue warnings. This did not establish final download/import completion.

## Connectivity investigation

- Reproduced an outage affecting SSH, ping and Jellyfin at the same IP. Connectivity returned after the lid was opened.
- Logs showed Wi-Fi reconnects/roaming but no suspend event. Existing power/lid settings and an audio-device power-state message were inspected; no definitive root cause or persistent networking fix was established.
- Temporary passwordless sudo access used for installation was removed and the removal verified. No permanent Docker-group access was added to `argus`.

## Documentation and resource audit

- Added individual guides for all ten apps, setup/architecture/operations documents and this change record.
- Added a read-only, unprivileged cgroup-v2 resource collector and a sanitized timestamped snapshot. Measured CPU over a defined window, memory/cache estimates, task counts, data-disk capacity and per-app config allocation.
- Confirmed no hard CPU quotas, per-container memory caps or dedicated core assignments in Compose and runtime cgroups. Documentation distinguishes shared availability from measured use.
- Corrected older summary wording about nine versus ten services, moving image tags versus Homarr's pin, manual sudo cleanup, download activity, and which follow-up settings are reproduced by source.

## Remaining work

Subtitle providers, Usenet service setup, scheduled off-host backups, a DHCP reservation, confirmed reboot recovery, real-client playback/stream-capacity testing and completion of the remaining requested downloads remain outstanding. This documentation task does not change resource limits, restart services or alter provider settings.


## Jellyfin discovery fix after completed downloads

On 22 November 2026, verified 14 completed Sonarr imports on the HDD while Jellyfin's TV index remained empty. Its last completed library scan was before those files arrived. Triggered a library refresh, waited for completion and verified all 14 episode entries. The subsequent log confirmed a watcher on `/media/tv`.

Added and tested a Sonarr `Emby / Jellyfin` import/upgrade/rename connection with a dedicated Jellyfin key and `/data/library/tv` → `/media/tv` path mapping. Updated the first-run bootstrap to request a library scan after creating libraries and to create this notification connection. Existing bootstrap completion markers were preserved; the live change was applied through the apps' APIs. No re-download, file move, mount change, container restart or deletion was needed. The scan established indexing; it did not by itself validate full playback or a later automatic notification event.


## Public Jellyfin hostname

On 22 November 2026, configured `jellyfin.surajkamath.dev` through the pre-existing healthy, remotely managed `homelab` Cloudflare Tunnel. No published-hostname configuration or conflicting DNS record existed at inspection. Added the Jellyfin origin route, 404 fallback, proxied CNAME and a hostname-scoped cache-bypass rule through `cf` CLI after dry-run previews. Reused the existing connector without retrieving its token, installing another daemon, or publishing other media apps.

Enabled Jellyfin remote access, preserved the administrator's existing remote permission and saved the observed origin address as an exact Known Proxy. Added an opt-in inventory setting and idempotent API helper to reproduce the Jellyfin side. Recorded non-secret Cloudflare resource state and rollback steps in [Public access](public-access.md).

Verified public HTTPS, successful login, the user endpoint returning 401 anonymously, an authenticated 1 KiB media range returning 206 and WebSocket upgrade returning 101. A final direct-video test returned 206 without credentials, and local tests also returned 206 for invalid header/query tokens. Temporarily changed the public hostname ingress to `http_status:403` (tunnel config version 2), preserving DNS and cache settings. Public access is pending the user's choice between a Cloudflare Access login gate and standard Jellyfin client compatibility with this known stream-authentication limitation. The public test listed 15 episodes. No sustained remote stream benchmark was performed. Sessions still reported the origin IP, so true-client IP attribution remains unverified. Jellyfin reported no pending restart; active playback was detected and no restart was forced.

## Uptime Kuma, Hermes Agent and requested torrent stop

On 22 November 2026, added a separate server-apps playbook and roles for Uptime Kuma and Hermes. The existing media stack, data mounts and extra SSD were preserved.

- Uptime Kuma `2.5.12` runs as UID/GID 1000 in `/opt/uptime-kuma`, with SQLite persistence, a generated private administrator password and a LAN listener on port 3001. Initial setup was completed on loopback before publication. All eleven initial HTTP/TCP monitors reported UP; an unauthenticated monitor-data request was denied. No notification destination or public status page was added.
- Hermes uses the official `nousresearch/hermes-agent:v0.23.3` Docker image, pinned by its observed immutable digest. Its agent/CLI runs as the image's `hermes` user remapped to UID/GID 1000. Persistent state is `/opt/hermes/data`; host networking supports a private loopback API and SSH-forwarded Codex OAuth callbacks. It has no Docker socket, host-home/media mount or GPU assignment. The API returned 200 for health, 401 for missing/invalid keys and 200 for an authenticated models request. The CLI reported v0.23.3, Python 3.14.9 and OpenAI SDK 2.54.0.
- The user selected ChatGPT/Codex sign-in instead of Nous Portal. Provider `openai-codex` and initial model `gpt-6-sol` are configured; external credential adoption is disabled. No desktop credentials were copied, no provider login exists yet, and no model-inference request was made. Use the SSH CLI wrapper's `hermes model` command to sign in yourself.
- A source installation encountered slow GitHub/PyPI transfers and a package timeout. The supported Docker image supplied the packaged runtime successfully. The incomplete source runtime and its temporary artifact staging were removed. No verification was disabled.
- During installation the user requested that all qBittorrent transfers be paused. An earlier script incorrectly treated the empty successful HTTP 204 login response as a credential failure; later verification confirmed both saved logins match and work. Gracefully stopped `media-stack-qbittorrent-1` to halt all downloads and seeding at that time. The user subsequently requested a restart and the service is running again.

The new roles configure restart policies and log rotation without explicit CPU/RAM quotas. Neither service was published through Cloudflare. Model-provider sign-in, an inference response, notification delivery and a full reboot remain unverified. See the individual [Kuma](apps/uptime-kuma.md) and [Hermes](apps/hermes.md) guides for usage, credentials, configuration and operations.

Final verification: reapplying both new roles completed with `changed=0`, no failed tasks, and qBittorrent remained stopped. Collected a 30-second per-app resource snapshot with the downloader explicitly omitted; Kuma used about 119.8 MiB working RAM and Hermes 264.6 MiB in that initial window. Their average CPU use was about 0.0212 and 0.0199 logical CPUs respectively. See [resources](resources.md) for the scope and limitations.

Removed `/etc/sudoers.d/99-codex-setup`, cleared the sudo timestamp and verified noninteractive sudo is denied. The Hermes CLI wrapper uses normal sudo authentication afterward.

On 22 November 2026, added the existing saved Kuma account to `/opt/media-stack/admin-credentials.json` under `uptime-kuma`, retaining the dedicated file. Verified the copies match, the other nine app entries remain and the main file remains owned by `argus` with mode `0600`. Updated the role to add a missing central Kuma entry after setup without overwriting existing entries. No app password was reset.


## Homarr shortcuts and Hermes browser interface

On 22 November 2026, added Uptime Kuma and Hermes Agent app records and board tiles through Homarr's authenticated APIs. Both tiles have desktop/mobile placement, open in a new tab and retain the existing private board. Readback verified existing items were unchanged; a second run added no duplicate tiles. Added a reproducible helper to the server-apps playbook.

The user selected a password-protected Hermes web interface instead of an SSH-only shortcut. Prepared `webapp.enabled`, port 9120, home-network public URL and the supported wildcard bind for the pinned release. Configured the built-in password provider with generated credentials and a persistent signing secret, preserving the existing model settings and private API. Saved the GUI account in the main credentials file under `hermes` and in the private Hermes data directory. The opt-in and helpers are recorded in Ansible. The user recreated the Hermes container to apply the new environment. Verified the Webapp root redirects to login, anonymous configuration access and an invalid password are rejected with `401`, the saved password succeeds, and authenticated configuration access returns `200`. Logged out the diagnostic session. Kuma and Hermes login URLs respond successfully, and the raw API still requires its bearer key. No public Cloudflare route was added.


## qBittorrent download recovery and source replacements

On 22 November 2026, authenticated successfully to the running qBittorrent v5.3.0 service and found two long-stalled metadata jobs occupying two of three download slots. Enabled `dont_count_slow_torrents` through the API and added that preference to first-run bootstrap. Kept the existing active limits, slow thresholds, storage paths and speed settings. Season 3 and 4 sources connected and transferred data; the existing movie also had many reachable seeds and was retained. Its pre-existing force-start flag was preserved.

Knaben searches worked, but its HTTP download endpoint returned `501` and Prowlarr backed off. Enabled **Prefer Magnet URL**, tested both Prowlarr and Sonarr indexer connections, verified a fresh magnet redirect, and successfully submitted three individual test releases through Sonarr.

Replaced The Lincoln Lawyer S02E01, S02E03 and S02E05 sources with the verified `The Lincoln Lawyer S02 1080p WEBRip x265` season pack, selecting only those three files. It had four connected complete seeds and about 122 KB/s at selection. Individual PSA alternatives for E01/E03 were much slower; the MeGusta E05 alternative could not retrieve metadata during the test. Removed those three test entries after comparison and cleared their temporary force-start flags. The pack remains subject to normal queue limits. S02E10 had reachable seeds and received data, so it was retained.

Removed the original stalled entries with file deletion disabled, blocklisted those original releases in Sonarr, and preserved their partial payloads. Removed the temporary comparison entries without blocklisting or deleting their files. Sonarr tracks the final season-pack replacement, reports no health warnings, and retains all 16 previously imported episodes. Private source backups, probe results and byte-counter measurements are under `/opt/media-stack`; no provider keys or magnets were added to the repo. Download completion and later import of these replacements remain pending.

Final 30-second sample ending **22 November 2026, 22:55:19 IST** received **256.2 MB** in total, averaging **8.54 MB/s**: season 3 about 3.61 MB/s, the existing movie 4.88 MB/s, S02E10 33 KB/s and the replacement season 2 pack 16 KB/s. Season 4 was queued under the retained limits and had transferred data earlier. The replacement had five connected seeds, but speed remained variable and low; no completion estimate is established. All temporary test force-start flags were cleared. Bootstrap Python syntax and `git diff --check` passed.

# Audiobookshelf

Audiobookshelf runs on the Alienware at
[http://192.168.1.243:13378](http://192.168.1.243:13378). The playbook sets up
a Homarr shortcut and adds a Kuma HTTP monitor on `/healthcheck`.

Run the playbook from `ansible` after the media stack, Homarr, and Uptime
Kuma are installed:

```bash
ansible-playbook playbooks/audiobookshelf.yml --ask-become-pass
```

The playbook creates the root account over loopback and verifies login before
opening the LAN listener. The generated `admin` account is stored under
`audiobookshelf` in the existing `/opt/media-stack/admin-credentials.json`.
Reruns reuse that account. The container uses UID/GID 1000 and stores its
database and metadata on the boot SSD under `/opt/audiobookshelf`.

## Library paths

| Library | Alienware HDD | Container |
| --- | --- | --- |
| Audiobooks | `/srv/media/library/audiobooks` | `/audiobooks` |
| Podcasts | `/srv/media/library/podcasts` | `/podcasts` |

Keep a book's files together in a folder such as
`/srv/media/library/audiobooks/Author/Book/`. Audiobookshelf watches the
library path, and **Scan** is available from the library menu.

## Using the ARR stack

[Listenarr](listenarr.md) automates completed-file imports from the existing
Prowlarr and qBittorrent setup into the Audiobooks library.

Audiobookshelf catalogs and plays files from the library folder. The existing
Sonarr, Radarr, and Lidarr instances manage television, films, and music.
The Servarr project retired Readarr, its former book and audiobook manager.
[Servarr retirement announcement](https://wiki.servarr.com/en/readarr/supported)

Use Prowlarr's `Audio/Audiobook` category for a manual search. Knaben and
The Pirate Bay advertise that category in the current configuration. Use the
existing qBittorrent client to download the release.
After completion, copy or hardlink the finished book into the Audiobooks
library on the same HDD. This leaves any active torrent path intact and
keeps partial downloads out of the catalog. Audiobookshelf then scans the
library. Podcast subscriptions and downloads are managed in Audiobookshelf.

Back up `/opt/audiobookshelf/config`, `/opt/audiobookshelf/metadata`, and
the relevant shared credential entry. Keep the media folders in the HDD
backup plan. [Audiobookshelf Docker storage guide](https://audiobookshelf.org/docs/documentation/install/docker/)

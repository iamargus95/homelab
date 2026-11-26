# Listenarr

[Listenarr](http://192.168.1.243:4545) searches Prowlarr's audiobook sources,
sends selected releases to qBittorrent, and organizes completed downloads for
Audiobookshelf. The playbook pins a canary image because upstream currently
publishes canary releases. [Installation guide](https://getlistenarr.com/docs/getting-started/installation/)

```bash
cd ansible
ansible-playbook playbooks/listenarr.yml --ask-become-pass
```

The playbook configures authentication over loopback before opening the
LAN listener. The generated `admin` credentials are under `listenarr` in
`/opt/media-stack/admin-credentials.json`. Homarr opens the LAN URL and Kuma
checks `/api/v1/system/ready`.

Listenarr and qBittorrent see the HDD at `/data` in Docker. The dedicated
`audiobooks` qBittorrent category saves to `/data/downloads/torrents/audiobooks`.
Listenarr imports to `/data/library/audiobooks` with **Hardlink/Copy**. It
prefers hardlinks and can copy when a hardlink is unavailable. Audiobookshelf
then picks up the organized files from its Audiobooks library.

Prowlarr provides the Torznab feeds for Knaben and The Pirate Bay. The
bootstrap tests each before adding it with category `3030` (Audio/Audiobook).
Add a book in Listenarr to start a search. Check **Activity** for the download
and import result and confirm the finished title appears in Audiobookshelf.
[Listenarr quick start](https://getlistenarr.com/docs/getting-started/quick-start/)

Back up the persistent `/opt/listenarr/config` directory privately. It contains
the database and settings used to connect to the other services.

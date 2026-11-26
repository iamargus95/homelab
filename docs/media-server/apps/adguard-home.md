# AdGuard Home

[Documentation home](../README.md) · [AdGuard Home setup guide](https://adguard-dns.io/kb/adguard-home/getting-started/)

The [AdGuard Home playbook](../../../ansible/playbooks/adguard-home.yml) provides DNS filtering on `192.168.1.243:53` over UDP and TCP. The [admin console](http://192.168.1.243:3080) uses the `adguard-home` entry in `/opt/media-stack/admin-credentials.json`. AdGuard Home sends upstream queries to Quad9 over HTTPS. Its persistent configuration and work directories are under `/opt/adguard-home`. The private [Homarr board](http://192.168.1.243:7575/boards/homelab) links to the admin console. [Uptime Kuma](http://192.168.1.243:3001) checks that AdGuard Home can resolve the A record for `example.org` on port 53.

The ISP router continues to provide DHCP. Set the DNS server to `192.168.1.243` in each device's Wi-Fi or Ethernet settings and leave its IP address and gateway on DHCP where the device supports separate DNS settings. Configure a second DNS address only when there is a second filtering resolver to use. Restore automatic DNS on a device if the Alienware becomes unavailable.

To verify the resolver from a LAN client, run:

```bash
dig @192.168.1.243 example.org A +short
dig @192.168.1.243 example.org A +short +tcp
dig @192.168.1.243 ad.doubleclick.net A +short
```

The first two queries should return public IP addresses. The advertising domain should return `0.0.0.0`. After configuring a device, check its requests in AdGuard Home's Query Log. Apps using their own encrypted DNS can bypass the system's resolver.

## Web, app, and TV filtering

The playbook enables [HaGeZi Pro, Samsung Tracker, and LG webOS Tracker](https://github.com/hagezi/dns-blocklists) alongside the default AdGuard DNS filter. The supplemental lists cover web and app ad networks plus device telemetry hosts. To investigate a playback issue, look up the affected client's requests in Query Log and identify the exact hostname and matching rule.

LAN checks confirmed that ad and telemetry hosts for DoubleClick, Amazon Ads, Taboola, InMobi, Vungle, SpotX, Samsung, LG, Samba TV, and Roku were blocked. Sampled YouTube, Netflix, Prime Video, JioHotstar, Disney+, Twitch, and Spotify service endpoints resolved. These checks cover DNS behavior and public page access. Signed-in playback and ad insertion in native apps require a client test.

DNS filtering cannot distinguish ads from playback when they share a hostname. Browser content blockers can filter web requests and page elements at a finer level.

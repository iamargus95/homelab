# Internet speed and availability

[Speedtest Tracker](https://docs.speedtest-tracker.dev/) runs Ookla tests from
the Alienware and stores download, upload, and latency history in SQLite. The
default schedule runs four tests per day at 00:17, 06:17, 12:17, and 18:17 IST.
It also supports on-demand tests from the dashboard.

Deploy after Uptime Kuma and the private Homarr board are configured:

```bash
cd ansible
ansible-playbook playbooks/internet-monitoring.yml --ask-become-pass
```

Open the **Speedtest Tracker** tile in Homarr or visit
[Speedtest Tracker](http://192.168.1.243:8765) on the home network. Use
`admin@example.com` and retrieve the generated initial password privately:

```bash
ssh -t alienware 'sudo sed -n "s/^ADMIN_PASSWORD=//p" /opt/speedtest-tracker/.env'
```

The playbook adds three monitors to the existing private Kuma instance:

| Monitor | Target |
| --- | --- |
| Speedtest Tracker | The application's LAN health endpoint |
| Internet - Cloudflare | HTTPS check to `1.1.1.1` by IP |
| Internet - Google | HTTPS check to `www.gstatic.com` expecting HTTP 204 |

The WAN probes run once per minute. Compare both timelines when diagnosing a
drop. A failure on one path can be specific to that provider or, for Google,
DNS. Outages while the Alienware or Kuma is off require a monitor outside the
home network to observe.

Back up `/opt/speedtest-tracker/config` and the root-only
`/opt/speedtest-tracker/.env` together. The latter holds the database
encryption key and bootstrap credentials. Stop the Compose project for a
consistent filesystem backup, then start it again.

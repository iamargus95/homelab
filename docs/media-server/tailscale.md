# Private access with Tailscale

[Documentation home](README.md) · [Editable Draw.io architecture](homelab-architecture.drawio)

The Alienware runs Tailscale as a host systemd service and advertises
`192.168.1.243/32`. Tailscale clients use that route to reach the existing
LAN-bound apps at their usual addresses. The route covers one server. VPN
connections use WireGuard with a direct connection where possible and an
encrypted relay when needed. The ISP router requires no port forwarding.

| Service | Address on the LAN or tailnet |
| --- | --- |
| Homarr | [192.168.1.243:7575/boards/homelab](http://192.168.1.243:7575/boards/homelab) |
| Jellyfin | [192.168.1.243:8096](http://192.168.1.243:8096) |
| SSH | `ssh alienware` with the existing local alias, or `ssh argus@192.168.1.243` |

Use the existing SSH host key and account credentials. The current tailnet has
one owner and its policy allows all ports between tailnet devices. Review that
policy before admitting additional users or devices. If sharing Jellyfin,
restrict that audience to TCP 8096 and keep admin access limited to the owner.
Route approval applies independently of access policy. App logins still apply,
and the Cloudflare Jellyfin hostname currently returns HTTP 403.

## Provision or restore

1. While on the LAN, verify the server address is still `192.168.1.243`.
   The media bindings and Tailscale route depend on it. Reserve the address in
   DHCP if the router supports reservations.
2. Run the dedicated playbook from the repository root.

   ```bash
   ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook \
     -i ansible/inventory/alienware.yml ansible/playbooks/tailscale.yml -K
   ```

   The playbook installs the vendor package and signing key, persists IPv4
   forwarding, and enables `tailscaled`. On an enrolled host it sets the
   advertised route to the inventory host's `/32` and allows incoming
   traffic from the tailnet. It manages the full list of advertised routes on
   this host. Use a LAN SSH session for route changes.
3. For a fresh install, review the tailnet's access policy first. On the
   Alienware, run `sudo tailscale up --shields-up` and authenticate in the
   browser as the owner. Rerun the playbook to apply the local route
   configuration. Enrollment uses an interactive login. Keep login URLs,
   enrollment keys and daemon state out of Git.
4. In the [Tailscale Machines console](https://login.tailscale.com/admin/machines),
   open the Alienware's **Edit route settings**, select `192.168.1.243/32` and
   save. Install Tailscale on each remote client and join the same tailnet.
   Linux clients need `sudo tailscale set --accept-routes=true` to use subnet
   routes. On macOS, enable **Use Tailscale subnets** if it was turned off.

## Verify and troubleshoot

On the Mac, check that the route uses a Tailscale tunnel interface before
testing from a home Wi-Fi connection.

```bash
route -n get 192.168.1.243
tailscale ping alienware
ssh alienware hostname
curl -fsS http://192.168.1.243:8096/health
curl -fsSL -o /dev/null -w '%{http_code}\n' http://192.168.1.243:7575/boards/homelab
```

On 26 November 2026, the Mac selected a `utun` interface for this route. SSH
returned `alienware`, Jellyfin returned `Healthy`, and Homarr returned HTTP 200
after redirecting to its login page. Mobile-data playback is still unverified.
To test it, turn off Wi-Fi on a phone connected to the tailnet and start a
Jellyfin video using the address above.

If a client can see the Alienware but cannot open apps, check that the route
is approved, the client accepts it, and the server address and app listeners
still match the inventory. If a remote stream buffers, use `tailscale ping
alienware` to distinguish a direct connection from a relayed one. Check device
key expiry in the Machines console if a previously working route stops.

For a rollback, disable the approved `/32` in the Machines console. To withdraw
the advertisement and block incoming tailnet connections to the Alienware,
run the following from a LAN or console session.

```bash
sudo tailscale set --advertise-routes= --shields-up=true
```

The next playbook run restores the configured route on an enrolled server.

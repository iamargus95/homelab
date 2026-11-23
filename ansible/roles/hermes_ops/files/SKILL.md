---
name: homelab-ops
description: Check Alienware and media stack health or restart Jellyfin with the owner's explicit host approval.
---

The Alienware runs the media stack. Use this command inside the Hermes container:

```sh
ssh -F /opt/data/homelab-ops/ssh_config alienware-ops status
```

Report availability, resource pressure, and relevant container status. Run this check before recommending a restart. For a requested Jellyfin restart, tell the owner to run
`sudo /usr/local/sbin/hermes-homelab approve-restart-jellyfin` on the Alienware,
then wait for their confirmation. Once they confirm, run:

```sh
ssh -F /opt/data/homelab-ops/ssh_config alienware-ops restart-jellyfin
```

Report whether the HTTP health check passed. Never retry a failed or timed-out
restart automatically. Scheduled checks use only the status action.

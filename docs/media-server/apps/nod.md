# Nod on the Alienware

[Documentation home](../README.md) · [Upstream self-hosting guide](https://nod.n8n.io/docs/deploy/self-host/)

Nod uses its own Docker Compose project with PostgreSQL, a browser, and an isolated workspace. The [Ansible playbook](../../../ansible/playbooks/nod.yml) builds the upstream stack from a pinned revision under `/opt/nod`. Docker keeps the named volumes on the boot SSD and restarts the containers when Docker starts.

## Deploy or reapply

From the repository's `ansible` directory, run:

```bash
ansible-playbook playbooks/nod.yml --ask-become-pass
```

The first build downloads the Node.js, browser, and workspace dependencies. The playbook verifies the loopback UI and token requirement, adds the Nod tile to the private Homarr board, and configures a Kuma HTTP monitor. Only the Nod server joins Kuma's existing Docker network. The monitor checks the web page once a minute without credentials. The upstream Docker health check separately verifies the database through the authenticated health endpoint.

## Open Nod and connect a model

Keep this SSH tunnel open whenever you use Nod:

```bash
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:4310:127.0.0.1:4310 alienware
```

Open [http://localhost:4310](http://localhost:4310) or click **Nod** in Homarr. In a private terminal, retrieve the access token:

```bash
ssh -t alienware "sudo sed -n 's/^NOD_AUTH_TOKEN=//p' /opt/nod/src/deployment/self-host/.env"
```

Paste the token into Nod's access form. For the same provider as Hermes, choose **OpenAI → Sign in with ChatGPT** during onboarding. If the final browser address fails to load, copy that full address into Nod's **Callback URL** field and select **Complete sign-in**. Keep the access token and callback URL private. [Nod model setup](https://nod.n8n.io/docs/connect/models/#connect-a-service)

## Backups and operations

The upstream `.env` holds the access token, database password, and Vault key. The setup script preserves them on reruns. Keep a private backup of that file along with Nod's data. The upstream backup script briefly stops parts of the stack, so schedule it for a quiet period. [Nod backup and update guide](https://nod.n8n.io/docs/deploy/server-operations/)

Use the Ansible playbook to reapply the stack. For container status on the host, include the monitoring overlay:

```bash
cd /opt/nod/src/deployment/self-host
docker compose -f compose.yaml -f /opt/nod/monitoring.compose.yml ps
```

Run the status command from a root shell on the Alienware. Keep the loopback port binding and the upstream workspace firewall in place.

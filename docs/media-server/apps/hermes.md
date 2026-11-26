# Hermes Agent on the Alienware

[Documentation home](../README.md) · [Setup](../setup.md)

This is **Nous Research's Hermes Agent runtime**, using **OpenAI Codex / ChatGPT subscription sign-in** for inference. A Nous Portal account is not required. It runs in its own Docker Compose project, separate from the media stack.

| Setting | Value |
| --- | --- |
| Image | `nousresearch/hermes-agent:v0.23.3` (official Docker Hub image) |
| Observed digest | `sha256:3e9fe4c6ef36490f43aa0d0d80f9df64e9c92a576eee3042f1a97c8813c05355` |
| Compose project | `/opt/hermes/compose.yml` |
| Container | `hermes-agent` |
| Host CLI wrapper | `/usr/local/bin/hermes` |
| Persistent state | `/opt/hermes/data` on host → `/opt/data` in container |
| Runtime user | Image's `hermes` user remapped to UID/GID `1000:1000` |
| Provider | `openai-codex` |
| Initial model | `gpt-6-sol`; choose another entitled model with `hermes model` |
| Webapp URL | [http://192.168.1.243:9120](http://192.168.1.243:9120) |
| Webapp account | `admin`; main credentials file entry `hermes` |
| API listener | `127.0.0.1:8642`, generated bearer key in `/opt/hermes/data/.env` |
| Restart | Docker `unless-stopped`; gateway supervised by upstream s6 |

The image starts its initialization/supervisor as root, then runs Hermes as the remapped normal user. It has no Docker socket, host-home mount, media mount or GPU device. Linux host networking allows both the private API and a temporary Codex loopback OAuth callback to work through SSH; it does not give the container access to the host filesystem. API binding remains loopback. The built-in Webapp is enabled for home-network access with password authentication. Slack uses Socket Mode. The web interface stays on the home network.

## Browser access from Homarr

The Homarr tile opens the built-in Webapp on port `9120`. It uses the username/password provider, separate from ChatGPT/Codex model authentication. The account is saved under `hermes` in `/opt/media-stack/admin-credentials.json`, with its dedicated copy at `/opt/hermes/data/admin-credentials.json`; both are private mode `0600`. The `.env` also holds a persistent session-signing secret. Passwords are not embedded in Homarr links.

The pinned release accepts a loopback or wildcard bind, so `webapp.host` is `0.0.0.0` with the home-network URL `http://192.168.1.243:9120`. A non-loopback listener requires authentication. The raw API remains at `127.0.0.1:8642`. This is trusted-home-network HTTP access; no public DNS/tunnel route or router forwarding was added.

`hermes_docker_webapp_enabled: true` opts the Alienware into the [Webapp helper](../../../ansible/roles/hermes_docker/files/configure-webapp.py). It preserves model/auth settings and existing service credentials while creating the Webapp password once. The prepared settings need a container recreation to load the new environment:

```bash
ssh -t alienware 'sudo docker compose --project-directory /opt/hermes up -d --force-recreate hermes'
```

The container was recreated and the Webapp is active. Verified the root redirects anonymous visitors to `/login`, unauthenticated configuration requests and invalid passwords return `401`, the saved web password is accepted, and authenticated configuration requests return `200`. The diagnostic login was logged out afterward. The Homarr app tile opens this interface.

## Sign in with your ChatGPT/Codex account

Run this in your own terminal:

```bash
ssh -t alienware 'hermes model'
```

The wrapper uses the server's normal sudo authentication to enter the container; enter your Ubuntu sudo password if prompted. Choose **ChatGPT or Codex Subscription** and follow the device-code sign-in. Alternatively, start only the provider login:

```bash
ssh -t alienware 'hermes auth add openai-codex'
```

Do not paste passwords or tokens into chat. Hermes stores its own login at `/opt/hermes/data/auth.json` on the host. `auth.adopt_external_logins` is disabled, and no desktop Codex credentials were copied. The official Docker CLI shim runs commands as the same user as the gateway, preserving ownership of auth files. Model access depends on your account; use the model picker if the initial default is unavailable.

For an organization that disables device-code login, forward the fixed browser callback port in one local terminal:

```bash
ssh -N -L 1455:127.0.0.1:1455 alienware
```

In another terminal:

```bash
ssh -t alienware 'hermes auth add openai-codex --browser'
```

Open the printed authorization URL locally. Host networking makes the container's loopback callback reachable through that SSH forward. After signing in, restart the gateway container so it loads the selected provider/model, then start a chat:

```bash
ssh -t alienware 'sudo docker compose --project-directory /opt/hermes restart'
ssh -t alienware 'hermes chat'
```

The live instance uses ChatGPT/Codex sign-in. Set up your own provider login when restoring from empty state. The gateway's local bearer key is separate from ChatGPT authentication.

## Operations and verification

```bash
ssh -t alienware 'sudo docker compose --project-directory /opt/hermes ps'
ssh -t alienware 'hermes --version'
ssh -t alienware 'hermes doctor'
```

Verified gateway `/health` returns `200`; `/v1/models` rejects absent/invalid bearer keys with `401` and returns `200` with the generated key. These are runtime/authentication checks, not an authenticated model-inference test. Its listener is on loopback, not the LAN. No full reboot test was performed.

The [Docker role](../../../ansible/roles/hermes_docker/tasks/main.yml) creates private state, configures the Codex provider and API key, renders Compose and installs the CLI wrapper. The CLI wrapper uses the operator's sudo credentials. The separate operations role grants fixed diagnostic actions and an approved Jellyfin restart to its dedicated SSH account. Configuration and auth use mode `0600`; the data directory uses `0700`. Back up state privately. Container logs rotate at 10 MB with three retained files.

The official image includes its dependencies and avoids rebuilding the Python runtime over this network's slow PyPI route. Slack DMs are working. Scheduled reports have not been configured. CPU and memory are shared without explicit quotas; see [resources](../resources.md).

Sources: [official Docker guide](https://hermes-agent.nousresearch.com/docs/user-guide/docker), [provider authentication](https://hermes-agent.nousresearch.com/docs/integrations/providers).

## Slack setup and recovery

The Homelab workspace uses a Slack app with Socket Mode. To rebuild the
integration, run `hermes slack manifest --write` on the Alienware and import
`/opt/hermes/data/slack-manifest.json` into the Slack app configuration.
Install the app in the workspace and set these values privately in
`/opt/hermes/data/.env`:

- `SLACK_BOT_TOKEN` from the installed workspace app (`xoxb-`).
- `SLACK_APP_TOKEN` with `connections:write` (`xapp-`).
- `SLACK_ALLOWED_USERS` with your Slack member ID.

Recreate Hermes with the Compose command above so it receives the updated
environment. Check `/opt/hermes/data/logs/agent.log` for the Slack authentication
and Socket Mode messages, then send a DM to verify delivery. Do not copy the
configuration or tokens into the repository.

On v0.23.3, if the CLI reports the Docker image is out of sync because pnpm is
missing, run `hermes pm install pnpm && hermes --version` on the Alienware.

## Homelab operations from Slack

Deploy the operations role from the repository's `ansible` directory:

```bash
ansible-playbook -i inventory/alienware.yml playbooks/hermes-ops.yml --ask-become-pass
```

The playbook verifies the read-only action from inside the running Hermes
container. In your private Hermes Slack DM, ask it to use the `homelab-ops`
skill to check the Alienware or investigate a service error. The status action
reports host uptime, memory, storage, monitored container states, and Jellyfin
HTTP health.

Ask for an excerpt from a named service, such as `logs jellyfin`. The allowlist
covers the monitored application containers, including Kuma, and the SSH,
Docker, and kernel journals. WAN probes are handled by Kuma. Each excerpt is
limited to the last two hours, up to 120 lines and 24 KB before redaction.
The helper removes URL queries and lines matching common credential patterns.
It accepts service names and reads the selected journal or container log.

For a restart, approve one action on the Alienware and then tell Hermes
to execute it in the Slack DM within five minutes:

```bash
sudo /usr/local/sbin/hermes-homelab approve-restart-jellyfin
```

Approval is consumed before the restart. Hermes reports whether Jellyfin's
HTTP health check recovered. Verify scheduled diagnostics independently before
adding a recurring Slack report.

## Repository changes from Slack

In `#hermes-agent`, mention Hermes and ask it to use `homelab-repo` for an
explicit repository task. For a private request, use the existing Hermes DM.
For example, ask it to make a specific Ansible change on a branch, run the
relevant checks, and push the branch. The skill asks Hermes to report the
branch, commit, and verification results. Pushing a branch does not deploy it.

The Alienware checkout is `/opt/hermes/data/workspace/homelab`, visible to
Hermes at `/opt/data/workspace/homelab`. It tracks the public GitHub repository.
Changes on another machine are visible to Hermes after they are pushed and it
fetches them. Use the `homelab-ops` skill for live service checks and the
[operations guide](../operations.md) for backup and recovery procedures.

Git uses the repository's write-enabled `Hermes on Alienware` deploy key.
Its private half and pinned host key are under `/opt/hermes/data/homelab-git`.
For a rebuild, restore them privately with the checkout or generate a new key
pair, register its public half as a write-enabled deploy key, and restore the
checkout's `core.sshCommand` with the container paths. The operations playbook
installs the repository skill when the checkout is present. Delete the deploy
key in GitHub if Hermes's push access needs to be revoked.

## Alienware power alerts

The existing Hermes job **Alienware power and battery alerts** runs
`alienware-power-watch.py` once a minute in script-only mode and sends alerts
to the operator's private Slack DM. The script reads Linux power-supply
status and emits a message when mains power is disconnected and when the
battery reaches 20% or lower during that outage. Reconnecting power resets
both alerts.

The operations playbook installs the script under `/opt/data/scripts` in
Hermes. When rebuilding from empty Hermes state, recreate the interval job
with this script and the operator's private Slack destination. The delivery
destination and prior alert state live in Hermes's private persistent data.

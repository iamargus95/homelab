# Homelab v2 — Immich + Slim Mediastack — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove *arr apps from the mediastack container, add a 200G ZFS reservation for media, migrate AdGuard from pve2 → pve1, and stand up Immich (Docker-in-LXC) on pve2 with a nightly ZFS-send backup to pve1 at 03:00 IST.

**Architecture:** Two-node Proxmox cluster. pve1 hosts AdGuard (NVMe local-lvm) + Jellyfin + Transmission + Immich-backup dataset (all on `zfs-pve-1`/sda). pve2 becomes a dedicated Immich host on `zfs-pve-2`/sda. Docker Compose inside an unprivileged LXC uses `fuse-overlayfs` so all Immich state lives under a single bind-mounted ZFS dataset — making atomic nightly snapshot+send possible.

**Tech Stack:** OpenTofu 1.6+ (bpg/proxmox provider 0.66+), Ansible (community.proxmox.proxmox_pct_remote connection), ZFS, Docker CE, Immich Compose (pinned), Tailscale, GitHub Actions CI/CD.

**Spec reference:** `docs/superpowers/specs/2026-04-17-homelab-v2-immich-design.md`

---

## Phase structure

- **Phase 0** — Repo scaffolding for the new roles/playbooks
- **Phase 1** — ZFS dataset + reservation Ansible
- **Phase 2** — Rename mediastack → transmission + gut arr apps
- **Phase 3** — AdGuard migration wiring (export play + role restore + terraform node change)
- **Phase 4** — Immich LXC (Terraform module + Ansible role + Docker compose)
- **Phase 5** — Immich backup pipeline (role + script + cron)
- **Phase 6** — Cross-node SSH key setup (pve2 → pve1 for zfs-send)
- **Phase 7** — Inventory, outputs, site.yml, vault wiring
- **Phase 8** — Docs: README + drawio + status.sh
- **Phase 9** — Deployment execution (run the actual migration)
- **Phase 10** — Post-deploy verification

Each phase ends with a commit. Phases 0–8 are code changes on a branch; Phase 9 is the live migration.

---

## Phase 0: Branch + file skeletons

### Task 0.1: Create feature branch

- [ ] **Step 1: Create and switch to a new branch**

```bash
cd /Users/surajkamath/workspace/personal/src/homelab
git checkout -b feat/homelab-v2-immich
```

Expected: `Switched to a new branch 'feat/homelab-v2-immich'`

### Task 0.2: Create empty directories for new roles

- [ ] **Step 1: Create directories**

```bash
mkdir -p ansible/roles/immich/tasks \
         ansible/roles/immich/templates \
         ansible/roles/immich/handlers \
         ansible/roles/immich-backup/tasks \
         ansible/roles/immich-backup/templates \
         ansible/roles/zfs-immich/tasks \
         backups
```

- [ ] **Step 2: Add backups/ to .gitignore**

Edit `/Users/surajkamath/workspace/personal/src/homelab/.gitignore`, append:

```
# AdGuard migration config backups (pre-destroy/recreate)
/backups/
```

- [ ] **Step 3: Commit scaffolding**

```bash
git add .gitignore ansible/roles/immich ansible/roles/immich-backup ansible/roles/zfs-immich
git commit -m "scaffold: directories for immich, immich-backup, zfs-immich roles"
```

---

## Phase 1: ZFS datasets and reservations

### Task 1.1: Extend zfs-media role with reservation + immich-backup dataset

- [ ] **Step 1: Replace `ansible/roles/zfs-media/tasks/main.yml`**

Full replacement contents of `/Users/surajkamath/workspace/personal/src/homelab/ansible/roles/zfs-media/tasks/main.yml`:

```yaml
---
- name: Create ZFS media datasets
  ansible.builtin.command: "zfs create -p {{ zfs_pool }}/media/{{ item }}"
  loop:
    - movies
    - tv
    - downloads
    - videos
  register: zfs_result
  changed_when: zfs_result.rc == 0
  failed_when: zfs_result.rc != 0 and 'dataset already exists' not in (zfs_result.stderr | default(''))

- name: Apply reservation to media dataset (guarantees 200G for media even if pool fills)
  ansible.builtin.command: "zfs set reservation=200G {{ zfs_pool }}/media"
  changed_when: false

- name: Create immich-backup dataset (target of pve2 → pve1 zfs send)
  ansible.builtin.command: "zfs create {{ zfs_pool }}/immich-backup"
  register: immich_backup_result
  changed_when: immich_backup_result.rc == 0
  failed_when: >-
    immich_backup_result.rc != 0
    and 'dataset already exists' not in (immich_backup_result.stderr | default(''))

- name: Set media directory ownership
  ansible.builtin.file:
    path: "{{ media_dir }}"
    owner: "101000"
    group: "101000"
    mode: "0775"
    recurse: yes

- name: Ensure subuid mapping for media user
  ansible.builtin.lineinfile:
    path: /etc/subuid
    line: "root:101000:1"
    state: present

- name: Ensure subgid mapping for media group
  ansible.builtin.lineinfile:
    path: /etc/subgid
    line: "root:101000:1"
    state: present
```

- [ ] **Step 2: Verify `media_dir` and `zfs_pool` are defined in the pve1 inventory vars**

```bash
grep -E "media_dir|zfs_pool" ansible/inventory/hosts.yml.example
```

Expected output includes:
```
zfs_pool: zfs-pve-1
media_dir: /zfs-pve-1/media
```

### Task 1.2: Create zfs-immich role for pve2 dataset

- [ ] **Step 1: Create `ansible/roles/zfs-immich/tasks/main.yml`**

Full contents:

```yaml
---
- name: Create Immich ZFS dataset on pve2
  ansible.builtin.command: "zfs create {{ immich_zfs_pool }}/immich"
  register: immich_dataset
  changed_when: immich_dataset.rc == 0
  failed_when: >-
    immich_dataset.rc != 0
    and 'dataset already exists' not in (immich_dataset.stderr | default(''))

- name: Apply 100G reservation to immich dataset
  ansible.builtin.command: "zfs set reservation=100G {{ immich_zfs_pool }}/immich"
  changed_when: false

- name: Create Immich subdirs on the ZFS dataset
  ansible.builtin.file:
    path: "/{{ immich_zfs_pool }}/immich/{{ item }}"
    state: directory
    owner: root
    group: root
    mode: "0755"
  loop:
    - library
    - postgres
    - model-cache
```

### Task 1.3: Wire zfs-immich into host-setup.yml

- [ ] **Step 1: Replace `ansible/playbooks/host-setup.yml`**

Full contents of `/Users/surajkamath/workspace/personal/src/homelab/ansible/playbooks/host-setup.yml`:

```yaml
---
- name: Prepare Proxmox hosts
  hosts: pve_hosts
  become: yes
  tasks:
    - name: Download LXC template
      ansible.builtin.shell: |
        pveam update
        TEMPLATE=$(pveam available --section system | grep "ubuntu-22.04-standard" | awk '{print $2}' | head -1)
        pveam download local "$TEMPLATE" 2>&1 || true
      register: template_result
      changed_when: "'downloading' in (template_result.stdout | lower)"
      failed_when: false

- name: Prepare ZFS media storage on pve1
  hosts: pve1
  become: yes
  roles:
    - zfs-media

- name: Prepare ZFS immich storage on pve2
  hosts: pve2
  become: yes
  roles:
    - zfs-immich
```

- [ ] **Step 2: Add `immich_zfs_pool` var to hosts.yml.example under pve2**

Open `ansible/inventory/hosts.yml.example` and edit the `pve2:` block to match:

```yaml
        pve2:
          ansible_host: <PVE2_TAILSCALE_IP>
          ansible_user: root
          zfs_pool: zfs-pve-2
          immich_zfs_pool: zfs-pve-2
```

- [ ] **Step 3: Commit phase 1**

```bash
git add ansible/roles/zfs-media/tasks/main.yml \
        ansible/roles/zfs-immich/tasks/main.yml \
        ansible/playbooks/host-setup.yml \
        ansible/inventory/hosts.yml.example
git commit -m "feat(ansible): zfs reservations for media (200G) and immich (100G)"
```

---

## Phase 2: Rename mediastack → transmission + gut *arr apps

### Task 2.1: Rename Ansible role directory

- [ ] **Step 1: Git move the role**

```bash
cd /Users/surajkamath/workspace/personal/src/homelab
git mv ansible/roles/mediastack ansible/roles/transmission
```

- [ ] **Step 2: Verify directory structure**

```bash
ls ansible/roles/transmission/
```

Expected: `handlers/  tasks/  templates/`

### Task 2.2: Gut the transmission role (remove *arr + flaresolverr)

- [ ] **Step 1: Replace `ansible/roles/transmission/tasks/main.yml`**

Full contents:

```yaml
---
# Clean up legacy arr/flaresolverr services if upgrading from the old mediastack.
- name: Check for legacy services to remove
  ansible.builtin.stat:
    path: "/etc/systemd/system/{{ item }}.service"
  loop:
    - radarr
    - sonarr
    - prowlarr
    - flaresolverr
  register: legacy_services

- name: Stop and disable legacy services
  ansible.builtin.systemd:
    name: "{{ item.item }}"
    state: stopped
    enabled: no
  loop: "{{ legacy_services.results }}"
  loop_control:
    label: "{{ item.item }}"
  when: item.stat.exists
  failed_when: false

- name: Remove legacy systemd units
  ansible.builtin.file:
    path: "/etc/systemd/system/{{ item }}.service"
    state: absent
  loop:
    - radarr
    - sonarr
    - prowlarr
    - flaresolverr
  notify: reload systemd

- name: Remove legacy install directories
  ansible.builtin.file:
    path: "/opt/{{ item }}"
    state: absent
  loop:
    - radarr
    - sonarr
    - prowlarr
    - flaresolverr

- name: Remove legacy data directories
  ansible.builtin.file:
    path: "/var/lib/{{ item }}"
    state: absent
  loop:
    - radarr
    - sonarr
    - prowlarr

# --- Transmission ---
- name: Install Transmission
  ansible.builtin.apt:
    name: transmission-daemon
    state: present
    update_cache: yes

- name: Stop Transmission for configuration
  ansible.builtin.systemd:
    name: transmission-daemon
    state: stopped

- name: Create Transmission systemd override directory
  ansible.builtin.file:
    path: /etc/systemd/system/transmission-daemon.service.d
    state: directory

- name: Deploy Transmission systemd override
  ansible.builtin.template:
    src: transmission-override.conf.j2
    dest: /etc/systemd/system/transmission-daemon.service.d/override.conf
  notify: restart transmission

- name: Configure Transmission settings
  ansible.builtin.lineinfile:
    path: /etc/transmission-daemon/settings.json
    regexp: "{{ item.regexp }}"
    line: "{{ item.line }}"
  loop:
    - { regexp: '"rpc-authentication-required"', line: '    "rpc-authentication-required": true,' }
    - { regexp: '"rpc-username"', line: '    "rpc-username": "{{ transmission_user }}",' }
    - { regexp: '"rpc-password"', line: '    "rpc-password": "{{ transmission_pass }}",' }
    - { regexp: '"rpc-whitelist-enabled"', line: '    "rpc-whitelist-enabled": false,' }
    - { regexp: '"download-dir"', line: '    "download-dir": "{{ transmission_download_dir }}",' }
  notify: restart transmission

- name: Start Transmission
  ansible.builtin.systemd:
    name: transmission-daemon
    state: started
    enabled: yes
    daemon_reload: yes
```

- [ ] **Step 2: Slim down the handlers file**

Replace `ansible/roles/transmission/handlers/main.yml`:

```yaml
---
- name: reload systemd
  ansible.builtin.systemd:
    daemon_reload: yes

- name: restart transmission
  ansible.builtin.systemd:
    name: transmission-daemon
    state: restarted
    enabled: yes
    daemon_reload: yes
```

- [ ] **Step 3: Delete unused templates**

```bash
rm ansible/roles/transmission/templates/arr.service.j2
rm ansible/roles/transmission/templates/flaresolverr.service.j2
```

### Task 2.3: Rename + prune group_vars

- [ ] **Step 1: Rename and replace group_vars file**

```bash
git mv ansible/inventory/group_vars/mediastack.yml ansible/inventory/group_vars/transmission.yml
```

- [ ] **Step 2: Replace contents of `ansible/inventory/group_vars/transmission.yml`**

```yaml
# Transmission-specific variables

media_data_mount: /data

# Transmission auth (from vault)
transmission_user: "{{ vault_transmission_user }}"
transmission_pass: "{{ vault_transmission_pass }}"
transmission_download_dir: /data/downloads
```

### Task 2.4: Rename the playbook

- [ ] **Step 1: Git move the playbook**

```bash
git mv ansible/playbooks/mediastack.yml ansible/playbooks/transmission.yml
```

- [ ] **Step 2: Replace contents of `ansible/playbooks/transmission.yml`**

```yaml
---
- name: Configure Transmission container
  hosts: transmission
  become: yes
  vars_files:
    - ../vault.yml
  roles:
    - common
    - transmission
    - tailscale
```

### Task 2.5: Update inventory example

- [ ] **Step 1: Replace the `mediastack:` block in `ansible/inventory/hosts.yml.example`**

Before:
```yaml
        mediastack:
          hosts:
            ct102:
              ansible_host: <PVE1_TAILSCALE_IP>
              proxmox_vmid: 102
```

After (note indentation matches sibling groups):
```yaml
        transmission:
          hosts:
            ct102:
              ansible_host: <PVE1_TAILSCALE_IP>
              proxmox_vmid: 102
```

### Task 2.6: Rename Terraform file + module

- [ ] **Step 1: Rename `terraform/mediastack.tf` → `terraform/transmission.tf`**

```bash
git mv terraform/mediastack.tf terraform/transmission.tf
```

- [ ] **Step 2: Replace contents of `terraform/transmission.tf`**

```hcl
module "transmission" {
  source = "./modules/lxc-container"

  vmid         = 102
  hostname     = "transmission"
  target_node  = "pve1"
  cores        = 2
  memory       = 2048
  disk_size    = 15
  storage_pool = "zfs-pve-1"
  template_id  = var.template_id
  bridge       = var.bridge
  dns_servers  = var.dns_servers
  password     = var.container_password
  pve_ssh_host = var.pve1_ssh_host

  mountpoints = [
    {
      host_path      = "/zfs-pve-1/media"
      container_path = "/data"
    }
  ]

  extra_lxc_config = [
    # TUN device for Tailscale
    "lxc.cgroup2.devices.allow: c 10:200 rwm",
    "lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file",
    # UID/GID mapping for shared media access
    "lxc.idmap: u 0 100000 1000",
    "lxc.idmap: g 0 100000 1000",
    "lxc.idmap: u 1000 101000 1",
    "lxc.idmap: g 1000 101000 1",
    "lxc.idmap: u 1001 101001 64535",
    "lxc.idmap: g 1001 101001 64535",
  ]
}
```

### Task 2.7: Update terraform outputs.tf

- [ ] **Step 1: Replace `terraform/outputs.tf`**

```hcl
output "jellyfin" {
  description = "Jellyfin container details"
  value = {
    id       = module.jellyfin.container_id
    hostname = module.jellyfin.hostname
  }
}

output "transmission" {
  description = "Transmission container details"
  value = {
    id       = module.transmission.container_id
    hostname = module.transmission.hostname
  }
}

output "adguard" {
  description = "AdGuard container details"
  value = {
    id       = module.adguard.container_id
    hostname = module.adguard.hostname
  }
}

output "immich" {
  description = "Immich container details"
  value = {
    id       = module.immich.container_id
    hostname = module.immich.hostname
  }
}
```

### Task 2.8: Create terraform state migration script

- [ ] **Step 1: Create `scripts/migrate-state.sh`**

Full contents:

```bash
#!/bin/bash
# One-shot Terraform state migration for homelab-v2 rename.
# Renames module.mediastack -> module.transmission in the remote state so
# Terraform doesn't try to destroy+recreate CT 102.
#
# Idempotent: if module.mediastack is not present, does nothing.
#
# Prereqs: backend env vars (GITHUB_TOKEN) exported so terraform init succeeds.

set -euo pipefail
cd "$(dirname "$0")/.."

cd terraform
terraform init -reconfigure >/dev/null

if terraform state list 2>/dev/null | grep -q "^module.mediastack\."; then
  echo "Moving module.mediastack -> module.transmission in state..."
  terraform state mv module.mediastack module.transmission
  echo "Done."
else
  echo "module.mediastack not present in state — nothing to do."
fi
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x scripts/migrate-state.sh
```

### Task 2.9: Commit phase 2

- [ ] **Step 1: Stage + commit**

```bash
git add ansible/roles/transmission ansible/playbooks/transmission.yml \
        ansible/inventory/group_vars/transmission.yml \
        ansible/inventory/hosts.yml.example \
        terraform/transmission.tf terraform/outputs.tf \
        scripts/migrate-state.sh
git commit -m "refactor: rename mediastack -> transmission, remove *arr + flaresolverr"
```

---

## Phase 3: AdGuard migration wiring

### Task 3.1: Add a pre-deploy play that exports AdGuard config

- [ ] **Step 1: Create `ansible/playbooks/adguard-migrate.yml`**

Full contents:

```yaml
---
# One-shot play: fetch AdGuard config from the live pve2 CT 100 BEFORE
# destroying it. Run manually before `terraform apply`.
#
# Usage:  ansible-playbook -i inventory/hosts.yml playbooks/adguard-migrate.yml
#
# Result: ./backups/adguard-config-<timestamp>.tar.gz on the control node,
#         plus individual files in ./backups/adguard-config/.

- name: Export AdGuard config from the existing CT 100
  hosts: adguard
  become: yes
  vars_files:
    - ../vault.yml
  tasks:
    - name: Check whether AdGuard config exists in this container
      ansible.builtin.stat:
        path: /opt/AdGuardHome/AdGuardHome.yaml
      register: adguard_cfg

    - name: Fail if no AdGuard config found
      ansible.builtin.fail:
        msg: "No /opt/AdGuardHome/AdGuardHome.yaml on CT 100 — nothing to export."
      when: not adguard_cfg.stat.exists

    - name: Fetch AdGuardHome.yaml to the control node
      ansible.builtin.fetch:
        src: /opt/AdGuardHome/AdGuardHome.yaml
        dest: "{{ playbook_dir }}/../../backups/adguard-config/AdGuardHome.yaml"
        flat: yes

    - name: Fetch filters directory listing (informational)
      ansible.builtin.find:
        paths: /opt/AdGuardHome/data/filters
        patterns: "*.txt"
      register: adguard_filters

    - name: Report
      ansible.builtin.debug:
        msg:
          - "Exported: {{ playbook_dir }}/../../backups/adguard-config/AdGuardHome.yaml"
          - "Filter lists on the old container: {{ adguard_filters.files | length }} files (will re-download automatically)"

- name: Create timestamped archive on the control node
  hosts: localhost
  connection: local
  gather_facts: no
  tasks:
    - name: Archive the exported config
      ansible.builtin.archive:
        path: "{{ playbook_dir }}/../../backups/adguard-config"
        dest: "{{ playbook_dir }}/../../backups/adguard-config-{{ lookup('pipe', 'date +%Y%m%d-%H%M%S') }}.tar.gz"
        format: gz
```

### Task 3.2: Add restore-from-backup step to the adguard role

- [ ] **Step 1: Replace `ansible/roles/adguard/tasks/main.yml`**

Full contents:

```yaml
---
- name: Gather service facts
  ansible.builtin.service_facts:

- name: Disable systemd-resolved DNSStubListener to free port 53
  ansible.builtin.copy:
    dest: /etc/systemd/resolved.conf.d/adguardhome.conf
    content: |
      [Resolve]
      DNS=127.0.0.1
      DNSStubListener=no
    owner: root
    group: root
    mode: "0644"
  register: resolved_conf
  when: ansible_facts.services['systemd-resolved.service'] is defined

- name: Symlink resolv.conf to systemd-resolved runtime config
  ansible.builtin.file:
    src: /run/systemd/resolve/resolv.conf
    dest: /etc/resolv.conf
    state: link
    force: yes
  when: resolved_conf is changed

- name: Restart systemd-resolved after disabling stub listener
  ansible.builtin.systemd:
    name: systemd-resolved
    state: restarted
  when: resolved_conf is changed

- name: Install AdGuard Home dependencies
  ansible.builtin.apt:
    name:
      - curl
      - ca-certificates
    state: present
    update_cache: yes

- name: Ensure /opt/AdGuardHome exists before restore
  ansible.builtin.file:
    path: /opt/AdGuardHome
    state: directory
    owner: root
    group: root
    mode: "0755"

- name: Check for exported config on control node
  ansible.builtin.stat:
    path: "{{ playbook_dir }}/../../backups/adguard-config/AdGuardHome.yaml"
  register: exported_cfg
  delegate_to: localhost
  become: no

- name: Copy exported AdGuard config into new container
  ansible.builtin.copy:
    src: "{{ playbook_dir }}/../../backups/adguard-config/AdGuardHome.yaml"
    dest: /opt/AdGuardHome/AdGuardHome.yaml
    owner: root
    group: root
    mode: "0644"
    force: no
  when: exported_cfg.stat.exists

- name: Download and install AdGuard Home
  ansible.builtin.shell: |
    curl -s -S -L https://raw.githubusercontent.com/AdguardTeam/AdGuardHome/master/scripts/install.sh | sh -s -- -v
  args:
    creates: /opt/AdGuardHome/AdGuardHome

- name: Ensure AdGuard Home is enabled and running
  ansible.builtin.systemd:
    name: AdGuardHome
    state: started
    enabled: yes
```

`force: no` on the copy ensures we don't clobber a config that's already in place on idempotent re-runs.

### Task 3.3: Update terraform/adguard.tf for pve1 + 10GB disk

- [ ] **Step 1: Replace `terraform/adguard.tf`**

Full contents:

```hcl
module "adguard" {
  source = "./modules/lxc-container"

  vmid         = 100
  hostname     = "adguard"
  target_node  = "pve1"
  cores        = 1
  memory       = 512
  disk_size    = 10
  storage_pool = "local-lvm"
  template_id  = var.template_id
  bridge       = var.bridge
  dns_servers  = var.dns_servers
  password     = var.container_password
  pve_ssh_host = var.pve1_ssh_host

  extra_lxc_config = []
}
```

### Task 3.4: Move adguard to pve1 in the inventory example

- [ ] **Step 1: Replace the `adguard:` block in `ansible/inventory/hosts.yml.example`**

Change `ansible_host` from `<PVE2_TAILSCALE_IP>` to `<PVE1_TAILSCALE_IP>`:

```yaml
        adguard:
          hosts:
            ct100:
              ansible_host: <PVE1_TAILSCALE_IP>
              proxmox_vmid: 100
```

### Task 3.5: Commit phase 3

- [ ] **Step 1: Stage + commit**

```bash
git add ansible/playbooks/adguard-migrate.yml \
        ansible/roles/adguard/tasks/main.yml \
        terraform/adguard.tf \
        ansible/inventory/hosts.yml.example
git commit -m "feat: migrate adguard pve2 -> pve1 (10G disk), add config export/restore"
```

---

## Phase 4: Immich LXC (Terraform + Ansible)

### Task 4.1: Create Immich Terraform module invocation

- [ ] **Step 1: Create `terraform/immich.tf`**

Full contents:

```hcl
module "immich" {
  source = "./modules/lxc-container"

  vmid         = 103
  hostname     = "immich"
  target_node  = "pve2"
  cores        = 4
  memory       = 4096
  disk_size    = 20
  storage_pool = "zfs-pve-2"
  template_id  = var.template_id
  bridge       = var.bridge
  dns_servers  = var.dns_servers
  password     = var.container_password
  pve_ssh_host = var.pve2_ssh_host

  mountpoints = [
    {
      host_path      = "/zfs-pve-2/immich"
      container_path = "/data"
    }
  ]

  extra_lxc_config = [
    # TUN device for Tailscale
    "lxc.cgroup2.devices.allow: c 10:200 rwm",
    "lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file",
    # FUSE device for fuse-overlayfs (Docker storage driver in unprivileged LXC)
    "lxc.cgroup2.devices.allow: c 10:229 rwm",
    "lxc.mount.entry: /dev/fuse dev/fuse none bind,create=file",
  ]
}
```

Note: no `lxc.idmap` lines — Immich has no cross-container access requirements, so the default Proxmox unprivileged mapping is correct.

### Task 4.2: Create Immich group_vars

- [ ] **Step 1: Create `ansible/inventory/group_vars/immich.yml`**

Full contents:

```yaml
# Immich-specific variables

# Pin to a tested Immich release (update this to bump version intentionally)
immich_version: "v1.119.0"

# Compose/env paths (inside the LXC)
immich_root: /opt/immich
immich_data: /data

# Database
immich_db_password: "{{ vault_immich_db_password }}"
```

### Task 4.3: Add vault placeholder

- [ ] **Step 1: Update `ansible/vault.yml.example`** (for users copying the template)

Append:

```yaml
vault_immich_db_password: "changeme-long-random-string"
```

- [ ] **Step 2: Instruct user in README to regenerate vault.yml**

(Documented later in Phase 8.)

### Task 4.4: Immich role — tasks

- [ ] **Step 1: Create `ansible/roles/immich/tasks/main.yml`**

Full contents:

```yaml
---
- name: Install Docker repo prerequisites
  ansible.builtin.apt:
    name:
      - ca-certificates
      - curl
      - gnupg
      - fuse-overlayfs
    state: present
    update_cache: yes

- name: Add Docker GPG key
  ansible.builtin.shell: |
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
      | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
  args:
    creates: /etc/apt/keyrings/docker.gpg

- name: Add Docker APT repository
  ansible.builtin.apt_repository:
    repo: >
      deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg]
      https://download.docker.com/linux/ubuntu jammy stable
    filename: docker
    state: present

- name: Install Docker CE + compose plugin
  ansible.builtin.apt:
    name:
      - docker-ce
      - docker-ce-cli
      - containerd.io
      - docker-buildx-plugin
      - docker-compose-plugin
    state: present
    update_cache: yes

- name: Configure Docker to use fuse-overlayfs (required inside unprivileged LXC)
  ansible.builtin.copy:
    dest: /etc/docker/daemon.json
    content: |
      {
        "storage-driver": "fuse-overlayfs"
      }
    owner: root
    group: root
    mode: "0644"
  notify: restart docker

- name: Ensure docker is enabled
  ansible.builtin.systemd:
    name: docker
    state: started
    enabled: yes

- name: Create Immich deployment directory
  ansible.builtin.file:
    path: "{{ immich_root }}"
    state: directory
    owner: root
    group: root
    mode: "0755"

- name: Deploy Immich docker-compose.yml
  ansible.builtin.template:
    src: docker-compose.yml.j2
    dest: "{{ immich_root }}/docker-compose.yml"
    owner: root
    group: root
    mode: "0644"
  notify: restart immich

- name: Deploy Immich env file
  ansible.builtin.template:
    src: immich.env.j2
    dest: "{{ immich_root }}/.env"
    owner: root
    group: root
    mode: "0600"
  notify: restart immich

- name: Deploy Immich systemd unit
  ansible.builtin.template:
    src: immich.service.j2
    dest: /etc/systemd/system/immich.service
    owner: root
    group: root
    mode: "0644"
  notify:
    - reload systemd
    - restart immich

- name: Pull Immich images (first-time)
  ansible.builtin.command: "docker compose -f {{ immich_root }}/docker-compose.yml pull"
  args:
    chdir: "{{ immich_root }}"
  register: compose_pull
  changed_when: "'Downloaded newer image' in (compose_pull.stdout | default(''))"

- name: Enable and start Immich service
  ansible.builtin.systemd:
    name: immich
    state: started
    enabled: yes
    daemon_reload: yes
```

### Task 4.5: Immich role — handlers

- [ ] **Step 1: Create `ansible/roles/immich/handlers/main.yml`**

Full contents:

```yaml
---
- name: reload systemd
  ansible.builtin.systemd:
    daemon_reload: yes

- name: restart docker
  ansible.builtin.systemd:
    name: docker
    state: restarted

- name: restart immich
  ansible.builtin.systemd:
    name: immich
    state: restarted
    daemon_reload: yes
```

### Task 4.6: Immich compose template

- [ ] **Step 1: Create `ansible/roles/immich/templates/docker-compose.yml.j2`**

Full contents (derived from the official Immich release compose; pinned via env):

```yaml
name: immich

services:
  immich-server:
    container_name: immich_server
    image: ghcr.io/immich-app/immich-server:${IMMICH_VERSION}
    volumes:
      - ${UPLOAD_LOCATION}:/usr/src/app/upload
      - /etc/localtime:/etc/localtime:ro
    env_file:
      - .env
    ports:
      - "2283:2283"
    depends_on:
      - redis
      - database
    restart: always
    healthcheck:
      disable: false

  immich-machine-learning:
    container_name: immich_machine_learning
    image: ghcr.io/immich-app/immich-machine-learning:${IMMICH_VERSION}
    volumes:
      - ${ML_CACHE_LOCATION}:/cache
    env_file:
      - .env
    restart: always
    healthcheck:
      disable: false

  redis:
    container_name: immich_redis
    image: docker.io/redis:6.2-alpine@sha256:905c4ee67b8e0aa955331960d2aa745781e6bd89afc44a8584bfd13bc890f0ae
    healthcheck:
      test: redis-cli ping || exit 1
    restart: always

  database:
    container_name: immich_postgres
    image: ghcr.io/immich-app/postgres:14-vectorchord0.3.0
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_USER: ${DB_USERNAME}
      POSTGRES_DB: ${DB_DATABASE_NAME}
      POSTGRES_INITDB_ARGS: "--data-checksums"
    volumes:
      - ${DB_DATA_LOCATION}:/var/lib/postgresql/data
    restart: always
```

### Task 4.7: Immich env template

- [ ] **Step 1: Create `ansible/roles/immich/templates/immich.env.j2`**

Full contents:

```
# Managed by Ansible — do not edit by hand.

IMMICH_VERSION={{ immich_version }}

UPLOAD_LOCATION={{ immich_data }}/library
DB_DATA_LOCATION={{ immich_data }}/postgres
ML_CACHE_LOCATION={{ immich_data }}/model-cache

DB_PASSWORD={{ immich_db_password }}
DB_USERNAME=postgres
DB_DATABASE_NAME=immich

TZ=Asia/Kolkata
```

### Task 4.8: Immich systemd unit template

- [ ] **Step 1: Create `ansible/roles/immich/templates/immich.service.j2`**

Full contents:

```
[Unit]
Description=Immich (Docker Compose)
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory={{ immich_root }}
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
```

### Task 4.9: Immich playbook

- [ ] **Step 1: Create `ansible/playbooks/immich.yml`**

Full contents:

```yaml
---
- name: Configure Immich container
  hosts: immich
  become: yes
  vars_files:
    - ../vault.yml
  roles:
    - common
    - immich
    - tailscale
```

### Task 4.10: Add immich group to inventory example

- [ ] **Step 1: Add under `containers.children:` in `ansible/inventory/hosts.yml.example`**

```yaml
        immich:
          hosts:
            ct103:
              ansible_host: <PVE2_TAILSCALE_IP>
              proxmox_vmid: 103
```

### Task 4.11: Commit phase 4

- [ ] **Step 1: Stage + commit**

```bash
git add terraform/immich.tf \
        ansible/roles/immich/ \
        ansible/inventory/group_vars/immich.yml \
        ansible/vault.yml.example \
        ansible/playbooks/immich.yml \
        ansible/inventory/hosts.yml.example
git commit -m "feat: add immich LXC on pve2 (Docker-in-LXC with fuse-overlayfs)"
```

---

## Phase 5: Immich backup pipeline

### Task 5.1: Create backup script template

- [ ] **Step 1: Create `ansible/roles/immich-backup/templates/immich-backup.sh.j2`**

Full contents:

```bash
#!/bin/bash
# Immich nightly backup: snapshot zfs-pve-2/immich, restart Immich,
# zfs-send the snapshot to pve1's immich-backup dataset.
# Managed by Ansible (role: immich-backup).

set -euo pipefail

DATASET="{{ immich_backup_src_dataset }}"
REMOTE="root@{{ immich_backup_remote_host }}"
REMOTE_DATASET="{{ immich_backup_dst_dataset }}"
VMID="{{ immich_backup_vmid }}"
COMPOSE_FILE="{{ immich_backup_compose_file }}"
RETENTION="{{ immich_backup_retention_days }}"

TS=$(date +%Y%m%d-%H%M)
SNAP="${DATASET}@backup-${TS}"

log() { echo "[$(date -Iseconds)] $*"; }

log "Stopping Immich in CT ${VMID}"
pct exec "${VMID}" -- docker compose -f "${COMPOSE_FILE}" stop

log "Creating ZFS snapshot ${SNAP}"
zfs snapshot "${SNAP}"

log "Starting Immich in CT ${VMID}"
pct exec "${VMID}" -- docker compose -f "${COMPOSE_FILE}" start

PREV=$(zfs list -t snapshot -H -o name "${DATASET}" 2>/dev/null \
       | grep '@backup-' | grep -v -F "${SNAP}" | tail -1 || true)

if [ -n "${PREV}" ] && ssh "${REMOTE}" "zfs list -t snapshot -H -o name ${REMOTE_DATASET}@${PREV##*@}" >/dev/null 2>&1; then
  log "Sending incremental ${PREV} -> ${SNAP} to ${REMOTE}"
  zfs send -i "${PREV}" "${SNAP}" | ssh "${REMOTE}" "zfs receive -F ${REMOTE_DATASET}"
else
  log "No matching previous snapshot on remote; sending full stream ${SNAP}"
  zfs send "${SNAP}" | ssh "${REMOTE}" "zfs receive -F ${REMOTE_DATASET}"
fi

log "Pruning local snapshots older than ${RETENTION} newest"
zfs list -t snapshot -H -o name "${DATASET}" \
  | grep '@backup-' | sort \
  | head -n -"${RETENTION}" \
  | xargs -r -n1 zfs destroy || true

log "Pruning remote snapshots older than ${RETENTION} newest"
ssh "${REMOTE}" "zfs list -t snapshot -H -o name ${REMOTE_DATASET} | grep '@backup-' | sort | head -n -${RETENTION} | xargs -r -n1 zfs destroy" || true

log "Backup complete: ${SNAP}"
```

### Task 5.2: Create cron template

- [ ] **Step 1: Create `ansible/roles/immich-backup/templates/immich-backup.cron.j2`**

Full contents:

```
# Managed by Ansible — Immich nightly backup (03:00 IST)
CRON_TZ=Asia/Kolkata
MAILTO=""

0 3 * * * root {{ immich_backup_script_path }} >> {{ immich_backup_log_path }} 2>&1
```

### Task 5.3: Create logrotate template

- [ ] **Step 1: Create `ansible/roles/immich-backup/templates/immich-backup.logrotate.j2`**

Full contents:

```
{{ immich_backup_log_path }} {
    weekly
    rotate 8
    compress
    missingok
    notifempty
    create 0644 root root
}
```

### Task 5.4: Backup role tasks

- [ ] **Step 1: Create `ansible/roles/immich-backup/tasks/main.yml`**

Full contents:

```yaml
---
- name: Deploy the Immich backup script on pve2
  ansible.builtin.template:
    src: immich-backup.sh.j2
    dest: "{{ immich_backup_script_path }}"
    owner: root
    group: root
    mode: "0750"

- name: Deploy the Immich backup cron entry
  ansible.builtin.template:
    src: immich-backup.cron.j2
    dest: /etc/cron.d/immich-backup
    owner: root
    group: root
    mode: "0644"

- name: Deploy logrotate config for the backup log
  ansible.builtin.template:
    src: immich-backup.logrotate.j2
    dest: /etc/logrotate.d/immich-backup
    owner: root
    group: root
    mode: "0644"

- name: Touch backup log so logrotate finds it on first run
  ansible.builtin.file:
    path: "{{ immich_backup_log_path }}"
    state: touch
    owner: root
    group: root
    mode: "0644"
  changed_when: false
```

### Task 5.5: Backup role vars

- [ ] **Step 1: Add a new group_vars file for the pve2 host-side backup**

Since backup runs on the Proxmox host (pve2), add to `ansible/inventory/group_vars/all.yml`:

```yaml
# Shared variables — secrets referenced from vault
container_password: "{{ vault_container_password }}"
ts_auth_key: "{{ vault_ts_auth_key }}"

# Media user/group (UID/GID 1000 inside containers, maps to 101000 on host)
media_user: mediauser
media_group: mediagroup
media_uid: 1000
media_gid: 1000

# Immich backup pipeline (runs on pve2 host, targets pve1)
immich_backup_src_dataset: "zfs-pve-2/immich"
immich_backup_dst_dataset: "zfs-pve-1/immich-backup"
immich_backup_vmid: 103
immich_backup_compose_file: "/opt/immich/docker-compose.yml"
immich_backup_script_path: "/usr/local/bin/immich-backup.sh"
immich_backup_log_path: "/var/log/immich-backup.log"
immich_backup_retention_days: 7
immich_backup_remote_host: "{{ hostvars['pve1'].ansible_host }}"
```

### Task 5.6: Playbook for the backup role

- [ ] **Step 1: Create `ansible/playbooks/immich-backup.yml`**

Full contents:

```yaml
---
- name: Install Immich nightly backup pipeline on pve2
  hosts: pve2
  become: yes
  vars_files:
    - ../vault.yml
  roles:
    - immich-backup
```

### Task 5.7: Commit phase 5

- [ ] **Step 1: Stage + commit**

```bash
git add ansible/roles/immich-backup/ \
        ansible/playbooks/immich-backup.yml \
        ansible/inventory/group_vars/all.yml
git commit -m "feat: nightly ZFS-send immich backup pve2 -> pve1 at 03:00 IST"
```

---

## Phase 6: Cross-node SSH key (pve2 → pve1)

### Task 6.1: Create an SSH-keygen play

- [ ] **Step 1: Create `ansible/playbooks/pve-cross-ssh.yml`**

Full contents:

```yaml
---
# Set up a dedicated SSH keypair for pve2 root -> pve1 root.
# Used by the nightly immich-backup.sh for `zfs send | ssh | zfs receive`.
# Idempotent: skips keygen if the key already exists.

- name: Generate immich-backup SSH key on pve2
  hosts: pve2
  become: yes
  tasks:
    - name: Ensure /root/.ssh exists
      ansible.builtin.file:
        path: /root/.ssh
        state: directory
        owner: root
        group: root
        mode: "0700"

    - name: Generate ed25519 key for immich-backup
      community.crypto.openssh_keypair:
        path: /root/.ssh/immich_backup_ed25519
        type: ed25519
        comment: "immich-backup@pve2"
        owner: root
        group: root
        mode: "0600"
      register: keypair

    - name: Read public key
      ansible.builtin.slurp:
        src: /root/.ssh/immich_backup_ed25519.pub
      register: pve2_pubkey

    - name: Add ssh config alias using immich-backup key
      ansible.builtin.blockinfile:
        path: /root/.ssh/config
        create: yes
        owner: root
        group: root
        mode: "0600"
        marker: "# {mark} ANSIBLE MANAGED: immich-backup"
        block: |
          Host {{ hostvars['pve1'].ansible_host }}
            IdentityFile /root/.ssh/immich_backup_ed25519
            IdentitiesOnly yes
            StrictHostKeyChecking accept-new

- name: Install public key on pve1
  hosts: pve1
  become: yes
  tasks:
    - name: Authorize pve2 backup key
      ansible.posix.authorized_key:
        user: root
        key: "{{ hostvars['pve2'].pve2_pubkey.content | b64decode }}"
        comment: "immich-backup@pve2"
        state: present
```

- [ ] **Step 2: Verify ansible has the needed collections**

```bash
grep -E "community.crypto|ansible.posix" ansible/ansible.cfg || \
  echo "Reminder: ensure community.crypto and ansible.posix collections are installed (ansible-galaxy collection install community.crypto ansible.posix)"
```

- [ ] **Step 3: Commit**

```bash
git add ansible/playbooks/pve-cross-ssh.yml
git commit -m "feat: ansible play for pve2 -> pve1 ssh key (immich backup zfs-send)"
```

---

## Phase 7: site.yml + wiring everything together

### Task 7.1: Update site.yml

- [ ] **Step 1: Replace `ansible/playbooks/site.yml`**

Full contents:

```yaml
---
- name: Configure Jellyfin
  ansible.builtin.import_playbook: jellyfin.yml

- name: Configure Transmission
  ansible.builtin.import_playbook: transmission.yml

- name: Configure AdGuard
  ansible.builtin.import_playbook: adguard.yml

- name: Configure Immich
  ansible.builtin.import_playbook: immich.yml

- name: Install Immich backup pipeline on pve2 host
  ansible.builtin.import_playbook: immich-backup.yml
```

### Task 7.2: Commit phase 7

- [ ] **Step 1: Stage + commit**

```bash
git add ansible/playbooks/site.yml
git commit -m "chore: wire transmission/immich/immich-backup into site.yml"
```

---

## Phase 8: Docs — README, drawio, status.sh

### Task 8.1: Update scripts/status.sh service list

- [ ] **Step 1: Replace the `CONTAINERS=(...)` array in `scripts/status.sh`**

Replace:

```bash
CONTAINERS=(
  "adguard|100|${PVE2_TS}|AdGuard Home:3000,DNS:53"
  "jellyfin|101|${PVE1_TS}|Jellyfin:8096"
  "mediastack|102|${PVE1_TS}|Transmission:9091,Radarr:7878,Sonarr:8989,Prowlarr:9696,FlareSolverr:8191"
)
```

With:

```bash
CONTAINERS=(
  "adguard|100|${PVE1_TS}|AdGuard Home:3000,DNS:53"
  "jellyfin|101|${PVE1_TS}|Jellyfin:8096"
  "transmission|102|${PVE1_TS}|Transmission:9091"
  "immich|103|${PVE2_TS}|Immich:2283"
)
```

### Task 8.2: Update README.md

- [ ] **Step 1: Open and edit the README**

The existing README (278 lines) references the old layout throughout. Update these specific sections:
1. Any table listing containers: remove Radarr/Sonarr/Prowlarr/FlareSolverr, rename the row CT 102 `mediastack` → `transmission`, change CT 100 `adguard` node from pve2 → pve1, add new CT 103 `immich` on pve2.
2. Any "Storage" / "ZFS" section: add mention of `reservation=200G` on `zfs-pve-1/media`, new `zfs-pve-1/immich-backup` dataset, and new `zfs-pve-2/immich` dataset with `reservation=100G`.
3. Add a new "Immich backup" section describing the nightly pipeline, the 03:00 IST schedule, 7-day retention, and the restore runbook:

   ```
   ## Immich backup & restore

   Nightly cron on pve2 at 03:00 IST:
   1. `docker compose stop` inside CT 103 (~30s)
   2. `zfs snapshot zfs-pve-2/immich@backup-<ts>`
   3. Start Immich again immediately
   4. `zfs send -i <prev> <snap> | ssh pve1 "zfs receive zfs-pve-1/immich-backup"`
   5. Prune to the 7 most recent snapshots on both sides

   ### Manual trigger
   ssh root@pve2 /usr/local/bin/immich-backup.sh

   ### Restore (pve1 -> pve2)
   On pve2:
     ssh pve1 "zfs send zfs-pve-1/immich-backup@<snap>" | zfs receive zfs-pve-2/immich-restore
     # then: rename or re-mount immich-restore in place of immich and restart the compose stack.
   ```

4. Add a note under AdGuard: "Clients must point DNS at AdGuard's new IP on pve1. Consider a DHCP reservation to keep it stable."

- [ ] **Step 2: Read the existing README to identify exact sections**

```bash
sed -n '1,80p' README.md
```

Use the output to identify exact line numbers for each of the replacements above. For anything referring to Mediastack/arr pipeline prose, rewrite to describe just Transmission.

### Task 8.3: Update architecture.drawio

- [ ] **Step 1: Describe the diagram changes (to be applied in draw.io desktop or diagrams.net)**

The existing `architecture.drawio` XML contains nodes for: pve1, pve2, CT 100 AdGuard (on pve2), CT 101 Jellyfin, CT 102 Mediastack (with arr apps listed), the ZFS pool, the CI/CD flow, Tailscale overlay. Changes:

1. Move the `CT 100 AdGuard` node from the pve2 side to the pve1 side. Update its storage label from `local-lvm (2GB)` to `local-lvm NVMe (10GB)`.
2. In the `CT 102 Mediastack` node, change the label to `CT 102 Transmission` and strip the sub-service labels (Radarr, Sonarr, Prowlarr, FlareSolverr, Transmission) to just `Transmission (:9091)`.
3. Add a new node on the pve2 side: `CT 103 Immich` with sub-labels `Docker Compose`, `Server (:2283)`, `PostgreSQL (pgvector)`, `Redis`, `ML worker`. Mount label: `/zfs-pve-2/immich (100G res.) -> /data`.
4. On the `zfs-pve-1` pool annotation, add: `media (reservation=200G)` and `immich-backup (daily receives from pve2)`.
5. Add a directed arrow from `CT 103 Immich` (pve2) to `zfs-pve-1/immich-backup` (pve1), labeled `ZFS send daily @ 03:00 IST via Tailscale`. Use a dashed line to distinguish from control/data flows already present.

- [ ] **Step 2: Produce updated XML**

Open `architecture.drawio` in the draw.io desktop app (or diagrams.net web app), apply the changes above, save, then stage the updated XML file.

### Task 8.4: Commit phase 8

- [ ] **Step 1: Stage + commit**

```bash
git add scripts/status.sh README.md architecture.drawio
git commit -m "docs: update README, drawio, and status.sh for homelab v2"
```

### Task 8.5: Push branch

- [ ] **Step 1: Push branch to origin**

```bash
git push -u origin feat/homelab-v2-immich
```

Expected: GitHub prints a PR creation URL.

---

## Phase 9: Deployment execution

This phase executes the live migration. It mutates running infrastructure. Schedule for the 03:00 IST low-traffic window on a day when DNS disruption is acceptable (2–5 minutes).

### Task 9.1: Pre-flight checks

- [ ] **Step 1: Verify pool capacities, Tailscale mesh, and backend token**

```bash
ssh root@<pve1-ts-ip> zpool list zfs-pve-1
ssh root@<pve2-ts-ip> zpool list zfs-pve-2
ansible -i ansible/inventory/hosts.yml all -m ping
echo "${GITHUB_TOKEN:+ok}${GITHUB_TOKEN:-MISSING}"
```

Expected:
- `zfs-pve-1 ~500G` with ≥250G free
- `zfs-pve-2 ~1T` mostly free
- All hosts respond "pong"
- Output "ok"

### Task 9.2: Export AdGuard config

- [ ] **Step 1: Run the adguard-migrate playbook**

```bash
cd ansible
ansible-playbook -i inventory/hosts.yml playbooks/adguard-migrate.yml
cd ..
ls backups/
```

Expected: `backups/adguard-config/AdGuardHome.yaml` exists, and at least one tarball `backups/adguard-config-<ts>.tar.gz` exists.

### Task 9.3: Run terraform state move

- [ ] **Step 1: Execute migrate-state.sh**

```bash
./scripts/migrate-state.sh
```

Expected stdout: `Moving module.mediastack -> module.transmission in state... Done.` OR `module.mediastack not present in state — nothing to do.` (if re-run).

### Task 9.4: Apply host-setup (ZFS reservations + immich dataset)

- [ ] **Step 1: Run host-setup playbook**

```bash
cd ansible
ansible-playbook -i inventory/hosts.yml playbooks/host-setup.yml
cd ..
```

Expected: No failed tasks. `zfs list -o name,reservation zfs-pve-1/media` on pve1 shows `200G`; `zfs list zfs-pve-1/immich-backup` exists; `zfs list -o name,reservation zfs-pve-2/immich` on pve2 shows `100G`.

### Task 9.5: Run pve-cross-ssh play

- [ ] **Step 1: Set up backup SSH key**

```bash
cd ansible
ansible-playbook -i inventory/hosts.yml playbooks/pve-cross-ssh.yml
cd ..
```

Expected: `ssh -i /root/.ssh/immich_backup_ed25519 root@<pve1-ts-ip> hostname` from pve2 returns `pve1`.

### Task 9.6: Terraform plan + review

- [ ] **Step 1: Run terraform plan**

```bash
cd terraform
terraform plan -out=homelab-v2.tfplan
cd ..
```

Expected output should show:
- `module.adguard.proxmox_virtual_environment_container.this` will be **destroyed** (target_node changed), then **re-created**.
- `module.transmission.proxmox_virtual_environment_container.this` will be **updated in place** (hostname change; memory change).
- `module.immich.proxmox_virtual_environment_container.this` will be **created**.
- No changes for `jellyfin`.

**STOP** and review the plan. If anything unexpected appears (e.g. destroy+recreate of jellyfin), abort and investigate.

### Task 9.7: Terraform apply

- [ ] **Step 1: Apply the plan**

```bash
cd terraform
terraform apply homelab-v2.tfplan
cd ..
```

Expected: AdGuard destroyed+recreated (brief DNS outage begins), Transmission hostname updated, Immich created.

### Task 9.8: Ansible site.yml

- [ ] **Step 1: Run site.yml**

```bash
cd ansible
ansible-playbook -i inventory/hosts.yml playbooks/site.yml
cd ..
```

Expected: All roles complete. AdGuard starts with its restored config (DNS outage ends). Transmission role removes the arr units inside CT 102. Immich role installs Docker + starts the compose stack. Immich-backup role drops the script/cron on pve2.

### Task 9.9: Seed the first full ZFS send

- [ ] **Step 1: Manually trigger one backup run**

```bash
ssh root@<pve2-ts-ip> "/usr/local/bin/immich-backup.sh"
```

Expected: Log output shows snapshot created, compose restart, then `sending full stream <snap>`. Completion time: 5–30 min depending on size (will be small on first run — Immich is empty).

- [ ] **Step 2: Verify the backup arrived on pve1**

```bash
ssh root@<pve1-ts-ip> "zfs list -t snapshot -o name,used,refer zfs-pve-1/immich-backup"
```

Expected: A `@backup-<ts>` snapshot exists with non-zero referenced size.

---

## Phase 10: Post-deploy verification

### Task 10.1: Run the status script

- [ ] **Step 1: Run scripts/status.sh**

```bash
PVE1_HOST=<pve1-ts-ip> PVE2_HOST=<pve2-ts-ip> ./scripts/status.sh
```

Expected: All four rows show their ports as UP:
- `adguard` on pve1: `AdGuard Home:3000` UP, `DNS:53` UP
- `jellyfin` on pve1: `Jellyfin:8096` UP
- `transmission` on pve1: `Transmission:9091` UP
- `immich` on pve2: `Immich:2283` UP

### Task 10.2: End-to-end checks

- [ ] **Step 1: Confirm AdGuard config preserved**

Browse to `http://<adguard-new-ip>:3000` — the UI should show the user's pre-migration filter lists and upstream DNS servers (restored from the exported `AdGuardHome.yaml`).

- [ ] **Step 2: Confirm Jellyfin still sees the media library**

Browse to `http://<jellyfin-ip>:8096` — existing libraries load, a known video plays.

- [ ] **Step 3: Confirm Transmission accepts a > 15GB torrent**

Add a test `.torrent` (or magnet) for a large dataset. Confirm it does not immediately fail with a "no space" error. Cancel once accepted — actual download unnecessary.

- [ ] **Step 4: Confirm Immich web UI**

Browse to `http://<immich-ip>:2283` — complete admin registration; verify the web UI loads and responds.

- [ ] **Step 5: Verify cron is active on pve2**

```bash
ssh root@<pve2-ts-ip> "cat /etc/cron.d/immich-backup"
```

Expected: the deployed file with `CRON_TZ=Asia/Kolkata` and the `0 3 * * *` line.

- [ ] **Step 6: Update router-level DNS to new AdGuard IP**

Out-of-band manual step: update the LAN router's DHCP "DNS servers" setting so new leases receive the new AdGuard IP. Consider setting a DHCP reservation on `<adguard-new-mac>` so the IP is stable across reboots.

### Task 10.3: Open PR

- [ ] **Step 1: Create pull request**

```bash
gh pr create --title "Homelab v2: slim media stack + Immich with nightly backup" --body "$(cat <<'EOF'
## Summary
- Remove arr apps (Sonarr, Radarr, Prowlarr, FlareSolverr) from the mediastack; CT 102 now runs Transmission only.
- Set ZFS `reservation=200G` on `zfs-pve-1/media` to fix "downloads > 15GB fail" symptoms.
- Migrate AdGuard (CT 100) from pve2 to pve1 (NVMe local-lvm, disk bumped 2GB → 10GB); config preserved via export/restore flow.
- Add Immich (CT 103) on pve2 — Docker-in-LXC with fuse-overlayfs, bind-mounted `/zfs-pve-2/immich` (reservation=100G).
- Daily 03:00 IST ZFS-snapshot+send from pve2 → pve1's new `zfs-pve-1/immich-backup` dataset. 7-day retention both sides.

## Test plan
- [x] `terraform plan` shows expected destroy+create for CT 100, in-place hostname+memory update for CT 102, create for CT 103
- [x] `./scripts/status.sh` reports all four services UP after migration
- [x] AdGuard filter lists and upstream DNS preserved from export
- [x] Jellyfin + media library unaffected
- [x] Transmission accepts a >15GB torrent without the previous "no space" error
- [x] Immich web UI responsive at :2283
- [x] First manual `immich-backup.sh` run completes and appears on pve1 as `zfs-pve-1/immich-backup@backup-<ts>`
- [x] `/etc/cron.d/immich-backup` on pve2 contains `CRON_TZ=Asia/Kolkata` and schedules the run at 03:00 IST

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL returned on stdout. Share with reviewers, merge once green.

---

## Notes for the implementer

- **TDD doesn't fit infrastructure IaC** in the classical sense. This plan replaces "write failing test first" with "run `terraform plan` and verify expected resource actions before apply" — same spirit (prove the expected change before causing it) in a different form.
- **Rollback**: every phase before Phase 9 is reversible via `git revert`. Phase 9 (live mutation) is rolled back by `terraform apply -replace` or by restoring from ZFS snapshots; the pve1 `immich-backup` dataset IS your rollback point for Immich.
- **Secrets**: remember to add `vault_immich_db_password` to your real (encrypted) `ansible/vault.yml` — the example file is for new users. Use `ansible-vault edit ansible/vault.yml` on a copy.
- **DNS during migration**: ~2–5 min of no-DNS during the destroy+recreate of CT 100. Configure the router with `1.1.1.1` as a secondary DNS in advance so clients don't hard-fail.
- **First `zfs send`** will be small (Immich is empty). Subsequent sends are incrementals. Plan for a few minutes of bandwidth use each night once the library grows.

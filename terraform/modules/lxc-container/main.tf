terraform {
  required_providers {
    proxmox = {
      source = "bpg/proxmox"
    }
  }
}

resource "proxmox_virtual_environment_container" "this" {
  vm_id     = var.vmid
  node_name = var.target_node

  description = "Managed by Terraform"

  initialization {
    hostname = var.hostname

    dns {
      servers = var.dns_servers
    }

    ip_config {
      ipv4 {
        address = "dhcp"
      }
    }

    user_account {
      password = var.password
    }
  }

  operating_system {
    template_file_id = var.template_id
    type             = "ubuntu"
  }

  cpu {
    cores = var.cores
  }

  memory {
    dedicated = var.memory
  }

  disk {
    datastore_id = var.storage_pool
    size         = var.disk_size
  }

  network_interface {
    name   = "eth0"
    bridge = var.bridge
  }

  features {
    nesting = var.nesting
  }

  unprivileged = var.unprivileged

  startup {
    order = 1
  }

  # Start stopped so the provisioner can inject raw LXC config + bind mounts
  # before the container boots for the first time.
  started = (length(var.extra_lxc_config) > 0 || length(var.mountpoints) > 0) ? false : true

  lifecycle {
    ignore_changes = [
      # Password is only set on creation
      initialization[0].user_account,
      # idmap and started are managed by the lxc_config_injection provisioner
      # (SSH), not by the provider. The provider reads them back on refresh,
      # causing perpetual drift that the Proxmox API rejects (HTTP 500).
      idmap,
      started,
      # Bind-mount points are applied via `pct set --mp<n>` in the provisioner
      # because the Proxmox REST API refuses to accept type=bind from any user
      # (even root@pam with privsep disabled).
      mount_point,
    ]
  }
}

# Inject raw LXC config (idmap, cgroup, device passthrough) AND bind-mount
# entries via root SSH. Needed because:
#   1. idmap/cgroup entries aren't exposed by the bpg/proxmox provider.
#   2. Proxmox REST API rejects bind mount points with "Permission check
#      failed (mount point type bind is only allowed for root@pam)" even
#      when the token user IS root@pam with privilege separation disabled.
#      The CLI (`pct set`) accepts them because it bypasses that check.
resource "terraform_data" "lxc_config_injection" {
  count = (length(var.extra_lxc_config) > 0 || length(var.mountpoints) > 0) ? 1 : 0

  triggers_replace = [
    join("\n", var.extra_lxc_config),
    jsonencode(var.mountpoints),
    proxmox_virtual_environment_container.this.vm_id,
  ]

  provisioner "remote-exec" {
    connection {
      type = "ssh"
      host = var.pve_ssh_host
      user = "root"
    }

    inline = concat(
      # Remove previously injected lxc.* and mp<n>: lines so re-runs are idempotent.
      ["sed -i '/^lxc\\./d' /etc/pve/lxc/${var.vmid}.conf"],
      ["sed -i '/^mp[0-9]/d' /etc/pve/lxc/${var.vmid}.conf"],
      # Append each raw LXC config line.
      [for line in var.extra_lxc_config : "echo '${line}' >> /etc/pve/lxc/${var.vmid}.conf"],
      # Apply each bind mount via pct set (REST-API path is blocked).
      [for idx, mp in var.mountpoints : "pct set ${var.vmid} --mp${idx} ${mp.host_path},mp=${mp.container_path}"],
      # Start the container.
      ["pct start ${var.vmid} || true"],
    )
  }

  depends_on = [proxmox_virtual_environment_container.this]
}

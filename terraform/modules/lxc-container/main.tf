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

  # Start stopped so we can inject raw LXC config before first boot
  started = length(var.extra_lxc_config) > 0 ? false : true

  dynamic "mount_point" {
    for_each = var.mountpoints
    content {
      volume = mount_point.value.host_path
      path   = mount_point.value.container_path
    }
  }

  lifecycle {
    ignore_changes = [
      # Password is only set on creation
      initialization[0].user_account,
    ]
  }
}

# Inject raw LXC config lines (idmap, cgroup, device passthrough) that the
# provider doesn't support natively, then start the container.
resource "terraform_data" "lxc_config_injection" {
  count = length(var.extra_lxc_config) > 0 ? 1 : 0

  triggers_replace = [
    join("\n", var.extra_lxc_config),
    proxmox_virtual_environment_container.this.vm_id,
  ]

  provisioner "remote-exec" {
    connection {
      type = "ssh"
      host = var.pve_ssh_host
      user = "root"
    }

    inline = concat(
      # Remove any previously injected lines (idempotent re-runs)
      ["sed -i '/^lxc\\./d' /etc/pve/lxc/${var.vmid}.conf"],
      # Append each config line
      [for line in var.extra_lxc_config : "echo '${line}' >> /etc/pve/lxc/${var.vmid}.conf"],
      # Start the container
      ["pct start ${var.vmid} || true"],
    )
  }

  depends_on = [proxmox_virtual_environment_container.this]
}

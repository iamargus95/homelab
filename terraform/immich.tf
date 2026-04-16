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

module "mediastack" {
  source = "../modules/lxc-container"

  vmid         = 102
  hostname     = "mediastack"
  target_node  = "pve1"
  cores        = 2
  memory       = 4096
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
      slot           = 0
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

module "jellyfin" {
  source = "../modules/lxc-container"

  vmid         = 101
  hostname     = "jellyfin"
  target_node  = "pve1"
  cores        = 2
  memory       = 2048
  disk_size    = 10
  storage_pool = "zfs-pve-1"
  template_id  = var.template_id
  bridge       = var.bridge
  dns_servers  = var.dns_servers
  password     = var.container_password
  pve_ssh_host = var.pve1_ssh_host

  mountpoints = [
    {
      host_path      = "/zfs-pve-1/media"
      container_path = "/media"
      slot           = 0
    }
  ]

  extra_lxc_config = [
    # Intel iGPU passthrough for hardware transcoding
    "lxc.cgroup2.devices.allow: c 226:0 rwm",
    "lxc.cgroup2.devices.allow: c 226:128 rwm",
    "lxc.cgroup2.devices.allow: c 10:200 rwm",
    "lxc.mount.entry: /dev/dri/card0 dev/dri/card0 none bind,optional,create=file",
    "lxc.mount.entry: /dev/dri/renderD128 dev/dri/renderD128 none bind,optional,create=file",
    # TUN device for Tailscale
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

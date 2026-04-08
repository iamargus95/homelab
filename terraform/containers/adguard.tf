module "adguard" {
  source = "../modules/lxc-container"

  vmid         = 100
  hostname     = "adguard"
  target_node  = "pve2"
  cores        = 1
  memory       = 512
  disk_size    = 2
  storage_pool = "local-lvm"
  template_id  = var.template_id
  bridge       = var.bridge
  dns_servers  = var.dns_servers
  password     = var.container_password
  pve_ssh_host = var.pve2_ssh_host

  extra_lxc_config = []
}

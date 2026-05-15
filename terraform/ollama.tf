module "ollama" {
  source = "./modules/lxc-container"

  vmid         = 104
  hostname     = "ollama"
  target_node  = "pve1"
  cores        = 2
  memory       = 10240
  disk_size    = 80
  storage_pool = "local-lvm"
  template_id  = var.template_id
  bridge       = var.bridge
  dns_servers  = var.dns_servers
  password     = var.container_password
  pve_ssh_host = var.pve1_ssh_host

  extra_lxc_config = []
}

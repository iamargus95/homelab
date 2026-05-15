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

output "ollama" {
  description = "Ollama container details"
  value = {
    id       = module.ollama.container_id
    hostname = module.ollama.hostname
  }
}

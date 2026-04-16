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

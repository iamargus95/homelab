output "jellyfin" {
  description = "Jellyfin container details"
  value = {
    id       = module.jellyfin.container_id
    hostname = module.jellyfin.hostname
  }
}

output "mediastack" {
  description = "Mediastack container details"
  value = {
    id       = module.mediastack.container_id
    hostname = module.mediastack.hostname
  }
}

output "adguard" {
  description = "AdGuard container details"
  value = {
    id       = module.adguard.container_id
    hostname = module.adguard.hostname
  }
}

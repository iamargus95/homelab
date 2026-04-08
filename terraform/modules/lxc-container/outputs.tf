output "container_id" {
  description = "The VMID of the created container"
  value       = proxmox_virtual_environment_container.this.vm_id
}

output "hostname" {
  description = "The hostname of the container"
  value       = var.hostname
}

output "ipv4_address" {
  description = "The IPv4 address of the container (if available)"
  value       = try(proxmox_virtual_environment_container.this.initialization[0].ip_config[0].ipv4[0].address, "dhcp")
}

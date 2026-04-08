variable "vmid" {
  description = "Container ID"
  type        = number
}

variable "hostname" {
  description = "Container hostname"
  type        = string
}

variable "target_node" {
  description = "Proxmox node to deploy on"
  type        = string
}

variable "cores" {
  description = "Number of CPU cores"
  type        = number
  default     = 2
}

variable "memory" {
  description = "Memory in MB"
  type        = number
  default     = 2048
}

variable "disk_size" {
  description = "Root disk size in GB"
  type        = number
  default     = 10
}

variable "storage_pool" {
  description = "Proxmox storage pool for root disk"
  type        = string
}

variable "template_id" {
  description = "LXC template file ID (e.g. local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst)"
  type        = string
}

variable "bridge" {
  description = "Network bridge"
  type        = string
  default     = "vmbr0"
}

variable "dns_servers" {
  description = "DNS servers (space-separated)"
  type        = list(string)
  default     = ["1.1.1.1", "8.8.8.8"]
}

variable "password" {
  description = "Container root password"
  type        = string
  sensitive   = true
}

variable "unprivileged" {
  description = "Run as unprivileged container"
  type        = bool
  default     = true
}

variable "nesting" {
  description = "Enable nesting feature"
  type        = bool
  default     = true
}

variable "onboot" {
  description = "Start container on boot"
  type        = bool
  default     = true
}

variable "mountpoints" {
  description = "Bind mount points from host to container"
  type = list(object({
    host_path      = string
    container_path = string
    slot           = number
  }))
  default = []
}

variable "extra_lxc_config" {
  description = "Raw LXC config lines to append to container config"
  type        = list(string)
  default     = []
}

variable "pve_ssh_host" {
  description = "SSH host for the Proxmox node (for raw config injection)"
  type        = string
}

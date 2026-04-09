# --- Proxmox Connection ---
variable "proxmox_endpoint" {
  description = "Proxmox API URL (e.g. https://192.168.1.36:8006)"
  type        = string
}

variable "proxmox_api_token" {
  description = "Proxmox API token (e.g. root@pam!terraform=uuid)"
  type        = string
  sensitive   = true
}

# --- Node SSH Hosts (Tailscale IPs for config injection) ---
variable "pve1_ssh_host" {
  description = "SSH host for pve1 (Tailscale IP)"
  type        = string
}

variable "pve2_ssh_host" {
  description = "SSH host for pve2 (Tailscale IP)"
  type        = string
}

# --- Container Defaults ---
variable "container_password" {
  description = "Root password for all containers"
  type        = string
  sensitive   = true
}

variable "template_id" {
  description = "LXC template file ID"
  type        = string
  default     = "local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst"
}

variable "bridge" {
  description = "Network bridge for containers"
  type        = string
  default     = "vmbr0"
}

variable "dns_servers" {
  description = "DNS servers for containers"
  type        = list(string)
  default     = ["1.1.1.1", "8.8.8.8"]
}

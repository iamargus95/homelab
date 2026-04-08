terraform {
  required_version = ">= 1.6.0"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = ">= 0.66.0"
    }
  }
}

provider "proxmox" {
  endpoint = var.proxmox_endpoint
  api_token = var.proxmox_api_token
  insecure  = true

  ssh {
    agent    = true
    username = "root"

    node {
      name    = "pve1"
      address = var.pve1_ssh_host
    }

    node {
      name    = "pve2"
      address = var.pve2_ssh_host
    }
  }
}

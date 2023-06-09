terraform {
  required_providers {
    equinix = {
      source  = "equinix/equinix"
      version = "1.14.3"
    }
  }
}

# depends on host creation
# provider "vsphere" {
#   source               = "hashicorp/vsphere"
#   user                 = "root"
#   password             = equinix_metal_device.esxi_hosts.root_password
#   vsphere_server       = equinix_metal_device.esxi_hosts.access_public_ipv4
#   allow_unverified_ssl = true
# }

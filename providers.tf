provider "equinix" {
  auth_token = var.auth_token
}

# primary vsphere provider
provider "vsphere" {
  user                 = "root"
  password             = module.esxi_hosts.0.root_password
  vsphere_server       = module.esxi_hosts.0.esxi_public_ip
  allow_unverified_ssl = true
}

# special provider for first esx host
provider "vsphere" {
  alias                = "esx1_host"
  user                 = "root"
  password             = module.esxi_hosts.0.root_password
  vsphere_server       = module.esxi_hosts.0.esxi_public_ip
  allow_unverified_ssl = true
}

output "esxi_public_ip" {
  depends_on = [time_sleep.vlan_sleep]

  value       = equinix_metal_device.esxi_hosts.access_public_ipv4
  description = "Public IP address for ESXi host"
}

output "esxi_public_network" {
  value       = equinix_metal_device.esxi_hosts.network.0
  description = "Public IP address for ESXi host"
}

output "esxi_hostname" {
  value       = var.esxi_hostname
  description = "Public IP address for ESXi host"
}

output "root_password" {
  value       = equinix_metal_device.esxi_hosts.root_password
  sensitive   = true
  description = "Root password for ESXi host"
}

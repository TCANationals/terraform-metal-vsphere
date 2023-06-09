# output "vcenter_fqdn" {
#   value       = format("vcva.%s", var.domain_name)
#   description = "The FQDN of vCenter (Private DNS only)"
# }

# output "vcenter_username" {
#   value       = format("%s@%s", var.vcenter_user_name, var.vcenter_domain)
#   description = "The username to login to vCenter"
# }

# output "vcenter_password" {
#   value       = random_password.sso_password.result
#   sensitive   = true
#   description = "The SSO Password to login to vCenter"
# }

# output "vcenter_root_password" {
#   value       = random_password.vcenter_password.result
#   sensitive   = true
#   description = "The root password to ssh or login at the console of vCenter."
# }

# output "ssh_key_path" {
#   value       = pathexpand("~/.ssh/${local.ssh_key_name}")
#   description = "The path of to the private SSH key created for this deployment"
# }

# output "vcenter_ip" {
#   value       = lookup(data.external.get_vcenter_ip.result, "vcenter_ip")
#   description = "The IP address of vCenter"
# }

output "bastion_ip" {
  value       = equinix_metal_device.bastion.access_public_ipv4
  description = "The IP address of the Bastion host"
}

module "esxi_hosts" {
  source     = "./modules/esxi_host"
  depends_on = [equinix_metal_ssh_key.ssh_pub_key]

  count                = var.esxi_host_count
  esxi_hostname        = format("%s%02d", var.esxi_hostname, count.index + 1)
  esxi_size            = var.esxi_size
  facility             = var.facility
  metro                = var.metro
  vmware_os            = var.vmware_os
  billing_cycle        = var.billing_cycle
  project_id           = local.project_id
  update_esxi          = var.update_esxi
  esxi_update_filename = var.esxi_update_filename
  ssh_private_key_pem  = tls_private_key.ssh_key_pair.private_key_pem
  vlan_ids             = concat(equinix_metal_vlan.private_vlans, [equinix_metal_vlan.public_vlan])
}

# Generate subnet list for ESXi

# resource "null_resource" "esx_network_prereqs" {
#   depends_on = [null_resource.run_pre_reqs]
#   connection {
#     type        = "ssh"
#     user        = local.ssh_user
#     private_key = chomp(tls_private_key.ssh_key_pair.private_key_pem)
#     host        = equinix_metal_device.bastion.access_public_ipv4
#   }

#   provisioner "file" {
#     content     = file("${path.module}/templates/esx_host_networking.py")
#     destination = "bootstrap/esx_host_networking.py"
#   }
# }

# resource "null_resource" "apply_esx_network_config" {
#   count = length(module.esxi_hosts)
#   depends_on = [null_resource.esx_network_prereqs]

#   connection {
#     type        = "ssh"
#     user        = local.ssh_user
#     private_key = chomp(tls_private_key.ssh_key_pair.private_key_pem)
#     host        = equinix_metal_device.bastion.access_public_ipv4
#   }

#   provisioner "remote-exec" {
#     inline = ["python3 $HOME/bootstrap/esx_host_networking.py --host '${element(module.esxi_hosts.*.esxi_public_ip, count.index)}' --user root --pass '${element(module.esxi_hosts.*.root_password, count.index)}'"]
#   }
# }

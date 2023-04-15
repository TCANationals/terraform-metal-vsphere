# resource "random_password" "vcenter_password" {
#   length           = 16
#   min_upper        = 2
#   min_lower        = 2
#   min_numeric      = 2
#   min_special      = 2
#   override_special = "$!?@*"
#   special          = true
# }

# resource "random_password" "sso_password" {
#   length           = 16
#   min_upper        = 2
#   min_lower        = 2
#   min_numeric      = 2
#   min_special      = 2
#   override_special = "$!?@*"
#   special          = true
# }


# resource "null_resource" "copy_vcva_template" {
#   depends_on = [
#     null_resource.run_pre_reqs,
#   ]
#   connection {
#     type        = "ssh"
#     user        = local.ssh_user
#     private_key = chomp(tls_private_key.ssh_key_pair.private_key_pem)
#     host        = equinix_metal_device.router.access_public_ipv4
#   }

#   provisioner "file" {
#     content = templatefile("${path.module}/templates/vcva_template.json", {
#       vcenter_password       = random_password.vcenter_password.result,
#       sso_password           = random_password.sso_password.result,
#       first_esx_pass         = equinix_metal_device.esxi_hosts.0.root_password,
#       domain_name            = var.domain_name,
#       vcenter_network        = var.vcenter_portgroup_name,
#       vcenter_domain         = var.vcenter_domain,
#       vcva_deployment_option = var.vcva_deployment_option
#     })

#     destination = "bootstrap/vcva_template.json"
#   }
# }

# resource "null_resource" "copy_update_uplinks" {
#   depends_on = [null_resource.run_pre_reqs]
#   connection {
#     type        = "ssh"
#     user        = local.ssh_user
#     private_key = chomp(tls_private_key.ssh_key_pair.private_key_pem)
#     host        = equinix_metal_device.router.access_public_ipv4
#   }

#   provisioner "file" {
#     content     = file("${path.module}/templates/update_uplinks.py")
#     destination = "bootstrap/update_uplinks.py"
#   }
# }

# resource "null_resource" "esx_network_prereqs" {
#   depends_on = [null_resource.run_pre_reqs]
#   connection {
#     type        = "ssh"
#     user        = local.ssh_user
#     private_key = chomp(tls_private_key.ssh_key_pair.private_key_pem)
#     host        = equinix_metal_device.router.access_public_ipv4
#   }

#   provisioner "file" {
#     content     = file("${path.module}/templates/esx_host_networking.py")
#     destination = "bootstrap/esx_host_networking.py"
#   }
# }

# resource "null_resource" "apply_esx_network_config" {
#   count = length(equinix_metal_device.esxi_hosts)
#   depends_on = [
#     null_resource.reboot_post_upgrade,
#     null_resource.esx_network_prereqs,
#     null_resource.copy_update_uplinks,
#     null_resource.install_vpn_server
#   ]

#   connection {
#     type        = "ssh"
#     user        = local.ssh_user
#     private_key = chomp(tls_private_key.ssh_key_pair.private_key_pem)
#     host        = equinix_metal_device.router.access_public_ipv4
#   }

#   provisioner "remote-exec" {
#     inline = ["python3 $HOME/bootstrap/esx_host_networking.py --host '${element(equinix_metal_device.esxi_hosts.*.access_public_ipv4, count.index)}' --user root --pass '${element(equinix_metal_device.esxi_hosts.*.root_password, count.index)}' --id '${element(equinix_metal_device.esxi_hosts.*.id, count.index)}' --index ${count.index} --ipRes ${element(equinix_metal_reserved_ip_block.esx_ip_blocks.*.id, count.index)}"]
#   }
# }

# resource "null_resource" "deploy_vcva" {
#   depends_on = [
#     null_resource.apply_esx_network_config,
#     null_resource.download_vcenter_iso
#   ]
#   connection {
#     type        = "ssh"
#     user        = local.ssh_user
#     private_key = chomp(tls_private_key.ssh_key_pair.private_key_pem)
#     host        = equinix_metal_device.router.access_public_ipv4
#   }

#   provisioner "file" {
#     source      = "${path.module}/templates/extend_datastore.sh"
#     destination = "bootstrap/extend_datastore.sh"
#   }

#   provisioner "file" {
#     content     = file("${path.module}/templates/vsan_claim.py")
#     destination = "bootstrap/vsan_claim.py"
#   }

#   provisioner "file" {
#     content     = file("${path.module}/templates/deploy_vcva.py")
#     destination = "bootstrap/deploy_vcva.py"
#   }

#   provisioner "remote-exec" {
#     inline = ["python3 $HOME/bootstrap/deploy_vcva.py"]
#   }
# }

# resource "null_resource" "vsan_claim" {
#   depends_on = [null_resource.deploy_vcva]
#   count      = var.esxi_host_count == 1 ? 0 : 1
#   connection {
#     type        = "ssh"
#     user        = local.ssh_user
#     private_key = chomp(tls_private_key.ssh_key_pair.private_key_pem)
#     host        = equinix_metal_device.router.access_public_ipv4
#   }

#   provisioner "remote-exec" {
#     inline = [
#       "echo 'vCenter Deployed... Waiting 60 seconds before configuring vSan...'",
#       "sleep 60",
#       "python3 $HOME/bootstrap/vsan_claim.py"
#     ]
#   }
# }

# data "external" "get_vcenter_ip" {
#   # The following command will test this script
#   # echo '{"private_subnets":"[{\"cidr\":\"172.16.0.0/24\",\"name\":\"VM Private Net 1\",\"nat\":true,\"reserved_ip_count\":100,\"routable\":true,\"vsphere_service_type\":\"management\"},{\"cidr\":\"172.16.1.0/24\",\"name\":\"vMotion\",\"nat\":false,\"routable\":false,\"vsphere_service_type\":\"vmotion\"},{\"cidr\":\"172.16.2.0/24\",\"name\":\"vSAN\",\"nat\":false,\"routable\":false,\"vsphere_service_type\":\"vsan\"}]","public_cidrs":"[\"147.75.35.160/29\"]","public_subnets":"[{\"ip_count\":8,\"name\":\"VM Public Net 1\",\"nat\":false,\"routable\":true,\"vsphere_service_type\":null}]","vcenter_network":"VM Public Net 1"}' | python3 get_vcenter_ip.py
#   program = ["python3", "${path.module}/scripts/get_vcenter_ip.py"]
#   query = {
#     "private_subnets" = jsonencode(var.private_subnets)
#     "public_subnets"  = jsonencode(var.public_subnets)
#     "public_cidrs"    = jsonencode(equinix_metal_reserved_ip_block.ip_blocks.*.cidr_notation)
#     "vcenter_network" = var.vcenter_portgroup_name
#   }
# }

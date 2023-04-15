# resource "equinix_metal_device" "bastion" {
#   depends_on              = [equinix_metal_ssh_key.ssh_pub_key]
#   hostname                = "bastion"
#   plan                    = var.bastion_size
#   facilities              = var.facility == "" ? null : [var.facility]
#   metro                   = var.metro == "" ? null : var.metro
#   operating_system        = var.bastion_os
#   billing_cycle           = var.billing_cycle
#   project_id              = local.project_id
#   hardware_reservation_id = lookup(var.reservations, "bastion", "")
# }

# data "template_file" "vars_file" {
#   template = file("${path.module}/templates/vars.py")
#   vars = {
#     private_subnets      = jsonencode(var.private_subnets),
#     private_vlans        = jsonencode(equinix_metal_vlan.private_vlans.*.vxlan),
#     public_subnets       = jsonencode(var.public_subnets),
#     public_vlans         = jsonencode(equinix_metal_vlan.public_vlans.*.vxlan),
#     public_cidrs         = jsonencode(equinix_metal_reserved_ip_block.ip_blocks.*.cidr_notation),
#     domain_name          = var.domain_name,
#     vcenter_network      = var.vcenter_portgroup_name,
#     vcenter_fqdn         = format("vcva.%s", var.domain_name),
#     vcenter_user         = var.vcenter_user_name,
#     vcenter_domain       = var.vcenter_domain,
#     sso_password         = random_password.sso_password.result,
#     vcenter_cluster_name = var.vcenter_cluster_name,
#     plan_type            = var.esxi_size,
#     esx_passwords        = jsonencode(equinix_metal_device.esxi_hosts.*.root_password),
#     dc_name              = var.vcenter_datacenter_name,
#     metal_token          = var.auth_token,
#   }
# }

# resource "null_resource" "run_pre_reqs" {
#   connection {
#     type        = "ssh"
#     user        = local.ssh_user
#     private_key = chomp(tls_private_key.ssh_key_pair.private_key_pem)
#     host        = equinix_metal_device.router.access_public_ipv4
#   }

#   provisioner "remote-exec" {
#     inline = ["mkdir -p $HOME/bootstrap/"]
#   }

#   provisioner "file" {
#     content     = data.template_file.vars_file.rendered
#     destination = "bootstrap/vars.py"
#   }

#   provisioner "file" {
#     content     = file("${path.module}/templates/pre_reqs.py")
#     destination = "bootstrap/pre_reqs.py"
#   }

#   provisioner "remote-exec" {
#     inline = ["python3 $HOME/bootstrap/pre_reqs.py"]
#   }
# }

# data "template_file" "download_vcenter" {
#   template = file("${path.module}/templates/download_vcenter.sh")
#   vars = {
#     object_store_bucket_name = var.object_store_bucket_name
#     s3_url                   = var.s3_url
#     s3_access_key            = var.s3_access_key
#     s3_secret_key            = var.s3_secret_key
#     s3_version               = var.s3_version
#     vcenter_iso_name         = var.vcenter_iso_name
#     ssh_private_key          = chomp(tls_private_key.ssh_key_pair.private_key_pem)
#   }
# }

# resource "null_resource" "download_vcenter_iso" {
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
#     content     = data.template_file.download_vcenter.rendered
#     destination = "bootstrap/download_vcenter.sh"
#   }

#   provisioner "remote-exec" {
#     inline = ["bash $HOME/bootstrap/download_vcenter.sh"]
#   }
# }

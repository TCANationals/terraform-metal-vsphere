# Setup public network on first ESX host
# resource "vsphere_host_port_group" "esx1_public_vlan" {
#   provider            = vsphere.esx1_host

#   name                = var.vcenter_portgroup_name
#   vlan_id             = equinix_metal_vlan.public_vlan.vxlan
#   host_system_id      = data.vsphere_host.esx1_host.id
#   virtual_switch_name = "vSwitch0" # default switch name
#   allow_promiscuous   = true
# }

# Setup JSON deployment template
resource "null_resource" "copy_vcva_template" {
  depends_on = [
    null_resource.run_pre_reqs,
  ]

  triggers = {
    build_number = "${timestamp()}"
  }

  connection {
    type        = "ssh"
    user        = local.ssh_user
    private_key = chomp(tls_private_key.ssh_key_pair.private_key_pem)
    host        = equinix_metal_device.bastion.access_public_ipv4
  }

  provisioner "file" {
    content = templatefile("${path.module}/templates/vcva_template.json", {
      vcenter_password       = random_password.vcenter_password.result,
      sso_password           = random_password.sso_password.result,
      first_esx_pass         = module.esxi_hosts.0.root_password,
      domain_name            = var.domain_name,
      vcenter_network        = var.vcenter_portgroup_name,
      vcenter_domain         = var.vcenter_domain,
      vcva_deployment_option = var.vcva_deployment_option,
      datacenter_name        = var.vcenter_datacenter_name,
    })

    destination = "bootstrap/vcva_template.json"
  }
}

resource "null_resource" "deploy_vcva" {
  depends_on = [
    null_resource.run_pre_reqs,
  ]

  triggers = {
    build_number = "${timestamp()}"
  }

  connection {
    type        = "ssh"
    user        = local.ssh_user
    private_key = chomp(tls_private_key.ssh_key_pair.private_key_pem)
    host        = equinix_metal_device.bastion.access_public_ipv4
  }

  provisioner "file" {
    content     = file("${path.module}/templates/deploy_vcva.py")
    destination = "bootstrap/deploy_vcva.py"
  }

  provisioner "remote-exec" {
    inline = ["python3 $HOME/bootstrap/deploy_vcva.py"]
  }
}

# Setup distributed network portgroups on vsphere

resource "null_resource" "setup_esx_hosts" {
  depends_on = [
    null_resource.deploy_vcva,
  ]

  triggers = {
    build_number = "${timestamp()}"
  }

  connection {
    type        = "ssh"
    user        = local.ssh_user
    private_key = chomp(tls_private_key.ssh_key_pair.private_key_pem)
    host        = equinix_metal_device.bastion.access_public_ipv4
  }

  provisioner "file" {
    content     = file("${path.module}/templates/vsan_claim.py")
    destination = "bootstrap/vsan_claim.py"
  }

  provisioner "file" {
    content     = file("${path.module}/templates/join_esx_hosts.py")
    destination = "bootstrap/join_esx_hosts.py"
  }

  #   provisioner "remote-exec" {
  #     inline = ["python3 $HOME/bootstrap/deploy_vcva.py"]
  #   }
}

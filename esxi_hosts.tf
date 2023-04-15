resource "equinix_metal_device" "esxi_hosts" {
  depends_on              = [equinix_metal_ssh_key.ssh_pub_key]
  count                   = var.esxi_host_count
  hostname                = format("%s%02d", var.esxi_hostname, count.index + 1)
  plan                    = var.esxi_size
  facilities              = var.facility == "" ? null : [var.facility]
  metro                   = var.metro == "" ? null : var.metro
  operating_system        = var.vmware_os
  billing_cycle           = var.billing_cycle
  project_id              = local.project_id
  hardware_reservation_id = lookup(var.reservations, format("%s%02d", var.esxi_hostname, count.index + 1), "")
  ip_address {
    type = "public_ipv4"
  }
  ip_address {
    type = "private_ipv4"
  }
  ip_address {
    type = "public_ipv6"
  }
}

# Have to sleep after ESXi hosts are provisioned, since they reboot the host at end of provisioning
resource "time_sleep" "reboot_post_creation" {
  depends_on      = [equinix_metal_device.esxi_hosts]
  create_duration = "300s"
}

data "template_file" "upgrade_script" {
  count    = var.update_esxi ? 1 : 0
  template = file("${path.module}/templates/update_esxi.sh.tpl")
  vars = {
    esxi_update_filename = "${var.esxi_update_filename}"
  }
}

# Run the ESXi update script file in each server.
# If you make changes to the shell script, you need to update the sed command line number to get rid of te { at the end of the file which gets created by Terraform for some reason.
resource "null_resource" "upgrade_nodes" {
  depends_on = [time_sleep.reboot_post_creation]
  count      = var.update_esxi ? length(equinix_metal_device.esxi_hosts) : 0

  connection {
    user        = local.ssh_user
    private_key = chomp(tls_private_key.ssh_key_pair.private_key_pem)
    host        = element(equinix_metal_device.esxi_hosts.*.access_public_ipv4, count.index)
  }

  provisioner "file" {
    content     = data.template_file.upgrade_script.0.rendered
    destination = "/tmp/update_esxi.sh"
  }

  provisioner "remote-exec" {
    inline = [
      "sed -i '30d' /tmp/update_esxi.sh",
      "echo 'Running update script on remote host.'",
      "chmod +x /tmp/update_esxi.sh",
      "/tmp/update_esxi.sh"
    ]
  }
}

# Give time for hosts to reboot again
resource "time_sleep" "reboot_post_upgrade" {
  depends_on = [null_resource.upgrade_nodes]
  count      = var.update_esxi ? 1 : 0

  create_duration = "300s"
}


# Transition servers to hybrid bonded mode after OS upgrade
resource "equinix_metal_device_network_type" "esxi_hosts" {
  depends_on = [time_sleep.reboot_post_creation, time_sleep.reboot_post_upgrade]
  count      = length(equinix_metal_device.esxi_hosts)
  device_id  = equinix_metal_device.esxi_hosts[count.index].id
  type       = "hybrid-bonded"
}

resource "equinix_metal_port" "esxi_hosts" {
  depends_on = [equinix_metal_device_network_type.esxi_hosts]
  count      = length(equinix_metal_device.esxi_hosts)
  bonded     = true
  layer2     = false
  port_id    = [for p in equinix_metal_device.esxi_hosts[count.index].ports : p.id if p.name == "bond0"][0]
  vlan_ids   = concat(equinix_metal_vlan.private_vlans.*.id, equinix_metal_vlan.public_vlans.*.id)

  reset_on_delete = true
}

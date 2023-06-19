# Provision VM
resource "equinix_metal_device" "esxi_hosts" {
  hostname         = var.esxi_hostname
  plan             = var.esxi_size
  facilities       = var.facility == "" ? null : [var.facility]
  metro            = var.metro == "" ? null : var.metro
  operating_system = var.vmware_os
  billing_cycle    = var.billing_cycle
  project_id       = var.project_id
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
  create_duration = "400s"
}

# Run the ESXi update script file in each server.
# If you make changes to the shell script, you need to update the sed command line number to get rid of te { at the end of the file which gets created by Terraform for some reason.
resource "null_resource" "upgrade_nodes" {
  depends_on = [time_sleep.reboot_post_creation]
  count      = var.update_esxi ? 1 : 0

  connection {
    user        = "root"
    private_key = var.ssh_private_key_pem
    host        = equinix_metal_device.esxi_hosts.access_public_ipv4
  }

  # Update ESXi to latest configured patch version
  provisioner "remote-exec" {
    inline = [
      # Swap must be enabled on the datastore. Otherwise, the upgrade may fail with a "no space left" error.
      "esxcli sched swap system set --datastore-enabled true",
      "esxcli sched swap system set --datastore-name datastore1",

      # DNS is setup for internal resolution, can be flaky
      "esxcli network ip dns server add --server=8.8.8.8",
      "esxcli network ip dns server add --server=8.8.4.4",

      # Handle upgrade
      "vim-cmd /hostsvc/maintenance_mode_enter || true",
      "esxcli network firewall ruleset set -e true -r httpClient",
      "esxcli software profile update -d https://hostupdate.vmware.com/software/VUM/PRODUCTION/main/vmw-depot-index.xml -p ${var.esxi_update_filename} --no-hardware-warning",
      "esxcli network firewall ruleset set -e false -r httpClient",
      "vim-cmd /hostsvc/maintenance_mode_exit || true",
      "reboot",
    ]
  }
}

# Give time for hosts to reboot again
resource "time_sleep" "reboot_post_upgrade" {
  depends_on = [null_resource.upgrade_nodes]
  count      = var.update_esxi ? 1 : 0

  create_duration = "400s" # m3.large can take awhile to reboot
}


# Transition servers to hybrid bonded mode after OS upgrade
resource "equinix_metal_device_network_type" "esxi_hosts" {
  depends_on = [time_sleep.reboot_post_creation, time_sleep.reboot_post_upgrade]
  device_id  = equinix_metal_device.esxi_hosts.id
  type       = "hybrid-bonded"
}

resource "equinix_metal_port" "esxi_hosts" {
  depends_on = [equinix_metal_device_network_type.esxi_hosts]
  bonded     = true
  layer2     = false
  port_id    = [for p in equinix_metal_device.esxi_hosts.ports : p.id if p.name == "bond0"][0]
  vxlan_ids  = flatten([for vlan in var.vlan_ids : vlan.vxlan])

  reset_on_delete = true
}

# Give time for VLANs to apply
resource "time_sleep" "vlan_sleep" {
  depends_on = [equinix_metal_port.esxi_hosts]

  create_duration = "10s"
}

# data "vsphere_datacenter" "datacenter" {
#   depends_on = [time_sleep.vlan_sleep]
#   name       = "default"
# }

# data "vsphere_host" "host" {
#   name          = var.esxi_hostname
#   datacenter_id = data.vsphere_datacenter.datacenter.id
# }

# resource "vsphere_host_port_group" "vlans" {
#   count = length(var.vlan_ids)

#   name                = "TF-${element(var.vlan_ids.*.description, count.index)}"
#   vlan_id             = element(var.vlan_ids.*.id, count.index)
#   host_system_id      = data.vsphere_host.host.id
#   virtual_switch_name = "vSwitch0" # default switch name
#   allow_promiscuous   = true
# }

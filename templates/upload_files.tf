variable "vcenter_ip" {
  type = string
}

variable "vcenter_password" {
  type      = string
  sensitive = true
}

provider "vsphere" {
  user                 = "Administrator@vsphere.local"
  password             = var.vcenter_password
  vsphere_server       = var.vcenter_ip
  allow_unverified_ssl = true
}

locals {
  vcenter_datacenter_name = "Metal"
  vcenter_cluster_name    = "Cluster"
  datastore_name          = "vsanDatastore"
  directory_name          = "uploads"
  files_to_uploads = [
    "en-us_sql_server_2019_enterprise_x64_dvd_46f0ba38.iso",
    "Windows_11_Enterprise_23H2.iso",
    "SW_DVD9_Win_Server_STD_CORE_2022_64Bit_English_DC_STD_MLF_X22-74290.iso",
    #"FreeBSD-13.2-RELEASE-amd64-disc1.iso",
    "ubuntu-22.04.1-live-server-amd64.iso",
    "ubuntu-22.04.2-desktop-amd64.iso",
    "VMware-tools-windows-12.4.0-23259341.iso",
    "euc-unified-access-gateway-23.03.0.0-21401666_OVF10.ova",
    "OPNsense-23.1-OpenSSL-dvd-amd64.iso",
    "ExchangeServer2019-x64-CU13.iso",
  ]
}

data "vsphere_datacenter" "datacenter" {
  name = local.vcenter_datacenter_name
}

data "vsphere_datastore" "datastore" {
  name          = local.datastore_name
  datacenter_id = data.vsphere_datacenter.datacenter.id
}

resource "vsphere_file" "file_upload" {
  for_each = toset(local.files_to_uploads)

  datacenter = data.vsphere_datacenter.datacenter.name
  datastore  = data.vsphere_datastore.datastore.name

  source_file        = "${path.module}/${each.key}"
  destination_file   = "/uploads/${each.key}"
  create_directories = true
}

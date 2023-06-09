data "equinix_metal_project" "project" {
  project_id = var.project_id
}

# data "equinix_metal_facility" "facility" {
#   code = equinix_metal_vlan.private_vlans[0].facility
# }

resource "random_string" "ssh_unique" {
  length  = 5
  special = false
  upper   = false
}

resource "tls_private_key" "ssh_key_pair" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "equinix_metal_ssh_key" "ssh_pub_key" {
  name       = local.ssh_key_name
  public_key = chomp(tls_private_key.ssh_key_pair.public_key_openssh)
}

resource "local_file" "project_private_key_pem" {
  content         = chomp(tls_private_key.ssh_key_pair.private_key_pem)
  filename        = pathexpand("~/.ssh/${local.ssh_key_name}")
  file_permission = "0600"
}

# Setup private VLANs for internal traffic
resource "equinix_metal_vlan" "private_vlans" {
  count       = length(var.private_subnets)
  facility    = var.facility == "" ? null : var.facility
  metro       = var.metro == "" ? null : var.metro
  project_id  = local.project_id
  description = jsonencode(element(var.private_subnets.*.name, count.index))
}

# Setup public IP block and routing table
resource "equinix_metal_reserved_ip_block" "ip_block" {
  project_id = local.project_id
  facility   = var.facility == "" ? null : var.facility
  metro      = var.metro == "" ? null : var.metro
  quantity   = var.public_subnet.ip_count
}

resource "equinix_metal_vlan" "public_vlan" {
  facility    = var.facility == "" ? null : var.facility
  metro       = var.metro == "" ? null : var.metro
  project_id  = local.project_id
  description = var.public_subnet.name
}

# Setup gateway for public IPs to pass traffic
resource "equinix_metal_gateway" "public_vlans" {
  project_id        = local.project_id
  vlan_id           = equinix_metal_vlan.public_vlan.id
  ip_reservation_id = equinix_metal_reserved_ip_block.ip_block.id
}

# Generate random passwords for vCenter & SSO
resource "random_password" "vcenter_password" {
  length           = 16
  min_upper        = 2
  min_lower        = 2
  min_numeric      = 2
  min_special      = 2
  override_special = "$!?@*"
  special          = true
}

resource "random_password" "sso_password" {
  length           = 16
  min_upper        = 2
  min_lower        = 2
  min_numeric      = 2
  min_special      = 2
  override_special = "$!?@*"
  special          = true
}

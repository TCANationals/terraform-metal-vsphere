variable "esxi_hostname" {
  description = "This is the hostname prefix for your esxi hosts. A number will be added to the end."
  type        = string
  default     = "esx"
}

variable "esxi_size" {
  description = "This is the size/plan/flavor of your ESXi machine(s)"
  type        = string
  default     = "c3.medium.x86"
}

variable "facility" {
  description = "This is the Region/Location of your deployment (Must be an IBX facility, Metro will be used if empty)"
  type        = string
  default     = ""
}

variable "metro" {
  description = "This is the Metro Location of your deployment. (Facility will be used if empty)"
  type        = string
  default     = ""
}

variable "vmware_os" {
  description = "This is the version of vSphere that you want to deploy (ESXi 6.5, 6.7, & 7.0 have been tested)"
  type        = string
  default     = "vmware_esxi_7_0"
}

variable "billing_cycle" {
  description = "This is billing cycle to use. The hasn't beend built to allow reserved isntances yet."
  type        = string
  default     = "hourly"
}

variable "project_id" {
  description = "Equinix Metal Project ID to use in case create_project is false"
  type        = string
  default     = "null"
}

variable "update_esxi" {
  description = "if true update the ESXi version before proceeding to vCenter installation"
  type        = bool
  default     = false
}

variable "esxi_update_filename" {
  description = <<-EOF
  The specific update version that your servers will be updated to.
  Note that the Equinix Metal portal and API will still show ESXi 6.5 as the OS but this script adds a tag with the update filename specified below.
  You can check all ESXi update versions/filenames here: https://esxi-patches.v-front.de/
  EOF
  type        = string
  default     = "ESXi-7.0U3d-19482537-standard"
}

variable "ssh_private_key_pem" {
  description = "The private SSH key to connect to the host"
  sensitive   = true
  type        = string
}

variable "vlan_ids" {
  description = "The list of VLANs to bind the host to"
  type = list(object({
    description = optional(string)
    vxlan       = number
  }))
  default = []
}

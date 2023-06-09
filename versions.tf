terraform {
  required_providers {
    null = {
      source = "hashicorp/null"
    }
    equinix = {
      source = "equinix/equinix"
    }
    random = {
      source = "hashicorp/random"
    }
    template = {
      source = "hashicorp/template"
    }
    tls = {
      source = "hashicorp/tls"
    }
    local = {
      source = "hashicorp/local"
    }
    vsphere = {
      source  = "hashicorp/vsphere"
      version = "2.4.0"
    }
  }
  required_version = ">= 0.14"
}

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
  }
  required_version = ">= 0.14"
}

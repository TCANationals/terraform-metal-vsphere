locals {
  ssh_user               = "root"
  project_name_sanitized = replace(data.equinix_metal_project.project.name, "/[ ]/", "_")

  ssh_key_name = format("%s-%s-key", local.project_name_sanitized, random_string.ssh_unique.result)

  project_id = data.equinix_metal_project.project.id
}

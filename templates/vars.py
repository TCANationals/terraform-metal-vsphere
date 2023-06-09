#!/usr/bin/python3
import json

# Vars from Terraform in """ so single quotes from Terraform vars don't escape
private_subnets = json.loads("""${private_subnets}""")
private_vlans = json.loads("""${private_vlans}""")
public_subnets = json.loads("""${public_subnets}""")
public_vlans = json.loads("""${public_vlans}""")
public_cidrs = json.loads("""${public_cidrs}""")
esx_ips = json.loads("""${esx_ips}""")
esx_passwords = json.loads("""${esx_passwords}""")

domain_name = """${domain_name}"""
vcenter_network = """${vcenter_network}"""
vcenter_fqdn = """${vcenter_fqdn}"""
vcenter_user = """${vcenter_user}"""
vcenter_domain = """${vcenter_domain}"""
vcenter_cluster_name = """${vcenter_cluster_name}"""
metal_token = """${metal_token}"""
vcenter_username = """${vcenter_user}@${vcenter_domain}"""
sso_password = """${sso_password}"""
dc_name = """${dc_name}"""
plan_type = """${plan_type}"""

# vcenter_password is not used

# assign IPs from public_cidrs
vcenter_ip = """${vcenter_ip}"""
opnsense_ip = """${opnsense_ip}"""
uag_ip = """${uag_ip}"""
primary_public_gateway = """${primary_public_gateway}"""
primary_public_vlan_id = """${primary_public_vlan_id}"""


# Build single subnet map with all vlans, cidrs, etc...
subnets = private_subnets

for i in range(len(private_vlans)):
    subnets[i]["vlan"] = private_vlans[i]

for i in range(len(public_vlans)):
    public_subnets[i]["vlan"] = public_vlans[i]
    public_subnets[i]["cidr"] = public_cidrs[i]
    subnets.append(public_subnets[i])

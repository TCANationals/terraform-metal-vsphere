import os
import sys
import json
from time import sleep
from pyVmomi import vim
from pyVim import connect
from vars import (
    private_subnets,
    public_subnets,
    public_vlans,
    public_cidrs,
    esx_passwords,
    esx_ips,
    vcenter_username,
    sso_password,
    dc_name,
    vcenter_cluster_name,
    vcenter_network,
    domain_name,
    vcenter_ip,
    primary_public_gateway,
)
from functions import (
    get_active_switch,
    create_port_group,
    get_ssl_thumbprint,
    connectToApi,
    getEsxStorageAssignments,
)

subnets = private_subnets

for i in range(len(public_cidrs)):
    public_subnets[i]["cidr"] = public_cidrs[i]
    subnets.append(public_subnets[i])

esx = []
for i in range(len(esx_ips)):
    esx.append({"password": esx_passwords[i], "ip": esx_ips[i]})

for subnet in subnets:
    if subnet["name"] == vcenter_network:
        prefix_length = int(subnet["cidr"].split("/")[1])

# connect to ESX to figure out disks
# Connect to vCenter
esx1_datastore_info = getEsxStorageAssignments(esx[0]["ip"], "root", esx[0]["password"])

os.system(
    "sed -i -e 's/__ESXI_IP__/{}/g' "
    "-e 's/__VCENTER_IP__/{}/g' "
    "-e 's/__VCENTER_GATEWAY__/{}/g' "
    "-e 's/__VCENTER_PREFIX_LENGTH__/{}/g' "
    "$HOME/bootstrap/vcva_template.json".format(
        esx[0]["ip"], vcenter_ip, primary_public_gateway, prefix_length
    )
)

# load JSON file to replace used disks
vcva_template_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vcva_template.json')
with open(vcva_template_file) as f:
   vcva_template = json.load(f)

vsan_disks = vcva_template['new_vcsa']['esxi']['VCSA_cluster']['disks_for_vsan']
cache_disks = []
capacity_disks = []

for host, disks in esx1_datastore_info.items():
    if len(disks["cache"]) > len(disks["capacity"]):
        disks["cache"] = disks["cache"][: len(disks["capacity"])]

    for disk in disks["cache"]:
        cache_disks.append(disk.canonicalName)
    
    for disk in disks["capacity"]:
        capacity_disks.append(disk.canonicalName)

vcva_template['new_vcsa']['esxi']['VCSA_cluster']['disks_for_vsan']['cache_disk'] = cache_disks
vcva_template['new_vcsa']['esxi']['VCSA_cluster']['disks_for_vsan']['capacity_disk'] = capacity_disks

# Add local Internet portgroup
esx1_host, si = connectToApi(esx[0]["ip"], "root", esx[0]["password"])
esx1_active_switch = get_active_switch(esx1_host)
create_port_group(esx1_host, f'TF-Internet', esx1_active_switch, public_vlans[0]) # only ever 1 public vlan

vcva_template['new_vcsa']['esxi']['deployment_network'] = f'TF-Internet'

# Write out updated file
with open(vcva_template_file, "w") as outfile:
    outfile.write(json.dumps(vcva_template))

os.system(
    "/mnt/vcsa-cli-installer/lin64/vcsa-deploy install --accept-eula --acknowledge-ceip "
    "--no-esx-ssl-verify $HOME/bootstrap/vcva_template.json"
)

# Connect to vCenter
si = None
for i in range(1, 30):
    try:
        si = connect.SmartConnect(
            host=vcenter_ip, user=vcenter_username, pwd=sso_password, port=443, disableSslCertValidation=True
        )
        break
    except Exception:
        sleep(10)
if si is None:
    print("Couldn't connect to vCenter!!!")
    sys.exit(1)

# Create Datacenter in the root folder
folder = si.content.rootFolder
#dc = folder.CreateDatacenter(name=dc_name)
dc = folder.childEntity[0] # data center created from vsan setup

# Create cluster config
cluster_config = vim.cluster.ConfigSpecEx()

# Create DRS config
drs_config = vim.cluster.DrsConfigInfo()
drs_config.enabled = True
cluster_config.drsConfig = drs_config

# if len(esx) > 2:
#     # Create vSan config
#     vsan_config = vim.vsan.cluster.ConfigInfo()
#     vsan_config.enabled = True
#     vsan_config.defaultConfig = vim.vsan.cluster.ConfigInfo.HostDefaultInfo(
#         autoClaimStorage=True
#     )
#     cluster_config.vsanConfig = vsan_config

# # Create HA config
# if len(esx) > 1:
#     ha_config = vim.cluster.DasConfigInfo()
#     ha_config.enabled = True
#     ha_config.hostMonitoring = vim.cluster.DasConfigInfo.ServiceState.enabled
#     ha_config.failoverLevel = 1
#     cluster_config.dasConfig = ha_config

# Create the cluster
# host_folder = dc.hostFolder
# cluster = host_folder.CreateClusterEx(name=vcenter_cluster_name, spec=cluster_config)

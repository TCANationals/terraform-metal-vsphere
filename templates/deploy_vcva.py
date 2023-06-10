import os
import sys
import json
from time import sleep
from pyVmomi import vim, pbm
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
    files_to_upload,
)
from functions import (
    get_active_switch,
    create_port_group,
    wait_for_task,
    get_ssl_thumbprint,
    connectToApi,
    getEsxStorageAssignments,
    pbm_connect,
    get_all_storage_profiles,
    upload_file_to_datastore,
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
cluster, si = connectToApi(vcenter_ip, vcenter_username, sso_password)

# Create Datacenter in the root folder
folder = si.content.rootFolder
#dc = folder.CreateDatacenter(name=dc_name)
dc = folder.childEntity[0] # data center created from vsan setup

# Create DVS config
network_folder = dc.networkFolder
pnic_specs = []
dvs_host_configs = []
uplink_port_names = ["dvUplink0", "dvUplink1"] # unused, all hosts will use LAG
dvs_create_spec = vim.DistributedVirtualSwitch.CreateSpec()

dvs_config_spec = vim.dvs.VmwareDistributedVirtualSwitch.ConfigSpec()
dvs_config_spec.name = 'metalSwitch0'
dvs_config_spec.uplinkPortPolicy = vim.DistributedVirtualSwitch.NameArrayUplinkPortPolicy()

dvs_config_spec.maxMtu = 9000

dvs_config_spec.uplinkPortPolicy.uplinkPortName = uplink_port_names

# Setup LACP for link discovery per Equinix docs
link_discov_config = vim.host.LinkDiscoveryProtocolConfig()
link_discov_config.protocol = vim.host.LinkDiscoveryProtocolConfig.ProtocolType.lldp
link_discov_config.operation = vim.host.LinkDiscoveryProtocolConfig.OperationType.listen
dvs_config_spec.linkDiscoveryProtocolConfig = link_discov_config

dvs_create_spec.configSpec = dvs_config_spec
dvs_create_spec.productInfo = vim.dvs.ProductSpec(version='7.0.3')

task = network_folder.CreateDVS_Task(dvs_create_spec)
wait_for_task(task, si)
dvs = task.info.result # created switch

# Setup link aggregation group once the switch is created
lacp_config = vim.dvs.VmwareDistributedVirtualSwitch.LacpGroupConfig()
lacp_config.name = 'lag0'
lacp_config.mode = vim.dvs.VmwareDistributedVirtualSwitch.UplinkLacpMode.active
lacp_config.uplinkNum = 4 # max number of NICs on a server
lacp_config.loadbalanceAlgorithm = vim.dvs.VmwareDistributedVirtualSwitch.LacpLoadBalanceAlgorithm.srcDestIpTcpUdpPortVlan

lacp_create_spec = vim.dvs.VmwareDistributedVirtualSwitch.LacpGroupSpec()
lacp_create_spec.lacpGroupConfig = lacp_config
lacp_create_spec.operation = vim.ConfigSpecOperation.add

lacp_task = dvs.UpdateDVSLacpGroupConfig_Task([lacp_create_spec])
wait_for_task(lacp_task, si)

# Disable all vSAN replica requirements (manually turn these on later!)
pbm_content = pbm_connect(si._stub)
pm = pbm_content.profileManager

all_storage_profiles = get_all_storage_profiles(pm)

# Find storage profiles with constraints so we can remove them
constrained_storage_profiles = []
denied_profile_list = [
    'Host-local PMem Default Storage Policy'.lower(),
    'vSAN ESA Default Policy - RAID5'.lower(),
    'vSAN ESA Default Policy - RAID6'.lower(),
]
for storage_profile in all_storage_profiles:
    if storage_profile.constraints and type(storage_profile.constraints) == pbm.profile.SubProfileCapabilityConstraints:
        if not storage_profile.isDefault and storage_profile.name[0:25].lower() != 'Management Storage Policy'.lower():
            if storage_profile.name.lower() not in denied_profile_list:
                constrained_storage_profiles.append(storage_profile)

for profile in constrained_storage_profiles:
    for subprofile in profile.constraints.subProfiles:
        pm.PbmUpdate(
            profileId=profile.profileId,
            updateSpec=pbm.profile.CapabilityBasedProfileUpdateSpec(
                description=None,
                constraints=pbm.profile.SubProfileCapabilityConstraints(
                    subProfiles=[
                        pbm.profile.SubProfileCapabilityConstraints.SubProfile(
                            name=subprofile.name,
                            capability=[
                                pbm.capability.CapabilityInstance(
                                    id=pbm.capability.CapabilityMetadata.UniqueId(
                                        namespace='VSAN',
                                        id='hostFailuresToTolerate'
                                    ),
                                    constraint=[
                                        pbm.capability.ConstraintInstance(
                                            propertyInstance=[
                                                pbm.capability.PropertyInstance(
                                                    id='hostFailuresToTolerate',
                                                    value=0
                                                )
                                            ]
                                        )
                                    ]
                                )
                            ]
                        )
                    ]
                )
            )
        )

# # Upload local files to vCenter
# datastore = None
# datastores_object_view = si.content.viewManager.CreateContainerView(
#     dc,
#     [vim.Datastore],
#     True)

# for ds_obj in datastores_object_view.view:
#     if ds_obj.info.name == 'vsanDatastore':
#         datastore = ds_obj

# if not datastore:
#     print("Could not find the datastore specified")
#     sys.exit(1)

# # Clean up the views now that we have what we need
# datastores_object_view.Destroy()

# # Create directory for uploaded files
# fileManager = si.content.fileManager
# fileManager.MakeDirectory('[vsanDatastore] uploads', createParentDirectories=True, datacenter=dc)

# for file in files_to_upload:
#     upload_file_to_datastore(file, datastore, dc, esx[0]["ip"], si)

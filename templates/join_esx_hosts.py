import ipaddress
import os
import sys
import subprocess
import socket
import requests
import urllib3
import json
from time import sleep
from pyVmomi import vim, vmodl
from pyVim import connect
from vars import (
    private_subnets,
    public_subnets,
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
    wait_for_task,
    get_ssl_thumbprint,
    connectToApi,
    get_obj,
    create_distributed_port_group,
    getEsxStorageAssignments,
    join_esx_host_to_vc,
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

# Connect to vCenter
host, si = connectToApi(vcenter_ip, vcenter_username, sso_password) # will pick a random host
cluster = host.parent
folder = si.content.rootFolder
dc = folder.childEntity[0] # data center

# Make sure PortGroups are setup
network_folder = dc.networkFolder
mainSwitch = get_obj(si.content, [vim.DistributedVirtualSwitch], 'metalSwitch0')

# Setup passthrough PG
try:
    create_distributed_port_group(si, f'DPG-NativeTraffic', mainSwitch, 0)
except Exception as e:
    print('Error creating native PG, ignoring...')
    print(e)

# Setup VLAN-based PGs
for subnet in subnets:
    create_distributed_port_group(si, f'DPG-{subnet["name"]}', mainSwitch, subnet['vlan'])

# Join hosts to the cluster
for host in esx:
    join_esx_host_to_vc(si, host, cluster)

# Add hosts to switch
# for host in esx:
#     add_esx_host_to_dvs(host, cluster)

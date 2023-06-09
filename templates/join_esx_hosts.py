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
from vmware.vapi.vsphere.client import create_vsphere_client
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

# no legit SSL, silence all errors
session = requests.session()
session.verify = False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_ssl_thumbprint(host_ip):
    p1 = subprocess.Popen(
        ("echo", "-n"), stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    p2 = subprocess.Popen(
        ("openssl", "s_client", "-connect", "{0}:443".format(host_ip)),
        stdin=p1.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    p3 = subprocess.Popen(
        ("openssl", "x509", "-noout", "-fingerprint", "-sha1"),
        stdin=p2.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out = p3.stdout.read()
    ssl_thumbprint = out.split(b"=")[-1].strip()
    return ssl_thumbprint.decode("utf-8")

def get_datastore_info(vi):
    datastores = {}
    disks = {}
    try:
        content = vi.RetrieveContent()
        # Search for all ESXi hosts
        objview = content.viewManager.CreateContainerView(content.rootFolder, [vim.HostSystem], True)
        esxi_hosts = objview.view
        objview.Destroy()
        for esxi_host in esxi_hosts:
            print("{}\t{}\t\n".format("ESXi Host:    ", esxi_host.name))
            # All Filesystems on ESXi host
            storage_system = esxi_host.configManager.storageSystem
            host_file_sys_vol_mount_info = storage_system.fileSystemVolumeInfo.mountInfo
            storage_device_luns = storage_system.storageDeviceInfo.scsiLun
            datastore_dict = {}
            # Map all filesystems
            for host_mount_info in host_file_sys_vol_mount_info:
                # Extract only VMFS volumes
                if host_mount_info.volume.type == "VMFS":
                    extents = host_mount_info.volume.extent
                    datastore_details = {
                        'uuid': host_mount_info.volume.uuid,
                        'capacity': host_mount_info.volume.capacity,
                        'vmfs_version': host_mount_info.volume.version,
                        'local': host_mount_info.volume.local,
                        'ssd': host_mount_info.volume.ssd,
                    }
                    extent_arr = []
                    for extent in extents:
                        # create an array of the devices backing the given datastore
                        extent_arr.append(extent.diskName)
                        # add the extent array to the datastore info
                        datastore_details['extents'] = extent_arr
                        # associate datastore details with datastore name
                        datastore_dict[host_mount_info.volume.name] = datastore_details
            disk_list = []
            for storage_device_lun in storage_device_luns:
                if storage_device_lun.lunType == 'disk':
                    disk_list.append(storage_device_lun.canonicalName)
            # associate ESXi host with the datastore it sees
            datastores[esxi_host.name] = datastore_dict
            disks[esxi_host.name] = disk_list
    except vmodl.MethodFault as error:
        print("Could not get ESX disk info!")
        print(error)
        sys.exit(1)
    return (datastores, disks)

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
dc = folder.CreateDatacenter(name=dc_name)

# Create cluster config
cluster_config = vim.cluster.ConfigSpecEx()

# Create DRS config
drs_config = vim.cluster.DrsConfigInfo()
drs_config.enabled = True
cluster_config.drsConfig = drs_config

# Create the cluster
host_folder = dc.hostFolder
cluster = host_folder.CreateClusterEx(name=vcenter_cluster_name, spec=cluster_config)

# Join hosts to the cluster
for host in esx:
    print(
        "Joining host {} to the cluster".format(host["ip"])
    )
    host_connect_spec = vim.host.ConnectSpec()
    host_connect_spec.hostName = host["ip"]
    host_connect_spec.userName = "root"
    host_connect_spec.password = host["password"]
    host_connect_spec.force = True
    host_connect_spec.sslThumbprint = get_ssl_thumbprint(host["ip"])
    cluster.AddHost(spec=host_connect_spec, asConnected=True)

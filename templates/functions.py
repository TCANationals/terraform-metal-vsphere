import sys
import subprocess
from time import sleep
from pyVmomi import vim
from pyVim import connect
import vsanapiutils
import requests
import ssl
from vars import (
    vcenter_fqdn,
    vcenter_username,
    sso_password,
    vcenter_cluster_name,
    plan_type,
)

# Workaround for SSL verification for VMware APIs
requests.packages.urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE

# vSAN deployment types, handles Equinix storage servers
if plan_type[0].lower() == "s":
    deploy_type = "hybrid"
else:
    deploy_type = "allFlash"


def connectToApi(host, user, password):
    si = None
    for i in range(1, 30):
        try:
            si = connect.SmartConnect(
                host=host, user=user, pwd=password, port=443, disableSslCertValidation=True
            )
            break
        except Exception:
            sleep(10)
    if si is None:
        print("Couldn't connect to host!!!")
        sys.exit(1)
    content = si.RetrieveContent()
    host = content.viewManager.CreateContainerView(
        content.rootFolder, [vim.HostSystem], True
    ).view[0]
    return host, si


def get_active_switch(host):
    host_name = host.name
    host_network_system = host.configManager.networkSystem
    online_pnics = []

    for i in range(1, 6):
        for pnic in host.config.network.pnic:
            if pnic.linkSpeed:
                online_pnics.append(pnic)
        if len(online_pnics) >= 1:
            break
        else:
            print(
                "Couldn't find a physical nic with a link speed. Sleeping 10 seconds and checking again."
            )
            sleep(10)

    if len(online_pnics) <= 0:
        print(
            f"ERROR: Couldn't find a physical nic with a link speed for over 1 minute. Exiting!!!"
        )
        sys.exit(1)

    active_switch = None
    for vswitch in host_network_system.networkInfo.vswitch:
        for pnic in vswitch.pnic:
            for n in range(len(online_pnics)):
                if pnic == online_pnics[n].key:
                    if vswitch.name == 'vSwitch0':
                        active_switch = vswitch
                        break

    if len(online_pnics) <= 0:
        print(
            "No additional uplink is active! Please email support@equinixmetal.com and tell them you think this server has a bad NIC!"
        )
        sys.exit(1)
    
    if active_switch is None:
        print(
            "No active switch found!"
        )
        sys.exit(1)
    
    return active_switch

def create_port_group(host, pg_name, switch, vlan_id):
    host_network_system = host.configManager.networkSystem

    for pg in switch.portgroup:
        if pg == f'key-vim.host.PortGroup-{pg_name}':
            print('PortGroup already exists, will not recreate', pg_name)
            return

    port_group_spec = vim.host.PortGroup.Specification()
    port_group_spec.name = pg_name
    port_group_spec.vlanId = vlan_id
    port_group_spec.vswitchName = switch.name

    security_policy = vim.host.NetworkPolicy.SecurityPolicy()
    security_policy.allowPromiscuous = True
    security_policy.forgedTransmits = True
    security_policy.macChanges = True

    port_group_spec.policy = vim.host.NetworkPolicy(security=security_policy)

    host_network_system.AddPortGroup(portgrp=port_group_spec)

    print("Successfully created PortGroup ", pg_name)


def getEsxStorageAssignments(host, user, password):
    host, si = connectToApi(host, user, password)
    cluster = getHostInstance(si)
    hostProps = CollectMultiple(
        si.content,
        cluster.host,
        ["name", "configManager.vsanSystem", "configManager.storageSystem"],
    )
    hosts = hostProps.keys()
    diskmap = {host: {"cache": [], "capacity": []} for host in hosts}
    cacheDisks = []
    capacityDisks = []
    for host in hosts:
        ssds = [
            result.disk
            for result in hostProps[host]["configManager.vsanSystem"].QueryDisksForVsan()
            if result.state == "eligible" and result.disk.ssd
        ]
        smallerSize = min([disk.capacity.block * disk.capacity.blockSize for disk in ssds])
        for ssd in ssds:
            size = ssd.capacity.block * ssd.capacity.blockSize
            if size == smallerSize:
                diskmap[host]["cache"].append(ssd)
                cacheDisks.append(
                    (ssd.displayName, sizeof_fmt(size), hostProps[host]["name"])
                )
            else:
                diskmap[host]["capacity"].append(ssd)
                capacityDisks.append(
                    (ssd.displayName, sizeof_fmt(size), hostProps[host]["name"])
                )
    return diskmap


def sizeof_fmt(num, suffix="B"):
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, "Yi", suffix)


# Assumes a single host (non-VC joined)
def getHostInstance(serviceInstance):
    content = serviceInstance.RetrieveContent()
    datacenters = content.rootFolder.childEntity
    for datacenter in datacenters:
        hosts = datacenter.hostFolder.childEntity
        if hosts is not None:
            return hosts[0]
    return None


def getClusterInstance(clusterName, serviceInstance):
    content = serviceInstance.RetrieveContent()
    searchIndex = content.searchIndex
    datacenters = content.rootFolder.childEntity
    for datacenter in datacenters:
        cluster = searchIndex.FindChild(datacenter.hostFolder, clusterName)
        if cluster is not None:
            return cluster
    return None


def CollectMultiple(content, objects, parameters, handleNotFound=True):
    if len(objects) == 0:
        return {}
    result = None
    pc = content.propertyCollector
    propSet = [vim.PropertySpec(type=objects[0].__class__, pathSet=parameters)]
    while result is None and len(objects) > 0:
        try:
            objectSet = []
            for obj in objects:
                objectSet.append(vim.ObjectSpec(obj=obj))
            specSet = [vim.PropertyFilterSpec(objectSet=objectSet, propSet=propSet)]
            result = pc.RetrieveProperties(specSet=specSet)
        except vim.ManagedObjectNotFound as ex:
            objects.remove(ex.obj)
            result = None
    out = {}
    for x in result:
        out[x.obj] = {}
        for y in x.propSet:
            out[x.obj][y.name] = y.val
    return out

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

import os
import sys
import subprocess
from time import sleep
from pyVmomi import pbm, vim, VmomiSupport, SoapStubAdapter
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


def create_distributed_port_group(si, pg_name, switch, vlan_id):
    for pg in switch.portgroup:
        if pg.name == pg_name:
            print('PortGroup already exists, will not recreate', pg_name)
            return

    port_group_spec = vim.dvs.DistributedVirtualPortgroup.ConfigSpec()
    port_group_spec.name = pg_name
    port_group_spec.type = vim.dvs.DistributedVirtualPortgroup.PortgroupType.ephemeral

    port_group_spec.defaultPortConfig = vim.dvs.VmwareDistributedVirtualSwitch.VmwarePortConfigPolicy()

    port_group_spec.defaultPortConfig.securityPolicy = vim.dvs.VmwareDistributedVirtualSwitch.SecurityPolicy()
    port_group_spec.defaultPortConfig.securityPolicy.macChanges = vim.BoolPolicy(value=False)
    port_group_spec.defaultPortConfig.securityPolicy.inherited = False
    port_group_spec.defaultPortConfig.securityPolicy.allowPromiscuous = vim.BoolPolicy(value=True)
    port_group_spec.defaultPortConfig.securityPolicy.forgedTransmits = vim.BoolPolicy(value=True)  

    port_group_spec.defaultPortConfig.vlan = vim.dvs.VmwareDistributedVirtualSwitch.VlanIdSpec()
    port_group_spec.defaultPortConfig.vlan.vlanId = vlan_id
    port_group_spec.defaultPortConfig.vlan.inherited = False

    port_group_spec.defaultPortConfig.uplinkTeamingPolicy = vim.dvs.VmwareDistributedVirtualSwitch.UplinkPortTeamingPolicy()
    port_group_spec.defaultPortConfig.uplinkTeamingPolicy.uplinkPortOrder = vim.dvs.VmwareDistributedVirtualSwitch.UplinkPortOrderPolicy()
    port_group_spec.defaultPortConfig.uplinkTeamingPolicy.uplinkPortOrder.activeUplinkPort = ['lag0'] # from deploy_vcva script
    port_group_spec.defaultPortConfig.uplinkTeamingPolicy.uplinkPortOrder.standbyUplinkPort = []

    task = switch.AddDVPortgroup_Task([port_group_spec])
    wait_for_task(task, si)

    print("Successfully created PortGroup ", pg_name)


def join_esx_host_to_vc(si, host, cluster):
    print(
        "Joining host {} to the cluster".format(host["ip"])
    )

    for joinedHost in cluster.host:
        if joinedHost.name == host["ip"]:
            print("Host already joined, skipping...")
            return

    host_connect_spec = vim.host.ConnectSpec()
    host_connect_spec.hostName = host["ip"]
    host_connect_spec.userName = "root"
    host_connect_spec.password = host["password"]
    host_connect_spec.force = True
    host_connect_spec.sslThumbprint = get_ssl_thumbprint(host["ip"])
    task = cluster.AddHost_Task(spec=host_connect_spec, asConnected=True)
    wait_for_task(task, si)
    return

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


def get_obj(content, vimtype, name):
    """
     Get the vsphere object associated with a given text name
    """    
    obj = None
    container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
    for c in container.view:
        if c.name == name:
            obj = c
            break
    return obj


def wait_for_task(task, actionName='job', hideResult=False):
    """
    Waits and provides updates on a vSphere task
    """
    
    while task.info.state == vim.TaskInfo.State.running:
        sleep(2)
    
    if task.info.state == vim.TaskInfo.State.success:
        if task.info.result is not None and not hideResult:
            out = '%s completed successfully, result: %s' % (actionName, task.info.result)
            print(out)
        else:
            out = '%s completed successfully.' % actionName
            print(out)
    else:
        out = '%s did not complete successfully: %s' % (actionName, task.info.error)
        print(out)
        print(task.info.error)
        return False
    
    return task.info.result


def get_all_storage_profiles(profile_manager):
    """Search vmware storage policy profile by name
    :param profile_manager: A VMware Storage Policy Service manager object
    :type profileManager: pbm.profile.ProfileManager
    :param name: A VMware Storage Policy profile name
    :type name: str
    :returns: A VMware Storage Policy profile
    :rtype: pbm.profile.Profile
    """
    profile_ids = profile_manager.PbmQueryProfile(
        resourceType=pbm.profile.ResourceType(resourceType="STORAGE"),
        profileCategory="REQUIREMENT"
    )

    if len(profile_ids) > 0:
        storage_profiles = profile_manager.PbmRetrieveContent(
            profileIds=profile_ids)

    return storage_profiles

def pbm_connect(stub_adapter, disable_ssl_verification=True):
    """Connect to the VMware Storage Policy Server
    :param stub_adapter: The ServiceInstance stub adapter
    :type stub_adapter: SoapStubAdapter
    :param disable_ssl_verification: A flag used to skip ssl certificate
        verification (default is False)
    :type disable_ssl_verification: bool
    :returns: A VMware Storage Policy Service content object
    :rtype: ServiceContent
    """

    if disable_ssl_verification:
        import ssl
        if hasattr(ssl, '_create_unverified_context'):
            ssl_context = ssl._create_unverified_context()
        else:
            ssl_context = None
    else:
        ssl_context = None

    VmomiSupport.GetRequestContext()["vcSessionCookie"] = \
        stub_adapter.cookie.split('"')[1]
    hostname = stub_adapter.host.split(":")[0]
    pbm_stub = SoapStubAdapter(
        host=hostname,
        version="pbm.version.version1",
        path="/pbm/sdk",
        poolSize=0,
        sslContext=ssl_context)
    pbm_si = pbm.ServiceInstance("ServiceInstance", pbm_stub)
    pbm_content = pbm_si.RetrieveContent()
    return pbm_content


def upload_file_to_datastore(filename, datastore, datacenter, host, si):
    resource = f"/folder/[vsanDatastore] uploads/{filename}"
    params = {"dsName": datastore.info.name, "dcPath": datacenter.name}
    http_url = "https://" + host + ":443" + resource

    # Get the cookie built from the current session
    client_cookie = si._stub.cookie
    # Break apart the cookie into it's component parts - This is more than
    # is needed, but a good example of how to break apart the cookie
    # anyways. The verbosity makes it clear what is happening.
    cookie_name = client_cookie.split("=", 1)[0]
    cookie_value = client_cookie.split("=", 1)[1].split(";", 1)[0]
    cookie_path = client_cookie.split("=", 1)[1].split(";", 1)[1].split(
        ";", 1)[0].lstrip()
    cookie_text = " " + cookie_value + "; $" + cookie_path
    # Make a cookie
    cookie = dict()
    cookie[cookie_name] = cookie_text

    # Get the request headers set up
    headers = {'Content-Type': 'application/octet-stream'}

    # Get the file to upload ready, extra protection by using with against
    # leaving open threads
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), "rb") as file_data:
        # Connect and upload the file
        requests.put(http_url,
                        params=params,
                        data=file_data,
                        headers=headers,
                        cookies=cookie,
                        verify=False)
    print("uploaded the file")

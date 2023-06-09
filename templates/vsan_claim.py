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

# A large portion of this code was lifted from: https://github.com/storage-code/vsanDeploy/blob/master/vsanDeploy.py






tasks = []
for host, disks in diskmap.items():
    if len(disks["cache"]) > len(disks["capacity"]):
        disks["cache"] = disks["cache"][: len(disks["capacity"])]
    try:
        dm = vim.VimVsanHostDiskMappingCreationSpec(
            cacheDisks=disks["cache"],
            capacityDisks=disks["capacity"],
            creationType=deploy_type,
            host=host,
        )
        task = vsanVcDiskManagementSystem.InitializeDiskMappings(dm)
        tasks.append(task)
    except:  # noqa: E722
        print("Some vSan Claim error... Check vSan...")

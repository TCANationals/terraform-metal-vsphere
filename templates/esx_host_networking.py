import ipaddress
import packet as metal
import optparse
import sys
from time import sleep
from pyVmomi import vim
from pyVim import connect
from subprocess import Popen
from vars import (
    private_subnets,
    private_vlans,
    public_subnets,
    public_vlans,
    public_cidrs,
    domain_name,
)

# Build single subnet map with all vlans, cidrs, etc...
subnets = private_subnets

for i in range(len(private_vlans)):
    subnets[i]["vlan"] = private_vlans[i]

for i in range(len(public_vlans)):
    public_subnets[i]["vlan"] = public_vlans[i]
    public_subnets[i]["cidr"] = public_cidrs[i]
    subnets.append(public_subnets[i])


class bcolors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def create_port_group(host_network_system, pg_name, switch, vlan_id):
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


def connect_to_host(esx_host, esx_user, esx_pass):
    for i in range(1, 30):
        si = None
        try:
            print("Trying to connect to ESX Host . . .")
            si = connect.SmartConnect(
                host=esx_host, user=esx_user, pwd=esx_pass, port=443, disableSslCertValidation=True
            )
            break
        except Exception:
            print(
                "There was a connection Error to host: {}. Sleeping 10 seconds and trying again.".format(
                    esx_host
                )
            )
            sleep(10)
        if i == 30:
            return None, None
    print("Connected to ESX Host !")
    content = si.RetrieveContent()
    host = content.viewManager.CreateContainerView(
        content.rootFolder, [vim.HostSystem], True
    ).view[0]
    return host, si


def prepare_parser():
    parser = optparse.OptionParser(
        usage="%prog --host <host_ip> --user <username> --pass <password>"
    )
    parser.add_option(
        "--host", dest="host", action="store", help="IP or FQDN of the ESXi host"
    )
    parser.add_option(
        "--user",
        dest="user",
        action="store",
        help="Username to authenticate to ESXi host",
    )
    parser.add_option(
        "--pass",
        dest="pw",
        action="store",
        help="Password to authenticarte to ESXi host",
    )
    return parser


def main():  # noqa: C901
    parser = prepare_parser()
    options, _ = parser.parse_args()
    if not (
        options.host
        and options.user
        and options.pw
    ):
        print("ERROR: Missing arguments")
        parser.print_usage()
        sys.exit(1)

    host, si = connect_to_host(options.host, options.user, options.pw)
    if si is None or host is None:
        print(
            "Couldn't connect to host: {} after 5 minutes. Skipping...".format(
                options.host
            )
        )
        sys.exit(1)

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
            f"{bcolors.FAIL}ERROR: Couldn't find a physical nic with a link speed for over 1 minute. Exiting!!!{bcolors.ENDC}"
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

    # Setup port groups for all known VLANs
    for subnet in subnets:
        create_port_group(
            host_network_system, f'TF-{subnet["name"]}', active_switch, subnet["vlan"]
        )
    connect.Disconnect(si)


# Start program
if __name__ == "__main__":
    main()

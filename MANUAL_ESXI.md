# Manual ESXi Install on Equinix Metal

Since Equinix metal has removed automated install support for ESXi, it must be manually installed. Follow these steps:

1) Start a server with `custom_ipxe` as the OS. Set the URL to `https://boot.netboot.xyz/`. Enable "Always PXE".

2) Once the server is provisioned, connect to the SOS console. Reboot as needed to get Netboot Menu.

3) Choose "Linux Network Installs", then "VMware ESXi". Use the following base URL:

	http://s3.amazonaws.com/files.tcanationals.com/esxi/ESXi-8.0.3-24674464

4) Follow ESXi install prompts. Once system is installed, disable PXE & boot into Rescue OS on Equinix console.

5) Run the following command to mount the ESXi boot drive:

	mount -t vfat /dev/sda5 /mnt

6) Edit `/mnt/boot.cfg`. Append the following to the end of the `kernelopts` line:

	gdbPort=none logPort=none tty2Port=com2

7) Reboot server

8) Add server to correct VLANs in Equinix console

9) Using SOS console, update management IP & VLANs as needed

Notes
---

* `c3.medium.x86` for vCenter & firewall
* `m3.large.x86` for everything else

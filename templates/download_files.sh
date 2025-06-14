#!/bin/bash

SSH_PRIVATE_KEY='${ssh_private_key}'

# TODO: This should probably not be hidden in the download_vcenter.sh
cat <<EOF >/$HOME/.ssh/esxi_key
$SSH_PRIVATE_KEY
EOF
chmod 0400 /$HOME/.ssh/esxi_key
# END TODO
echo "Set SSH config to not do StrictHostKeyChecking"
cat <<EOF >/$HOME/.ssh/config
Host *
    StrictHostKeyChecking no
EOF
chmod 0400 /$HOME/.ssh/config

BASE_DIR="/$HOME/bootstrap"

mkdir -p $BASE_DIR
cd $BASE_DIR

sudo apt-get update
sudo apt-get install -y lighttpd

echo "USING S3"
curl -Lo mc https://dl.min.io/client/mc/release/linux-amd64/archive/mc.RELEASE.2022-01-07T06-01-38Z
echo -n '33d25b2242626d1e07ce7341a9ecc2164c0ef5c0  mc' | shasum -a1 -c - && chmod +x mc
mv mc /usr/local/bin/
mc config host add s3 ${s3_url} ${s3_access_key} ${s3_secret_key}

# Download ISOs
mc cp s3/${object_store_bucket_name}/en-us_sql_server_2019_enterprise_x64_dvd_46f0ba38.iso .
mc cp s3/${object_store_bucket_name}/Windows_11_Enterprise_23H2.iso .
mc cp s3/${object_store_bucket_name}/en-us_windows_11_enterprise_ltsc_2024_x64_dvd_965cfb00.iso .
mc cp s3/${object_store_bucket_name}/SW_DVD9_Win_Server_STD_CORE_2022_64Bit_English_DC_STD_MLF_X22-74290.iso .
#mc cp s3/${object_store_bucket_name}/FreeBSD-13.2-RELEASE-amd64-disc1.iso .
mc cp s3/${object_store_bucket_name}/ubuntu-22.04.1-live-server-amd64.iso .
mc cp s3/${object_store_bucket_name}/ubuntu-22.04.2-desktop-amd64.iso .
mc cp s3/${object_store_bucket_name}/OPNsense-25.1-dvd-amd64.iso .
mc cp s3/${object_store_bucket_name}/ExchangeServer2019-x64-CU13.iso .

# Download vmware tools ISO
mc cp s3/${object_store_bucket_name}/VMware-tools-windows-12.5.2-24697584.iso .

# Download vCenter ISO
mc cp s3/${object_store_bucket_name}/${vcenter_iso_name} .

# Download OVAs
mc cp s3/${object_store_bucket_name}/euc-unified-access-gateway-23.03.0.0-21401666_OVF10.ova .

# Download other tools
mc cp s3/${object_store_bucket_name}/vsanapiutils.py .
mc cp s3/${object_store_bucket_name}/vsanmgmtObjects.py .

mount $BASE_DIR/${vcenter_iso_name} /mnt/

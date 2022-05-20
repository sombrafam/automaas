# Installing MAAS with LXD and LXD VMs


## -1. Configuring QEMU

```sh
git checkout v6.1.1
git clone https://gitlab.com/qemu-project/qemu.git
cd qemu
git submodule init
git submodule update --recursive

sudo apt-get install -y python3-pip pkg-config libglib2.0-dev libpixman-1-dev libaio-dev liblzo2-dev
sudo pip3 install ninja
./configure --target-list="x86_64-softmmu" --enable-tools --enable-lzo --enable-linux-aio
make
```

- Setting up host



## 0. Setup a base host

Setup a server with Ubuntu Focal (20.04). Then install these required packages:

```sh
sudo apt-get install -y qemu-kvm bridge-utils
sudo snap refresh --channel=4.23/stable lxd

```


Initialize LXD

```sh
STORAGE_POOL_SIZE="100GB"
cat << EOF | sudo lxd init --preseed
config: {}
networks:
- config:
    ipv4.address: 10.214.49.1/24
    ipv4.nat: "true"
    ipv6.address: fd42:de68:9ae:1f43::1/64
    ipv6.nat: "true"
  description: ""
  name: lxdbr0
  type: bridge
  project: default
storage_pools:
- config:
    size: ${STORAGE_POOL_SIZE}
    source: /var/snap/lxd/common/lxd/disks/default.img
    zfs.pool_name: default
  description: ""
  name: default
  driver: zfs
profiles:
- config: {}
  description: Default LXD profile
  devices:
    eth0:
      name: eth0
      network: lxdbr0
      type: nic
    root:
      path: /
      pool: default
      type: disk
  name: default
projects:
- config:
    features.images: "true"
    features.networks: "true"
    features.profiles: "true"
    features.storage.volumes: "true"
  description: Default LXD project
  name: default
EOF
```

Enable LXD API

```sh
lxc config set core.https_address :8443
```


## 1. Create the networks

Template:

```sh
lxc network create oam bridge.driver=native \
    bridge.external_interfaces=\
    bridge.hwaddr=\
    bridge.mtu=\
    dns.mode=none\
    ipv4.address=\
    ipv4.dhcp=\
    ipv4.dhcp.gateway=\
    ipv4.dhcp.ranges=\
    ipv4.firewall=??\
    ipv4.nat=\
    ipv4.nat.address=\
```

Admin
```sh

BRIDGE_IFACE=enp68s0f1

#  - admin:
#      type: nat
#      addr: 10.10.10.1/24
#      mtu: 1500
sudo lxc network create admin\
    bridge.hwaddr='0a:d2:63:10:10:01'\
    bridge.mtu=1500\
    ipv4.address='10.10.10.1/24'\
    ipv4.dhcp=false\
    ipv4.nat=false\
    ipv4.nat.address='10.10.10.1'

#  - oam:
#      dhcp: true
#      type: isolated
#      addr: 10.10.20.1/24
sudo lxc network create oam\
    bridge.hwaddr='0a:d2:63:20:20:01'\
    ipv4.dhcp=false\
    ipv4.nat=true\
    bridge.mtu=1500\
    ipv4.address='10.10.20.1/24'

#  - ext:
#      type: bridged
#      bridge_mapping: ens3
#      addr: 10.10.30.0/24
#      mtu: 9000
# The tap is just for testing

test -z ${BRIDGE_IFACE} && sudo ip tuntap add dev tap0 mode tap && BRIDGE_IFACE=tap0
sudo lxc network create ext\
    bridge.hwaddr='0a:d2:63:30:30:01'\
    bridge.mtu=9000\
    ipv4.dhcp=false\
    ipv4.address='10.10.30.1/24'\
    ipv4.nat=false\
    ipv4.nat.address='10.10.30.1'\
    bridge.external_interfaces=tap0
```

Cleanup

```sh
lxc network delete oam
lxc network delete admin
lxc network delete ext
```

## 2. Create a MAAS Server

### The MAAS server VM

```sh
lxc delete maas --force
lxc profile delete maas_server_vm

SERVER_NAME=maas_server_vm
SERVER_DESCRIPTION="The mighty MAAS Server"
MEM_SIZE=4GB
CPUS=2
NAMESERVERS=10.230.56.2
NAMESERVERS_SEARCH=segmaas.1ss
LP_ID=sombrafam
DATA_DIR=/home/ubuntu/vms
DATA_DISK_SIZE=40GB

# mkdir -p ${DATA_DIR}
# diskpath=${DATA_DIR}/${SERVER_NAME}.img
# stat ${diskpath} &> /dev/null || truncate -s ${DATA_DISK_SIZE} ${diskpath}
# loopdevice=$(losetup -f)
# losetup | grep ${diskpath} &> /dev/null || sudo losetup ${loopdevice} ${diskpath}
stat /home/ubuntu/.ssh/id_rsa.pub &> /dev/null || sudo -u ubuntu ssh-keygen -t rsa -P "" -f /home/ubuntu/.ssh/id_rsa &> /dev/null
ssh_key=$(cat /home/ubuntu/.ssh/id_rsa.pub)

sudo lxc profile create maas_server_vm &> /dev/null || true
cat << EOF | sudo lxc profile edit maas_server_vm
name: ${SERVER_NAME}
description: ${SERVER_DESCRIPTION}
config:
  limits.memory: ${MEM_SIZE}
  limits.cpu: ${CPUS}
  user.network-config: |-
    version: 2
    ethernets:
      oam0:
        match:
          macaddress: 0a:d2:63:20:20:02
        dhcp4: false
        addresses:
          - 10.10.20.2/24
        gateway4: 10.10.20.1
        nameservers:
          search: [${NAMESERVERS_SEARCH}]
          addresses: [${NAMESERVERS}]
      ext0:
        match:
          macaddress: 0a:d2:63:10:10:02
        dhcp4: false
        addresses:
          - 10.10.10.2/24
      admin0:
        match:
          macaddress: 0a:d2:63:30:30:02
        dhcp4: false
        addresses:
          - 10.10.30.2/24
  user.user-data: |-
    #cloud-config
    ssh_pwauth: yes

    users:
      - name: ubuntu
        lock_passwd: false
        groups: lxd
        shell: /bin/bash
        sudo: ALL=(ALL) NOPASSWD:ALL
        ssh_authorized_keys:
          - ${ssh_key}
        ssh_import_id:
          - lp:${LP_ID}

    growpart:
      mode: auto
      devices: ['/']
      ignore_growroot_disabled: false
devices:
  admin0:
    name: admin0
    network: admin
    type: nic
    hwaddr: 0a:d2:63:10:10:02
  oam0:
    name: oam0
    network: oam
    type: nic
    hwaddr: 0a:d2:63:20:20:02
  ext0:
    name: ext0
    network: ext
    type: nic
    hwaddr: 0a:d2:63:30:30:02
  root:
    path: /
    pool: default
    type: disk
EOF

LXC_IMAGE=68a5aa67379d # ubuntu/focal
sudo lxc init ubuntu:focal maas --profile maas_server_vm
sudo lxc config device override maas root size=${DATA_DISK_SIZE}
lxc start maas
lxc console maas
```

## 3. Setting up MAAS on Ubuntu

Inside the maas container, run the following steps:

0. Install packages from this list:

```sh
sudo snap install --channel=3.1/stable maas
sudo snap install maas-test-db
```

1. Initialize MAAS:

```sh
WORKERS=4
USERNAME=admin
PASSWD=admin
PASSWD=sombrafam
sudo maas init region+rack\
    --database-uri "maas-test-db:///"\
    --maas-url "http://10.10.20.2:5240/MAAS"\
    --num-workers ${WORKERS}\
    --enable-debug\
    --admin-username ${USERNAME}\
    --admin-password ${PASSWD}\
    --admin-ssh-import ${PASSWD}

echo 'debug: true' | sudo tee -a /var/snap/maas/current/rackd.conf
echo 'debug: true' | sudo tee -a /var/snap/maas/current/regiond.conf
sudo snap restart maas

sudo maas createadmin --username admin --password admin --email admin@mymaas.com --ssh-import sombrafam
sudo maas apikey --username=admin | tee ~/maas-apikey.txt

# enable MAAS debugs
maas login admin http://10.10.20.2:5240/MAAS/ `cat ~/maas-apikey.txt`
```

2. MAAS Initial configuration


```sh

UPSTREAM_DNS=10.230.56.2
maas admin maas set-config name=upstream_dns value=${UPSTREAM_DNS}

PROFILE=admin
maas $PROFILE boot-source-selections create 1 \
    os="ubuntu" release="bionic" arches="amd64" \
    subarches="*" labels="*"
maas $PROFILE boot-source-selections create 1 \
    os="ubuntu" release="focal" arches="amd64" \
    subarches="*" labels="*"

maas $PROFILE boot-resources import
maas $PROFILE boot-resources read

# maas $PROFILE rack-controllers read
# j[0]["interface_set"][2]['links'][0]['subnet']['vlan']['fabric']
#maas $PROFILE vlan update 2 0 dhcp_on=true

```
- DNS Forwarder
- Images
- DHCP


## 4. Create MAAS VMs

The VMs used by MAAS

```sh
lxc delete vm --force
lxc profile delete vms

SERVER_NAME=vm
SERVER_DESCRIPTION="Network booted VM"
MEM_SIZE=4GB
CPUS=2
DATA_DIR=/home/ubuntu/vms
DATA_DISK_SIZE=40GB

mkdir -p ${DATA_DIR}
diskpath=${DATA_DIR}/${SERVER_NAME}.img
stat ${diskpath} &> /dev/null || sudo truncate -s ${DATA_DISK_SIZE} ${diskpath}
loopdevice=$(losetup -f)
losetup | grep ${diskpath} &> /dev/null || sudo losetup ${loopdevice} ${diskpath}

sudo lxc profile create vms &> /dev/null || true
cat << EOF | sudo lxc profile edit vms
name: ${SERVER_NAME}
description: ${SERVER_DESCRIPTION}
config:
  limits.memory: ${MEM_SIZE}
  limits.cpu: ${CPUS}
  user.network-config: |-
    version: 2
    ethernets:
      oam0:
        match:
          macaddress: 0a:d2:63:20:20:55
        dhcp4: true
  user.user-data: |-
    #cloud-config
    ssh_pwauth: yes

    users:
      - name: ubuntu
        lock_passwd: false
        groups: lxd
        shell: /bin/bash
        sudo: ALL=(ALL) NOPASSWD:ALL
        ssh_authorized_keys:
          - ${ssh_key}
        ssh_import_id:
          - lp:${LP_ID}

    growpart:
      mode: auto
      devices: ['/']
      ignore_growroot_disabled: false
devices:
  oam0:
    name: oam0
    network: oam
    type: nic
    #hwaddr: 0a:d2:63:20:20:55
    boot.priority: 10
  root:
    path: /
    pool: default
    type: disk
EOF

lxc delete vm --force
LXC_IMAGE=6bc6c743ff33 # ubuntu/focal/cloud
LXC_IMAGE=ubuntu/focal/cloud/amd64
sudo lxc init --vm images:${LXC_IMAGE} vm2 --profile vms -c security.secureboot=false
sudo lxc config device override vm2 root size=${DATA_DISK_SIZE}
lxc start vm2
lxc console vm2


lxc init vm1 --empty --vm -c limits.cpu=4 -c limits.memory=8GiB -c security.secureboot=false --profile vms
sudo lxc config device override vm1 root size=${DATA_DISK_SIZE}
lxc start vm1
lxc console vm1




for i in `lxc image list images: architecture=amd64 os=Ubuntu type=disk-kvm.img| awk -F'|' '{print $3}'| grep -v FINGERPRINT | sort -u`; do
lxc launch --vm images:$i --profile vms vm-$i;
done


#lxc launch images:ubuntu/focal maas --vm --profile maas_server_vm


#lxc config device add ubuntu eth1 nic name=eth1 nictype=bridged parent=oam
#lxc config device add ubuntu eth1 nic nictype=bridge parent=ext

```


3. Setup port forward:

```sh
# ?? Not working?
sudo iptables -I PREROUTING -t nat -p tcp -d 10.230.62.178 --dport 5240 -j DNAT --to-destination 10.10.20.2:5240
sudo iptables -I PREROUTING -t nat -p tcp -d 10.230.62.178 --dport 2222 -j DNAT --to-destination 10.10.20.2:22
```

4. Configure LXD API

```
lxc config set core.https_address :8443
lxc config set core.trust_password automaas_lxd_maas

lxc config trust add - <<EOF

-----BEGIN CERTIFICATE-----
MIIE0DCCArgCEHTmYzRusHwzTOWw1UYiS+kwDQYJKoZIhvcNAQENBQAwPjENMAsG
A1UECgwETUFBUzEtMCsGA1UECwwkNmYzYWRjYTktNjQ1OC00MTM2LTg2OWItODZm
MmUzMDQ2Yzc1MB4XDTIyMDMxODE4NTI1M1oXDTMyMDMxNTE4NTI1M1owDzENMAsG
A1UEAwwEbWFhczCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAMDU3dtV
cI13CSo2p0voqHwdBaBvXSjb2TmeSPKi8wJ5GzvaHzFLnpZSlY0hKF2ocMzznmOJ
sLKAlGzWjxeW/C2C1ehfqEgy1Odje72uGPZOdwbctH/wmxY6SoJaSbP/uXJmkdkt
u/xrubyvSNb04EoextzqILl/tFFHqNCDG2HF+wUbbG5lE6BeEGLOuq++Exftfc/I
KuZgdKTqHpCZWxEMBiWTjDr9uVlsnj7SKnPoPl8Nk1zHC7mtY/Ue2TkA9TmHTHM4
hv2vWyN/NTmSsRVZiKe7wBEu7FuZ/hQPzr5jswiYLNfbiFizqJvLBvpgsDSdsi4K
CZBwz3GGEc6SsioOjzr7A+bSiYzyYR4wjiiHEhGv+xbdBKcba43ANoDi+PShf6Q/
ue2xuaIUMgDVYSJda+e1fdq7OddAeI4QVRmsM0h6N+IZAQHe0WiI623M4RJcraFS
JG5blF4+6evm38QzSLGJ3EngwGgoc0GczdHBo9sWXoJTggkgKctoqUo2Z2dqBAtn
b629KTPbPUfJZScfr/csyBk4org716sZbN4iE3p4F5TTOcKVKaqATtOIZl0oJQ42
MvCXyzkUnexMgaq/mP/mqeOnEGrKrEpIjjy8n63TD6CDw3BuiHBdudyolyI/xayu
lm/3azcpJ6VY4v1qC7Cmwc2P9z17JdnIN8BzAgMBAAEwDQYJKoZIhvcNAQENBQAD
ggIBABbln6wuLqPW0XZ/KfMH21IpUbY47+drv/F6hXSDNMa3JFbMwHW2oFMcWSwc
H++gvdgov02iliUdSVoeztUZWZFEIg2HPAuEjUdxwAZORPsbP23EQQh5jjKJoGj8
Kp4A1btbF7xr+lr2Zt+vfza1FNNcp/J+qC1l8UWnjgVk2U+6Mf2ER+oCnsyhlxgA
A5ZKiQhJT0Vk2WVmNSCPxbbxz9XTo2lH96dkorVwUWKMdXKMm5heG1X3fsIPKAoP
aNvTNDvbpqlc2Yde2AhP3dT9DeaZbuDKUNqJZdi2Geeu3k02hr1vmiucQWCmNWfv
TuyIFNOz6In6Eu1KQhyFP9g3hFUSKIzyXNY/KFK2sW7I5lBLmyT1FN25rbKfAOlt
G2ckmvWmj9S44eJ+DkO9Oc55rqG4u0whP6yWZDCclxfVR507zt0/IOAQNlMkXyEK
mVp6EQgorupdkw0WHa+Q5JhuWiJ+mMw39cHRwl/LV2J9nvjycY/dg1J+5QsUDh5s
I+lJJGEhBUhBDrjB8Yqw4PHvf+5sCIx+JNrZbA85X6bcru4NS7+sMxXxWA1r6ucw
QsnseSIRnd5OQweWpWg/W2dm+bDTuPxa38wdf3vuqlY3hGCc4gD8GeIIERm+d+is
gTe+FDViFBDyTg1pkn9NqhuWQdB8GIM6ol3WCD+iNfopi5Zn
-----END CERTIFICATE-----

EOF
```

## Appendix

```sh
maas <user> machines create -d \\
    architecture=amd64 \
    mac_addresses=<mac> \
    domain=<domain> \
    hostname=<name> \
    power_type=vmware \
    power_parameters_power_vm_name=<vm_name> \
    power_parameters_power_uuid=<vm_uuid> \
    power_parameters_power_address=<vcenter_host_name> \
    power_parameters_power_user='<maas_user_in_quotes>' \
    power_parameters_power_pass='<password_in_quotes>' \
    power_parameters_power_port=443 \
    power_parameters_power_protocol=https+unverified
    ```

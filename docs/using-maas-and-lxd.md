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
sudo apt-get install snapd
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

# enable MAAS debugs
echo 'debug: true' | sudo tee -a /var/snap/maas/current/rackd.conf
echo 'debug: true' | sudo tee -a /var/snap/maas/current/regiond.conf
sudo snap restart maas

sudo maas createadmin --username admin --password admin --email admin@mymaas.com --ssh-import sombrafam
sudo maas apikey --username=admin | tee ~/maas-apikey.txt
```

2. MAAS Initial configuration


```sh
maas login admin http://10.10.20.2:5240/MAAS/ `cat ~/maas-apikey.txt`
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
DATA_DIR=/home/erlon/vms
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

lxc delete vm2 --force
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
sudo lxc config set core.https_address :8443
sudo lxc config set core.trust_password automaas_lxd_maas

lxc config trust add - <<EOF

-----BEGIN CERTIFICATE-----
MIIE3zCCAscCEQCUPQm0MW4Rq9bkaZUR/NNvMA0GCSqGSIb3DQEBDQUAMD4xDTAL
BgNVBAoMBE1BQVMxLTArBgNVBAsMJDI4MzE3OTJiLWExMDUtNDg1MS05NDk3LWI2
MDIwODM3NWJjZjAeFw0yMjA5MDkxNTA4NTZaFw0zMjA5MDYxNTA4NTZaMB0xGzAZ
BgNVBAMMEmF1dG9tYWFzLWNvbnRhaW5lcjCCAiIwDQYJKoZIhvcNAQEBBQADggIP
ADCCAgoCggIBAKZbX9gxhK32wyTqCOQ1WSfIFYaD6Vb/5OzV7a9aQ0o86CtwEclH
04tejmCsG61w8U3vUCzkyenlQG1wMhKNLSdFJ7BnS2bg4H/6Q9XaPL8kdUIPpPWP
RF/NSYuOkqvwGMtviSHOt6XVwLoAYsW5U5t4wtEvL+Ven2IAeqirlUW9tJ6MtYJ3
pZl7pD6DMxF6sKpDiFQsWRYWmiA8HT5j+/0EsVCkIAG3AidBOIhG995Veie/2O5d
dBsBWd83EOqVWn4n2mc/8aamTEYR/V9IjJ79V3onk3GLCafqBIwR6/K6dTCY8T3g
UjUMJXpvtUKijYb8xWjIE+/QCCLg//lk9wzki2KMWvvl3I7mB7xsLba6q+i30IqJ
l+D+5MUkoQxijx4OxKu5e41XOv234cImcEtfqJI1cD4caHp00nuh1r8gG9DjozCe
tSU1FdYvHRVO530daURr046SDm6VdFax98nwl2pWm2pNYtygJCq29HEzGOhe5B5q
DG13eVVcQHlyvUQOgSfdBEx+GqAWXzlQaiGeY+Le5Eohq3CTITO/82wlVTFJ7eLy
urC1OzBUA2jmfoc2t8qQgkoXsYBduHo9x4mK5KEoKMXIEjPKUHEfzqtSRqzHPljc
gD7lpr/58m5fQY0NBTY4+jWw72aKR40LHrx5ldkAvtc58HMWVaBOl8oTAgMBAAEw
DQYJKoZIhvcNAQENBQADggIBACG8g1Gug1Xk9cyzTHHy8eRlNAHIUrb2JTjfrsYq
AWUM+09DFSUUvFzLz2lXI5KopdKfTcFxyIZFgqB11TpIJtsePJfNKhlYW+9vcHwM
FkWfMW8h1NE0vBPf9EMQ4nkxtpgnR2sypG+n4gRlo1pfP8o0CAkG5RgcpYBlJiIE
wVPaSFzm8K4mCFlqJo6El8IhYwHPkHPcEMSvmmIPTf7Jg2tNve9z1Ijks8xJmnH9
4GNQLHRfJxxr2GJwxN6+8AKKj902c8fLpqCpW5ZSUQ6BHs9tkykNkMaxJXbnSCBV
xP2OPMmNmJ3HkKc5Vf4FJtX7GDUfJ3TjrcdLop3Rqn9rco75l37Rt7qyRnQwTI5T
Ws/K3nn4kNWIK52qF2k3FdOHqLyTUnz9CARRclhUKylISZywSWmlvNJi41npT6Bv
Sr0grpiEKJmChTjZ32Xpmhk6BAPgrUxAxEdmZB/3g8BCy34C5ds2ieZ3CBwJXneC
tPDEsTZusMgtFqJkyL0aLREGG2IwWnZFLbxeA651VBKDtWGM7MAMW944Hb9PXcxm
Ma7pl4FFvM/9SEyLCGWgoi2vEUdG7CtbrRYROpww9FXZ5G3xVx9INw7V9C98PW4W
ywLDWpGL9NU/OZxM5FsLFvY/tPwzZG86tw/TJrh7LtTH0OW7AXxdNqFd1F0OqPKr
Ss+n
-----END CERTIFICATE-----
EOF
```


m1 = c.machines.list()[3]
m1.set_power("lxd", power_parameters={'project': 'default', 'password': 'automaas_lxd_maas','power_address': 'https://10.10.20.1:8443', 'instance_name': 'server-lma-6'})
m1.hostname = "server-lma-6"
m1.save()
m1.commission()



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

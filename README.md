# AutoMAAS

The scripts in this repo allow you to create a MAAS virtual environment to test
MAAS cloud projects, like OpenStack, Kubernetes and any other that support MAAS.
The input for the scripts is the IP of a host (previously configuired with key
based ssh access) and a few other optional parameters.

Automaas will log into that machine, create a set of VMs and networks and in
this way setup a virtual deployment mimicing the networks and spaces used in
customer deployments.

## How to run

1. Setup a *bionic* baremetal host and add your ssh keys to the host. The host
requirements are:

- Bionic
- '>= 64GB of RAM'
- SSH enabled and key-based, password-less access

2. In your local environment, install ansible:

```sh
sudo apt-add-repository -y ppa:ansible/ansible
sudo apt-get update
sudo apt-get install -y ansible
```

3. In your local machine copy `hosts.template` to another `hosts.yaml` file and
add the host or hosts you want to install.

```yaml
all:
  hosts:
    x1maas:
      ansible_user: ubuntu
      ansible_port: 22
      ansible_host: 192.168.122.160
```

4. Run `playbook.yaml`:

```sh
ansible-playbook -i hosts playbook.yaml
```

Once it finishes, the STDOUT messages from the playbook will print messages
with the address and login for the new servers. Port redirections for HTTP and
SSH access are done automatically.

5. Fix the DNS server

Currently, you will need to manually fix the global DNS config of the MAAS to
point to SEG's internal DNS (10.230.56.2).

6. Deploy more VMs and controllers

By default, 6 VMs are created with the networking configuration and booted via
PXE. They will appear as `new` in the MAAS listing. You need to change their
power configuration so MAAS can control them and deploy. You can identify the
VMs names by their MAC addresses in the MAAS listings. The easiest way I know
is to use virt-manager to connect to the hypervisor, and rename the domain.
Then, set the machine's power configuration:

```
Power Type: Virsh
Address: qemu+ssh://ubuntu@10.10.10.1/system
Password: tijolo22
Virsh VM ID: <domain_id>
```

Remember that if you are bootstraping a juju controller, your juju
client must reach the OAM network (run it from the host or one of the VMS).

## Adding more VMs

If you need to create more VMs, log in the KVM host and run:

```sh
/home/ubuntu/bin/spawn-vm --name <VM_NAME> --vcpus 2 --mem 8192 --disk 60  \
  --maas --series bionic
```

** The series there is kind of irrelevant since these will be re-installed by
MAAS during deployment with the image defined there.

You can use virsh or virt-manager to create more VMs. Just make sure they are
properly connected to the needed networks.

## Network configuration

In case you want to use a similar to production network scheme, these are the
networks created ando configured by default:

| Fabric  **|   Space   |**    Subnet        |
|---------**|-----------|**------------------|
|fabric-0 **|           |** 192.168.123.0/24 |
|fabric-2 **| admin     |** 10.10.20.0/24    |
|fabric-3 **| ext       |** 10.10.50.0/24    |
|fabric-4 **| internal  |** 10.10.40.0/24    |
|fabric-5 **| k8s       |** 10.10.60.0/24    |
|fabric-6 **| oam       |** 10.10.10.0/24    |
|fabric-7 **| public    |** 10.10.30.0/24    |
# AutoMAAS

The scripts in this repo allow you to create a MAAS virtual environment to test
MAAS cloud projects, like OpenStack, Kubernetes and any other that support MAAS.
The input for the scripts is the IP of a host (previously configuired with key
based ssh access) and a few other optional parameters.

Automaas will log into that machine, create a set of VMs and networks and in
this way setup a virtual deployment mimicing the networks and spaces used in
customer deployments.

## Pre-configuring the MAAS environment

1. Setup a *bionic* baremetal host and add your ssh keys to the host.
2. In your local environment, install ansible:

```sh
sudo apt-add-repository -y ppa:ansible/ansible
sudo apt-get update
sudo apt-get install -y ansible
```



## Running automaas

```sh

```


## Logging into MAAS

### SSH

### MAAS Web interface

### Booted machines

## Network configuration



### Fabric space mapping

| Fabric  |   Space   |    Subnet        |
|---------|-----------|------------------|
|fabric-0 |           | 192.168.123.0/24 |             |
|fabric-2 | admin     | 10.10.20.0/24    |
|fabric-3 | ext       | 10.10.50.0/24    |
|fabric-4 | internal  | 10.10.40.0/24    |
|fabric-5 | k8s       | 10.10.60.0/24    |
|fabric-6 | oam       | 10.10.10.0/24    |
|fabric-7 | public    | 10.10.30.0/24    |
import logging
import subprocess
import os
import paramiko
import time
import yaml

from automaas.common import DictConfs
from automaas.common import HostManager
from automaas.common import setup_step
from automaas.common import DEFAULT_VM_SERIES
from automaas.lib import db
import automaas.yaml_helpers as yhelper

log = logging.getLogger("automaas")

SERIES_IMAGE_MAP = {
    "bionic": "ubuntu/bionic/cloud",
    "focal": "ubuntu/focal/cloud"
}


class LXDManager(HostManager):
    PKG_DEPS = ""
    SNAP_DEPS = "lxd==4.23/stable"

    def __init__(self, config):
        super(LXDManager, self).__init__(config)
        self.dpkg_deps += list(filter(None, LXDManager.PKG_DEPS.split(',')))
        self.snap_deps += list(filter(None, LXDManager.SNAP_DEPS.split(',')))
        self.lxd_config_folder = os.path.join(os.path.dirname(__file__),
                                              "templates", "lxd_config")
        self.profile_config_folder = os.path.join(os.path.dirname(__file__),
                                                  "templates", "lxd_profile")

    def _build_lxd_config(self):

        lxd_config_yaml = yhelper.loader(
            os.path.join(self.lxd_config_folder, "config.yaml"))

        networks = []
        log.debug("self.config.networks: {}".format(self.config.networks))
        for net in self.config.networks:
            lxd_net_info = {}
            log.debug("net: {}".format(net))
            lxd_net_info['name'] = net.name
            # NOTE(erlon): For LXD 'bridge' means a network that is created on
            # top of a Linux or OVS bridge. For automaas, a bridge is a network
            # that has a physical device connected to that bridge.
            lxd_net_info['type'] = "bridge"
            lxd_net_info['description'] = "This is an automaas generated " \
                                          "network: {}".format(net.name)
            lxd_net_info['project'] = "default"
            lxd_net_info['config'] = {}
            bridge_ip = net.addr[1]  # First IP from the net
            lxd_net_info['config']['ipv4.address'] = "{}/{}".format(
                bridge_ip, net.addr.prefixlen)
            lxd_net_info['config']['ipv4.nat'] = \
                "true" if net.type == "nat" else "false"
            lxd_net_info['config']['ipv4.dhcp'] = "false"
            lxd_net_info['config']['bridge.mtu'] = net.mtu

            networks.append(lxd_net_info)

        lxd_config_yaml.update({'networks': networks})

        storage_pool_confs = yhelper.loader(
            os.path.join(self.lxd_config_folder, "storage_pools.yaml"))
        storage_pool_confs["storage_pools"][0]['config']['size'] = \
            "{}GB".format(self.config.host.lxd_storage_pool_size_gb)
        lxd_config_yaml.update(storage_pool_confs)

        project_confs = yhelper.loader(
            os.path.join(self.lxd_config_folder, "projects.yaml"))
        lxd_config_yaml.update(project_confs)

        return lxd_config_yaml

    @setup_step("Initializing LXD storage and networks")
    def init_virtualization_manager(self):
        initial_config = self._build_lxd_config()
        yaml.safe_dump(initial_config, open("initial_lxd.yaml", "w"))
        data = yaml.safe_dump(initial_config, None)
        self._shell_run("sudo lxd init --preseed", stdin=data.encode())

    def _build_vm_profile(self, id, name, cpus, mem, description=""):

        def _make_cmd(cmd):
            cmd = list(cmd.split())
            return cmd

        profile = dict()
        profile['name'] = name
        if not description:
            profile['description'] = profile.get(
                'description', "Server Profile")

        profile['config'] = dict()
        profile['devices'] = dict()

        profile['config']['limits.memory'] = "%sGB" % mem
        profile['config']['limits.cpu'] = cpus

        # user.network-config
        net_config = dict()

        net_config['version'] = 2
        net_config['ethernets'] = dict()
        for net in self.config.networks:
            net_dev = dict()
            device_mac = "%s:%s:%s:%s:%s:%s" % (
                "0a", "0b", "0c", "0d", net.mac_id, "%02x" % id)

            net_dev[net.name] = {
                'name': net.name,
                'network': net.name,
                'type': 'nic',
                'hwaddr': device_mac
            }

            net_config_values = dict()
            net_config_values[net.name] = dict()
            net_config_values[net.name] = {
                'match': {'macaddress': device_mac},
                'dhcp4': False,
                'addresses': ['%s/%s' % (str(net.addr[id]),
                                         net.addr.prefixlen)],
            }

            if net.type == "nat":
                net_dev[net.name]['boot.priority'] = 10
                updates = {
                    'gateway4': str(net.addr[1]),
                    'nameservers': {
                        'search': [self.config.maas.dns_search],
                        'addresses': [self.config.maas.dns_addresses]
                    }
                }
                self.config.maas.macaddr = device_mac
                net_config_values[net.name].update(updates)

            net_config['ethernets'].update(net_config_values)
            profile['devices'].update(net_dev)

        profile['devices']['root'] = {'path': '/',
                                   'pool': 'automaas',
                                   'type': 'disk'}
        profile['config']['user.network-config'] = yaml.safe_dump(net_config)

        try:
            ssh_key = open(self.config.host.ssh_pubkey_path).read().strip()
        except Exception as e:
            log.warning("Error loading SSH Key")
            log.exception("{}".format(e))
            exit(1)

        user_data = dict()
        user_data['ssh_pwauth'] = 'yes'
        user_data['users'] = [{
            'name': 'ubuntu',
            'primary_group': 'ubuntu',
            'gecos': 'Automaas',
            'lock_passwd': 'false',
            'groups': 'lxd',
            'shell': '/bin/bash',
            'sudo': 'ALL = (ALL) NOPASSWD: ALL',
            'ssh_authorized_keys': ["{}".format(ssh_key)]
        }]

        user_data['growpart'] = {
            'mode': 'auto',
            'devices': ["/"],
            'ignore_growroot_disabled': False,
        }

        user_data['packages'] = ['python3', 'openssh-server',
                                 'ssh-import-id', 'snapd']
        user_data['runcmd'] = list()
        # This is to unlock the user that is locked by default
        user_data['runcmd'].append(_make_cmd("sudo usermod -p \"\" ubuntu"))
        profile['config']['user.user-data'] = (
                "#cloud-config\n" + yaml.safe_dump(
            user_data, sort_keys=False, indent=2))
        return profile

    def _create_profile(self, profile):

        profile_name = profile.get('name')
        yaml.safe_dump(
            profile, open("{}.yaml".format(profile_name), "w"))
        data = yaml.safe_dump(profile, None)

        try:
            self._shell_run(
                "sudo lxc profile delete {}".format(profile_name))
        except subprocess.CalledProcessError as e:
            if "Profile is currently in use" in str(e.output):
                log.error("Deleting previous profile {}. The profile is "
                          "in use by some container or VM. Please delete it "
                          "manually and try again.".format(profile_name))
                exit(1)

        self._shell_run("sudo lxc profile create {}".format(profile_name))
        self._shell_run("sudo lxc profile edit {}".format(profile_name),
                        stdin=data.encode())

    def _create_instance(self, profile_name, instance_name, lxc_image_name,
                         instance_type='vm'):
        cmd = "sudo lxc init images:{} {} --profile {}".format(
            lxc_image_name, instance_name, profile_name)

        if instance_type == "vm":
            cmd = cmd + " --vm"

        self._shell_run(cmd)
        self._shell_run(
            "sudo lxc config device override {} root size=30GB".format(
                instance_name))
        self._shell_run("sudo lxc start {}".format(instance_name))

    @setup_step("Creating MAAS Container")
    def create_maas(self):

        name = "maas_server_profile"

        srv = db.AutoMaasServer(name, 'maas')
        srv.id = 2
        srv.save()

        maas_profile = self._build_vm_profile(
            srv.id, name, self.config.maas.cpus, self.config.maas.mem_gb,
            description="MAAS Server Profile")
        self._create_profile(maas_profile)
        self._create_instance(name, 'automaas-container', 'ubuntu/focal/cloud',
                              instance_type='container')

    @setup_step("Creating hosts")
    def setup_vms(self):
        for group in self.config.servers:
            for i in range(0, group.count):
                srv = db.AutoMaasServer.factory("", group.group_name)
                name = "server-{}-{}".format(group.group_name, srv.id)
                srv.name = name
                srv.save()

                try:
                    series = SERIES_IMAGE_MAP[group.series]
                except AttributeError:
                    series = SERIES_IMAGE_MAP[DEFAULT_VM_SERIES]

                profile = self._build_vm_profile(
                    srv.id, name, group.cpus, group.memory_gb,
                    description="automaas server {}-{}".format(
                        group.group_name, i))

                yaml.safe_dump(
                    profile, open("{}.yaml".format(name), "w"))
                yaml.safe_dump(profile, None)
                self._create_profile(profile)
                self._create_instance(name, name, series, instance_type='vm')

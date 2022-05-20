import logging
import subprocess
import os
import yaml

from automaas.common import HostManager
from automaas.common import setup_step
import automaas.yaml_helpers as yhelper

log = logging.getLogger("automaas")


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

    def _build_maas_profile(self):
        def _make_cmd(cmd):
            cmd = list(cmd.split())
            return cmd

        maas = dict()
        maas['name'] = "MAAS Server Profile"
        maas['description'] = "MAAS Server Profile"
        maas['config'] = dict()
        maas['devices'] = dict()

        maas['config']['limits.memory'] = "%sGB" % self.config.maas.mem_gb
        maas['config']['limits.cpu'] = self.config.maas.cpus
        # user.network-config
        net_config = dict()

        net_config['version'] = 2
        net_config['ethernets'] = dict()
        for net in self.config.networks:
            net_dev = dict()
            device_mac = "%s:%s:%s:%s:%s:%s" % (
                "0a", "0b", "0c", "0d", net.mac_id, "02")

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
                'addresses': ['%s/%s' % (str(net.addr[2]), net.addr.prefixlen)]
            }

            if net.type == "nat":
                updates = {
                    'gateway4': str(net.addr[1]),
                    'nameservers': {
                        'search': [self.config.maas.dns_search],
                        'addresses': [self.config.maas.dns_addresses]
                    }
                }
                net_config_values[net.name].update(updates)

            net_config['ethernets'].update(net_config_values)
            maas['devices'].update(net_dev)

        maas['devices']['root'] = {'path': '/',
                                   'pool': 'automaas',
                                   'type': 'disk'}
        maas['config']['user.network-config'] = yaml.safe_dump(net_config)

        try:
            ssh_key = open(self.config.host.ssh_key_path).read().strip()
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

        # FIXME: The image i've trying does not have ssh-import installed so
        #  this is failling. See: https://github.com/lxc/lxc-ci/issues/132
        # if len(self.config.host.lp_id) > 0:
        #    user_data['users'][0].update(
        #        {'ssh_import_id': ["lp: {}".format(self.config.host.lp_id)]}
        #    )
        user_data['packages'] = ['python3', 'openssh-server', 'ssh-import-id']
        user_data['runcmd'] = []
        user_data['runcmd'].append(
            _make_cmd("ssh-import-id-lp lp:{}".format(self.config.host.lp_id)))
        user_data['runcmd'].append(_make_cmd("sudo usermod -p \"\" ubuntu"))

        maas['config']['user.user-data'] = (
                "#cloud-config\n" + yaml.safe_dump(
            user_data, sort_keys=False, indent=2))
        return maas

    @setup_step("Creating MAAS Container")
    def create_maas_container(self):
        maas_profile = self._build_maas_profile()
        # TODO: This is just a debug to see how is the output file
        yaml.safe_dump(maas_profile, open("maas_profile.yaml", "w"))
        data = yaml.safe_dump(maas_profile, None)
        try:
            self._shell_run("sudo lxc profile delete maas_server_profile")
        except subprocess.CalledProcessError as e:
            if "Profile is currently in use" in str(e.output):
                log.error("Deleting previous automaas profile. The profile is "
                          "in use by some container or VM. Please delete it "
                          "manually and try again.")
                exit(1)

        self._shell_run("sudo lxc profile create maas_server_profile")
        self._shell_run("sudo lxc profile edit maas_server_profile",
                        stdin=data.encode())

    def _create_vm(self):
        pass

    def create_maas_vm(self):
        pass

    def setup_vms(self):
        pass
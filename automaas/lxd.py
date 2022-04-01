import logging
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

    def _build_lxd_config(self):
        config_folder = os.path.join(os.path.dirname(__file__),
                                     "templates", "lxd_config")
        lxd_config_yaml = yhelper.loader(os.path.join(config_folder,
                                                      "config.yaml"))

        networks = []
        log.info("self.config.networks: {}".format(self.config.networks))
        for net in self.config.networks:
            name, confs = list(net.items())[0]

            lxd_net_info = {}
            log.info("net: {}".format(net))
            lxd_net_info['name'] = name
            # NOTE(erlon): For LXD 'bridge' means a network that is created on
            # top of a Linux or OVS bridge. For automaas, a bridge is a network
            # that has a physical device connected to that bridge.
            lxd_net_info['type'] = "bridge"
            lxd_net_info['description'] = "This is an automaas generated " \
                                          "network: {}".format(name)
            lxd_net_info['project'] = "default"
            lxd_net_info['config'] = {}
            lxd_net_info['config']['ipv4.address'] = confs['addr']
            lxd_net_info['config']['ipv4.nat'] = "true" if confs.get('type') == "nat" else "false"
            lxd_net_info['config']['mtu'] = confs.get('mtu', 1500)

            networks.append(lxd_net_info)

        lxd_config_yaml.update({'networks': networks})

        storage_pool_confs = yhelper.loader(os.path.join(config_folder, "storage_pools.yaml"))
        log.info("storage_pool_confs: {}".format(storage_pool_confs))
        storage_pool_confs["storage_pools"][0]['config']['size'] = self.config.host.lxd_storage_pool_size_gb
        lxd_config_yaml.update(storage_pool_confs)

        project_confs = yhelper.loader(os.path.join(config_folder, "projects.yaml"))
        lxd_config_yaml.update(project_confs)

        return lxd_config_yaml

    @setup_step("Initializing LXD")
    def init_virtualization_manager(self):
        initial_config = self._build_lxd_config()
        yaml.safe_dump(initial_config, open("initial_lxd.conf", "w"))

    @setup_step("Initializing LXD networks")
    def init_network_manager(self):
        pass

    def _create_network(self):
        pass

    def setup_networks(self):
        pass

    def _create_vm(self):
        pass

    def create_maas_vm(self):
        pass

    def setup_vms(self):
        pass
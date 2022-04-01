# Copyright (c) 2022 Erlon Cruz.  All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import logging
import lsb_release
import os
import psutil
import subprocess
import sys
import yaml


log = logging.getLogger("automaas")


def setup_step(phase):
    def decorator(function):
        def wrapper(*args, **kwargs):
            log.info("automaas setup: {}".format(phase))
            for hdl in log.handlers:
                hdl.setFormatter(
                    logging.Formatter('  %(levelname)s: %(message)s'))
            result = function(*args, **kwargs)
            for hdl in log.handlers:
                hdl.setFormatter(
                    logging.Formatter('%(levelname)s: %(message)s'))
            return result
        return wrapper
    return decorator


class DictConfs(object):
    def __init__(self, config_dict):
        for k, v in config_dict.items():
            setattr(self, k, v)


class ConfigManager(object):
    def __init__(self, config_path):
        self.networks = []
        self.servers = []

        self.config_path = config_path if config_path else "automaas.yaml"
        if not os.path.exists(self.config_path):
            log.error("Config file not found")
            exit(1)

        try:
            config_data = open(self.config_path, "r").read()
        except Exception as e:
            log.error("Error opening file {}".format(self.config_path))
            log.exception("{}".format(e))
            exit(1)

        self._sanity_checks(config_data)

    @setup_step("Checking config for errors")
    def _sanity_checks(self, config_data):

        config_yaml = yaml.safe_load(config_data)
        for section in ['host', 'maas', 'networks', 'servers']:
            try:
                config_yaml[section]
            except KeyError:
                log.error("Missing config section {} in config file".format(
                    section))
                exit(1)

        for conf in ["networking_manager",
                     "virt_manager", "lxd_storage_pool_size_gb"]:
            try:
                config_yaml["host"][conf]
            except KeyError:
                log.error("Missing config {} from [host] in config file".format(
                    conf))
                exit(1)

        for conf in ["maas-name", "admin-user", "admin-passwd",
                     "dns-addresses", "cpus", "mem_gb"]:
            try:
                config_yaml["maas"][conf]
            except KeyError:
                log.error("Missing config {} from [maas] in config file".format(
                    conf))
                exit(1)

        # - At least 1 network should be routed
        # - At least 1 network should have DHCP
        # - Only 1 network should be DHCP
        routed = dhcped = 0
        for net in list(config_yaml['networks']):
            self.networks.append(net)
            net = list(net.values())[0]
            if net.get('type') == "nat":
                routed += 1
            if net.get('dhcp'):
                dhcped += 1

        if dhcped != 1:
            log.error("There should be at least and at most 1 DHCP network "
                      "in config file")
            exit(1)

        if routed < 1:
            log.error("There should be at least 1 routed network")
            exit(1)

        disk_required = 0
        mem_required = 0
        for server in list(config_yaml['servers']):
            self.servers.append(server)
            count = list(server.values())[0]['count']
            mem_required += list(server.values())[0]['memory_gb'] * count

            for disk, size in list(server.values())[0]['disks'].items():
                disk_required += size * count

        log.debug("Setting up env with mem: {}".format(mem_required))
        log.debug("Setting up env with disk: {}".format(disk_required))
        # - resources defined on servers should fit into resources provides by
        # the host.
        system_mem_gb = psutil.virtual_memory().total/(1000*1000*1000)
        system_disk_gb = psutil.disk_usage('/').free/(1000*1000*1000)

        log.debug("System avail mem: {}".format(system_mem_gb))
        log.debug("System avail disk: {}".format(system_disk_gb))
        if system_mem_gb < mem_required or system_disk_gb < disk_required:
            log.error("Host does not have required disk/mem resources. ")
            log.error("Required mem: {}G. Required disk {}G.".format(
                mem_required, disk_required))
            log.error("Avail mem: {}G. Avail disk {}G.".format(
                int(system_mem_gb), int(system_disk_gb)))
            log.error("Use a bigger host or decrease resources "
                      "defined in '{}'".format(self.config_path))
            exit(1)

        # TODO(erlon): Check bridge mapped interfaces should exist in the host

        self.host = DictConfs(config_yaml['host'])
        self.maas = DictConfs(config_yaml['maas'])


class HostManager(object):
    PKG_DEPS = "qemu-kvm,bridge-utils"
    SNAP_DEPS = ""

    def __init__(self, config):
        self.dpkg_deps = list(filter(None, HostManager.PKG_DEPS.split(',')))
        self.snap_deps = list(filter(None, HostManager.SNAP_DEPS.split(',')))

        self.config = config

    def _get_package_deps(self):
        return self.dpkg_deps

    def _get_snaps_deps(self):
        return self.snap_deps

    def _shell_run(self, cmd):
        log.debug("Running CMD: {}".format(cmd))
        cmd = tuple(cmd.split())
        return subprocess.check_output(cmd)

    @setup_step("Checking host requirements")
    def host_check(self):
        # check python version
        if sys.version_info.major < 3 and sys.version_info.minor < 6:
            log.error("Must use python version >= 3.6")
            exit(1)

        # host is focal
        release = lsb_release.get_os_release()['CODENAME']
        if release != 'focal':
            log.error("This host version ({}) is not supported. Please use "
                      "a focal release.".format(release))
            exit(1)

        # host has internet access?

        pass

    @setup_step("Installing packages and required snaps")
    def install_packages(self):
        try:
            output = self._shell_run("sudo apt-get install -y {}".format(
                " ".join(self.dpkg_deps)))
            log.debug(output)
        except Exception as e:
            log.error("Error installing packages: {}".format(e))
            exit(1)

        for snap in self.snap_deps:
            if '==' in snap:
                snap_name = snap.split('==')[0]
                snap_version = snap.split('==')[1]
            else:
                snap_name = snap.split('==')[0]
                snap_version = 'latest/stable'

            # FIXME(erlon): we always call install -> refresh, but we could
            #  check if the snap is installed and avoid calling twice.
            out = self._shell_run('sudo snap install --channel={} {}'.format(
                snap_version, snap_name))
            log.debug(out)
            out = self._shell_run('sudo snap refresh --channel={} {}'.format(
                snap_version, snap_name))
            log.debug(out)


class MAASManager(object):
    pass

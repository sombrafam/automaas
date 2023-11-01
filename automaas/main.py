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

import argparse
import logging

from automaas import common
from automaas import lxd

log = logging.getLogger("automaas")
formatter = logging.Formatter('%(levelname)s: %(message)s')

c_handler = logging.StreamHandler()
c_handler.setLevel(logging.INFO)
c_handler.setFormatter(formatter)
log.addHandler(c_handler)

f_handler = logging.FileHandler('automaas.log')
f_handler.setLevel(logging.DEBUG)
f_handler.setFormatter(formatter)
log.addHandler(f_handler)

# Always start in debug mode so we can debug what happens before we read
# the --debug option.
log.setLevel(logging.DEBUG)


def create_single_vm(manager, group):
    """Create a single VM

    """

    log.info("Creating {} VM".format(group))
    vm = self.maas.create_vm(vm_name, vm_config)
    vm.start()
    vm.wait_for_online()
    vm.wait_for_ssh()
    vm.wait_for_cloud_init()
    return vm

def main():

    parser = argparse.ArgumentParser(
        description='Automated MAAS Deployment for developers',
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument("--config", required=False,
                        help="The config file with all options needed")
    parser.add_argument("--skip-host-checks", required=False,
                        action="store_true",
                        help="Skip any host check. Allow automaas to run in a "
                             "host that does not have all required resources.")
    args = parser.parse_args()

    host_man = lxd.LXDManager(common.ConfigManager(args.config,
                                                   args.skip_host_checks))
    host_man.host_check(args.skip_host_checks)
    host_man.install_packages(args.skip_host_checks)
    host_man.init_virtualization_manager()
    host_man.create_maas()
    host_man.maas.wait_for_online()
    host_man.maas.initialize()
    host_man.maas.setup()
    # host_man.image_sync_check()
    host_man.create_vms()

    exit(0)


if __name__ == "__main__":
    main()

    exit(0)

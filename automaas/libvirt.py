from automaas.common import HostManager

class LibvirtManager(HostManager):
    PKG_DEPS = ""
    SNAP_DEPS = ""

    def __init__(self, config):
        super(LibvirtManager, self).__init__(config)
        self.dpkg_deps += list(filter(None, LibvirtManager.PKG_DEPS.split(',')))
        self.snap_deps += list(filter(None, LibvirtManager.SNAP_DEPS.split(',')))
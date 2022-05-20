import logging
import yaml

log = logging.getLogger("automaas")


def loader(path, replace_keys=None):

    data = open(path, "r").read()

    if replace_keys:
        for key, value in replace_keys.items():
            log.info("Replacing: {}->{}".format(key, value))
            data.replace(key, value)

    try:
        ret = yaml.load(data)
    except Exception as e:
        log.error("Error loading YAML file {}".format(path))
        log.debug("{}".format(e))
        exit(1)
    return ret

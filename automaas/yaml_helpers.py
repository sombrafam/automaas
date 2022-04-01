import logging
import yaml

log = logging.getLogger("automaas")


def loader(path):
    try:
        data = open(path, "r").read()
        ret = yaml.load(data)
    except Exception as e:
        log.error("Error loading YAML file {}".format(path))
        log.debug("{}".format(e))
        exit(1)
    return ret


def merge(y1, y2):
    y3 = ""
    return y3

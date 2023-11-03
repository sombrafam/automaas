import logging
import time

from maas.client import connect
from maas.client import enum


log = logging.getLogger("automaas")


def get_client(url, api_key):
    # TODO: Add timed out/decorator approach
    while True:
        try:
            client = connect(url, apikey=api_key, insecure=True)
            break
        except Exception as e:
            log.debug("MAAS Server not ready: {}".format(e))
            time.sleep(1)

    return client


def set_dhcp(c, if_mac_addr, start, end, dns=None):
    while True:
        try:
            rc_l = c.rack_controllers.list()
            rc = rc_l[0]
            # Sometimes, the controller object is not completly ready, so we
            # need to wait it to fully populate the interfaces' list.
            if len(rc.interfaces) > 0:
                break
        except IndexError:
            log.info("MAAS Rack controller not yet available. Waiting 5s")
            time.sleep(5)

    log.info("Rack controller found!")
    target_fabric = None
    log.debug("Searching for mac: {} in {}".format(if_mac_addr, rc.interfaces))
    for i in rc.interfaces:
        if i.mac_address == if_mac_addr:
            log.debug("Found interface")
            target_fabric = i.vlan.fabric
            target_fabric.refresh()
            break

    # Why not just use i.vlan? don't remember why this was done like that
    while True:
        try:
            vlan = target_fabric.vlans.get_default()
            break
        except AttributeError:
            log.debug("For some reason cannot get vlans from interface")
            time.sleep(5)

    range = c.ip_ranges.create(start, end, type=enum.IPRangeType.DYNAMIC)

    if dns:
        range.subnet.dns_servers = dns
        range.subnet.save()

    rack = c.rack_controllers.list()[0]
    vlan.dhcp_on = True
    vlan.primary_rack = rack
    vlan.save()


def set_maas_opts(c, dns):
    c.maas.set_upstream_dns([dns])
    c.maas.set_kernel_options("console=ttyS0")


def get_events(c, level='INFO', **filters):
    events = c.events.query(level='INFO', **filters)
    return events


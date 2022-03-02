import libxml2


def _get_xml_entry(ctx, path: str) -> str:
    res = ctx.xpathEval(path)
    if res is None or len(res) == 0:
        value = "Unknown"
    else:
        value = res[0].content
    return value


def get_domain_by_mac_address(conn, mac):
    domain_names = conn.listDefinedDomains()
    for name in domain_names:
        dom = conn.lookupByName(name)
        xml_desc = dom.XMLDesc(0)
        doc = libxml2.parseDoc(xml_desc)
        ctx = doc.xpathNewContext()
        devs = ctx.xpathEval("/domain/devices/*")
        for dev in devs:
            ctx.setContextNode(dev)
            device_type = _get_xml_entry(ctx, "@type")
            if device_type == "network":
                if mac == _get_xml_entry(ctx, "mac/@address"):
                    return dom
    return None





from ..utils.utils import normalize_links


class EndpointConfig(dict):
    def __init__(self, version, aliases=None, links=None, ipv4_address=None,
                 ipv6_address=None, link_local_ips=None):

        if aliases:
            self["Aliases"] = aliases

        if links:
            self["Links"] = normalize_links(links)

        ipam_config = {}
        if ipv4_address:
            ipam_config['IPv4Address'] = ipv4_address

        if ipv6_address:
            ipam_config['IPv6Address'] = ipv6_address

        if link_local_ips is not None:
            ipam_config['LinkLocalIPs'] = link_local_ips

        if ipam_config:
            self['IPAMConfig'] = ipam_config


class NetworkingConfig(dict):
    def __init__(self, endpoints_config=None):
        if endpoints_config:
            self["EndpointsConfig"] = endpoints_config



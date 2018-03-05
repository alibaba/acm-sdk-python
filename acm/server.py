import socket
import logging
import random

try:
    # python3.6
    from urllib.request import Request, urlopen
    from urllib.error import URLError
except ImportError:
    # python2.7
    from urllib2 import Request, urlopen, URLError

logger = logging.getLogger("acm")

ADDRESS_URL_PTN = "http://%s/diamond-server/diamond"

ADDRESS_SERVER_TIMEOUT = 3  # in seconds


def is_ipv4_address(address):
    try:
        socket.inet_aton(address)
    except socket.error:
        return False
    return True


def get_server_list(endpoint, default_port=8080, cai_enabled=True):
    server_list = list()
    if not cai_enabled:
        logger.info("[get-server-list] cai server is not used, regard endpoint:%s as server." % endpoint)
        content = endpoint.encode()
    else:
        try:
            # use 8080 as default port.
            if ":" not in endpoint:
                endpoint = endpoint + ":8080"
            content = urlopen(ADDRESS_URL_PTN % endpoint, timeout=ADDRESS_SERVER_TIMEOUT).read()
            logger.debug("[get-server-list] content from endpoint:%s" % content)
        except (URLError, OSError, socket.timeout) as e:
            logger.error("[get-server-list] get server from %s failed, cause:%s" % (endpoint, e))
            return server_list

    if content:
        for server_info in content.decode().strip().split("\n"):
            sp = server_info.strip().split(":")
            if len(sp) == 1:
                server_list.append((sp[0], default_port, is_ipv4_address(sp[0])))
            else:
                try:
                    server_list.append((sp[0], int(sp[1]), is_ipv4_address(sp[0])))
                except ValueError:
                    logger.warning("[get-server-list] bad server address:%s ignored" % server_info)

    random.shuffle(server_list)

    return server_list

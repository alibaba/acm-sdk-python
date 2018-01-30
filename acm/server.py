from urllib import request, error
from http.client import HTTPException

import logging

logger = logging.getLogger("acm")

ADDRESS_URL_PTN = "http://%s/diamond-server/diamond"

ADDRESS_SERVER_TIMEOUT = 3  # in seconds


def get_server_list(endpoint, default_port=8080, cai_enabled=True):
    server_list = list()
    if not cai_enabled:
        logger.info("[get-server-list] cai server is not used, regard endpoint:%s as server." % endpoint)
        content = endpoint
    else:
        try:
            content = request.urlopen(ADDRESS_URL_PTN % endpoint, timeout=ADDRESS_SERVER_TIMEOUT).read()
            logger.debug("[get-server-list] content from endpoint:%s" % content)
        except (error.URLError, HTTPException, OSError) as e:
            logger.error("[get-server-list] get server from %s failed, cause:%s" % (endpoint, e))
            return server_list

    if content:
        for server_info in content.decode().strip().split("\n"):
            sp = server_info.strip().split(":")
            if len(sp) == 1:
                server_list.append((sp[0], default_port))
            else:
                try:
                    server_list.append((sp[0], int(sp[1])))
                except ValueError:
                    logger.warning("[get-server-list] bad server address:%s ignored" % server_info)

    return server_list

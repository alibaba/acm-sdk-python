import base64
import hashlib
import hmac
import logging
import socket
import time
from http import HTTPStatus
from multiprocessing import Process, Manager, Queue, pool
from threading import RLock, Thread
from urllib import request, error, parse

from .commons import synchronized_with_attr
from .params import group_key, parse_key, is_valid
from .server import get_server_list

logger = logging.getLogger("acm")

DEBUG = True
VERSION = "1.0"

if DEBUG:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s:%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

DEFAULT_TIMEOUT = 3  # in seconds
DEFAULT_GROUP_NAME = "DEFAULT_GROUP"
DEFAULT_TENANT = "DEFAULT_TENANT"
PULLING_CONFIG_SIZE = 3000
CALLBACK_THREAD_NUM = 10


class ACMException(Exception):
    pass


def process_common_params(data_id, group):
    if not group or not group.strip():
        group = DEFAULT_GROUP_NAME
    else:
        group = group.strip()

    if not data_id or not is_valid(data_id):
        raise ACMException("Invalid dataId.")

    if not is_valid(group):
        raise ACMException("Invalid group.")
    return data_id, group


class ACMClient:

    def __init__(self, endpoint, namespace=None, ak=None, sk=None, default_timeout=DEFAULT_TIMEOUT,
                 tls_enabled=False, auth_enabled=True, cai_enabled=True):
        self.endpoint = endpoint
        self.namespace = namespace or DEFAULT_TENANT
        self.ak = ak
        self.sk = sk
        self.default_timeout = default_timeout
        self.tls_enabled = tls_enabled
        self.auth_enabled = auth_enabled
        self.cai_enabled = cai_enabled
        self.server_list = list()
        self.server_offset = 0
        self.watcher_mapping = dict()
        self.pulling_lock = RLock()
        self.puller_mapping = None
        self.notify_queue = None
        self.callback_tread_pool = None
        self.process_mgr = None

        logger.info(
            "[client-init] endpoint:%s, tenant:%s, default_timeout:%s, tls_enabled:%s, auth_enabled:%s, "
            "cai_enabled:%s" % (endpoint, namespace, default_timeout, tls_enabled, auth_enabled, cai_enabled))

    def current_server(self):
        if not self.server_list:
            logger.info("[current-server] server list is null, try to initialize")
            server_list = get_server_list(self.endpoint, 443 if self.tls_enabled else 8080, self.cai_enabled)
            if not server_list:
                logger.error("[client-get-server] server_list is null from %s" % self.endpoint)
                raise ACMException("Can't get servers from endpoint:%s" % self.endpoint)
            self.server_list = server_list

            logger.info("[current-server] server_num:%s server_list:%s" % (len(self.server_list), self.server_list))
        server = self.server_list[self.server_offset]
        logger.info("[current-server] use server:%s, offset:%s" % (str(server), self.server_offset))
        return server

    def get(self, data_id, group, timeout=None):
        data_id, group = process_common_params(data_id, group)
        logger.info("[get-config] data_id:%s, group:%s, namespace:%s, timeout:%s" % (
            data_id, group, self.namespace, timeout))

        params = {
            "dataId": data_id,
            "group": group,
            "tenant": self.namespace
        }

        # todo get info from failover

        try:
            resp = self._do_sync_req("/diamond-server/config.co", "GET", None, params, None,
                                     timeout or self.default_timeout)
            content = resp.read().decode("GBK")
            logger.info("[get-config] content from server:%s, data_id:%s, group:%s, namespace:%s" % (
                content, data_id, group, self.namespace))
            # todo save snapshot
            return content
        except error.HTTPError as e:
            if e.code == HTTPStatus.NOT_FOUND:
                logger.warning("[get-config] config not found for data_id:%s, group:%s, namespace:%s" % (
                    data_id, group, self.namespace))
                # todo save snapshot
                return None
            elif e.code == HTTPStatus.CONFLICT:
                logger.error(
                    "[get-config] config being modified concurrently for data_id:%s, group:%s, namespace:%s" % (
                        data_id, group, self.namespace))
                # raise ACMException("Conflict read-write detected.")
            elif e.code == HTTPStatus.FORBIDDEN:
                logger.error("[get-config] no right for data_id:%s, group:%s, namespace:%s" % (
                    data_id, group, self.namespace))
                raise ACMException("Insufficient privilege.") from None
            else:
                logger.error("[get-config] error code [:%s] for data_id:%s, group:%s, namespace:%s" % (
                    e.code, data_id, group, self.namespace))
                # raise ACMException("Exception %s." % e.msg)
        except OSError:
            logger.exception("[get-config] unknown exception data_id:%s, group:%s, namespace:%s" % (
                data_id, group, self.namespace))
            # raise ACMException("Unknown exception.")

        # todo get from snapshot
        return None

    @synchronized_with_attr("pulling_lock")
    def add_watcher(self, data_id, group, cb):
        if not cb:
            raise ACMException("A callback function is needed.")
        data_id, group = process_common_params(data_id, group)
        logger.info("[add-watcher] data_id:%s, group:%s, namespace:%s" % (data_id, group, self.namespace))
        cache_key = group_key(data_id, group, self.namespace)
        wl = self.watcher_mapping.get(cache_key)
        if not wl:
            wl = list()
            self.watcher_mapping[cache_key] = wl
        wl.append(cb)
        logger.info("[add-watcher] watcher has been added for key:%s, new callback is:%s, callback number is:%s" % (
            cache_key, cb.__name__, len(wl)))

        if self.puller_mapping is None:
            logger.debug("[add-watcher] pulling should be initialized")
            self._int_pulling()

        if cache_key in self.puller_mapping:
            logger.debug("[add-watcher] key:%s is already in pulling" % cache_key)
            return

        for key, puller_info in self.puller_mapping.items():
            if len(puller_info[1]) < PULLING_CONFIG_SIZE:
                logger.debug("[add-watcher] puller:%s is available, add key:%s" % (puller_info[0], cache_key))
                puller_info[1].append(key)
                self.puller_mapping[cache_key] = puller_info
                break
        else:
            logger.debug("[add-watcher] no puller available, new one and add key:%s" % cache_key)
            key_list = self.process_mgr.list()
            puller = Process(target=self._do_pulling, args=(key_list, self.notify_queue))
            puller.daemon = True
            puller.start()
            self.puller_mapping[cache_key] = (puller, key_list)

    @synchronized_with_attr("pulling_lock")
    def remove_watcher(self, data_id, group, cb):
        if not cb:
            raise ACMException("A callback function is needed.")
        data_id, group = process_common_params(data_id, group)
        if not self.puller_mapping:
            logger.warning("[remove-watcher] watcher is never started.")
            return
        cache_key = group_key(data_id, group, self.namespace)
        wl = self.watcher_mapping.get(cache_key)
        if not wl:
            logger.warning("[remove-watcher] there is no watcher on key:%s" % cache_key)
            return
        wl.remove(cb)
        logger.info("[remove-watcher] callback:%s is removed from key:%s" % (cb.__name__, cache_key))
        if not wl:
            logger.debug("[remove-watcher] there is no watcher for:%s, kick out from pulling" % cache_key)
            self.watcher_mapping.pop(cache_key)
            puller_info = self.puller_mapping[cache_key]
            puller_info[1].remove(cache_key)
            if not puller_info[1]:
                logger.debug("[remove-watcher] there is no pulling keys for puller:%s, stop it" % puller_info[0])
                self.puller_mapping.pop(cache_key)
                puller_info[0].stop()

    def _do_sync_req(self, url, method, headers=None, params=None, data=None, timeout=None):
        logger.debug(
            "[do-sync-req] method:%s, url:%s, headers:%s, params:%s, data:%s, timeout:%s" % (
                method, url, headers, params, data, timeout))
        url = "?".join([url, parse.urlencode(params)])
        all_headers = self._get_common_headers(params)
        if headers:
            all_headers.update(headers)
        tries = 0
        while True:
            try:
                server = self.current_server()
                server_url = "%s://%s:%s" % ("https" if self.tls_enabled else "http", server[0], server[1])
                req = request.Request(url=server_url + url, data=data, headers=all_headers, method=method)
                resp = request.urlopen(req, timeout=timeout)
                logger.debug("[do-sync-req] info from server:%s" % str(server))
                return resp
            except error.HTTPError as e:
                if e.code in {HTTPStatus.INTERNAL_SERVER_ERROR, HTTPStatus.BAD_GATEWAY,
                              HTTPStatus.SERVICE_UNAVAILABLE}:
                    logger.warning("[do-sync-req] server:%s is not available for reason:%s" % (str(server), e.msg))
                else:
                    raise
            except socket.timeout:
                logger.warning("[do-sync-req] server:%s request timeout" % (str(server)))
            except error.URLError as e:
                logger.warning("[do-sync-req] server:%s connection error:%s" % (str(server), e.msg))

            tries += 1
            if tries == len(self.server_list):
                logger.error("[do-sync-req] server:%s maybe down, no server is currently available" % str(server))
                raise ACMException("All server are not available")
            self.server_offset = (self.server_offset + 1) % len(self.server_list)
            logger.warning("[do-sync-req] server:%s maybe down, skip to next" % str(server))

    def _do_pulling(self, cache_list, queue):
        while cache_list:
            # todo get local md5
            # todo do post request
            changed_keys = list()
            for k in changed_keys:
                data_id, group, namespace = parse_key(k)
                content = self.get(data_id, group)
                queue.put((k, content))

    @synchronized_with_attr("pulling_lock")
    def _int_pulling(self):
        if self.puller_mapping is not None:
            logger.info("[init-pulling] puller is already initialized")
            return
        self.puller_mapping = dict()
        self.notify_queue = Queue()
        self.callback_tread_pool = pool.ThreadPool(CALLBACK_THREAD_NUM)
        self.process_mgr = Manager()
        t = Thread(target=self._process_change_event)
        t.setDaemon(True)
        t.start()
        logger.info("[init-pulling] init completed")

    def _process_change_event(self):
        while True:
            info = self.notify_queue.get()
            logger.debug("[process-change-event] receive an event:%s" % str(info))
            wl = self.watcher_mapping.get(info[0])
            if not wl:
                logger.warning("[process-change-event] no watcher on %s, ignored" % info[0])
                continue
            data_id, group, namespace = parse_key(info[0])
            params = {
                "data_id": data_id,
                "group": group,
                "namespace": namespace,
                "content": info[1]
            }
            for watcher in wl:
                self.callback_tread_pool.apply(watcher, (params,))

    def _get_common_headers(self, params):
        ts = str(int(time.time() * 1000))

        headers = {
            "Client-Version": VERSION,
            "Content-Type": "application/x-www-form-urlencoded; charset=GBK",
            "exConfigInfo": "true",
        }

        if self.auth_enabled:
            sign_str = "+".join([params["tenant"], params["group"], ts])
            headers.update({
                "Spas-AccessKey": self.ak,
                "timeStamp": ts,
                'Spas-Signature': base64.encodebytes(
                    hmac.new(self.sk.encode(), sign_str.encode(), digestmod=hashlib.sha1).digest()).decode().strip(),
            })

        return headers

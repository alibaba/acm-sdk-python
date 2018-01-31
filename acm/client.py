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

from .commons import synchronized_with_attr, truncate
from .params import group_key, parse_key, is_valid
from .server import get_server_list
from .files import read_file, save_file, delete_file

logger = logging.getLogger("acm")

DEBUG = True
VERSION = "1.0"

if DEBUG:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s:%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

DEFAULT_GROUP_NAME = "DEFAULT_GROUP"
WORD_SEPARATOR = bytes([2]).decode()
LINE_SEPARATOR = bytes([1]).decode()

DEFAULTS = {
    "TIMEOUT": 3,  # in seconds
    "GROUP": "DEFAULT_GROUP",
    "NAMESPACE": "DEFAULT_TENANT",
    "PULLING_CONFIG_SIZE": 3000,
    "CALLBACK_THREAD_NUM": 10,
    "FAILOVER_BASE": "acm-data/data",
    "SNAPSHOT_BASE": "acm-data/snapshot"
}


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


def parse_pulling_result(result):
    if not result:
        return list()
    return [i.split(WORD_SEPARATOR) for i in parse.unquote(result.decode(), "utf8").split(LINE_SEPARATOR) if i.strip()]


class WatcherWrap:
    def __init__(self, key, callback):
        self.callback = callback
        self.last_md5 = None
        self.watch_key = key


class CacheData:
    def __init__(self, key, client):
        self.key = key
        local_value = read_file(client.failover_base, key) or read_file(client.snapshot_base, key)
        self.md5 = hashlib.md5(local_value.encode()).hexdigest() if local_value else None
        self.is_init = True
        if not self.md5:
            logger.debug("[init-cache] cache for %s does not have local value" % key)


class ACMClient:

    def __init__(self, endpoint, namespace=None, ak=None, sk=None, default_timeout=None,
                 tls_enabled=False, auth_enabled=True, cai_enabled=True, pulling_config_size=None,
                 callback_thread_num=None, failover_base=None, snapshot_base=None):
        self.endpoint = endpoint
        self.namespace = namespace or DEFAULTS["NAMESPACE"]
        self.ak = ak
        self.sk = sk
        self.default_timeout = default_timeout or DEFAULTS["TIMEOUT"]
        self.tls_enabled = tls_enabled
        self.auth_enabled = auth_enabled and self.ak and self.sk
        self.cai_enabled = cai_enabled
        self.server_list = list()
        self.server_offset = 0
        self.watcher_mapping = dict()
        self.pulling_lock = RLock()
        self.puller_mapping = None
        self.notify_queue = None
        self.callback_tread_pool = None
        self.process_mgr = None
        self.pulling_config_size = pulling_config_size or DEFAULTS["PULLING_CONFIG_SIZE"]
        self.callback_tread_num = callback_thread_num or DEFAULTS["CALLBACK_THREAD_NUM"]
        self.failover_base = failover_base or DEFAULTS["FAILOVER_BASE"]
        self.snapshot_base = snapshot_base or DEFAULTS["SNAPSHOT_BASE"]

        logger.info(
            "[client-init] endpoint:%s, tenant:%s, tls_enabled:%s, auth_enabled:%s, "
            "cai_enabled:%s" % (endpoint, namespace, tls_enabled, auth_enabled, cai_enabled))

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

        cache_key = group_key(data_id, group, self.namespace)
        # get from failover
        content = read_file(self.failover_base, cache_key)
        if content is None:
            logger.debug("[get-config] failover config is not exist for %s, try to get from server" % cache_key)
        else:
            logger.debug("[get-config] get %s from failover directory, content is %s" % (cache_key, truncate(content)))
            return content

        # get from server
        try:
            resp = self._do_sync_req("/diamond-server/config.co", "GET", None, params, None,
                                     timeout or self.default_timeout)
            content = resp.read().decode("GBK")
            logger.info("[get-config] content from server:%s, data_id:%s, group:%s, namespace:%s" % (
                truncate(content), data_id, group, self.namespace))
            save_file(self.snapshot_base, cache_key, content)
            return content
        except error.HTTPError as e:
            if e.code == HTTPStatus.NOT_FOUND:
                logger.warning("[get-config] config not found for data_id:%s, group:%s, namespace:%s" % (
                    data_id, group, self.namespace))
                delete_file(self.snapshot_base, cache_key)
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

        logger.error("[get-config] get config from server failed, try snapshot, data_id:%s, group:%s, namespace:%s" % (
            data_id, group, self.namespace))
        return read_file(self.snapshot_base, cache_key)

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
        wl.append(WatcherWrap(cache_key, cb))
        logger.info("[add-watcher] watcher has been added for key:%s, new callback is:%s, callback number is:%s" % (
            cache_key, cb.__name__, len(wl)))

        if self.puller_mapping is None:
            logger.debug("[add-watcher] pulling should be initialized")
            self._int_pulling()

        if cache_key in self.puller_mapping:
            logger.debug("[add-watcher] key:%s is already in pulling" % cache_key)
            return

        for key, puller_info in self.puller_mapping.items():
            if len(puller_info[1]) < self.pulling_config_size:
                logger.debug("[add-watcher] puller:%s is available, add key:%s" % (puller_info[0], cache_key))
                puller_info[1].append(key)
                self.puller_mapping[cache_key] = puller_info
                break
        else:
            logger.debug("[add-watcher] no puller available, new one and add key:%s" % cache_key)
            key_list = self.process_mgr.list()
            key_list.append(cache_key)
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
        for i in wl:
            if i.callback == cb:
                wl.remove(i)
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
        url = "?".join([url, parse.urlencode(params)]) if params else url
        all_headers = self._get_common_headers(params)
        if headers:
            all_headers.update(headers)
        logger.debug(
            "[do-sync-req] method:%s, url:%s, headers:%s, params:%s, data:%s, timeout:%s" % (
                method, url, all_headers, params, data, timeout))
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
                logger.warning("[do-sync-req] server:%s connection error:%s" % (str(server), e.reason))

            tries += 1
            if tries == len(self.server_list):
                logger.error("[do-sync-req] server:%s maybe down, no server is currently available" % str(server))
                raise ACMException("All server are not available")
            self.server_offset = (self.server_offset + 1) % len(self.server_list)
            logger.warning("[do-sync-req] server:%s maybe down, skip to next" % str(server))

    def _do_pulling(self, cache_list, queue):
        cache_pool = dict()
        for cache_key in cache_list:
            cache_pool[cache_key] = CacheData(cache_key, self)

        while cache_list:
            unused_keys = set(cache_pool.keys())
            contains_init_key = False
            probe_update_string = ""
            for cache_key in cache_list:
                cache_data = cache_pool.get(cache_key)
                if not cache_data:
                    logger.debug("[do-pulling] new key added: %s" % cache_key)
                    cache_data = CacheData(cache_key, self)
                    cache_pool[cache_key] = cache_data
                if cache_data.is_init:
                    contains_init_key = True
                data_id, group, namespace = parse_key(cache_key)
                probe_update_string += WORD_SEPARATOR.join(
                    [data_id, group, cache_data.md5 or "", self.namespace]) + LINE_SEPARATOR
                unused_keys.remove(cache_key)
            for k in unused_keys:
                logger.debug("[do-pulling] %s is no longer watched, remove from cache" % k)
                cache_pool.pop(k)

            logger.debug(
                "[do-pulling] try to detected change from server probe string is %s" % truncate(probe_update_string))
            headers = {"longPullingTimeout": "30000"}
            if contains_init_key:
                headers["longPullingNoHangUp"] = "true"

            data = parse.urlencode({"Probe-Modify-Request": probe_update_string}).encode()
            # todo handle error
            resp = self._do_sync_req("/diamond-server/config.co", "POST", headers, None, data
                                     , 30000)
            for cache_key, cache_data in cache_pool.items():
                cache_data.is_init = False

            changed_keys = parse_pulling_result(resp.read())

            for data_id, group, namespace in changed_keys:
                content = self.get(data_id, group)
                cache_key = group_key(data_id, group, namespace)
                cache_pool[cache_key].md5 = hashlib.md5(content.encode()).hexdigest()
                queue.put((cache_key, content))

    @synchronized_with_attr("pulling_lock")
    def _int_pulling(self):
        if self.puller_mapping is not None:
            logger.info("[init-pulling] puller is already initialized")
            return
        self.puller_mapping = dict()
        self.notify_queue = Queue()
        self.callback_tread_pool = pool.ThreadPool(self.callback_tread_num)
        self.process_mgr = Manager()
        t = Thread(target=self._process_change_event)
        t.setDaemon(True)
        t.start()
        logger.info("[init-pulling] init completed")

    def _process_change_event(self):
        while True:
            cache_key, content = self.notify_queue.get()
            logger.debug("[process-change-event] receive an event:%s" % cache_key)
            wl = self.watcher_mapping.get(cache_key)
            if not wl:
                logger.warning("[process-change-event] no watcher on %s, ignored" % cache_key)
                continue

            data_id, group, namespace = parse_key(cache_key)
            params = {
                "data_id": data_id,
                "group": group,
                "namespace": namespace,
                "content": content
            }
            md5 = hashlib.md5(content.encode()).hexdigest()
            for watcher in wl:
                if not watcher.last_md5 == md5:
                    # todo error handle
                    logger.debug(
                        "[process-change-event] md5 has changed since last call, calling %s" % watcher.callback.__name__)
                    self.callback_tread_pool.apply(watcher.callback, (params,))
                    watcher.last_md5 = md5

    def _get_common_headers(self, params):
        # todo add client identification info
        headers = {
            "Client-Version": "3.8.6",
            "Content-Type": "application/x-www-form-urlencoded; charset=GBK",
            "exConfigInfo": "true",
        }
        if self.auth_enabled:
            ts = str(int(time.time() * 1000))
            headers.update({
                "Spas-AccessKey": self.ak,
                "timeStamp": ts,
            })
            sign_str = ""
            # in case tenant or group is null
            if not params:
                return headers

            if "tenant" in params:
                sign_str = params["tenant"] + "+"
            if "group" in params:
                sign_str = sign_str + params["group"] + "+"
            if sign_str:
                sign_str += ts
                headers["Spas-Signature"] = base64.encodebytes(
                    hmac.new(self.sk.encode(), sign_str.encode(), digestmod=hashlib.sha1).digest()).decode().strip()
        return headers

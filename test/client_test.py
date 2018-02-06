# -*- coding: utf8 -*-

from __future__ import print_function
import unittest
import acm
from acm import files
import time
import shutil


ENDPOINT = "acm.aliyun.com:8080"
NAMESPACE = "***********"
AK = "***********"
SK = "***********"


class TestClient(unittest.TestCase):

    def test_get_server(self):
        acm.ACMClient.set_debugging()
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
        self.assertIsInstance(c.get_server(), tuple)

    def test_get_server_err(self):
        c2 = acm.ACMClient("100.100.84.215:8080")
        self.assertIsNone(c2.get_server())

        c3 = acm.ACMClient("10.101.84.215:8081")
        self.assertIsNone(c3.get_server())

    def test_get_server_no_cai(self):
        c = acm.ACMClient("11.162.248.130:8080")
        c.set_options(cai_enabled=False)
        data_id = "com.alibaba"
        group = ""
        self.assertIsNone(c.get(data_id, group))

    def test_get_key(self):
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
        data_id = "com.alibaba.cloud.acm:sample-app.properties"
        group = "group"
        self.assertIsNotNone(c.get(data_id, group))

    def test_no_auth(self):
        c = acm.ACMClient("jmenv.tbsite.net:8080")
        data_id = "com.alibaba"
        group = ""
        self.assertIsNone(c.get(data_id, group))

    def test_tls(self):
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
        c.set_options(tls_enabled=True)
        data_id = "com.alibaba.cloud.acm:sample-app.properties"
        group = "group"
        self.assertIsNotNone(c.get(data_id, group))

    def test_server_failover(self):
        acm.ACMClient.set_debugging()
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
        c.server_list = [("1.100.84.215", 8080, True), ("139.196.135.144", 8080, True)]
        c.current_server = ("1.100.84.215", 8080, True)
        data_id = "com.alibaba.cloud.acm:sample-app.properties"
        group = "group"
        self.assertIsNotNone(c.get(data_id, group))

    def test_server_failover_comp(self):
        acm.ACMClient.set_debugging()
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
        c.get_server()
        c.server_list = [("1.100.84.215", 8080, True), ("100.196.135.144", 8080, True)]
        c.current_server = ("1.100.84.215", 8080, True)
        data_id = "com.alibaba.cloud.acm:sample-app.properties"
        group = "group"
        shutil.rmtree(c.snapshot_base, True)
        self.assertIsNone(c.get(data_id, group))

        time.sleep(31)
        shutil.rmtree(c.snapshot_base, True)
        self.assertIsNotNone(c.get(data_id, group))

    def test_fake_watcher(self):
        data_id = "com.alibaba"
        group = "tsing"

        class Share:
            content = None
            count = 0
        cache_key = "+".join([data_id, group, ""])

        def test_cb(args):
            print(args)
            Share.count += 1
            Share.content = args["content"]

        c = acm.ACMClient(ENDPOINT)

        c.add_watcher(data_id, group, test_cb)
        c.add_watcher(data_id, group, test_cb)
        c.add_watcher(data_id, group, test_cb)
        time.sleep(1)
        c.notify_queue.put((cache_key, "xxx", "md51"))
        time.sleep(2)
        self.assertEqual(Share.content, "xxx")
        self.assertEqual(Share.count, 3)

        c.remove_watcher(data_id, group, test_cb)
        Share.count = 0
        c.notify_queue.put((cache_key, "yyy", "md52"))
        time.sleep(2)
        self.assertEqual(Share.content, "yyy")
        self.assertEqual(Share.count, 2)

        c.remove_watcher(data_id, group, test_cb, True)
        Share.count = 0
        c.notify_queue.put((cache_key, "not effective, no watchers", "md53"))
        time.sleep(2)
        self.assertEqual(Share.content, "yyy")
        self.assertEqual(Share.count, 0)

        Share.count = 0
        c.add_watcher(data_id, group, test_cb)
        time.sleep(1)
        c.notify_queue.put((cache_key, "zzz", "md54"))
        time.sleep(2)
        self.assertEqual(Share.content, "zzz")
        self.assertEqual(Share.count, 1)

        Share.count = 0
        c.notify_queue.put((cache_key, "not effective, md5 no changes", "md54"))
        time.sleep(2)
        self.assertEqual(Share.content, "zzz")
        self.assertEqual(Share.count, 0)

    def test_long_pulling(self):
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)

        class Share:
            content = None

        def cb(x):
            Share.content = x["content"]
            print(Share.content)
        # test common
        data_id = "com.alibaba.cloud.acm:sample-app.properties"
        group = "group"
        c.add_watcher(data_id, group, cb)
        time.sleep(10)
        self.assertIsNotNone(Share.content)

    def test_get_from_failover(self):
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
        data_id = "com.alibaba.cloud.acm:sample-app.properties"
        group = "group"
        key = "+".join([data_id, group, NAMESPACE])
        files.save_file(c.failover_base, key, "xxx")
        self.assertEqual(c.get(data_id, group), "xxx")
        shutil.rmtree(c.failover_base)

    def test_get_from_snapshot(self):
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
        c.server_list = [("1.100.84.215", 8080, True)]
        data_id = "com.alibaba.cloud.acm:sample-app.properties"
        group = "group"
        key = "+".join([data_id, group, NAMESPACE])
        files.save_file(c.snapshot_base, key, "yyy")
        self.assertEqual(c.get(data_id, group), "yyy")
        shutil.rmtree(c.snapshot_base)

    def test_file(self):
        a = "中文 测试 abc"
        data_id = "com.alibaba.cloud.acm:sample-app.properties"
        group = "group"
        key = "+".join([data_id, group, NAMESPACE])
        files.delete_file(acm.DEFAULTS["SNAPSHOT_BASE"], key)
        files.save_file(acm.DEFAULTS["SNAPSHOT_BASE"], key, a)
        self.assertEqual(a, files.read_file(acm.DEFAULTS["SNAPSHOT_BASE"], key))





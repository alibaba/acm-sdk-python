from __future__ import print_function
import unittest
import acm


ENDPOINT = "acm.aliyun.com:8080"
NAMESPACE = "**********"
AK = "**********"
SK = "**********"


class TestClient(unittest.TestCase):

    def test_get_server(self):
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
        self.assertIsInstance(c.current_server(), tuple)

    def test_get_server_err(self):
        c2 = acm.ACMClient("100.100.84.215:8080")
        self.assertRaises(acm.ACMException, c2.current_server)

        c3 = acm.ACMClient("10.101.84.215:8081")
        self.assertRaises(acm.ACMException, c3.current_server)

    def test_get_server_no_cai(self):
        c = acm.ACMClient("11.162.248.130:8080", cai_enabled=False)
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
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK, tls_enabled=True)
        data_id = "com.alibaba.cloud.acm:sample-app.properties"
        group = "group"
        self.assertIsNotNone(c.get(data_id, group))

    def test_server_failover(self):
        c = acm.ACMClient(ENDPOINT)
        c.server_list = [("1.100.84.215", 8080, True), ("11.162.248.130", 8080, True)]
        data_id = "com.alibaba"
        group = "tsing"
        self.assertIsNone(c.get(data_id, group))
        self.assertIsNone(c.get(data_id, group))

    def test_fake_watcher(self):
        import time
        data_id = "com.alibaba"
        group = "tsing"

        class Share:
            content = None
            count = 0
        cache_key = "+".join([data_id, group, "DEFAULT_TENANT"])

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
        import time
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
        data_id = "com.alibaba.cloud.acm:sample-app.properties"
        group = "group1"
        c.add_watcher(data_id, group, lambda x: print(x))
        time.sleep(10)

    def test_get_from_failover(self):
        from acm import files
        import shutil
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
        data_id = "com.alibaba.cloud.acm:sample-app.properties"
        group = "group"
        key = "+".join([data_id, group, NAMESPACE])
        files.save_file(c.failover_base, key, "xxx")
        self.assertEqual(c.get(data_id, group), "xxx")
        shutil.rmtree(c.failover_base)

    def test_get_from_snapshot(self):
        from acm import files
        import shutil
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
        c.server_list = [("1.100.84.215", 8080, True)]
        data_id = "com.alibaba.cloud.acm:sample-app.properties"
        group = "group"
        key = "+".join([data_id, group, NAMESPACE])
        files.save_file(c.snapshot_base, key, "yyy")
        self.assertEqual(c.get(data_id, group), "yyy")
        shutil.rmtree(c.snapshot_base)

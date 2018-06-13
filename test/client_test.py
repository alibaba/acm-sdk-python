# -*- coding: utf8 -*-

from __future__ import print_function
import unittest
import acm
from acm import files
import time
import shutil

ENDPOINT = "acm.aliyun.com:8080"
NAMESPACE = "815********bac3"
AK = "4c79*********96b489"
SK = "Uj**********Ok1E="
KMS_AK = "LT********gyI"
KMS_SECRET = "xz*******b01"
KEY_ID = "ed********67be"
REGION_ID = "c****ai"


class TestClient(unittest.TestCase):

    def test_get_server(self):
        acm.ACMClient.set_debugging()
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
        self.assertEqual(type(c.get_server()), tuple)

    def test_get_server_err(self):
        c2 = acm.ACMClient("100.100.84.215:8080")
        self.assertEqual(c2.get_server(), None)

        c3 = acm.ACMClient("10.101.84.215:8081")
        self.assertEqual(c3.get_server(), None)

    def test_get_server_no_cai(self):
        c = acm.ACMClient("11.162.248.130:8080")
        c.set_options(cai_enabled=False)
        data_id = "com.alibaba"
        group = ""
        self.assertEqual(c.get(data_id, group), None)

    def test_get_key(self):
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
        c.set_options(no_snapshot=True)
        data_id = "com.alibaba.cloud.acm:sample-app.properties"
        group = "DEFAULT_GROUP"
        print(c.get(data_id, group))
        self.assertNotEqual(c.get(data_id, group), None)

    def test_no_auth(self):
        c = acm.ACMClient("jmenv.tbsite.net:8080")
        data_id = "com.alibaba"
        group = ""
        self.assertEqual(c.get(data_id, group), None)

    def test_tls(self):
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
        c.set_options(tls_enabled=True)
        data_id = "com.alibaba.cloud.acm:sample-app.properties-tlstest"
        group = "group"
        c.publish(data_id, group, "test")
        self.assertNotEqual(c.get(data_id, group), None)
        c.remove(data_id, group)

    def test_server_failover(self):
        acm.ACMClient.set_debugging()
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
        data_id = "com.alibaba.cloud.acm:sample-app.properties-fo"
        group = "group"
        c.publish(data_id, group, "test")
        c.server_list = [("1.100.84.215", 8080, True), ("139.196.135.144", 8080, True)]
        c.current_server = ("1.100.84.215", 8080, True)
        self.assertNotEqual(c.get(data_id, group), None)
        c.remove(data_id, group)

    def test_server_failover_comp(self):
        acm.ACMClient.set_debugging()
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
        data_id = "com.alibaba.cloud.acm:sample-app.properties-foc"
        group = "group"
        c.get_server()
        c.publish(data_id, group, "test")
        c.server_list = [("1.100.84.215", 8080, True), ("100.196.135.144", 8080, True)]
        c.current_server = ("1.100.84.215", 8080, True)
        shutil.rmtree(c.snapshot_base, True)
        self.assertEqual(c.get(data_id, group), None)

        time.sleep(31)
        shutil.rmtree(c.snapshot_base, True)
        self.assertNotEqual(c.get(data_id, group), None)
        c.remove(data_id, group)

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
        acm.ACMClient.set_debugging()
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)

        class Share:
            content = None

        def cb(x):
            Share.content = x["content"]
            print(Share.content)

        # test common
        data_id = "com.alibaba.cloud.acm:sample-app.properties"
        group = "DEFAULT_GROUP"
        c.add_watcher(data_id, group, cb)
        time.sleep(10)
        self.assertNotEqual(Share.content, None)

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

    def test_publish_remove(self):
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
        data_id = "com.alibaba.cloud.acm:sample-app.properties"
        group = "acm"
        content = u"test中文"
        c.remove(data_id, group)
        time.sleep(0.5)
        self.assertIsNone(c.get(data_id, group))
        c.publish(data_id, group, content)
        time.sleep(0.5)
        self.assertEqual(c.get(data_id, group), content)

    def test_list_all(self):
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
        c.set_debugging()
        self.assertGreater(len(c.list_all()), 1)

    def test_kms_encrypt(self):
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
        c.set_options(kms_enabled=True, kms_ak=KMS_AK, kms_secret=KMS_SECRET,
                      region_id=REGION_ID, key_id=KEY_ID)
        self.assertNotEqual(c.encrypt("中文"), "中文")

    def test_kms_decrypt(self):
        c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
        c.set_options(kms_enabled=True, kms_ak=KMS_AK, kms_secret=KMS_SECRET,
                      region_id=REGION_ID, key_id=KEY_ID)
        a = c.encrypt("test")
        self.assertEqual(c.decrypt(a), "test")

    def test_key_encrypt(self):
        c = acm.ACMClient(ENDPOINT, NAMESPACE, KMS_AK, KMS_SECRET)
        c.set_options(kms_enabled=True, region_id=REGION_ID, key_id=KEY_ID)
        value = "test"
        self.assertTrue(c.publish("cipher-test_python", None, value))
        self.assertEqual(c.get("cipher-test_python", None), value)

    def test_key_decrypt(self):
        c = acm.ACMClient(ENDPOINT, NAMESPACE, KMS_AK, KMS_SECRET)
        c.set_options(kms_enabled=True, region_id=REGION_ID)
        value = "test"
        self.assertEqual(c.get("cipher-test_python", None), value)


if __name__ == '__main__':
    unittest.main()

import unittest
import acm

TEST_ENDPOINT = "acm.aliyun.com:8080"
NAMESPACE = "60186702-3643-4214-bf88-1a244a700d38"
AK = "654b437ab82b4d0ba418a10b71ce9750"
SK = "GLffQ/+fSXMVbCwyYSyTsydxcao="


class TestClient(unittest.TestCase):

    def test_init(self):
        c = acm.ACMClient(TEST_ENDPOINT)
        self.assertIsNotNone(c)

    def test_get_server(self):
        c = acm.ACMClient(TEST_ENDPOINT, NAMESPACE, AK, SK)
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
        c = acm.ACMClient(TEST_ENDPOINT, NAMESPACE, AK, SK)
        data_id = "com.alibaba.cloud.acm:sample-app.properties"
        group = "group"
        self.assertIsNotNone(c.get(data_id, group))

    def test_server_failover(self):
        c = acm.ACMClient(TEST_ENDPOINT)
        c.server_list = [("1.100.84.215", 8080), ("11.162.248.130", 8080)]
        data_id = "com.alibaba"
        group = "tsing"
        self.assertIsNone(c.get(data_id, group))

    def test_fake_watcher(self):
        data_id = "com.alibaba"
        group = "tsing"

        def test_cb(args):
            print(args)

        c = acm.ACMClient(TEST_ENDPOINT)
        c.add_watcher(data_id, group, test_cb)
        c.add_watcher(data_id, group, test_cb)
        c.add_watcher(data_id, group, test_cb)
        import time
        time.sleep(3)
        c.notify_queue.put(("com.alibaba+tsing+DEFAULT_TANENT", "xxxx"))
        time.sleep(5)
        c.remove_watcher(data_id, group, test_cb)
        c.notify_queue.put(("com.alibaba+tsing+DEFAULT_TANENT", "yyy"))
        time.sleep(5)

    def test_long_pulling(self):
        pass
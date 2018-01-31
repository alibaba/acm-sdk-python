# acm-client

> Aliyun acm client for python.

## Install

```bash
$ pip install dist/acm_sdk_python-1.0-py3-none-any.whl
```

## Usage

```python
import acm

ENDPOINT = "acm.aliyun.com:8080"
NAMESPACE = "60186702-3643-4214-bf88-1a244a700d38"
AK = "654b437ab82b4d0ba418a10b71ce9750"
SK = "GLffQ/+fSXMVbCwyYSyTsydxcao="

# 获取配置
client = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
data_id = "com.alibaba.cloud.acm:sample-app.properties"
group = "group"
print(client.get(data_id, group))

# 监听配置变更（同步）
import time
client.add_watcher(data_id, group, lambda x:print("config change detected: " + x))
time.sleep(5) # 等待配置变更

# 监听配置变更（异步)
```

### API

* `get(data_id, group, timeout)`
* `add_watcher(data_id, group, cb)`
* `remove_watcher(data_id, group, cb)`
 - {str} data_id    配置项ID
 - {str} group      配置分组
 - {func} cb        回调函数
 - {float} timeout  超时时间（秒）
 
## Contacts

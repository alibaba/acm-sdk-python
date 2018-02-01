# User Guide

## Introduction

Python SDK for ACM. 

### Features
1. Get config from ACM server use REST API
2. Watch config changes from server
3. Auto failover when server down
4. TLS supported
5. Address server supported
6. Both Aliyun and Stand-alone deployment supported

### Supported Python：

1. Python 2.7
2. Python 3.3
3. Python 3.4
4. Python 3.5
5. Python 3.6

### Supported ACM version
1. ACM 1.0

### Change Logs

## Installation
For development only:
```shell
git clone ${REPO_URL}
pip install acm-sdk-python/dist/acm_sdk_python-0.1.0-py2.py3-none-any.whl
```

## Getting Started
```python
import acm

ENDPOINT = "acm.aliyun.com:8080"
NAMESPACE = "60186702-3643-4214-bf88-1a244a700d38"
AK = "654b437ab82b4d0ba418a10b71ce9750"
SK = "GLffQ/+fSXMVbCwyYSyTsydxcao="

# get config
client = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
data_id = "com.alibaba.cloud.acm:sample-app.properties"
group = "group"
print(client.get(data_id, group))

# add watch
import time
client.add_watcher(data_id, group, lambda x:print("config change detected: " + x))
time.sleep(5) # wait for an config change

```

## Configuration
Client can be configured by constructor：
```
client = ACMClient(endpoint, namespace, ak, sk, default_timeout, tls_enabled, auth_enabled, cai_enabled, pulling_timeout,
            pulling_config_size, callback_thread_num, failover_base, snapshot_base, app_name)
```

### Options
>* **endpoint** - *required*  - ACM server address
>* **namespace** - namespace | default: `DEFAULT_TENANT`
>* **ak** - *AccessKey* for Aliyun | default: `None`
>* **sk** - *SecretKey* for Aliyun | default: `None`
>* **default_timeout** - default timeout for get config from server in seconds | default: `3`
>* **tls_enabled** - whether to use https | default: `False`
>* **auth_enabled** - whether to use auth features | default: `True`
>* **cai_enabled** - whether to user address server | default: `True`
>* **pulling_timeout** - long polling timeout in seconds | default: `30`
>* **pulling_config_size** - max config items number listened by one polling process | default: `3000`
>* **callback_thread_num** - concurrency for invoking callback | default: `10`
>* **failover_base** - dir to store failover config files | default: `${cwd}/acm-data/data`
>* **snapshot_base** - dir to store snapshot config files | default: `${cwd}/acm-data/snapshot`
>* **app_name** - client app identifier | default `ACM-SDK-Python`

## API Reference
 
### get config
Get value of one config item following priority:

* Step 1 - Get from local failover dir(default: `${cwd}/acm/data`)
  * failover dir can be manually copied from snapshot dir(default: `${cwd}/acm/snapshot`) in advance
  * this helps to suppress the effect of known server failure
    
* Step 2 - Get from one server until value is got or all servers tried
  * content will be save to snapshot dir after got from server

* Step 3 - Get from snapshot dir

>`ACMClient.get(data_id, group, timeout)`
>* `param` **data_id** dataId
>* `param` **group** group, use `DEFAULT_GROUP` if no group specified
>* `param` **timeout** timeout for requesting server in seconds
>* `return` value

***
### add watcher
Add a watcher to a specified config item.
* Once changes or deletion of the item happened, callback function will be invoked
* If the item is already exists, callback function will invoked at once
* Multiple callbacks on one item is allowed and all callback functions are invoked concurrently by `threading.Thread`
* Callback function is invoked from current process

>`ACMClient.add_watcher(data_id, group, cb)`
>* `param` **data_id** data_id
>* `param` **group** group, use `DEFAULT_GROUP` if no group specified
>* `param` **cb** callback function
>* `return`

***
### remove watcher
Remove watcher from specified key.

>`ACMClient.remove_watcher(data_id, group, cb, remove_all)`
>* `param` **data_id** data_id
>* `param` **group** group, use "DEFAULT_GROUP" if no group specified
>* `param` **cb** callback function
>* `param` **remove_all** whether to remove all occurrence of the callback or just once
>* `return`

***
## Other Resources




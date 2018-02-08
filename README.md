# User Guide

[![Pypi Version](https://badge.fury.io/py/acm-sdk-python.svg)](https://badge.fury.io/py/acm-sdk-python)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/alibaba/acm-sdk-python/blob/master/LICENSE)

## Introduction

Python SDK for ACM. 

### Features
1. Get config from ACM server use REST API.
2. Watch config changes from server.
3. Auto failover on server failure.
4. TLS supported.
5. Address server supported.
6. Both Alibaba Cloud ACM and Stand-alone deployment supported.

### Supported Python：

1. Python 2.6
2. Python 2.7
3. Python 3.3
4. Python 3.4
5. Python 3.5
6. Python 3.6

### Supported ACM version
1. ACM 1.0

### Change Logs

## Installation

For Python 2.7 and above:
```shell
pip install acm-sdk-python
```

For Python 2.6:
```shell
# install setuptools first:
wget https://pypi.io/packages/source/s/setuptools/setuptools-33.1.1.zip
unzip setuptools-33.1.1.zip
cd setuptools-33.1.1 && sudo python setup.py install

# if setuptools already exists:
sudo easy_install acm-sdk-python
```

## Getting Started
```python
import acm

ENDPOINT = "acm.aliyun.com:8080"
NAMESPACE = "**********"
AK = "**********"
SK = "**********"

# get config
client = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
data_id = "com.alibaba.cloud.acm:sample-app.properties"
group = "group"
print(client.get(data_id, group))

# add watch
import time
client.add_watcher(data_id, group, lambda x:print("config change detected: " + x))
time.sleep(5) # wait for config changes

```

## Configuration
```
client = ACMClient(endpoint, namespace, ak, sk)
```

* *endpoint* - **required**  - ACM server address.
* *namespace* - Namespace. | default: `DEFAULT_TENANT`
* *ak* - AccessKey For Alibaba Cloud ACM. | default: `None`
* *sk* - SecretKey For Alibaba Cloud ACM. | default: `None`

#### Extra Options
Extra option can be set by `set_options`, as following:

```
client.set_options({key}={value})
```

Configurable options are:

* *default_timeout* - Default timeout for get config from server in seconds.
* *tls_enabled* - Whether to use https.
* *auth_enabled* - Whether to use auth features.
* *cai_enabled* - Whether to use address server.
* *pulling_timeout* - Long polling timeout in seconds.
* *pulling_config_size* - Max config items number listened by one polling process.
* *callback_thread_num* - Concurrency for invoking callback.
* *failover_base* - Dir to store failover config files.
* *snapshot_base* - Dir to store snapshot config files.
* *app_name* - Client app identifier.

## API Reference
 
### Get Config
>`ACMClient.get(data_id, group, timeout)`

* `param` *data_id* Data id.
* `param` *group* Group, use `DEFAULT_GROUP` if no group specified.
* `param` *timeout* Timeout for requesting server in seconds.
* `return` 

Get value of one config item following priority:

* Step 1 - Get from local failover dir(default: `${cwd}/acm/data`).
  * Failover dir can be manually copied from snapshot dir(default: `${cwd}/acm/snapshot`) in advance.
  * This helps to suppress the effect of known server failure.
    
* Step 2 - Get from one server until value is got or all servers tried.
  * Content will be save to snapshot dir after got from server.

* Step 3 - Get from snapshot dir.

### Add Watchers
>`ACMClient.add_watchers(data_id, group, cb_list)`

* `param` *data_id* Data id.
* `param` *group* Group, use `DEFAULT_GROUP` if no group specified.
* `param` *cb_list* List of callback functions to add.
* `return`

Add watchers to a specified config item.
* Once changes or deletion of the item happened, callback functions will be invoked.
* If the item is already exists in server, callback functions will be invoked for once.
* Multiple callbacks on one item is allowed and all callback functions are invoked concurrently by `threading.Thread`.
* Callback functions are invoked from current process.

### Remove Watcher
>`ACMClient.remove_watcher(data_id, group, cb, remove_all)`

* `param` *data_id* Data id.
* `param` *group* Group, use "DEFAULT_GROUP" if no group specified.
* `param` *cb* Callback function to delete.
* `param` *remove_all* Whether to remove all occurrence of the callback or just once.
* `return`

Remove watcher from specified key.

## Debugging Mode
Debugging mode if useful for getting more detailed log on console.

Debugging mode can be set by:
```
ACMClient.set_debugging()
# only effective within the current process
```

## Other Resources

* Alibaba Cloud ACM homepage: https://www.aliyun.com/product/acm



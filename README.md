# User Guide

[![Pypi Version](https://badge.fury.io/py/acm-sdk-python.svg)](https://badge.fury.io/py/acm-sdk-python)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/alibaba/acm-sdk-python/blob/master/LICENSE)

## Introduction

Python SDK for ACM. 

### Features
1. Get/Publish/Remove config from ACM server use REST API.
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
* *no_snapshot* - To disable default snapshot behavior, this can be overridden by param *no_snapshot* in *get* method.

## API Reference
 
### Get Config
>`ACMClient.get(data_id, group, timeout, no_snapshot)`

* `param` *data_id* Data id.
* `param` *group* Group, use `DEFAULT_GROUP` if no group specified.
* `param` *timeout* Timeout for requesting server in seconds.
* `param` *no_snapshot* Whether to use local snapshot while server is unavailable.
* `return` 
W
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

### List All Config
>`ACMClient.list_all(group, prefix)`
        
* `param` *group* Only dataIds with group match shall be returned, default is None.
* `param` *group* only dataIds startswith prefix shall be returned, default is None **Case sensitive**.
* `return` List of data items.

Get all config items of current namespace, with dataId and group information only.
* Warning: If there are lots of config in namespace, this function may cost some time.

### Publish Config
>`ACMClient.publish(data_id, group, content, timeout)`

* `param` *data_id* Data id.
* `param` *group* Group, use "DEFAULT_GROUP" if no group specified.
* `param` *content* Config value.
* `param` *timeout* Timeout for requesting server in seconds.
* `return` True if success or an exception will be raised.

Publish one data item to ACM.
* If the data key is not exist, create one first.
* If the data key is exist, update to the content specified.
* Content can not be set to None, if there is need to delete config item, use function **remove** instead.

### Remove Config
>`ACMClient.remove_watcher(data_id, group, cb, remove_all)`

* `param` *data_id* Data id.
* `param` *group* Group, use "DEFAULT_GROUP" if no group specified.
* `param` *timeout* Timeout for requesting server in seconds.
* `return` True if success or an exception will be raised.

Remove one data item from ACM.

## Debugging Mode
Debugging mode if useful for getting more detailed log on console.

Debugging mode can be set by:
```
ACMClient.set_debugging()
# only effective within the current process
```

## CLI Tool

A CLI Tool is along with python SDK to make convenient access and management of config items in ACM server.

You can use `acm {subcommand}` directly after installation, sub commands available are as following:

```shell
    add                 add a namespace
    use                 switch to a namespace
    current             show current endpoint and namespace
    show                show all endpoints and namespaces
    list                get list of dataIds
    pull                get one config content
    push                push one config
    export              export dataIds to local files
    import              import files to ACM server
```

Use `acm -h` to see the detailed manual.

## Data Security Options

ACM allows you to encrypt data along with [Key Management Service](https://www.aliyun.com/product/kms), service provided by Alibaba Cloud (also known as **KMS**).

To use this feature, you can follow these steps:
1. Install KMS SDK by `pip install aliyun-python-sdk-kms`.
2. Name your data_id with a `cipher-` prefix.
3. Get and filling all the needed configuration to `ACMClient`, info needed are: `region_id`, `kms_ak`, `kms_secret`, `key_id`.
4. Just make API calls and SDK will process data encrypt & decrypt automatically.

Example:
```
c = acm.ACMClient(ENDPOINT, NAMESPACE, AK, SK)
c.set_options(kms_enabled=True, kms_ak=KMS_AK, kms_secret=KMS_SECRET, region_id=REGION_ID, key_id=KEY_ID)

# publish an encrypted config item.
c.publish("cipher-dataId", None, "plainText")

# get the content of an encrypted config item.
c.get("cipher-dataId", None)
```

## Use RAM
It is a best practice to use RAM instead of hard coded **AccessKey** and **SecretKey** at client side, because it's much more safe and simple.

Example:
```python
ENDPOINT = "acm.aliyun.com"
NAMESPACE = "9ca*****c1e"
RAM_ROLE_NAME = "ECS-STS-KMS-ACM"
REGION_ID = "cn-shanghai"
KEY_ID="192d****dc"

# use RAM role name for configuration.
a=acm.ACMClient(ENDPOINT, NAMESPACE, ram_role_name=RAM_ROLE_NAME)
a.set_options(kms_enabled=True, region_id=REGION_ID, key_id=KEY_ID)

# call API like the same as before.
a.list_all()
a.get('cipher-dataId','DEFAULT_GROUP')
```


For more information, refer to this [document](https://help.aliyun.com/document_detail/54579.html?spm=5176.11065259.1996646101.searchclickresult.1f4c11fakqh55j).
## Other Resources

* Alibaba Cloud ACM homepage: https://www.aliyun.com/product/acm



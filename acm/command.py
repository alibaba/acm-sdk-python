import os.path
import sys
import json
import fcntl
import shutil
import gettext
from datetime import datetime
import zipfile
from acm import ACMClient, DEFAULT_GROUP_NAME


# override the default expression of "positional arguments"
def translate_patch(msg):
    return "required arguments" if msg == "positional arguments" else msg


gettext.gettext = translate_patch

import argparse

###

DEFAULT_ENDPOINT = "acm.aliyun.com"
DEFAULT_PORT = 8080
CMD = set(["bind", "set", "use"])
CONF = os.path.join(os.getenv("HOME"), ".acm.json")

INIT_CONF = {
    "endpoints": {
        DEFAULT_ENDPOINT: {
            "tls": False,
            "is_current": True,
            "region_id": None,
            "kms_enabled": False,
            "namespaces": {
                "[default]": {
                    "is_current": True,
                    "ak": None,
                    "sk": None,
                    "alias": "[default]",
                    "kms_ak": None,
                    "kms_secret": None,
                    "key_id": None,
                    "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            }
        }
    }
}


def _colored(txt, color="green"):
    cm = {
        "green": 32,
        "red": 31,
        "yellow": 33,
        "grey": 30,
    }

    return "\033[1;%sm%s\033[0m" % (cm[color], txt)


def read_config():
    try:
        if not os.path.exists(CONF):
            write_config(INIT_CONF)
        if sys.version_info[0] == 3:
            with open(CONF, "r+", newline="") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                return json.loads(f.read())
        else:
            with open(CONF, "r+") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                return json.loads(f.read())
    except Exception as e:
        print("Read config error due to %s" % str(e))
        sys.exit(1)


def write_config(config):
    try:
        content = json.dumps(config, indent=4)
        with open(CONF, "wb") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(content if type(content) == bytes else content.encode("utf8"))
    except Exception as e:
        print("Save config error due to %s" % str(e))
        sys.exit(1)


def _get_current(config):
    endpoint = ""
    namespace = ""
    for k, v in config["endpoints"].items():
        if not v["is_current"]:
            continue
        endpoint = k
        for k2, v2 in v["namespaces"].items():
            if not v2["is_current"]:
                continue
            namespace = k2
            break

    return endpoint, namespace


def _set_current(config, endpoint, namespace=None):
    for k, v in config["endpoints"].items():
        if k == endpoint:
            v["is_current"] = True
            if namespace is not None:
                for k2, v2 in v["namespaces"].items():
                    if k2 == namespace:
                        v2["is_current"] = True
                    else:
                        v2["is_current"] = False
        else:
            v["is_current"] = False

    return config


def add(args):
    if ":" in args.namespace:
        pos = args.namespace.index(":")
        e = args.namespace[:pos]
        ns = args.namespace[pos + 1:]
    else:
        e = DEFAULT_ENDPOINT
        ns = args.namespace
    config = read_config()
    alias = args.alias or ns

    if args.alias is not None and ":" in args.alias:
        print('":" is invalid symbol in alias.')
        sys.exit(1)

    # detect alias, ensure unique globally
    for ep, ep_info in config["endpoints"].items():
        for k, v in ep_info["namespaces"].items():
            if args.alias is None and v["alias"] == alias and (k != ns or ep != e):
                alias = "-".join([e, ns])
            elif v["alias"] == alias and k != ns:
                print("Alias %s has been taken by %s:%s, choose another one." % (_colored(alias, "red"), ep, k))
                sys.exit(1)

    # new endpoint
    if e not in config["endpoints"]:
        if args.kms:
            if not args.region_id:
                print(_colored("Region ID", "red") + " must be specified to use KMS.")
                sys.exit(1)
        config["endpoints"][e] = {
            "tls": args.tls,
            "is_current": False,
            "region_id": args.region_id,
            "kms_enabled": args.kms,
            "namespaces": {}
        }
        print(
                "Adding a new endpoint: %s, using TLS is %s.\n" % (_colored(e, "yellow"), _colored(args.tls, "yellow")))
    else:
        endpoint = config["endpoints"][e]
        if args.kms and not args.region_id and not endpoint.get("region_id"):
            print(_colored("Region ID", "red") + " must be specified to use KMS.")
            sys.exit(1)
        if endpoint.get("tls") != args.tls:
            endpoint["tls"] = args.tls
            print("TLS attr of %s has changed to %s.\n" % (_colored(e, "yellow"), _colored(args.tls, "yellow")))
        if endpoint.get("kms_enabled") != args.kms:
            endpoint["kms_enabled"] = args.kms
            print("KMS enabled of %s has turned to %s.\n" % (_colored(e, "yellow"), _colored(args.kms, "yellow")))
        if args.region_id is not None:
            if endpoint.get("region_id") != args.region_id:
                endpoint["region_id"] = args.region_id
                print("Region ID of %s has changed to %s.\n" % (
                _colored(e, "yellow"), _colored(args.region_id, "yellow")))

    if ns in config["endpoints"][e]["namespaces"]:
        namespace = config["endpoints"][e]["namespaces"][ns]
        if args.ak is not None:
            namespace["ak"] = args.ak
        if args.sk is not None:
            namespace["sk"] = args.sk
        if args.alias is not None:
            namespace["alias"] = alias
        if args.kms_ak is not None:
            namespace["kms_ak"] = args.kms_ak
        if args.kms_secret is not None:
            namespace["kms_secret"] = args.kms_secret
        if args.key_id is not None:
            namespace["key_id"] = args.key_id
        if args.kms:
            if not namespace.get("kms_ak"):
                if not namespace.get("ak"):
                    print(_colored("AccessKey", "red") + ' must be specified to use KMS.')
                    sys.exit(1)
                namespace["kms_ak"] = namespace.get("ak")
            if not namespace.get("kms_secret"):
                if not namespace.get("sk"):
                    print(_colored("SecretKey", "red") + ' must be specified to use KMS.')
                    sys.exit(1)
                namespace["kms_secret"] = namespace.get("sk")
        namespace["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("Namespace %s is already exist in %s, updating configs.\n" % (
            _colored(ns, "green"), _colored(e, "yellow")))
    else:
        namespace = {"ak": args.ak, "sk": args.sk, "alias": alias, "is_current": False,
                     "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                     "kms_ak": None, "kms_secret": None, "key_id": None}
        if args.kms:
            kms_ak = args.kms_ak or args.ak
            if not kms_ak:
                print(_colored("AccessKey", "red") + ' must be specified to use KMS.')
                sys.exit(1)
            kms_secret = args.kms_secret or args.sk
            if not kms_secret:
                print(_colored("SecretKey", "red") + ' must be specified to use KMS.')
                sys.exit(1)
            namespace["kms_ak"] = kms_ak
            namespace["kms_secret"] = kms_secret
            namespace["key_id"] = args.key_id
        config["endpoints"][e]["namespaces"][ns] = namespace
        print(
                "Add new namespace %s(%s) to %s.\n" %
                (_colored(ns, "green"), _colored(alias, "green"), _colored(e, "yellow")))

    write_config(config)

    try:
        print("Try to access the namespace...")
        c = ACMClient(endpoint=e, namespace=(None if ns == "[default]" else ns),
                      ak=config["endpoints"][e]["namespaces"][ns]["ak"],
                      sk=config["endpoints"][e]["namespaces"][ns]["sk"])
        if config["endpoints"][e]["tls"]:
            c.set_options(tls_enabled=True)
        c.list(1, 1)
        print("Namespace access succeed.")
    except:
        print(_colored("\nWarning: Access test failed, there may be mistakes in configuration.\n", "grey"))


def use(args):
    config = read_config()

    if ":" in args.namespace:
        pos = args.namespace.index(":")
        e = args.namespace[:pos]
        ns = args.namespace[pos + 1:]
    else:
        e = None
        ns = None

    found = False
    # detect alias, ensure unique globally
    for ep, ep_info in config["endpoints"].items():
        for k, v in ep_info["namespaces"].items():
            if v["alias"] == args.namespace or (k == ns and ep == e):
                _set_current(config, ep, k)
                print("Namespace changed to %s alias:%s.\n" % (
                    _colored("%s:%s" % (ep, k), "green"), _colored(v["alias"], "green")))
                write_config(config)
                found = True
                break
        if found:
            break
    else:
        print("No namespace named or aliased as %s, please check.\n" % _colored(args.namespace, "red"))


def _process_namespace(args):
    config = read_config()

    if args.namespace is not None:
        if ":" in args.namespace:
            pos = args.namespace.index(":")
            e = args.namespace[:pos]
            ns = args.namespace[pos + 1:]
        else:
            e = None
            ns = None
        for ep, ep_info in config["endpoints"].items():
            for k, v in ep_info["namespaces"].items():
                if v["alias"] == args.namespace or (k == ns and ep == e):
                    return ep, ep_info, k, v
        print("No namespace named or aliased as %s, please check.\n" % _colored(args.namespace, "red"))
        sys.exit(1)

    e, n = _get_current(config)
    return e, config["endpoints"][e], n, config["endpoints"][e]["namespaces"][n]


def list_conf(args):
    e, ep, n, ns = _process_namespace(args)
    c = ACMClient(endpoint=e, namespace=(None if n == "[default]" else n), ak=ns["ak"], sk=ns["sk"])
    if ep["tls"]:
        c.set_options(tls_enabled=True)

    try:
        configs = c.list_all(args.group, args.prefix)
    except:
        print("List failed.")
        sys.exit(1)

    for i in sorted(configs, key=lambda x: x["group"] + x["dataId"]):
        print("%(group)s/%(dataId)s" % i)


def _write_file(file, content):
    try:
        with open(file, "wb") as f:
            f.write(content if type(content) == bytes else content.encode("utf8"))
    except Exception as e:
        print("Write file error due to %s" % str(e))
        sys.exit(1)


def _read_file(file):
    try:
        if sys.version_info[0] == 3:
            with open(file, "r+", newline="") as f:
                return f.read()
        else:
            with open(file, "r+") as f:
                return f.read()
    except Exception as e:
        print("Read file error due to %s" % str(e))
        sys.exit(1)


def pull(args):
    e, ep, n, ns = _process_namespace(args)
    c = _get_client(e, ep, n, ns)
    try:
        if "/" in args.data_id:
            g, d = args.data_id.split("/")
            content = c.get(d, g, no_snapshot=True)
        else:
            content = c.get(args.data_id, None, no_snapshot=True)
    except:
        print("Pull %s failed." % args.data_id)
        sys.exit(1)

    if content is None:
        print("%s does not exist." % _colored(args.data_id, "red"))
        sys.exit(1)
    os.write(1, content.encode("utf8"))


def push(args):
    if args.file:
        if not sys.stdin.isatty():
            print(_colored("Warning: content from stdin will be ignored since file is specified.", "grey"))
        if not os.path.exists(args.file):
            print("File %s does not exist." % _colored(args.file, "red"))
            sys.exit(1)
        content = _read_file(args.file)
    elif not sys.stdin.isatty():
        content = sys.stdin.read()
    else:
        print("Use file or stdin as input.")
        sys.exit(1)

    e, ep, n, ns = _process_namespace(args)
    c = _get_client(e, ep, n, ns)

    if args.data_id.count("/") > 1:
        print("Invalid dataId or filename, more than one / is given.")
        sys.exit(1)

    group, data_id = args.data_id.split("/") if "/" in args.data_id else (None, args.data_id)

    try:
        c.publish(data_id, group, content)
    except:
        import traceback
        traceback.print_exc()
        print("Push %s failed." % args.data_id)
        sys.exit(1)

    print("content has been pushed to [dataId:%s].\n" % (_colored(args.data_id, "green")))


def current(args):
    config = read_config()
    e, n = _get_current(config)
    print("Current Endpoint:\t%s, using TLS is %s, using KMS is %s, Region ID is %s." % (
        _colored(e, "yellow"), _colored(config["endpoints"][e].get("tls"), "yellow"),
        _colored(config["endpoints"][e].get("kms_enabled"), "yellow"),
        _colored(config["endpoints"][e].get("region_id"), "yellow")))
    print("\nCurrent Namespace:\t%s" % (_colored(n)))
    ns = config["endpoints"][e]["namespaces"][n]

    print("\tAlias:\t\t%s" % _colored(ns["alias"], "green"))
    print("\tAccessKey:\t%s" % ns["ak"])
    print("\tSecretKey:\t%s" % ns["sk"])
    if config["endpoints"][e].get("kms_enabled"):
        print("\tAccessKey for KMS:\t%s" % ns.get("kms_ak"))
        print("\tSecretKey for KMS:\t%s" % ns.get("kms_secret"))
        print("\tKey ID:\t%s" % ns.get("key_id"))
    print("")


def show(args):
    config = read_config()
    e, n = _get_current(config)
    max_ep = 10
    max_ns = 10
    max_alias = 10

    table_header = ["", "ENDPOINT", "NAMESPACE_ID", "ALIAS", "UPDATED"]
    table_data = list()

    for k, v in config["endpoints"].items():
        if len(k) > max_ep:
            max_ep = len(k)
        start = True
        for k2, v2 in v["namespaces"].items():
            if k == e and k2 == n:
                row_data = ["*"]
            else:
                row_data = [""]
            if start:
                row_data.append(k)
                start = False
            else:
                row_data.append(k)
            if len(k2) > max_ns:
                max_ns = len(k2)
            if len(v2["alias"]) > max_alias:
                max_alias = len(v2["alias"])
            row_data.append(k2)
            row_data.append(v2["alias"])
            row_data.append(v2.get("updated", "None"))
            table_data.append(row_data)
    table_data = sorted(table_data, key=lambda x: x[4], reverse=True)
    ptn = "%%-3s%%-%is%%-%is%%-%is%%-20s" % (max_ep + 5, max_ns + 5, max_alias + 5)
    print(ptn % tuple(table_header))
    print("-" * (max_ep + max_ns + max_alias + 38))
    for row in table_data:
        print(ptn % tuple(row))
    print("-" * (max_ep + max_ns + max_alias + 38))
    print("")


def export(args):
    e, ep, n, ns = _process_namespace(args)
    c = _get_client(e, ep, n, ns)
    try:
        configs = c.list_all()
    except:
        print("Get config list failed.")
        sys.exit(1)

    groups = set()
    elements = set()
    for i in configs:
        groups.add(i["group"])
        elements.add(os.path.join(i["group"], i["dataId"]) if i["group"] != DEFAULT_GROUP_NAME else i["dataId"])
    dest_file = args.file or "%s-%s.zip" % (e, n)
    zip_file = None

    if args.dir:
        try:
            os.makedirs(args.dir)
        except OSError:
            pass
        # process deleting
        if args.delete:
            candidates = list()
            # get candidates
            for root, dirs, files in os.walk(args.dir):
                if not os.path.basename(root).startswith("."):
                    for i in dirs:
                        if i.startswith("."):
                            continue

                        if i not in groups:
                            candidates.append(os.path.join(root, i))

                    for i in files:
                        if i.startswith("."):
                            continue
                        candidates.append(os.path.join(root, i))
            # kick out elements
            delete_list = list()
            trunc_len = len(args.dir) + len(os.path.sep)
            for i in candidates:
                if i[trunc_len:] not in elements:
                    delete_list.append(i)

            # deleting
            if delete_list:
                print("Following files and dirs are not exist in ACM Server:\n")
                for i in delete_list:
                    print(" - " + i)

                delete = True
                if not args.force:
                    while True:
                        if sys.version_info[0] == 3:
                            choice = input("\nDeleting all files above? (y/n)")
                        else:
                            choice = raw_input("\nDeleting all files above? (y/n)")
                        if choice.lower() in ["y", "n"]:
                            delete = choice.lower() == "y"
                            break
                        print("Invalid choice, please input y or n.")
                if delete:
                    for i in delete_list:
                        try:
                            if os.path.isfile(i):
                                os.remove(i)
                            else:
                                shutil.rmtree(i)
                        except OSError:
                            pass
                    print("Delete complete, continue to export...\n")
    else:
        zip_file = zipfile.ZipFile(dest_file, 'w', zipfile.ZIP_DEFLATED)

    print(_colored(len(configs), "green") + " dataIds on ACM server will be exported to %s.\n" % _colored(
        args.dir or dest_file, "yellow"))

    i = 0
    for config in configs:
        rel_path = config["group"] if config["group"] != DEFAULT_GROUP_NAME else ""
        if args.dir:
            try:
                os.makedirs(os.path.join(args.dir, rel_path))
            except OSError:
                pass
        i += 1
        sys.stdout.write("\033[K\rExporting: %s/%s   %s:%s" % (i, len(configs), config["group"], config["dataId"]))
        sys.stdout.flush()
        try:
            content = c.get(config["dataId"], config["group"], no_snapshot=True)
        except:
            print("Get content of %s:%s failed." % (config["group"] or DEFAULT_GROUP_NAME, config["dataId"]))
            sys.exit(1)

        if args.dir:
            _write_file(os.path.join(args.dir, rel_path, config["dataId"]), content)
        else:
            zip_file.writestr(os.path.join(rel_path, config["dataId"]), content.encode("utf8"))
    if zip_file:
        zip_file.close()
    print("")
    print("All dataIds exported.\n")


def import_to_server(args):
    e, ep, n, ns = _process_namespace(args)
    c = _get_client(e, ep, n, ns)

    if args.dir and not os.path.isdir(args.dir):
        print("%s does not exist." % _colored(args.dir, "red"))
        sys.exit(1)

    src_file = args.file or args.file or "%s-%s.zip" % (e, n)
    zip_file = None
    if not args.dir and not os.path.isfile(src_file):
        print("%s does not exist." % _colored(src_file, "red"))
        sys.exit(1)

    data_to_import = list()
    if args.dir:
        for f in os.listdir(args.dir):
            if f.startswith("."):
                continue
            if os.path.isfile(os.path.join(args.dir, f)):
                data_to_import.append((f, DEFAULT_GROUP_NAME))
            else:
                for ff in os.listdir(os.path.join(args.dir, f)):
                    if not ff.startswith(".") and os.path.isfile(os.path.join(args.dir, f, ff)):
                        data_to_import.append((ff, f))
    else:
        zip_file = zipfile.ZipFile(src_file, 'r', zipfile.ZIP_DEFLATED)
        for info in zip_file.infolist():
            sp = info.filename.split(os.path.sep)
            if len(sp) == 1:
                data_to_import.append((sp[0], DEFAULT_GROUP_NAME))
            elif len(sp) == 2 and sp[1]:
                data_to_import.append((sp[1], sp[0]))
            else:
                print("ignoring invalid path: %s" % info.filename)

    # process deleting
    if args.delete:
        # pick up candidates
        delete_list = list()
        configs = c.list_all()
        for i in configs:
            if (i["dataId"], i["group"]) not in data_to_import:
                delete_list.append(i)

        # deleting
        if delete_list:
            print("Following dataIds are not exist in %s:\n" % _colored(args.dir or src_file, "yellow"))
            for i in delete_list:
                print(" - %s:%s" % (i["group"], i["dataId"]))

            delete = True
            if not args.force:
                while True:
                    if sys.version_info[0] == 3:
                        choice = input("\nDeleting all dataIds above in ACM server? (y/n)")
                    else:
                        choice = raw_input("\nDeleting all dataIds above in ACM server? (y/n)")
                    if choice.lower() in ["y", "n"]:
                        delete = choice.lower() == "y"
                        break
                    print("Invalid choice, please input y or n.")
            if delete:
                for i in delete_list:
                    c.remove(i["dataId"], i["group"])
                print("Delete complete, continue to import...\n")

    print(_colored(len(data_to_import), "green") + " files will be imported to ACM server.\n")

    i = 0
    for data in data_to_import:
        i += 1
        sys.stdout.write("\033[K\rImporting: %s/%s   %s:%s" % (i, len(data_to_import), data[1], data[0]))
        sys.stdout.flush()
        if args.dir:
            f = os.path.join(args.dir, data[1], data[0]) if data[1] != DEFAULT_GROUP_NAME else os.path.join(args.dir,
                                                                                                            data[0])
            content = _read_file(f)
        else:
            name = os.path.join(data[1], data[0]) if data[1] != DEFAULT_GROUP_NAME else data[0]
            content = zip_file.read(name)

        try:
            c.publish(data[0], data[1], content)
        except:
            print("Publish %s/%s failed." % (data[1], data[0]))
            sys.exit(1)
    if zip_file:
        zip_file.close()
    print("")
    print("All files imported.\n")


def _get_client(e, ep, n, ns):
    c = ACMClient(endpoint=e, namespace=(None if n == "[default]" else n), ak=ns["ak"], sk=ns["sk"])
    if ep.get("kms_enabled"):
        c.set_options(kms_enabled=True, kms_ak=ns.get("kms_ak"), kms_secret=ns.get("kms_secret"),
                      region_id=ep.get("region_id"), key_id=ns.get("key_id"))
    if ep["tls"]:
        c.set_options(tls_enabled=True)
    return c


def arg_parse():
    parser = argparse.ArgumentParser(prog="acm",
                                     description="ACM command line tools for querying and exporting data.", )
    subparsers = parser.add_subparsers(help='sub-command help', title="Sub commands")

    # add
    parser_add = subparsers.add_parser("add", help="add a namespace",
                                       description='Add a namespace, '
                                                   'update if namespace is already exist.',
                                       epilog="Example: acm add acm.aliyun.com:ea61357b-d417-460c-92e4-032677dd8153 "
                                              "-s 'GLff***xcao=' -a 654b43******e9750 -n foo")
    parser_add.add_argument("namespace", default=None, help='use "endpoint:namespace_id" to locate a namespace, '
                                                            'if endpoint is missing, "acm.aliyun.com" act as default.')
    parser_add.add_argument("-a", dest="ak", default=None, help='AccessKey of this namespace.')
    parser_add.add_argument("-s", dest="sk", help='SecretKey of this namespace.')
    parser_add.add_argument("-n", dest="alias", help='alias of the namespace, ":" is not allowed in alias.')
    parser_add.add_argument("--tls", action="store_true", default=False, help="to use TLS connection.")
    parser_add.add_argument("--kms", action="store_true", default=False, help="to use Key Management Service (KMS).")
    parser_add.add_argument("-ka", dest="kms_ak", default=None,
                            help='AccessKey for KMS, use AccessKey by default, required if KMS is enabled.')
    parser_add.add_argument("-ks", dest="kms_secret", default=None,
                            help='SecretKey for KMS, use SecretKey by default, required if KMS is enabled.')
    parser_add.add_argument("-k", dest="key_id", default=None, help='Key ID of KMS, required if KMS is enabled.')
    parser_add.add_argument("-r", dest="region_id", default=None,
                            help='Region ID of Alibaba Cloud, required if KMS is enabled.')
    parser_add.set_defaults(func=add)

    # use
    parser_use = subparsers.add_parser("use", help="switch to a namespace",
                                       description="Switch to a namespace.",
                                       epilog="Example: acm use acm.aliyun.com:ea61357b-d417-460c-92e4-032677dd8153")
    parser_use.add_argument("namespace", help='"endpoint:namespace_id" or alias to use.')
    parser_use.set_defaults(func=use)

    # current
    parser_current = subparsers.add_parser("current", help="show current namespace",
                                           description="Show current namespace.")
    parser_current.set_defaults(func=current)

    # show
    parser_show = subparsers.add_parser("show", help="show all namespaces",
                                        description="Show all namespaces.")
    parser_show.set_defaults(func=show)

    # list
    parser_list = subparsers.add_parser("list", help="get list of dataIds", description="Get list of dataIds.")
    parser_list.add_argument("-g", dest="group", default=None, help='group of the dataId.')
    parser_list.add_argument("-p", dest="prefix", default=None, help='prefix of dataId.')
    parser_list.add_argument("-n", dest="namespace", default=None, help='"endpoint:namespace_id" or alias.')
    parser_list.set_defaults(func=list_conf)

    # pull
    parser_pull = subparsers.add_parser("pull", help="get one config content",
                                        description="Get one config content from ACM server.",
                                        epilog="Example: acm pull group/dataId > dest.txt")
    parser_pull.add_argument("data_id", help='the dataId to pull from, use group"/"dataId to specify group.')
    parser_pull.add_argument("-n", dest="namespace", default=None, help='"endpoint:namespace_id" or alias.')
    parser_pull.set_defaults(func=pull)

    # push
    parser_push = subparsers.add_parser("push", help="push one config",
                                        description="Push one config with the content of a local file or stdin.",
                                        epilog="Example: cat source.txt | acm push group/dataId")
    parser_push.add_argument("data_id", help='the dataId to store the content, use group"/"dataId to specify group.')
    parser_push.add_argument("-f", dest="file", default=None, help='the file to push, stdin can not be empty '
                                                                   'if file is not specified.')
    parser_push.add_argument("-n", dest="namespace", default=None, help='"endpoint:namespace_id" or alias.')
    parser_push.set_defaults(func=push)

    # export
    parser_export = subparsers.add_parser("export", help="export dataIds to local",
                                          description="Export dataIds of specified namespace to local dir or zip file.")
    parser_export.add_argument("-f", dest="file", default=None, help='zip file name, '
                                                                     'use "endpoint-namepspace_id.zip" as default.')
    parser_export.add_argument("-d", dest="dir", default=None, help='export destination dir, file is ignored '
                                                                    'if dir is specified.')
    parser_export.add_argument("-n", dest="namespace", default=None, help='"endpoint:namespace_id" or alias.')
    parser_export.add_argument("--delete", action="store_true", default=False,
                               help="[only for dir mode] "
                                    "delete the file not exist in ACM server (hidden files startswith . are igonred).")
    parser_export.add_argument("--force", action="store_true", default=False, help="[only for dir mode] "
                                                                                   "run and delete silently.")
    parser_export.set_defaults(func=export)

    # import
    parser_import = subparsers.add_parser("import", help="import local dir or zip file to ACM server",
                                          description="Import local dir or zip file to ACM server.")
    parser_import.add_argument("-f", dest="file", default=None, help='zip file name, '
                                                                     'use "endpoint-namepspace_id.zip" as default.')
    parser_import.add_argument("-d", dest="dir", default=None, help='import source dir, file is ignored '
                                                                    'if dir is specified.')
    parser_import.add_argument("-n", dest="namespace", default=None, help='"endpoint:namespace_id" or alias.')
    parser_import.add_argument("--delete", action="store_true", default=False,
                               help="delete the dataId not exist locally.")
    parser_import.add_argument("--force", action="store_true", default=False, help="run and delete silently.")
    parser_import.set_defaults(func=import_to_server)

    return parser.parse_args()


def main():
    args = arg_parse()
    try:
        args.func(args)
    except AttributeError:
        print("No sub command is specified, use -h for help.")

    """
    Usage:
        acm <command> [params]

    Global Commands:
        acm add {endpoint}:{namespace_id} [-a {ak} -s {sk}] [-n {alias}] # Add or update an namespace, not mandatory.
        acm use {endpoint}:{namespace}/{alias} # Choose a namespace for following commands (can be overwritten by -n).
        acm current # Print current endpoint and
        acm show # Print all endpoint and namespace info.

    Namespace Commands(use blank namespace if not specified):
        acm list [-g {group}] [-p {prefix}] # Get all dataIds matching group or prefix.

        acm pull {dataId}                   # Get a config content, default group is DEFAULT_GROUP.

        acm push {dataId} [-f {file}]       # Push one file or content from stdin to ACM

        acm export [-d {dir}] [-f {zip_file}] [--delete] [--force]  # Export dataIds as files.
            --delete:   If local file or directory can not match dataIds ACM, delete it.
            --force:    Overwrite or delete files without asking.

        acm import [-d {dir}] [-f {zip_file}] [--delete] [--force]  # Import files to ACM.
            --delete:   If dataId or group can not match local files, delete it.
            --force:    Overwrite or delete dataIds without asking.

    Examples:
        Configurations:
            |--------------|----------|------------------|
            |   Namespace  |   group  |      dataId      |
            +--------------+----------+------------------+
            |           dev|       ACM|   jdbc.properties|
            +--------------+----------+------------------+
            |           dev|       ACM|   application.yml|
            +--------------+----------+------------------+
            |           dev| VipServer|        nginx.conf|
            +--------------+----------+------------------+
            |       product|       ACM|   jdbc.properties|
            +--------------+----------+------------------+
            |       product|       ACM|   application.yml|
            +--------------+----------+------------------+
            |       product| VipServer|        nginx.conf|
            +--------------+----------+------------------+

        Get started:
            acm add acm.aliyun.com:'60*****0d38' -a '654b4*****50' -s 'GLf****ao=' -n dev
            acm add acm.aliyun.com:'7u*****d9eb' -a '37ab8*****2b' -s 'XMV****xc=' -n product

            acm use dev

        Find all configurations:
            acm list -g ACM

        Get from ACM:
            acm pull ACM/jdbc.properties >> ACM/jdbc.properties

        Modify it, then publish to ACM:
            cat ACM/jdbc.properties | acm push ACM/jdbc.properties

        Clone all configs from ACM:
            acm export -d dev_configs

        Local directories:
        dev_configs
          |
          |-- ACM
          |    |--jdbc.properties
          |    |--application.yml
          |
          |-- VipServer
               |--nginx.conf

        Transfer configs to an other namespace to make an product release
            acm import -d dev_configs -n product


        Tricks Use crontab and local VCS (git,svn) to make synchronization of configurations:
            acm use dev
            acm import -d {local_repo} --delete --force

    """


if __name__ == "__main__":
    main()

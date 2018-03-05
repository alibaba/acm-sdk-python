import os.path
import sys
import json
import fcntl
import shutil
import gettext
from datetime import datetime
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
            "namespaces": {
                "[default]": {
                    "is_current": True,
                    "ak": None,
                    "sk": None,
                    "alias": "[default]",
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
    tls = args.tls
    config = read_config()
    ak = args.ak
    sk = args.sk
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
        config["endpoints"][e] = {
            "tls": tls,
            "is_current": False,
            "namespaces": {}
        }
        print(
                "Adding a new endpoint: %s, using TLS is %s.\n" % (_colored(e, "yellow"), _colored(tls, "yellow")))
    else:
        if config["endpoints"][e]["tls"] != tls:
            config["endpoints"][e]["tls"] = tls
            print("TLS attr of %s has changed to %s.\n" % (_colored(e, "yellow"), _colored(tls, "yellow")))

    if ns in config["endpoints"][e]["namespaces"]:
        if ak is not None:
            config["endpoints"][e]["namespaces"][ns]["ak"] = ak
        if sk is not None:
            config["endpoints"][e]["namespaces"][ns]["sk"] = sk
        if args.alias is not None:
            config["endpoints"][e]["namespaces"][ns]["alias"] = alias
        config["endpoints"][e]["namespaces"][ns]["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("Namespace %s is already exist in %s, updating configs.\n" % (
            _colored(ns, "green"), _colored(e, "yellow")))
    else:
        config["endpoints"][e]["namespaces"][ns] = {"ak": ak, "sk": sk, "alias": alias, "is_current": False,
                                                    "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
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
    configs = c.list_all(args.group, args.prefix)
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
    c = ACMClient(endpoint=e, namespace=(None if n == "[default]" else n), ak=ns["ak"], sk=ns["sk"])
    if ep["tls"]:
        c.set_options(tls_enabled=True)
    if "/" in args.data_id:
        g, d = args.data_id.split("/")
        content = c.get(d, g, no_snapshot=True)
    else:
        content = c.get(args.data_id, None, no_snapshot=True)

    if content is None:
        print("%s does not exist." % _colored(args.data_id, "red"))
        sys.exit(1)

    if args.stdout:
        print(content)
        sys.exit(0)

    fn = args.file or args.data_id
    if "/" in fn:
        try:
            os.makedirs(fn[:fn.rindex("/")])
        except OSError:
            pass
    _write_file(fn, content)

    print("[dataId:%s] has been saved to [file:%s].\n" % (_colored(args.data_id, "green"), _colored(fn, "yellow")))


def push(args):
    e, ep, n, ns = _process_namespace(args)
    c = ACMClient(endpoint=e, namespace=(None if n == "[default]" else n), ak=ns["ak"], sk=ns["sk"])
    if ep["tls"]:
        c.set_options(tls_enabled=True)

    if not os.path.exists(args.file):
        print("File %s does not exist." % _colored(args.file, "red"))
        sys.exit(1)

    data_id = args.data_id or args.file

    if data_id.count("/") > 1:
        print("Invalid dataId or filename, more than one / is given.")
        sys.exit(1)

    if "/" in data_id:
        group, data_id = data_id.split("/")
    else:
        group = None

    content = _read_file(args.file)

    c.publish(data_id, group, content)

    print("[file:%s] has been pushed to [dataId:%s].\n" % (
        _colored(args.file, "yellow"), _colored(args.data_id or args.file, "green")))


def current(args):
    config = read_config()
    e, n = _get_current(config)
    print("Current Endpoint:\t%s, using TLS is %s." % (
        _colored(e, "yellow"), _colored(config["endpoints"][e]["tls"], "yellow")))
    print("\nCurrent Namespace:\t%s" % (_colored(n)))
    ns = config["endpoints"][e]["namespaces"][n]

    print("\tAlias:\t\t%s" % _colored(ns["alias"], "green"))
    print("\tAccessKey:\t%s" % ns["ak"])
    print("\tSecretKey:\t%s" % ns["sk"])
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
    c = ACMClient(endpoint=e, namespace=(None if n == "[default]" else n), ak=ns["ak"], sk=ns["sk"])
    if ep["tls"]:
        c.set_options(tls_enabled=True)

    if args.dir:
        try:
            os.makedirs(args.dir)
        except OSError:
            pass

    d = args.dir or "."

    configs = c.list_all()
    groups = set()
    elements = set()
    for i in configs:
        groups.add(i["group"])
        elements.add(os.path.join(i["group"], i["dataId"]) if i["group"] != DEFAULT_GROUP_NAME else i["dataId"])

    # process deleting
    if args.delete:
        candidates = list()
        # get candidates
        for root, dirs, files in os.walk(d):
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
        trunc_len = len(d) + len(os.path.sep)
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

    print(_colored(len(configs), "green") + " dataIds on ACM server will be exported to %s.\n" % _colored(d, "yellow"))

    i = 0
    for config in configs:
        rel_path = config["group"] if config["group"] != DEFAULT_GROUP_NAME else ""
        try:
            os.makedirs(os.path.join(d, rel_path))
        except OSError:
            pass
        i += 1
        sys.stdout.write("\033[K\rExporting: %s/%s   %s:%s" % (i, len(configs), config["group"], config["dataId"]))
        sys.stdout.flush()
        _write_file(os.path.join(d, rel_path, config["dataId"]),
                    c.get(config["dataId"], config["group"], no_snapshot=True))
    print("")
    print("All dataIds exported.\n")


def import_to_server(args):
    e, ep, n, ns = _process_namespace(args)
    c = ACMClient(endpoint=e, namespace=(None if n == "[default]" else n), ak=ns["ak"], sk=ns["sk"])
    if ep["tls"]:
        c.set_options(tls_enabled=True)

    if args.dir and not os.path.isdir(args.dir):
        print("%s does not exist." % _colored(args.dir, "red"))

    d = args.dir or "."

    data_to_import = list()
    for f in os.listdir(d):
        if f.startswith("."):
            continue
        if os.path.isfile(os.path.join(d, f)):
            data_to_import.append((f, DEFAULT_GROUP_NAME))
        else:
            for ff in os.listdir(os.path.join(d, f)):
                if not ff.startswith(".") and os.path.isfile(os.path.join(d, f, ff)):
                    data_to_import.append((ff, f))

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
            print("Following dataIds are not exist in %s:\n" % _colored(d, "yellow"))
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
        f = os.path.join(d, data[1], data[0]) if data[1] != DEFAULT_GROUP_NAME else os.path.join(d, data[0])
        c.publish(data[0], data[1], _read_file(f))
    print("")
    print("All files imported.\n")


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
    parser_add.add_argument("--tls", action="store_true", default=False, help="to use tls connection.")
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
                                        description="Get one config content from ACM server and save to local file.",
                                        epilog="Example: acm pull group/dataId")
    parser_pull.add_argument("data_id", help='the dataId to pull, use group"/"dataId to specify group, '
                                             'if group is specified, file will be store under an subdir of group name.')
    parser_pull.add_argument("-f", dest="file", default=None, help="file to store the content, create one if absent.")
    parser_pull.add_argument("-o", action="store_true", dest="stdout", default=False, help="only print on console.")
    parser_pull.add_argument("-n", dest="namespace", default=None, help='"endpoint:namespace_id" or alias.')
    parser_pull.set_defaults(func=pull)

    # push
    parser_push = subparsers.add_parser("push", help="push one config",
                                        description="Push one config with content of local file to ACM server.",
                                        epilog="Example: acm push dir/file")
    parser_push.add_argument("file", help="file to push, filename is use as dataId by default, "
                                          "if parent dir is attached, it will be use as group.")
    parser_push.add_argument("-d", dest="data_id", default=None, help='dataId to store the content, '
                                                                      'use group"/"dataId to specify group.')
    parser_push.add_argument("-n", dest="namespace", default=None, help='"endpoint:namespace_id" or alias.')
    parser_push.set_defaults(func=push)

    # export
    parser_export = subparsers.add_parser("export", help="export dataIds to local files",
                                          description="Export dataIds of specified namespace to local files.")
    parser_export.add_argument("-d", dest="dir", default=None, help='export destination dir.')
    parser_export.add_argument("-n", dest="namespace", default=None, help='"endpoint:namespace_id" or alias.')
    parser_export.add_argument("--delete", action="store_true", default=False,
                               help="delete the file not exist in ACM server (hidden files startswith . are igonred).")
    parser_export.add_argument("--force", action="store_true", default=False, help="run and delete silently.")
    parser_export.set_defaults(func=export)

    # import
    parser_import = subparsers.add_parser("import", help="import files to ACM server",
                                          description="Import files to ACM server, using specified namespace.")
    parser_import.add_argument("-d", dest="dir", default=None, help='import source dir.')
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

        acm pull {dataId} [-f {file}] [-o]  # Get a config content, default group is DEFAULT_GROUP.
            -o: Print content to screen.

        acm push {file} [-d {dataId}]      # Push one file to ACM

        acm export [-d {dir}] [--delete] [--force]  # Export dataIds as files, with group as parent directory.
            --delete:   If local file or directory can not match dataIds ACM, delete it.
            --force:    Overwrite or delete files without asking.

        acm import [-d {dir}] [--delete] [--force]  # Import files to ACM, first level
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
            acm pull jdbc.properties -g ACM

        Modify it, then publish to ACM:
            acm push jdbc.properties -g ACM

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

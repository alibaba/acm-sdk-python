import os.path
import fcntl
import logging
import sys

logger = logging.getLogger("acm")


def read_file(base, key):
    file_path = os.path.join(base, key)
    if not os.path.exists(file_path):
        return None

    try:
        if sys.version_info[0] == 3:
            with open(file_path, "r+", newline="") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                return f.read()
        else:
            with open(file_path, "r+") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                return f.read()
    except OSError:
        logger.exception("[read-file] read file failed, file path:%s" % file_path)
        return None


def save_file(base, key, content):
    file_path = os.path.join(base, key)
    if not os.path.isdir(base):
        try:
            os.makedirs(base)
        except OSError:
            logger.warning("[save-file] dir %s is already exist" % base)

    try:
        with open(file_path, "wb") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(content if type(content) == bytes else content.encode("utf8"))

    except OSError:
        logger.exception("[save-file] save file failed, file path:%s" % file_path)


def delete_file(base, key):
    file_path = os.path.join(base, key)
    try:
        os.remove(file_path)
    except OSError:
        logger.warning("[delete-file] file not exists, file path:%s" % file_path)

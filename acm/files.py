import os.path
import fcntl
import logging

logger = logging.getLogger("acm")


def read_file(base, key):
    file_path = os.path.join(base, key)
    if not os.path.exists(file_path):
        return None
    with open(file_path, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
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

    with open(file_path, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(content)
        except OSError:
            logger.exception("[save-file] save file failed, file path:%s" % file_path)


def delete_file(base, key):
    file_path = os.path.join(base, key)
    try:
        os.remove(file_path)
    except OSError:
        logger.warning("[delete-file] file not exists, file path:%s" % file_path)

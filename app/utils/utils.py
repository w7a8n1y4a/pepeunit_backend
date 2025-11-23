import base64
import datetime
import hashlib
import logging
import os
import shutil
import string
import time
import uuid
from collections.abc import AsyncGenerator
from typing import TypeVar

import pyaes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dateutil.relativedelta import relativedelta
from fastapi import UploadFile
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern

from app import settings
from app.configs.errors import CipherError


def aes_encode(data: str, key: str = settings.pu_encrypt_key) -> str:
    """
    data: any python str
    key: (base64 str) 16, 24, 32 bytes sync encrypt key
    return: (base64 str - iv).(base64 str - encrypted data)
    """

    len_content = len(data)
    if len_content > settings.pu_max_cipher_length:
        msg = f"The encryption content is {len_content} long, although only <= {settings.pu_max_cipher_length} is allowed"
        raise CipherError(msg)

    key = base64.b64decode(key.encode())
    iv = os.urandom(16)

    # set encrypter
    encrypter = pyaes.Encrypter(pyaes.AESModeOfOperationCBC(key, iv))
    # encrypted binary to base64 str
    cipher = base64.b64encode(encrypter.feed(data) + encrypter.feed()).decode(
        "utf-8"
    )

    return f"{base64.b64encode(iv).decode('utf-8')}.{cipher}"


def aes_decode(data: str, key: str = settings.pu_encrypt_key) -> str:
    """
    data: (base64 str - iv).(base64 str - encrypted data)
    key: (base64 str) 16, 24, 32 bytes sync encrypt key
    return: decode python str
    """
    key = base64.b64decode(key.encode())
    iv = base64.b64decode(data.split(".")[0].encode())

    # set decrypter
    decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(key, iv))
    # data (iv).(encrypted text) to binary encrypted text
    cipher = base64.b64decode(data.split(".")[1].encode())

    return (decrypter.feed(cipher) + decrypter.feed()).decode("utf-8")


def aes_gcm_encode(data: str, key: str = settings.pu_encrypt_key) -> str:
    """
    data: any python str
    key: (base64 str) 16, 24, 32 bytes sync encrypt key
    return: (base64 str - nonce).(base64 str - encrypted data).(base64 str - tag)
    """
    len_content = len(data)
    if len_content > settings.pu_max_cipher_length:
        msg = f"The encryption content is {len_content} long, although only <= {settings.pu_max_cipher_length} is allowed"
        raise CipherError(msg)

    key = base64.b64decode(key.encode())
    nonce = os.urandom(12)  # 96-bit nonce for AES-GCM
    aesgcm = AESGCM(key)

    cipher = aesgcm.encrypt(nonce, data.encode(), None)  # Encrypt data

    return f"{base64.b64encode(nonce).decode()}.{base64.b64encode(cipher).decode()}"


def aes_gcm_decode(data: str, key: str = settings.pu_encrypt_key) -> str:
    """
    data: (base64 str - nonce).(base64 str - encrypted data)
    key: (base64 str) 16, 24, 32 bytes sync encrypt key
    return: decode python str
    """
    key = base64.b64decode(key.encode())
    nonce, cipher = data.split(".")
    nonce = base64.b64decode(nonce.encode())
    cipher = base64.b64decode(cipher.encode())

    aesgcm = AESGCM(key)

    return aesgcm.decrypt(nonce, cipher, None).decode("utf-8")


def password_to_hash(password: str) -> (str, str):
    dynamic_salt = base64.b64encode(os.urandom(16)).decode("utf-8")

    hashed_password = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        (dynamic_salt + settings.pu_static_salt).encode("utf-8"),
        100000,
    )

    return aes_gcm_encode(dynamic_salt), base64.b64encode(
        hashed_password
    ).decode("utf-8")


def check_password(
    password: str, hashed_password_db: str, cipher_dynamic_salt: str
) -> bool:
    dynamic_salt = aes_gcm_decode(cipher_dynamic_salt)

    hashed_password = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        (dynamic_salt + settings.pu_static_salt).encode("utf-8"),
        100000,
    )

    return hashed_password_db == base64.b64encode(hashed_password).decode(
        "utf-8"
    )


def generate_random_string(length=6):
    chars = string.ascii_lowercase + string.ascii_uppercase + string.digits
    return "".join(chars[c % len(chars)] for c in os.urandom(length))


def clean_files_with_pepeignore(directory: str, pepe_ignore_path: str) -> None:
    if not os.path.exists(pepe_ignore_path):
        return

    with open(pepe_ignore_path) as f:
        pepeignore_rules = f.read().splitlines()

    spec = PathSpec.from_lines(GitWildMatchPattern, pepeignore_rules)

    for root, dirs, files in os.walk(directory, topdown=False):
        rel_root = os.path.relpath(root, directory)
        for file in files:
            if rel_root == ".":
                file_path = file
            else:
                file_path = os.path.join(rel_root, file)
            if spec.match_file(file_path):
                full_path = os.path.join(directory, file_path)
                os.remove(full_path)
        for dir_name in dirs:
            if rel_root == ".":
                dir_path = dir_name
            else:
                dir_path = os.path.join(rel_root, dir_name)
            if spec.match_file(dir_path) or spec.match_file(f"{dir_path}/"):
                full_dir_path = os.path.join(directory, dir_path)
                shutil.rmtree(full_dir_path, ignore_errors=True)


def timeit(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        logging.info(
            f"Function '{func.__name__}' executed in {execution_time} seconds."
        )
        return result

    return wrapper


def snake_to_camel(snake_str: str) -> str:
    return "".join(part.capitalize() for part in snake_str.split("_"))


def obj_serializer(obj):
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    msg = f"Type {type(obj)} not serializable"
    raise TypeError(msg)


async def create_upload_file_from_path(file_path: str) -> UploadFile:
    return UploadFile(
        filename=file_path.split("/")[-1],
        file=open(file_path, "rb"),
        size=os.path.getsize(file_path),
    )


def remove_dict_none(data):
    if isinstance(data, dict):
        return {
            k: remove_dict_none(v) for k, v in data.items() if v is not None
        }
    if isinstance(data, list):
        return [remove_dict_none(item) for item in data if item is not None]
    return data


T = TypeVar("T")


async def async_chunked[T](a_gen: AsyncGenerator[T], size: int):
    batch = []
    async for item in a_gen:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def ensure_timezone_aware(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.UTC)
    return dt


def parse_interval(s: str) -> datetime.timedelta | relativedelta:
    value, unit = int(s[:-1]), s[-1]
    match unit:
        case "s":
            return datetime.timedelta(seconds=value)
        case "m":
            return datetime.timedelta(minutes=value)
        case "h":
            return datetime.timedelta(hours=value)
        case "d":
            return datetime.timedelta(days=value)
        case "M":
            return relativedelta(months=value)
        case "y":
            return relativedelta(years=value)
        case _:
            msg = f"Unknown interval: {s}"
            raise ValueError(msg)


def logo_to_console():
    logging.info(
        rf"""

                             ........:
                            :......::-
                             .....::.:
                             .....::.-
                        :.........::.-****
                      :........::::--==++###%
                    :::-++*++=======++*#@@%%-::
                  ....:-=---==++******###%%*-...:
                :....:--===++=*=+**%@@%@%%%%*+:..:
              :....::=====+====+==*##%@%%%#*##+=...:
            -...........:-===++*=++**#%*:....::---...:
           :......-..:*##%%*+++===+#*-.:-..+#%%%#*+:...:
         :......=..++*##%%%%#**++--=..-.--*##%%*%@#+=....-
        :..:-:.+-+=+#%%***+#@#*=---..+:=**+%@%%*%@@*+=-...:
       =--===-.%%=#*#%-.=:+@@%**==-::%%#==#@@#%@@+@%**+=:::
       =-=====.+@%%+@@%:.-#@@##***+-:%@%*%@%@%%=%@@#++::-::
       =--====-.#@@*@+@@*@@@#***#**#-:%@*%%+@=@*@@#*==-..::
       ==+*=+++=::#@@@@@@@########*#%==+%@@@@@@@#**++++*+::-
       *@*+++++++++****#####%##%###%#%%%%#########*##+==*#--
       -*@%**==+=+*#=+**###%%%%####%%##%%%%%%%#%%%#####@@%=+
    :::-=--+%%@*##*.-.*#####%%%########%%%%%%%###%%@@%*++=+****
    ....:---------==***#%%%%%*%#%%#%%%%%%%%%#*++=====+**#######%
    ....:-:::-=====-----------------------===+++***+++*#%@@%###%
    :--=:=++++====---::::---------===========++*##%@@@@@@@@@@@@@
       =--+*++++***+=+*****###########%%%%%%%%%#%%%#@@@@@@@@
         +==++++**+...:*=+=*=+==*++##++=+++#%-:-*%#%@@@@@@
            %#*****#####*##*-+-=*==#--+#**%*%%%%@@@@@@@
              *##%@@@@@@@%%%%%%%%%%%%%%@@@@@@@@@@@@@@
              *###%%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
                  %%@@@@@@@@@@@@@@@@@@@@@@@@@@@@
               _____                            _ _
              |  __ \                          (_) |
              | |__) |__ _ __   ___ _   _ _ __  _| |_
              |  ___/ _ \ '_ \ / _ \ | | | '_ \| | __|
              | |  |  __/ |_) |  __/ |_| | | | | | |_
              |_|   \___| .__/ \___|\__,_|_| |_|_|\__|
                        | |
                        |_|

       v{settings.version} - {settings.license}
       Federated IoT Platform
       Front: {settings.pu_link}
       REST:  {settings.pu_link_prefix}/docs
       GQL:   {settings.pu_link_prefix}/graphql
       TG:    {settings.pu_telegram_bot_link}
       Docs:  https://pepeunit.com
              """
    )

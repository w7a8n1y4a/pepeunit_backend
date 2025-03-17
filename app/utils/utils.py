import base64
import hashlib
import logging
import os
import string
import time

import pyaes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern

from app import settings
from app.configs.errors import CipherError


def aes_encode(data: str, key: str = settings.backend_encrypt_key) -> str:
    """
    data: any python str
    key: (base64 str) 16, 24, 32 bytes sync encrypt key
    return: (base64 str - iv).(base64 str - encrypted data)
    """

    len_content = len(data)
    if len_content > settings.backend_max_cipher_length:
        raise CipherError(
            'The encryption content is {} long, although only <= {} is allowed'.format(
                len_content, settings.backend_max_cipher_length
            )
        )

    key = base64.b64decode(key.encode())
    iv = os.urandom(16)

    # set encrypter
    encrypter = pyaes.Encrypter(pyaes.AESModeOfOperationCBC(key, iv))
    # encrypted binary to base64 str
    cipher = base64.b64encode(encrypter.feed(data) + encrypter.feed()).decode('utf-8')

    return f"{base64.b64encode(iv).decode('utf-8')}.{cipher}"


def aes_decode(data: str, key: str = settings.backend_encrypt_key) -> str:
    """
    data: (base64 str - iv).(base64 str - encrypted data)
    key: (base64 str) 16, 24, 32 bytes sync encrypt key
    return: decode python str
    """
    key = base64.b64decode(key.encode())
    iv = base64.b64decode(data.split('.')[0].encode())

    # set decrypter
    decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(key, iv))
    # data (iv).(encrypted text) to binary encrypted text
    cipher = base64.b64decode(data.split('.')[1].encode())

    return (decrypter.feed(cipher) + decrypter.feed()).decode('utf-8')


def aes_gcm_encode(data: str, key: str = settings.backend_encrypt_key) -> str:
    """
    data: any python str
    key: (base64 str) 16, 24, 32 bytes sync encrypt key
    return: (base64 str - nonce).(base64 str - encrypted data).(base64 str - tag)
    """
    len_content = len(data)
    if len_content > settings.backend_max_cipher_length:
        raise CipherError(
            f'The encryption content is {len_content} long, although only <= {settings.backend_max_cipher_length} is allowed'
        )

    key = base64.b64decode(key.encode())
    nonce = os.urandom(12)  # 96-bit nonce for AES-GCM
    aesgcm = AESGCM(key)

    cipher = aesgcm.encrypt(nonce, data.encode(), None)  # Encrypt data

    return f"{base64.b64encode(nonce).decode()}.{base64.b64encode(cipher).decode()}"


def aes_gcm_decode(data: str, key: str = settings.backend_encrypt_key) -> str:
    """
    data: (base64 str - nonce).(base64 str - encrypted data)
    key: (base64 str) 16, 24, 32 bytes sync encrypt key
    return: decode python str
    """
    key = base64.b64decode(key.encode())
    nonce, cipher = data.split('.')
    nonce = base64.b64decode(nonce.encode())
    cipher = base64.b64decode(cipher.encode())

    aesgcm = AESGCM(key)

    return aesgcm.decrypt(nonce, cipher, None).decode('utf-8')


def password_to_hash(password: str) -> (str, str):
    dynamic_salt = base64.b64encode(os.urandom(16)).decode('utf-8')

    hashed_password = hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), (dynamic_salt + settings.backend_static_salt).encode('utf-8'), 100000
    )

    return aes_gcm_encode(dynamic_salt), base64.b64encode(hashed_password).decode('utf-8')


def check_password(password: str, hashed_password_db: str, cipher_dynamic_salt: str) -> bool:
    dynamic_salt = aes_gcm_decode(cipher_dynamic_salt)

    hashed_password = hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), (dynamic_salt + settings.backend_static_salt).encode('utf-8'), 100000
    )

    return hashed_password_db == base64.b64encode(hashed_password).decode('utf-8')


def generate_random_string(length=6):
    chars = string.ascii_lowercase + string.ascii_uppercase + string.digits
    return ''.join(chars[c % len(chars)] for c in os.urandom(length))


def clean_files_with_pepeignore(directory: str, pepe_ignore_path: str) -> None:
    if not os.path.exists(pepe_ignore_path):
        return

    with open(pepe_ignore_path, 'r') as f:
        pepeignore_rules = f.read().splitlines()

    spec = PathSpec.from_lines(GitWildMatchPattern, pepeignore_rules)

    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.relpath(os.path.join(root, file), directory)
            if spec.match_file(file_path):
                full_path = os.path.join(directory, file_path)
                os.remove(full_path)


def timeit(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        logging.info(f"Function '{func.__name__}' executed in {execution_time:.6f} seconds.")
        return result

    return wrapper

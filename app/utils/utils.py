import os
import pyaes
import base64
import hashlib

from sqlalchemy import desc, asc
from sqlmodel import or_

from app import settings
from app.core.enum import OrderByDate


def aes_encode(data: str, key: str = settings.encrypt_key) -> str:
    """
    data: any python str
    key: (base64 str) 16, 24, 32 bytes sync encrypt key
    return: (base64 str - iv).(base64 str - encrypted data)
    """
    key = base64.b64decode(key.encode())
    iv = os.urandom(16)

    # set encrypter
    encrypter = pyaes.Encrypter(pyaes.AESModeOfOperationCBC(key, iv))
    # encrypted binary to base64 str
    cipher = base64.b64encode(encrypter.feed(data) + encrypter.feed()).decode('utf-8')

    return f"{base64.b64encode(iv).decode('utf-8')}.{cipher}"


def aes_decode(data: str, key: str = settings.encrypt_key) -> str:
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


def password_to_hash(password: str) -> (str, str):
    dynamic_salt = base64.b64encode(os.urandom(16)).decode('utf-8')

    hashed_password = hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), (dynamic_salt + settings.static_salt).encode('utf-8'), 100000
    )

    return aes_encode(dynamic_salt), base64.b64encode(hashed_password).decode('utf-8')


def check_password(password: str, hashed_password_db: str, cipher_dynamic_salt: str) -> bool:
    dynamic_salt = aes_decode(cipher_dynamic_salt)

    hashed_password = hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), (dynamic_salt + settings.static_salt).encode('utf-8'), 100000
    )

    return hashed_password_db == base64.b64encode(hashed_password).decode('utf-8')


def apply_ilike_search_string(query, filters, fields: list):
    if filters.dict()['search_string'] and len(filters.dict()['search_string']) > 0:
        for word in filters.search_string.split():
            query = query.where(or_(*[field.ilike(f'%{word}%') for field in fields]))

    return query


def apply_enums(query, filters, fields: dict):
    for field, value in filters.dict():
        if field in fields.values():
            query = query.where(fields[field] == value)
    return query


def apply_offset_and_limit(query, filters):
    return query.offset(filters.offset if filters.offset else None).limit(filters.limit if filters.limit else None)


def apply_orders_by(query, filters, fields: dict):
    for field, value in filters.dict():
        if field in fields.values() and isinstance(value, OrderByDate):
            query = query.order_by(asc(fields[field]) if value == OrderByDate.asc else desc(fields[field]))
    return query

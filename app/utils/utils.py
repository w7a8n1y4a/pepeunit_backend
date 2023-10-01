import pyaes
import base64


def aes_encode(key: bytes, iv: bytes, data: str) -> str:
    """
    key: 16, 24, 32 bytes sync encrypt key
    iv: initial vector - 16 bytes
    data: python str
    return: base64 str - utf-8
    """

    # set encrypter
    encrypter = pyaes.Encrypter(pyaes.AESModeOfOperationCBC(key, iv))

    return base64.b64encode(encrypter.feed(data) + encrypter.feed()).decode('utf-8')


def aes_decode(key: bytes, iv: bytes, cipher: str) -> str:
    """
    key: 16, 24, 32 bytes sync encrypt key
    iv: initial vector - 16 bytes
    data: base64 str - utf-8
    return: python str
    """

    # set decrypter
    decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(key, iv))

    return decrypter.feed(base64.b64decode(cipher)) + decrypter.feed()

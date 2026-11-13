from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _cipher():
    key = settings.SERVICE_TOKEN_KEY
    if not key:
        raise ImproperlyConfigured("SERVICE_TOKEN_KEY must be set before creating services")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise ImproperlyConfigured("SERVICE_TOKEN_KEY must be a Fernet key") from exc


def encrypt_token(token):
    return _cipher().encrypt(token.encode("utf-8")).decode("ascii")


def decrypt_token(ciphertext):
    return _cipher().decrypt(ciphertext.encode("ascii")).decode("utf-8")

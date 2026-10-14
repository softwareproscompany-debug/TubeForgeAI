"""Encrypted-secret helpers.

All secret material at rest is Fernet-encrypted with ``settings.FERNET_KEY``.
Ciphertext is stored in :class:`core.models.EncryptedSecret.encrypted_value`.

Key rotation
------------
1. Generate a new key: ``Fernet.generate_key()``.
2. For every EncryptedSecret row, call :func:`rotate_encryption` with the old
   and new keys and persist the returned bytes.
3. Only after every row is re-encrypted, update the ``FERNET_KEY`` env var and
   restart. Rotating the env var first will make old ciphertext undecryptable.
"""
from cryptography.fernet import Fernet
from django.conf import settings


def _fernet(key=None):
    raw = key if key is not None else settings.FERNET_KEY
    if isinstance(raw, str):
        raw = raw.encode()
    return Fernet(raw)


def encrypt_value(plaintext):
    """Encrypt ``str``/``bytes`` and return Fernet token bytes."""
    if isinstance(plaintext, str):
        plaintext = plaintext.encode()
    return _fernet().encrypt(bytes(plaintext))


def decrypt_value(ciphertext):
    """Decrypt Fernet token bytes back to ``str``."""
    if isinstance(ciphertext, memoryview):
        ciphertext = ciphertext.tobytes()
    return _fernet().decrypt(bytes(ciphertext)).decode()


def rotate_encryption(old_key, new_key, ciphertext):
    """Re-encrypt ``ciphertext`` from ``old_key`` to ``new_key``.

    Returns the new token bytes. The caller persists them and only afterwards
    switches ``FERNET_KEY`` (see module docstring for the rotation procedure).
    """
    if isinstance(ciphertext, memoryview):
        ciphertext = ciphertext.tobytes()
    plaintext = _fernet(old_key).decrypt(bytes(ciphertext))
    return _fernet(new_key).encrypt(plaintext)

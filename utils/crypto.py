"""
Módulo de cifrado AES-256-GCM con derivación de clave PBKDF2.

Usado por:
- config_backup.py: cifrar/descifrar exportación de configuración
- config.py: cifrar/descifrar .env en disco (protección en reposo)
"""
import base64
import os
import logging

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger("TradingBot")

# --- Constantes ---
_SALT_LEN = 16          # bytes, salt para PBKDF2
_NONCE_LEN = 12         # bytes, nonce para AES-GCM (recomendado: 12)
_ITERATIONS = 600_000   # iteraciones PBKDF2 (OWASP 2024 recomienda >600k)
_KEY_LEN = 32           # bytes = AES-256


def _derive_key(password: str, salt: bytes) -> bytes:
    """Deriva una clave AES-256 desde una password usando PBKDF2-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=_KEY_LEN,
        salt=salt,
        iterations=_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt(password: str, plaintext: str) -> str:
    """
    Cifra texto plano con AES-256-GCM.

    Args:
        password: Contraseña del usuario.
        plaintext: Texto a cifrar.

    Returns:
        String en base64 con formato: salt + nonce + ciphertext (todo concatenado).
    """
    if not plaintext:
        return ""
    salt = os.urandom(_SALT_LEN)
    nonce = os.urandom(_NONCE_LEN)
    key = _derive_key(password, salt)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # Empaquetar: salt + nonce + ciphertext
    payload = salt + nonce + ciphertext
    return base64.urlsafe_b64encode(payload).decode("ascii")


def decrypt(password: str, encrypted: str) -> str:
    """
    Descifra texto cifrado con AES-256-GCM.

    Args:
        password: Contraseña del usuario.
        encrypted: String en base64 (salt + nonce + ciphertext).

    Returns:
        Texto descifrado, o string vacío si hay error.
    """
    if not encrypted:
        return ""
    try:
        payload = base64.urlsafe_b64decode(encrypted.encode("ascii"))
        if len(payload) < _SALT_LEN + _NONCE_LEN:
            logger.error("Payload cifrado demasiado corto")
            return ""
        salt = payload[:_SALT_LEN]
        nonce = payload[_SALT_LEN:_SALT_LEN + _NONCE_LEN]
        ciphertext = payload[_SALT_LEN + _NONCE_LEN:]
        key = _derive_key(password, salt)
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
    except Exception as e:
        logger.error(f"Error descifrando: {e}")
        return ""




"""X.509 command signing for Bambu Lab printers (post-Jan 2025 firmware).

Signs outbound MQTT commands with RSA-SHA256 using the publicly-extracted
Bambu Connect application certificate. Without this, commands silently fail
on printers running newer firmware without Developer Mode enabled.

The embedded keys are already public knowledge:
https://hackaday.com/2025/01/19/bambu-connects-authentication-x-509-certificate-and-private-key-extracted/

Override via BAMBU_APP_PRIVATE_KEY / BAMBU_APP_CERTIFICATE env vars if
Bambu Lab rotates the credentials.
"""

from __future__ import annotations

import base64
import json
import logging
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

logger = logging.getLogger("bambu_printer_manager")

DEFAULT_CERT_ID = "GLOF3813734089-524a37c80000c6a6a274a47b3281"

_DEFAULT_PRIVATE_KEY = """\
-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDQNp2NfkajwcWH
PIqosa08P1ZwETPr1veZCMqieQxWtYw97wp+JCxX4yBrBcAwid7o7PHI9KQVzPRM
f0uXspaDUdSljrfJ/YwGEz7+GJz4+ml1UbWXBePyzXW1+N2hIGGn7BcNuA0v8rMY
uvVgiIIQNjLErgGcCWmMHLwsMMQ7LNprUZZKsSNB4HaQDH7cQZmYBN/O45np6l+K
VuLdzXdDpZcOM7bNO6smev822WPGDuKBo1iVfQbUe10X4dCNwkBR3QGpScVvg8gg
tRYZDYue/qc4Xaj806RZPttknWfxdvfZgoOmAiwnyQ5K3+mzNYHgQZAOC2ydkK4J
s+ZizK3lAgMBAAECggEAKwEcyXyrWmdLRQNcIDuSbD8ouzzSXIOp4BHQyH337nDQ
5nnY0PTns79VksU9TMktIS7PQZJF0brjOmmQU2SvcbAVG5y+mRmlMhwHhrPOuB4A
ahrWRrsQubV1+n/MRttJUEWS/WJmVuDp3NHAnI+VTYPkOHs4GeJXynik5PutjAr3
tYmr3kaw0Wo/hYAXTKsI/R5aenC7jH8ZSyVcZ/j+bOSH5sT5/JY122AYmkQOFE7s
JA0EfYJaJEwiuBWKOfRLQVEHhOFodUBZdGQcWeW3uFb88aYKN8QcKTO8/f6e4r8w
QojgK3QMj1zmfS7xid6XCOVa17ary2hZHAEPnjcigQKBgQDQnm4TlbVTsM+CbFUS
1rOIJRzPdnH3Y7x3IcmVKZt81eNktsdu56A4U6NEkFQqk4tVTT4TYja/hwgXmm6w
J+w0WwZd445Bxj8PmaEr6Z/NSMYbCsi8pRelKWmlIMwD2YhtY/1xXD37zpOgN8oQ
ryTKZR2gljbPxdfhKS7YerLp2wKBgQD/gJt3Ds69j1gMDLnnPctjmhsPRXh7PQ0e
E9lqgFkx/vNuCuyRs6ymic2rBZmkdlpjsTJFmz1bwOzIvSRoH6kp0Mfyo6why5kr
upDf7zz+hlvaFewme8aDeV3ex9Wvt73D66nwAy5ABOgn+66vZJeo0Iq/tnCwK3a/
evTL9BOzPwKBgEUi7AnziEc3Bl4Lttnqa08INZcPgs9grzmv6dVUF6J0Y8qhxFAd
1Pw1w5raVfpSMU/QrGzSFKC+iFECLgKVCHOFYwPEgQWNRKLP4BjkcMAgiP63QTU7
ZS2oHsnJp7Ly6YKPK5Pg5O3JVSU4t+91i7TDc+EfRwTuZQ/KjSrS5u4XAoGBAP06
v9reSDVELuWyb0Yqzrxm7k7ScbjjJ28aCTAvCTguEaKNHS7DP2jHx5mrMT35N1j7
NHIcjFG2AnhqTf0M9CJHlQR9B4tvON5ISHJJsNAq5jpd4/G4V2XTEiBNOxKvL1tQ
5NrGrD4zHs0R+25GarGcDwg3j7RrP4REHv9NZ4ENAoGAY7Nuz6xKu2XUwuZtJP7O
kjsoDS7bjP95ddrtsRq5vcVjJ04avnjsr+Se9WDA//t7+eSeHjm5eXD7u0NtdqZo
WtSm8pmWySOPXMn9QQmdzKHg1NOxer//f1KySVunX1vftTStjsZH7dRCtBEePcqg
z5Av6MmEFDojtwTqvEZuhBM=
-----END PRIVATE KEY-----"""


def _load_private_key():
    """Load the RSA private key, preferring env var override."""
    pem = os.environ.get("BAMBU_APP_PRIVATE_KEY", _DEFAULT_PRIVATE_KEY)
    return serialization.load_pem_private_key(pem.encode("utf-8"), password=None)


# Lazy-loaded singleton — avoid paying the cost on import
_private_key = None


def _get_private_key():
    global _private_key
    if _private_key is None:
        _private_key = _load_private_key()
    return _private_key


def sign_command(command: dict) -> dict:
    """Add an RSA-SHA256 signature header to an MQTT command dict.

    1. Serialize the command to JSON (this is what gets signed)
    2. Sign with RSA-SHA256
    3. Add header to the command dict (after signing)
    4. Return the modified dict
    """
    payload_str = json.dumps(command)
    payload_bytes = payload_str.encode("utf-8")

    key = _get_private_key()
    signature = key.sign(payload_bytes, padding.PKCS1v15(), hashes.SHA256())
    signature_b64 = base64.b64encode(signature).decode("ascii")

    cert_id = os.environ.get("BAMBU_APP_CERT_ID", DEFAULT_CERT_ID)

    command["header"] = {
        "sign_ver": "v1.0",
        "sign_alg": "RSA_SHA256",
        "sign_string": signature_b64,
        "cert_id": cert_id,
        "payload_len": len(payload_bytes),
    }

    return command

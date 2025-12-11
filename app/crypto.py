from cryptography.fernet import Fernet
import os

CRYPTO_KEY = os.getenv("CRYPTO_KEY")

def _get_fernet() -> Fernet:
    global CRYPTO_KEY
    if not CRYPTO_KEY:
        CRYPTO_KEY = Fernet.generate_key().decode()
    return Fernet(CRYPTO_KEY.encode())

def encrypt(value: str) -> str:
    f = _get_fernet()
    return f.encrypt(value.encode()).decode()

def decrypt(token: str) -> str:
    f = _get_fernet()
    return f.decrypt(token.encode()).decode()

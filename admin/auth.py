import hashlib
import hmac
import os


def _bcrypt_available() -> bool:
    try:
        from passlib.hash import bcrypt as _b
        _b.hash("test")  # probe
        return True
    except Exception:
        return False


def hash_password(password: str) -> str:
    """Hash password. Uses bcrypt if available, else sha256+salt."""
    if _bcrypt_available():
        from passlib.hash import bcrypt as _b
        return _b.hash(password)
    salt = os.urandom(16).hex()
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"sha256${salt}${h}"


def verify_login(username: str, password: str, expected_username: str, password_hash: str) -> bool:
    if not expected_username or not password_hash:
        return False
    if username != expected_username:
        return False
    if password_hash.startswith("sha256$"):
        _, salt, stored = password_hash.split("$", 2)
        h = hashlib.sha256((salt + password).encode()).hexdigest()
        return hmac.compare_digest(h, stored)
    try:
        from passlib.hash import bcrypt as _b
        return bool(_b.verify(password, password_hash))
    except Exception:
        return False


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m admin hash-password <password>")
        sys.exit(1)
    print(hash_password(sys.argv[1]))

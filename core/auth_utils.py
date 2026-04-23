from argon2 import PasswordHasher

_ph = PasswordHasher()

def hash_password(password: str) -> str:
    """Hash password using Argon2."""
    return _ph.hash(password)

def verify_user_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hashed password."""
    try:
        _ph.verify(hashed_password, plain_password)
        return True
    except Exception:
        return False
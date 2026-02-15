from passlib.context import CryptContext
import re

pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=14, deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def validate_password_strength(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters.")
    if len(password) > 72:
        raise ValueError("Password must not exceed 72 characters.")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lower letter.")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit.")
    if not re.search(r"[@$!%*?#&]", password):
        raise ValueError(
            "Password must contain at least one special character: @, $, !, %, *, ?, #, &."
        )
    return password

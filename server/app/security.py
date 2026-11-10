import time

import bcrypt
import jwt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=10)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(user_id: int, secret: str, days: int = 7) -> str:
    return jwt.encode({"id": user_id, "exp": int(time.time()) + days * 86400}, secret, algorithm="HS256")


def decode_token(token: str, secret: str) -> int:
    """Returns the user id or raises jwt.PyJWTError."""
    return int(jwt.decode(token, secret, algorithms=["HS256"])["id"])

import sqlite3
from typing import Iterator

import jwt
from fastapi import Depends, HTTPException, Request

from .db import connect
from .security import decode_token


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    conn = connect(request.app.state.settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


def current_user(request: Request, db: sqlite3.Connection = Depends(get_db)) -> sqlite3.Row:
    header = request.headers.get("authorization", "")
    token = header.removeprefix("Bearer ").strip()
    try:
        user_id = decode_token(token, request.app.state.settings.jwt_secret)
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(401, "Unauthorized")
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        raise HTTPException(401, "Unauthorized")
    return user


def admin_user(user: sqlite3.Row = Depends(current_user)) -> sqlite3.Row:
    if not user["is_admin"]:
        raise HTTPException(403, "Admins only")
    return user

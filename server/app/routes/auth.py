import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

from ..deps import current_user, get_db
from ..schemas import LoginIn, RegisterIn
from ..security import create_token, hash_password, verify_password

router = APIRouter(prefix="/api", tags=["auth"])

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,28}[a-z0-9]$")
RESERVED = {"api", "admin", "sites", "assets", "static", "www", "health", "metrics"}


def public_user(u: sqlite3.Row) -> dict:
    return {"id": u["id"], "username": u["username"], "email": u["email"], "is_admin": bool(u["is_admin"])}


@router.post("/auth/register", status_code=201)
def register(body: RegisterIn, request: Request, db: sqlite3.Connection = Depends(get_db)):
    settings = request.app.state.settings
    username, email = body.username.lower().strip(), body.email.lower().strip()
    if not USERNAME_RE.match(username) or username in RESERVED:
        raise HTTPException(400, "Username must be 3-30 chars: a-z, 0-9, hyphens (not at the ends).")
    if not re.match(r"^\S+@\S+\.\S+$", email):
        raise HTTPException(400, "Valid email required")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    is_admin = int(bool(settings.admin_email) and email == settings.admin_email.lower())
    try:
        cur = db.execute(
            "INSERT INTO users (username, email, password_hash, is_admin) VALUES (?, ?, ?, ?)",
            (username, email, hash_password(body.password), is_admin),
        )
        db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Username or email already taken")
    user = db.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    return {"token": create_token(user["id"], settings.jwt_secret), "user": public_user(user)}


@router.post("/auth/login")
def login(body: LoginIn, request: Request, db: sqlite3.Connection = Depends(get_db)):
    user = db.execute("SELECT * FROM users WHERE email = ?", (body.email.lower().strip(),)).fetchone()
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    return {"token": create_token(user["id"], request.app.state.settings.jwt_secret), "user": public_user(user)}


@router.get("/me")
def me(user: sqlite3.Row = Depends(current_user)):
    return public_user(user)

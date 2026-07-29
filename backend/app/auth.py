"""
Auth utilities — v6.0: JSON-file credential store, no database, no
self-registration.

Only the emails/passwords listed in `users.json` (next to this backend —
i.e. `backend/users.json` — path overridable via the USERS_FILE env var)
can log in. There is no /auth/register endpoint anymore: to add or remove
a person's access, edit that file directly.

Passwords in users.json can be either:
  - plain text (simplest — just type the password), or
  - a bcrypt hash starting with "$2a$"/"$2b$"/"$2y$", if you'd rather not
    keep plaintext passwords on disk (see generate_password_hash.py)

The file is re-read fresh on every login AND on every authenticated
request — nothing is cached in memory. That means removing a line from
users.json immediately blocks that person, even if they already have a
valid, unexpired token in their browser.

Env vars:
    JWT_SECRET_KEY                required in production
    JWT_ALGORITHM                 default "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES   default 1440 (1 day)
    USERS_FILE                    default "<backend>/users.json"
"""
import os
import json
import datetime as dt
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-insecure-secret-change-me")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24)))

BACKEND_DIR = Path(__file__).resolve().parent.parent  # .../backend
USERS_FILE = Path(os.getenv("USERS_FILE", str(BACKEND_DIR / "users.json")))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _load_users() -> list[dict]:
    if not USERS_FILE.exists():
        raise HTTPException(
            status_code=500,
            detail=(
                f"No users.json found at {USERS_FILE}. Create it with a JSON "
                f"array like [{{\"email\": \"you@example.com\", \"password\": \"...\"}}]."
            ),
        )
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise HTTPException(status_code=500, detail=f"users.json is invalid: {e}")
    if not isinstance(data, list):
        raise HTTPException(
            status_code=500,
            detail="users.json must be a JSON array of {email, password} objects.",
        )
    return data


def _find_user(email: str) -> Optional[dict]:
    email_norm = (email or "").strip().lower()
    for u in _load_users():
        if str(u.get("email", "")).strip().lower() == email_norm:
            return u
    return None


def _check_password(plain_password: str, stored_password: str) -> bool:
    if isinstance(stored_password, str) and stored_password.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            return pwd_context.verify(plain_password, stored_password)
        except Exception:
            return False
    # Plain-text entry in users.json — direct comparison.
    return plain_password == stored_password


def authenticate_user(email: str, password: str) -> Optional[dict]:
    """Returns the matching user dict (from users.json) if credentials are
    valid, else None. Never raises for bad credentials — the caller decides
    how to respond (so failed logins don't leak whether the email exists)."""
    user = _find_user(email)
    if not user:
        return None
    if not _check_password(password, str(user.get("password", ""))):
        return None
    return user


def create_access_token(subject: str, expires_minutes: Optional[int] = None) -> str:
    expire = dt.datetime.utcnow() + dt.timedelta(
        minutes=expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        subject = payload.get("sub")
        if subject is None:
            raise JWTError("missing subject")
        return subject
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """Returns the authenticated user's email (the JWT subject). Re-checks
    users.json on every request — see module docstring for why."""
    email = decode_token(token)
    if _find_user(email) is None:
        raise HTTPException(status_code=401, detail="User no longer exists in users.json")
    return email

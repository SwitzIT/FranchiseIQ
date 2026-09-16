"""Auth routes — v6.0: login only. Credentials come from users.json; there
is no self-registration. Add/remove users by editing that file directly."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.auth import authenticate_user, create_access_token, get_current_user, get_user_record
from app.utils import get_logger

log = get_logger("routes.auth")
router = APIRouter(prefix="/auth", tags=["Auth"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # OAuth2PasswordRequestForm's field is named `username` — we treat it as email.
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(401, "Incorrect email or password.")
    token = create_access_token(subject=user["email"])
    log.info(f"[Auth] login success: {user['email']}")
    return TokenResponse(access_token=token)


@router.get("/me")
def me(current_user: str = Depends(get_current_user)):
    # v9.2 — company/country let the frontend auto-select the user's
    # assigned market and skip the manual country picker on login.
    record = get_user_record(current_user)
    return {
        "email": current_user,
        "company": (record or {}).get("company"),
        "country": (record or {}).get("country"),
    }

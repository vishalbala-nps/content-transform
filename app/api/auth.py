"""Signing in and out, and who is calling.

`current_user` is the one place the API learns who is calling. It is
attached to the whole API router, so a new route is signed-in only unless it
is added here. A single sign-on later means another way to start a session
(or an identity header read here), not a change to any route.

The session travels in an HttpOnly cookie rather than a header, because the
browser's event stream, download links and logo images cannot send headers.
SameSite=Lax keeps the cookie off requests other sites start; the Origin
check below refuses any that still arrive to change data.
"""

import asyncio
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.core import users
from app.core.config import get_settings
from app.db.models import User

COOKIE = "spectra_session"
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


def same_origin(request: Request) -> None:
    """Refuse a data-changing request sent from another site's page.

    Browsers send Origin with every such request; a request without one
    (curl, a script) is not a browser acting for someone else. The origin
    must be this server's own address, or one listed in ALLOWED_ORIGINS for
    a proxy in front that rewrites Host.
    """
    if request.method in SAFE_METHODS:
        return
    origin = request.headers.get("origin")
    if not origin or urlsplit(origin).netloc == request.headers.get("host"):
        return
    if origin.rstrip("/") not in get_settings().allowed_origins:
        raise HTTPException(status_code=403, detail="Request from another site refused.")


def current_user(request: Request, _: Annotated[None, Depends(same_origin)]) -> User:
    token = request.cookies.get(COOKIE)
    user = users.user_for_session(token) if token else None
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    request.state.session_id = users.session_id(token)
    return user


CurrentUser = Annotated[User, Depends(current_user)]

router = APIRouter(prefix="/api/auth", dependencies=[Depends(same_origin)])


class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=1_000)


class PasswordChange(BaseModel):
    current: str = Field(max_length=1_000)
    new: str = Field(min_length=1, max_length=1_000)


class Me(BaseModel):
    email: str


@router.post("/login", response_model=Me)
async def login(creds: Credentials, response: Response) -> Me:
    try:
        # scrypt takes a third of a second: off the event loop.
        user = await asyncio.to_thread(users.authenticate, creds.email, creds.password)
    except users.TooManyAttempts as e:
        raise HTTPException(
            status_code=429, detail=str(e), headers={"Retry-After": str(e.retry_after_s)}
        ) from e
    if user is None:
        # One message for a wrong email and a wrong password.
        raise HTTPException(status_code=401, detail="Wrong email or password.")
    token, expires = users.create_session(user.id)
    settings = get_settings()
    response.set_cookie(
        COOKIE,
        token,
        max_age=int(settings.session_hours * 3600),
        expires=expires,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
    )
    return Me(email=user.email)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response) -> Response:
    if token := request.cookies.get(COOKIE):
        users.end_session(token)
    response = Response(status_code=204)
    response.delete_cookie(COOKIE, path="/")
    return response


@router.get("/me", response_model=Me)
async def me(user: CurrentUser) -> Me:
    return Me(email=user.email)


@router.post("/password", status_code=204)
async def change_password(req: PasswordChange, user: CurrentUser, request: Request) -> Response:
    """Other sessions of this user end; this one stays signed in."""
    ok = await asyncio.to_thread(users.verify_password, req.current, user.password_hash)
    if not ok:
        raise HTTPException(status_code=403, detail="The current password is wrong.")
    if req.new == req.current:
        raise HTTPException(status_code=422, detail="The new password is the same as the current one.")
    await asyncio.to_thread(users.set_password, user.email, req.new, request.state.session_id)
    return Response(status_code=204)

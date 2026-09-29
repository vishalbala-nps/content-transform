"""Users, passwords and sessions.

Users are created from the command line only (`python -m tools.users`);
there is no sign-up and no admin role. Signing in makes a session: a random
token in a cookie, of which only the SHA-256 is stored. How someone signed
in is not recorded on the session, so a single sign-on (an OIDC callback, or
an identity header from a proxy) can later create the same sessions and
nothing that reads them changes.

Passwords are hashed with scrypt from the standard library (no new
dependency), with a random salt per password and the parameters stored in
the hash, so they can be raised later without breaking old hashes.
"""

import base64
import hashlib
import hmac
import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update

from app.core.config import get_settings
from app.db.models import BrandKitRecord, Job, User, UserSession, session

# scrypt at OWASP's recommended cost: 128 MiB and about a third of a second
# per hash, which is what makes a stolen hash slow to guess.
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**17, 8, 1
SCRYPT_MAXMEM = 2**28

# Short passwords are allowed (the command line warns), since policies differ.
RECOMMENDED_PASSWORD_LENGTH = 12

# After this many wrong passwords for one email within the window, sign-in
# for that email is refused until the window has passed. Kept in memory: a
# restart clears it, which is acceptable for slowing down guessing.
MAX_FAILURES = 5
FAILURE_WINDOW_S = 15 * 60


class UserError(Exception):
    pass


def normalise_email(email: str) -> str:
    email = email.strip().lower()
    local, _, domain = email.partition("@")
    if not local or "." not in domain or " " in email:
        raise UserError(f"{email!r} is not an email address.")
    return email


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, maxmem=SCRYPT_MAXMEM
    )
    b64 = base64.b64encode
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${b64(salt).decode()}${b64(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    expected = base64.b64decode(digest)
    actual = hashlib.scrypt(
        password.encode(),
        salt=base64.b64decode(salt),
        n=int(n),
        r=int(r),
        p=int(p),
        maxmem=SCRYPT_MAXMEM,
        dklen=len(expected),
    )
    return hmac.compare_digest(actual, expected)


# Checked against when the email is unknown, so a wrong email takes as long
# to refuse as a wrong password and the timing does not say which it was.
_DUMMY_HASH: str | None = None


def _dummy_hash() -> str:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password(secrets.token_hex(8))
    return _DUMMY_HASH


# --- Users (the command line) --------------------------------------------------


def get_user_by_email(email: str) -> User | None:
    with session() as s:
        return s.scalar(select(User).where(User.email == normalise_email(email)))


def create_user(email: str, password: str) -> User:
    email = normalise_email(email)
    if not password:
        raise UserError("The password is empty.")
    if get_user_by_email(email):
        raise UserError(f"{email} already has an account.")
    user = User(id=uuid.uuid4().hex, email=email, password_hash=hash_password(password), active=True)
    with session() as s:
        s.add(user)
        s.commit()
    return user


def list_users() -> list[User]:
    with session() as s:
        return list(s.scalars(select(User).order_by(User.created_at)))


def _require(email: str) -> User:
    user = get_user_by_email(email)
    if user is None:
        raise UserError(f"No account for {normalise_email(email)}.")
    return user


def set_password(email: str, password: str, keep_session: str | None = None) -> None:
    """Changing a password signs the user out everywhere else."""
    if not password:
        raise UserError("The password is empty.")
    user = _require(email)
    with session() as s:
        s.execute(update(User).where(User.id == user.id).values(password_hash=hash_password(password)))
        s.commit()
    end_sessions(user.id, keep=keep_session)


def set_active(email: str, active: bool) -> None:
    """A disabled user is signed out at once and cannot sign in."""
    user = _require(email)
    with session() as s:
        s.execute(update(User).where(User.id == user.id).values(active=active))
        s.commit()
    if not active:
        end_sessions(user.id)


def adopt_unowned(email: str) -> tuple[int, int]:
    """Give every job and brand kit with no owner to this user. Rows from
    before users existed have none. Returns (jobs, kits) adopted."""
    user = _require(email)
    with session() as s:
        jobs = s.execute(update(Job).where(Job.user_id.is_(None)).values(user_id=user.id)).rowcount
        kits = s.execute(
            update(BrandKitRecord).where(BrandKitRecord.user_id.is_(None)).values(user_id=user.id)
        ).rowcount
        s.commit()
    return jobs, kits


# --- Signing in ------------------------------------------------------------------

_failures: dict[str, list[float]] = {}


def _recent_failures(email: str) -> list[float]:
    cutoff = time.monotonic() - FAILURE_WINDOW_S
    recent = [t for t in _failures.get(email, []) if t > cutoff]
    _failures[email] = recent
    return recent


class TooManyAttempts(Exception):
    def __init__(self, retry_after_s: int):
        super().__init__(f"Too many failed sign-ins. Try again in {retry_after_s // 60 + 1} minutes.")
        self.retry_after_s = retry_after_s


def authenticate(email: str, password: str) -> User | None:
    """The user, if the email and password match an active account.

    Slow on purpose (scrypt): call it off the event loop.
    """
    try:
        email = normalise_email(email)
    except UserError:
        return None
    recent = _recent_failures(email)
    if len(recent) >= MAX_FAILURES:
        raise TooManyAttempts(int(recent[0] + FAILURE_WINDOW_S - time.monotonic()))
    user = get_user_by_email(email)
    ok = verify_password(password, user.password_hash if user else _dummy_hash())
    if not (ok and user and user.active):
        _failures[email] = [*recent, time.monotonic()]
        return None
    _failures.pop(email, None)
    return user


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user_id: str) -> tuple[str, datetime]:
    """A new session's token, for the cookie, and when it expires."""
    token = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(hours=get_settings().session_hours)
    with session() as s:
        s.add(UserSession(token_hash=_token_hash(token), user_id=user_id, expires_at=expires))
        # Expired sessions are cleared here rather than by a timer.
        s.execute(delete(UserSession).where(UserSession.expires_at < datetime.now(UTC)))
        s.commit()
    return token, expires


def user_for_session(token: str) -> User | None:
    """The signed-in user, if the token is a live session of an active user."""
    with session() as s:
        record = s.get(UserSession, _token_hash(token))
        if record is None:
            return None
        expires = record.expires_at
        # SQLite hands back naive datetimes; they were stored as UTC.
        if (expires if expires.tzinfo else expires.replace(tzinfo=UTC)) < datetime.now(UTC):
            return None
        user = s.get(User, record.user_id)
        return user if user and user.active else None


def session_id(token: str) -> str:
    return _token_hash(token)


def end_session(token: str) -> None:
    with session() as s:
        s.execute(delete(UserSession).where(UserSession.token_hash == _token_hash(token)))
        s.commit()


def end_sessions(user_id: str, keep: str | None = None) -> None:
    """Sign a user out everywhere, except the session whose id is `keep`."""
    with session() as s:
        query = delete(UserSession).where(UserSession.user_id == user_id)
        if keep:
            query = query.where(UserSession.token_hash != keep)
        s.execute(query)
        s.commit()

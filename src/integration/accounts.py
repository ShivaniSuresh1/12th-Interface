"""Accounts: email + password with a 6-digit code, and where profiles are stored.

Two interchangeable setups, picked by frontend/app.py from Streamlit secrets:

- Production (secrets has [supabase]): Supabase Auth sends the 6-digit code
  by email and checks passwords; profiles live in a Supabase table, so they
  survive the app restarting. Google sign-in is Streamlit's own st.login
  (secrets [auth]); it ends up at the same profile table, keyed by email.
- Local / tests (no secrets): `LocalAuth` keeps hashed passwords in a JSON
  file and shows the code on screen instead of emailing it, and profiles are
  JSON files (`storage.ProfileStore`). Same flow, nothing to set up.

The Supabase client is imported lazily, so the core package and CI don't
need it installed.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .dashboard import DashboardSession, now_local
from .storage import student_id_for

MIN_PASSWORD = 8
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthError(Exception):
    """Something the person can fix; the message is shown as-is."""


class NeedsVerification(AuthError):
    """The account exists but its email hasn't been confirmed with the code yet."""


def normalize_email(email: str) -> str:
    email = email.strip().lower()
    if not _EMAIL.match(email):
        raise AuthError("Enter a valid email address, like name@tamu.edu.")
    return email


def check_password(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise AuthError(f"Use at least {MIN_PASSWORD} characters for your password.")


def student_id_for_email(email: str) -> str:
    return student_id_for(normalize_email(email))


# -- local (dev + tests) ----------------------------------------------------------


def _hash(password: str, salt: bytes) -> str:
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1).hex()


class LocalAuth:
    """Email/password accounts in a JSON file. The code is returned, not emailed."""

    sends_real_email = False

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, accounts: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(accounts, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def sign_up(self, email: str, password: str) -> str:
        email = normalize_email(email)
        check_password(password)
        accounts = self._load()
        if email in accounts and accounts[email]["verified"]:
            raise AuthError("That email already has an account. Sign in instead.")
        salt = secrets.token_bytes(16)
        code = f"{secrets.randbelow(10**6):06d}"
        accounts[email] = {
            "salt": salt.hex(),
            "hash": _hash(password, salt),
            "verified": False,
            "code": code,
        }
        self._save(accounts)
        return code

    def verify(self, email: str, code: str) -> None:
        email = normalize_email(email)
        accounts = self._load()
        account = accounts.get(email)
        if account is None:
            raise AuthError("No sign-up found for that email. Create an account first.")
        if not hmac.compare_digest(account.get("code") or "", code.strip()):
            raise AuthError("That code doesn't match. Check it and try again.")
        account.update(verified=True, code=None)
        self._save(accounts)

    def resend(self, email: str) -> str:
        email = normalize_email(email)
        accounts = self._load()
        if email not in accounts:
            raise AuthError("No sign-up found for that email. Create an account first.")
        code = f"{secrets.randbelow(10**6):06d}"
        accounts[email]["code"] = code
        self._save(accounts)
        return code

    def sign_in(self, email: str, password: str) -> str:
        email = normalize_email(email)
        account = self._load().get(email)
        wrong = AuthError("Email or password is incorrect.")
        if account is None:
            raise wrong
        if not hmac.compare_digest(account["hash"], _hash(password, bytes.fromhex(account["salt"]))):
            raise wrong
        if not account["verified"]:
            raise NeedsVerification("Confirm your email first. We've sent you a new code.")
        return email


# -- Supabase (production) --------------------------------------------------------


def _supabase(url: str, key: str):
    from supabase import create_client  # lazy: only needed when deployed

    return create_client(url, key)


def _message(exc: Exception) -> str:
    text = str(exc) or exc.__class__.__name__
    lowered = text.lower()
    if "already registered" in lowered or "already been registered" in lowered:
        return "That email already has an account. Sign in instead."
    if "invalid login credentials" in lowered:
        return "Email or password is incorrect."
    if "expired" in lowered or ("invalid" in lowered and "token" in lowered):
        return "That code is wrong or has expired. Request a new one."
    if "rate limit" in lowered or "security purposes" in lowered:
        return "Too many attempts. Wait a minute, then try again."
    return text


class SupabaseAuth:
    """Supabase Auth: the 6-digit code arrives by email (template uses {{ .Token }})."""

    sends_real_email = True

    def __init__(self, url: str, anon_key: str, client_factory: Callable = _supabase) -> None:
        self.url, self.anon_key, self._factory = url, anon_key, client_factory

    def _client(self):
        # A fresh client per call: Supabase clients hold a session, and this
        # server is shared by everyone using the site.
        return self._factory(self.url, self.anon_key)

    def sign_up(self, email: str, password: str) -> None:
        email = normalize_email(email)
        check_password(password)
        try:
            self._client().auth.sign_up({"email": email, "password": password})
        except Exception as exc:  # Supabase raises several error types
            raise AuthError(_message(exc)) from exc

    def verify(self, email: str, code: str) -> None:
        email = normalize_email(email)
        try:
            self._client().auth.verify_otp({"email": email, "token": code.strip(), "type": "email"})
        except Exception as exc:  # Supabase raises several error types
            raise AuthError(_message(exc)) from exc

    def resend(self, email: str) -> None:
        try:
            self._client().auth.resend({"type": "signup", "email": normalize_email(email)})
        except Exception as exc:  # Supabase raises several error types
            raise AuthError(_message(exc)) from exc

    def sign_in(self, email: str, password: str) -> str:
        email = normalize_email(email)
        try:
            self._client().auth.sign_in_with_password({"email": email, "password": password})
        except Exception as exc:  # Supabase raises several error types
            if "not confirmed" in str(exc).lower():
                self.resend(email)
                raise NeedsVerification(
                    "Confirm your email first. We've sent you a new code."
                ) from exc
            raise AuthError(_message(exc)) from exc
        return email


class SupabaseStore:
    """Profiles in a Supabase table (see DEPLOY.md for the SQL). Same API as ProfileStore."""

    def __init__(
        self,
        url: str,
        service_key: str,
        table: str = "student_profiles",
        client_factory: Callable = _supabase,
    ) -> None:
        self._db = client_factory(url, service_key)
        self.table = table

    def exists(self, student_id: str) -> bool:
        rows = (
            self._db.table(self.table).select("student_id").eq("student_id", student_id)
            .limit(1).execute().data
        )
        return bool(rows)

    def save(self, session: DashboardSession) -> None:
        self._db.table(self.table).upsert(
            {
                "student_id": session.student_id,
                "email": session.email or None,
                "data": session.to_dict(),
                "updated_at": datetime.now().astimezone().isoformat(),
            }
        ).execute()

    def load(
        self, student_id: str, clock: Callable[[], datetime] = now_local
    ) -> DashboardSession:
        rows = (
            self._db.table(self.table).select("data").eq("student_id", student_id)
            .limit(1).execute().data
        )
        if not rows:
            raise KeyError(student_id)
        return DashboardSession.from_dict(rows[0]["data"], clock=clock)

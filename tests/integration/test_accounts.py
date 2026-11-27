"""Accounts: local email/password + code, and the Supabase adapters (with fakes)."""

from datetime import time
from types import SimpleNamespace
from typing import ClassVar

import pytest

from domain_model import TaskType
from integration.accounts import (
    AuthError,
    LocalAuth,
    NeedsVerification,
    SupabaseAuth,
    SupabaseStore,
    normalize_email,
    student_id_for_email,
)
from integration.dashboard import DashboardSession

# -- LocalAuth ----------------------------------------------------------------------


@pytest.fixture
def auth(tmp_path):
    return LocalAuth(tmp_path / "_accounts.json")


def test_sign_up_verify_sign_in(auth):
    code = auth.sign_up("Priya@TAMU.edu ", "correct horse")
    assert len(code) == 6 and code.isdigit()
    auth.verify("priya@tamu.edu", code)
    assert auth.sign_in("priya@tamu.edu", "correct horse") == "priya@tamu.edu"


def test_wrong_code_is_rejected(auth):
    code = auth.sign_up("a@b.co", "password1")
    with pytest.raises(AuthError, match="doesn't match"):
        auth.verify("a@b.co", "000000" if code != "000000" else "111111")


def test_unverified_account_must_confirm_first(auth):
    auth.sign_up("a@b.co", "password1")
    with pytest.raises(NeedsVerification):
        auth.sign_in("a@b.co", "password1")


def test_wrong_password_is_vague_on_purpose(auth):
    auth.verify("a@b.co", auth.sign_up("a@b.co", "password1"))
    for email, pw in (("a@b.co", "nope-nope"), ("x@y.co", "password1")):
        with pytest.raises(AuthError, match="incorrect"):
            auth.sign_in(email, pw)


def test_cannot_sign_up_twice(auth):
    auth.verify("a@b.co", auth.sign_up("a@b.co", "password1"))
    with pytest.raises(AuthError, match="already has an account"):
        auth.sign_up("a@b.co", "password2")


def test_resend_replaces_the_code(auth):
    first = auth.sign_up("a@b.co", "password1")
    second = auth.resend("a@b.co")
    if first != second:
        with pytest.raises(AuthError):
            auth.verify("a@b.co", first)
    auth.verify("a@b.co", second)


def test_passwords_are_not_stored_in_plain_text(auth, tmp_path):
    auth.sign_up("a@b.co", "password1")
    assert "password1" not in (tmp_path / "_accounts.json").read_text()


@pytest.mark.parametrize("bad", ["", "nope", "a@b", "a b@c.co"])
def test_email_must_look_like_an_email(bad):
    with pytest.raises(AuthError):
        normalize_email(bad)


def test_short_passwords_are_rejected(auth):
    with pytest.raises(AuthError, match="at least"):
        auth.sign_up("a@b.co", "short")


def test_student_id_from_email():
    assert student_id_for_email(" Priya@TAMU.edu") == "priya-tamu-edu"


# -- Supabase adapters, with a fake client -----------------------------------------------


class FakeSupabaseError(Exception):
    """Stands in for supabase_auth.errors.AuthApiError."""


class FakeAuthApi:
    def __init__(self, fail=None):
        self.calls, self.fail = [], fail

    def _call(self, name, payload):
        self.calls.append((name, payload))
        if self.fail:
            raise FakeSupabaseError(self.fail)
        return SimpleNamespace(user=None, session=None)

    def sign_up(self, c):
        return self._call("sign_up", c)

    def verify_otp(self, p):
        return self._call("verify_otp", p)

    def resend(self, c):
        return self._call("resend", c)

    def sign_in_with_password(self, c):
        return self._call("sign_in", c)


def _supabase_auth(api):
    return SupabaseAuth("https://x.supabase.co", "anon", client_factory=lambda u, k: SimpleNamespace(auth=api))


def test_supabase_auth_calls():
    api = FakeAuthApi()
    a = _supabase_auth(api)
    a.sign_up("A@b.co", "password1")
    a.verify("a@b.co", " 123456 ")
    assert a.sign_in("a@b.co", "password1") == "a@b.co"
    assert api.calls[0] == ("sign_up", {"email": "a@b.co", "password": "password1"})
    assert api.calls[1] == ("verify_otp", {"email": "a@b.co", "token": "123456", "type": "email"})


def test_supabase_errors_become_plain_messages():
    a = _supabase_auth(FakeAuthApi(fail="Invalid login credentials"))
    with pytest.raises(AuthError, match="incorrect"):
        a.sign_in("a@b.co", "password1")


def test_supabase_unconfirmed_email_resends_the_code():
    class Api(FakeAuthApi):
        def sign_in_with_password(self, c):
            raise FakeSupabaseError("Email not confirmed")

    api = Api()
    with pytest.raises(NeedsVerification):
        _supabase_auth(api).sign_in("a@b.co", "password1")
    assert api.calls == [("resend", {"type": "signup", "email": "a@b.co"})]


class FakeTable:
    rows: ClassVar[dict] = {}

    def __init__(self):
        self._filter = None
        self._upsert = None

    def select(self, _cols):
        return self

    def eq(self, _col, value):
        self._filter = value
        return self

    def limit(self, _n):
        return self

    def upsert(self, row):
        self._upsert = row
        return self

    def execute(self):
        if self._upsert:
            FakeTable.rows[self._upsert["student_id"]] = self._upsert
            return SimpleNamespace(data=[self._upsert])
        row = FakeTable.rows.get(self._filter)
        return SimpleNamespace(data=[row] if row else [])


def test_supabase_store_round_trip():
    FakeTable.rows = {}
    db = SimpleNamespace(table=lambda name: FakeTable())
    store = SupabaseStore("https://x.supabase.co", "service", client_factory=lambda u, k: db)
    session = DashboardSession.onboard(
        "priya-tamu-edu", "Priya", 7.0, time(7, 30),
        {"low": TaskType.READING, "medium": None, "high": None},
        email="priya@tamu.edu",
    )
    assert not store.exists("priya-tamu-edu")
    store.save(session)
    assert store.exists("priya-tamu-edu")
    assert FakeTable.rows["priya-tamu-edu"]["email"] == "priya@tamu.edu"
    loaded = store.load("priya-tamu-edu", clock=session.clock)
    assert loaded.name == "Priya" and loaded.email == "priya@tamu.edu"
    with pytest.raises(KeyError):
        store.load("nobody")

"""Click through the Streamlit dashboard headlessly, in local dev-auth mode (no secrets).
Skipped if streamlit isn't installed (CI installs only the core requirements); run
locally after `pip install -r frontend/requirements.txt`."""

import re
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("plotly")

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[2] / "frontend" / "app.py")
PAGES = ["Home", "My Schedule", "Insights", "Study Mode", "Replanning"]
EMAIL, PASSWORD = "priya@tamu.edu", "correct horse"


@pytest.fixture(autouse=True)
def _temp_profiles(tmp_path, monkeypatch):
    monkeypatch.setenv("TWELFTH_PROFILE_DIR", str(tmp_path))


def _start():
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert not at.exception
    return at


def _click(at, label):
    labels = [b.label for b in at.button]
    assert label in labels, labels
    at.button[labels.index(label)].click().run()
    assert not at.exception


SLUGS = {"Home": "home", "My Schedule": "schedule", "Insights": "insights", "Study Mode": "study",
         "Replanning": "replan"}


def _go(at, page):
    """Sidebar navigation: each section is its own page with its own URL."""
    at.sidebar.button(key=f"nav_{SLUGS[page]}").click().run()
    assert not at.exception


def _dev_code(at):
    text = " ".join(i.value for i in at.info)
    return re.search(r"\b(\d{6})\b", text).group(1)


def _signed_up(email=EMAIL, password=PASSWORD):
    at = _start()
    _click(at, "Get started")
    at.text_input[0].set_value(email)
    at.text_input[1].set_value(password)
    _click(at, "Create account")
    at.text_input[0].set_value(_dev_code(at))
    _click(at, "Verify email")
    at.text_input[0].set_value("Priya")
    _click(at, "Continue")  # setup 1: name
    _click(at, "Continue")  # setup 2: sleep (defaults)
    at.selectbox(key="pref_low").set_value(at.selectbox(key="pref_low").options[4])
    _click(at, "Create my plan")  # setup 3: preferences
    return at


def test_landing_comes_first_and_hides_the_app():
    at = _start()
    labels = [b.label for b in at.button]
    assert "Get started" in labels and "Sign in" in labels
    assert len(at.sidebar.radio) == 0


def test_google_button_is_off_without_secrets():
    at = _start()
    _click(at, "Get started")
    google = at.button(key="google")
    assert google.disabled


def test_sign_up_with_email_code_then_setup(tmp_path):
    at = _signed_up()
    assert any("You're set up" in s.value for s in at.success)
    assert any("Priya" in m.value for m in at.markdown)
    assert (tmp_path / "priya-tamu-edu.json").exists()
    assert "correct horse" not in (tmp_path / "_accounts.json").read_text()


def test_wrong_code_is_rejected():
    at = _start()
    _click(at, "Get started")
    at.text_input[0].set_value(EMAIL)
    at.text_input[1].set_value(PASSWORD)
    _click(at, "Create account")
    code = _dev_code(at)
    at.text_input[0].set_value("000000" if code != "000000" else "111111")
    _click(at, "Verify email")
    assert any("doesn't match" in w.value for w in at.warning)


def test_short_password_is_rejected():
    at = _start()
    _click(at, "Get started")
    at.text_input[0].set_value(EMAIL)
    at.text_input[1].set_value("short")
    _click(at, "Create account")
    assert any("at least" in w.value for w in at.warning)


def test_sign_in_continues_where_you_left_off():
    first = _signed_up()
    first.radio(key="home_feeling").set_value("Tired").run()
    _click(first, "Log check-in")
    at = _start()
    _click(at, "Sign in")
    at.text_input[0].set_value(EMAIL)
    at.text_input[1].set_value(PASSWORD)
    _click(at, "Sign in")
    assert any("Tired" in s.value for s in at.success)


def test_wrong_password():
    _signed_up()
    at = _start()
    _click(at, "Sign in")
    at.text_input[0].set_value(EMAIL)
    at.text_input[1].set_value("not the password")
    _click(at, "Sign in")
    assert any("incorrect" in w.value for w in at.warning)


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders(page):
    at = _signed_up()
    _go(at, page)
    assert not at.exception


def test_ask_flow_end_to_end():
    at = _signed_up()
    _go(at, "Replanning")
    at.selectbox[0].set_value("Something else came up").run()
    _click(at, "Suggest a new plan")
    at.text_input[0].set_value("honestly I'm wiped, 20 minutes max")
    _click(at, "Tell the planner")
    assert any("20 minutes" in s.value for s in at.success)


def test_sign_out_returns_to_landing():
    at = _signed_up()
    _click(at, "Sign out")
    assert "Get started" in [b.label for b in at.button]


def test_new_students_start_with_an_empty_schedule_and_the_assistant():
    at = _signed_up()
    assert not any("sample" in s.value for s in at.success)
    _go(at, "My Schedule")
    assert any("build your week" in m.markdown[0].value for m in at.chat_message)


def test_chat_builds_the_week_end_to_end():
    at = _signed_up()
    _go(at, "My Schedule")
    for text in ["CSCE 634 MWF 10:20-11:10", "done", "IUI final report due in 5 days 3 hours",
                 "stats homework due tomorrow 2h"]:
        at.chat_input[0].set_value(text).run()
        assert not at.exception
    said = [m.markdown[0].value for m in at.chat_message]
    assert any("Blocked your class" in s for s in said)
    assert sum("Added" in s for s in said) >= 1
    _click(at, "Plan my week")  # jumps to the Week view
    assert at.radio(key="sched_view").value == "Week"
    for view in ["Day", "Week"]:
        at.radio(key="sched_view").set_value(view).run()
        assert not at.exception
    _go(at, "Insights")
    assert not at.exception
    assert any("Deadlines" in m.value for m in at.markdown)


@pytest.mark.parametrize(("page", "heading"), [
    ("My Schedule", "My schedule"), ("Insights", "Insights"), ("Study Mode", "Ready to focus?"),
    ("Replanning", "Something changed?"), ("Home", "Good "),
])
def test_each_section_is_its_own_page(page, heading):
    at = _signed_up()
    _go(at, page)
    assert any(heading in m.value for m in at.markdown)
    here = next(b for b in at.sidebar.button if b.key == f"nav_{SLUGS[page]}")
    assert here.proto.type == "primary"  # the current page is highlighted


def test_sign_out_from_a_sub_page_returns_to_landing():
    at = _signed_up()
    _go(at, "Insights")
    _click(at, "Sign out")
    assert "Get started" in [b.label for b in at.button]

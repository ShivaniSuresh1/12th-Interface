"""Click through the Streamlit dashboard headlessly. Skipped if streamlit isn't installed
(CI installs only the core requirements); run locally after
`pip install -r frontend/requirements.txt`."""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("plotly")

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[2] / "frontend" / "app.py")
PAGES = ["Home", "My Schedule", "Insights", "Study Mode", "Replanning"]


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


def _signed_up(name="Priya"):
    at = _start()
    _click(at, "Get started")
    at.text_input[0].set_value(name)
    _click(at, "Continue")  # step 1: name
    _click(at, "Continue")  # step 2: sleep (defaults)
    at.selectbox(key="pref_low").set_value(at.selectbox(key="pref_low").options[4])
    _click(at, "Create my plan")  # step 3: preferences
    return at


def test_landing_comes_first():
    at = _start()
    labels = [b.label for b in at.button]
    assert "Get started" in labels and "Sign in" in labels
    assert len(at.sidebar.radio) == 0  # no dashboard until signed in


def test_get_started_walks_three_steps(tmp_path):
    at = _signed_up()
    assert any("You're set up" in s.value for s in at.success)
    assert any("Priya" in m.value for m in at.markdown)
    assert (tmp_path / "priya.json").exists()


def test_back_goes_to_the_previous_step():
    at = _start()
    _click(at, "Get started")
    at.text_input[0].set_value("Sam")
    _click(at, "Continue")
    _click(at, "Back")
    assert at.text_input[0].value == "Sam"


def test_name_must_be_new():
    _signed_up()
    at = _start()
    _click(at, "Get started")
    at.text_input[0].set_value("priya")
    _click(at, "Continue")
    assert any("already has a profile" in w.value for w in at.warning)


def test_sign_in_continues_where_you_left_off():
    first = _signed_up()
    first.radio(key="home_feeling").set_value("Tired").run()
    _click(first, "Log check-in")
    at = _start()
    _click(at, "Sign in")
    at.text_input[0].set_value("Priya")
    _click(at, "Sign in")
    assert any("Tired" in s.value for s in at.success)


def test_unknown_name_is_not_found():
    at = _start()
    _click(at, "Sign in")
    at.text_input[0].set_value("nobody")
    _click(at, "Sign in")
    assert any("No profile" in w.value for w in at.warning)


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders(page):
    at = _signed_up()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception


def test_ask_flow_end_to_end():
    at = _signed_up()
    at.sidebar.radio[0].set_value("Replanning").run()
    at.selectbox[0].set_value("Something else came up").run()
    _click(at, "Suggest a new plan")
    at.text_input[0].set_value("honestly I'm wiped, 20 minutes max")
    _click(at, "Tell the planner")
    assert any("20 minutes" in s.value for s in at.success)


def test_sign_out_returns_to_landing():
    at = _signed_up()
    _click(at, "Sign out")
    assert "Get started" in [b.label for b in at.button]

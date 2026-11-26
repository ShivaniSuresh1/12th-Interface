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


def _click(at, label):
    at.button[[b.label for b in at.button].index(label)].click().run()
    assert not at.exception


def _onboarded(name="Priya"):
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert not at.exception
    at.text_input[0].set_value(name)
    at.selectbox(key="pref_low").set_value(at.selectbox(key="pref_low").options[4])
    _click(at, "Start planning")
    return at


def test_new_user_sees_onboarding_first():
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["I'm new here", "I've been here before"]
    assert len(at.sidebar.radio) == 0  # no dashboard until onboarded


def test_onboarding_leads_to_a_personal_dashboard(tmp_path):
    at = _onboarded()
    assert any("You're all set" in s.value for s in at.success)
    assert any("Priya" in m.value for m in at.markdown)
    assert (tmp_path / "priya.json").exists()


def test_name_must_be_new():
    _onboarded()
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    at.text_input[0].set_value("priya")
    _click(at, "Start planning")
    assert any("already saved" in w.value for w in at.warning)


def test_returning_student_continues():
    first = _onboarded()
    first.radio(key="home_feeling").set_value("Tired").run()
    _click(first, "Update my energy")
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    at.text_input[1].set_value("Priya")
    _click(at, "Continue")
    assert any("Tired" in s.value for s in at.success)


def test_unknown_returning_name_is_not_found():
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    at.text_input[1].set_value("nobody")
    _click(at, "Continue")
    assert any("couldn't find" in w.value for w in at.warning)


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders(page):
    at = _onboarded()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception


def test_ask_flow_end_to_end():
    at = _onboarded()
    at.sidebar.radio[0].set_value("Replanning").run()
    at.selectbox[0].set_value("Something else came up").run()
    _click(at, "Suggest a new plan")
    at.text_input[0].set_value("honestly I'm wiped, 20 minutes max")
    _click(at, "Tell the planner")
    assert any("20 minutes" in s.value for s in at.success)

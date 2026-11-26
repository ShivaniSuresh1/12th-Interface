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


def _app():
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert not at.exception
    return at


def _click(at, label):
    at.button[[b.label for b in at.button].index(label)].click().run()
    assert not at.exception


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders(page):
    at = _app()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception


def test_checkin_updates_the_energy_shown():
    at = _app()
    at.radio(key="home_feeling").set_value("Tired").run()
    _click(at, "Update my energy")
    assert any("Tired" in s.value for s in at.success)


def test_ask_flow_end_to_end():
    at = _app()
    at.sidebar.radio[0].set_value("Replanning").run()
    at.selectbox[0].set_value("Something else came up").run()
    _click(at, "Suggest a new plan")
    at.text_input[0].set_value("honestly I'm wiped, 20 minutes max")
    _click(at, "Tell the planner")
    assert any("20 minutes" in s.value for s in at.success)

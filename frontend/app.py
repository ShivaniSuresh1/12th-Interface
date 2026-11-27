"""The 12th Interface: student dashboard (Streamlit), wired to the live planner.

Run from the repo root:

    pip install -r frontend/requirements.txt
    streamlit run frontend/app.py

Every number, recommendation, "why" and replan comes from StudySessionPlanner
through integration.dashboard.DashboardSession. Accounts come from
integration.accounts: Supabase + Google when secrets are set (see DEPLOY.md),
otherwise a local dev mode that shows the email code on screen.

Visual idea: a signal. The outside (landing and sign-in) is an electric-blue
field with the day's energy drawn as a white signal line over a faint grid,
plus a terminal-style day log. Inside, a cool white workspace with a blue
sidebar; energy keeps one scale everywhere (blue low, violet moderate,
orange high).
"""

import math
import os
import sys
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

# Let `streamlit run frontend/app.py` find the src/ packages without PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain_model import TaskType
from integration.accounts import (
    AuthError,
    LocalAuth,
    NeedsVerification,
    SupabaseAuth,
    SupabaseStore,
    student_id_for_email,
)
from integration.dashboard import DISRUPTIONS, FEELINGS, DashboardSession
from integration.storage import ProfileStore
from user_model.survey import MAX_SURVEY_SLEEP_HOURS

st.set_page_config(
    page_title="The 12th Interface",
    page_icon="🌙",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==========================================================
# TOKENS
# ==========================================================

SIGNAL = "#0000F2"  # electric blue: the brand field
SIGNAL_DEEP = "#0000B8"
PAPER = "#F3F4FB"  # cool white workspace
CARD = "#FFFFFF"
INK = "#0B0B3B"  # deep blue-black text
MUTED = "#5B5F8A"
LINE = "#DADDF0"
LOW = "#3D49FF"  # energy scale
MID = "#8A5CFF"
HIGH = "#FF7A2F"

TASK_TINT = {"problem_set": HIGH, "review": MID, "reading": "#2FA8FF", "memorization": "#C04CFF"}


def energy_color(pct: int) -> str:
    """Same cut points as the planner (33% / 66%)."""
    return LOW if pct < 33 else MID if pct < 66 else HIGH


st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..800&family=JetBrains+Mono:wght@400;600&display=swap');

/* hide Streamlit's own chrome: this is a product, not a notebook */
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"],
#MainMenu, footer, [data-testid="stAppDeployButton"] {{ display: none !important; }}
[data-testid="stHeader"] {{ background: transparent; height: 2.5rem; }}

html, body, [data-testid="stAppViewContainer"] {{
    font-family: 'Archivo', system-ui, sans-serif; color: {INK};
}}
[data-testid="stAppViewContainer"] {{
    background: radial-gradient(circle, rgba(11,11,59,.07) 1px, transparent 1.2px) 0 0/22px 22px, {PAPER};
}}
[data-testid="stMainBlockContainer"] {{ max-width: 1180px; padding-top: 2rem; }}
p, li, label {{ font-size: 16px; line-height: 1.55; }}

.wide, .hello, .form-title, .section, .task, .big, .brand {{
    font-family: 'Archivo', sans-serif !important; font-stretch: 125%;
}}
.mono, .t {{ font-family: 'JetBrains Mono', ui-monospace, monospace !important; }}

/* ---------- buttons ---------- */
.stButton > button, .stFormSubmitButton > button, .stLinkButton > a {{
    border-radius: 12px; font-weight: 600; padding: 0.6rem 1.2rem;
    border: 1.5px solid {LINE}; background: {CARD}; color: {INK};
}}
.stButton > button[kind^="primary"], .stFormSubmitButton > button[kind^="primary"] {{
    background: {SIGNAL}; color: #fff; border-color: {SIGNAL};
}}
.stButton > button[kind^="primary"]:hover, .stFormSubmitButton > button[kind^="primary"]:hover {{
    background: {SIGNAL_DEEP}; border-color: {SIGNAL_DEEP}; color: #fff;
}}
.stButton > button[kind="tertiary"] {{
    border: none; background: transparent; color: {SIGNAL}; padding: .2rem 0; font-weight: 600;
}}
.stButton > button[kind="tertiary"] p {{ color: {SIGNAL}; }}
button:focus-visible {{ outline: 3px solid {HIGH} !important; outline-offset: 2px; }}
[data-testid="stForm"] {{ border: none; padding: 0; }}

/* radios: no circles. Sidebar = navigation list, home = pills */
[data-testid="stRadioOption"] > div > div:first-child:not([data-testid]) {{ display: none; }}

/* ---------- sidebar (signed in) ---------- */
[data-testid="stSidebar"] {{
    background:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 300 300'%3E%3Cg fill='none' stroke='white' stroke-opacity='.18'%3E%3Ccircle cx='150' cy='300' r='90'/%3E%3Ccircle cx='150' cy='300' r='140' stroke-dasharray='2 8'/%3E%3Ccircle cx='150' cy='300' r='190'/%3E%3C/g%3E%3Ccircle cx='62' cy='232' r='6' fill='%23FF7A2F'/%3E%3C/svg%3E") bottom / 100% auto no-repeat,
        {SIGNAL};
    border-right: none;
}}
[data-testid="stSidebar"] * {{ color: #fff; }}
[data-testid="stSidebar"] [data-testid="stRadioOption"] {{
    padding: 10px 14px; border-radius: 10px; width: 100%; margin-bottom: 2px;
}}
[data-testid="stSidebar"] [data-testid="stRadioOption"] p {{ font-weight: 600; opacity: .72; }}
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] {{ background: rgba(255,255,255,.14); }}
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] p {{ opacity: 1; }}
[data-testid="stSidebar"] [data-testid="stNumberInput"] input,
[data-testid="stSidebar"] [data-testid="stNumberInput"] button,
[data-testid="stSidebar"] [data-testid="stNumberInput"] svg {{
    color: {INK} !important; -webkit-text-fill-color: {INK}; fill: {INK};
}}
[data-testid="stSidebar"] .stButton > button {{ background: transparent; border-color: rgba(255,255,255,.4); }}
.brand {{ font-weight: 800; font-size: 19px; letter-spacing: -0.01em; }}
.brand-sub {{ opacity: .7; font-size: 14px; margin: 2px 0 20px 0; }}
.who {{ display: flex; gap: 10px; align-items: center; padding: 12px; border-radius: 14px;
        background: rgba(255,255,255,.1); margin: 10px 0 14px 0; }}
.who .dot {{ width: 32px; height: 32px; border-radius: 50%; display: grid; place-items: center;
             font-weight: 800; background: #fff; color: {SIGNAL} !important; }}
.who .n {{ font-weight: 700; }}
.who .s {{ font-size: 13px; opacity: .75; }}

/* ---------- workspace ---------- */
.hello {{ font-size: clamp(30px, 4vw, 46px); font-weight: 800; line-height: 1.05; letter-spacing: -0.02em; }}
.date {{ color: {MUTED}; margin-top: 6px; }}
.big {{ font-weight: 800; font-size: clamp(64px, 9vw, 112px); line-height: .9; letter-spacing: -0.04em; }}
.state {{ font-size: 20px; font-weight: 700; margin-top: 10px; }}
.quiet {{ color: {MUTED}; font-size: 15px; }}
.section {{ font-weight: 800; font-size: 20px; margin: 30px 0 12px 0; }}
.panel {{ background: {CARD}; border: 1.5px solid {LINE}; border-radius: 18px; padding: 22px 24px; }}
.task {{ font-weight: 800; font-size: 30px; letter-spacing: -0.02em; margin-bottom: 8px; }}
.why {{ font-size: 17px; line-height: 1.6; max-width: 48ch; }}
.form-title {{ font-weight: 800; font-size: clamp(28px, 3.6vw, 40px); letter-spacing: -0.02em; line-height: 1.08; margin: 0 0 8px 0; }}
.st-key-addpanel {{ background: {CARD}; border: 1.5px solid {LINE}; border-radius: 18px; padding: 18px 20px; }}

.st-key-pills [role="radiogroup"] {{ gap: 8px; flex-wrap: wrap; }}
.st-key-pills [data-testid="stRadioOption"] {{
    border: 1.5px solid {LINE}; border-radius: 999px; padding: 7px 18px; margin: 0; background: {CARD};
}}
.st-key-pills [data-testid="stRadioOption"][data-selected="true"] {{ background: {INK}; border-color: {INK}; }}
.st-key-pills [data-testid="stRadioOption"][data-selected="true"] p {{ color: #fff; }}

.row {{
    display: grid; grid-template-columns: 84px 1fr auto; gap: 14px; align-items: center;
    padding: 12px 16px; border-radius: 14px; background: {CARD};
    border: 1.5px solid {LINE}; border-left: 5px solid var(--tint); margin-bottom: 8px;
}}
.row .t {{ color: {MUTED}; font-size: 14px; }}
.row .n {{ font-weight: 700; }}
.row .k {{ color: {MUTED}; font-size: 14px; }}
.row .st {{ font-size: 13px; padding: 3px 10px; border-radius: 999px; border: 1.5px solid {LINE}; color: {MUTED}; }}
.row.done {{ opacity: .5; }}
.row.missed .st {{ color: {HIGH}; border-color: {HIGH}; }}
.row.now {{ border-color: {SIGNAL}; }}
.row.now .st {{ background: {SIGNAL}; border-color: {SIGNAL}; color: #fff; }}

[data-testid="stAlert"] > div {{ background: #E9EBFF !important; border-radius: 14px; color: {INK} !important; }}
[data-testid="stAlert"] p, [data-testid="stAlert"] li {{ color: {INK} !important; }}

/* ---------- outside: the blue field ---------- */
.st-key-outside {{ position: relative; }}
.field-title {{
    font-family: 'Archivo', sans-serif; font-stretch: 125%; font-weight: 800;
    font-size: clamp(44px, 6.6vw, 92px); line-height: .92; letter-spacing: -0.035em;
    color: #fff; margin: 18px 0 22px 0; max-width: 11ch;
}}
.field-sub {{ color: rgba(255,255,255,.82); font-size: 19px; line-height: 1.55; max-width: 42ch; }}
.field-brand {{ color: #fff; font-family: 'Archivo', sans-serif; font-stretch: 125%; font-weight: 800; font-size: 18px; }}
.signal {{ width: 100%; height: auto; display: block; }}
.signal .draw {{ stroke-dasharray: 1500; stroke-dashoffset: 1500; animation: draw 2.4s cubic-bezier(.6,.1,.2,1) .2s forwards; }}
.signal .late {{ opacity: 0; animation: fade .6s ease 2.3s forwards; }}
@keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
@keyframes fade {{ to {{ opacity: 1; }} }}
@media (prefers-reduced-motion: reduce) {{
    .signal .draw {{ animation: none; stroke-dashoffset: 0; }}
    .signal .late {{ animation: none; opacity: 1; }}
}}
.log {{
    font-family: 'JetBrains Mono', monospace; font-size: 14px; line-height: 1.9;
    color: rgba(255,255,255,.88); border: 1.5px solid rgba(255,255,255,.28);
    border-radius: 14px; padding: 16px 18px; margin-top: 14px; background: rgba(0,0,60,.18);
}}
.log .h {{ color: #fff; opacity: .55; }}
.log .o {{ color: {HIGH}; }}
/* hero artwork + floating product cards */
.art {{ position: relative; margin-top: 6px; }}
.float {{
    position: absolute; background: #fff; color: {INK}; border-radius: 16px;
    padding: 12px 14px; box-shadow: 0 22px 50px rgba(0,0,60,.35); font-size: 14px;
}}
.float.f1 {{ left: -4%; bottom: 8%; transform: rotate(-3deg); }}
.float.f2 {{ right: -2%; top: 40%; width: 210px; transform: rotate(2.5deg); border-left: 5px solid {HIGH}; }}
.fl-k {{ color: {MUTED}; font-size: 12px; font-family: 'JetBrains Mono', monospace; margin-bottom: 6px; }}
.fl-t {{ font-family: 'Archivo', sans-serif; font-stretch: 125%; font-weight: 800; font-size: 20px; }}
.fl-s {{ color: {MUTED}; font-size: 13px; line-height: 1.4; margin-top: 2px; }}
.fl-pills span, .tile-pills span {{
    display: inline-block; border: 1.5px solid {LINE}; border-radius: 999px; padding: 3px 10px;
    margin-right: 4px; font-size: 13px;
}}
.fl-pills .on {{ background: {INK}; border-color: {INK}; color: #fff; }}

/* bento: three illustrated tiles */
.bento {{ display: grid; grid-template-columns: 1.1fr 1fr 1fr; gap: 16px; margin-top: 40px; }}
.tile {{
    background: rgba(255,255,255,.08); border: 1.5px solid rgba(255,255,255,.2);
    border-radius: 20px; padding: 18px 20px 20px; color: rgba(255,255,255,.8); font-size: 15px;
    backdrop-filter: blur(6px);
}}
.tile b {{ display: block; color: #fff; font-family: 'Archivo', sans-serif; font-stretch: 125%; font-size: 18px; margin: 14px 0 4px 0; }}
.tile-art {{ width: 100%; height: 96px; }}
.tile-pills span {{ border-color: rgba(255,255,255,.4); color: #fff; }}
.tile-pills .on {{ background: #fff; color: {SIGNAL}; border-color: #fff; }}
.tile-meter {{ height: 10px; border-radius: 10px; background: rgba(255,255,255,.18); margin-top: 22px; overflow: hidden; }}
.tile-meter i {{ display: block; height: 100%; background: linear-gradient(90deg, {LOW}, {MID}, {HIGH}); }}
.tile-move {{ position: relative; height: 96px; }}
.slot {{ font-family: 'JetBrains Mono', monospace; font-size: 13px; border-radius: 10px; padding: 8px 10px; position: absolute; left: 0; right: 0; }}
.slot.old {{ top: 6px; border: 1.5px dashed rgba(255,255,255,.4); color: rgba(255,255,255,.55); text-decoration: line-through; }}
.slot.new {{ top: 50px; background: #fff; color: {SIGNAL}; font-weight: 600; box-shadow: 0 10px 24px rgba(0,0,60,.3); }}

/* workspace texture + sun path */
.sunpath {{ width: 100%; max-width: 250px; height: auto; display: block; margin: -6px 0 0 auto; }}
.fine {{ color: rgba(255,255,255,.6); font-size: 13px; margin-top: 36px; }}

.st-key-land_start button {{ background: #fff !important; color: {SIGNAL} !important; border: none !important; padding: .75rem 1.2rem; }}
.st-key-land_start button p {{ color: {SIGNAL} !important; font-weight: 700; }}
.st-key-land_signin button {{ background: transparent !important; border: 1.5px solid rgba(255,255,255,.65) !important; padding: .75rem 1.2rem; }}
.st-key-land_signin button p {{ color: #fff !important; font-weight: 700; }}

.st-key-authcard {{
    background: {CARD}; border-radius: 22px; padding: 30px 30px 22px 30px;
    box-shadow: 0 30px 80px rgba(0,0,40,.35);
}}
.st-key-authcard .stButton > button {{ width: 100%; }}
.st-key-google button {{ font-weight: 600; }}
.st-key-google button::before {{
    content: ""; width: 18px; height: 18px; margin-right: 10px; display: inline-block;
    background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'%3E%3Cpath fill='%23FFC107' d='M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z'/%3E%3Cpath fill='%23FF3D00' d='m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z'/%3E%3Cpath fill='%234CAF50' d='M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z'/%3E%3Cpath fill='%231976D2' d='M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z'/%3E%3C/svg%3E") no-repeat center / contain;
}}
.or {{ display: flex; align-items: center; gap: 12px; color: {MUTED}; font-size: 14px; margin: 14px 0 6px 0; }}
.or::before, .or::after {{ content: ""; flex: 1; height: 1.5px; background: {LINE}; }}
.card-title {{ font-family: 'Archivo', sans-serif; font-stretch: 125%; font-weight: 800; font-size: 28px; letter-spacing: -0.02em; margin: 0 0 4px 0; color: {INK}; }}
.step {{ color: {MUTED}; font-size: 14px; }}
.bar {{ height: 5px; border-radius: 5px; background: {LINE}; margin: 8px 0 22px 0; overflow: hidden; }}
.bar i {{ display: block; height: 100%; background: {SIGNAL}; }}
.devcode {{ font-family: 'JetBrains Mono', monospace; font-size: 22px; letter-spacing: .3em; color: {SIGNAL}; }}

@media (max-width: 760px) {{
    .bento {{ grid-template-columns: 1fr; }}
    .float {{ display: none; }}
    .row {{ grid-template-columns: 70px 1fr; }}
    .row .st {{ grid-column: 2; justify-self: start; }}
}}
</style>
""", unsafe_allow_html=True)


# ==========================================================
# ACCOUNTS + STORAGE
# ==========================================================

PROFILE_DIR = Path(
    os.environ.get("TWELFTH_PROFILE_DIR") or Path(__file__).resolve().parents[1] / "profiles"
)


def _secret(section: str):
    try:
        return st.secrets.get(section)
    except (FileNotFoundError, StreamlitSecretNotFoundError):  # no secrets (local dev, tests)
        return None


SUPABASE = _secret("supabase")
GOOGLE = bool((_secret("auth") or {}).get("google"))


@st.cache_resource
def _supabase_store(url: str, key: str) -> SupabaseStore:
    return SupabaseStore(url, key)


if SUPABASE:
    auth = SupabaseAuth(SUPABASE["url"], SUPABASE["anon_key"])
    store = _supabase_store(SUPABASE["url"], SUPABASE["service_role_key"])
else:
    auth = LocalAuth(PROFILE_DIR / "_accounts.json")
    store = ProfileStore(PROFILE_DIR)

for key, value in {
    "view": "landing",  # landing | signup | verify | signin | setup
    "account": None,  # {"email", "name"} once signed in, before a profile exists
    "pending_email": "",
    "dev_code": "",
    "setup_step": 1,
    "setup": {},
    "proposal": None,
    "replan_result": "",
    "notice": "",
    "just_onboarded": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = value

TASK_TYPES = list(TaskType)


def go_to(view: str) -> None:
    st.session_state.view = view


def enter(email: str, name: str = "") -> None:
    """Signed in: open the saved profile, or start first-time setup."""
    student_id = student_id_for_email(email)
    if store.exists(student_id):
        st.session_state.backend = store.load(student_id)
    else:
        st.session_state.account = {"email": email, "name": name}
        st.session_state.setup = {"name": name}
        st.session_state.setup_step = 1
        st.session_state.view = "setup"


# ==========================================================
# OUTSIDE: landing, sign up, verify, sign in, first-time setup
# ==========================================================

def _flat(html: str) -> str:
    """Markdown treats indented lines as code, so send HTML/SVG as one line."""
    return " ".join(line.strip() for line in html.splitlines() if line.strip())


# Film grain: SVG turbulence noise, tiled. Sits over everything, never clickable.
GRAIN = (
    "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E"
    "%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3' "
    "stitchTiles='stitch'/%3E%3CfeColorMatrix values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .55 0'/%3E"
    "%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")"
)

# Orbit rings + a scatter of stars, used behind the sign-in card.
ORBITS = (
    "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 900'%3E"
    "%3Cg fill='none' stroke='white' stroke-opacity='.16'%3E"
    "%3Ccircle cx='600' cy='470' r='300'/%3E%3Ccircle cx='600' cy='470' r='420' stroke-dasharray='2 10'/%3E"
    "%3Ccircle cx='600' cy='470' r='560'/%3E%3C/g%3E"
    "%3Ccircle cx='312' cy='372' r='7' fill='%23FF7A2F'/%3E%3Ccircle cx='1012' cy='640' r='5' fill='white'/%3E"
    "%3Cg fill='white' fill-opacity='.7'%3E%3Ccircle cx='140' cy='120' r='1.6'/%3E%3Ccircle cx='980' cy='160' r='1.4'/%3E"
    "%3Ccircle cx='1080' cy='330' r='1.8'/%3E%3Ccircle cx='220' cy='700' r='1.4'/%3E%3Ccircle cx='860' cy='820' r='1.6'/%3E"
    "%3Ccircle cx='420' cy='90' r='1.2'/%3E%3C/g%3E%3C/svg%3E\") center / cover no-repeat"
)


def blue_field(orbits: bool = False):
    art = f"{ORBITS}," if orbits else ""
    st.markdown(
        "<style>"
        f"[data-testid='stAppViewContainer']{{background:{art}"
        "radial-gradient(900px 600px at 85% 10%, rgba(120,140,255,.55), transparent 60%),"
        "radial-gradient(700px 500px at 0% 100%, rgba(0,0,120,.6), transparent 60%),"
        "linear-gradient(rgba(255,255,255,.055) 1px, transparent 1px) 0 0/100% 44px,"
        "linear-gradient(90deg, rgba(255,255,255,.055) 1px, transparent 1px) 0 0/44px 100%,"
        f"{SIGNAL} !important}}"
        f"[data-testid='stAppViewContainer']::after{{content:'';position:fixed;inset:0;"
        f"background:{GRAIN};opacity:.09;pointer-events:none;mix-blend-mode:overlay;z-index:0}}"
        "[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl']{display:none}"
        "</style>",
        unsafe_allow_html=True,
    )


def hero_art() -> str:
    """The day as a dial: sun path, moon, stars, and the energy signal across it,
    with two floating product cards (a check-in and a suggestion)."""
    signal = ("M40,330 C100,326 130,250 190,222 S290,170 340,182 S420,258 470,254 "
              "S560,200 620,210 S700,270 760,300")
    stars = "".join(
        f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fff" fill-opacity="{o}"/>'
        for x, y, r, o in [(70, 60, 1.6, .8), (160, 120, 1.1, .6), (640, 70, 1.8, .9), (720, 150, 1.2, .6),
                           (520, 40, 1.2, .7), (300, 30, 1.0, .5), (760, 40, 1.4, .7), (40, 180, 1.0, .5)]
    )
    svg = f"""
    <svg class="signal" viewBox="0 0 800 420" role="img"
         aria-label="Illustration: the day as an arc from sunrise to night, with an energy line across it">
      <defs>
        <radialGradient id="sun" cx="50%" cy="50%" r="50%">
          <stop offset="0" stop-color="#FFD3B0"/><stop offset=".55" stop-color="{HIGH}"/>
          <stop offset="1" stop-color="{HIGH}" stop-opacity="0"/>
        </radialGradient>
        <linearGradient id="dial" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stop-color="#fff" stop-opacity=".16"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>
        </linearGradient>
      </defs>
      {stars}
      <path d="M60,380 A340,340 0 0 1 740,380" fill="url(#dial)" stroke="#fff" stroke-opacity=".35" stroke-width="1.5"/>
      <path d="M140,380 A260,260 0 0 1 660,380" fill="none" stroke="#fff" stroke-opacity=".22" stroke-dasharray="3 9"/>
      <path d="M220,380 A180,180 0 0 1 580,380" fill="none" stroke="#fff" stroke-opacity=".14"/>
      <line x1="20" y1="380" x2="780" y2="380" stroke="#fff" stroke-opacity=".4"/>
      <circle cx="232" cy="128" r="46" fill="url(#sun)"/>
      <circle cx="232" cy="128" r="17" fill="#FFE2CC"/>
      <path d="M706,110 a26,26 0 1 0 22,40 a20,20 0 1 1 -22,-40z" fill="#fff" fill-opacity=".9"/>
      <g font-family="JetBrains Mono, monospace" font-size="15" fill="#fff" fill-opacity=".7">
        <text x="44" y="404">06:00</text><text x="372" y="404">14:00</text><text x="706" y="404">22:00</text>
      </g>
      <path class="draw" d="{signal}" fill="none" stroke="#fff" stroke-width="4.5" stroke-linecap="round"/>
      <g class="late">
        <circle cx="340" cy="182" r="10" fill="{HIGH}" stroke="#fff" stroke-width="3"/>
        <circle cx="470" cy="254" r="7" fill="#fff"/>
      </g>
    </svg>"""
    cards = """
    <div class="float f1">
      <div class="fl-k">Check-in, 10:02</div>
      <div class="fl-pills"><span>Tired</span><span class="on">Fine</span><span>Energized</span></div>
    </div>
    <div class="float f2">
      <div class="fl-k">Up next</div>
      <div class="fl-t">Problem sets</div>
      <div class="fl-s">because you're at your peak until about 11:30</div>
    </div>"""
    return _flat(f'<div class="art">{svg}{cards}</div>')


def bento() -> str:
    """Three illustrated tiles: what it does, shown rather than described."""
    nights = [(6.5, LOW), (7.5, MID), (5.0, LOW), (8.0, HIGH), (7.0, MID), (8.5, HIGH), (6.0, LOW)]
    bars = "".join(
        f'<rect x="{12 + i * 34}" y="{110 - h * 11}" width="20" height="{h * 11}" rx="6" fill="{c}"/>'
        for i, (h, c) in enumerate(nights)
    )
    return _flat(f"""
    <div class="bento">
      <div class="tile">
        <svg viewBox="0 0 250 120" class="tile-art" aria-hidden="true">{bars}
          <line x1="0" y1="111" x2="250" y2="111" stroke="#fff" stroke-opacity=".35"/></svg>
        <b>Starts from your sleep</b>A short night lowers the whole curve. No wearable needed.
      </div>
      <div class="tile">
        <div class="tile-pills"><span>Tired</span><span class="on">Fine</span><span>Energized</span></div>
        <div class="tile-meter"><i style="width:58%"></i></div>
        <b>One-tap check-ins</b>The estimate follows how you actually feel, not just the clock.
      </div>
      <div class="tile">
        <div class="tile-move">
          <div class="slot old">14:00 Data structures</div>
          <div class="slot new">14:20 Data structures</div>
        </div>
        <b>Plans that ask first</b>Something ran late? It proposes a change. Nothing moves until you say so.
      </div>
    </div>
    <div class="fine">A CSCE 634 prototype by Team 12th Interface. Please don't store anything sensitive here.</div>
    """)


def landing():
    blue_field()
    left, right = st.columns([1, 1.1], gap="large")
    with left:
        st.markdown(
            '<div class="field-brand">The 12th Interface</div>'
            '<div class="field-title">Study with your energy.</div>'
            '<div class="field-sub">Tell it how you slept. It maps your energy across the day, '
            "suggests what kind of studying fits right now, and tells you why.</div>",
            unsafe_allow_html=True,
        )
        st.write("")
        a, b, _ = st.columns([1, 1, 0.5])
        with a:
            if st.button("Get started", key="land_start", width="stretch"):
                go_to("signup")
                st.rerun()
        with b:
            if st.button("Sign in", key="land_signin", width="stretch"):
                go_to("signin")
                st.rerun()
    with right:
        st.markdown(hero_art(), unsafe_allow_html=True)
    st.markdown(bento(), unsafe_allow_html=True)


def auth_shell(title: str, subtitle: str):
    """Blue field + centred white card. Returns the card container."""
    blue_field(orbits=True)
    _, mid, _ = st.columns([1, 1.25, 1])
    with mid:
        st.markdown('<div class="field-brand" style="margin:10px 0 18px 0">The 12th Interface</div>',
                    unsafe_allow_html=True)
        card = st.container(key="authcard")
        card.markdown(f'<div class="card-title">{title}</div><p class="quiet">{subtitle}</p>',
                      unsafe_allow_html=True)
    return card


def google_button(card):
    with card:
        if GOOGLE:
            if st.button("Continue with Google", key="google", width="stretch"):
                st.login("google")
        else:
            st.button("Continue with Google", key="google", disabled=True, width="stretch",
                      help="Google sign-in is switched on in the deployed site (see DEPLOY.md).")
        st.markdown('<div class="or">or with email</div>', unsafe_allow_html=True)


def signup():
    card = auth_shell("Create your account", "Free, and it takes a minute.")
    google_button(card)
    with card:
        with st.form("signup_form"):
            email = st.text_input("Email", placeholder="you@tamu.edu")
            password = st.text_input("Password", type="password", placeholder="At least 8 characters")
            create = st.form_submit_button("Create account", type="primary", width="stretch")
        if create:
            try:
                code = auth.sign_up(email, password)
            except AuthError as e:
                st.warning(str(e))
            else:
                st.session_state.pending_email = email.strip().lower()
                st.session_state.dev_code = code or ""
                go_to("verify")
                st.rerun()
        if st.button("I already have an account", key="to_signin", type="tertiary"):
            go_to("signin")
            st.rerun()
        if st.button("Back", key="signup_back", type="tertiary"):
            go_to("landing")
            st.rerun()


def verify():
    email = st.session_state.pending_email
    card = auth_shell("Check your email", f"We sent a 6-digit code to <b>{email}</b>.")
    with card:
        if not auth.sends_real_email and st.session_state.dev_code:
            st.info(f"Dev mode, no email sent. Your code is {st.session_state.dev_code}")
        with st.form("verify_form"):
            code = st.text_input("Code", max_chars=6, placeholder="123456")
            ok = st.form_submit_button("Verify email", type="primary", width="stretch")
        if ok:
            try:
                auth.verify(email, code)
            except AuthError as e:
                st.warning(str(e))
            else:
                st.session_state.dev_code = ""
                enter(email)
                st.rerun()
        if st.button("Send a new code", key="resend", type="tertiary"):
            try:
                st.session_state.dev_code = auth.resend(email) or ""
                st.success("New code sent.")
            except AuthError as e:
                st.warning(str(e))
        if st.button("Use a different email", key="verify_back", type="tertiary"):
            go_to("signup")
            st.rerun()


def signin():
    card = auth_shell("Welcome back", "Sign in to pick up where you left off.")
    google_button(card)
    with card:
        with st.form("signin_form"):
            email = st.text_input("Email", placeholder="you@tamu.edu")
            password = st.text_input("Password", type="password")
            go_on = st.form_submit_button("Sign in", type="primary", width="stretch")
        if go_on:
            try:
                signed_in = auth.sign_in(email, password)
            except NeedsVerification as e:
                st.session_state.pending_email = email.strip().lower()
                if not auth.sends_real_email:
                    st.session_state.dev_code = auth.resend(email) or ""
                st.info(str(e))
                go_to("verify")
                st.rerun()
            except AuthError as e:
                st.warning(str(e))
            else:
                enter(signed_in)
                st.rerun()
        if st.button("Create an account", key="to_signup", type="tertiary"):
            go_to("signup")
            st.rerun()
        if st.button("Back", key="signin_back", type="tertiary"):
            go_to("landing")
            st.rerun()


SETUP_STEPS = 3


def setup():
    """First-time setup after the account exists: name, sleep, study preferences."""
    step = st.session_state.setup_step
    data = st.session_state.setup
    account = st.session_state.account
    titles = {1: "What should we call you?", 2: "How do you usually sleep?",
              3: "What do you like to study when…"}
    subs = {
        1: "Shown on your dashboard.",
        2: "Your energy estimate starts here. You can log last night's sleep any day.",
        3: "Not sure? Leave it on no preference and I'll learn from what you pick.",
    }
    card = auth_shell(titles[step], subs[step])
    with card:
        st.markdown(
            f'<div class="step">Step {step} of {SETUP_STEPS}</div>'
            f'<div class="bar"><i style="width:{step / SETUP_STEPS * 100:.0f}%"></i></div>',
            unsafe_allow_html=True,
        )
        if step == 1:
            with st.form("setup_name"):
                name = st.text_input("Name", value=data.get("name") or "", placeholder="e.g. Priya")
                nxt = st.form_submit_button("Continue", type="primary", width="stretch")
            if nxt:
                if not name.strip():
                    st.warning("Enter a name to continue.")
                else:
                    data["name"] = name.strip()
                    st.session_state.setup_step = 2
                    st.rerun()
        elif step == 2:
            with st.form("setup_sleep"):
                hours = st.number_input(
                    "Hours of sleep on a typical night", min_value=0.0,
                    max_value=float(MAX_SURVEY_SLEEP_HOURS), value=float(data.get("hours", 7.5)), step=0.5,
                )
                wake = st.time_input(
                    "Usual wake-up time",
                    value=data.get("wake", datetime.strptime("07:30", "%H:%M").time()), step=900,
                )
                nxt = st.form_submit_button("Continue", type="primary", width="stretch")
            if nxt:
                data.update(hours=hours, wake=wake)
                st.session_state.setup_step = 3
                st.rerun()
        else:
            with st.form("setup_prefs"):
                options = [None, *TASK_TYPES]
                prefs = {}
                labels = {"low": "…you're tired?", "medium": "…your energy is so-so?",
                          "high": "…you're energized?"}
                for bucket, label in labels.items():
                    prefs[bucket] = st.selectbox(
                        label, options, key=f"pref_{bucket}",
                        format_func=lambda t: "No preference" if t is None else t.label.capitalize(),
                    )
                done = st.form_submit_button("Create my plan", type="primary", width="stretch")
            if done:
                session = DashboardSession.onboard(
                    student_id=student_id_for_email(account["email"]), name=data["name"],
                    typical_sleep_hours=data["hours"], typical_wake_time=data["wake"],
                    task_preferences=prefs, email=account["email"],
                )
                store.save(session)
                st.session_state.backend = session
                st.session_state.just_onboarded = True
                st.rerun()
        if step > 1 and st.button("Back", key="setup_back", type="tertiary"):
            st.session_state.setup_step = step - 1
            st.rerun()


if "backend" not in st.session_state:
    if GOOGLE and st.user.is_logged_in and st.session_state.account is None:
        enter(st.user.email, name=st.user.get("given_name") or st.user.get("name") or "")
        st.rerun()
    {"landing": landing, "signup": signup, "verify": verify, "signin": signin, "setup": setup}[
        st.session_state.view
    ]()
    st.stop()

backend: DashboardSession = st.session_state.backend


# ==========================================================
# SHARED PIECES (workspace)
# ==========================================================

def day_curve_figure(curve, checkins, now_pct, height=320):
    hours = [8 + i for i in range(len(curve))]
    values = [p for _t, p in curve]
    fig = go.Figure()
    fig.add_hrect(y0=0, y1=33, fillcolor=LOW, opacity=0.05, line_width=0)
    fig.add_hrect(y0=66, y1=100, fillcolor=HIGH, opacity=0.06, line_width=0)
    fig.add_trace(go.Scatter(
        x=hours, y=values, mode="lines", name="Estimated energy",
        line={"color": SIGNAL, "width": 3.5, "shape": "spline", "smoothing": 1.1},
        customdata=[t for t, _p in curve], hovertemplate="%{customdata}: %{y}%<extra></extra>",
    ))
    if checkins:
        fig.add_trace(go.Scatter(
            x=[_hour_of(t) for t, _p in checkins], y=[p for _t, p in checkins],
            mode="markers", name="Your check-ins",
            marker={"size": 12, "color": INK, "symbol": "diamond", "line": {"color": "#fff", "width": 2}},
            hovertemplate="check-in: %{y}%<extra></extra>",
        ))
    now = datetime.now()
    now_x = now.hour + now.minute / 60
    if hours[0] <= now_x <= hours[-1]:
        fig.add_vline(x=now_x, line_width=1.5, line_dash="dot", line_color=INK)
        fig.add_trace(go.Scatter(
            x=[now_x], y=[now_pct], mode="markers+text", text=["now"], textposition="top center",
            textfont={"color": INK, "size": 13, "family": "JetBrains Mono, ui-monospace, monospace"}, showlegend=False,
            hoverinfo="skip",
            marker={"size": 16, "color": energy_color(now_pct), "line": {"color": "#fff", "width": 3}},
        ))
    fig.update_layout(
        height=height, margin={"l": 8, "r": 8, "t": 18, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Archivo, sans-serif", "color": MUTED, "size": 12},
        showlegend=bool(checkins), legend={"orientation": "h", "y": 1.12, "x": 0},
        hoverlabel={"bgcolor": INK, "font_color": "#fff"},
    )
    fig.update_xaxes(tickvals=hours[::2], showgrid=False, zeroline=False,
                     ticktext=[f"{h:02d}:00" for h in hours[::2]],
                     tickfont={"family": "JetBrains Mono, ui-monospace, monospace"})
    fig.update_yaxes(range=[0, 100], ticksuffix="%", gridcolor=LINE, zeroline=False, tickvals=[33, 66])
    return fig


def _hour_of(label: str) -> float:
    t = datetime.strptime(label, "%I:%M %p")
    return t.hour + t.minute / 60


def _clock(label: str) -> str:
    """'9:45 PM' -> '21:45' (the workspace shows 24h times in mono)."""
    return datetime.strptime(label, "%I:%M %p").strftime("%H:%M")


def schedule_row(item):
    labels = {t.label: t.value for t in TaskType}
    tint = TASK_TINT.get(labels.get(item["task_type"]) or "", LINE)
    cls = {"Completed": "done", "Done": "done", "Missed": "missed", "In progress": "now"}.get(item["status"], "")
    status = "Done" if item["status"] in ("Completed", "Done") else item["status"]
    st.markdown(f"""
    <div class="row {cls}" style="--tint:{tint}">
      <div class="t">{_clock(item["time"])}</div>
      <div><div class="n">{item["task"]}</div>
           <div class="k">{item["task_type"].capitalize()}, {item["duration"]}</div></div>
      <div class="st">{status}</div>
    </div>""", unsafe_allow_html=True)


def sun_path(now: datetime) -> str:
    """Today as an arc from 06:00 to 22:00, with the sun (or moon) where 'now' is."""
    t = now.hour + now.minute / 60
    frac = min(max((t - 6) / 16, 0), 1)
    angle = math.pi * (1 - frac)
    x, y = 180 + 150 * math.cos(angle), 170 - 150 * math.sin(angle)
    night = t < 6 or t > 22
    marker = (
        f'<path d="M{x - 6:.0f},{y - 14:.0f} a14,14 0 1 0 12,22 a11,11 0 1 1 -12,-22z" fill="{SIGNAL}"/>'
        if night else
        f'<circle cx="{x:.0f}" cy="{y:.0f}" r="20" fill="{HIGH}" fill-opacity=".25"/>'
        f'<circle cx="{x:.0f}" cy="{y:.0f}" r="10" fill="{HIGH}"/>'
    )
    done = "" if night else (
        f'<path d="M30,170 A150,150 0 0 1 {x:.1f},{y:.1f}" fill="none" stroke="{SIGNAL}" stroke-width="3"/>'
    )
    return _flat(f"""
    <svg class="sunpath" viewBox="0 0 360 200" role="img" aria-label="Where you are in today">
      <path d="M30,170 A150,150 0 0 1 330,170" fill="none" stroke="{LINE}" stroke-width="3" stroke-dasharray="2 7"/>
      {done}
      <line x1="10" y1="170" x2="350" y2="170" stroke="{LINE}" stroke-width="1.5"/>
      {marker}
      <g font-family="JetBrains Mono, monospace" font-size="12" fill="{MUTED}">
        <text x="14" y="192">06:00</text><text x="160" y="192">14:00</text><text x="306" y="192">22:00</text>
      </g>
    </svg>""")


# ==========================================================
# SIDEBAR
# ==========================================================

with st.sidebar:
    st.markdown('<div class="brand">The 12th Interface</div>'
                '<div class="brand-sub">Your study companion</div>', unsafe_allow_html=True)
    page = st.radio("Navigation", ["Home", "My Schedule", "Insights", "Study Mode", "Replanning"],
                    label_visibility="collapsed")
    sleep = st.number_input("Last night's sleep (hours)", min_value=0.0, max_value=14.0,
                            value=float(backend.sleep_hours), step=0.5)
    if sleep != backend.sleep_hours:
        backend.set_sleep(sleep)
    plan = backend.plan()
    pct = plan["energy_pct"]
    st.markdown(f"""
    <div class="who"><div class="dot">{backend.name[:1].upper()}</div>
      <div><div class="n">{backend.name}</div><div class="s">{backend.email or "local profile"}</div></div>
    </div>""", unsafe_allow_html=True)
    if st.button("Sign out", width="stretch"):
        store.save(backend)
        google = GOOGLE and st.user.is_logged_in
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        if google:
            st.logout()
        st.rerun()

schedule = backend.schedule_items()
color = energy_color(pct)


# ==========================================================
# HOME
# ==========================================================

if page == "Home":
    now = datetime.now()
    part = "morning" if now.hour < 12 else "afternoon" if now.hour < 17 else "evening"
    head, arc = st.columns([1.6, 1])
    with head:
        st.markdown(f'<div class="hello">Good {part}, {backend.name}.</div>'
                    f'<div class="date">{now.strftime("%A, %B")} {now.day}</div>', unsafe_allow_html=True)
    with arc:
        st.markdown(sun_path(now), unsafe_allow_html=True)
    if st.session_state.just_onboarded:
        st.success("You're set up. Here's where I'll start:\n\n"
                   + "\n".join(f"- {line}" for line in backend.starting_suggestions())
                   + "\n\nI added a sample study day so you can try things out.")
        st.session_state.just_onboarded = False

    st.write("")
    left, right = st.columns([0.9, 1.6], gap="large")
    with left:
        st.markdown(f"""
        <div class="big" style="color:{color}">{pct}%</div>
        <div class="state">{plan["energy_label"]}</div>
        <div class="quiet">{plan["energy_source"]}</div>""", unsafe_allow_html=True)
        st.markdown('<div class="section" style="margin-top:24px">How are you feeling?</div>',
                    unsafe_allow_html=True)
        with st.container(key="pills"):
            feeling = st.radio("How are you feeling?", list(FEELINGS), horizontal=True,
                               label_visibility="collapsed", key="home_feeling")
        if st.button("Log check-in", type="primary"):
            backend.checkin(feeling)
            st.rerun()
        if backend.last_feeling:
            st.success(f"Your latest check-in: {backend.last_feeling}")
    with right:
        st.plotly_chart(day_curve_figure(backend.energy_curve(), backend.checkin_history(), pct),
                        width="stretch", config={"displayModeBar": False})

    left, right = st.columns([1.1, 1], gap="large")
    with left:
        st.markdown('<div class="section">Up next for you</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="panel" style="border-left:5px solid {TASK_TINT.get(plan["task_type"], MID)}">
          <div class="task">{plan["task_label"].capitalize()}</div>
          <div class="why">I'd go with {plan["task_label"]} {plan["why"]}.</div>
        </div>""", unsafe_allow_html=True)
        if plan["cold_start"]:
            st.caption("I'm still learning your patterns, so early suggestions lean on default rules.")
        st.write("")
        if st.button("Start this task", type="primary"):
            backend.start_task(plan["task_type"])
            st.session_state.notice = f"{plan['task_label'].capitalize()} started. It's waiting in Study Mode."
            st.rerun()
        if st.session_state.notice:
            st.success(st.session_state.notice)
    with right:
        st.markdown('<div class="section">Today</div>', unsafe_allow_html=True)
        upcoming = [x for x in schedule if x["status"] in ("In progress", "Upcoming")]
        for item in (upcoming or schedule)[:4]:
            schedule_row(item)
        if not schedule:
            st.caption("Nothing planned today. Add a session in My Schedule.")


# ==========================================================
# MY SCHEDULE
# ==========================================================

elif page == "My Schedule":
    st.markdown('<div class="form-title">My schedule</div>', unsafe_allow_html=True)
    done = sum(1 for x in schedule if x["status"] == "Completed")
    st.markdown(f'<p class="quiet">{len(schedule)} sessions today, {done} done.</p>', unsafe_allow_html=True)
    left, right = st.columns([1.5, 1], gap="large")
    with left:
        for item in schedule:
            schedule_row(item)
            if item["status"] not in ("Completed", "Done") and st.button(
                "Mark done", key=f"complete_{item['session_id']}", type="tertiary"
            ):
                backend.mark_completed(item["session_id"])
                st.rerun()
        if backend.deferred:
            st.caption("Moved to tomorrow: " + ", ".join(e["title"] for e in backend.deferred))
    with right:
        add = st.container(key="addpanel")
        add.markdown('<div class="section" style="margin-top:0">Add a session</div>', unsafe_allow_html=True)
        with add.form("add_session_form"):
            new_task = st.text_input("What are you studying?", placeholder="e.g. Database assignment")
            new_type = st.selectbox("Kind of task", TASK_TYPES, format_func=lambda t: t.label.capitalize())
            today = datetime.now().astimezone()
            slots = [today.replace(hour=h, minute=m, second=0, microsecond=0)
                     for h in range(8, 22) for m in (0, 30)]
            new_time = st.selectbox("Start", slots, format_func=lambda t: t.strftime("%H:%M"))
            duration = st.selectbox("Length (minutes)", [15, 25, 30, 45, 60, 90], index=3)
            submitted = st.form_submit_button("Add session", type="primary", width="stretch")
        if submitted:
            if new_task.strip():
                backend.add_session(new_task.strip(), new_time, duration, new_type)
                st.success("Session added.")
                st.rerun()
            else:
                st.warning("Give the session a name first.")
        st.caption(f"Right now {plan['task_label']} fits best: {plan['why']}.")


# ==========================================================
# INSIGHTS
# ==========================================================

elif page == "Insights":
    curve = backend.energy_curve()
    checkins = backend.checkin_history()
    peak_time, peak = max(curve, key=lambda x: x[1])
    low_time, low = min(curve, key=lambda x: x[1])
    st.markdown('<div class="form-title">Your energy today</div>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="why">Your best stretch is around <b>{_clock(peak_time)}</b> ({peak}%). '
        f"The lowest point is around <b>{_clock(low_time)}</b> ({low}%). That's from "
        f"{backend.sleep_hours:g} hours of sleep and {len(checkins)} "
        f"check-in{'s' if len(checkins) != 1 else ''} today.</p>", unsafe_allow_html=True)
    st.plotly_chart(day_curve_figure(curve, checkins, pct, 380), width="stretch",
                    config={"displayModeBar": False})
    st.caption("Change last night's sleep in the sidebar and watch the curve move.")

    st.markdown('<div class="section">This week</div>', unsafe_allow_html=True)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    energy_week = [75, 55, 85, 65, 45, 90, 70]
    week = go.Figure()
    week.add_trace(go.Bar(x=days, y=[7.5, 6.5, 8, 7, 6, 9, 7.5], name="Sleep (h)",
                          marker_color=[energy_color(e) for e in energy_week], marker_line_width=0))
    week.add_trace(go.Scatter(x=days, y=energy_week, name="Energy", yaxis="y2", mode="lines+markers",
                              line={"color": INK, "width": 2}))
    week.update_layout(
        height=300, margin={"l": 8, "r": 8, "t": 30, "b": 8}, bargap=0.45,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Archivo, sans-serif", "color": MUTED},
        yaxis={"title": "Sleep (h)", "gridcolor": LINE},
        yaxis2={"title": "Energy %", "overlaying": "y", "side": "right", "range": [0, 100],
                "showgrid": False, "tickvals": [0, 33, 66, 100]},
        legend={"orientation": "h", "y": 1.15},
    )
    st.plotly_chart(week, width="stretch", config={"displayModeBar": False})
    st.caption("The weekly chart is sample data, not your measurements.")


# ==========================================================
# STUDY MODE
# ==========================================================

elif page == "Study Mode":
    if backend.active_task:
        active = TaskType(backend.active_task)
        st.markdown(f"""
        <div class="panel" style="background:{SIGNAL};border-color:{SIGNAL};padding:48px 44px">
          <div style="color:rgba(255,255,255,.75)">You're studying</div>
          <div class="big" style="color:#fff;font-size:clamp(48px,7vw,88px)">{active.label.capitalize()}</div>
          <p class="why" style="color:#fff;margin-top:14px">One thing at a time. Finish when you're ready.</p>
        </div>""", unsafe_allow_html=True)
        st.write("")
        if st.button("Finish study session", type="primary"):
            backend.finish_task()
            st.session_state.notice = ""
            st.rerun()
    else:
        st.markdown('<div class="form-title">Ready to focus?</div>', unsafe_allow_html=True)
        st.markdown(f'<p class="quiet">At {pct}% I\'d pick {plan["task_label"]}, but it\'s your call. '
                    "What you choose teaches the planner what you like.</p>", unsafe_allow_html=True)
        pick, _ = st.columns([1, 1])
        with pick:
            selected = st.selectbox(
                "What would you like to work on?", TASK_TYPES,
                index=TASK_TYPES.index(TaskType(plan["task_type"])),
                format_func=lambda t: t.label.capitalize() + ("  (suggested)" if t.value == plan["task_type"] else ""),
            )
            st.select_slider("How long?", options=[15, 25, 30, 45, 60, 90], value=45,
                             format_func=lambda x: f"{x} min")
        if st.button("Start my session", type="primary"):
            backend.start_task(selected.value)
            st.rerun()


# ==========================================================
# REPLANNING
# ==========================================================

elif page == "Replanning":
    st.markdown('<div class="form-title">Something changed?</div>', unsafe_allow_html=True)
    st.markdown('<p class="quiet">Tell me what happened. I\'ll suggest a change, '
                "and nothing moves until you say so.</p>", unsafe_allow_html=True)
    pick, _ = st.columns([1, 1])
    with pick:
        trigger = st.selectbox("What happened?", list(DISRUPTIONS))
    if st.button("Suggest a new plan", type="primary"):
        st.session_state.proposal = backend.disrupt(trigger)
        st.session_state.replan_result = ""

    proposal = st.session_state.proposal
    if proposal is not None:
        change = proposal.proposed_change
        if backend.is_ask(proposal):
            detail = "No change yet. Tell me what's going on and I'll adjust."
        else:
            start = datetime.fromisoformat(change["new_start"])
            end = datetime.fromisoformat(change["new_end"])
            detail = (f'New time for {change.get("title") or "this session"}: '
                      f'<span class="mono">{start.strftime("%H:%M")}–{end.strftime("%H:%M")}</span>')
        st.write("")
        st.markdown(f"""
        <div class="panel" style="border-left:5px solid {SIGNAL}">
          <div class="why" style="max-width:64ch">{proposal.message}</div>
          <div class="quiet" style="margin-top:10px">{detail}</div>
        </div>""", unsafe_allow_html=True)
        st.write("")
        if backend.is_ask(proposal):
            with st.form("ask_form", clear_on_submit=True):
                answer = st.text_input("What changed?",
                                       placeholder="e.g. \"I'm wiped, 20 minutes max\" or \"let's do it tomorrow\"")
                c1, c2 = st.columns(2)
                with c1:
                    sent = st.form_submit_button("Tell the planner", type="primary", width="stretch")
                with c2:
                    skipped = st.form_submit_button("Never mind", width="stretch")
            if sent or skipped:
                st.session_state.replan_result = backend.answer_ask(proposal, answer if sent else "never mind")
                st.session_state.proposal = None
                st.rerun()
        else:
            c1, c2, _ = st.columns([1, 1, 1.2])
            with c1:
                if st.button("Accept suggestion", type="primary", width="stretch"):
                    st.session_state.replan_result = backend.respond(proposal, "accept")
                    st.session_state.proposal = None
                    st.rerun()
            with c2:
                if st.button("Keep my original plan", width="stretch"):
                    st.session_state.replan_result = backend.respond(proposal, "reject")
                    st.session_state.proposal = None
                    st.rerun()

    if st.session_state.replan_result:
        st.success(st.session_state.replan_result)
        st.markdown('<div class="section">Today, updated</div>', unsafe_allow_html=True)
        for item in backend.schedule_items():
            schedule_row(item)


# Save after every interaction, so the next visit picks up here.
store.save(backend)


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
from datetime import datetime, timedelta
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

/* ---------- week + day timelines ---------- */
.tl {{ background: {CARD}; border: 1.5px solid {LINE}; border-radius: 18px; padding: 14px 14px 10px 8px; overflow-x: auto; }}
.tl-grid {{ display: grid; grid-template-columns: 58px repeat(var(--cols), minmax(var(--minw), 1fr)); column-gap: 6px; }}
.tl-head {{ text-align: center; padding: 2px 0 10px 0; color: {MUTED}; font-size: 13px; font-weight: 600; }}
.tl-head span {{ display: block; }}
.tl-head b {{ display: inline-block; font-family: 'Archivo', sans-serif; font-stretch: 125%; font-size: 22px; color: {INK}; line-height: 1.1; }}
.tl-head.today b {{ color: #fff; background: {SIGNAL}; border-radius: 10px; display: inline-block; padding: 0 9px; margin-top: 2px; }}
.tl-gutter, .tl-col {{ position: relative; height: var(--h); }}
.tl-col {{ border-radius: 12px; background: repeating-linear-gradient(to bottom, {LINE} 0 1px, transparent 1px var(--pph)); }}
.tl-col.today {{ background-color: rgba(0,0,242,.035); }}
.tl-hour {{ position: absolute; right: 8px; transform: translateY(-50%); font-family: 'JetBrains Mono', monospace; font-size: 11px; color: {MUTED}; }}
.tl-energy {{ position: absolute; left: 4px; width: 5px; border-radius: 3px; }}
.blk {{ position: absolute; left: 3px; right: 3px; border-radius: 9px; padding: 4px 7px; overflow: hidden;
        font-size: 12px; line-height: 1.25; color: {INK}; border-left: 4px solid var(--tint);
        background: color-mix(in srgb, var(--tint) 14%, white); box-shadow: 0 1px 0 rgba(11,11,59,.05); }}
.blk .bt {{ font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.blk .bm {{ font-family: 'JetBrains Mono', monospace; font-size: 10.5px; color: {MUTED}; }}
.blk.fixed {{ --tint: {INK}; background: repeating-linear-gradient(135deg, #ECEDF7 0 6px, #F5F6FB 6px 12px); }}
.blk.brk {{ --tint: {LINE}; background: transparent; border: 1.5px dashed {LINE}; }}
.blk.done {{ opacity: .45; }}
.blk.missed {{ border-left-style: dashed; background: #fff; }}
.blk .fit {{ position: absolute; top: 4px; right: 6px; font-size: 11px; }}
.tl.day .blk {{ font-size: 14px; padding: 6px 12px; }}
.tl.day .blk .bm {{ font-size: 12px; }}
.nowline {{ position: absolute; left: -4px; right: 0; height: 2px; background: {HIGH}; z-index: 3; }}
.nowline::before {{ content: ""; position: absolute; left: -2px; top: -4px; width: 10px; height: 10px; border-radius: 50%; background: {HIGH}; }}
.legend {{ display: flex; gap: 16px; flex-wrap: wrap; color: {MUTED}; font-size: 13px; margin: 10px 2px 0 2px; }}
.legend i {{ display: inline-block; width: 12px; height: 12px; border-radius: 4px; margin-right: 6px; vertical-align: -1px; }}

/* ---------- assistant chat ---------- */
.st-key-chatbox {{ background: {CARD}; border: 1.5px solid {LINE}; border-radius: 18px; padding: 8px 14px 12px 14px; }}
[data-testid="stChatMessage"] {{ background: transparent; padding: 8px 4px; }}
[data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li {{ font-size: 15.5px; }}
[data-testid="stChatMessage"] code {{ background: #EEF0FF; color: {SIGNAL_DEEP}; border-radius: 6px; padding: 1px 6px; }}
.st-key-listpanel {{ background: {CARD}; border: 1.5px solid {LINE}; border-radius: 18px; padding: 16px 18px; }}
.chip {{ display: flex; justify-content: space-between; gap: 10px; align-items: baseline; padding: 9px 12px; margin-bottom: 6px;
         border-radius: 12px; border: 1.5px solid {LINE}; border-left: 5px solid var(--tint); font-size: 14px; }}
.chip b {{ font-weight: 700; }}
.chip span {{ color: {MUTED}; font-family: 'JetBrains Mono', monospace; font-size: 12px; white-space: nowrap; }}
.st-key-viewpills [role="radiogroup"], .st-key-daypills [role="radiogroup"], .st-key-weekpills [role="radiogroup"] {{ gap: 8px; flex-wrap: wrap; }}
.st-key-viewpills [data-testid="stRadioOption"], .st-key-daypills [data-testid="stRadioOption"], .st-key-weekpills [data-testid="stRadioOption"] {{
    border: 1.5px solid {LINE}; border-radius: 999px; padding: 7px 16px; margin: 0; background: {CARD};
}}
.st-key-viewpills [data-testid="stRadioOption"][data-selected="true"], .st-key-daypills [data-testid="stRadioOption"][data-selected="true"],
.st-key-weekpills [data-testid="stRadioOption"][data-selected="true"] {{ background: {INK}; border-color: {INK}; }}
.st-key-viewpills [data-testid="stRadioOption"][data-selected="true"] p, .st-key-daypills [data-testid="stRadioOption"][data-selected="true"] p,
.st-key-weekpills [data-testid="stRadioOption"][data-selected="true"] p {{ color: #fff; }}

/* ---------- insights ---------- */
.kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 8px 0 6px 0; }}
.kpi {{ background: {CARD}; border: 1.5px solid {LINE}; border-radius: 18px; padding: 16px 18px; }}
.kpi .v {{ font-family: 'Archivo', sans-serif; font-stretch: 125%; font-weight: 800; font-size: 34px; letter-spacing: -0.02em; line-height: 1.05; }}
.kpi .l {{ color: {MUTED}; font-size: 14px; margin-top: 4px; }}
.tip {{ display: grid; grid-template-columns: 34px 1fr; gap: 10px; align-items: start; background: {CARD};
        border: 1.5px solid {LINE}; border-radius: 16px; padding: 14px 16px; margin-bottom: 10px; font-size: 15.5px; line-height: 1.5; }}
.tip .ic {{ width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; font-size: 17px; background: #EEF0FF; }}
.dl {{ display: grid; grid-template-columns: 1fr 170px 96px; gap: 14px; align-items: center; padding: 12px 16px; background: {CARD};
       border: 1.5px solid {LINE}; border-left: 5px solid var(--tint); border-radius: 14px; margin-bottom: 8px; }}
.dl .n {{ font-weight: 700; }}
.dl .k {{ color: {MUTED}; font-size: 13px; }}
.dl .bar {{ margin: 0; height: 8px; }}
.dl .bar i {{ background: var(--tint); }}
.dl .st {{ font-size: 12.5px; text-align: center; padding: 3px 8px; border-radius: 999px; border: 1.5px solid {LINE}; color: {MUTED}; }}
.dl .st.warn {{ color: {HIGH}; border-color: {HIGH}; }}
.dl .st.ok {{ color: {SIGNAL}; border-color: {SIGNAL}; }}

@media (max-width: 760px) {{
    .kpis {{ grid-template-columns: 1fr 1fr; }}
    .dl {{ grid-template-columns: 1fr; }}
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


KIND_TINT = {"class": INK, "other": INK}


def _tint(block) -> str:
    if block["kind"] in KIND_TINT:
        return KIND_TINT[block["kind"]]
    return TASK_TINT.get(block["task_type"] or "", LINE)


def _block_html(b, h0: int, pph: int, detailed: bool) -> str:
    top = (b["start"].hour + b["start"].minute / 60 - h0) * pph
    height = max(b["minutes"] / 60 * pph - 3, 16)
    cls = ["blk"]
    if b["kind"] in ("class", "other"):
        cls.append("fixed")
    elif b["kind"] == "break":
        cls.append("brk")
    if b["status"] in ("Completed", "Done") and b["kind"] == "study":
        cls.append("done")
    if b["status"] == "Missed":
        cls.append("missed")
    kind = (TaskType(b["task_type"]).label.capitalize() if b["task_type"]
            else "Class" if b["kind"] == "class" else b["kind"].capitalize())
    meta = f'{b["start"]:%H:%M}–{b["end"]:%H:%M}' + (f" · {kind}" if detailed else "")
    if b["status"] == "Completed":
        meta += " · done ✓"
    elif b["status"] == "Missed":
        meta += " · missed"
    fit = '<span class="fit" title="Fits your energy at this time">⚡</span>' if b["fits"] else ""
    show_meta = height >= 30
    return (f'<div class="{" ".join(cls)}" style="top:{top:.0f}px;height:{height:.0f}px;--tint:{_tint(b)}" '
            f'title="{b["title"]} {meta}">{fit}<div class="bt">{b["title"]}</div>'
            + (f'<div class="bm">{meta}</div>' if show_meta else "") + "</div>")


def timeline_html(days, detailed: bool = False, pph: int = 44) -> str:
    """A calendar: one column per day, hour lines, blocks placed by time, energy strip, now line."""
    blocks = [b for d in days for b in d["blocks"]]
    h0 = min([7, *[b["start"].hour for b in blocks]])
    h1 = max([22, *[b["end"].hour + (1 if b["end"].minute else 0) for b in blocks]])
    height = (h1 - h0) * pph
    now = datetime.now().astimezone()
    curve = {_hour_of(t): p for t, p in backend.energy_curve(range(h0, h1))}
    gutter = "".join(f'<div class="tl-hour" style="top:{(h - h0) * pph}px">{h:02d}:00</div>'
                     for h in range(h0 + 1, h1))
    gutter += "".join(
        f'<div class="tl-energy" style="top:{(h - h0) * pph + 2}px;height:{pph - 4}px;'
        f'background:{energy_color(p)};opacity:{0.25 + p / 160:.2f}" title="Typical energy {p}%"></div>'
        for h, p in curve.items())
    head = '<div class="tl-head"></div>'
    cols = ""
    for d in days:
        today = d["date"] == now.date()
        name = f'{d["date"]:%A, %B}' if detailed else f'{d["date"]:%a}'
        head += f'<div class="tl-head{" today" if today else ""}"><span>{name}</span><b>{d["date"].day}</b></div>'
        inner = "".join(_block_html(b, h0, pph, detailed) for b in d["blocks"])
        if today and h0 <= now.hour < h1:
            inner += f'<div class="nowline" style="top:{(now.hour + now.minute / 60 - h0) * pph:.0f}px"></div>'
        cols += f'<div class="tl-col{" today" if today else ""}">{inner}</div>'
    minw = "220px" if detailed else "92px"
    return (f'<div class="tl{" day" if detailed else ""}"><div class="tl-grid" style="--cols:{len(days)};'
            f'--minw:{minw};--h:{height}px;--pph:{pph}px">{head}<div class="tl-gutter">{gutter}</div>{cols}'
            '</div></div>')


LEGEND = _flat(f"""
<div class="legend">
  <span><i style="background:{HIGH}"></i>Problem sets</span><span><i style="background:{MID}"></i>Review</span>
  <span><i style="background:#2FA8FF"></i>Reading</span><span><i style="background:#C04CFF"></i>Memorization</span>
  <span><i style="background:repeating-linear-gradient(135deg,#D9DBEA 0 3px,#F5F6FB 3px 6px);border:1px solid {INK}"></i>Classes &amp; fixed</span>
  <span>⚡ fits your energy then</span>
  <span><i style="background:linear-gradient({LOW},{MID},{HIGH})"></i>left strip: your typical energy</span>
</div>""")


def block_row(b):
    """A Today-list row for any block (session or class)."""
    tint = _tint(b)
    if b["kind"] in ("class", "other"):
        cls, kind, status = "", "Class" if b["kind"] == "class" else "Fixed", b["status"]
        status = {"Class": "Class", "Now": "Now", "Done": "Done"}[status]
    else:
        cls = {"Completed": "done", "Done": "done", "Missed": "missed", "In progress": "now"}.get(b["status"], "")
        kind = TaskType(b["task_type"]).label.capitalize() if b["task_type"] else "Break"
        status = "Done" if b["status"] in ("Completed", "Done") else b["status"]
    st.markdown(_flat(f"""
    <div class="row {cls}" style="--tint:{tint}">
      <div class="t">{b["start"]:%H:%M}</div>
      <div><div class="n">{b["title"]}{" ⚡" if b["fits"] else ""}</div>
           <div class="k">{kind}, {b["minutes"]} min</div></div>
      <div class="st">{status}</div>
    </div>"""), unsafe_allow_html=True)


# ==========================================================
# SIDEBAR
# ==========================================================

with st.sidebar:
    st.markdown('<div class="brand">The 12th Interface</div>'
                '<div class="brand-sub">Your study companion</div>', unsafe_allow_html=True)
    if st.session_state.get("goto"):
        st.session_state.nav = st.session_state.pop("goto")
    page = st.radio("Navigation", ["Home", "My Schedule", "Insights", "Study Mode", "Replanning"],
                    label_visibility="collapsed", key="nav")
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
                   + "\n\nNext: open **My Schedule** and tell the assistant your classes and what's due. "
                   "It'll arrange your week around your energy.")
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
        today_blocks = [b for b in backend.day_blocks(datetime.now().astimezone().date()) if b["kind"] != "break"]
        upcoming = [b for b in today_blocks if b["status"] in ("In progress", "Upcoming", "Class", "Now")]
        for b in (upcoming or today_blocks)[:5]:
            block_row(b)
        if not today_blocks:
            st.caption("Nothing on today yet.")
            if st.button("Plan my week with the assistant", key="home_plan"):
                st.session_state.goto = "My Schedule"
                st.rerun()


# ==========================================================
# MY SCHEDULE
# ==========================================================

elif page == "My Schedule":
    st.markdown('<div class="form-title">My schedule</div>', unsafe_allow_html=True)
    week_items = [b for d in backend.week() for b in d["blocks"] if b["kind"] == "study"]
    planned = sum(b["minutes"] for b in week_items)
    st.markdown(f'<p class="quiet">{len(week_items)} study sessions this week ({planned // 60}h {planned % 60}m), '
                f'{len(backend.classes)} classes and fixed blocks, {len(backend.todo)} things on your list.</p>',
                unsafe_allow_html=True)
    with st.container(key="viewpills"):
        view = st.radio("View", ["Plan with me", "Week", "Day"], horizontal=True,
                        label_visibility="collapsed", key="sched_view")

    if view == "Plan with me":
        talk, side = st.columns([1.55, 1], gap="large")
        with talk:
            box = st.container(key="chatbox", height=560)
            with box:
                for msg in backend.chat_log:
                    with st.chat_message(msg["role"], avatar="🌙" if msg["role"] == "assistant" else None):
                        st.markdown(msg["text"])
            said = st.chat_input("Type a class, a task, or 'plan my week'…", key="chat_in")
            if said:
                backend.chat(said)
                st.rerun()
        with side:
            panel = st.container(key="listpanel")
            with panel:
                st.markdown('<div class="section" style="margin-top:0">Your list</div>', unsafe_allow_html=True)
                if backend.classes:
                    st.markdown('<div class="quiet" style="margin-bottom:6px">Fixed every week</div>',
                                unsafe_allow_html=True)
                    st.markdown("".join(
                        f'<div class="chip" style="--tint:{INK}"><b>{c.title}</b><span>{c.when()}</span></div>'
                        for c in backend.classes), unsafe_allow_html=True)
                if backend.todo:
                    st.markdown('<div class="quiet" style="margin:10px 0 6px 0">To do</div>', unsafe_allow_html=True)
                    st.markdown("".join(
                        f'<div class="chip" style="--tint:{TASK_TINT.get(t.task_type, MID)}"><b>{t.title}</b>'
                        f'<span>{t.minutes // 60}h{t.minutes % 60:02d} · due {t.due:%a %-d}</span></div>'
                        for t in sorted(backend.todo, key=lambda t: t.due)), unsafe_allow_html=True)
                if not backend.classes and not backend.todo:
                    st.caption("Empty for now. Tell the assistant your classes first, then what's due.")
                st.write("")
                def _plan_and_show():
                    backend.chat("plan my week")
                    st.session_state.sched_view = "Week"

                st.button("Plan my week", type="primary", width="stretch", key="chat_plan",
                          disabled=not backend.todo, on_click=_plan_and_show)
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Show my list", width="stretch", key="chat_show"):
                        backend.chat("show")
                        st.rerun()
                with c2:
                    if st.button("Start over", width="stretch", key="chat_reset"):
                        backend.chat("start over")
                        st.rerun()
            st.caption("Tip: one thing per message. `CSCE 634 MWF 10:20-11:10`, "
                       "`stats homework due Friday 2h`, `remove stats homework`.")

    elif view == "Week":
        with st.container(key="weekpills"):
            which = st.radio("Week", ["This week", "Next week"], horizontal=True,
                             label_visibility="collapsed", key="week_pick")
        today = datetime.now().astimezone().date()
        monday = today - timedelta(days=today.weekday()) + timedelta(days=7 if which == "Next week" else 0)
        days = backend.week(monday)
        st.markdown(f'<p class="quiet">{monday:%B} {monday.day} – {(monday + timedelta(days=6)):%B} '
                    f'{(monday + timedelta(days=6)).day}</p>', unsafe_allow_html=True)
        st.markdown(timeline_html(days), unsafe_allow_html=True)
        st.markdown(LEGEND, unsafe_allow_html=True)
        if not any(d["blocks"] for d in days):
            st.info("Nothing here yet. Go to **Plan with me** and tell the assistant your classes and tasks.")

    else:  # Day
        today = datetime.now().astimezone().date()
        options = [today + timedelta(days=i) for i in range(7)]
        with st.container(key="daypills"):
            picked = st.radio("Day", options, horizontal=True, label_visibility="collapsed", key="day_pick",
                              format_func=lambda d: "Today" if d == today else f"{d:%a} {d.day}")
        blocks = backend.day_blocks(picked)
        left, right = st.columns([1.5, 1], gap="large")
        with left:
            st.markdown(timeline_html([{"date": picked, "blocks": blocks}], detailed=True, pph=56),
                        unsafe_allow_html=True)
        with right:
            st.markdown('<div class="section" style="margin-top:0">Sessions</div>', unsafe_allow_html=True)
            sessions = [b for b in blocks if b["kind"] == "study"]
            for b in sessions:
                block_row(b)
                if b["status"] not in ("Completed", "Done") and st.button(
                    "Mark done", key=f"complete_{b['session_id']}", type="tertiary"
                ):
                    backend.mark_completed(b["session_id"])
                    st.rerun()
            if not sessions:
                st.caption("No study sessions this day.")
            if picked == today and backend.deferred:
                st.caption("Moved to tomorrow: " + ", ".join(e["title"] for e in backend.deferred))
            with st.expander("Add a session by hand"):
                with st.form("add_session_form"):
                    new_task = st.text_input("What are you studying?", placeholder="e.g. Database assignment")
                    new_type = st.selectbox("Kind of task", TASK_TYPES, format_func=lambda t: t.label.capitalize())
                    base = datetime.combine(picked, datetime.min.time()).astimezone()
                    slots = [base.replace(hour=h, minute=m) for h in range(7, 23) for m in (0, 15, 30, 45)]
                    new_time = st.selectbox("Start", slots, index=8, format_func=lambda t: t.strftime("%H:%M"))
                    duration = st.selectbox("Length (minutes)", [15, 25, 30, 45, 60, 90], index=3)
                    submitted = st.form_submit_button("Add session", type="primary", width="stretch")
                if submitted:
                    if new_task.strip():
                        backend.add_session(new_task.strip(), new_time, duration, new_type)
                        st.rerun()
                    else:
                        st.warning("Give the session a name first.")
        st.caption(f"Right now {plan['task_label']} fits best: {plan['why']}.")


# ==========================================================
# INSIGHTS
# ==========================================================

elif page == "Insights":
    info = backend.insights()
    curve = backend.energy_curve()
    checkins = backend.checkin_history()
    low_time, low = min(curve, key=lambda x: x[1])
    study_h = info["study_min"] / 60
    st.markdown('<div class="form-title">Insights</div>', unsafe_allow_html=True)
    st.markdown(f'<p class="quiet">Week of {info["week_start"]:%B} {info["week_start"].day}, '
                f"from your real schedule, sleep and check-ins.</p>", unsafe_allow_html=True)

    fit = "–" if info["fit_pct"] is None else f'{info["fit_pct"]}%'
    done_pct = round(100 * info["done_min"] / info["study_min"]) if info["study_min"] else 0
    st.markdown(_flat(f"""
    <div class="kpis">
      <div class="kpi"><div class="v">{study_h:.1f}h</div><div class="l">study planned this week</div></div>
      <div class="kpi"><div class="v" style="color:{SIGNAL}">{fit}</div><div class="l">of it matches your energy ⚡</div></div>
      <div class="kpi"><div class="v">{done_pct}%</div><div class="l">done so far ({info["done_n"]} sessions)</div></div>
      <div class="kpi"><div class="v" style="color:{HIGH}">{_clock(info["peak_start"])}</div><div class="l">your sharpest 2 hours start</div></div>
    </div>"""), unsafe_allow_html=True)

    # Plain-language insights, each from a real number.
    tips = []
    today_classes = [b for b in backend.day_blocks(datetime.now().astimezone().date()) if b["kind"] == "class"]
    peak_h = _hour_of(info["peak_start"])
    clash = [b for b in today_classes if b["start"].hour < peak_h + 2 and b["end"].hour + b["end"].minute / 60 > peak_h]
    if clash:
        tips.append(("🎯", (f"Your peak ({_clock(info['peak_start'])}) overlaps <b>{clash[0]['title']}</b> today, so "
                     "save hard problem sets for your next-best stretch, and use the class itself as active focus time.")))
    else:
        tips.append(("🎯", (f"Your sharpest window starts around <b>{_clock(info['peak_start'])}</b> "
                     f"(~{info['peak_pct']}% energy). That's where I put problem sets first.")))
    tips.append(("🌙", (f"Your energy dips lowest around <b>{_clock(low_time)}</b> ({low}%). "
                 "Reading and flashcards go there, not new problems.")))
    short = [d for d in info["deadlines"] if d["status"] in ("Short on time", "Not planned yet")]
    if short:
        d = short[0]
        tips.append(("⚠️", (f"<b>{d['title']}</b> is due in {max(d['days_left'], 0)} day"
                     f"{'s' if d['days_left'] != 1 else ''} with {d['planned'] // 60}h{d['planned'] % 60:02d} of "
                     f"{d['needed'] // 60}h{d['needed'] % 60:02d} planned. Say <b>plan my week</b> to fit the rest.")))
    if info["busiest"]:
        b = info["busiest"]
        tips.append(("📅", (f"<b>{b['date']:%A}</b> is your heaviest day: {(b['study'] + b['fixed']) / 60:.1f}h of "
                     "classes and study. Keep that evening light.")))
    if info["fit_pct"] is not None and info["fit_pct"] < 60:
        tips.append(("🔁", "Less than 60% of your study time fits your energy. Re-planning usually fixes that."))
    if info["missed_n"]:
        tips.append(("🧭", (f"You missed {info['missed_n']} session{'s' if info['missed_n'] != 1 else ''} this week. "
                     "Use Replanning to move it instead of skipping it.")))
    if backend.sleep_hours < 7:
        tips.append(("😴", (f"{backend.sleep_hours:g}h of sleep last night lowers today's curve. "
                     "An extra hour tonight lifts tomorrow's energy.")))
    if not backend.todo and not backend.classes:
        tips = [("💬", ("Tell the assistant in <b>My Schedule</b> your classes and what's due, "
                 "and these insights fill in from your real week."))]
    st.markdown('<div class="section">What I notice</div>', unsafe_allow_html=True)
    st.markdown("".join(f'<div class="tip"><div class="ic">{ic}</div><div>{t}</div></div>' for ic, t in tips),
                unsafe_allow_html=True)

    st.markdown('<div class="section">Your energy today</div>', unsafe_allow_html=True)
    fig = day_curve_figure(curve, checkins, pct, 340)
    for b in today_classes:
        fig.add_vrect(x0=b["start"].hour + b["start"].minute / 60, x1=b["end"].hour + b["end"].minute / 60,
                      fillcolor=INK, opacity=0.07, line_width=0, annotation_text=b["title"],
                      annotation_position="top left", annotation_font_size=11, annotation_font_color=MUTED)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption(f"From {backend.sleep_hours:g}h of sleep and {len(checkins)} check-in"
               f"{'s' if len(checkins) != 1 else ''} today. Shaded: your classes.")

    left, right = st.columns([1.5, 1], gap="large")
    with left:
        st.markdown('<div class="section">Your week at a glance</div>', unsafe_allow_html=True)
        labels = [f"{d['date']:%a} {d['date'].day}" for d in info["per_day"]]
        week = go.Figure()
        week.add_trace(go.Bar(x=labels, y=[d["fixed"] / 60 for d in info["per_day"]], name="Classes & fixed",
                              marker_color="#C9CCE4", marker_line_width=0,
                              hovertemplate="%{y:.1f}h classes<extra></extra>"))
        week.add_trace(go.Bar(x=labels, y=[d["study"] / 60 for d in info["per_day"]], name="Study",
                              marker_color=SIGNAL, marker_line_width=0,
                              hovertemplate="%{y:.1f}h study<extra></extra>"))
        week.update_layout(
            barmode="stack", height=300, margin={"l": 8, "r": 8, "t": 30, "b": 8}, bargap=0.45,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font={"family": "Archivo, sans-serif", "color": MUTED}, hoverlabel={"bgcolor": INK},
            yaxis={"title": "hours", "gridcolor": LINE}, legend={"orientation": "h", "y": 1.15},
        )
        st.plotly_chart(week, width="stretch", config={"displayModeBar": False})
    with right:
        st.markdown('<div class="section">Where study time goes</div>', unsafe_allow_html=True)
        mix = {k: v for k, v in info["by_type"].items() if v}
        if mix:
            donut = go.Figure(go.Pie(
                labels=[TaskType(k).label.capitalize() for k in mix], values=[v / 60 for v in mix.values()],
                hole=0.62, sort=False, marker={"colors": [TASK_TINT[k] for k in mix], "line": {"color": "#fff", "width": 3}},
                textinfo="none", hovertemplate="%{label}: %{value:.1f}h<extra></extra>",
            ))
            donut.update_layout(
                height=300, margin={"l": 8, "r": 8, "t": 10, "b": 8}, paper_bgcolor="rgba(0,0,0,0)",
                font={"family": "Archivo, sans-serif", "color": MUTED}, legend={"orientation": "h", "y": -0.05},
                annotations=[{"text": f"<b>{study_h:.1f}h</b>", "showarrow": False,
                              "font": {"size": 26, "color": INK, "family": "Archivo"}}],
            )
            st.plotly_chart(donut, width="stretch", config={"displayModeBar": False})
        else:
            st.caption("No study sessions this week yet.")

    st.markdown('<div class="section">Deadlines</div>', unsafe_allow_html=True)
    if info["deadlines"]:
        rows = ""
        for d in info["deadlines"]:
            pct_planned = min(100, round(100 * max(d["planned"], d["done"]) / d["needed"])) if d["needed"] else 100
            css = "ok" if d["status"] in ("Planned", "Done") else "warn"
            when = "today" if d["days_left"] == 0 else "overdue" if d["days_left"] < 0 else f"in {d['days_left']}d"
            rows += _flat(f"""
            <div class="dl" style="--tint:{TASK_TINT.get(d['task_type'], MID)}">
              <div><div class="n">{d['title']}</div>
                   <div class="k">due {d['due']:%a %b} {d['due'].day} ({when}) · {d['planned'] // 60}h{d['planned'] % 60:02d}
                   planned of {d['needed'] // 60}h{d['needed'] % 60:02d}</div></div>
              <div class="bar"><i style="width:{pct_planned}%"></i></div>
              <div class="st {css}">{d['status']}</div>
            </div>""")
        st.markdown(rows, unsafe_allow_html=True)
    else:
        st.caption("No deadlines yet. Tell the assistant what's due.")


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


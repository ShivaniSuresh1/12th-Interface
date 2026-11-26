"""The 12th Interface: student dashboard (Streamlit), wired to the live planner.

Run from the repo root:

    pip install -r frontend/requirements.txt
    streamlit run frontend/app.py

Every number, recommendation, "why" and replan on this page comes from
StudySessionPlanner through integration.dashboard.DashboardSession. The only
illustrative data left is the weekly chart on the Insights page, and it is
labelled as sample data.

Visual idea: your day is a curve. Energy is drawn on one scale everywhere
(deep blue = low, lavender = moderate, sunrise peach = high), and the energy
curve with a "now" marker is the one element the whole design leans on.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

# Let `streamlit run frontend/app.py` find the src/ packages without PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain_model import TaskType
from domain_model.onboarding import QUESTIONS as PREFERENCE_QUESTIONS
from integration.dashboard import DISRUPTIONS, FEELINGS, DashboardSession
from integration.storage import ProfileStore, student_id_for
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

INK = "#0F1533"  # page
PANEL = "#182047"  # raised surfaces
LINE = "#2A3366"  # hairlines
TEXT = "#EEF0FA"
MUTED = "#9AA3C7"
LOW = "#4C5FD5"  # energy: deep blue
MID = "#9A86F2"  # energy: lavender
HIGH = "#FFB088"  # energy: sunrise peach

TASK_TINT = {
    "problem_set": HIGH,
    "review": MID,
    "reading": "#7FB2F0",
    "memorization": "#C9A7F5",
}


def energy_color(pct: int) -> str:
    """Same cut points as the planner (33% / 66%)."""
    return LOW if pct < 33 else MID if pct < 66 else HIGH


st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,600;12..96,800&family=Figtree:wght@400;500;600&display=swap');

html, body, [data-testid="stAppViewContainer"] {{
    background: {INK};
    color: {TEXT};
    font-family: 'Figtree', system-ui, sans-serif;
}}
[data-testid="stAppViewContainer"] {{
    background:
        radial-gradient(1200px 500px at 85% -10%, rgba(154,134,242,0.16), transparent 60%),
        radial-gradient(900px 400px at -10% 110%, rgba(76,95,213,0.18), transparent 60%),
        {INK};
}}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stMainBlockContainer"] {{ max-width: 1180px; padding-top: 2.2rem; }}

h1, h2, h3, .display, .hero-title, .form-title, .hello, .brand, .section, .task, .big {{
    font-family: 'Bricolage Grotesque', sans-serif !important;
    letter-spacing: -0.02em;
    color: {TEXT};
}}
p, li, label, .stMarkdown {{ font-size: 16px; line-height: 1.55; }}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {{
    background: rgba(24,32,71,0.92);
    border-right: 1px solid {LINE};
}}
.brand {{
    font-family: 'Bricolage Grotesque', sans-serif;
    font-weight: 800; font-size: 22px; letter-spacing: -0.03em;
    margin: 4px 0 2px 0;
}}
.brand-sub {{ color: {MUTED}; font-size: 14px; margin-bottom: 18px; }}
.who {{
    display: flex; align-items: center; gap: 10px;
    padding: 10px 12px; border-radius: 14px; background: {INK};
    border: 1px solid {LINE}; margin: 8px 0 14px 0;
}}
.who .dot {{ width: 30px; height: 30px; border-radius: 50%;
    display: grid; place-items: center; font-weight: 700; color: {INK}; }}
.who .n {{ font-weight: 600; }}
.who .s {{ color: {MUTED}; font-size: 13px; }}

/* radios: no circles; navigation is a list, the check-in is a row of pills */
[data-testid="stRadioOption"] > div > div:first-child:not([data-testid]) {{ display: none; }}
[data-testid="stSidebar"] [data-testid="stRadioOption"] {{
    padding: 9px 14px; border-radius: 12px; margin-bottom: 2px; width: 100%;
    border: 1px solid transparent; color: {MUTED};
}}
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] {{
    background: {INK}; border-color: {LINE}; color: {TEXT};
}}
[data-testid="stSidebar"] [data-testid="stRadioOption"] p {{ font-weight: 500; }}

/* ---------- buttons & inputs ---------- */
.stButton > button, .stFormSubmitButton > button {{
    border-radius: 999px; font-weight: 600; padding: 0.55rem 1.2rem;
    border: 1px solid {LINE}; background: transparent; color: {TEXT};
}}
.stButton > button[kind^="primary"], .stFormSubmitButton > button[kind^="primary"] {{
    background: linear-gradient(90deg, {MID}, {HIGH});
    color: {INK}; border: none;
}}
.stButton > button:focus-visible, .stFormSubmitButton > button:focus-visible {{
    outline: 2px solid {HIGH}; outline-offset: 2px;
}}
[data-testid="stForm"] {{ border: none; padding: 0; }}
div[data-baseweb="input"], div[data-baseweb="select"] > div {{
    background: {INK} !important; border-radius: 12px !important;
}}

/* check-in radio as pills */
.st-key-pills [role="radiogroup"] {{ gap: 8px; flex-wrap: wrap; }}
.st-key-pills [data-testid="stRadioOption"] {{
    border: 1px solid {LINE}; border-radius: 999px; padding: 7px 18px; margin: 0;
}}
.st-key-pills [data-testid="stRadioOption"][data-selected="true"] {{ background: {TEXT}; }}
.st-key-pills [data-testid="stRadioOption"][data-selected="true"] p {{ color: {INK}; }}

/* alerts in the palette instead of stock green */
[data-testid="stAlert"] > div {{
    background: rgba(154,134,242,0.12) !important; border: 1px solid {LINE};
    border-radius: 16px; color: {TEXT} !important;
}}
[data-testid="stAlert"] p, [data-testid="stAlert"] li {{ color: {TEXT} !important; }}

/* ---------- surfaces ---------- */
.st-key-addpanel {{
    background: {PANEL}; border: 1px solid {LINE}; border-radius: 22px; padding: 18px 20px;
}}
.panel {{
    background: {PANEL}; border: 1px solid {LINE};
    border-radius: 22px; padding: 22px 24px;
}}
.hello {{ font-size: clamp(30px, 4vw, 44px); font-weight: 600; margin: 0; line-height: 1.1; }}
.date {{ color: {MUTED}; margin-top: 6px; }}
.big {{
    font-family: 'Bricolage Grotesque', sans-serif; font-weight: 800;
    font-size: clamp(64px, 9vw, 104px); line-height: 0.9; letter-spacing: -0.05em;
}}
.state {{ font-size: 20px; font-weight: 600; margin-top: 8px; }}
.quiet {{ color: {MUTED}; font-size: 14px; }}
.task {{
    font-family: 'Bricolage Grotesque', sans-serif; font-weight: 600;
    font-size: 30px; letter-spacing: -0.02em; margin: 2px 0 8px 0;
}}
.why {{ font-size: 17px; line-height: 1.6; color: {TEXT}; max-width: 46ch; }}
.section {{
    font-family: 'Bricolage Grotesque', sans-serif; font-weight: 600;
    font-size: 21px; margin: 28px 0 12px 0;
}}

/* schedule rows: a coloured spine shows the kind of task */
.row {{
    display: grid; grid-template-columns: 78px 1fr auto; gap: 14px; align-items: center;
    padding: 12px 16px; border-radius: 16px; background: {PANEL};
    border: 1px solid {LINE}; margin-bottom: 8px;
    border-left: 4px solid var(--tint);
}}
.row .t {{ color: {MUTED}; font-variant-numeric: tabular-nums; }}
.row .n {{ font-weight: 600; }}
.row .k {{ color: {MUTED}; font-size: 14px; }}
.row .st {{ font-size: 13px; padding: 3px 10px; border-radius: 999px; border: 1px solid {LINE}; color: {MUTED}; }}
.row.done {{ opacity: 0.55; }}
.row.missed .st {{ color: {HIGH}; border-color: rgba(255,176,136,0.4); }}
.row.now {{ background: linear-gradient(90deg, rgba(154,134,242,0.18), {PANEL}); }}
.row.now .st {{ color: {INK}; background: {TEXT}; border-color: {TEXT}; }}

/* ---------- landing ---------- */
.hero-title {{
    font-family: 'Bricolage Grotesque', sans-serif; font-weight: 800;
    font-size: clamp(44px, 7vw, 88px); line-height: 0.95; letter-spacing: -0.045em;
    margin: 0 0 18px 0; max-width: 12ch;
}}
.hero-sub {{ font-size: 19px; color: {MUTED}; max-width: 44ch; line-height: 1.55; }}
.curve-svg {{ width: 100%; height: auto; display: block; margin: 8px 0 4px 0; }}
.curve-svg .draw {{
    stroke-dasharray: 1400; stroke-dashoffset: 1400;
    animation: draw 2.4s cubic-bezier(.6,.1,.2,1) .2s forwards;
}}
.curve-svg .fill {{ opacity: 0; animation: fade 1s ease 1.8s forwards; }}
.curve-svg .sun {{ opacity: 0; animation: fade .6s ease 2.4s forwards; }}
@keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
@keyframes fade {{ to {{ opacity: 1; }} }}
@media (prefers-reduced-motion: reduce) {{
    .curve-svg .draw {{ animation: none; stroke-dashoffset: 0; }}
    .curve-svg .fill, .curve-svg .sun {{ animation: none; opacity: 1; }}
}}
.how {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-top: 28px; }}
.how div {{ border-top: 1px solid {LINE}; padding-top: 14px; }}
.how b {{ display: block; font-family: 'Bricolage Grotesque', sans-serif; font-size: 18px; margin-bottom: 4px; }}
.how span {{ color: {MUTED}; font-size: 15px; }}
.step {{ color: {MUTED}; font-size: 15px; margin-bottom: 6px; }}
.bar {{ height: 4px; border-radius: 4px; background: {LINE}; margin: 6px 0 26px 0; overflow: hidden; }}
.bar i {{ display: block; height: 100%; background: linear-gradient(90deg, {LOW}, {MID}, {HIGH}); }}
.form-title {{
    font-family: 'Bricolage Grotesque', sans-serif; font-weight: 600;
    font-size: clamp(30px, 4vw, 42px); letter-spacing: -0.03em; margin: 0 0 8px 0;
}}
.footnote {{ color: {MUTED}; font-size: 13px; margin-top: 48px; }}

@media (max-width: 760px) {{
    .how {{ grid-template-columns: 1fr; }}
    .row {{ grid-template-columns: 64px 1fr; }}
    .row .st {{ grid-column: 2; justify-self: start; }}
}}
</style>
""", unsafe_allow_html=True)


# ==========================================================
# STATE
# ==========================================================

# Saved students live in <repo>/profiles/ (gitignored), one JSON file each.
# TWELFTH_PROFILE_DIR overrides it (the UI tests use a temp folder).
store = ProfileStore(
    Path(os.environ.get("TWELFTH_PROFILE_DIR") or Path(__file__).resolve().parents[1] / "profiles")
)

for key, value in {
    "view": "landing",  # landing | signup | signin (before a student is signed in)
    "signup_step": 1,
    "signup": {},
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
    st.session_state.signup_step = 1


# ==========================================================
# SHARED PIECES
# ==========================================================

def landing_curve() -> str:
    """A day drawn as an energy curve, morning rise, afternoon dip, evening fade."""
    path = (
        "M0,190 C60,185 90,120 150,90 S250,40 300,52 "
        "S380,120 430,118 S520,70 580,82 S700,150 800,175"
    )
    return f"""
    <svg class="curve-svg" viewBox="0 0 800 230" role="img"
         aria-label="A day's energy: rising in the morning, dipping after lunch, fading at night">
      <defs>
        <linearGradient id="g" x1="0" x2="1">
          <stop offset="0" stop-color="{LOW}"/><stop offset=".35" stop-color="{HIGH}"/>
          <stop offset=".55" stop-color="{MID}"/><stop offset=".72" stop-color="{HIGH}"/>
          <stop offset="1" stop-color="{LOW}"/>
        </linearGradient>
        <linearGradient id="f" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stop-color="{MID}" stop-opacity=".28"/>
          <stop offset="1" stop-color="{MID}" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <path class="fill" d="{path} L800,220 L0,220 Z" fill="url(#f)"/>
      <path class="draw" d="{path}" fill="none" stroke="url(#g)" stroke-width="5" stroke-linecap="round"/>
      <g class="sun" font-family="Figtree, sans-serif" font-size="22" fill="{TEXT}">
        <circle cx="300" cy="52" r="7" fill="{HIGH}"/>
        <text x="250" y="28">problem sets here</text>
        <circle cx="430" cy="118" r="7" fill="{MID}"/>
        <text x="360" y="160">review after lunch</text>
        <circle cx="740" cy="160" r="7" fill="{LOW}"/>
        <text x="560" y="214">flashcards before bed</text>
      </g>
    </svg>
    """


def day_curve_figure(curve, checkins, now_pct, height=300):
    """The planner's estimate for each hour today, with a marker at 'now'."""
    hours = [8 + i for i in range(len(curve))]
    values = [p for _t, p in curve]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hours, y=values, mode="lines", name="Estimated energy",
        line={"color": MID, "width": 4, "shape": "spline", "smoothing": 1.1},
        fill="tozeroy", fillcolor="rgba(154,134,242,0.12)",
        hovertemplate="%{customdata}: %{y}%<extra></extra>",
        customdata=[t for t, _p in curve],
    ))
    fig.add_trace(go.Scatter(
        x=hours, y=values, mode="markers", showlegend=False, hoverinfo="skip",
        marker={"size": 7, "color": [energy_color(v) for v in values]},
    ))
    if checkins:
        fig.add_trace(go.Scatter(
            x=[_hour_of(t) for t, _p in checkins], y=[p for _t, p in checkins],
            mode="markers", name="Your check-ins",
            marker={"size": 13, "color": TEXT, "symbol": "diamond", "line": {"color": INK, "width": 2}},
            hovertemplate="check-in: %{y}%<extra></extra>",
        ))
    now = datetime.now()
    now_x = now.hour + now.minute / 60
    if hours[0] <= now_x <= hours[-1]:
        fig.add_vline(x=now_x, line_width=1, line_dash="dot", line_color=TEXT)
        fig.add_trace(go.Scatter(
            x=[now_x], y=[now_pct], mode="markers+text", text=["now"], textposition="top center",
            textfont={"color": TEXT, "size": 13}, showlegend=False, hoverinfo="skip",
            marker={"size": 16, "color": energy_color(now_pct), "line": {"color": INK, "width": 3}},
        ))
    fig.update_layout(
        height=height, margin={"l": 8, "r": 8, "t": 18, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Figtree, sans-serif", "color": MUTED, "size": 12},
        showlegend=bool(checkins), legend={"orientation": "h", "y": 1.12, "x": 0},
        hoverlabel={"bgcolor": PANEL, "font_color": TEXT},
    )
    fig.update_xaxes(
        tickvals=hours[::2],
        ticktext=[datetime(2000, 1, 1, h).strftime("%I %p").lstrip("0").lower() for h in hours[::2]],
        showgrid=False, zeroline=False,
    )
    fig.update_yaxes(range=[0, 100], ticksuffix="%", gridcolor=LINE, zeroline=False, tickvals=[33, 66])
    return fig


def _hour_of(label: str) -> float:
    t = datetime.strptime(label, "%I:%M %p")
    return t.hour + t.minute / 60


def schedule_row(item):
    tint = TASK_TINT.get(item.get("task_type_value") or "", LINE)
    cls = {"Completed": "done", "Done": "done", "Missed": "missed", "In progress": "now"}.get(
        item["status"], ""
    )
    status = "Done" if item["status"] in ("Completed", "Done") else item["status"]
    st.markdown(f"""
    <div class="row {cls}" style="--tint:{tint}">
        <div class="t">{item["time"]}</div>
        <div><div class="n">{item["task"]}</div>
             <div class="k">{item["task_type"].capitalize()}, {item["duration"]}</div></div>
        <div class="st">{status}</div>
    </div>
    """, unsafe_allow_html=True)


def with_tint(items):
    """Attach the TaskType value so rows can be coloured by kind of task."""
    labels = {t.label: t.value for t in TaskType}
    return [{**i, "task_type_value": labels.get(i["task_type"])} for i in items]


# ==========================================================
# BEFORE SIGN-IN: landing, get started (3 steps), sign in
# ==========================================================

def hide_sidebar():
    st.markdown(
        '<style>[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"]'
        "{display:none}</style>",
        unsafe_allow_html=True,
    )


def landing():
    left, right = st.columns([1.05, 1], gap="large")
    with left:
        st.markdown('<div class="brand">The 12th Interface</div>', unsafe_allow_html=True)
        st.markdown(
            '<h1 class="hero-title">Study with your energy, not against it.</h1>'
            '<p class="hero-sub">Tell it how you slept. It estimates your energy through the day, '
            "suggests the kind of studying that fits right now, and explains why.</p>",
            unsafe_allow_html=True,
        )
        a, b, _ = st.columns([1, 1, 0.6])
        with a:
            if st.button("Get started", type="primary", width="stretch"):
                go_to("signup")
                st.rerun()
        with b:
            if st.button("Sign in", width="stretch"):
                go_to("signin")
                st.rerun()
    with right:
        st.markdown('<div style="height:110px"></div>', unsafe_allow_html=True)
        st.markdown(landing_curve(), unsafe_allow_html=True)

    st.markdown("""
    <div class="how">
      <div><b>Starts from your sleep</b><span>A short night lowers the whole curve. No wearable needed.</span></div>
      <div><b>One-tap check-ins</b><span>Tired, fine or energized. The estimate adjusts to how you actually feel.</span></div>
      <div><b>Plans that bend</b><span>Meeting ran late? It proposes a change and asks first. Nothing moves silently.</span></div>
    </div>
    <div class="footnote">A CSCE 634 prototype. Please don't enter anything private;
    saved profiles may be reset when the site restarts.</div>
    """, unsafe_allow_html=True)


STEPS = 3


def signup():
    step = st.session_state.signup_step
    data = st.session_state.signup
    _, mid, _ = st.columns([1, 1.6, 1])
    with mid:
        st.markdown('<div class="brand">The 12th Interface</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="step">Step {step} of {STEPS}</div>'
            f'<div class="bar"><i style="width:{step / STEPS * 100:.0f}%"></i></div>',
            unsafe_allow_html=True,
        )

        if step == 1:
            st.markdown('<h2 class="form-title">What should I call you?</h2>', unsafe_allow_html=True)
            st.markdown('<p class="quiet">You\'ll use this name to sign in next time.</p>',
                        unsafe_allow_html=True)
            with st.form("step_name"):
                name = st.text_input("Name", value=data.get("name", ""), placeholder="e.g. Priya")
                nxt = st.form_submit_button("Continue", type="primary", width="stretch")
            if nxt:
                try:
                    student_id = student_id_for(name)
                except ValueError as e:
                    st.warning(str(e))
                else:
                    if store.exists(student_id):
                        st.warning(f"{name.strip()} already has a profile. Sign in instead, or pick another name.")
                    else:
                        data.update(name=name.strip(), student_id=student_id)
                        st.session_state.signup_step = 2
                        st.rerun()

        elif step == 2:
            st.markdown(f'<h2 class="form-title">How do you usually sleep, {data["name"]}?</h2>',
                        unsafe_allow_html=True)
            st.markdown('<p class="quiet">Your energy estimate starts from this. '
                        "You can log last night's sleep any day from the sidebar.</p>",
                        unsafe_allow_html=True)
            with st.form("step_sleep"):
                hours = st.number_input(
                    "Hours of sleep on a typical night",
                    min_value=0.0, max_value=float(MAX_SURVEY_SLEEP_HOURS),
                    value=float(data.get("hours", 7.5)), step=0.5,
                )
                wake = st.time_input(
                    "Usual wake-up time",
                    value=data.get("wake", datetime.strptime("07:30", "%H:%M").time()), step=900,
                )
                nxt = st.form_submit_button("Continue", type="primary", width="stretch")
            if nxt:
                data.update(hours=hours, wake=wake)
                st.session_state.signup_step = 3
                st.rerun()

        else:
            st.markdown('<h2 class="form-title">What do you like to study when…</h2>', unsafe_allow_html=True)
            st.markdown('<p class="quiet">Not sure? Leave it on no preference and I\'ll learn from '
                        "what you pick.</p>", unsafe_allow_html=True)
            with st.form("step_prefs"):
                options = [None, *TASK_TYPES]
                prefs = {}
                short = {"low": "…you're tired?", "medium": "…your energy is so-so?",
                         "high": "…you're energized?"}
                for bucket in PREFERENCE_QUESTIONS:
                    prefs[bucket] = st.selectbox(
                        short[bucket], options,
                        format_func=lambda t: "No preference" if t is None else t.label,
                        key=f"pref_{bucket}",
                    )
                done = st.form_submit_button("Create my plan", type="primary", width="stretch")
            if done:
                session = DashboardSession.onboard(
                    student_id=data["student_id"], name=data["name"],
                    typical_sleep_hours=data["hours"], typical_wake_time=data["wake"],
                    task_preferences=prefs,
                )
                store.save(session)
                st.session_state.backend = session
                st.session_state.just_onboarded = True
                st.session_state.signup = {}
                st.rerun()

        if st.button("Back", key="signup_back"):
            if step == 1:
                go_to("landing")
            else:
                st.session_state.signup_step = step - 1
            st.rerun()


def signin():
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        st.markdown('<div class="brand">The 12th Interface</div>', unsafe_allow_html=True)
        st.markdown('<h2 class="form-title">Welcome back</h2>'
                    '<p class="quiet">Enter the name you signed up with.</p>',
                    unsafe_allow_html=True)
        # Type your name rather than pick from a list, so a public deployment
        # never shows who else has a profile.
        with st.form("signin_form"):
            name = st.text_input("Name", placeholder="Your name")
            go_on = st.form_submit_button("Sign in", type="primary", width="stretch")
        if go_on:
            try:
                student_id = student_id_for(name)
            except ValueError as e:
                st.warning(str(e))
            else:
                if store.exists(student_id):
                    st.session_state.backend = store.load(student_id)
                    st.rerun()
                else:
                    st.warning("No profile with that name. Check the spelling, or get started as new.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Back", key="signin_back"):
                go_to("landing")
                st.rerun()
        with c2:
            if st.button("I'm new here", key="signin_new"):
                go_to("signup")
                st.rerun()


if "backend" not in st.session_state:
    hide_sidebar()
    {"landing": landing, "signup": signup, "signin": signin}[st.session_state.view]()
    st.stop()

backend: DashboardSession = st.session_state.backend


# ==========================================================
# SIDEBAR
# ==========================================================

with st.sidebar:
    st.markdown('<div class="brand">The 12th Interface</div>'
                '<div class="brand-sub">Your study companion</div>', unsafe_allow_html=True)

    page = st.radio(
        "Navigation",
        ["Home", "My Schedule", "Insights", "Study Mode", "Replanning"],
        label_visibility="collapsed",
    )

    sleep = st.number_input(
        "Last night's sleep (hours)",
        min_value=0.0, max_value=14.0, value=float(backend.sleep_hours), step=0.5,
        help="Your energy estimate starts from this.",
    )
    if sleep != backend.sleep_hours:
        backend.set_sleep(sleep)

    plan = backend.plan()
    pct = plan["energy_pct"]

    st.markdown(f"""
    <div class="who">
      <div class="dot" style="background:{energy_color(pct)}">{backend.name[:1].upper()}</div>
      <div><div class="n">{backend.name}</div><div class="s">{pct}% energy right now</div></div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Sign out", width="stretch"):
        store.save(backend)
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    st.caption("Progress saves automatically.")


schedule = with_tint(backend.schedule_items())
color = energy_color(pct)


# ==========================================================
# HOME
# ==========================================================

if page == "Home":
    now = datetime.now()
    part = "morning" if now.hour < 12 else "afternoon" if now.hour < 17 else "evening"
    st.markdown(
        f'<div class="hello">Good {part}, {backend.name}.</div>'
        f'<div class="date">{now.strftime("%A, %B")} {now.day}</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.just_onboarded:
        st.success(
            "You're set up. Here's where I'll start:\n\n"
            + "\n".join(f"- {line}" for line in backend.starting_suggestions())
            + "\n\nI added a sample study day so you can try things out."
        )
        st.session_state.just_onboarded = False

    st.write("")
    left, right = st.columns([0.9, 1.6], gap="large")
    with left:
        st.markdown(f"""
        <div class="big" style="color:{color}">{pct}%</div>
        <div class="state">{plan["energy_label"]}</div>
        <div class="quiet">{plan["energy_source"]}</div>
        """, unsafe_allow_html=True)
        st.markdown('<div class="section" style="margin-top:22px">How are you feeling?</div>',
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
        st.plotly_chart(
            day_curve_figure(backend.energy_curve(), backend.checkin_history(), pct, 330),
            width="stretch", config={"displayModeBar": False},
        )

    left, right = st.columns([1.1, 1], gap="large")
    with left:
        st.markdown('<div class="section">Up next for you</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="panel" style="border-left:4px solid {TASK_TINT.get(plan["task_type"], MID)}">
          <div class="task">{plan["task_label"].capitalize()}</div>
          <div class="why">I'd go with {plan["task_label"].lower()} {plan["why"]}.</div>
        </div>
        """, unsafe_allow_html=True)
        if plan["cold_start"]:
            st.caption("I'm still learning your patterns, so early suggestions lean on default rules.")
        st.write("")
        if st.button("Start this task", type="primary"):
            backend.start_task(plan["task_type"])
            st.session_state.notice = f"{plan['task_label']} started. It's waiting in Study Mode."
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
    st.markdown('<h2 class="form-title">My schedule</h2>', unsafe_allow_html=True)
    done = sum(1 for x in schedule if x["status"] == "Completed")
    st.markdown(f'<p class="quiet">{len(schedule)} sessions today, {done} done.</p>',
                unsafe_allow_html=True)

    left, right = st.columns([1.5, 1], gap="large")
    with left:
        for item in schedule:
            schedule_row(item)
            if item["status"] not in ("Completed", "Done") and st.button(
                "Mark done", key=f"complete_{item['session_id']}"
            ):
                backend.mark_completed(item["session_id"])
                st.rerun()
        if backend.deferred:
            st.caption("Moved to tomorrow: " + ", ".join(e["title"] for e in backend.deferred))
    with right:
        add_panel = st.container(key="addpanel")
        add_panel.markdown('<div class="section" style="margin-top:0">Add a session</div>',
                           unsafe_allow_html=True)
        with add_panel.form("add_session_form"):
            new_task = st.text_input("What are you studying?", placeholder="e.g. Database assignment")
            new_type = st.selectbox("Kind of task", TASK_TYPES, format_func=lambda t: t.label)
            today = datetime.now().astimezone()
            slots = [today.replace(hour=h, minute=m, second=0, microsecond=0)
                     for h in range(8, 22) for m in (0, 30)]
            new_time = st.selectbox("Start", slots,
                                    format_func=lambda t: t.strftime("%I:%M %p").lstrip("0"))
            duration = st.selectbox("Length (minutes)", [15, 25, 30, 45, 60, 90], index=3)
            submitted = st.form_submit_button("Add session", type="primary", width="stretch")
        if submitted:
            if new_task.strip():
                backend.add_session(new_task.strip(), new_time, duration, new_type)
                st.success("Session added.")
                st.rerun()
            else:
                st.warning("Give the session a name first.")
        st.caption(f"Right now {plan['task_label'].lower()} fits best: {plan['why']}.")


# ==========================================================
# INSIGHTS
# ==========================================================

elif page == "Insights":
    curve = backend.energy_curve()
    checkins = backend.checkin_history()
    peak_time, peak = max(curve, key=lambda x: x[1])
    low_time, low = min(curve, key=lambda x: x[1])

    st.markdown('<h2 class="form-title">Your energy today</h2>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="why">Your best stretch is around <b>{peak_time}</b> ({peak}%). '
        f"Expect the lowest point around <b>{low_time}</b> ({low}%). "
        f"That's from {backend.sleep_hours:g} hours of sleep and "
        f"{len(checkins)} check-in{'s' if len(checkins) != 1 else ''} today.</p>",
        unsafe_allow_html=True,
    )
    st.plotly_chart(day_curve_figure(curve, checkins, pct, 380), width="stretch",
                    config={"displayModeBar": False})
    st.caption("Change last night's sleep in the sidebar and watch the curve move.")

    st.markdown('<div class="section">This week</div>', unsafe_allow_html=True)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    sleep_week = [7.5, 6.5, 8, 7, 6, 9, 7.5]
    energy_week = [75, 55, 85, 65, 45, 90, 70]
    week = go.Figure()
    week.add_trace(go.Bar(x=days, y=sleep_week, name="Sleep (h)",
                          marker_color=[energy_color(e) for e in energy_week], marker_line_width=0))
    week.add_trace(go.Scatter(x=days, y=energy_week, name="Energy", yaxis="y2", mode="lines+markers",
                              line={"color": TEXT, "width": 2}))
    week.update_layout(
        height=300, margin={"l": 8, "r": 8, "t": 30, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Figtree, sans-serif", "color": MUTED},
        yaxis={"title": "Sleep (h)", "gridcolor": LINE},
        yaxis2={"title": "Energy %", "overlaying": "y", "side": "right", "range": [0, 100],
                "showgrid": False, "tickvals": [0, 33, 66, 100]},
        legend={"orientation": "h", "y": 1.15}, bargap=0.45,
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
        <div class="panel" style="padding:44px 40px; border-left:4px solid {TASK_TINT[active.value]}">
          <div class="quiet">You're studying</div>
          <div class="big" style="font-size:clamp(48px,7vw,84px)">{active.label.capitalize()}</div>
          <p class="why" style="margin-top:14px">One thing at a time. Finish when you're ready.</p>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        if st.button("Finish study session", type="primary"):
            backend.finish_task()
            st.session_state.notice = ""
            st.rerun()
    else:
        st.markdown('<h2 class="form-title">Ready to focus?</h2>', unsafe_allow_html=True)
        st.markdown(f'<p class="quiet">At {pct}% I\'d pick {plan["task_label"].lower()}, '
                    "but it's your call. What you choose teaches the planner what you like.</p>",
                    unsafe_allow_html=True)
        selected = st.selectbox(
            "What would you like to work on?", TASK_TYPES,
            index=TASK_TYPES.index(TaskType(plan["task_type"])),
            format_func=lambda t: t.label + ("  (suggested)" if t.value == plan["task_type"] else ""),
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
    st.markdown('<h2 class="form-title">Something changed?</h2>', unsafe_allow_html=True)
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
                      f'{start.strftime("%I:%M %p").lstrip("0")} to {end.strftime("%I:%M %p").lstrip("0")}')
        st.write("")
        st.markdown(f"""
        <div class="panel" style="border-left:4px solid {MID}">
          <div class="why" style="max-width:62ch">{proposal.message}</div>
          <div class="quiet" style="margin-top:10px">{detail}</div>
        </div>
        """, unsafe_allow_html=True)
        st.write("")

        if backend.is_ask(proposal):
            with st.form("ask_form", clear_on_submit=True):
                answer = st.text_input(
                    "What changed?",
                    placeholder="e.g. \"I'm wiped, 20 minutes max\" or \"let's do it tomorrow\"",
                )
                c1, c2 = st.columns(2)
                with c1:
                    sent = st.form_submit_button("Tell the planner", type="primary", width="stretch")
                with c2:
                    skipped = st.form_submit_button("Never mind", width="stretch")
            if sent or skipped:
                st.session_state.replan_result = backend.answer_ask(
                    proposal, answer if sent else "never mind"
                )
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
        for item in with_tint(backend.schedule_items()):
            schedule_row(item)


# Save after every interaction, so a restart (or the next visit) picks up here.
store.save(backend)

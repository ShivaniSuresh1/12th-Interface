
"""The 12th Interface: student dashboard (Streamlit), wired to the live planner.

Run from the repo root:

    pip install -r frontend/requirements.txt
    streamlit run frontend/app.py

Every number, recommendation, "why" and replan on this page comes from
StudySessionPlanner through integration.dashboard.DashboardSession. The
only illustrative data left is the weekly charts on the Insights page,
and they are labelled as sample data.
"""

import sys
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

# Let `streamlit run frontend/app.py` find the src/ packages without PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain_model import TaskType
from integration.dashboard import DISRUPTIONS, FEELINGS, DashboardSession

# ==========================================================
# PAGE CONFIGURATION
# ==========================================================

st.set_page_config(
    page_title="The 12th Interface",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==========================================================
# THEME AND STYLING
# ==========================================================

st.markdown("""
<style>

/* ---------- GLOBAL ---------- */

.stApp {
    background: #0D0E17;
    color: #F4F0FF;
}

[data-testid="stHeader"] {
    background: transparent;
}

[data-testid="stMainBlockContainer"] {
    max-width: 1600px;
    padding: 2rem 3rem 3rem 3rem;
}

/* ---------- SIDEBAR ---------- */

section[data-testid="stSidebar"] {
    background: #141521;
    border-right: 1px solid #28283B;
}

section[data-testid="stSidebar"] > div {
    padding-top: 2rem;
}

.sidebar-brand {
    font-size: 23px;
    font-weight: 800;
    color: #F4F0FF;
    letter-spacing: -0.8px;
}

.sidebar-subtitle {
    color: #918AA8;
    font-size: 12px;
    margin-top: 5px;
    margin-bottom: 30px;
}

.nav-label {
    color: #77718F;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1.5px;
    margin-top: 20px;
    margin-bottom: 10px;
}

/* Sidebar radio navigation */
section[data-testid="stSidebar"] div[role="radiogroup"] {
    gap: 8px;
}

section[data-testid="stSidebar"] div[role="radiogroup"] label {
    background: transparent;
    border-radius: 10px;
    padding: 10px 12px;
    color: #B7B0C9;
    border: 1px solid transparent;
}

section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
    background: #29213F;
    border-color: #59447D;
    color: #D8C5FF;
}

/* ---------- TEXT ---------- */

h1, h2, h3, h4, p, label {
    color: #F4F0FF;
}

.page-heading {
    color: #F4F0FF;
    font-size: 29px;
    font-weight: 800;
    letter-spacing: -0.8px;
    margin-bottom: 4px;
}

.page-description {
    color: #9690A8;
    font-size: 13px;
    margin-bottom: 25px;
}

.section-heading {
    color: #F4F0FF;
    font-size: 17px;
    font-weight: 750;
    margin-top: 15px;
    margin-bottom: 12px;
}

.muted {
    color: #9992AA;
    font-size: 12px;
}

/* ---------- WELCOME ---------- */

.welcome {
    background: linear-gradient(115deg, #302348, #211D35);
    border: 1px solid #4B3969;
    border-radius: 20px;
    padding: 30px;
    margin-bottom: 25px;
}

.welcome-label {
    color: #C3A6FF;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 2px;
}

.welcome-title {
    color: #FFFFFF;
    font-size: 32px;
    font-weight: 800;
    margin-top: 12px;
    margin-bottom: 8px;
}

.welcome-description {
    color: #C6BDD8;
    font-size: 14px;
}

/* ---------- CARDS ---------- */

.metric-card {
    background: #191A29;
    border: 1px solid #2D2D42;
    border-radius: 16px;
    padding: 21px;
    min-height: 145px;
}

.metric-label {
    color: #A29BB5;
    font-size: 11px;
    font-weight: 750;
    letter-spacing: 1px;
}

.metric-value {
    color: #F5F0FF;
    font-size: 34px;
    font-weight: 800;
    margin-top: 10px;
    margin-bottom: 3px;
}

.metric-caption {
    color: #9992AA;
    font-size: 12px;
}

/* ---------- FEATURE CARDS ---------- */

.feature-card {
    background: #191A29;
    border: 1px solid #302E45;
    border-radius: 16px;
    padding: 22px;
}

.recommendation-card {
    background: linear-gradient(140deg, #2C2243, #211D35);
    border: 1px solid #594477;
    border-radius: 17px;
    padding: 24px;
    min-height: 190px;
}

.recommendation-label {
    color: #C6A7FF;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1.5px;
}

.recommendation-title {
    color: #FFFFFF;
    font-size: 24px;
    font-weight: 800;
    margin-top: 15px;
}

.recommendation-description {
    color: #B9B0CB;
    font-size: 13px;
    margin-top: 8px;
}

/* ---------- SCHEDULE ---------- */

.schedule-card {
    background: #191A29;
    border: 1px solid #302F43;
    border-radius: 12px;
    padding: 15px 17px;
    margin-bottom: 9px;
}

.schedule-time {
    color: #B99AFF;
    font-size: 12px;
    font-weight: 800;
}

.schedule-name {
    color: #F4F0FF;
    font-size: 14px;
    font-weight: 650;
}

.schedule-detail {
    color: #918AA5;
    font-size: 11px;
    margin-top: 4px;
}

/* ---------- BUTTONS ---------- */

div.stButton > button {
    background: #222236;
    color: #EDE7FA;
    border: 1px solid #3A3651;
    border-radius: 10px;
    min-height: 42px;
    font-weight: 650;
    transition: 0.2s ease;
}

div.stButton > button:hover {
    background: #38304E;
    color: white;
    border-color: #A78BFA;
}

div.stButton > button[kind="primary"] {
    background: #805AD5;
    border: 1px solid #9B7AE8;
    color: white;
}

div.stButton > button[kind="primary"]:hover {
    background: #9671E7;
    color: white;
}

/* ---------- INPUTS ---------- */

div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div {
    background: #191A29;
    border-color: #39364E;
    color: #F4F0FF;
}

div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input {
    background: #191A29;
    color: #F4F0FF;
}

/* ---------- EXPANDERS ---------- */

div[data-testid="stExpander"] {
    background: #191A29;
    border: 1px solid #353248;
    border-radius: 12px;
}

/* ---------- CHARTS ---------- */

div[data-testid="stPlotlyChart"] {
    background: #191A29;
    border: 1px solid #302F43;
    border-radius: 15px;
    padding: 8px;
}

/* ---------- DIVIDERS ---------- */

hr {
    border-color: #2D2D40;
    margin-top: 22px;
    margin-bottom: 22px;
}

/* ---------- FOOTER ---------- */

.footer {
    color: #716B83;
    text-align: center;
    font-size: 11px;
    padding: 25px 0;
}

/* ---------- RESPONSIVE ---------- */

@media (max-width: 900px) {
    [data-testid="stMainBlockContainer"] {
        padding: 1.3rem !important;
    }

    .welcome-title {
        font-size: 25px;
    }
}

</style>
""", unsafe_allow_html=True)


# ==========================================================
# SESSION STATE (the live backend lives here between reruns)
# ==========================================================

if "backend" not in st.session_state:
    st.session_state.backend = DashboardSession(student_id="demo", sleep_hours=7.5)

for key, value in {"proposal": None, "replan_result": "", "page_notice": ""}.items():
    if key not in st.session_state:
        st.session_state[key] = value

backend: DashboardSession = st.session_state.backend
TASK_TYPES = list(TaskType)


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def make_chart_layout(fig, height=300):
    fig.update_layout(
        height=height,
        paper_bgcolor="#191A29",
        plot_bgcolor="#191A29",
        font={"color": "#B8B0CA", "size": 11},
        margin={"l": 20, "r": 20, "t": 30, "b": 25},
        legend={
            "orientation": "h",
            "y": 1.12,
            "x": 0
        },
        hoverlabel={
            "bgcolor": "#28243A",
            "font_color": "#FFFFFF"
        },
    )
    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        color="#918AA5"
    )
    fig.update_yaxes(
        gridcolor="#302F43",
        zeroline=False,
        color="#918AA5"
    )
    return fig


def page_header(title, description):
    st.markdown(
        f'<div class="page-heading">{title}</div>'
        f'<div class="page-description">{description}</div>',
        unsafe_allow_html=True
    )


def metric_card(label, value, caption):
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-caption">{caption}</div>
    </div>
    """, unsafe_allow_html=True)

def schedule_card(item):
    status = item["status"]
    status_text = "✓ Completed" if status == "Completed" else status
    st.markdown(f"""
    <div class="schedule-card">
        <div class="schedule-time">{item["time"]}</div>
        <div class="schedule-name">{item["task"]}</div>
        <div class="schedule-detail">
            {item["task_type"]} · {item["duration"]} · {status_text}
        </div>
    </div>
    """, unsafe_allow_html=True)


def completed_count():
    return sum(1 for x in backend.schedule_items() if x["status"] == "Completed")


# ==========================================================
# SIDEBAR NAVIGATION
# ==========================================================

with st.sidebar:

    st.markdown(
        '<div class="sidebar-brand">✦ The 12th Interface</div>'
        '<div class="sidebar-subtitle">'
        'Your personal study companion</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="nav-label">WORKSPACE</div>',
        unsafe_allow_html=True
    )

    page = st.radio(
        "Navigation",
        [
            "Home",
            "My Schedule",
            "Insights",
            "Study Mode",
            "Replanning",
        ],
        label_visibility="collapsed",
    )

    st.markdown("---")

    st.markdown(
        '<div class="nav-label">LAST NIGHT</div>',
        unsafe_allow_html=True
    )

    sleep = st.number_input(
        "Hours of sleep",
        min_value=0.0,
        max_value=14.0,
        value=float(backend.sleep_hours),
        step=0.5,
        help="Your energy estimate starts from this.",
    )
    if sleep != backend.sleep_hours:
        backend.set_sleep(sleep)

    plan = backend.plan()

    st.markdown(
        '<div class="nav-label">YOUR DAILY SUMMARY</div>',
        unsafe_allow_html=True
    )

    st.metric("Current energy", f'{plan["energy_pct"]}%')
    st.metric("Sessions completed", completed_count())

    st.markdown("---")

    if st.button("Reset demo", width="stretch"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    st.caption("Live planner · Sample schedule")


# ==========================================================
# SHARED ENERGY INFORMATION (all from the planner)
# ==========================================================

energy = plan["energy_pct"]
energy_label = plan["energy_label"]
recommended_task = plan["task_label"]
explanation = plan["why"]
schedule = backend.schedule_items()


# ==========================================================
# HOME PAGE
# ==========================================================

if page == "Home":

    now = datetime.now()

    greeting = (
        "Good morning!" if now.hour < 12
        else "Good afternoon!" if now.hour < 17
        else "Good evening!"
    )

    header_left, header_right = st.columns([3, 1])

    with header_left:
        page_header(
            "Your study dashboard",
            "A smarter way to plan your day around your energy."
        )

    with header_right:
        st.markdown(
            f'<p style="text-align:right;color:#9992AA;">'
            f'{now.strftime("%A, %B %d")}</p>',
            unsafe_allow_html=True
        )

    st.markdown(f"""
    <div class="welcome">
        <div class="welcome-label">YOUR PERSONAL STUDY SPACE</div>
        <div class="welcome-title">{greeting}</div>
        <div class="welcome-description">
            Let's make today a productive one.
            Your study plan should work with your energy, not against it.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        '<div class="section-heading">Your energy today</div>',
        unsafe_allow_html=True
    )

    c1, c2, c3 = st.columns(3, gap="medium")

    with c1:
        metric_card("ESTIMATED ENERGY", f"{energy}%", energy_label)

    with c2:
        metric_card("SLEEP LAST NIGHT", f"{backend.sleep_hours:g}h",
                    "From the sidebar")

    with c3:
        metric_card(
            "SESSIONS COMPLETED",
            str(completed_count()),
            "Study sessions completed today"
        )

    st.write("")

    energy_col, checkin_col = st.columns([1.2, 1], gap="large")

    with energy_col:

        st.markdown(
            '<div class="section-heading">Your energy level</div>',
            unsafe_allow_html=True
        )

        gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=energy,
            number={
                "suffix": "%",
                "font": {"size": 35, "color": "#F4F0FF"}
            },
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickcolor": "#918AA5"
                },
                "bar": {"color": "#A78BFA"},
                "bgcolor": "#25243A",
                "borderwidth": 0,
                # same low / moderate / high cut points as the planner (0.33 / 0.66)
                "steps": [
                    {"range": [0, 33], "color": "#382332"},
                    {"range": [33, 66], "color": "#342D4A"},
                    {"range": [66, 100], "color": "#293D3A"},
                ],
            }
        ))

        gauge.update_layout(
            height=220,
            paper_bgcolor="#191A29",
            font_color="#F4F0FF",
            margin={"l": 30, "r": 30, "t": 25, "b": 10}
        )

        st.plotly_chart(gauge, width="stretch")
        st.caption(plan["energy_source"])

    with checkin_col:

        st.markdown(
            '<div class="section-heading">How are you feeling?</div>',
            unsafe_allow_html=True
        )

        st.write("Your check-in helps adjust your study plan.")

        feeling = st.radio(
            "Select how you feel",
            list(FEELINGS),
            horizontal=True,
            label_visibility="collapsed",
            key="home_feeling"
        )

        if st.button(
            "Update my energy",
            type="primary",
            width="stretch"
        ):
            backend.checkin(feeling)
            st.rerun()

        if backend.last_feeling:
            st.success(f"Your latest check-in: {backend.last_feeling}")

    st.markdown("---")

    left, right = st.columns([1, 1.2], gap="large")

    with left:

        st.markdown(
            '<div class="section-heading">Your next study task</div>',
            unsafe_allow_html=True
        )

        st.markdown(f"""
        <div class="recommendation-card">
            <div class="recommendation-label">
                ✦ RECOMMENDED FOR YOU
            </div>
            <div class="recommendation-title">
                {recommended_task}
            </div>
            <div class="recommendation-description">
                {energy_label} ({energy}%)
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("Why this recommendation?", expanded=True):
            st.write(f"I suggest {recommended_task.lower()} {explanation}.")
            st.caption(plan["energy_source"])
            if plan["cold_start"]:
                st.caption(
                    "I'm still learning your patterns, so I'm leaning on default rules for now."
                )

        if st.button(
            "Start this task",
            type="primary",
            width="stretch"
        ):
            backend.start_task(plan["task_type"])
            st.session_state.page_notice = (
                f"{recommended_task} session started. Open Study Mode to see it."
            )
            st.rerun()

        if st.session_state.page_notice:
            st.success(st.session_state.page_notice)

    with right:

        st.markdown(
            '<div class="section-heading">Today\'s schedule</div>',
            unsafe_allow_html=True
        )

        upcoming = [x for x in schedule if x["status"] in ("In progress", "Upcoming")]
        for item in (upcoming or schedule)[:4]:
            schedule_card(item)

        st.caption("Choose My Schedule in the sidebar to see the full day.")


# ==========================================================
# MY SCHEDULE PAGE
# ==========================================================

elif page == "My Schedule":

    page_header(
        "My Schedule",
        "Organize your study sessions and make time for breaks."
    )

    a, b, c = st.columns(3)

    with a:
        metric_card(
            "TOTAL SESSIONS",
            len(schedule),
            "Planned for today"
        )

    with b:
        metric_card(
            "COMPLETED",
            completed_count(),
            "Sessions finished"
        )

    with c:
        metric_card(
            "SLEEP",
            f"{backend.sleep_hours:g}h",
            "Last night's sleep"
        )

    st.write("")

    left, right = st.columns([1.4, 1], gap="large")

    with left:

        st.markdown(
            '<div class="section-heading">Today\'s study timeline</div>',
            unsafe_allow_html=True
        )

        for item in schedule:

            schedule_card(item)

            if item["status"] not in ("Completed", "Done") and st.button(
                "Mark completed",
                key=f"complete_{item['session_id']}"
            ):
                backend.mark_completed(item["session_id"])
                st.rerun()

        if backend.deferred:
            st.caption(
                "Moved to tomorrow: "
                + ", ".join(e["title"] for e in backend.deferred)
            )

    with right:

        st.markdown(
            '<div class="section-heading">Add a study session</div>',
            unsafe_allow_html=True
        )

        with st.form("add_session_form"):

            new_task = st.text_input(
                "Task name",
                placeholder="e.g. Database assignment"
            )

            new_type = st.selectbox(
                "Kind of task",
                TASK_TYPES,
                format_func=lambda t: t.label,
            )

            today = datetime.now().astimezone()
            slots = [
                today.replace(hour=h, minute=m, second=0, microsecond=0)
                for h in range(8, 22)
                for m in (0, 30)
            ]
            new_time = st.selectbox(
                "Start time",
                slots,
                format_func=lambda t: t.strftime("%I:%M %p").lstrip("0"),
            )

            duration = st.selectbox(
                "Duration (minutes)",
                [15, 25, 30, 45, 60, 90],
                index=3,
            )

            submitted = st.form_submit_button(
                "Add to schedule",
                type="primary",
                width="stretch"
            )

            if submitted:
                if new_task.strip():
                    backend.add_session(new_task.strip(), new_time, duration, new_type)
                    st.success("Session added!")
                    st.rerun()
                else:
                    st.warning("Please enter a task name.")

        st.markdown("---")

        st.markdown(
            '<div class="section-heading">Your study tip</div>',
            unsafe_allow_html=True
        )

        st.info(
            f"Right now your energy is {energy_label.lower()}, "
            f"so {recommended_task.lower()} is a good fit: {explanation}."
        )


# ==========================================================
# INSIGHTS PAGE
# ==========================================================

elif page == "Insights":

    page_header(
        "Energy & Productivity Insights",
        "Understand your patterns and discover when you study best."
    )

    curve = backend.energy_curve()
    checkins = backend.checkin_history()

    c1, c2, c3 = st.columns(3)

    with c1:
        metric_card(
            "AVERAGE ENERGY TODAY",
            f"{round(sum(p for _t, p in curve) / len(curve))}%",
            "Planner estimate, 8 AM-10 PM",
        )

    with c2:
        peak_time, peak = max(curve, key=lambda x: x[1])
        metric_card("PEAK ENERGY", f"{peak}%", f"Estimated around {peak_time}")

    with c3:
        metric_card("CHECK-INS", str(len(checkins)), "Used to personalize your estimate")

    st.write("")

    st.markdown(
        '<div class="section-heading">Energy throughout the day</div>',
        unsafe_allow_html=True
    )

    energy_chart = go.Figure()

    energy_chart.add_trace(go.Scatter(
        x=[t for t, _p in curve],
        y=[p for _t, p in curve],
        mode="lines+markers",
        name="Estimated energy",
        line={"color": "#A78BFA", "width": 3, "shape": "spline"},
        marker={"size": 7, "color": "#C4A7FF"},
        fill="tozeroy",
        fillcolor="rgba(167,139,250,0.10)"
    ))

    if checkins:
        energy_chart.add_trace(go.Scatter(
            x=[t for t, _p in checkins],
            y=[p for _t, p in checkins],
            mode="markers",
            name="Your check-ins",
            marker={"size": 12, "color": "#F4F0FF", "symbol": "diamond"},
        ))

    energy_chart.update_yaxes(
        title="Energy level",
        range=[0, 100],
        ticksuffix="%"
    )

    st.plotly_chart(
        make_chart_layout(energy_chart, 330),
        width="stretch"
    )

    st.caption(
        "From the planner's energy model: your sleep from the sidebar, the time of day, "
        "and your check-ins. Change your sleep to see the curve move."
    )

    st.markdown("---")

    left, right = st.columns(2, gap="large")

    with left:
        st.markdown(
            '<div class="section-heading">Weekly study hours</div>',
            unsafe_allow_html=True
        )

        study_chart = go.Figure(go.Bar(
            x=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            y=[2.5, 3, 1.5, 4, 2, 3.5, 1],
            marker_color="#8B6AD0",
            name="Study hours"
        ))

        study_chart.update_yaxes(title="Hours")

        st.plotly_chart(
            make_chart_layout(study_chart, 290),
            width="stretch"
        )

    with right:
        st.markdown(
            '<div class="section-heading">Task completion</div>',
            unsafe_allow_html=True
        )

        completion_chart = go.Figure(go.Pie(
            labels=["Completed", "Remaining"],
            values=[8, 4],
            hole=0.68,
            marker={
                "colors": ["#A78BFA", "#343247"],
                "line": {"color": "#191A29", "width": 3}
            },
            textinfo="label+percent"
        ))

        completion_chart.update_layout(
            height=290,
            paper_bgcolor="#191A29",
            plot_bgcolor="#191A29",
            font_color="#F4F0FF",
            margin={"l": 10, "r": 10, "t": 20, "b": 10},
            showlegend=False
        )

        st.plotly_chart(
            completion_chart,
            width="stretch"
        )

    st.markdown("---")

    st.markdown(
        '<div class="section-heading">Sleep and energy</div>',
        unsafe_allow_html=True
    )

    sleep_chart = go.Figure()

    sleep_chart.add_trace(go.Bar(
        x=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        y=[7.5, 6.5, 8, 7, 6, 9, 7.5],
        name="Sleep hours",
        marker_color="#7161A9"
    ))

    sleep_chart.add_trace(go.Scatter(
        x=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        y=[75, 55, 85, 65, 45, 90, 70],
        name="Energy",
        yaxis="y2",
        mode="lines+markers",
        line={"color": "#C4A7FF", "width": 3}
    ))

    sleep_chart.update_layout(
        height=330,
        paper_bgcolor="#191A29",
        plot_bgcolor="#191A29",
        font_color="#B8B0CA",
        margin={"l": 20, "r": 20, "t": 35, "b": 25},
        yaxis={
            "title": "Sleep hours",
            "gridcolor": "#302F43"
        },
        yaxis2={
            "title": "Energy %",
            "overlaying": "y",
            "side": "right",
            "range": [0, 100]
        },
        legend={"orientation": "h", "y": 1.15}
    )

    st.plotly_chart(
        sleep_chart,
        width="stretch"
    )

    st.caption(
        "The weekly charts above use illustrative sample data. "
        "They are not actual student measurements."
    )


# ==========================================================
# STUDY MODE PAGE
# ==========================================================

elif page == "Study Mode":

    page_header(
        "Study Mode",
        "Focus on one task at a time. Your study session starts here."
    )

    if backend.active_task:

        st.markdown("""
        <div class="welcome">
            <div class="welcome-label">FOCUS SESSION ACTIVE</div>
            <div class="welcome-title">Time to focus.</div>
            <div class="welcome-description">
                Stay focused on your current task.
                You can finish the session whenever you're ready.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(
            '<div class="section-heading">Currently studying</div>',
            unsafe_allow_html=True
        )

        metric_card(
            "CURRENT TASK",
            TaskType(backend.active_task).label,
            "Your active study session"
        )

        st.write("")

        if st.button(
            "Finish study session",
            type="primary",
            width="stretch"
        ):
            backend.finish_task()
            st.session_state.page_notice = ""
            st.success("Great work! Your session is complete.")
            st.rerun()

    else:

        st.markdown("""
        <div class="welcome">
            <div class="welcome-label">YOUR FOCUS SPACE</div>
            <div class="welcome-title">Ready to get started?</div>
            <div class="welcome-description">
                Choose a task and begin your next study session.
            </div>
        </div>
        """, unsafe_allow_html=True)

        selected_task = st.selectbox(
            "What would you like to work on?",
            TASK_TYPES,
            index=TASK_TYPES.index(TaskType(plan["task_type"])),
            format_func=lambda t: t.label
            + ("  (recommended)" if t.value == plan["task_type"] else ""),
        )

        duration = st.select_slider(
            "How long would you like to study?",
            options=[15, 25, 30, 45, 60, 90],
            value=45,
            format_func=lambda x: f"{x} minutes"
        )

        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-label">PLANNED FOCUS TIME</div>'
            f'<div class="metric-value">{duration} min</div>'
            f'<div class="metric-caption">One focused session at a time.</div>'
            f'</div>',
            unsafe_allow_html=True
        )

        if st.button(
            "Start my session",
            type="primary",
            width="stretch"
        ):
            backend.start_task(selected_task.value)
            st.rerun()

        st.caption("What you choose here teaches the planner what you like at this energy level.")


# ==========================================================
# REPLANNING PAGE
# ==========================================================

elif page == "Replanning":

    page_header(
        "Let's adjust your plan",
        "When something changes, your planner helps you find another way."
    )

    st.markdown("""
    <div class="welcome">
        <div class="welcome-label">FLEXIBLE PLANNING</div>
        <div class="welcome-title">Plans can change.</div>
        <div class="welcome-description">
            Tell us what happened. We will suggest an adjustment
            instead of silently changing your schedule.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        '<div class="section-heading">What happened?</div>',
        unsafe_allow_html=True
    )

    trigger = st.selectbox("Choose a disruption", list(DISRUPTIONS))

    if st.button(
        "Suggest a new plan",
        type="primary",
        width="stretch"
    ):
        st.session_state.proposal = backend.disrupt(trigger)
        st.session_state.replan_result = ""

    proposal = st.session_state.proposal

    if proposal is not None:

        st.markdown("---")

        st.markdown(
            '<div class="section-heading">Your planner says</div>',
            unsafe_allow_html=True
        )

        change = proposal.proposed_change
        if backend.is_ask(proposal):
            detail = "No change yet. Tell me what changed and I'll adjust."
        else:
            start = datetime.fromisoformat(change["new_start"])
            end = datetime.fromisoformat(change["new_end"])
            detail = (
                f'Suggested: "{change.get("title") or "this session"}" '
                f'{start.strftime("%I:%M %p").lstrip("0")}-{end.strftime("%I:%M %p").lstrip("0")}'
            )

        st.markdown(f"""
        <div class="recommendation-card">
            <div class="recommendation-label">
                ✦ PLANNER SUGGESTION
            </div>
            <div class="recommendation-title">
                {proposal.message}
            </div>
            <div class="recommendation-description">
                {detail}
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.write("")

        if backend.is_ask(proposal):

            with st.form("ask_form", clear_on_submit=True):
                answer = st.text_input(
                    "What changed?",
                    placeholder='e.g. "I\'m wiped, 20 minutes max" or "let\'s do it tomorrow"',
                )
                send_col, skip_col = st.columns(2)
                with send_col:
                    sent = st.form_submit_button(
                        "Tell the planner", type="primary", width="stretch"
                    )
                with skip_col:
                    skipped = st.form_submit_button(
                        "Never mind", width="stretch"
                    )
            if sent or skipped:
                st.session_state.replan_result = backend.answer_ask(
                    proposal, answer if sent else "never mind"
                )
                st.session_state.proposal = None
                st.rerun()

        else:

            accept_col, reject_col = st.columns(2)

            with accept_col:
                if st.button(
                    "Accept suggestion",
                    type="primary",
                    width="stretch"
                ):
                    st.session_state.replan_result = backend.respond(proposal, "accept")
                    st.session_state.proposal = None
                    st.rerun()

            with reject_col:
                if st.button(
                    "Keep my original plan",
                    width="stretch"
                ):
                    st.session_state.replan_result = backend.respond(proposal, "reject")
                    st.session_state.proposal = None
                    st.rerun()

    if st.session_state.replan_result:
        st.success(st.session_state.replan_result)

        st.markdown(
            '<div class="section-heading">Today\'s schedule now</div>',
            unsafe_allow_html=True
        )
        for item in backend.schedule_items():
            schedule_card(item)


# ==========================================================
# FOOTER
# ==========================================================

st.markdown("---")

st.markdown("""
<div class="footer">
    THE 12TH INTERFACE<br>
    Plan smarter. Study better. Work with your energy.
    <br><br>
    Prototype · Live planner, sample schedule
</div>
""", unsafe_allow_html=True)

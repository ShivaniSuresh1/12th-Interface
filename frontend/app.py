
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta

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
# SESSION STATE
# ==========================================================

defaults = {
    "energy": 68,
    "sleep": 7.5,
    "feeling": "",
    "study_started": False,
    "completed_sessions": 0,
    "active_task": "Review lecture notes",
    "disruption_message": "",
    "schedule": [
        {"time": "10:00 AM", "task": "Reading assignment",
         "duration": "45 min", "status": "Upcoming"},
        {"time": "11:00 AM", "task": "Problem set",
         "duration": "60 min", "status": "Upcoming"},
        {"time": "1:00 PM", "task": "Review lecture notes",
         "duration": "45 min", "status": "Upcoming"},
        {"time": "3:00 PM", "task": "Take a short break",
         "duration": "15 min", "status": "Upcoming"},
    ],
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value.copy() if isinstance(value, list) else value


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def get_energy_details(value):
    if value < 40:
        return (
            "Low energy",
            "Reading assignment",
            "A lighter reading task may be more suitable right now."
        )
    elif value < 70:
        return (
            "Moderate energy",
            "Review lecture notes",
            "Reviewing material is a good match for your current energy."
        )
    else:
        return (
            "High energy",
            "Problem set",
            "You may be ready to work on a more challenging task."
        )


def make_chart_layout(fig, height=300):
    fig.update_layout(
        height=height,
        paper_bgcolor="#191A29",
        plot_bgcolor="#191A29",
        font=dict(color="#B8B0CA", size=11),
        margin=dict(l=20, r=20, t=30, b=25),
        legend=dict(
            orientation="h",
            y=1.12,
            x=0
        ),
        hoverlabel=dict(
            bgcolor="#28243A",
            font_color="#FFFFFF"
        ),
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
            {item["duration"]} · {status_text}
        </div>
    </div>
    """, unsafe_allow_html=True)


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
        '<div class="nav-label">YOUR DAILY SUMMARY</div>',
        unsafe_allow_html=True
    )

    st.metric(
        "Current energy",
        f'{st.session_state.energy}%'
    )

    st.metric(
        "Sessions completed",
        st.session_state.completed_sessions
    )

    st.markdown("---")
    st.caption("Early prototype · Sample data")


# ==========================================================
# SHARED ENERGY INFORMATION
# ==========================================================

energy = st.session_state.energy
energy_label, recommended_task, explanation = get_energy_details(energy)


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
        metric_card("SLEEP LAST NIGHT", f'{st.session_state.sleep}h',
                    "Based on your input")

    with c3:
        metric_card(
            "SESSIONS COMPLETED",
            str(st.session_state.completed_sessions),
            "Study sessions completed today"
        )

    st.write("")

    # Energy progress visualization
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
                "steps": [
                    {"range": [0, 40], "color": "#382332"},
                    {"range": [40, 70], "color": "#342D4A"},
                    {"range": [70, 100], "color": "#293D3A"},
                ],
            }
        ))

        gauge.update_layout(
            height=220,
            paper_bgcolor="#191A29",
            font_color="#F4F0FF",
            margin=dict(l=30, r=30, t=25, b=10)
        )

        st.plotly_chart(gauge, use_container_width=True)

    with checkin_col:
        st.markdown(
            '<div class="section-heading">How are you feeling?</div>',
            unsafe_allow_html=True
        )

        st.write("Your check-in helps adjust your study plan.")

        feeling = st.radio(
            "Select how you feel",
            ["Tired", "Fine", "Energized"],
            horizontal=True,
            label_visibility="collapsed",
            key="home_feeling"
        )

        if st.button(
            "Update my energy",
            type="primary",
            use_container_width=True
        ):
            values = {
                "Tired": 30,
                "Fine": 60,
                "Energized": 90,
            }

            st.session_state.energy = values[feeling]
            st.session_state.feeling = feeling
            st.rerun()

        if st.session_state.feeling:
            st.success(
                f"Your latest check-in: {st.session_state.feeling}"
            )

    st.markdown("---")

    # Recommendation and schedule
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
                {explanation}
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("Why this recommendation?"):
            st.write(explanation)
            st.caption(
                "This prototype uses a simple energy-to-task rule."
            )

        if st.button(
            "Start this task",
            type="primary",
            use_container_width=True
        ):
            st.session_state.active_task = recommended_task
            st.session_state.study_started = True
            st.success("Your study session is ready!")
            st.rerun()

    with right:
        st.markdown(
            '<div class="section-heading">Today\'s schedule</div>',
            unsafe_allow_html=True
        )

        for item in st.session_state.schedule[:4]:
            schedule_card(item)

        if st.button("View full schedule"):
            st.session_state.page_target = "My Schedule"
            st.info("Choose My Schedule in the sidebar to view all sessions.")

    st.markdown("---")

    # Weekly preview chart
    st.markdown(
        '<div class="section-heading">Your weekly study activity</div>',
        unsafe_allow_html=True
    )

    weekly = go.Figure()

    weekly.add_trace(go.Bar(
        x=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        y=[2.5, 3, 1.5, 4, 2, 3.5, 1],
        marker_color="#8B6AD0",
        marker_line_width=0,
        name="Study hours"
    ))

    weekly.update_yaxes(title="Hours", range=[0, 5])
    st.plotly_chart(
        make_chart_layout(weekly, 260),
        use_container_width=True
    )


# ==========================================================
# MY SCHEDULE PAGE
# ==========================================================

elif page == "My Schedule":

    page_header(
        "My Schedule",
        "Organize your study sessions and make time for breaks."
    )

    today = datetime.now()

    a, b, c = st.columns(3)

    with a:
        metric_card(
            "TOTAL SESSIONS",
            len(st.session_state.schedule),
            "Planned for today"
        )

    with b:
        metric_card(
            "COMPLETED",
            sum(
                1 for x in st.session_state.schedule
                if x["status"] == "Completed"
            ),
            "Sessions finished"
        )

    with c:
        metric_card(
            "SLEEP",
            f'{st.session_state.sleep}h',
            "Last night's sleep"
        )

    st.write("")

    left, right = st.columns([1.4, 1], gap="large")

    with left:
        st.markdown(
            '<div class="section-heading">Today\'s study timeline</div>',
            unsafe_allow_html=True
        )

        for index, item in enumerate(st.session_state.schedule):
            schedule_card(item)

            if item["status"] != "Completed":
                if st.button(
                    f"Mark completed",
                    key=f"complete_{index}"
                ):
                    st.session_state.schedule[index]["status"] = "Completed"
                    st.session_state.completed_sessions += 1
                    st.rerun()

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

            new_time = st.selectbox(
                "Start time",
                [
                    "9:00 AM", "10:00 AM", "11:00 AM",
                    "12:00 PM", "1:00 PM", "2:00 PM",
                    "3:00 PM", "4:00 PM", "5:00 PM"
                ]
            )

            duration = st.selectbox(
                "Duration",
                ["15 min", "30 min", "45 min", "60 min", "90 min"]
            )

            submitted = st.form_submit_button(
                "Add to schedule",
                type="primary",
                use_container_width=True
            )

            if submitted:
                if new_task.strip():
                    st.session_state.schedule.append({
                        "time": new_time,
                        "task": new_task.strip(),
                        "duration": duration,
                        "status": "Upcoming"
                    })
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
            "Try alternating challenging study sessions "
            "with short breaks to avoid getting overwhelmed."
        )


# ==========================================================
# INSIGHTS PAGE
# ==========================================================

elif page == "Insights":

    page_header(
        "Energy & Productivity Insights",
        "Understand your patterns and discover when you study best."
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        metric_card("AVERAGE ENERGY", "68%", "Illustrative weekly average")

    with c2:
        metric_card("STUDY HOURS", "17.5h", "Illustrative weekly total")

    with c3:
        metric_card("STUDY STREAK", "4 days", "Illustrative current streak")

    st.write("")

    # Energy trend
    st.markdown(
        '<div class="section-heading">Energy throughout the day</div>',
        unsafe_allow_html=True
    )

    energy_chart = go.Figure()

    energy_chart.add_trace(go.Scatter(
        x=[
            "8 AM", "10 AM", "12 PM",
            "2 PM", "4 PM", "6 PM", "8 PM"
        ],
        y=[55, 78, 65, 45, 70, 62, 48],
        mode="lines+markers",
        name="Energy",
        line=dict(color="#A78BFA", width=3, shape="spline"),
        marker=dict(size=8, color="#C4A7FF"),
        fill="tozeroy",
        fillcolor="rgba(167,139,250,0.10)"
    ))

    energy_chart.update_yaxes(
        title="Energy level",
        range=[0, 100],
        ticksuffix="%"
    )

    st.plotly_chart(
        make_chart_layout(energy_chart, 330),
        use_container_width=True
    )

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
            use_container_width=True
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
            marker=dict(
                colors=["#A78BFA", "#343247"],
                line=dict(color="#191A29", width=3)
            ),
            textinfo="label+percent"
        ))

        completion_chart.update_layout(
            height=290,
            paper_bgcolor="#191A29",
            plot_bgcolor="#191A29",
            font_color="#F4F0FF",
            margin=dict(l=10, r=10, t=20, b=10),
            showlegend=False
        )

        st.plotly_chart(
            completion_chart,
            use_container_width=True
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
        line=dict(color="#C4A7FF", width=3)
    ))

    sleep_chart.update_layout(
        height=330,
        paper_bgcolor="#191A29",
        plot_bgcolor="#191A29",
        font_color="#B8B0CA",
        margin=dict(l=20, r=20, t=35, b=25),
        yaxis=dict(
            title="Sleep hours",
            gridcolor="#302F43"
        ),
        yaxis2=dict(
            title="Energy %",
            overlaying="y",
            side="right",
            range=[0, 100]
        ),
        legend=dict(orientation="h", y=1.15)
    )

    st.plotly_chart(
        sleep_chart,
        use_container_width=True
    )

    st.caption(
        "All analytics on this page use illustrative sample data. "
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

    if st.session_state.study_started:
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
            st.session_state.active_task,
            "Your active study session"
        )

        st.write("")

        if st.button(
            "Finish study session",
            type="primary",
            use_container_width=True
        ):
            st.session_state.study_started = False
            st.session_state.completed_sessions += 1
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

        task_options = [
            "Reading assignment",
            "Problem set",
            "Review lecture notes",
            "Memorization",
            "Other"
        ]

        selected_task = st.selectbox(
            "What would you like to work on?",
            task_options
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
            use_container_width=True
        ):
            st.session_state.active_task = selected_task
            st.session_state.study_started = True
            st.rerun()


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

    trigger = st.selectbox(
        "Choose a disruption",
        [
            "Meeting ran late",
            "I am feeling tired",
            "I missed a study session"
        ]
    )

    if trigger == "Meeting ran late":
        suggestion = (
            "Your meeting ran late. Consider moving your next "
            "study session to a later time."
        )
        proposed_time = "2:00 PM"
    elif trigger == "I am feeling tired":
        suggestion = (
            "Your energy is low. Consider replacing your next "
            "challenging task with a lighter reading session."
        )
        proposed_time = "Keep the same time"
    else:
        suggestion = (
            "You missed a study session. Consider adding it "
            "to a later open time in your day."
        )
        proposed_time = "4:00 PM"

    if st.button(
        "Suggest a new plan",
        type="primary",
        use_container_width=True
    ):
        st.session_state.disruption_message = suggestion
        st.session_state.proposed_time = proposed_time
        st.session_state.proposal_pending = True

    if st.session_state.get("proposal_pending", False):

        st.markdown("---")

        st.markdown(
            '<div class="section-heading">Your proposed change</div>',
            unsafe_allow_html=True
        )

        st.markdown(f"""
        <div class="recommendation-card">
            <div class="recommendation-label">
                ✦ PLANNER SUGGESTION
            </div>
            <div class="recommendation-title">
                {st.session_state.disruption_message}
            </div>
            <div class="recommendation-description">
                Suggested adjustment: {st.session_state.proposed_time}
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.write("")

        accept_col, reject_col = st.columns(2)

        with accept_col:
            if st.button(
                "Accept suggestion",
                type="primary",
                use_container_width=True
            ):
                st.session_state.replan_result = (
                    "Your suggested change has been accepted in the demo."
                )
                st.session_state.proposal_pending = False
                st.rerun()

        with reject_col:
            if st.button(
                "Keep my original plan",
                use_container_width=True
            ):
                st.session_state.replan_result = (
                    "Your original plan has been kept."
                )
                st.session_state.proposal_pending = False
                st.rerun()

    if st.session_state.get("replan_result"):
        st.success(st.session_state.replan_result)


# ==========================================================
# FOOTER
# ==========================================================

st.markdown("---")

st.markdown("""
<div class="footer">
    THE 12TH INTERFACE<br>
    Plan smarter. Study better. Work with your energy.
    <br><br>
    Early prototype · Illustrative data
</div>
""", unsafe_allow_html=True)

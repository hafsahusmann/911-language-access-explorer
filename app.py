"""
Language Access Data Explorer
Internal navigation tool for the 911 dispatch / language access research team.

Runs on the real, de-identified dataset exported from the study's SPSS file
(see data/prep_data.py to regenerate data/calls.csv from a new .sav export).
"""

import streamlit as st
import pandas as pd
import plotly.express as px

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:  # missing until pip install -r requirements.txt
    gspread = None
    Credentials = None

# ---------------------------------------------------------------------------
# Page setup + brand colors
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Language Access Data Explorer",
    layout="wide",
    initial_sidebar_state="expanded",
)

PURPLE = "#865391"
LAVENDER = "#b98cc4"
CORAL = "#D85A30"
TEAL = "#1D9E75"

st.markdown(
    f"""
    <style>
    .main-header {{
        background-color: {PURPLE};
        padding: 1.1rem 1.5rem;
        border-radius: 6px;
        color: white;
        margin-bottom: 1.2rem;
    }}
    .main-header h1 {{
        color: white;
        font-size: 1.5rem;
        margin: 0;
    }}
    .stat-card {{
        background-color: {LAVENDER};
        border-radius: 8px;
        padding: 0.9rem 1rem;
        text-align: center;
        color: white;
    }}
    .stat-card .value {{
        font-size: 1.8rem;
        font-weight: 700;
    }}
    .stat-card .label {{
        font-size: 0.8rem;
        opacity: 0.9;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-header"><h1>Language Access Data Explorer</h1></div>',
    unsafe_allow_html=True,
)

SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


NUMERIC_COLUMNS = ["interpreter_connect_min", "response_time_min", "onscene_time_min"]


def _clean_zip(series: pd.Series) -> pd.Series:
    """Treat zip codes as a category: strip float artifacts from Sheets
    (e.g. 98501.0 -> "98501") and turn blank cells into real nulls."""
    zip_str = series.astype("string").str.replace(r"\.0$", "", regex=True)
    return zip_str.replace("", pd.NA)


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["zip_code"] = _clean_zip(df["zip_code"])
    df["call_date"] = pd.to_datetime(df["call_date"])
    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _sheet_id_and_tab():
    """Support either top-level sheet_id or [gsheet] block in secrets.toml."""
    if "gsheet" in st.secrets:
        sid = st.secrets["gsheet"]["sheet_id"]
        tab = st.secrets["gsheet"].get("worksheet", "calls")
    else:
        sid = st.secrets["sheet_id"]
        tab = st.secrets.get("worksheet", "calls")
    return sid, tab


def _has_sheet_secrets() -> bool:
    try:
        return "gcp_service_account" in st.secrets and (
            "sheet_id" in st.secrets or "gsheet" in st.secrets
        )
    except Exception:
        return False


def _load_from_sheet() -> pd.DataFrame:
    if gspread is None or Credentials is None:
        raise RuntimeError("Install gspread and google-auth to load from Google Sheets.")
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), scopes=SHEETS_SCOPES
    )
    sheet_id, worksheet_name = _sheet_id_and_tab()
    worksheet = gspread.authorize(creds).open_by_key(sheet_id).worksheet(worksheet_name)
    return pd.DataFrame(worksheet.get_all_records())


# ---------------------------------------------------------------------------
# Data loading — Google Sheet only (credentials in Streamlit secrets, never in git)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300)
def load_data():
    return _normalize(_load_from_sheet())


if not _has_sheet_secrets():
    st.error(
        "This app reads the study data from a private Google Sheet. "
        "Add the GCP service account and sheet_id to Streamlit secrets "
        "(see `.streamlit/secrets.toml.example`). "
        "`data/calls.csv` is not shipped in this repo."
    )
    st.stop()

df = load_data()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
st.sidebar.header("Filters")

centers_sel = st.sidebar.multiselect(
    "Call Center", options=sorted(df["call_center"].dropna().unique()),
    default=sorted(df["call_center"].dropna().unique()),
)

dated = df["call_date"].dropna()
min_date, max_date = dated.min().date(), dated.max().date()
date_range = st.sidebar.date_input(
    "Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date,
)

interp_choice = st.sidebar.radio(
    "Interpreter Used?", options=["All", "Yes", "No"], horizontal=True,
)

lang_group_options = sorted(df["lang_group"].dropna().unique())
lang_group_sel = st.sidebar.multiselect("Language Group", options=lang_group_options, default=[])

zip_options = sorted(df["zip_code"].dropna().unique())
zip_sel = st.sidebar.multiselect("Zip Code", options=zip_options, default=[])

tod_options = [c for c in df["time_of_day"].cat.categories] if hasattr(df["time_of_day"], "cat") else sorted(df["time_of_day"].dropna().unique())
tod_sel = st.sidebar.multiselect("Time of Day", options=tod_options, default=[])

# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------
filtered = df[df["call_center"].isin(centers_sel)]

if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
    in_range = (filtered["call_date"].dt.date >= start) & (filtered["call_date"].dt.date <= end)
    filtered = filtered[in_range | filtered["call_date"].isna()]

if interp_choice != "All":
    filtered = filtered[filtered["interpreter_used"] == interp_choice]

if lang_group_sel:
    filtered = filtered[filtered["lang_group"].isin(lang_group_sel)]

if zip_sel:
    filtered = filtered[filtered["zip_code"].isin(zip_sel)]

if tod_sel:
    filtered = filtered[filtered["time_of_day"].isin(tod_sel)]

# ---------------------------------------------------------------------------
# Stat cards
# ---------------------------------------------------------------------------
total_calls = len(filtered)
pct_interp = (filtered["interpreter_used"].eq("Yes").mean() * 100) if total_calls else 0
# interpreter_connect_min = OPI connection time minus access time — the full
# time a caller/PST spent on hold waiting for an interpreter (system delay).
avg_system_delay = filtered["interpreter_connect_min"].mean() if total_calls else 0

c1, c2, c3 = st.columns(3)
for col, value, label in zip(
    [c1, c2, c3],
    [f"{total_calls:,}", f"{pct_interp:.0f}%", f"{avg_system_delay:.1f} min"],
    ["Total Calls", "Interpreter Use", "Avg System Delay"],
):
    col.markdown(
        f'<div class="stat-card"><div class="value">{value}</div>'
        f'<div class="label">{label}</div></div>',
        unsafe_allow_html=True,
    )

st.write("")

CORAL_TEAL = {"Yes": CORAL, "No": TEAL}


def empty_notice():
    st.info("No calls match the current filters.")


# ---------------------------------------------------------------------------
# Charts, grouped by category (see the team's plot-tracking sheet).
# Language Access is kept first; order within a category doesn't matter.
# When adding a new chart, pick (or add) a category section for it below.
# ---------------------------------------------------------------------------

st.header("Call Center Detail")

with st.expander("About these four call centers — read before comparing", expanded=True):
    st.markdown(
        """
Study calls come from **four Emergency Communication Centers (ECCs)**: Valley,
NORCOM, and Benton/Franklin in Washington State, and Verdugo in California. All
four follow Criteria-Based Dispatch (CBD) or closely related protocols, but they
were **not sampled the same way**, so raw center-to-center differences below
reflect study design as much as (or more than) real differences between centers:

- **Purposive sampling, not real-world volume.** Each month, calls were drawn
  as 15 Language Line (LL) and 15 non-LL calls per center. Center-level LL-use
  rates and call counts here do not reflect each center's actual LL usage or
  volume.
- **LL calls were oversampled from Verdugo (CA).** Two of the three Washington
  centers had lower-than-anticipated LL call volume, so LL calls were
  oversampled from Verdugo to maintain analytic power — this inflates its LL
  share relative to the Washington centers.
- **Benton/Franklin joined the study partway through**, added later to supply
  a rural ECC perspective and more LL calls. Its sample is backfilled and
  covers a shorter window than the other three centers, and it is the
  smallest sample of the four.
- **One center had a two-month gap in data collection**, so the study does
  not have full capture of all language-barrier calls from two of the four
  centers.

Treat the breakdowns below as descriptive context for this dataset, not as
evidence about which call center performs better.
        """
    )

if total_calls:
    center_summary = (
        filtered.groupby("call_center")
        .agg(
            calls=("call_id", "count"),
            pct_ll=("interpreter_used", lambda s: (s == "Yes").mean() * 100),
            avg_system_delay=("interpreter_connect_min", "mean"),
            avg_response=("response_time_min", "mean"),
            avg_onscene=("onscene_time_min", "mean"),
        )
        .reset_index()
        .sort_values("calls", ascending=False)
    )

    center_cols = st.columns(len(center_summary))
    for col, row in zip(center_cols, center_summary.itertuples()):
        col.markdown(
            f'<div class="stat-card"><div class="value">{row.calls}</div>'
            f'<div class="label">{row.call_center}</div></div>',
            unsafe_allow_html=True,
        )
        col.caption(
            f"{row.pct_ll:.0f}% LL use  \n"
            f"System delay: {row.avg_system_delay:.1f} min  \n"
            f"Response: {row.avg_response:.1f} min  \n"
            f"Onscene: {row.avg_onscene:.1f} min"
        )

    st.write("")

    center_time_summary = (
        filtered.groupby("call_center")[["response_time_min", "onscene_time_min"]]
        .mean().reset_index()
        .melt(id_vars="call_center", var_name="metric", value_name="minutes")
    )
    center_time_summary["metric"] = center_time_summary["metric"].map({
        "response_time_min": "Response time",
        "onscene_time_min": "Onscene time",
    })
    fig = px.bar(
        center_time_summary, x="call_center", y="minutes", color="metric", barmode="group",
        color_discrete_map={"Response time": CORAL, "Onscene time": TEAL},
        labels={"call_center": "", "minutes": "Avg Minutes", "metric": ""},
    )
    fig.update_layout(legend_title="", margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
else:
    empty_notice()

st.header("Language Access")
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Interpreter Use by Call Center")
    st.caption(
        "These proportions are likely not representative of real-world rates "
        "given the study's purposive over-sampling of LL calls (manuscript Table 1 note)."
    )
    if total_calls:
        summary = (
            filtered.groupby(["call_center", "interpreter_used"])
            .size().reset_index(name="count")
        )
        fig = px.bar(
            summary, x="call_center", y="count", color="interpreter_used", barmode="group",
            color_discrete_map=CORAL_TEAL,
            labels={"call_center": "", "count": "Calls", "interpreter_used": "Interpreter"},
        )
        fig.update_layout(legend_title="", margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        empty_notice()

with chart_col2:
    st.subheader("Language Groups by Call Center")
    st.caption(
        "Same caveat as the chart to the left — language group mix here reflects "
        "the study's sampling design, not each call center's real caseload."
    )
    if total_calls:
        summary = (
            filtered.groupby(["call_center", "lang_group"])
            .size().reset_index(name="count")
        )
        fig = px.bar(
            summary, x="call_center", y="count", color="lang_group", barmode="stack",
            labels={"call_center": "", "count": "Calls", "lang_group": "Language Group"},
        )
        fig.update_layout(legend_title="", margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        empty_notice()

chart_col3, chart_col4 = st.columns(2)

with chart_col3:
    st.subheader("Emergency Type Within Language Group")
    if total_calls:
        summary = (
            filtered.dropna(subset=["emergency_type"])
            .groupby(["lang_group", "emergency_type"])
            .size().reset_index(name="count")
        )
        fig = px.bar(
            summary, x="lang_group", y="count", color="emergency_type", barmode="stack",
            labels={"lang_group": "", "count": "Calls", "emergency_type": "Emergency Type"},
        )
        fig.update_layout(legend_title="", margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        empty_notice()

with chart_col4:
    st.subheader("Language Groups by System Delay")
    st.caption(
        "System delay = OPI connection time minus access time (full time on hold). "
        "In the published study, system delay ranged from 27s (SD 22) for Spanish "
        "speakers to 133s (SD 113) for Russian speakers — the shortest and longest "
        "among the five most common languages (manuscript Results)."
    )
    if total_calls:
        summary = (
            filtered.dropna(subset=["interpreter_connect_min"])
            .groupby("lang_group")["interpreter_connect_min"]
            .mean().reset_index()
        )
        fig = px.bar(
            summary, x="lang_group", y="interpreter_connect_min",
            labels={"lang_group": "", "interpreter_connect_min": "Avg System Delay (min)"},
            color_discrete_sequence=[PURPLE],
        )
        fig.update_layout(margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        empty_notice()

st.header("Response Patterns")
st.caption(
    "Response time = manuscript Table 2's \"time to first dispatch\"; onscene time = "
    "\"time to first arrival on scene.\" Published study-wide medians [IQR]: dispatch "
    "1.59 min [0.78, 1.93] (non-LL 1.26, LL 2.01); arrival on scene 7.52 min "
    "[5.62, 8.60] (non-LL 7.09, LL 8.13) — useful as a sanity check against whatever "
    "filtered subset you're viewing below."
)

st.subheader("Calls per Week")
dated_filtered = filtered.dropna(subset=["call_date"])
if len(dated_filtered):
    weekly = (
        dated_filtered.set_index("call_date")
        .resample("W")["call_id"].count()
        .reset_index(name="calls")
    )
    fig = px.line(weekly, x="call_date", y="calls", labels={"call_date": "", "calls": "Calls"})
    fig.update_traces(line_color=PURPLE)
    fig.update_layout(margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
else:
    empty_notice()

st.subheader("Response and Onscene Time by Zip Code (Top 15 by Volume)")
if total_calls:
    top_zips = filtered["zip_code"].value_counts().nlargest(15).index
    zip_filtered = filtered[filtered["zip_code"].isin(top_zips)]
    zip_summary = (
        zip_filtered.groupby("zip_code")[["response_time_min", "onscene_time_min"]]
        .mean().reset_index()
        .melt(id_vars="zip_code", var_name="metric", value_name="minutes")
    )
    zip_summary["metric"] = zip_summary["metric"].map({
        "response_time_min": "Response time",
        "onscene_time_min": "Onscene time",
    })
    fig = px.bar(
        zip_summary, x="zip_code", y="minutes", color="metric", barmode="group",
        color_discrete_map={"Response time": CORAL, "Onscene time": TEAL},
        labels={"zip_code": "", "minutes": "Avg Minutes", "metric": ""},
    )
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=list(top_zips))
    fig.update_layout(legend_title="", margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
else:
    empty_notice()

st.header("Caller Behavior")

st.subheader("Hang-Ups Within Language Group")
st.caption("Hang-ups are rare in this dataset, so some bars will be thin.")
if total_calls:
    summary = (
        filtered.groupby(["lang_group", "hangup"])
        .size().reset_index(name="count")
    )
    fig = px.bar(
        summary, x="lang_group", y="count", color="hangup", barmode="group",
        color_discrete_map=CORAL_TEAL,
        labels={"lang_group": "", "count": "Calls", "hangup": "Hang-up"},
    )
    fig.update_layout(legend_title="", margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
else:
    empty_notice()

st.header("Dispatcher Communication")
chart_col5, chart_col6 = st.columns(2)

with chart_col5:
    st.subheader("Jargon Use vs. Caller Compliance")
    if total_calls:
        summary = (
            filtered.dropna(subset=["jargon_validation", "compliance"])
            .groupby(["jargon_validation", "compliance"])
            .size().reset_index(name="count")
        )
        fig = px.bar(
            summary, x="jargon_validation", y="count", color="compliance", barmode="group",
            labels={"jargon_validation": "", "count": "Calls", "compliance": "Compliance"},
        )
        fig.update_layout(legend_title="", margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        empty_notice()

with chart_col6:
    st.subheader("Caller Emotion vs. Emotion Validation")
    if total_calls:
        summary = (
            filtered.dropna(subset=["caller_emotion", "emotion_validated"])
            .groupby(["caller_emotion", "emotion_validated"])
            .size().reset_index(name="count")
        )
        fig = px.bar(
            summary, x="caller_emotion", y="count", color="emotion_validated", barmode="group",
            color_discrete_map=CORAL_TEAL,
            labels={"caller_emotion": "", "count": "Calls", "emotion_validated": "Emotion Validated"},
        )
        fig.update_layout(legend_title="", margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        empty_notice()

import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Australian Housing Loans ($FUM)",
    layout="wide",
)

# ── Load config ───────────────────────────────────────────────────────────────
@st.cache_data
def load_config():
    with open("config/institutions.json") as f:
        cfg = json.load(f)
    return {inst["abn"]: inst for inst in cfg["big5"]}

BIG5_CONFIG = load_config()   # abn → {name, short, brand_color}
BIG5_ABNS   = list(BIG5_CONFIG.keys())

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    df = pd.read_csv(
        "data/processed/housing_market_share_by_institution.csv",
        dtype={"abn": str},
    )
    df["period"]   = pd.to_datetime(df["period"])
    df["big5_flag"] = df["big5_flag"].astype(str).str.lower() == "true"
    return df

df = load_data()

# ── Column maps ───────────────────────────────────────────────────────────────
LOAN_TYPE_MAP = {
    "Total Housing":  ("total_housing_value_millions",  "system_total_housing_millions",  "total_housing_share"),
    "Owner-occupied": ("owner_occupied_value_millions", "system_owner_occupied_millions", "owner_occupied_share"),
    "Investment":     ("investment_value_millions",      "system_investment_millions",     "investment_share"),
}

OTHER_COLOR  = "#CBD5E1"  # neutral slate for the "Other" bucket

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Controls")

    loan_type = st.selectbox(
        "Loan type",
        options=list(LOAN_TYPE_MAP.keys()),
        index=0,
    )

    universe = st.selectbox(
        "Universe",
        options=["Big 5 only", "All institutions"],
        index=0,
    )

    top_n = None
    if universe == "All institutions":
        top_n = st.slider("Top N institutions", min_value=5, max_value=25, value=10)

value_col, system_col, share_col = LOAN_TYPE_MAP[loan_type]

# ── Title ─────────────────────────────────────────────────────────────────────
st.title("Australian Housing Loans ($FUM)")
st.caption(
    f"APRA monthly ADI statistics  ·  {loan_type}  ·  "
    f"{df['period'].min().strftime('%b %Y')} – {df['period'].max().strftime('%b %Y')}"
)

# ── Build series for stacked area ─────────────────────────────────────────────
periods = sorted(df["period"].unique())
latest  = df["period"].max()

def make_fig(series_list):
    """
    series_list: list of dicts {name, color, data: pd.Series indexed by period}
    Renders bottom-up so the first item in the list is at the bottom of the stack.
    """
    fig = go.Figure()
    for s in series_list:
        values_bn = s["data"].reindex(periods).fillna(0) / 1000  # millions → billions
        fig.add_trace(go.Scatter(
            x=periods,
            y=values_bn,
            name=s["name"],
            mode="lines",
            stackgroup="one",
            fillcolor=s["color"],
            line=dict(color=s["color"], width=0.5),
            hovertemplate="%{x|%b %Y}<br>$%{y:,.1f}B<extra>" + s["name"] + "</extra>",
        ))
    fig.update_layout(
        margin=dict(t=20, b=20, l=0, r=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.01,
            font=dict(size=12),
            traceorder="reversed",   # top of stack shown first in legend
        ),
        xaxis=dict(
            title=None,
            showgrid=False,
            showline=True,
            linecolor="#E2E8F0",
            tickformat="%b %Y",
        ),
        yaxis=dict(
            title="Loan balance ($B)",
            showgrid=True,
            gridcolor="#F1F5F9",
            tickprefix="$",
            ticksuffix="B",
            tickformat=",.0f",
            zeroline=False,
        ),
        hovermode="x unified",
        height=500,
    )
    return fig

# ── Big 5 only ────────────────────────────────────────────────────────────────
if universe == "Big 5 only":
    b5_df = df[df["big5_flag"]].copy()

    # Pivot: institution × period
    pivot = (
        b5_df.pivot_table(index="period", columns="abn", values=value_col, aggfunc="sum")
        .reindex(columns=BIG5_ABNS)
    )

    # Order: smallest at bottom so the largest institution crowns the stack
    avg_vals = pivot.mean().sort_values()
    ordered_abns = avg_vals.index.tolist()

    series = []
    for abn in ordered_abns:
        cfg = BIG5_CONFIG[abn]
        series.append({
            "name":  cfg["short"],
            "color": cfg["brand_color"],
            "data":  pivot[abn],
        })

    fig = make_fig(series)
    st.plotly_chart(fig, use_container_width=True)

# ── All institutions (Top N + Other) ─────────────────────────────────────────
else:
    # Rank by latest-period FUM
    latest_fum = (
        df[df["period"] == latest]
        .groupby("institution_name")[value_col]
        .sum()
        .sort_values(ascending=False)
    )
    top_names   = latest_fum.head(top_n).index.tolist()
    other_names = latest_fum.iloc[top_n:].index.tolist()

    pivot = df.pivot_table(index="period", columns="institution_name", values=value_col, aggfunc="sum")

    # Top N ordered smallest-first (bottom of stack)
    top_ranked_asc = list(reversed(top_names))   # largest last = top of stack
    top_avg = pivot[top_names].mean().sort_values()
    ordered_top = top_avg.index.tolist()

    # Colour palette — highlight Big 5 within the Top N
    PALETTE = [
        "#3B82F6","#EF4444","#10B981","#F59E0B","#8B5CF6",
        "#06B6D4","#EC4899","#84CC16","#F97316","#6366F1",
        "#14B8A6","#D97706","#A855F7","#0EA5E9","#BE185D",
        "#22C55E","#E11D48","#2563EB","#7C3AED","#059669",
        "#DC2626","#CA8A04","#0369A1","#65A30D","#9333EA",
    ]
    color_map = {}
    palette_idx = 0
    for name in ordered_top:
        # Check if it's a Big 5 institution
        abn_match = df[df["institution_name"] == name]["abn"].iloc[0] if len(df[df["institution_name"] == name]) else None
        if abn_match and abn_match in BIG5_CONFIG:
            color_map[name] = BIG5_CONFIG[abn_match]["brand_color"]
        else:
            color_map[name] = PALETTE[palette_idx % len(PALETTE)]
            palette_idx += 1

    series = []
    for name in ordered_top:
        series.append({
            "name":  name,
            "color": color_map[name],
            "data":  pivot[name] if name in pivot.columns else pd.Series(dtype=float),
        })

    # "Other" = sum of remaining institutions
    if other_names:
        other_cols = [n for n in other_names if n in pivot.columns]
        other_series = pivot[other_cols].sum(axis=1) if other_cols else pd.Series(0, index=periods)
        series.insert(0, {          # bottom of stack
            "name":  f"Other ({len(other_names)} institutions)",
            "color": OTHER_COLOR,
            "data":  other_series,
        })

    fig = make_fig(series)
    st.plotly_chart(fig, use_container_width=True)

# ── Metric cards ──────────────────────────────────────────────────────────────
st.divider()

latest_sys_m  = df[df["period"] == latest][system_col].max()
latest_b5_m   = df[(df["period"] == latest) & df["big5_flag"]][value_col].sum()
latest_b5_shr = df[(df["period"] == latest) & df["big5_flag"]][share_col].sum()

# prior month for delta
prev_period  = df[df["period"] < latest]["period"].max()
prev_sys_m   = df[df["period"] == prev_period][system_col].max()
prev_b5_m    = df[(df["period"] == prev_period) & df["big5_flag"]][value_col].sum()
prev_b5_shr  = df[(df["period"] == prev_period) & df["big5_flag"]][share_col].sum()

sys_delta_bn = (latest_sys_m - prev_sys_m) / 1000
b5_delta_bn  = (latest_b5_m  - prev_b5_m)  / 1000
shr_delta_pp = (latest_b5_shr - prev_b5_shr) * 100

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label=f"System {loan_type} FUM — {latest.strftime('%b %Y')}",
        value=f"${latest_sys_m / 1000:,.1f}B",
        delta=f"{sys_delta_bn:+,.1f}B vs prior month",
        delta_color="off",
    )
with col2:
    st.metric(
        label=f"Big 5 {loan_type} FUM — {latest.strftime('%b %Y')}",
        value=f"${latest_b5_m / 1000:,.1f}B",
        delta=f"{b5_delta_bn:+,.1f}B vs prior month",
        delta_color="off",
    )
with col3:
    st.metric(
        label=f"Big 5 {loan_type} share — {latest.strftime('%b %Y')}",
        value=f"{latest_b5_shr * 100:.2f}%",
        delta=f"{shr_delta_pp:+.2f}pp vs prior month",
        delta_color="off",
    )

st.caption(
    "Source: APRA Monthly ADI Statistics  ·  Values in $billions  ·  "
    "Big 5: CBA · Westpac · NAB · ANZ · Macquarie"
)

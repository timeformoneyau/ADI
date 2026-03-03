import json
import re
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Australian Residential Lending ($FUM)", layout="wide")

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Metric cards */
[data-testid="stMetric"] {
    background: rgba(30,41,59,0.6);
    border: 1px solid rgba(51,65,85,0.9);
    border-radius: 10px;
    padding: 1rem 1.25rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}
[data-testid="stMetricLabel"] p {
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.03em !important;
    text-transform: uppercase !important;
    color: #94A3B8 !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.5rem !important;
    font-weight: 700 !important;
    color: #F1F5F9 !important;
}
[data-testid="stMetricDelta"] svg { display: none; }
[data-testid="stMetricDelta"] > div {
    font-size: 0.82rem !important;
}
/* Section headers */
.section-head {
    font-size: 1.0rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: #CBD5E1;
    margin: 1.5rem 0 0.75rem 0;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid rgba(51,65,85,0.8);
}
/* Insights */
.insight-box {
    background: rgba(15,23,42,0.7);
    border: 1px solid rgba(51,65,85,0.8);
    border-radius: 10px;
    padding: 1.25rem 1.5rem;
    margin-top: 0.5rem;
}
.insight-bullet {
    display: flex;
    align-items: flex-start;
    gap: 0.6rem;
    margin: 0.55rem 0;
    color: #CBD5E1;
    font-size: 0.88rem;
    line-height: 1.5;
}
.insight-bullet::before {
    content: "▸";
    color: #3B82F6;
    flex-shrink: 0;
    margin-top: 0.05rem;
}
</style>
""", unsafe_allow_html=True)

# ── Config & data ─────────────────────────────────────────────────────────────
@st.cache_data
def load_config():
    with open("config/institutions.json") as f:
        return {i["abn"]: i for i in json.load(f)["big5"]}

@st.cache_data
def load_data():
    df = pd.read_csv(
        "data/processed/housing_market_share_by_institution.csv",
        dtype={"abn": str},
    )
    df["period"]    = pd.to_datetime(df["period"])
    df["big5_flag"] = df["big5_flag"].astype(str).str.lower() == "true"
    return df

BIG5_CONFIG = load_config()
BIG5_ABNS   = list(BIG5_CONFIG.keys())
df          = load_data()

LOAN_TYPE_MAP = {
    "Total Housing":  ("total_housing_value_millions",  "system_total_housing_millions",  "total_housing_share"),
    "Owner-occupied": ("owner_occupied_value_millions", "system_owner_occupied_millions", "owner_occupied_share"),
    "Investment":     ("investment_value_millions",      "system_investment_millions",     "investment_share"),
}

PALETTE = [
    "#3B82F6","#EF4444","#10B981","#F59E0B","#8B5CF6","#06B6D4",
    "#EC4899","#84CC16","#F97316","#6366F1","#14B8A6","#D97706",
    "#A855F7","#0EA5E9","#BE185D","#22C55E","#E11D48","#2563EB",
    "#7C3AED","#059669","#DC2626","#CA8A04","#0369A1","#65A30D","#9333EA",
]
OTHER_COLOR  = "#475569"
BIG5_GROUP_COLOR    = "#2563EB"   # grouped Big 5 series
NON_BIG5_GROUP_COLOR = "#64748B"  # grouped Non-Big 5 series

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Controls")
    loan_type  = st.selectbox("Loan type",   list(LOAN_TYPE_MAP.keys()), index=0)
    chart_mode = st.selectbox("Chart mode",  ["Institutions", "Big 5 vs Non–Big 5"], index=0)
    if chart_mode == "Institutions":
        universe = st.selectbox("Universe",  ["Big 5 only", "All institutions"], index=0)
        top_n    = st.slider("Top N institutions", 5, 25, 10) if universe == "All institutions" else None
    else:
        universe = None
        top_n    = None

value_col, system_col, share_col = LOAN_TYPE_MAP[loan_type]

# ── Reference periods ─────────────────────────────────────────────────────────
all_periods     = sorted(df["period"].unique())
latest          = all_periods[-1]
prev_period     = all_periods[-2] if len(all_periods) >= 2 else None

def nearest_period(target):
    t = pd.Timestamp(target)
    return min(all_periods, key=lambda p: abs((p - t).days))

yoy_period      = nearest_period(latest - pd.DateOffset(years=1))
inception_period = nearest_period(pd.Timestamp("2019-03-01"))

# ── Scalar helpers ────────────────────────────────────────────────────────────
def sys_val(period, col):
    return df[df["period"] == period][col].max()

def b5_val(period, col):
    return df[(df["period"] == period) & df["big5_flag"]][col].sum()

def safe_pct(a, b):
    return (a / b - 1) * 100 if b and b > 0 and a is not None else None

def safe_cagr(end, start, yrs):
    return ((end / start) ** (1 / yrs) - 1) * 100 if all(v and v > 0 for v in [end, start]) else None

# ── Chart layout ──────────────────────────────────────────────────────────────
CHART_LAYOUT = dict(
    plot_bgcolor  = "rgba(15,23,42,0.55)",
    paper_bgcolor = "rgba(0,0,0,0)",
    margin        = dict(t=20, b=20, l=0, r=0),
    height        = 490,
    hovermode     = "x unified",
    font          = dict(color="#CBD5E1", family="Inter, system-ui, sans-serif", size=13),
    xaxis = dict(
        showgrid   = False,
        showline   = True,
        linecolor  = "#334155",
        tickcolor  = "#475569",
        tickfont   = dict(color="#94A3B8", size=13),
        tickformat = "%b %Y",
        title      = None,
    ),
    yaxis = dict(
        showgrid   = True,
        gridcolor  = "rgba(51,65,85,0.5)",
        gridwidth  = 1,
        showline   = False,
        tickfont   = dict(color="#94A3B8", size=13),
        title      = dict(text="Loan balance ($B)", font=dict(color="#94A3B8", size=13)),
        tickprefix = "$",
        ticksuffix = "B",
        tickformat = ",.0f",
        zeroline   = False,
    ),
    legend = dict(
        orientation = "v",
        yanchor     = "middle",
        y           = 0.5,
        xanchor     = "left",
        x           = 1.01,
        font        = dict(size=14, color="#CBD5E1"),
        traceorder  = "reversed",
        bgcolor     = "rgba(15,23,42,0.5)",
        bordercolor = "#334155",
        borderwidth = 1,
    ),
)

def make_stacked_area(series_list):
    fig = go.Figure()

    # Pre-compute per-period visible totals (for % in hover)
    period_totals = pd.Series(0.0, index=all_periods)
    for s in series_list:
        period_totals += s["data"].reindex(all_periods).fillna(0) / 1000

    for s in series_list:
        vals_bn    = s["data"].reindex(all_periods).fillna(0) / 1000
        pct_series = (vals_bn / period_totals.replace(0, np.nan) * 100).fillna(0)
        customdata = pct_series.values.reshape(-1, 1)

        fig.add_trace(go.Scatter(
            x             = all_periods,
            y             = vals_bn,
            name          = s["name"],
            mode          = "lines",
            stackgroup    = "one",
            fillcolor     = s["color"],
            line          = dict(color="rgba(255,255,255,0.15)", width=0.8),
            customdata    = customdata,
            hovertemplate = (
                "$%{y:,.2f}B · %{customdata[0]:.1f}%"
                "<extra>" + s["name"] + "</extra>"
            ),
        ))

    fig.update_layout(**CHART_LAYOUT)
    return fig

# ── Build series ──────────────────────────────────────────────────────────────
if chart_mode == "Big 5 vs Non–Big 5":
    b5_by_period  = df[df["big5_flag"]].groupby("period")[value_col].sum()
    sys_by_period = df.groupby("period")[system_col].max()
    non_b5_by_period = (sys_by_period - b5_by_period).clip(lower=0)
    series = [
        {"name": "Non–Big 5", "color": NON_BIG5_GROUP_COLOR, "data": non_b5_by_period},
        {"name": "Big 5",     "color": BIG5_GROUP_COLOR,     "data": b5_by_period},
    ]

elif universe == "Big 5 only":
    pivot   = (
        df[df["big5_flag"]]
        .pivot_table(index="period", columns="abn", values=value_col, aggfunc="sum")
        .reindex(columns=BIG5_ABNS)
    )
    ordered = pivot.mean().sort_values().index.tolist()
    series  = [
        {"name":  BIG5_CONFIG[a]["short"],
         "color": BIG5_CONFIG[a]["brand_color"],
         "data":  pivot[a]}
        for a in ordered
    ]

else:  # All institutions
    latest_fum  = (df[df["period"] == latest]
                   .groupby("institution_name")[value_col].sum()
                   .sort_values(ascending=False))
    top_names   = latest_fum.head(top_n).index.tolist()
    other_names = latest_fum.iloc[top_n:].index.tolist()
    pivot       = df.pivot_table(index="period", columns="institution_name",
                                  values=value_col, aggfunc="sum")
    ordered     = pivot[top_names].mean().sort_values().index.tolist()
    p_idx, color_map = 0, {}
    for name in ordered:
        abn = df[df["institution_name"] == name]["abn"].iloc[0] if (df["institution_name"] == name).any() else None
        if abn and abn in BIG5_CONFIG:
            color_map[name] = BIG5_CONFIG[abn]["brand_color"]
        else:
            color_map[name] = PALETTE[p_idx % len(PALETTE)]
            p_idx += 1
    series = [{"name": n, "color": color_map[n], "data": pivot[n]} for n in ordered]
    if other_names:
        other_cols = [n for n in other_names if n in pivot.columns]
        other_data = pivot[other_cols].sum(axis=1) if other_cols else pd.Series(0, index=all_periods)
        series.insert(0, {"name": f"Other ({len(other_names)} institutions)",
                          "color": OTHER_COLOR, "data": other_data})

# ── Title + chart ─────────────────────────────────────────────────────────────
st.title("Australian Residential Lending ($FUM)")
st.caption(
    f"APRA monthly ADI statistics  ·  Residential lending  ·  "
    f"{df['period'].min().strftime('%b %Y')} – {latest.strftime('%b %Y')}"
)
st.plotly_chart(make_stacked_area(series), use_container_width=True)

# ── Compute metrics ───────────────────────────────────────────────────────────
sys_lat       = sys_val(latest,           system_col)
sys_prev      = sys_val(prev_period,      system_col) if prev_period else None
sys_yoy       = sys_val(yoy_period,       system_col)
sys_inception = sys_val(inception_period, system_col)

b5_lat        = b5_val(latest,      value_col)
b5_prev       = b5_val(prev_period, value_col) if prev_period else None
b5_yoy        = b5_val(yoy_period,  value_col)

b5_shr_lat    = b5_lat  / sys_lat  if sys_lat  else None
b5_shr_prev   = b5_prev / sys_prev if sys_prev else None
b5_shr_yoy    = b5_yoy  / sys_yoy  if sys_yoy  else None

b5_shr_pp_mom = (b5_shr_lat - b5_shr_prev) * 100 if b5_shr_lat and b5_shr_prev else None
b5_shr_pp_yoy = (b5_shr_lat - b5_shr_yoy)  * 100 if b5_shr_lat and b5_shr_yoy  else None

mom_delta_bn  = (sys_lat - sys_prev) / 1000 if sys_prev else None
mom_pct       = safe_pct(sys_lat, sys_prev)
yoy_delta_bn  = (sys_lat - sys_yoy)  / 1000
yoy_pct       = safe_pct(sys_lat, sys_yoy)

b5_mom_delta_bn = (b5_lat - b5_prev) / 1000 if b5_prev else None
b5_mom_pct      = safe_pct(b5_lat, b5_prev)

n_years_inception = (latest - inception_period).days / 365.25
avg_annual_growth = safe_cagr(sys_lat, sys_inception, n_years_inception)

b5_yoy_delta_m  = b5_lat - b5_yoy
sys_yoy_delta_m = sys_lat - sys_yoy
b5_contribution = (b5_yoy_delta_m / sys_yoy_delta_m * 100) if sys_yoy_delta_m else None

# ── Format helpers ────────────────────────────────────────────────────────────
def fbn(v):   return f"${v:,.1f}B" if v is not None else "—"
def fpct(v):  return f"{v:.2f}%"   if v is not None else "—"
def fpp(v):   return f"{v:+.2f}pp" if v is not None else "—"
def fsign_bn(v): return f"{v:+,.1f}B" if v is not None else None
def fsign_pct(v): return f"{v:+.2f}%" if v is not None else None

# ── MARKET SIZE cards ─────────────────────────────────────────────────────────
st.markdown('<div class="section-head">Market Size</div>', unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)

with c1:
    delta_parts = []
    if mom_delta_bn is not None: delta_parts.append(f"{mom_delta_bn:+,.1f}B")
    if mom_pct      is not None: delta_parts.append(f"({mom_pct:+.2f}%)")
    st.metric(
        f"Total Residential Loans (All ADIs)\nas at {latest.strftime('%b %Y')}",
        fbn(sys_lat / 1000),
        delta=" ".join(delta_parts) if delta_parts else None,
        delta_color="off",
        help="Aggregate balance across all licensed ADIs reporting to APRA",
    )

with c2:
    delta_parts = []
    if b5_mom_delta_bn is not None: delta_parts.append(f"{b5_mom_delta_bn:+,.1f}B")
    if b5_mom_pct      is not None: delta_parts.append(f"({b5_mom_pct:+.2f}%)")
    st.metric(
        f"Big 5 Total Residential Lending\nas at {latest.strftime('%b %Y')}",
        fbn(b5_lat / 1000),
        delta=" ".join(delta_parts) if delta_parts else None,
        delta_color="off",
    )

with c3:
    share_delta_parts = []
    if b5_shr_pp_mom is not None: share_delta_parts.append(f"{b5_shr_pp_mom:+.2f}pp MoM")
    if b5_shr_pp_yoy is not None: share_delta_parts.append(f"{b5_shr_pp_yoy:+.2f}pp YoY")
    st.metric(
        f"Big 5 Market Share\nas at {latest.strftime('%b %Y')}",
        fpct(b5_shr_lat * 100) if b5_shr_lat else "—",
        delta="  ·  ".join(share_delta_parts) if share_delta_parts else None,
        delta_color="off",
    )

# ── GROWTH cards ──────────────────────────────────────────────────────────────
st.markdown('<div class="section-head">Growth</div>', unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)

with c1:
    label = (
        f"Change vs Prior Month\n"
        f"{prev_period.strftime('%b %Y') if prev_period else ''} → {latest.strftime('%b %Y')}"
    )
    st.metric(
        label,
        fbn(mom_delta_bn),
        delta=fsign_pct(mom_pct),
        delta_color="normal",
    )

with c2:
    st.metric(
        f"Year-on-Year Change\n{yoy_period.strftime('%b %Y')} → {latest.strftime('%b %Y')}",
        fbn(yoy_delta_bn),
        delta=fsign_pct(yoy_pct),
        delta_color="normal",
    )

with c3:
    st.metric(
        f"Average Annual Growth\n{inception_period.strftime('%b %Y')} → {latest.strftime('%b %Y')}",
        fpct(avg_annual_growth) if avg_annual_growth else "—",
        help="Compound annual growth rate from the start of the APRA data series",
    )

# ── Insights ──────────────────────────────────────────────────────────────────
def inst_yoy_analysis(v_col, sys_col):
    g_lat  = df[df["period"] == latest].groupby("institution_name").agg(
                 v_lat=(v_col, "sum"), abn=("abn", "first"))
    g_yoy  = df[df["period"] == yoy_period].groupby("institution_name").agg(
                 v_yoy=(v_col, "sum"))
    merged = g_lat.join(g_yoy, how="inner").dropna()
    s_lat  = sys_val(latest,     sys_col)
    s_yoy  = sys_val(yoy_period, sys_col)
    merged["delta_m"]  = merged["v_lat"] - merged["v_yoy"]
    merged["shr_lat"]  = merged["v_lat"] / s_lat if s_lat else 0
    merged["shr_yoy"]  = merged["v_yoy"] / s_yoy if s_yoy else 0
    merged["delta_pp"] = (merged["shr_lat"] - merged["shr_yoy"]) * 100
    return merged.reset_index()

inst = inst_yoy_analysis(value_col, system_col)

def bold(text):
    return re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)

bullets = []

if yoy_pct is not None:
    verb = "grew" if yoy_delta_bn > 0 else "contracted"
    bullets.append(
        f"System {loan_type.lower()} loans {verb} by **${abs(yoy_delta_bn):,.1f}B** "
        f"(**{yoy_pct:+.1f}%**) over the year to {latest.strftime('%b %Y')}, "
        f"reaching **{fbn(sys_lat/1000)}** outstanding."
    )

if b5_shr_pp_yoy is not None:
    verb = "gained" if b5_shr_pp_yoy > 0 else "shed"
    bullets.append(
        f"The Big 5 **{verb} {abs(b5_shr_pp_yoy):.2f}pp** of market share year-on-year, "
        f"now holding **{b5_shr_lat*100:.1f}%** of system {loan_type.lower()} FUM "
        f"(from **{b5_shr_yoy*100:.1f}%** a year ago)."
    )

if len(inst) > 0:
    top = inst.loc[inst["delta_m"].idxmax()]
    bullets.append(
        f"**{top['institution_name']}** recorded the largest absolute YoY increase, "
        f"adding **${top['delta_m']/1000:,.2f}B** in {loan_type.lower()} loans "
        f"(${top['v_yoy']/1000:,.1f}B → ${top['v_lat']/1000:,.1f}B)."
    )

if len(inst) > 0:
    top_pp  = inst.loc[inst["delta_pp"].idxmax()]
    top_dol = inst.loc[inst["delta_m"].idxmax()]
    if top_pp["institution_name"] != top_dol["institution_name"]:
        bullets.append(
            f"**{top_pp['institution_name']}** posted the largest market share gain, "
            f"up **{top_pp['delta_pp']:+.2f}pp** YoY "
            f"({top_pp['shr_yoy']*100:.2f}% → {top_pp['shr_lat']*100:.2f}%)."
        )

oo_lat   = sys_val(latest,     "system_owner_occupied_millions")
oo_yoy_  = sys_val(yoy_period, "system_owner_occupied_millions")
inv_lat  = sys_val(latest,     "system_investment_millions")
inv_yoy_ = sys_val(yoy_period, "system_investment_millions")
oo_pct   = safe_pct(oo_lat,  oo_yoy_)
inv_pct  = safe_pct(inv_lat, inv_yoy_)

if oo_pct is not None and inv_pct is not None:
    faster     = "owner-occupied" if oo_pct > inv_pct else "investment"
    slower     = "investment"     if faster == "owner-occupied" else "owner-occupied"
    f_pct      = oo_pct  if faster == "owner-occupied" else inv_pct
    s_pct      = inv_pct if faster == "owner-occupied" else oo_pct
    f_delta_bn = (oo_lat - oo_yoy_) / 1000 if faster == "owner-occupied" else (inv_lat - inv_yoy_) / 1000
    s_delta_bn = (inv_lat - inv_yoy_) / 1000 if faster == "owner-occupied" else (oo_lat - oo_yoy_) / 1000
    bullets.append(
        f"**{faster.title()}** lending grew faster YoY (**{f_pct:+.1f}%**, +${abs(f_delta_bn):,.1f}B) "
        f"than **{slower}** lending (**{s_pct:+.1f}%**, +${abs(s_delta_bn):,.1f}B)."
    )

if avg_annual_growth is not None:
    bullets.append(
        f"The system {loan_type.lower()} book has grown at **{avg_annual_growth:.1f}% p.a.** "
        f"on average since {inception_period.strftime('%b %Y')} "
        f"({inception_period.strftime('%b %Y')} → {latest.strftime('%b %Y')})."
    )

st.divider()
st.markdown("### Insights")
bullet_html = "\n".join(
    f'<div class="insight-bullet">{bold(b)}</div>' for b in bullets
)
st.markdown(
    f'<div class="insight-box">{bullet_html}</div>',
    unsafe_allow_html=True,
)

st.caption(
    "Source: APRA Monthly ADI Statistics  ·  Values in $billions  ·  "
    "Big 5: CBA · Westpac · NAB · ANZ · Macquarie"
)

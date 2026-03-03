import json
import re
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Australian Housing Loans ($FUM)", layout="wide")

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
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
    color: #94A3B8 !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.45rem !important;
    font-weight: 700 !important;
    color: #F1F5F9 !important;
}
[data-testid="stMetricDelta"] svg { display: none; }
[data-testid="stMetricDelta"] > div {
    font-size: 0.78rem !important;
    color: #94A3B8 !important;
}
/* Section headers */
.section-head {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #64748B;
    margin: 1.25rem 0 0.5rem 0;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid rgba(51,65,85,0.6);
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
OTHER_COLOR = "#475569"

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Controls")
    loan_type = st.selectbox("Loan type", list(LOAN_TYPE_MAP.keys()), index=0)
    universe  = st.selectbox("Universe", ["Big 5 only", "All institutions"], index=0)
    top_n = st.slider("Top N institutions", 5, 25, 10) if universe == "All institutions" else None

value_col, system_col, share_col = LOAN_TYPE_MAP[loan_type]

# ── Reference periods ─────────────────────────────────────────────────────────
all_periods = sorted(df["period"].unique())
latest      = all_periods[-1]
prev_period = all_periods[-2] if len(all_periods) >= 2 else None

def nearest_period(target):
    t = pd.Timestamp(target)
    return min(all_periods, key=lambda p: abs((p - t).days))

yoy_period  = nearest_period(latest - pd.DateOffset(years=1))
cagr_period = nearest_period(latest - pd.DateOffset(years=3))

# ── Scalar helpers ────────────────────────────────────────────────────────────
def sys_val(period, col):
    return df[df["period"] == period][col].max()

def b5_val(period, col):
    return df[(df["period"] == period) & df["big5_flag"]][col].sum()

def safe_pct(a, b):
    return (a / b - 1) * 100 if b and b > 0 and a is not None else None

def safe_cagr(end, start, yrs):
    return ((end / start) ** (1 / yrs) - 1) * 100 if all(v and v > 0 for v in [end, start]) else None

# ── Chart theme ───────────────────────────────────────────────────────────────
CHART_LAYOUT = dict(
    plot_bgcolor  = "rgba(15,23,42,0.55)",
    paper_bgcolor = "rgba(0,0,0,0)",
    margin        = dict(t=20, b=20, l=0, r=0),
    height        = 490,
    hovermode     = "x unified",
    font          = dict(color="#CBD5E1", family="Inter, system-ui, sans-serif", size=12),
    xaxis = dict(
        showgrid   = False,
        showline   = True,
        linecolor  = "#334155",
        tickcolor  = "#475569",
        tickfont   = dict(color="#94A3B8", size=11),
        tickformat = "%b %Y",
        title      = None,
    ),
    yaxis = dict(
        showgrid    = True,
        gridcolor   = "rgba(51,65,85,0.5)",
        gridwidth   = 1,
        showline    = False,
        tickfont    = dict(color="#94A3B8", size=11),
        title       = dict(text="Loan balance ($B)", font=dict(color="#94A3B8", size=11)),
        tickprefix  = "$",
        ticksuffix  = "B",
        tickformat  = ",.0f",
        zeroline    = False,
    ),
    legend = dict(
        orientation = "v",
        yanchor     = "middle",
        y           = 0.5,
        xanchor     = "left",
        x           = 1.01,
        font        = dict(size=12, color="#CBD5E1"),
        traceorder  = "reversed",
        bgcolor     = "rgba(15,23,42,0.5)",
        bordercolor = "#334155",
        borderwidth = 1,
    ),
)

def make_stacked_area(series_list):
    fig = go.Figure()
    for s in series_list:
        vals_bn = s["data"].reindex(all_periods).fillna(0) / 1000
        fig.add_trace(go.Scatter(
            x             = all_periods,
            y             = vals_bn,
            name          = s["name"],
            mode          = "lines",
            stackgroup    = "one",
            fillcolor     = s["color"],
            line          = dict(color="rgba(255,255,255,0.15)", width=0.8),
            hovertemplate = "%{x|%b %Y}<br>$%{y:,.2f}B<extra>" + s["name"] + "</extra>",
        ))
    fig.update_layout(**CHART_LAYOUT)
    return fig

# ── Build series ──────────────────────────────────────────────────────────────
if universe == "Big 5 only":
    pivot = (
        df[df["big5_flag"]]
        .pivot_table(index="period", columns="abn", values=value_col, aggfunc="sum")
        .reindex(columns=BIG5_ABNS)
    )
    ordered = pivot.mean().sort_values().index.tolist()
    series  = [{"name": BIG5_CONFIG[a]["short"], "color": BIG5_CONFIG[a]["brand_color"],
                 "data": pivot[a]} for a in ordered]

else:
    latest_fum  = (df[df["period"] == latest]
                   .groupby("institution_name")[value_col].sum()
                   .sort_values(ascending=False))
    top_names   = latest_fum.head(top_n).index.tolist()
    other_names = latest_fum.iloc[top_n:].index.tolist()
    pivot       = df.pivot_table(index="period", columns="institution_name",
                                  values=value_col, aggfunc="sum")
    ordered     = pivot[top_names].mean().sort_values().index.tolist()
    p_idx       = 0
    color_map   = {}
    for name in ordered:
        abn = df[df["institution_name"] == name]["abn"].iloc[0] if (df["institution_name"] == name).any() else None
        color_map[name] = BIG5_CONFIG[abn]["brand_color"] if abn in (BIG5_CONFIG or {}) else PALETTE[p_idx % len(PALETTE)]
        if abn not in (BIG5_CONFIG or {}): p_idx += 1
    series = [{"name": n, "color": color_map[n], "data": pivot[n]} for n in ordered]
    if other_names:
        other_cols = [n for n in other_names if n in pivot.columns]
        other_data = pivot[other_cols].sum(axis=1) if other_cols else pd.Series(0, index=all_periods)
        series.insert(0, {"name": f"Other ({len(other_names)} institutions)",
                          "color": OTHER_COLOR, "data": other_data})

# ── Title + chart ─────────────────────────────────────────────────────────────
st.title("Australian Housing Loans ($FUM)")
st.caption(
    f"APRA monthly ADI statistics  ·  {loan_type}  ·  "
    f"{df['period'].min().strftime('%b %Y')} – {latest.strftime('%b %Y')}"
)
st.plotly_chart(make_stacked_area(series), use_container_width=True)

# ── Compute all metrics ───────────────────────────────────────────────────────
sys_lat   = sys_val(latest,      system_col)
sys_prev  = sys_val(prev_period, system_col) if prev_period else None
sys_yoy   = sys_val(yoy_period,  system_col)
sys_cagr0 = sys_val(cagr_period, system_col)

b5_lat    = b5_val(latest,      value_col)
b5_prev   = b5_val(prev_period, value_col) if prev_period else None
b5_yoy    = b5_val(yoy_period,  value_col)

b5_shr_lat = b5_lat / sys_lat if sys_lat else None
b5_shr_yoy = b5_yoy / sys_yoy if sys_yoy else None

mom_delta   = (sys_lat - sys_prev) / 1000 if sys_prev else None
mom_pct     = safe_pct(sys_lat, sys_prev)
yoy_delta   = (sys_lat - sys_yoy) / 1000
yoy_pct     = safe_pct(sys_lat, sys_yoy)
cagr_3yr    = safe_cagr(sys_lat, sys_cagr0, 3)

b5_shr_pp_yoy   = (b5_shr_lat - b5_shr_yoy) * 100 if b5_shr_lat and b5_shr_yoy else None
b5_yoy_delta_m  = b5_lat - b5_yoy
sys_yoy_delta_m = sys_lat - sys_yoy
b5_contribution = (b5_yoy_delta_m / sys_yoy_delta_m * 100) if sys_yoy_delta_m else None

# Universe FUM
if universe == "Big 5 only":
    univ_fum_bn   = b5_lat / 1000
    univ_label    = "Big 5"
else:
    top_set       = set(latest_fum.head(top_n).index)
    univ_fum_bn   = df[(df["period"] == latest) & df["institution_name"].isin(top_set)][value_col].sum() / 1000
    univ_label    = f"Top {top_n}"

# ── Format helpers ────────────────────────────────────────────────────────────
def fbn(v):    return f"${v:,.1f}B"  if v is not None else "—"
def fpct(v):   return f"{v:.2f}%"   if v is not None else "—"
def fpp(v):    return f"{v:+.2f}pp" if v is not None else "—"
def fdelta(v): return f"{v:+,.1f}B" if v is not None else None
def fmom(p, q): return f"{p.strftime('%b')} → {q.strftime('%b %Y')}"

# ── Metric cards — Market Size ────────────────────────────────────────────────
st.markdown('<div class="section-head">Market Size</div>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric(
        f"{loan_type} Outstanding — All ADIs\n{latest.strftime('%b %Y')} month-end",
        fbn(sys_lat / 1000),
        delta=fdelta(mom_delta),
        delta_color="off",
        help="Sum of all licensed ADIs reporting to APRA",
    )
with c2:
    st.metric(
        f"{univ_label} {loan_type}\n{latest.strftime('%b %Y')} month-end",
        fbn(univ_fum_bn),
        delta=fdelta((b5_lat - b5_prev) / 1000 if universe == "Big 5 only" and b5_prev else None),
        delta_color="off",
    )
with c3:
    st.metric(
        f"Big 5 Market Share\n{latest.strftime('%b %Y')}",
        fpct(b5_shr_lat * 100) if b5_shr_lat else "—",
        delta=f"{fpp(b5_shr_pp_yoy)} YoY" if b5_shr_pp_yoy else None,
        delta_color="off",
    )
with c4:
    st.metric(
        f"Big 5 Share of YoY System Growth\n{yoy_period.strftime('%b %Y')} → {latest.strftime('%b %Y')}",
        fpct(b5_contribution) if b5_contribution else "—",
        help="Big 5 $ growth as % of total system $ growth over the year",
    )

# ── Metric cards — Growth ─────────────────────────────────────────────────────
st.markdown('<div class="section-head">Growth</div>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric(
        f"MoM Change\n{fmom(prev_period, latest) if prev_period else ''}",
        fbn(mom_delta),
        delta=fpct(mom_pct) if mom_pct else None,
        delta_color="off",
    )
with c2:
    st.metric(
        f"YoY Change\n{yoy_period.strftime('%b %Y')} → {latest.strftime('%b %Y')}",
        fbn(yoy_delta),
        delta=fpct(yoy_pct) if yoy_pct else None,
        delta_color="off",
    )
with c3:
    st.metric(
        f"3-Year CAGR\n{cagr_period.strftime('%b %Y')} → {latest.strftime('%b %Y')}",
        fpct(cagr_3yr) if cagr_3yr else "—",
    )
with c4:
    st.metric(
        f"Big 5 Share — YoY Change\n{yoy_period.strftime('%b %Y')} → {latest.strftime('%b %Y')}",
        fpp(b5_shr_pp_yoy) if b5_shr_pp_yoy else "—",
        delta=f"From {fpct(b5_shr_yoy*100)}" if b5_shr_yoy else None,
        delta_color="off",
    )

# ── Insights ──────────────────────────────────────────────────────────────────
# Per-institution YoY analysis
def inst_yoy_analysis(v_col, sys_col):
    g_lat = df[df["period"] == latest].groupby("institution_name").agg(
        v_lat=(v_col, "sum"), abn=("abn", "first"))
    g_yoy = df[df["period"] == yoy_period].groupby("institution_name").agg(
        v_yoy=(v_col, "sum"))
    merged    = g_lat.join(g_yoy, how="inner").dropna()
    s_lat     = sys_val(latest,      sys_col)
    s_yoy     = sys_val(yoy_period,  sys_col)
    merged["delta_m"]  = merged["v_lat"] - merged["v_yoy"]
    merged["shr_lat"]  = merged["v_lat"] / s_lat  if s_lat else 0
    merged["shr_yoy"]  = merged["v_yoy"] / s_yoy  if s_yoy else 0
    merged["delta_pp"] = (merged["shr_lat"] - merged["shr_yoy"]) * 100
    return merged.reset_index()

inst = inst_yoy_analysis(value_col, system_col)

def bold(text):
    """Convert **bold** markers to HTML <strong>."""
    return re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)

bullets = []

# 1. System YoY growth
if yoy_pct is not None:
    verb = "grew" if yoy_delta > 0 else "contracted"
    bullets.append(
        f"System {loan_type.lower()} loans {verb} by **${abs(yoy_delta):,.1f}B** "
        f"(**{yoy_pct:+.1f}%**) over the year to {latest.strftime('%b %Y')}, "
        f"reaching **{fbn(sys_lat/1000)}** outstanding."
    )

# 2. Big 5 share change
if b5_shr_pp_yoy is not None:
    verb = "gained" if b5_shr_pp_yoy > 0 else "shed"
    bullets.append(
        f"The Big 5 **{verb} {abs(b5_shr_pp_yoy):.2f}pp** of market share year-on-year, "
        f"now holding **{b5_shr_lat*100:.1f}%** of total system {loan_type.lower()} FUM "
        f"(from **{b5_shr_yoy*100:.1f}%** a year ago)."
    )

# 3. Largest YoY $ mover
if len(inst) > 0:
    top = inst.loc[inst["delta_m"].idxmax()]
    bullets.append(
        f"**{top['institution_name']}** recorded the largest absolute YoY increase, "
        f"adding **${top['delta_m']/1000:,.2f}B** in {loan_type.lower()} loans "
        f"(${top['v_yoy']/1000:,.1f}B → ${top['v_lat']/1000:,.1f}B)."
    )

# 4. Largest YoY share gainer (if different from #3)
if len(inst) > 0:
    top_pp  = inst.loc[inst["delta_pp"].idxmax()]
    top_dol = inst.loc[inst["delta_m"].idxmax()]
    if top_pp["institution_name"] != top_dol["institution_name"]:
        bullets.append(
            f"**{top_pp['institution_name']}** posted the largest market share gain, "
            f"up **{top_pp['delta_pp']:+.2f}pp** YoY "
            f"({top_pp['shr_yoy']*100:.2f}% → {top_pp['shr_lat']*100:.2f}%)."
        )

# 5. OO vs Investment split (always computed regardless of selected loan type)
oo_lat  = sys_val(latest,      "system_owner_occupied_millions")
oo_yoy_ = sys_val(yoy_period,  "system_owner_occupied_millions")
inv_lat = sys_val(latest,      "system_investment_millions")
inv_yoy_= sys_val(yoy_period,  "system_investment_millions")
oo_pct  = safe_pct(oo_lat,  oo_yoy_)
inv_pct = safe_pct(inv_lat, inv_yoy_)

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

# 6. 3yr CAGR
if cagr_3yr is not None:
    bullets.append(
        f"The system {loan_type.lower()} book has compounded at **{cagr_3yr:.1f}% p.a.** "
        f"over the past 3 years ({cagr_period.strftime('%b %Y')} → {latest.strftime('%b %Y')})."
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

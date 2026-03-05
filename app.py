import json
import re
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import ui_style
import charts  # noqa: F401  — available for future chart helpers

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Australian Residential Lending ($FUM)", layout="wide")

# ── CSS: global / Streamlit-internal overrides only ───────────────────────────
# NOTE: @import for fonts (no <link> tags – they confuse Streamlit's parser).
# All custom HTML components use inline styles for reliability.
_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*='css'], .stApp {
    font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
    background-color: #0B1220 !important;
    color: #E6EDF6 !important;
}
.block-container {
    padding-top: 2.5rem !important;
    padding-bottom: 3rem !important;
    max-width: 1440px !important;
}
h1 {
    font-family: 'Inter', sans-serif !important;
    font-size: 2.75rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.025em !important;
    color: #E6EDF6 !important;
    line-height: 1.1 !important;
    margin-bottom: 0.2rem !important;
}
h2, h3 { color: #E6EDF6 !important; font-family: 'Inter', sans-serif !important; }

[data-testid='stSidebar'] {
    background: #0D1526 !important;
    border-right: 1px solid rgba(255,255,255,0.05) !important;
}
[data-testid='stSidebar'] h1 {
    font-size: 1rem !important;
    font-weight: 700 !important;
    letter-spacing: 0 !important;
    color: #E6EDF6 !important;
}
[data-testid='stSidebar'] .stRadio > label,
[data-testid='stSidebar'] .stSlider > label {
    font-size: 0.67rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    color: #6C7A99 !important;
    display: block !important;
    margin-bottom: 4px !important;
}

div[data-testid='stRadio'] > div {
    display: flex !important;
    flex-direction: column !important;
    gap: 3px !important;
    background: rgba(11,18,32,0.9) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 8px !important;
    padding: 3px !important;
}
div[data-testid='stRadio'] label {
    display: flex !important;
    align-items: center !important;
    border-radius: 6px !important;
    padding: 7px 12px !important;
    cursor: pointer !important;
    transition: background 0.15s ease, color 0.15s ease !important;
    margin: 0 !important;
}
div[data-testid='stRadio'] label p {
    font-size: 12px !important;
    font-weight: 600 !important;
    color: #6C7A99 !important;
    margin: 0 !important;
    letter-spacing: 0.02em !important;
    line-height: 1 !important;
}
div[data-testid='stRadio'] label:has(input:checked) {
    background: #1E3A5F !important;
}
div[data-testid='stRadio'] label:has(input:checked) p {
    color: #60A5FA !important;
}
div[data-testid='stRadio'] input[type='radio'] {
    position: absolute !important;
    opacity: 0 !important;
    width: 0 !important;
    height: 0 !important;
    pointer-events: none !important;
}

hr { border-color: rgba(255,255,255,0.05) !important; margin: 2rem 0 !important; }
.stCaption p, [data-testid='stCaptionContainer'] p {
    color: #6C7A99 !important;
    font-size: 0.77rem !important;
}
footer    { visibility: hidden; }
#MainMenu { visibility: hidden; }
"""
st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)
ui_style.apply_global_css()  # adds card, section, toolbar, and typography helpers

# ── Inline style constants (all custom HTML uses these – no CSS class deps) ───
_F  = "font-family:Inter,system-ui,sans-serif;"

_SH = (                                      # section header
    f"{_F}font-size:0.67rem;font-weight:700;letter-spacing:0.13em;"
    "text-transform:uppercase;color:#6C7A99;"
    "margin:2.5rem 0 1rem 0;padding-bottom:0.5rem;"
    "border-bottom:1px solid rgba(255,255,255,0.05);"
)
_SR = "display:flex;gap:14px;align-items:stretch;width:100%;margin-bottom:0.25rem;"  # card row
_SC = (                                      # card
    "flex:1;background:#111A2E;"
    "border:1px solid rgba(255,255,255,0.05);border-radius:8px;"
    "padding:20px 22px 18px;box-shadow:0 4px 20px rgba(0,0,0,0.3);"
    "display:flex;flex-direction:column;gap:10px;min-height:108px;"
)
_SL = (                                      # card label
    f"{_F}font-size:0.68rem;font-weight:700;letter-spacing:0.09em;"
    "text-transform:uppercase;color:#A8B3CF;line-height:1.45;"
)
_SSL = (                                     # card sub-label
    "display:block;font-size:0.85em;font-weight:500;"
    "letter-spacing:0;text-transform:none;color:#6C7A99;margin-top:2px;"
)
_SB  = "display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;"   # card body row
_SV  = (                                     # card value
    f"{_F}font-size:1.9rem;font-weight:700;color:#E6EDF6;"
    "font-variant-numeric:tabular-nums;letter-spacing:-0.02em;line-height:1;"
)
_SD  = f"{_F}font-size:0.82rem;font-weight:600;font-variant-numeric:tabular-nums;white-space:nowrap;"
_SDP = _SD + "color:#22C55E;"               # delta positive
_SDN = _SD + "color:#EF4444;"               # delta negative
_SDU = _SD + "color:#A8B3CF;"               # delta neutral
_SS  = f"{_F}font-size:0.7rem;color:#6C7A99;font-variant-numeric:tabular-nums;margin-top:-4px;"  # card sub-note

_IG  = "display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-top:1rem;"   # insight grid
_IC  = (                                     # insight card
    "background:#111A2E;border:1px solid rgba(255,255,255,0.05);border-radius:8px;"
    "padding:16px 18px;box-shadow:0 4px 16px rgba(0,0,0,0.2);"
    "display:flex;align-items:flex-start;gap:10px;"
    f"{_F}font-size:0.82rem;color:#CBD5E1;line-height:1.6;min-height:90px;"
)
_II  = "color:#3B82F6;flex-shrink:0;font-size:0.65rem;padding-top:0.35rem;"  # insight icon


# ── Helper: render a section header ───────────────────────────────────────────
def section_head(text):
    st.markdown(f'<div style="{_SH}">{text}</div>', unsafe_allow_html=True)


# ── Helper: build a metric card HTML string ───────────────────────────────────
def mcard(label, sublabel, value, delta=None, pos=None, sub=None):
    """
    label    : main label text (uppercase)
    sublabel : smaller sub-label below label (e.g. date context)
    value    : primary value string
    delta    : delta string shown INLINE to the RIGHT of value
    pos      : True → green, False → red, None → muted grey
    sub      : optional footnote beneath value row
    """
    sl_html = f'<span style="{_SSL}">{sublabel}</span>' if sublabel else ""
    ds      = _SDP if pos is True else (_SDN if pos is False else _SDU)
    d_html  = f'<span style="{ds}">{delta}</span>' if delta else ""
    s_html  = f'<div style="{_SS}">{sub}</div>' if sub else ""
    return (
        f'<div style="{_SC}">'
          f'<div style="{_SL}">{label}{sl_html}</div>'
          f'<div>'
            f'<div style="{_SB}">'
              f'<span style="{_SV}">{value}</span>'
              f'{d_html}'
            f'</div>'
            f'{s_html}'
          f'</div>'
        f'</div>'
    )


# ── Config & data ──────────────────────────────────────────────────────────────
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
OTHER_COLOR          = "#475569"
BIG5_GROUP_COLOR     = "#2563EB"
NON_BIG5_GROUP_COLOR = "#64748B"

def adj_color(color):
    """NAB uses pure black — lift to dark navy so it's visible on dark bg."""
    return "#252B3B" if color == "#000000" else color

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Controls")
    loan_type  = st.radio("Loan type",  list(LOAN_TYPE_MAP.keys()), index=0)
    chart_mode = st.radio("Chart mode", ["Institutions", "Big 5 vs Non–Big 5"], index=0)
    if chart_mode == "Institutions":
        universe = st.radio("Universe", ["Big 5 only", "All institutions"], index=0)
        top_n    = st.slider("Top N institutions", 5, 25, 10) if universe == "All institutions" else None
    else:
        universe = None
        top_n    = None

value_col, system_col, share_col = LOAN_TYPE_MAP[loan_type]

# ── Reference periods ──────────────────────────────────────────────────────────
all_periods      = sorted(df["period"].unique())
latest           = all_periods[-1]
prev_period      = all_periods[-2] if len(all_periods) >= 2 else None

def nearest_period(target):
    t = pd.Timestamp(target)
    return min(all_periods, key=lambda p: abs((p - t).days))

yoy_period       = nearest_period(latest - pd.DateOffset(years=1))
inception_period = nearest_period(pd.Timestamp("2019-03-01"))

# ── Scalar helpers ─────────────────────────────────────────────────────────────
def sys_val(period, col):
    return df[df["period"] == period][col].max()

def b5_val(period, col):
    return df[(df["period"] == period) & df["big5_flag"]][col].sum()

def safe_pct(a, b):
    return (a / b - 1) * 100 if b and b > 0 and a is not None else None

def safe_cagr(end, start, yrs):
    return ((end / start) ** (1 / yrs) - 1) * 100 if all(v and v > 0 for v in [end, start]) else None

# ── Chart layout ───────────────────────────────────────────────────────────────
CHART_LAYOUT = dict(
    plot_bgcolor  = "rgba(13,21,38,0.85)",
    paper_bgcolor = "rgba(0,0,0,0)",
    margin        = dict(t=24, b=24, l=0, r=175),
    height        = 510,
    hovermode     = "x unified",
    font          = dict(color="#A8B3CF", family="Inter, system-ui, sans-serif", size=13),
    xaxis = dict(
        showgrid   = False,
        showline   = True,
        linecolor  = "rgba(255,255,255,0.07)",
        tickcolor  = "rgba(255,255,255,0.07)",
        tickfont   = dict(color="#6C7A99", size=13),
        tickformat = "%b %Y",
        title      = None,
    ),
    yaxis = dict(
        showgrid   = True,
        gridcolor  = "rgba(255,255,255,0.04)",
        gridwidth  = 1,
        showline   = False,
        tickfont   = dict(color="#6C7A99", size=13),
        title      = dict(text="Loan balance ($B)", font=dict(color="#6C7A99", size=13)),
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
        x           = 1.02,
        font        = dict(size=13, color="#A8B3CF", family="Inter, system-ui, sans-serif"),
        traceorder  = "reversed",
        bgcolor     = "rgba(13,21,38,0.6)",
        bordercolor = "rgba(255,255,255,0.06)",
        borderwidth = 1,
    ),
    hoverlabel = dict(
        bgcolor    = "#141F35",
        bordercolor= "rgba(255,255,255,0.08)",
        font       = dict(size=13, color="#E6EDF6", family="Inter, system-ui, sans-serif"),
    ),
)

def _hex_to_rgba(hex_color, alpha=0.7):
    """Convert a #RRGGBB hex colour to an rgba() CSS string."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def make_stacked_area(series_list):
    fig = go.Figure()
    period_totals = pd.Series(0.0, index=all_periods)
    for s in series_list:
        period_totals += s["data"].reindex(all_periods).fillna(0) / 1000

    # ── Balance area traces (left Y axis) ─────────────────────────────────
    for s in series_list:
        vals_bn    = s["data"].reindex(all_periods).fillna(0) / 1000
        pct_series = (vals_bn / period_totals.replace(0, np.nan) * 100).fillna(0)
        customdata = pct_series.values.reshape(-1, 1)
        fig.add_trace(go.Scatter(
            x             = all_periods,
            y             = vals_bn,
            name          = f"{s['name']} (balance)",
            legendgroup   = s["name"],
            mode          = "lines",
            stackgroup    = "one",
            fillcolor     = s["color"],
            line          = dict(color="rgba(255,255,255,0.18)", width=1),
            customdata    = customdata,
            hovertemplate = (
                "$%{y:,.2f}B · %{customdata[0]:.1f}%"
                "<extra>" + s["name"] + "</extra>"
            ),
        ))

    # ── Share % line traces (right Y axis) ────────────────────────────────
    for s in series_list:
        vals_bn    = s["data"].reindex(all_periods).fillna(0) / 1000
        pct_series = (vals_bn / period_totals.replace(0, np.nan) * 100).fillna(0)
        fig.add_trace(go.Scatter(
            x           = all_periods,
            y           = pct_series,
            name        = f"{s['name']} (share%)",
            legendgroup = s["name"],
            mode        = "lines",
            yaxis       = "y2",
            line        = dict(
                color = _hex_to_rgba(s["color"], alpha=0.75),
                width = 1.5,
                dash  = "dot",
            ),
            opacity     = 0.7,
            hoverinfo   = "skip",
        ))

    # Build layout locally so we can add yaxis2 without mutating CHART_LAYOUT
    layout = dict(**CHART_LAYOUT)
    layout["yaxis2"] = dict(
        overlaying = "y",
        side       = "right",
        range      = [0, 100],
        ticksuffix = "%",
        showgrid   = False,
        zeroline   = False,
        tickfont   = dict(color="#6C7A99", size=13),
        title      = dict(text="Market share", font=dict(color="#6C7A99", size=13)),
    )
    # Widen right margin to give room for Y2 tick labels alongside the legend
    layout["margin"] = dict(**CHART_LAYOUT["margin"], r=220)
    fig.update_layout(**layout)
    return fig

# ── Build series ───────────────────────────────────────────────────────────────
if chart_mode == "Big 5 vs Non–Big 5":
    b5_by_period     = df[df["big5_flag"]].groupby("period")[value_col].sum()
    sys_by_period    = df.groupby("period")[system_col].max()
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
         "color": adj_color(BIG5_CONFIG[a]["brand_color"]),
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
            color_map[name] = adj_color(BIG5_CONFIG[abn]["brand_color"])
        else:
            color_map[name] = PALETTE[p_idx % len(PALETTE)]
            p_idx += 1
    series = [{"name": n, "color": color_map[n], "data": pivot[n]} for n in ordered]
    if other_names:
        other_cols = [n for n in other_names if n in pivot.columns]
        other_data = pivot[other_cols].sum(axis=1) if other_cols else pd.Series(0, index=all_periods)
        series.insert(0, {"name": f"Other ({len(other_names)} institutions)",
                          "color": OTHER_COLOR, "data": other_data})

# ── Title + chart ──────────────────────────────────────────────────────────────
st.title("Australian Residential Lending ($FUM)")
st.caption(
    f"APRA monthly ADI statistics  ·  Residential lending  ·  "
    f"{df['period'].min().strftime('%b %Y')} – {latest.strftime('%b %Y')}"
)
st.plotly_chart(make_stacked_area(series), use_container_width=True)

# ── Compute metrics ────────────────────────────────────────────────────────────
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

# ── Format helpers ─────────────────────────────────────────────────────────────
def fbn(v):       return f"${v:,.1f}B"  if v is not None else "—"
def fpct(v):      return f"{v:.2f}%"    if v is not None else "—"
def fsign_pct(v): return f"{v:+.2f}%"  if v is not None else None

# ── MARKET SIZE ────────────────────────────────────────────────────────────────
section_head("Market Size")

lat_str = latest.strftime('%b %Y')

c1_delta, c1_pos = None, None
if mom_delta_bn is not None and mom_pct is not None:
    c1_delta = f"{mom_delta_bn:+,.1f}B ({mom_pct:+.2f}%) MoM"
    c1_pos   = mom_delta_bn > 0

c2_delta, c2_pos = None, None
if b5_mom_delta_bn is not None and b5_mom_pct is not None:
    c2_delta = f"{b5_mom_delta_bn:+,.1f}B ({b5_mom_pct:+.2f}%) MoM"
    c2_pos   = b5_mom_delta_bn > 0

c3_delta, c3_pos = None, None
share_parts = []
if b5_shr_pp_mom is not None: share_parts.append(f"{b5_shr_pp_mom:+.2f}pp MoM")
if b5_shr_pp_yoy is not None: share_parts.append(f"{b5_shr_pp_yoy:+.2f}pp YoY")
if share_parts:
    c3_delta = "  ·  ".join(share_parts)
    c3_pos   = (b5_shr_pp_mom > 0) if b5_shr_pp_mom is not None else None

st.markdown(
    f'<div style="{_SR}">'
    + mcard("Total Residential Loans", f"All ADIs · as at {lat_str}",
            fbn(sys_lat / 1000), c1_delta, c1_pos)
    + mcard("Big 5 Residential Lending", f"as at {lat_str}",
            fbn(b5_lat / 1000), c2_delta, c2_pos)
    + mcard("Big 5 Market Share", f"as at {lat_str}",
            fpct(b5_shr_lat * 100) if b5_shr_lat else "—",
            c3_delta, c3_pos)
    + '</div>',
    unsafe_allow_html=True,
)

# ── GROWTH ─────────────────────────────────────────────────────────────────────
section_head("Growth")

prev_str      = prev_period.strftime('%b %Y') if prev_period else ""
yoy_str       = yoy_period.strftime('%b %Y')
inception_str = inception_period.strftime('%b %Y')

st.markdown(
    f'<div style="{_SR}">'
    + mcard("Change vs Prior Month", f"{prev_str} → {lat_str}",
            fbn(mom_delta_bn),
            fsign_pct(mom_pct),
            (mom_pct > 0) if mom_pct is not None else None)
    + mcard("Year-on-Year Change", f"{yoy_str} → {lat_str}",
            fbn(yoy_delta_bn),
            fsign_pct(yoy_pct),
            (yoy_pct > 0) if yoy_pct is not None else None)
    + mcard("Average Annual Growth", f"{inception_str} → {lat_str}",
            fpct(avg_annual_growth) if avg_annual_growth else "—",
            None, None,
            "Compound annual growth rate from inception")
    + '</div>',
    unsafe_allow_html=True,
)

# ── Insights ───────────────────────────────────────────────────────────────────
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

# Pad to full rows of 3 for even grid
while len(bullets) % 3 != 0:
    bullets.append("")

cards_html = ""
for b in bullets:
    if b:
        cards_html += (
            f'<div style="{_IC}">'
            f'<span style="{_II}">▸</span>'
            f'<span>{bold(b)}</span>'
            f'</div>'
        )
    else:
        cards_html += f'<div style="{_IC}opacity:0;pointer-events:none;"></div>'

st.markdown(f'<div style="{_IG}">{cards_html}</div>', unsafe_allow_html=True)

st.caption(
    "Source: APRA Monthly ADI Statistics  ·  Values in $billions  ·  "
    "Big 5: CBA · Westpac · NAB · ANZ · Macquarie"
)

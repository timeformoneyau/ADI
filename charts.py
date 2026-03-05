from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import pandas as pd
import plotly.graph_objects as go


# -----------------------------
# Core styling tokens (align with your Streamlit theme + ui_style.py)
# -----------------------------
SERIES_PALETTE = [
    "#60A5FA",  # blue
    "#34D399",  # green
    "#FBBF24",  # amber
    "#F472B6",  # pink
    "#A78BFA",  # purple
    "#FB7185",  # rose
    "#22D3EE",  # cyan
    "#F97316",  # orange
]

PANEL = "#111A2E"
GRID = "rgba(255,255,255,0.08)"
TEXT = "#E5E7EB"
MUTED = "rgba(229,231,235,0.72)"


@dataclass(frozen=True)
class ChartDefaults:
    height: int = 420
    line_width: int = 2
    axis_title_size: int = 12
    axis_tick_size: int = 11
    legend_size: int = 11
    hover_decimal_places: int = 2


DEFAULTS = ChartDefaults()


def _base_layout(title: Optional[str] = None, height: Optional[int] = None) -> dict:
    return dict(
        title=dict(text=title or "", font=dict(size=14, color=TEXT), x=0.0, xanchor="left"),
        height=height or DEFAULTS.height,
        margin=dict(l=14, r=14, t=36, b=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT),
        hoverlabel=dict(bgcolor=PANEL, font=dict(color=TEXT)),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=DEFAULTS.legend_size, color=MUTED),
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor=GRID,
            zeroline=False,
            tickfont=dict(size=DEFAULTS.axis_tick_size, color=MUTED),
            titlefont=dict(size=DEFAULTS.axis_title_size, color=MUTED),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=GRID,
            zeroline=False,
            tickfont=dict(size=DEFAULTS.axis_tick_size, color=MUTED),
            titlefont=dict(size=DEFAULTS.axis_title_size, color=MUTED),
        ),
    )


def _ensure_datetime(df: pd.DataFrame, col: str) -> pd.DataFrame:
    out = df.copy()
    if col in out.columns and not pd.api.types.is_datetime64_any_dtype(out[col]):
        out[col] = pd.to_datetime(out[col], errors="coerce")
    return out


def line_timeseries(
    df: pd.DataFrame,
    x: str,
    ys: Iterable[str],
    labels: Optional[dict[str, str]] = None,
    yaxis_title: Optional[str] = None,
    title: Optional[str] = None,
    height: Optional[int] = None,
    y_tickformat: Optional[str] = None,
) -> go.Figure:
    """
    Standard multi-series line chart.

    Args:
      df: DataFrame with x and y columns
      x: x-axis column name (typically a date)
      ys: iterable of y series column names
      labels: mapping of column -> display name
      yaxis_title: y-axis label
      title: chart title (optional)
      height: chart height override
      y_tickformat: Plotly tickformat (e.g. ",.0f", ".1%")
    """
    labels = labels or {}
    dfx = _ensure_datetime(df, x)

    fig = go.Figure()
    for idx, y in enumerate(ys):
        if y not in dfx.columns:
            continue
        color = SERIES_PALETTE[idx % len(SERIES_PALETTE)]
        fig.add_trace(
            go.Scatter(
                x=dfx[x],
                y=dfx[y],
                mode="lines",
                name=labels.get(y, y),
                line=dict(width=DEFAULTS.line_width, color=color),
                hovertemplate=(
                    "<b>%{fullData.name}</b><br>"
                    + "%{x|%b %Y}<br>"
                    + "%{y}<extra></extra>"
                ),
            )
        )

    layout = _base_layout(title=title, height=height)
    if yaxis_title:
        layout["yaxis"]["title"] = dict(text=yaxis_title)
    if y_tickformat:
        layout["yaxis"]["tickformat"] = y_tickformat

    fig.update_layout(**layout)

    # Improve hover vertical line + unified hover
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(showspikes=True, spikecolor=GRID, spikethickness=1, spikedash="solid")
    fig.update_yaxes(showspikes=False)

    return fig


def area_timeseries(
    df: pd.DataFrame,
    x: str,
    y: str,
    label: Optional[str] = None,
    yaxis_title: Optional[str] = None,
    title: Optional[str] = None,
    height: Optional[int] = None,
    y_tickformat: Optional[str] = None,
) -> go.Figure:
    """
    Single-series area chart for clean macro trend presentation.
    """
    dfx = _ensure_datetime(df, x)

    color = SERIES_PALETTE[0]
    fig = go.Figure(
        go.Scatter(
            x=dfx[x],
            y=dfx[y],
            mode="lines",
            name=label or y,
            line=dict(width=DEFAULTS.line_width, color=color),
            fill="tozeroy",
            fillcolor="rgba(96,165,250,0.18)",
            hovertemplate=(
                "<b>%{fullData.name}</b><br>"
                + "%{x|%b %Y}<br>"
                + "%{y}<extra></extra>"
            ),
        )
    )

    layout = _base_layout(title=title, height=height)
    if yaxis_title:
        layout["yaxis"]["title"] = dict(text=yaxis_title)
    if y_tickformat:
        layout["yaxis"]["tickformat"] = y_tickformat

    fig.update_layout(**layout)
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(showspikes=True, spikecolor=GRID, spikethickness=1, spikedash="solid")
    fig.update_yaxes(showspikes=False)

    return fig


def stacked_area_timeseries(
    df: pd.DataFrame,
    x: str,
    ys: Iterable[str],
    labels: Optional[dict[str, str]] = None,
    yaxis_title: Optional[str] = None,
    title: Optional[str] = None,
    height: Optional[int] = None,
    y_tickformat: Optional[str] = None,
    normalize_to_percent: bool = False,
) -> go.Figure:
    """
    Stacked area chart. Optional normalization to percent (0–100) for composition views.
    """
    labels = labels or {}
    dfx = _ensure_datetime(df, x)

    plot_df = dfx[[x] + [c for c in ys if c in dfx.columns]].copy()

    if normalize_to_percent:
        value_cols = [c for c in ys if c in plot_df.columns]
        row_sum = plot_df[value_cols].sum(axis=1)
        for c in value_cols:
            plot_df[c] = (plot_df[c] / row_sum) * 100

    fig = go.Figure()
    for idx, y in enumerate([c for c in ys if c in plot_df.columns]):
        color = SERIES_PALETTE[idx % len(SERIES_PALETTE)]
        fig.add_trace(
            go.Scatter(
                x=plot_df[x],
                y=plot_df[y],
                mode="lines",
                name=labels.get(y, y),
                line=dict(width=1, color=color),
                stackgroup="one",
                hovertemplate=(
                    "<b>%{fullData.name}</b><br>"
                    + "%{x|%b %Y}<br>"
                    + ("%{y:.1f}%" if normalize_to_percent else "%{y}")
                    + "<extra></extra>"
                ),
            )
        )

    layout = _base_layout(title=title, height=height)
    if yaxis_title:
        layout["yaxis"]["title"] = dict(text=yaxis_title)
    if y_tickformat and not normalize_to_percent:
        layout["yaxis"]["tickformat"] = y_tickformat
    if normalize_to_percent:
        layout["yaxis"]["range"] = [0, 100]
        layout["yaxis"]["ticksuffix"] = "%"

    fig.update_layout(**layout)
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(showspikes=True, spikecolor=GRID, spikethickness=1, spikedash="solid")
    fig.update_yaxes(showspikes=False)

    return fig


def format_table(
    df: pd.DataFrame,
    money_cols: Optional[list[str]] = None,
    percent_cols: Optional[list[str]] = None,
    int_cols: Optional[list[str]] = None,
    date_cols: Optional[list[str]] = None,
) -> pd.DataFrame:
    """
    Utility to consistently format tables for display in Streamlit (st.dataframe / st.table).

    This returns a new DataFrame with formatted string values (so sorting will be lexical).
    If you want sortable numeric tables, skip this and use st.dataframe with column_config.
    """
    out = df.copy()

    money_cols = money_cols or []
    percent_cols = percent_cols or []
    int_cols = int_cols or []
    date_cols = date_cols or []

    for c in date_cols:
        if c in out.columns:
            out[c] = pd.to_datetime(out[c], errors="coerce").dt.strftime("%d %b %Y")

    for c in int_cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").map(lambda v: "" if pd.isna(v) else f"{int(v):,}")

    for c in money_cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").map(
                lambda v: "" if pd.isna(v) else f"${v:,.0f}"
            )

    for c in percent_cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").map(
                lambda v: "" if pd.isna(v) else f"{v*100:.1f}%"
            )

    return out
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

import streamlit as st


@dataclass(frozen=True)
class UiTokens:
    # Keep these aligned with .streamlit/config.toml so everything “clicks”
    primary: str = "#2563EB"
    bg: str = "#0B1220"
    panel: str = "#111A2E"
    panel_2: str = "#0F172A"
    border: str = "rgba(255,255,255,0.08)"
    text: str = "#E5E7EB"
    muted: str = "rgba(229,231,235,0.72)"
    subtle: str = "rgba(229,231,235,0.55)"
    success: str = "#22C55E"
    warning: str = "#F59E0B"
    danger: str = "#EF4444"


TOKENS = UiTokens()


def apply_global_css() -> None:
    """
    Call this once near the top of your app/page.
    It standardizes spacing, typography, and gives you reusable “card” containers.
    """
    st.markdown(
        f"""
<style>
/* Page width & padding */
.block-container {{
  max-width: 1200px;
  padding-top: 1.25rem;
  padding-bottom: 2.0rem;
}}

/* Typography tweaks */
h1, h2, h3, h4 {{
  letter-spacing: -0.02em;
}}
.small-muted {{
  color: {TOKENS.muted};
  font-size: 0.9rem;
}}
.tiny-muted {{
  color: {TOKENS.subtle};
  font-size: 0.8rem;
}}
.hr {{
  border-top: 1px solid {TOKENS.border};
  margin: 0.75rem 0 1rem 0;
}}

/* Card */
.adi-card {{
  background: linear-gradient(180deg, {TOKENS.panel} 0%, {TOKENS.panel_2} 100%);
  border: 1px solid {TOKENS.border};
  border-radius: 14px;
  padding: 14px 16px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.25);
}}
.adi-card-title {{
  font-size: 1.0rem;
  font-weight: 650;
  margin-bottom: 0.25rem;
}}
.adi-card-help {{
  color: {TOKENS.muted};
  font-size: 0.85rem;
  margin-bottom: 0.75rem;
}}

/* Section header */
.adi-section-title {{
  font-size: 1.05rem;
  font-weight: 650;
  margin-top: 0.25rem;
  margin-bottom: 0.15rem;
}}
.adi-section-desc {{
  color: {TOKENS.muted};
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
}}

/* Control bar */
.adi-toolbar {{
  background: rgba(255,255,255,0.03);
  border: 1px solid {TOKENS.border};
  border-radius: 12px;
  padding: 10px 12px;
}}

/* Make Streamlit widgets align nicer inside toolbars/cards */
div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stHorizontalBlock"]) {{
  gap: 0.6rem;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str, updated_on: Optional[datetime] = None) -> None:
    updated = updated_on or datetime.now()
    st.title(title)
    cols = st.columns([0.78, 0.22], vertical_alignment="bottom")
    with cols[0]:
        st.markdown(f'<div class="small-muted">{subtitle}</div>', unsafe_allow_html=True)
    with cols[1]:
        st.markdown(
            f'<div class="tiny-muted" style="text-align:right;">Updated {updated:%d %b %Y}</div>',
            unsafe_allow_html=True,
        )
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)


def section(title: str, description: Optional[str] = None) -> None:
    st.markdown(f'<div class="adi-section-title">{title}</div>', unsafe_allow_html=True)
    if description:
        st.markdown(f'<div class="adi-section-desc">{description}</div>', unsafe_allow_html=True)


@contextmanager
def card(title: Optional[str] = None, help_text: Optional[str] = None):
    """
    Usage:
        with card("Chart title", "Optional help"):
            st.plotly_chart(...)
    """
    st.markdown('<div class="adi-card">', unsafe_allow_html=True)
    if title:
        st.markdown(f'<div class="adi-card-title">{title}</div>', unsafe_allow_html=True)
    if help_text:
        st.markdown(f'<div class="adi-card-help">{help_text}</div>', unsafe_allow_html=True)
    try:
        yield
    finally:
        st.markdown("</div>", unsafe_allow_html=True)


@contextmanager
def toolbar():
    """
    Usage:
        with toolbar():
            c1, c2, c3 = st.columns([0.35, 0.35, 0.30])
            ...
    """
    st.markdown('<div class="adi-toolbar">', unsafe_allow_html=True)
    try:
        yield
    finally:
        st.markdown("</div>", unsafe_allow_html=True)


def kpi_strip(items: list[tuple[str, str, Optional[str]]]) -> None:
    """
    items: list of (label, value, delta)
    """
    cols = st.columns(len(items))
    for col, (label, value, delta) in zip(cols, items):
        with col:
            st.metric(label=label, value=value, delta=delta)
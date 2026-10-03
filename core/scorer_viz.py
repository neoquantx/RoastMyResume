"""Consistent, self-contained Plotly score cards for resume analysis.

Numeric strings are accepted, but missing, non-finite and out-of-range scores
are unavailable, never silently replaced with an average or clamped score.
"""

from collections.abc import Mapping
from html import escape
from math import isfinite
from textwrap import wrap

import plotly.graph_objects as go


CANVAS = "#F7F8F2"
PANEL = "#FFFFFF"
INK = "#242A20"
MUTED = "#71776B"
BORDER = "#E0E4D9"
ACCENT = "#5F7144"
TINT = "#EDF1E6"
FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, SF Pro Display, Avenir Next, "
    "Segoe UI, Helvetica Neue, Arial, sans-serif"
)

RISK_COLORS = {
    "low": ACCENT,
    "medium": "#9B712D",
    "high": "#B35C45",
    "critical": "#8B1A1A",
}
RISK_LABELS = {
    "low": "Low risk",
    "medium": "Moderate risk",
    "high": "High risk",
    "critical": "Critical risk",
}
# Retain the legacy symbol for callers, but use plain-language labels.
RISK_EMOJI = RISK_LABELS.copy()


def _number(value, maximum=None):
    """Return a finite nonnegative number, or None for unavailable data."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not isfinite(number) or number < 0:
        return None
    if maximum is not None and number > maximum:
        return None
    return number


def _key(value):
    return value.strip().lower() if isinstance(value, str) else ""


def _short_label(label):
    """Wrap compact axis labels; full escaped names remain in hover text."""
    return "<br>".join(
        escape(line) for line in wrap(label, width=12, max_lines=2, placeholder="...")
    )


def _section_rows(sections):
    if not isinstance(sections, Mapping):
        return []
    rows = []
    for name, data in sections.items():
        label = str(name).replace("_", " ").strip().title() or "Untitled section"
        data = data if isinstance(data, Mapping) else {}
        rows.append((label, _number(data.get("score"), 100), _key(data.get("risk"))))
    return rows


def _figure(title, height=280):
    fig = go.Figure()
    fig.update_layout(
        template="none",
        autosize=True,
        height=height,
        title=dict(text=title, x=0.04, xanchor="left", font=dict(size=16, color=INK)),
        font=dict(family=FONT_STACK, size=12, color=INK),
        paper_bgcolor=PANEL,
        plot_bgcolor=CANVAS,
        colorway=[ACCENT],
        margin=dict(t=54, b=42, l=24, r=24),
        showlegend=False,
        hoverlabel=dict(bgcolor=PANEL, bordercolor=BORDER, font=dict(family=FONT_STACK, color=INK)),
    )
    return fig


def _empty(fig, message):
    fig.update_xaxes(visible=False, fixedrange=True)
    fig.update_yaxes(visible=False, fixedrange=True)
    fig.add_annotation(
        text=message, x=0.5, y=0.5, xref="paper", yref="paper",
        showarrow=False, align="center", font=dict(size=13, color=MUTED),
    )
    return fig


def build_rejection_risk_gauge(risk_score: int) -> go.Figure:
    """Show an estimated rejection risk index from 0 to 100 (lower is better)."""
    score = _number(risk_score, 100)
    fig = _figure("", height=260)
    fig.update_layout(margin=dict(t=20, b=30, l=20, r=20))
    if score is None:
        return _empty(fig, "Score unavailable<br>A score from 0 to 100 is needed.")

    if score >= 80:
        risk = "critical"
    elif score >= 60:
        risk = "high"
    elif score >= 30:
        risk = "medium"
    else:
        risk = "low"

    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=score,
        number=dict(suffix=" /100", font=dict(family=FONT_STACK, size=32, color=INK)),
        domain=dict(x=[0.08, 0.92], y=[0.15, 0.95]),
        gauge=dict(
            axis=dict(range=[0, 100], tickvals=[0, 50, 100], tickcolor=BORDER,
                      tickfont=dict(size=12, color=MUTED, family=FONT_STACK)),
            bar=dict(color=RISK_COLORS[risk], thickness=0.36),
            bgcolor=CANVAS,
            borderwidth=1,
            bordercolor=BORDER,
            steps=[dict(range=[0, 100], color=TINT)],
        ),
    ))
    fig.add_annotation(
        text=f"<span style='color:{RISK_COLORS[risk]};font-weight:600;'>{RISK_LABELS[risk]}</span> · not a probability",
        x=0.5, y=-0.04, xref="paper", yref="paper",
        showarrow=False,
        font=dict(size=12, color=MUTED, family=FONT_STACK),
    )
    return fig


def build_resume_score_gauge(score: int) -> go.Figure:
    """Show an overall resume score out of 100 (higher is better) with guaranteed centered placement."""
    val = _number(score, 100)
    fig = _figure("", height=260)
    fig.update_layout(margin=dict(t=20, b=30, l=20, r=20))
    if val is None:
        return _empty(fig, "Score unavailable<br>A score from 0 to 100 is needed.")

    # Higher is better
    rating = "excellent" if val >= 85 else "good" if val >= 70 else "fair" if val >= 50 else "poor"

    RATING_COLORS = {
        "excellent": ACCENT,
        "good": "#9B712D",
        "fair": "#B35C45",
        "poor": "#B35C45",
    }
    RATING_LABELS = {
        "excellent": "Strong match",
        "good": "Good potential",
        "fair": "Needs improvement",
        "poor": "Weak match",
    }

    color = RATING_COLORS[rating]
    fig.add_trace(go.Indicator(
        mode="gauge",
        value=val,
        domain=dict(x=[0.08, 0.92], y=[0.15, 0.95]),
        gauge=dict(
            axis=dict(range=[0, 100], tickvals=[0, 50, 100], tickcolor=BORDER,
                      tickfont=dict(size=12, color=MUTED, family=FONT_STACK)),
            bar=dict(color=color, thickness=0.36),
            bgcolor=CANVAS,
            borderwidth=1,
            bordercolor=BORDER,
            steps=[dict(range=[0, 100], color=TINT)],
        ),
    ))
    # Centered score number - guaranteed exact placement, no Plotly auto-displacement glitches
    fig.add_annotation(
        text=f"<b>{int(round(val))}</b>",
        x=0.5, y=0.30, xref="paper", yref="paper",
        showarrow=False,
        font=dict(size=44, color=INK, family=FONT_STACK),
    )
    fig.add_annotation(
        text=f"<span style='color:{color};font-weight:600;'>{RATING_LABELS[rating]}</span> · Higher is better",
        x=0.5, y=-0.04, xref="paper", yref="paper",
        showarrow=False,
        font=dict(size=12, color=MUTED, family=FONT_STACK),
    )
    return fig


def build_section_radar(sections: dict) -> go.Figure:
    """Plot supplied section strength scores; gaps are never invented scores."""
    rows = _section_rows(sections)
    fig = _figure("Section strengths", height=350)
    if not any(score is not None for _, score, _ in rows):
        return _empty(fig, "Section scores unavailable<br>Analyze a resume to see its strengths.")

    # Stable IDs keep wrapped/truncated labels from merging distinct sections.
    categories = [f"section_{index}" for index in range(len(rows))]
    theta = categories.copy()
    scores = [score for _, score, _ in rows]
    names = [escape(name) for name, _, _ in rows]
    complete = all(score is not None for score in scores)
    polygon = len(rows) >= 3
    if polygon:
        theta.append(theta[0])
        scores.append(scores[0])
        names.append(names[0])

    fig.add_trace(go.Scatterpolar(
        r=scores, theta=theta, customdata=names,
        mode="lines+markers" if polygon else "markers",
        connectgaps=False,
        fill="toself" if complete and polygon else "none",
        fillcolor="rgba(95, 113, 68, 0.12)",
        line=dict(color=ACCENT, width=2),
        marker=dict(color=ACCENT, size=7, line=dict(color=PANEL, width=1)),
        name="Section strength",
        hovertemplate="<b>%{customdata}</b><br>Strength: %{r:g}/100<extra></extra>",
    ))
    fig.update_layout(
        margin=dict(t=60, b=64, l=68, r=68),
        polar=dict(
            bgcolor=CANVAS,
            radialaxis=dict(range=[0, 100], tickvals=[25, 50, 75, 100],
                            tickfont=dict(size=10, color=MUTED),
                            gridcolor=BORDER, linecolor=BORDER, angle=90),
            angularaxis=dict(
                tickmode="array", tickvals=categories,
                ticktext=[_short_label(name) + ("<br>N/A" if score is None else "")
                          for name, score, _ in rows],
                categoryorder="array", categoryarray=categories,
                tickfont=dict(size=11, color=INK), gridcolor=BORDER, linecolor=BORDER,
                rotation=90, direction="clockwise",
            ),
        ),
    )
    fig.add_annotation(
        text="Strength /100 · Higher is better" + ("<br>N/A = score unavailable" if not complete else ""),
        x=0.5, y=-0.22, xref="paper", yref="paper", showarrow=False,
        font=dict(size=11, color=MUTED),
    )
    return fig


def build_section_bar(sections: dict) -> go.Figure:
    """Compare section strength, with restrained colors for reported risk."""
    rows = _section_rows(sections)
    fig = _figure("Section scores", height=max(280, 52 * len(rows) + 110))
    if not rows:
        return _empty(fig, "Section scores unavailable<br>No sections have been provided.")

    positions = list(range(len(rows)))
    fig.add_trace(go.Bar(
        x=[score for _, score, _ in rows], y=positions, orientation="h", width=0.45,
        marker=dict(color=[RISK_COLORS.get(risk, MUTED) for _, _, risk in rows],
                    line=dict(color=BORDER, width=1)),
        customdata=[[escape(name), RISK_LABELS.get(risk, "Risk unavailable")]
                    for name, _, risk in rows],
        hovertemplate="<b>%{customdata[0]}</b><br>Strength: %{x:g}/100<br>%{customdata[1]}<extra></extra>",
    ))
    # Paper-anchored values remain legible at both 0 and 100, without clipping
    # or widening the score scale beyond 100. Missing scores have no bar.
    for index, (_, score, _) in enumerate(rows):
        fig.add_annotation(
            text=f"{score:g}/100" if score is not None else "N/A",
            x=1.03, xref="paper", xanchor="left", y=index, yref="y",
            showarrow=False, font=dict(size=11, color=INK if score is not None else MUTED),
        )
    fig.update_layout(
        margin=dict(t=54, b=52, l=8, r=70),
        xaxis=dict(range=[0, 100], tickvals=[0, 50, 100], fixedrange=True,
                   tickfont=dict(size=11, color=MUTED), gridcolor=BORDER,
                   zeroline=False, title=dict(text="Strength /100 · Higher is better", font=dict(size=11))),
        yaxis=dict(range=[len(rows) - 0.5, -0.5], fixedrange=True, tickmode="array",
                   tickvals=positions, ticktext=[_short_label(name) for name, _, _ in rows],
                   tickfont=dict(size=11, color=INK), automargin=True,
                   showgrid=False, zeroline=False),
    )
    if any(score is None for _, score, _ in rows):
        fig.add_annotation(
            text="N/A = score unavailable", x=0, y=1.08, xref="paper", yref="paper",
            xanchor="left", showarrow=False, font=dict(size=11, color=MUTED),
        )
    return fig


def build_keyword_match_donut(match_percent: int) -> go.Figure:
    """Show keyword coverage against the role, not overall candidate fit."""
    match = _number(match_percent, 100)
    fig = _figure("Role keyword match")
    if match is None:
        return _empty(fig, "Role keyword match unavailable<br>A valid keyword comparison is needed.")

    fig.add_trace(go.Pie(
        values=[match, 100 - match], labels=["Matched", "Not matched"],
        hole=0.74, sort=False, direction="clockwise",
        marker=dict(colors=[ACCENT, TINT], line=dict(color=PANEL, width=1)),
        textinfo="none",
        hovertemplate="<b>%{label}</b><br>%{value:g}% of role keywords<extra></extra>",
    ))
    fig.add_annotation(
        text=f"<b>{match:g}%</b><br><span style='font-size:11px'>Role keywords</span>",
        x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False,
        font=dict(size=22, color=INK),
    )
    fig.update_layout(
        margin=dict(t=54, b=52, l=24, r=24), showlegend=True,
        legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.08, yanchor="top",
                    font=dict(size=11, color=MUTED), bgcolor=PANEL,
                    itemclick=False, itemdoubleclick=False),
    )
    return fig


def build_attention_timer_text(seconds: int) -> str:
    """Describe the model's attention estimate, not an observed recruiter action."""
    seconds = _number(seconds)
    if seconds is None:
        return "Estimated attention unavailable."
    if seconds <= 3:
        detail = "Lead with your strongest evidence."
    elif seconds <= 6:
        detail = "Make key strengths easy to find in a brief scan."
    elif seconds <= 10:
        detail = "Promising first impression; keep the evidence specific."
    elif seconds <= 20:
        detail = "Clear strengths support a closer review."
    else:
        detail = "Strong evidence supports sustained interest."
    return f"Estimated attention: **{seconds:g}s** — {detail}"


def get_verdict_color_and_emoji(verdict: str) -> tuple:
    """Return (plain-language label, color); preserve the legacy function name."""
    verdicts = {
        "complete_overhaul": ("Comprehensive revision needed", RISK_COLORS["high"]),
        "needs_work": ("Needs refinement", RISK_COLORS["medium"]),
        "junior_ready": ("Ready for junior roles", ACCENT),
        "strong_candidate": ("Strong candidate", ACCENT),
    }
    return verdicts.get(_key(verdict), ("Assessment unavailable", MUTED))

"""Privacy-aware Plotly charts and summaries for uploaded tabular data."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .tools import is_sensitive_column

from .i18n import tr

COLORS = {"blue": "#2997ff", "teal": "#0071e3", "red": "#dc2626", "muted": "#64748b"}


def empty_figure(message: str, title: str = "") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, x=0.5, y=0.5, xref="paper", yref="paper",
                       showarrow=False, font={"size": 14, "color": COLORS["muted"]})
    fig.update_layout(title=title, height=330, xaxis={"visible": False}, yaxis={"visible": False},
                      margin={"l": 24, "r": 24, "t": 52, "b": 24})
    return _polish(fig)


def overview_markdown(frame: pd.DataFrame) -> str:
    rows, columns = frame.shape
    missing = int(frame.isna().sum().sum())
    duplicate_rows = int(frame.duplicated().sum())
    return ("### " + tr("数据概况") + "\n"
            + tr("**{rows} 行** · **{cols} 列** · **{missing} 个缺失单元格** · **{dups} 行完全重复记录**",
                 rows=f"{rows:,}", cols=f"{columns:,}", missing=f"{missing:,}", dups=f"{duplicate_rows:,}"))


def missingness_figure(frame: pd.DataFrame) -> go.Figure:
    counts = frame.isna().sum().sort_values(ascending=True)
    counts = counts[counts > 0].tail(8)
    if counts.empty:
        return empty_figure(tr("未发现缺失值"), tr("各字段缺失值数量"))
    ratios = counts / max(len(frame), 1) * 100
    fig = go.Figure(go.Bar(
        x=counts.values, y=[str(c) for c in counts.index], orientation="h",
        marker_color=COLORS["blue"], width=.42, text=counts.values, textposition="outside", cliponaxis=False,
        customdata=ratios.values,
        hovertemplate=tr("字段") + ": %{y}<br>" + tr("缺失") + ": %{x}<br>" + tr("占比") + ": %{customdata:.1f}%<extra></extra>",
    ))
    if len(counts) <= 2:
        fig.update_yaxes(range=[-1, len(counts)])
    fig.update_xaxes(tickformat=",d", dtick=1 if counts.max() <= 10 else None, range=[0, float(counts.max()) * 1.25])
    fig.update_layout(title=tr("各字段缺失值数量（最多显示 20 个）"), xaxis_title=tr("缺失行数"),
                      yaxis_title=tr("字段"), height=max(330, 36 * len(counts) + 110),
                      margin={"l": 24, "r": 24, "t": 58, "b": 44},
                      template="plotly_white")
    return _polish(fig)


def distribution_columns(frame: pd.DataFrame) -> list[str]:
    """Offer numeric fields and low-cardinality categories, excluding sensitive names."""
    choices = []
    for column in frame.columns:
        if is_sensitive_column(column):
            continue
        series = frame[column]
        if pd.api.types.is_numeric_dtype(series) or series.nunique(dropna=True) <= 40:
            choices.append(str(column))
    choices.sort(key=lambda column: not pd.api.types.is_numeric_dtype(frame[column]))
    return choices


def distribution_figure(frame: pd.DataFrame, column: str | None) -> go.Figure:
    if not column or column not in frame.columns:
        return empty_figure(tr("请选择一个可视化字段"), tr("字段分布"))
    if is_sensitive_column(column):
        return empty_figure(tr("该字段按敏感字段规则隐藏，图表不展示其取值"), tr("字段分布"))

    series = frame[column]
    numeric = pd.to_numeric(series, errors="coerce")
    is_numeric = pd.api.types.is_numeric_dtype(series) or (
        series.notna().sum() > 0 and numeric.notna().sum() / series.notna().sum() >= 0.9
    )
    if is_numeric:
        values = numeric.dropna()
        if values.empty:
            return empty_figure(tr("该字段没有可绘制的数值"), tr("{col}：数值分布", col=column))
        fig = go.Figure(go.Histogram(x=values, nbinsx=min(20, max(5, int(len(values) ** .5))), marker_color=COLORS["teal"],
                                     hovertemplate=tr("区间") + ": %{x}<br>" + tr("记录数") + ": %{y}<extra></extra>"))
        if len(values) <= 30:
            fig.update_yaxes(dtick=1)
        fig.update_layout(title=tr("{col}：数值分布", col=column), xaxis_title=str(column), yaxis_title=tr("记录数"),
                          height=360, template="plotly_white",
                          margin={"l": 24, "r": 24, "t": 58, "b": 48})
        return _polish(fig)

    counts = series.astype("string").fillna(tr("（缺失）")).value_counts().head(15).sort_values()
    if counts.empty:
        return empty_figure(tr("该字段没有可绘制的类别"), tr("{col}：类别分布", col=column))
    fig = go.Figure(go.Bar(x=counts.values, y=counts.index.astype(str), orientation="h",
                           marker_color=COLORS["teal"],
                           hovertemplate=tr("类别") + ": %{y}<br>" + tr("记录数") + ": %{x}<extra></extra>"))
    fig.update_yaxes(type="category")
    fig.update_layout(title=tr("{col}：类别频数（前 15 项）", col=column), xaxis_title=tr("记录数"),
                      yaxis_title=tr("类别"), height=max(330, 32 * len(counts) + 110),
                      template="plotly_white", margin={"l": 24, "r": 24, "t": 58, "b": 44})
    return _polish(fig)


def _polish(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        title=None, height=290, bargap=.15, paper_bgcolor="white", plot_bgcolor="white",
        font={"family": "-apple-system, BlinkMacSystemFont, PingFang SC, sans-serif", "size": 11, "color": "#8b95a7"},
        margin={"l": 10, "r": 10, "t": 12, "b": 34},
        hoverlabel={"bgcolor": "white", "font_size": 12},
    )
    fig.update_xaxes(gridcolor="#f0f0f3", zeroline=False, title_font_size=10, tickfont_size=10)
    fig.update_yaxes(gridcolor="#f0f0f3", zeroline=False, title_font_size=10, tickfont_size=10, automargin=True)
    return fig

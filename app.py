"""
NYC Affordable Housing x Traffic Safety - multi-page dashboard (DEV Milestone 1)

Run locally:   .venv/bin/python app.py
Deploy:        gunicorn app:server
Data files:    data/building_exposure.csv, data/integrated_zip_year.csv
Styling:       assets/style.css (loaded automatically by Dash)

Navigation
  Top bar  = analysis pages   /  /housing  /safety  /equity   (use the filters)
  Sidebar  = project pages    /story  /data  /team  + download filtered CSV
"""
from pathlib import Path
from datetime import datetime
import re

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import Dash, html, dcc, Input, Output, State, no_update

DATA = Path(__file__).resolve().parent / "data"

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------
BOROUGHS = ["Bronx", "Brooklyn", "Manhattan", "Queens", "Staten Island"]
BORO_COLORS = {"Bronx": "#7c5cff", "Brooklyn": "#3fa7f5", "Manhattan": "#ff6f91",
               "Queens": "#2fbf8a", "Staten Island": "#f5a524"}

TRANSPORT = {
    "persons_injured": "All injuries",
    "pedestrians_injured": "Pedestrian injuries",
    "cyclists_injured": "Cyclist injuries",
    "motorists_injured": "Motorist injuries",
    "persons_killed": "Fatalities",
    "crashes": "Crashes",
}
BUILDING_METRIC = {"pedestrians_injured": "ped_injured_250m_per_year",
                   "crashes": "crashes_250m_per_year"}
BUILDING_LABEL = {
    "injured_250m_per_year": "Injured per year within 250 m",
    "ped_injured_250m_per_year": "Pedestrians injured per year within 250 m",
    "crashes_250m_per_year": "Crashes per year within 250 m",
}

DANGER_CANON = {"low": "Low", "medium": "Medium", "moderate": "Medium",
                "high": "High", "very high": "Very high"}
DANGER_ORDER = ["Low", "Medium", "High", "Very high"]
DANGER_COLORS = {"Low": "#2fbf8a", "Medium": "#f5c24c", "High": "#f08a4b",
                 "Very high": "#e0475b", "Unknown": "#c4c1d6"}
HIGH = {"High", "Very high"}
LI_GROUPS = ["None", "Up to 25%", "25–50%", "Over 50%"]
LI_COLORS = ["#cfc5ff", "#a48bff", "#7c5cff", "#4b2fc2"]
VICTIM_COLORS = {"Pedestrians": "#ff6f91", "Cyclists": "#f5a524", "Motorists": "#3fa7f5"}

FONT = "Inter, system-ui, -apple-system, sans-serif"
INK, MUTED, GRID = "#1d1b34", "#8a87a3", "#efedf7"
TEAM = ["Youssef Ahmed", "Hana Ahmed", "Mostafa Abuelabbas", "Ziad Moharam", "Hazem Ahmed"]


# ----------------------------------------------------------------------------
# Load + tidy data
# ----------------------------------------------------------------------------
def clean_zip(s):
    z = pd.to_numeric(s, errors="coerce")
    return z.map(lambda v: f"{int(v):05d}" if pd.notna(v) else None)


def clean_boro(s):
    return s.astype(str).str.strip().str.title().replace({"The Bronx": "Bronx"})


def to_bool(s):
    if s.dtype == bool:
        return s
    return s.astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y"])


zy = pd.read_csv(DATA / "integrated_zip_year.csv")
zy["zip_code"] = clean_zip(zy["zip_code"])
zy["borough"] = clean_boro(zy["borough"])
zy["year"] = pd.to_numeric(zy["year"], errors="coerce")
zy = zy.dropna(subset=["year", "zip_code"]).copy()
zy["year"] = zy["year"].astype(int)
for c in list(TRANSPORT) + ["affordable_units_completed"]:
    zy[c] = pd.to_numeric(zy[c], errors="coerce").fillna(0)
zy["is_special_zip"] = to_bool(zy["is_special_zip"]) if "is_special_zip" in zy else False

bd = pd.read_csv(DATA / "building_exposure.csv")
bd["zip_code"] = clean_zip(bd["zip_code"])
bd["borough"] = clean_boro(bd["borough"])
for c in ["completion_year", "all_counted_units", "total_units", "lowest_income_units",
          "crashes_250m_per_year", "injured_250m_per_year", "ped_injured_250m_per_year",
          "latitude", "longitude", "lowest_income_share"]:
    bd[c] = pd.to_numeric(bd[c], errors="coerce")
bd["all_counted_units"] = bd["all_counted_units"].fillna(0)
bd["reporting_construction_type"] = (bd["reporting_construction_type"]
                                     .fillna("Unknown").astype(str).str.strip())
bd["danger_level"] = (bd["danger_level"].fillna("Unknown").astype(str).str.strip()
                      .map(lambda v: DANGER_CANON.get(v.lower(), v)))
bd["is_duplicate_site"] = to_bool(bd["is_duplicate_site"])

share = bd["lowest_income_share"]
if share.max() > 1.5:                      # stored as 0-100 instead of 0-1
    share = share / 100
bd["li_group"] = pd.cut(share, bins=[-0.001, 0, 0.25, 0.5, 1.0001],
                        labels=LI_GROUPS).astype(str).replace("nan", np.nan)

present = set(bd["danger_level"].unique())
DANGER_LEVELS = [d for d in DANGER_ORDER if d in present] + sorted(present - set(DANGER_ORDER))

YEARS = sorted(zy["year"].unique().tolist())
HOUSING_TYPES = sorted(t for t in bd["reporting_construction_type"].unique() if t != "Unknown")
Y_MIN, Y_MAX = YEARS[0], YEARS[-1]

DEFAULT_REPORT = {"boro": "all", "year": "all", "housing": "all",
                  "metric": "persons_injured", "ts": None}


# ----------------------------------------------------------------------------
# Filtering helpers
# ----------------------------------------------------------------------------
def f_buildings(boro, year, housing, dedupe=False):
    d = bd
    if boro != "all":
        d = d[d["borough"] == boro]
    if year != "all":
        d = d[d["completion_year"] == int(year)]
    if housing != "all":
        d = d[d["reporting_construction_type"] == housing]
    if dedupe:
        d = d[~d["is_duplicate_site"]]
    return d


def f_zip(boro, year):
    d = zy
    if boro != "all":
        d = d[d["borough"] == boro]
    if year != "all":
        d = d[d["year"] == int(year)]
    return d


def fmt(n):
    n = float(n)
    if abs(n) >= 1e6:
        return f"{n / 1e6:.2f}M"
    if abs(n) >= 1e4:
        return f"{n / 1e3:.1f}k"
    return f"{n:,.0f}"


# ----------------------------------------------------------------------------
# Figure styling
# ----------------------------------------------------------------------------
def style(fig, h=340, legend=True):
    fig.update_layout(
        height=h, margin=dict(l=8, r=8, t=10, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color=INK, size=12),
        hoverlabel=dict(bgcolor="white", bordercolor="#e5e2f3",
                        font=dict(family=FONT, color=INK)),
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0,
                    title=None, font=dict(size=11)),
        showlegend=legend,
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=GRID,
                     tickfont=dict(color=MUTED), title_font=dict(color=MUTED, size=11))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID,
                     tickfont=dict(color=MUTED), title_font=dict(color=MUTED, size=11))
    return fig


def empty(h=340, msg="No data for this selection"):
    fig = style(go.Figure(), h, legend=False)
    fig.add_annotation(text=msg, showarrow=False, font=dict(color=MUTED, size=14))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


# ----------------------------------------------------------------------------
# Charts
# ----------------------------------------------------------------------------
def fig_trend(boro, year, housing, metric, h=340):
    """Bars = affordable units completed, line = selected transport measure, per year."""
    harm = f_zip(boro, "all").groupby("year")[metric].sum().reindex(YEARS, fill_value=0)
    b = f_buildings(boro, "all", housing).dropna(subset=["completion_year"])
    units = (b.groupby(b["completion_year"].astype(int))["all_counted_units"].sum()
             .reindex(YEARS, fill_value=0))
    if harm.sum() == 0 and units.sum() == 0:
        return empty(h)
    bar_colors = ["#7c5cff" if (year == "all" or y == int(year)) else "#dcd4ff" for y in YEARS]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=YEARS, y=units.values, name="Affordable units completed",
                marker_color=bar_colors, marker_line_width=0,
                hovertemplate="%{x}<br>%{y:,.0f} units<extra></extra>", secondary_y=False)
    fig.add_scatter(x=YEARS, y=harm.values, name=TRANSPORT[metric], mode="lines+markers",
                    line=dict(color="#ff6f91", width=3, shape="spline"),
                    marker=dict(size=7, color="#ff6f91", line=dict(width=2, color="white")),
                    hovertemplate="%{x}<br>%{y:,.0f} " + TRANSPORT[metric].lower() + "<extra></extra>",
                    secondary_y=True)
    style(fig, h)
    fig.update_layout(bargap=0.4)
    fig.update_xaxes(dtick=1, showgrid=False)
    fig.update_yaxes(title_text="Affordable units", secondary_y=False)
    fig.update_yaxes(title_text=TRANSPORT[metric], secondary_y=True, showgrid=False)
    return fig


def fig_map(boro, year, housing, h=480):
    d = f_buildings(boro, year, housing).dropna(subset=["latitude", "longitude"])
    d = d[d["latitude"].between(40.45, 40.95) & d["longitude"].between(-74.30, -73.65)]
    if d.empty:
        return empty(h)
    d = d.assign(size=d["all_counted_units"].clip(lower=1))
    kw = dict(
        lat="latitude", lon="longitude", color="danger_level", size="size", size_max=16,
        category_orders={"danger_level": DANGER_LEVELS},
        color_discrete_map=DANGER_COLORS, hover_name="project_name",
        hover_data={"zip_code": True, "all_counted_units": ":,.0f",
                    "injured_250m_per_year": ":.1f", "completion_year": ":.0f",
                    "latitude": False, "longitude": False, "size": False},
        labels={"danger_level": "Danger level", "zip_code": "ZIP",
                "all_counted_units": "Affordable units",
                "injured_250m_per_year": "Injured / yr within 250 m",
                "completion_year": "Completed"},
        center=dict(lat=d["latitude"].mean(), lon=d["longitude"].mean()),
        zoom=9.6 if boro == "all" else 10.6,
    )
    if hasattr(px, "scatter_map"):          # plotly >= 5.24
        fig = px.scatter_map(d, map_style="carto-positron", **kw)
    else:
        fig = px.scatter_mapbox(d, mapbox_style="carto-positron", **kw)
    fig.update_traces(marker=dict(opacity=0.75))
    return style(fig, h)


def fig_danger(boro, year, housing, h=480):
    """100% stacked horizontal bar: share of each borough's units by danger level."""
    d = f_buildings(boro, year, housing)
    d = d[d["borough"].isin(BOROUGHS)]
    if d.empty or d["all_counted_units"].sum() == 0:
        return empty(h)
    g = d.groupby(["borough", "danger_level"])["all_counted_units"].sum().reset_index()
    g["pct"] = g["all_counted_units"] / g.groupby("borough")["all_counted_units"].transform("sum") * 100
    order = (g[g["danger_level"].isin(HIGH)].groupby("borough")["pct"].sum()
             .reindex(g["borough"].unique(), fill_value=0).sort_values().index.tolist())
    fig = px.bar(g, x="pct", y="borough", color="danger_level", orientation="h",
                 category_orders={"danger_level": DANGER_LEVELS, "borough": order},
                 color_discrete_map=DANGER_COLORS, custom_data=["all_counted_units"])
    fig.update_traces(marker_line_width=0,
                      hovertemplate="%{y}<br>%{fullData.name}: %{x:.1f}%<br>"
                                    "%{customdata[0]:,.0f} units<extra></extra>")
    style(fig, h)
    fig.update_layout(barmode="stack", bargap=0.45)
    fig.update_xaxes(range=[0, 100], ticksuffix="%", title=None)
    fig.update_yaxes(title=None, showgrid=False, type="category")
    return fig


def fig_top_zips(boro, year, housing, h=330):
    """Top 10 ZIPs by affordable units completed."""
    b = f_buildings(boro, year, housing)
    g = (b.groupby("zip_code").agg(units=("all_counted_units", "sum"),
                                   borough=("borough", "first"))
         .nlargest(10, "units").reset_index())
    g = g[g["units"] > 0]
    if g.empty:
        return empty(h)
    g = g.sort_values("units")
    fig = px.bar(g, x="units", y="zip_code", color="borough", orientation="h",
                 color_discrete_map=BORO_COLORS,
                 category_orders={"zip_code": g["zip_code"].tolist(), "borough": BOROUGHS},
                 labels={"units": "Affordable units completed", "zip_code": "ZIP",
                         "borough": "Borough"})
    fig.update_traces(marker_line_width=0,
                      hovertemplate="ZIP %{y}<br>%{x:,.0f} units<extra></extra>")
    style(fig, h)
    fig.update_layout(bargap=0.35)
    fig.update_yaxes(type="category", showgrid=False, title=None)
    return fig


def fig_heat(boro, metric, h=380):
    """Borough x year (all boroughs) or top-12 ZIP x year (one borough)."""
    z = f_zip(boro, "all")
    if boro == "all":
        z = z[z["borough"].isin(BOROUGHS)]
        p = z.pivot_table(index="borough", columns="year", values=metric, aggfunc="sum")
    else:
        top = z.groupby("zip_code")[metric].sum().nlargest(12).index
        p = z[z["zip_code"].isin(top)].pivot_table(index="zip_code", columns="year",
                                                   values=metric, aggfunc="sum").reindex(top)
    if p.empty:
        return empty(h)
    fig = go.Figure(go.Heatmap(
        z=p.values, x=[str(c) for c in p.columns], y=[str(i) for i in p.index],
        colorscale=[[0, "#f4f1ff"], [0.5, "#a48bff"], [1, "#3b1e9e"]],
        xgap=3, ygap=3, colorbar=dict(thickness=10, outlinewidth=0),
        hovertemplate="%{y} · %{x}<br>" + TRANSPORT[metric] + ": %{z:,.0f}<extra></extra>",
    ))
    style(fig, h, legend=False)
    fig.update_xaxes(type="category", showgrid=False)
    fig.update_yaxes(type="category", showgrid=False, autorange="reversed")
    return fig


def fig_scatter(boro, year, housing, metric, h=380):
    """ZIP level: affordable units vs. traffic harm, linear trend + Spearman rho."""
    z = f_zip(boro, year)
    z = z[~z["is_special_zip"].astype(bool)]
    harm = z.groupby("zip_code").agg(borough=("borough", "first"),
                                     harm=(metric, "sum")).reset_index()
    units = (f_buildings(boro, year, housing).groupby("zip_code")["all_counted_units"]
             .sum().rename("units"))
    m = harm.merge(units, on="zip_code", how="left").fillna({"units": 0})
    m = m[m["borough"].isin(BOROUGHS)]
    if len(m) < 3:
        return empty(h), None
    rho = m["units"].rank().corr(m["harm"].rank())     # Spearman without scipy
    fig = px.scatter(m, x="units", y="harm", color="borough", hover_name="zip_code",
                     color_discrete_map=BORO_COLORS, category_orders={"borough": BOROUGHS},
                     labels={"units": "Affordable units completed",
                             "harm": TRANSPORT[metric], "borough": "Borough"})
    fig.update_traces(marker=dict(size=9, opacity=0.8, line=dict(width=1, color="white")))
    if m["units"].nunique() > 1:
        k, c = np.polyfit(m["units"], m["harm"], 1)
        xs = np.linspace(m["units"].min(), m["units"].max(), 50)
        fig.add_scatter(x=xs, y=k * xs + c, mode="lines", name="Linear trend",
                        line=dict(color=INK, dash="dot", width=1.5), hoverinfo="skip")
    return style(fig, h), rho


def fig_victims(boro, year, h=380):
    """Who gets hurt: pedestrian / cyclist / motorist share (100% stacked)."""
    cols = {"pedestrians_injured": "Pedestrians", "cyclists_injured": "Cyclists",
            "motorists_injured": "Motorists"}
    if boro == "all":
        z = f_zip("all", year)
        z = z[z["borough"].isin(BOROUGHS)]
        key = "borough"
    else:
        z = f_zip(boro, "all")
        key = "year"
    g = z.groupby(key)[list(cols)].sum().rename(columns=cols)
    g = g[g.sum(axis=1) > 0]
    if g.empty:
        return empty(h)
    pct = g.div(g.sum(axis=1), axis=0).mul(100).reset_index()
    long = pct.melt(id_vars=key, var_name="victim", value_name="pct")
    long[key] = long[key].astype(str)
    fig = px.bar(long, x=key, y="pct", color="victim", color_discrete_map=VICTIM_COLORS,
                 category_orders={"victim": list(VICTIM_COLORS)},
                 labels={key: key.title(), "pct": "Share of people injured", "victim": ""})
    fig.update_traces(marker_line_width=0,
                      hovertemplate="%{x}<br>%{fullData.name}: %{y:.1f}%<extra></extra>")
    style(fig, h)
    fig.update_layout(barmode="stack", bargap=0.4)
    fig.update_yaxes(range=[0, 100], ticksuffix="%")
    fig.update_xaxes(type="category", showgrid=False, title=None)
    return fig


def fig_box(boro, year, housing, metric, h=380):
    """Injuries near each building, by share of lowest-income units."""
    col = BUILDING_METRIC.get(metric, "injured_250m_per_year")
    d = f_buildings(boro, year, housing, dedupe=True).dropna(subset=["li_group", col])
    if d.empty:
        return empty(h), col
    fig = px.box(d, x="li_group", y=col, color="li_group", points=False,
                 category_orders={"li_group": LI_GROUPS}, color_discrete_sequence=LI_COLORS,
                 labels={"li_group": "Share of lowest-income units", col: BUILDING_LABEL[col]})
    style(fig, h, legend=False)
    fig.update_xaxes(showgrid=False)
    return fig, col


def fig_li_danger(boro, year, housing, h=380):
    """% of units in High / Very high danger areas, by lowest-income group."""
    b = f_buildings(boro, year, housing).dropna(subset=["li_group"])
    tot = b.groupby("li_group")["all_counted_units"].sum()
    hi = b[b["danger_level"].isin(HIGH)].groupby("li_group")["all_counted_units"].sum()
    pct = (hi.reindex(tot.index, fill_value=0) / tot.replace(0, np.nan) * 100)
    pct = pct.reindex(LI_GROUPS).dropna()
    if pct.empty:
        return empty(h)
    fig = go.Figure(go.Bar(
        x=pct.index.tolist(), y=pct.values, text=[f"{v:.1f}%" for v in pct.values],
        textposition="outside", marker=dict(color=LI_COLORS[:len(pct)], line=dict(width=0)),
        hovertemplate="%{x}<br>%{y:.1f}% of units in high-danger areas<extra></extra>",
    ))
    style(fig, h, legend=False)
    fig.update_layout(bargap=0.45)
    fig.update_yaxes(ticksuffix="%", range=[0, max(100, pct.max() * 1.15)],
                     title_text="Units in High / Very high danger")
    fig.update_xaxes(type="category", showgrid=False, title_text="Share of lowest-income units")
    return fig


# ----------------------------------------------------------------------------
# Building blocks
# ----------------------------------------------------------------------------
def graph(fig, h):
    return dcc.Graph(figure=fig, style={"height": f"{h}px"},
                     config={"displaylogo": False,
                             "modeBarButtonsToRemove": ["lasso2d", "select2d"]})


def card(title, sub, body, span, extra_cls=""):
    return html.Div(className=f"card span-{span} {extra_cls}", children=[
        html.Div(className="card-head", children=[
            html.Div([html.H3(title, className="card-title"),
                      html.P(sub, className="card-sub")]),
        ]),
        body,
    ])


def kpi(color, icon, label, value, note):
    return html.Div(className=f"kpi {color}", children=[
        html.Div(className="kpi-label", children=[
            html.Span(html.I(className=f"bi {icon}"), className="kpi-icon"), label]),
        html.Div(value, className="kpi-value"),
        html.Div(note, className="kpi-note"),
    ])


def labels(r):
    return ["All boroughs" if r["boro"] == "all" else r["boro"],
            f"{Y_MIN}–{Y_MAX}" if r["year"] == "all" else str(r["year"]),
            "All housing" if r["housing"] == "all" else r["housing"],
            TRANSPORT[r["metric"]]]


def build_kpis(boro, year, housing, metric):
    b = f_buildings(boro, year, housing)
    z = f_zip(boro, year)
    units = b["all_counted_units"].sum()
    harm = z[metric].sum()
    high = b.loc[b["danger_level"].isin(HIGH), "all_counted_units"].sum() / units * 100 if units else 0
    inj = z["persons_injured"].sum()
    ped = z["pedestrians_injured"].sum() / inj * 100 if inj else 0
    delta = f"{Y_MIN}–{Y_MAX} total" if year == "all" else f"in {year}"
    if year != "all" and int(year) - 1 in YEARS:
        prev = f_zip(boro, int(year) - 1)[metric].sum()
        if prev:
            delta = f"{(harm - prev) / prev * 100:+.1f}% vs {int(year) - 1}"
    return html.Div(className="kpis span-12", children=[
        kpi("purple", "bi-buildings", "Affordable units", fmt(units), f"{len(b):,} buildings"),
        kpi("blue", "bi-cone-striped", TRANSPORT[metric], fmt(harm), delta),
        kpi("green", "bi-exclamation-triangle", "Units in high-danger areas",
            f"{high:.1f}%", "High + Very high danger level"),
        kpi("pink", "bi-person-walking", "Pedestrian share", f"{ped:.1f}%", "of all people injured"),
    ])


def build_report(r):
    boro, year, housing, metric = r["boro"], r["year"], r["housing"], r["metric"]
    b = f_buildings(boro, year, housing)
    z = f_zip(boro, year)
    if boro == "all":
        top = z[z["borough"].isin(BOROUGHS)].groupby("borough")[metric].sum()
        where = (f"Most {TRANSPORT[metric].lower()}: {top.idxmax()} ({fmt(top.max())})"
                 if top.sum() else "No traffic data for this selection")
    else:
        top = z.groupby("zip_code")[metric].sum()
        where = (f"Worst ZIP: {top.idxmax()} ({fmt(top.max())} {TRANSPORT[metric].lower()})"
                 if top.sum() else "No traffic data for this selection")
    units_zip = b.groupby("zip_code")["all_counted_units"].sum()
    most = (f"Most new affordable units: ZIP {units_zip.idxmax()} ({fmt(units_zip.max())})"
            if len(units_zip) and units_zip.max() > 0 else "No affordable housing in this selection")
    med = f_buildings(boro, year, housing, dedupe=True).groupby("li_group")["injured_250m_per_year"].median()
    if {"None", "Over 50%"} <= set(med.index) and pd.notna(med["None"]) and med["None"] \
            and pd.notna(med["Over 50%"]):
        gap = (med["Over 50%"] - med["None"]) / med["None"] * 100
        equity = f"Buildings >50% lowest-income see {gap:+.0f}% injuries nearby vs. buildings with none"
    else:
        equity = "Not enough buildings to compare income groups"
    ts = r.get("ts") or datetime.now().strftime("%d %b %Y, %H:%M")
    rows = [("bi-geo-alt", where), ("bi-house-door", most), ("bi-people", equity)]
    return html.Div([
        *[html.Div(className="report-item", children=[
            html.Span(html.I(className=f"bi {icon}"), className="report-dot"),
            html.Div(text, className="report-text")]) for icon, text in rows],
        html.Div(f"Generated {ts}", className="report-time"),
    ])


# ----------------------------------------------------------------------------
# Pages
# ----------------------------------------------------------------------------
def page_overview(r):
    boro, year, housing, metric = r["boro"], r["year"], r["housing"], r["metric"]
    return [
        build_kpis(boro, year, housing, metric),
        card("Housing vs. traffic harm",
             "Affordable units completed (bars) and the selected transport measure (line) per year",
             graph(fig_trend(boro, year, housing, metric), 340), 8),
        card("Report summary", "What this selection shows", build_report(r), 4),
    ]


def page_housing(r):
    boro, year, housing = r["boro"], r["year"], r["housing"]
    return [
        card("Where affordable housing is built",
             "Each dot is a building · colour = traffic danger level within 250 m · size = units",
             graph(fig_map(boro, year, housing), 480), 8),
        card("Units by danger level",
             "Share of each borough's affordable units by surrounding danger level",
             graph(fig_danger(boro, year, housing), 480), 4),
        card("Top 10 ZIP codes", "Most affordable units completed in this selection",
             graph(fig_top_zips(boro, year, housing), 330), 12),
    ]


def page_safety(r):
    boro, year, housing, metric = r["boro"], r["year"], r["housing"], r["metric"]
    scatter, rho = fig_scatter(boro, year, housing, metric)
    rho_txt = f" · Spearman ρ = {rho:.2f}" if rho is not None and not np.isnan(rho) else ""
    heat_sub = (f"{TRANSPORT[metric]} by borough and year (all years)" if boro == "all"
                else f"{TRANSPORT[metric]} in {boro}'s 12 worst ZIPs, by year (all years)")
    vic_sub = ("Share of people injured, by borough" if boro == "all"
               else f"Share of people injured in {boro}, by year")
    return [
        card("Traffic harm heatmap", heat_sub, graph(fig_heat(boro, metric), 380), 12),
        card("More housing, more harm?",
             "ZIP level · affordable units vs. " + TRANSPORT[metric].lower() + rho_txt,
             graph(scatter, 380), 7),
        card("Who gets hurt", vic_sub, graph(fig_victims(boro, year), 380), 5),
    ]


def page_equity(r):
    boro, year, housing, metric = r["boro"], r["year"], r["housing"], r["metric"]
    box, col = fig_box(boro, year, housing, metric)
    box_sub = "Per building · " + BUILDING_LABEL[col].lower()
    if metric not in BUILDING_METRIC and metric != "persons_injured":
        box_sub += f" ({TRANSPORT[metric].lower()} not available per building)"
    return [
        card("Are the poorest households more exposed?", box_sub, graph(box, 380), 7),
        card("Units in dangerous areas, by income mix",
             "% of units in High / Very high danger areas",
             graph(fig_li_danger(boro, year, housing), 380), 5),
        card("Report summary", "What this selection shows", build_report(r), 12),
    ]


STORY_FINDINGS = """
**1. The problem is at neighbourhood level.** ZIPs that received more affordable housing rank much higher for traffic injuries (r = 0.56). The danger clusters are the South/Central Bronx, Upper Manhattan and Central/East Brooklyn.

**2. Danger is shared roughly equally across income groups.** Injuries near buildings with no lowest-income units and with over 50% differ by only ~5%. The exception is the Bronx (+13%).

**3. New housing does not make streets more dangerous.** After a building opens, nearby crash changes follow the city trend. ZIPs with the most new housing saw injuries fall the most (–12.5%).

**4. Placement is improving.** The share of new units in dangerous areas fell from 43% (2016–20) to 37% (2021–25).

**5. Pedestrians carry extra risk in the Bronx and Queens** (+4–5 pp pedestrian share near new housing).
"""
STORY_NYC = """
1. **Plan street safety with housing, not after it.** New projects in the red clusters should come with a street-safety plan from day one.
2. **Pedestrian infrastructure first in the Bronx and Queens:** crossings, signal timing, sidewalk extensions.
3. **Treat crash volume around lowest-income housing:** intersection redesign, loading zones, parking enforcement.
4. **Prioritise the Bronx:** the only borough where the poorest households are clearly more exposed.
5. **Keep steering new units** away from High / Very high danger areas.
"""
STORY_LIMITS = """
- **No population or traffic-volume data:** denser ZIPs naturally have more housing *and* more crashes, so part of the link is a density effect.
- **Correlation, not causation:** Vision Zero redesigns, COVID-19 and enforcement changes happened at the same time.
- **Only affordable housing:** there are no market-rate buildings to compare against.
- **Spatial choices matter:** the 250 m radius picks up nearby arterials; ZIP-level joins hide variation inside a ZIP.
"""


def page_story(_):
    return [html.Div(className="card span-12", children=[
        html.Div(className="story-hero", children=
                 "New York's affordable housing is concentrated in neighbourhoods that already have a lot of "
                 "traffic injuries, but building it does not make those streets more dangerous, and the poorest "
                 "households are not placed on worse streets than other affordable-housing residents."),
        html.Div(className="story-cols", children=[
            html.Div(className="story-col", children=[html.H4("Key findings"), dcc.Markdown(STORY_FINDINGS)]),
            html.Div(className="story-col", children=[html.H4("What it means for NYC"), dcc.Markdown(STORY_NYC)]),
            html.Div(className="story-col", children=[html.H4("Limitations"), dcc.Markdown(STORY_LIMITS)]),
        ]),
    ])]


def dataset_card(color, title, text, badge, link):
    return html.Div(className=f"ds-card span-4 {color}", children=[
        html.P(title, className="ds-title"),
        html.P(text, className="ds-text"),
        html.Div(className="ds-foot", children=[
            html.Span(badge, className="ds-badge"),
            html.A("Open dataset ↗", href=link, target="_blank", className="ds-link")
            if link else html.Span(),
        ]),
    ])


PIPELINE = [
    ("bi-search", "Explore", "Profiled both datasets: rows, columns, location and time fields, known issues."),
    ("bi-brush", "Clean", "Missing values, outliers (IQR), inconsistent boroughs and ZIPs, duplicates."),
    ("bi-link-45deg", "Integrate", "Joined on ZIP code × year; each building also linked to crashes within 250 m."),
    ("bi-check2-circle", "Clean after join", "New missing values, repeated columns, mismatched data types."),
    ("bi-bar-chart-line", "Visualise", "This multi-page Dash app with filters, search and Generate Report."),
]


def page_data(_):
    cols = ["zip_code", "year", "borough", "crashes", "persons_injured",
            "pedestrians_injured", "affordable_units_completed"]
    cols = [c for c in cols if c in zy.columns]
    sample = zy[zy["persons_injured"] > 0].sort_values(["year", "zip_code"]).head(8)[cols]
    table = html.Table(className="preview", children=[
        html.Thead(html.Tr([html.Th(c.replace("_", " ")) for c in cols])),
        html.Tbody([html.Tr([html.Td(f"{v:,.0f}" if isinstance(v, (int, float, np.number))
                                     and c not in ("year",) else str(v)) for c, v in row.items()])
                    for _, row in sample.iterrows()]),
    ])
    return [
        dataset_card("purple", "Affordable Housing Production by Building",
                     "NYC HPD · buildings, units and income bands.", f"{len(bd):,} buildings",
                     "https://data.cityofnewyork.us/Housing-Development/Affordable-Housing-Production-by-Building/hg8x-zxpr"),
        dataset_card("blue", "Motor Vehicle Collisions – Crashes",
                     "NYPD · every reported crash with injuries and fatalities.",
                     f"{fmt(zy['crashes'].sum())} crashes",
                     "https://data.cityofnewyork.us/Public-Safety/Motor-Vehicle-Collisions-Crashes/h9gi-nx95"),
        dataset_card("green", "Integrated ZIP × year table",
                     "Both datasets joined on ZIP code and year.",
                     f"{zy['zip_code'].nunique()} ZIPs × {len(YEARS)} yrs", None),
        html.Div(className="card span-12", children=[
            html.H3("Data pipeline", className="card-title"),
            html.P("From raw open data to this dashboard", className="card-sub"),
            html.Div(className="pipeline", children=[
                html.Div(className="step", children=[
                    html.Span(html.I(className=f"bi {icon}"), className="report-dot"),
                    html.Div([html.Div(f"{i}. {name}", className="step-title"),
                              html.Div(text, className="step-text")])])
                for i, (icon, name, text) in enumerate(PIPELINE, 1)]),
        ]),
        html.Div(className="card span-12", children=[
            html.H3("Integrated table preview", className="card-title"),
            html.P("First rows of integrated_zip_year.csv · use the download icon in the sidebar "
                   "to export the rows behind your current report", className="card-sub"),
            html.Div(table, className="table-wrap"),
        ]),
    ]


def page_team(_):
    def initials(n):
        return "".join(p[0] for p in n.split()[:2]).upper()
    return [
        html.Div(className="card span-12", children=[
            html.H3("The team", className="card-title"),
            html.P("Data Engineering & Visualization · Milestone 1 · German International University",
                   className="card-sub"),
            html.Div(className="team", children=[
                html.Div(className="member", children=[
                    html.Span(initials(n), className="member-avatar"),
                    html.Div(n, className="member-name")]) for n in TEAM]),
        ]),
    ]


ANALYSIS_PAGES = {
    "/": ("Dashboard", "Overview of affordable housing and traffic harm", page_overview),
    "/housing": ("Housing", "Where new affordable housing is built and how dangerous its streets are", page_housing),
    "/safety": ("Safety", "Traffic harm across boroughs, ZIPs and years", page_safety),
    "/equity": ("Equity", "Are the poorest households placed on more dangerous streets?", page_equity),
}
OTHER_PAGES = {
    "/story": ("Story", "Summary & conclusions from our analysis", page_story),
    "/data": ("Data & methods", "Datasets, pipeline and the integrated table", page_data),
    "/team": ("Team", "Who built this project", page_team),
}
SIDE_LINKS = [("/story", "bi-book", "Story"), ("/data", "bi-database", "Data & methods"),
              ("/team", "bi-people", "Team")]


# ----------------------------------------------------------------------------
# App + shared layout
# ----------------------------------------------------------------------------
app = Dash(__name__, title="NYC Housing × Traffic Safety", suppress_callback_exceptions=True,
           external_stylesheets=["https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css"])
server = app.server


def dropdown(did, label, options, value):
    return html.Div([
        html.Div(label, className="field-label"),
        dcc.Dropdown(id=did, options=options, value=value, clearable=False,
                     searchable=False, className="dd"),
    ])


sidebar = html.Div(className="sidebar", children=[
    *[dcc.Link(id=f"side-{p.strip('/')}", href=p, className="side-icon", children=[
        html.I(className=f"bi {icon}"), html.Span(label, className="tip")])
      for p, icon, label in SIDE_LINKS],
    html.Div(className="side-sep"),
    html.Button(id="dl-btn", className="side-icon", n_clicks=0, children=[
        html.I(className="bi bi-download"), html.Span("Download report data (CSV)", className="tip")]),
    dcc.Download(id="dl"),
])

topbar = html.Div(className="topbar", children=[
    dcc.Link("NYC", href="/", className="logo"),
    html.Nav(className="pills", children=[
        dcc.Link(name, id=f"top-{p.strip('/') or 'home'}", href=p, className="pill")
        for p, (name, _, _) in ANALYSIS_PAGES.items()]),
    html.Div(className="top-actions", children=[
        html.Span(f"{Y_MIN}–{Y_MAX}", className="chip big"),
        html.Span("DEV", className="round avatar"),
    ]),
])

filters = html.Div(id="filters", className="card", children=[
    html.H3("Build a report", className="card-title"),
    html.P("Search or pick filters, then generate", className="card-sub"),
    html.Div(className="search-wrap", children=[
        dcc.Input(id="search", type="text", className="search-input",
                  placeholder="e.g. Bronx 2022 new construction pedestrians"),
        html.Button(html.I(className="bi bi-search"), id="search-btn", className="search-btn"),
    ]),
    html.Div(id="search-msg", className="search-msg"),
    dropdown("f-boro", "Borough", [{"label": "All boroughs", "value": "all"}] +
             [{"label": b, "value": b} for b in BOROUGHS], "all"),
    dropdown("f-year", "Year", [{"label": "All years", "value": "all"}] +
             [{"label": str(y), "value": y} for y in YEARS], "all"),
    dropdown("f-housing", "Housing category", [{"label": "All housing", "value": "all"}] +
             [{"label": h, "value": h} for h in HOUSING_TYPES], "all"),
    dropdown("f-transport", "Transport category",
             [{"label": v, "value": k} for k, v in TRANSPORT.items()], "persons_injured"),
    html.Button([html.I(className="bi bi-stars"), " Generate Report"],
                id="generate", n_clicks=0, className="generate"),
    html.P("The report applies to every page in the top bar.", className="filter-hint"),
])

app.layout = html.Div(className="shell", children=[
    dcc.Location(id="url"),
    dcc.Store(id="report-store", data=DEFAULT_REPORT),
    sidebar,
    topbar,
    html.Div(id="page-head"),
    html.Div(id="layout", className="layout", children=[
        html.Div(className="left", children=[filters]),
        dcc.Loading(type="dot", color="#7c5cff", parent_className="page-wrap",
                    children=html.Div(id="page", className="grid")),
    ]),
])


# ----------------------------------------------------------------------------
# Callbacks
# ----------------------------------------------------------------------------
@app.callback(
    Output("page-head", "children"), Output("page", "children"), Output("layout", "className"),
    Input("url", "pathname"), Input("report-store", "data"),
)
def render_page(path, r):
    r = r or DEFAULT_REPORT
    path = path if path in ANALYSIS_PAGES or path in OTHER_PAGES else "/"
    if path in ANALYSIS_PAGES:
        title, sub, builder = ANALYSIS_PAGES[path]
        chips = html.Div(className="head-chips", children=[
            html.Span(x, className="chip") for x in labels(r)])
        head = html.Div(className="page-head", children=[
            html.Div([html.H1(title, className="page-title"), html.P(sub, className="page-sub")]),
            chips])
        return head, builder(r), "layout"
    title, sub, builder = OTHER_PAGES[path]
    head = html.Div(className="page-head", children=[
        html.Div([html.H1(title, className="page-title"), html.P(sub, className="page-sub")])])
    return head, builder(r), "layout no-filters"


NAV_IDS = [f"top-{p.strip('/') or 'home'}" for p in ANALYSIS_PAGES] + \
          [f"side-{p.strip('/')}" for p, _, _ in SIDE_LINKS]
NAV_PATHS = list(ANALYSIS_PAGES) + [p for p, _, _ in SIDE_LINKS]


@app.callback([Output(i, "className") for i in NAV_IDS], Input("url", "pathname"))
def highlight_nav(path):
    out = []
    for i, p in zip(NAV_IDS, NAV_PATHS):
        base = "pill" if i.startswith("top-") else "side-icon"
        out.append(f"{base} active" if path == p else base)
    return out


@app.callback(
    Output("report-store", "data"),
    Input("generate", "n_clicks"),
    State("f-boro", "value"), State("f-year", "value"),
    State("f-housing", "value"), State("f-transport", "value"),
    prevent_initial_call=True,
)
def generate_report(_, boro, year, housing, metric):
    """Generate Report: saves the filters; every analysis page redraws from them."""
    return {"boro": boro or "all", "year": "all" if year in (None, "") else year,
            "housing": housing or "all", "metric": metric or "persons_injured",
            "ts": datetime.now().strftime("%d %b %Y, %H:%M")}


@app.callback(
    Output("f-boro", "value"), Output("f-year", "value"),
    Output("f-housing", "value"), Output("f-transport", "value"),
    Output("search-msg", "children"),
    Input("search", "n_submit"), Input("search-btn", "n_clicks"),
    State("search", "value"),
    prevent_initial_call=True,
)
def run_search(_, __, text):
    """Free-text search -> sets all four dropdowns."""
    if not text or not text.strip():
        return no_update, no_update, no_update, no_update, \
            "Try “Bronx 2022 new construction pedestrians”."
    q = text.lower()

    boro = "all"
    for key, name in [("staten", "Staten Island"), ("bronx", "Bronx"), ("brooklyn", "Brooklyn"),
                      ("manhattan", "Manhattan"), ("queens", "Queens")]:
        if key in q:
            boro = name
            break

    year, note = "all", ""
    m = re.search(r"\b(19|20)\d{2}\b", q)
    if m:
        if int(m.group()) in YEARS:
            year = int(m.group())
        else:
            note = f" (no data for {m.group()})"

    housing = "all"
    for h in HOUSING_TYPES:
        hl = h.lower()
        if ("new" in q and "new" in hl) or ("preserv" in q and "preserv" in hl):
            housing = h
            break

    metric = "persons_injured"
    for keys, col in [(("pedestrian", "walk"), "pedestrians_injured"),
                      (("cycl", "bike", "bicycl"), "cyclists_injured"),
                      (("motorist", "driver", "car "), "motorists_injured"),
                      (("fatal", "kill", "death", "dead"), "persons_killed"),
                      (("crash",), "crashes")]:
        if any(k in q + " " for k in keys):
            metric = col
            break

    parts = labels({"boro": boro, "year": year, "housing": housing, "metric": metric})
    return boro, year, housing, metric, "✓ " + " · ".join(parts) + note + " — press Generate Report"


@app.callback(Output("dl", "data"), Input("dl-btn", "n_clicks"),
              State("report-store", "data"), prevent_initial_call=True)
def download(_, r):
    r = r or DEFAULT_REPORT
    d = f_zip(r["boro"], r["year"])
    name = "_".join(x.replace(" ", "-").replace("–", "-") for x in labels(r)[:2]).lower()
    return dcc.send_data_frame(d.to_csv, f"nyc_report_{name}.csv", index=False)


if __name__ == "__main__":
    app.run(debug=True)

import json
from collections import defaultdict
from datetime import datetime

import plotly.graph_objects as go

FLOW_JSON   = "flow_rates_hourly.json"
NAMES_JSON  = "station_names.json"
OUTPUT_HTML = "flow_rate_viz.html"

with open(FLOW_JSON, encoding="utf-8") as f:
    data = json.load(f)

with open(NAMES_JSON, encoding="utf-8") as f:
    station_names = json.load(f)

# --- Aggregate arrivals & departures by (day_of_week, hour) per station ---
# Result: average over all weeks in the dataset -> "typical week" pattern
station_buckets = defaultdict(lambda: defaultdict(lambda: {"arr": [], "dep": []}))

for window_str, stations in data.items():
    dt  = datetime.strptime(window_str, "%Y-%m-%d %H:%M")
    key = (dt.weekday(), dt.hour)   # (0=Mon … 6=Sun, 0-23)
    for sid, counts in stations.items():
        station_buckets[sid][key]["arr"].append(counts["arrivals"])
        station_buckets[sid][key]["dep"].append(counts["departures"])

# --- Build the 168-point x-axis (7 days × 24 hours) ---
DAYS       = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
x_keys     = [(dow, hr) for dow in range(7) for hr in range(24)]
x_labels   = [f"{DAYS[dow]} {hr:02d}:00" for dow, hr in x_keys]

# Tick marks: one per day, placed at each day's first hour label
day_ticks  = [f"{d} 00:00" for d in DAYS]

# --- Build one trace-set per station ---
TRACES_PER_STATION = 3   # net flow (filled), arrivals, departures
fig = go.Figure()

station_ids = sorted(station_buckets.keys(), key=lambda s: int(s))

for i, sid in enumerate(station_ids):
    buckets = station_buckets[sid]
    y_arr, y_dep, y_net = [], [], []
    for key in x_keys:
        b = buckets.get(key)
        if b and b["arr"]:
            arr = sum(b["arr"]) / len(b["arr"])
            dep = sum(b["dep"]) / len(b["dep"])
        else:
            arr = dep = 0.0
        y_arr.append(round(arr, 3))
        y_dep.append(round(dep, 3))
        y_net.append(round(arr - dep, 3))

    visible = (i == 0)
    sname   = station_names.get(sid, f"Station {sid}")

    # Net flow — filled area
    fig.add_trace(go.Scatter(
        x=x_labels, y=y_net,
        mode="lines",
        name="Net flow",
        line=dict(shape="spline", smoothing=1.3, color="#4a90d9", width=2.5),
        fill="tozeroy",
        fillcolor="rgba(74,144,217,0.12)",
        hovertemplate="%{x}<br>Net flow: %{y:.1f}<extra></extra>",
        visible=visible,
    ))
    # Arrivals
    fig.add_trace(go.Scatter(
        x=x_labels, y=y_arr,
        mode="lines",
        name="Arrivals",
        line=dict(shape="spline", smoothing=1.3, color="#27ae60", width=1.5, dash="dot"),
        hovertemplate="Arrivals: %{y:.1f}<extra></extra>",
        visible=visible,
    ))
    # Departures
    fig.add_trace(go.Scatter(
        x=x_labels, y=y_dep,
        mode="lines",
        name="Departures",
        line=dict(shape="spline", smoothing=1.3, color="#e67e22", width=1.5, dash="dot"),
        hovertemplate="Departures: %{y:.1f}<extra></extra>",
        visible=visible,
    ))

# --- Dropdown: one button per station ---
buttons = []
for i, sid in enumerate(station_ids):
    vis = [False] * (len(station_ids) * TRACES_PER_STATION)
    for j in range(TRACES_PER_STATION):
        vis[i * TRACES_PER_STATION + j] = True
    sname = station_names.get(sid, f"Station {sid}")
    buttons.append(dict(
        label=f"[{sid}] {sname}",
        method="update",
        args=[
            {"visible": vis},
            {"title": {"text": f"Weekly Flow Pattern  ·  [{sid}] {sname}", "font": {"size": 16}}},
        ],
    ))

# --- Day-boundary vertical lines ---
shapes = [
    dict(
        type="line",
        xref="x", yref="paper",
        x0=f"{d} 00:00", x1=f"{d} 00:00",
        y0=0, y1=1,
        line=dict(color="rgba(255,255,255,0.12)", width=1, dash="dash"),
    )
    for d in DAYS[1:]   # skip Monday (it's the left edge)
]

first_name = station_names.get(station_ids[0], station_ids[0])

fig.update_layout(
    title=dict(
        text=f"Weekly Flow Pattern  ·  [{station_ids[0]}] {first_name}",
        font=dict(size=16),
    ),
    updatemenus=[dict(
        buttons=buttons,
        direction="down",
        showactive=True,
        bgcolor="#2a2a4a",
        bordercolor="#555",
        font=dict(color="white"),
        x=0.0, xanchor="left",
        y=1.18, yanchor="top",
    )],
    xaxis=dict(
        tickmode="array",
        tickvals=day_ticks,
        ticktext=DAYS,
        showgrid=True,
        gridcolor="rgba(255,255,255,0.07)",
        tickfont=dict(size=13),
    ),
    yaxis=dict(
        title="Avg trips / hour",
        showgrid=True,
        gridcolor="rgba(255,255,255,0.07)",
        zeroline=True,
        zerolinecolor="rgba(255,255,255,0.25)",
        zerolinewidth=1,
    ),
    shapes=shapes,
    plot_bgcolor="#1a1a2e",
    paper_bgcolor="#1a1a2e",
    font=dict(color="white", family="sans-serif"),
    legend=dict(
        orientation="h",
        y=-0.12, x=0.5, xanchor="center",
        bgcolor="rgba(0,0,0,0)",
    ),
    hovermode="x unified",
    margin=dict(t=100, b=80),
)

fig.write_html(OUTPUT_HTML, include_plotlyjs="cdn")
print(f"Saved to {OUTPUT_HTML}")

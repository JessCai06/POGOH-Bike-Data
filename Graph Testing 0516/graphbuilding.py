import csv
import networkx as nx
from collections import Counter
from pyvis.network import Network

TRIPS_PATH    = "combined_trips_april27.csv"
STATS_PATH    = r"..\Station Sample Data\STATION_STATS_EXPORT-1676.csv"

G = nx.MultiDiGraph()

with open(TRIPS_PATH, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        start_id = row["Start Station Id"].strip()
        end_id = row["End Station Id"].strip()

        # Add nodes with attributes (safe to call repeatedly — networkx skips if already present)
        if start_id not in G:
            G.add_node(start_id,
                name=row["Start Station Name"],
                lat=row["Start Station Lat"],
                lon=row["Start Station Lon"],
            )
        if end_id not in G:
            G.add_node(end_id,
                name=row["End Station Name"],
                lat=row["End Station Lat"],
                lon=row["End Station Lon"],
            )

        G.add_edge(start_id, end_id,
            trip_id=row["Id"],
            duration=int(row["Duration"]) if row["Duration"] else None,
            start_date=row["Start Date"],
            end_date=row["End Date"],
            rider_type=row["Rider Type"],
            closed_status=row["Closed Status"],
        )

# Load end-of-day station capacity from station stats (last record per station on Apr 27)
station_capacity = {}
with open(STATS_PATH, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        if row["Date Time"].startswith("4/27/2026"):
            sid = str(int(float(row["Station ID"])))
            station_capacity[sid] = {
                "capacity": row["Total Docks Installed"].strip(),
                "bikes_eod": row["Total Bikes At Station Per Model"].strip(),
                "avail_docks_eod": row["Number of Available Docks"].strip(),
            }

def cap_str(node_id):
    c = station_capacity.get(node_id)
    if not c:
        return "  capacity: n/a"
    return f"  capacity: {c['capacity']} docks  |  bikes at 23:59: {c['bikes_eod']}  |  open docks: {c['avail_docks_eod']}"

def bar(value, max_val, width=30):
    filled = round(value / max_val * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"

# --- Summary statistics ---
print("=" * 60)
print(f"  POGOH April 27 — Graph Summary")
print("=" * 60)
print(f"  Stations: {G.number_of_nodes()}   |   Trips: {G.number_of_edges()}")

rider_counts = Counter(data["rider_type"] for _, _, data in G.edges(data=True))
print(f"  " + "  ".join(f"{t}: {c}" for t, c in sorted(rider_counts.items())))

durations = [data["duration"] for _, _, data in G.edges(data=True) if data["duration"] is not None]
print(f"  Avg duration: {sum(durations)/len(durations)/60:.1f} min  |  Median: {sorted(durations)[len(durations)//2]//60} min")

wcc = nx.number_weakly_connected_components(G)
scc = nx.number_strongly_connected_components(G)
self_loops = sum(1 for u, v in G.edges() if u == v)
print(f"  Weakly connected components: {wcc}  |  Strongly: {scc}  |  Round trips: {self_loops}")

# Degree tables
out_degrees = sorted(G.out_degree(), key=lambda x: x[1], reverse=True)
in_degrees  = sorted(G.in_degree(),  key=lambda x: x[1], reverse=True)
max_out = out_degrees[0][1]
max_in  = in_degrees[0][1]

print()
print("=" * 60)
print("  TOP 10 — DEPARTURES")
print("=" * 60)
for rank, (node_id, out_deg) in enumerate(out_degrees[:10], 1):
    in_deg   = G.in_degree(node_id)
    net_flow = out_deg - in_deg
    name     = G.nodes[node_id]["name"]
    print(f"  {rank:2}. [{node_id:>3}] {name}")
    print(f"      {bar(out_deg, max_out)} {out_deg} out  |  {in_deg} in  |  net: {net_flow:+d}")
    print(cap_str(node_id))
    print()

print("=" * 60)
print("  TOP 10 — ARRIVALS")
print("=" * 60)
for rank, (node_id, in_deg) in enumerate(in_degrees[:10], 1):
    out_deg  = G.out_degree(node_id)
    net_flow = out_deg - in_deg
    name     = G.nodes[node_id]["name"]
    print(f"  {rank:2}. [{node_id:>3}] {name}")
    print(f"      {bar(in_deg, max_in)} {in_deg} in  |  {out_deg} out  |  net: {net_flow:+d}")
    print(cap_str(node_id))
    print()

print("=" * 60)
print("  TOP 10 -- NET FLOW (departures - arrivals)")
print("=" * 60)
net_flows = sorted(
    ((nid, G.out_degree(nid) - G.in_degree(nid)) for nid in G.nodes()),
    key=lambda x: abs(x[1]), reverse=True
)
max_net = abs(net_flows[0][1])
for rank, (node_id, net_flow) in enumerate(net_flows[:10], 1):
    out_deg = G.out_degree(node_id)
    in_deg  = G.in_degree(node_id)
    name    = G.nodes[node_id]["name"]
    direction = "source ▲" if net_flow > 0 else "sink   ▼"
    print(f"  {rank:2}. [{node_id:>3}] {name}  ({direction})")
    print(f"      {bar(abs(net_flow), max_net)} net {net_flow:+d}  ({out_deg} out, {in_deg} in)")
    print(cap_str(node_id))
    print()

# --- Visualization ---
RIDER_COLORS = {"MEMBER": "#4a90d9", "CASUAL": "#27ae60", "TECH": "#e67e22"}

# Aggregate multi-edges into a simple weighted digraph for cleaner rendering
agg = {}  # (u, v) -> {count, rider_type_counts}
for u, v, data in G.edges(data=True):
    key = (u, v)
    if key not in agg:
        agg[key] = {"count": 0, "rider_types": Counter()}
    agg[key]["count"] += 1
    agg[key]["rider_types"][data["rider_type"]] += 1

# Scale lat/lon to pixel coords (center on Pittsburgh)
lats = [float(d["lat"]) for _, d in G.nodes(data=True) if d.get("lat")]
lons = [float(d["lon"]) for _, d in G.nodes(data=True) if d.get("lon")]
center_lat = sum(lats) / len(lats)
center_lon = sum(lons) / len(lons)
SCALE = 12000

net = Network(height="800px", width="100%", directed=True, bgcolor="#1a1a2e", font_color="white")
net.barnes_hut(gravity=0, central_gravity=0, spring_length=0, spring_strength=0, damping=1)

total_degree = dict(G.degree())
max_degree = max(total_degree.values())

for node_id, data in G.nodes(data=True):
    lat = float(data["lat"]) if data.get("lat") else center_lat
    lon = float(data["lon"]) if data.get("lon") else center_lon
    x = (lon - center_lon) * SCALE
    y = -(lat - center_lat) * SCALE  # flip so north is up

    deg = total_degree[node_id]
    size = 8 + (deg / max_degree) * 30

    out_deg = G.out_degree(node_id)
    in_deg  = G.in_degree(node_id)
    net_flow = out_deg - in_deg
    # Blue = net source (more departures), red = net sink (more arrivals)
    color = f"rgb({min(255, 80 + max(0, net_flow))}, 120, {min(255, 80 + max(0, -net_flow))})"

    net.add_node(
        node_id,
        label=data["name"],
        title=f"<b>{data['name']}</b><br>ID: {node_id}<br>Departures: {out_deg}<br>Arrivals: {in_deg}<br>Net flow: {net_flow:+d}",
        x=x, y=y,
        size=size,
        color=color,
        physics=False,
    )

for (u, v), info in agg.items():
    if u == v:
        continue  # skip self-loops for readability
    dominant_type = info["rider_types"].most_common(1)[0][0]
    color = RIDER_COLORS.get(dominant_type, "#aaaaaa")
    width = 1 + (info["count"] / 20)
    breakdown = ", ".join(f"{t}: {c}" for t, c in info["rider_types"].most_common())
    net.add_edge(
        u, v,
        width=width,
        color={"color": color, "opacity": 0.6},
        title=f"{info['count']} trips ({breakdown})",
        arrows="to",
    )

net.set_options("""
{
  "edges": { "smooth": { "type": "curvedCW", "roundness": 0.15 } },
  "interaction": { "hover": true, "tooltipDelay": 100 }
}
""")

OUTPUT_HTML = "station_graph_april27.html"
net.write_html(OUTPUT_HTML)
print(f"\nVisualization saved to {OUTPUT_HTML}")

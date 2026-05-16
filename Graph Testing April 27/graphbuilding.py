import csv
import networkx as nx
from collections import Counter
from pyvis.network import Network

TRIPS_PATH = "combined_trips_april27.csv"

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

# --- Summary statistics ---
print(f"Nodes (stations): {G.number_of_nodes()}")
print(f"Edges (trips):    {G.number_of_edges()}")
print()

# Degree stats
out_degrees = sorted(G.out_degree(), key=lambda x: x[1], reverse=True)
in_degrees  = sorted(G.in_degree(),  key=lambda x: x[1], reverse=True)

print("Top 5 departure stations (out-degree):")
for node_id, deg in out_degrees[:5]:
    print(f"  [{node_id}] {G.nodes[node_id]['name']}  —  {deg} trips out")

print()
print("Top 5 arrival stations (in-degree):")
for node_id, deg in in_degrees[:5]:
    print(f"  [{node_id}] {G.nodes[node_id]['name']}  —  {deg} trips in")

print()

# Rider type breakdown per edge
rider_counts = Counter(data["rider_type"] for _, _, data in G.edges(data=True))
print("Trips by rider type:")
for rtype, count in sorted(rider_counts.items()):
    print(f"  {rtype}: {count}")

print()

# Average trip duration
durations = [data["duration"] for _, _, data in G.edges(data=True) if data["duration"] is not None]
print(f"Avg trip duration: {sum(durations) / len(durations):.0f} sec  ({sum(durations) / len(durations) / 60:.1f} min)")
print(f"Min: {min(durations)} sec  |  Max: {max(durations)} sec")

print()

# Connectivity
wcc = nx.number_weakly_connected_components(G)
scc = nx.number_strongly_connected_components(G)
print(f"Weakly connected components:  {wcc}")
print(f"Strongly connected components: {scc}")

# Self-loops (trips that start and end at the same station)
self_loops = sum(1 for u, v in G.edges() if u == v)
print(f"Self-loops (round trips):     {self_loops}")

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

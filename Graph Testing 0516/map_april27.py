import csv
import networkx as nx
import folium
from collections import Counter

TRIPS_PATH = "combined_trips_april27.csv"
OUTPUT_HTML = "station_map_april27.html"

RIDER_COLORS = {"MEMBER": "#4a90d9", "CASUAL": "#27ae60", "TECH": "#e67e22"}

# --- Build graph (same as graphbuilding.py) ---
G = nx.MultiDiGraph()

with open(TRIPS_PATH, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        start_id = row["Start Station Id"].strip()
        end_id   = row["End Station Id"].strip()

        if start_id not in G:
            G.add_node(start_id,
                name=row["Start Station Name"],
                lat=float(row["Start Station Lat"]) if row["Start Station Lat"] else None,
                lon=float(row["Start Station Lon"]) if row["Start Station Lon"] else None,
            )
        if end_id not in G:
            G.add_node(end_id,
                name=row["End Station Name"],
                lat=float(row["End Station Lat"]) if row["End Station Lat"] else None,
                lon=float(row["End Station Lon"]) if row["End Station Lon"] else None,
            )

        G.add_edge(start_id, end_id,
            rider_type=row["Rider Type"],
            duration=int(row["Duration"]) if row["Duration"] else None,
        )

# Aggregate multi-edges into (u, v) -> {count, rider_type_counts}
agg = {}
for u, v, data in G.edges(data=True):
    key = (u, v)
    if key not in agg:
        agg[key] = {"count": 0, "rider_types": Counter()}
    agg[key]["count"] += 1
    agg[key]["rider_types"][data["rider_type"]] += 1

# --- Build Folium map ---
valid_nodes = [(d["lat"], d["lon"]) for _, d in G.nodes(data=True) if d.get("lat")]
center_lat = sum(lat for lat, _ in valid_nodes) / len(valid_nodes)
center_lon = sum(lon for _, lon in valid_nodes) / len(valid_nodes)

m = folium.Map(location=[center_lat, center_lon], zoom_start=14, tiles="CartoDB dark_matter")

total_degree = dict(G.degree())
max_degree   = max(total_degree.values())

# --- Draw edges first (so nodes render on top) ---
edge_layer = folium.FeatureGroup(name="Trips", show=True)

for (u, v), info in agg.items():
    if u == v:
        continue
    u_data = G.nodes[u]
    v_data = G.nodes[v]
    if not (u_data.get("lat") and v_data.get("lat")):
        continue

    dominant_type = info["rider_types"].most_common(1)[0][0]
    color  = RIDER_COLORS.get(dominant_type, "#aaaaaa")
    weight = 1 + (info["count"] / 15)
    breakdown = ", ".join(f"{t}: {c}" for t, c in info["rider_types"].most_common())

    folium.PolyLine(
        locations=[[u_data["lat"], u_data["lon"]], [v_data["lat"], v_data["lon"]]],
        color=color,
        weight=weight,
        opacity=0.55,
        tooltip=f"{G.nodes[u]['name']} → {G.nodes[v]['name']}<br>{info['count']} trips ({breakdown})",
    ).add_to(edge_layer)

edge_layer.add_to(m)

# --- Draw nodes ---
node_layer = folium.FeatureGroup(name="Stations", show=True)

for node_id, data in G.nodes(data=True):
    if not data.get("lat"):
        continue

    out_deg = G.out_degree(node_id)
    in_deg  = G.in_degree(node_id)
    deg     = total_degree[node_id]
    net_flow = out_deg - in_deg

    radius = 5 + (deg / max_degree) * 18

    # Blue = net source, red = net sink, white = balanced
    intensity = min(abs(net_flow) / 30, 1.0)
    if net_flow > 0:
        color = f"#{int(80 + 175 * intensity):02x}b0ff"  # blue
    elif net_flow < 0:
        color = f"#ff{int(80 + 175 * (1 - intensity)):02x}{int(80 + 175 * (1 - intensity)):02x}"  # red
    else:
        color = "#ffffff"

    popup_html = (
        f"<b>{data['name']}</b><br>"
        f"Station ID: {node_id}<br>"
        f"Departures: {out_deg}<br>"
        f"Arrivals: {in_deg}<br>"
        f"Net flow: {net_flow:+d}"
    )

    folium.CircleMarker(
        location=[data["lat"], data["lon"]],
        radius=radius,
        color="#ffffff",
        weight=1,
        fill=True,
        fill_color=color,
        fill_opacity=0.85,
        tooltip=data["name"],
        popup=folium.Popup(popup_html, max_width=220),
    ).add_to(node_layer)

node_layer.add_to(m)

folium.LayerControl().add_to(m)

m.save(OUTPUT_HTML)
print(f"Map saved to {OUTPUT_HTML}")

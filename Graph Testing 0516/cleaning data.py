import csv
import json
from datetime import datetime


def parse_date(s):
    return datetime.fromisoformat(s.replace("T", " "))


OUTPUT_FIELDS = [
    "Id",
    "Closed Status",
    "Duration",
    "Start Station Id",
    "Start Station Lat",
    "Start Station Lon",
    "Start Date",
    "Start Station Name",
    "End Date",
    "End Station Id",
    "End Station Lat",
    "End Station Lon",
    "End Station Name",
    "Rider Type",
]

CUSTOMER_TRIPS_PATH = r"..\Open Source Scraped Data\Trip Data April 2026 WRPC.csv"
OPERATOR_TRIPS_PATH = r"..\Station Sample Data\data-specialist-all-operator-trips.csv"
LOCATIONS_PATH = r"..\Open Source Scraped Data\station_locations_0516.json"
OUTPUT_PATH = "combined_trips_april27.csv"

with open(LOCATIONS_PATH, encoding="utf-8") as f:
    _stations = json.load(f)["data"]["stations"]
# Key by station_id; operator trips store End Station Id as "56.0" so normalize to int string
station_coords = {
    s["station_id"]: (s["lat"], s["lon"]) for s in _stations
}

def get_coords(station_id):
    # Normalize "56.0" -> "56" to match JSON keys
    key = str(int(float(station_id))) if station_id else ""
    lat, lon = station_coords.get(key, ("", ""))
    return lat, lon

TARGET_DATE = "2026-04-27"

combined = []

with open(CUSTOMER_TRIPS_PATH, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["Start Date"].startswith(TARGET_DATE) or r["End Date"].startswith(TARGET_DATE):
            s_lat, s_lon = get_coords(r["Start Station Id"])
            e_lat, e_lon = get_coords(r["End Station Id"])
            combined.append({
                "Id": r["_id"],
                "Closed Status": r["Closed Status"],
                "Duration": r["Duration"],
                "Start Station Id": r["Start Station Id"],
                "Start Station Lat": s_lat,
                "Start Station Lon": s_lon,
                "Start Date": r["Start Date"].replace("T", " "),
                "Start Station Name": r["Start Station Name"],
                "End Date": r["End Date"].replace("T", " "),
                "End Station Id": r["End Station Id"],
                "End Station Lat": e_lat,
                "End Station Lon": e_lon,
                "End Station Name": r["End Station Name"],
                "Rider Type": r["Rider Type"],
            })

with open(OPERATOR_TRIPS_PATH, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["Start Date"].startswith(TARGET_DATE) or r["End Date"].startswith(TARGET_DATE):
            s_lat, s_lon = get_coords(r["Start Station Id"])
            e_lat, e_lon = get_coords(r["End Station Id"])
            combined.append({
                "Id": r["Id"],
                "Closed Status": r["Closed Status"],
                "Duration": r["Duration"],
                "Start Station Id": r["Start Station Id"],
                "Start Station Lat": s_lat,
                "Start Station Lon": s_lon,
                "Start Date": r["Start Date"],
                "Start Station Name": r["Start Station Name"],
                "End Date": r["End Date"],
                "End Station Id": r["End Station Id"],
                "End Station Lat": e_lat,
                "End Station Lon": e_lon,
                "End Station Name": r["End Station Name"],
                "Rider Type": r["Rider Type"],
            })

combined.sort(key=lambda r: parse_date(r["Start Date"]))

with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
    writer.writeheader()
    writer.writerows(combined)

print(f"Total rows written: {len(combined)}")
from collections import Counter
types = Counter(r["Rider Type"] for r in combined)
for rider_type, count in sorted(types.items()):
    print(f"  {rider_type}: {count}")
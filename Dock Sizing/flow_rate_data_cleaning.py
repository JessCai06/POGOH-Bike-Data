import json
import pandas as pd

RIDES_2025    = r"..\Station Sample Data\data-specialist-all-rides-2025.csv"
RIDES_2026    = r"..\Station Sample Data\data-specialist-all-rides-2026.csv"
OPERATOR_TRIPS = r"..\Station Sample Data\data-specialist-all-operator-trips.csv"

KEEP_COLS = [
    "Id", "Closed Status", "Duration",
    "Start Station Id", "Start Date", "Start Station Name",
    "End Station Id",   "End Date",   "End Station Name",
    "Rider Type", "Bike Barcode", "Bike Model",
]

# --- 1. Read all-rides (May 2025 – May 2026) ---
rides_2025 = pd.read_csv(RIDES_2025, usecols=lambda c: c in KEEP_COLS)
rides_2026 = pd.read_csv(RIDES_2026, usecols=lambda c: c in KEEP_COLS)

rides = pd.concat([rides_2025, rides_2026], ignore_index=True)

rides["Start Date"] = pd.to_datetime(rides["Start Date"])
rides = rides[
    (rides["Start Date"] >= "2025-05-01") &
    (rides["Start Date"] <  "2026-06-01")
]

# --- 2. Add operator trips with matching columns ---
operator = pd.read_csv(OPERATOR_TRIPS, usecols=lambda c: c in KEEP_COLS)
operator["Start Date"] = pd.to_datetime(operator["Start Date"])
operator = operator[
    (operator["Start Date"] >= "2025-05-01") &
    (operator["Start Date"] <  "2026-06-01")
]

combined = pd.concat([rides, operator], ignore_index=True)

# --- 3. Remove grace period entries ---
combined = combined[combined["Closed Status"] != "GRACE_PERIOD"].copy()

# --- 4. Explode into 2 rows per trip: one departure, one arrival ---
departures = combined[[
    "Id", "Closed Status", "Duration", "Rider Type", "Bike Barcode", "Bike Model",
    "Start Station Id", "Start Station Name", "Start Date",
]].rename(columns={
    "Start Station Id":   "Station Id",
    "Start Station Name": "Station Name",
    "Start Date":         "Timestamp",
})
departures["Event"] = "departure"

arrivals = combined[[
    "Id", "Closed Status", "Duration", "Rider Type", "Bike Barcode", "Bike Model",
    "End Station Id", "End Station Name", "End Date",
]].rename(columns={
    "End Station Id":   "Station Id",
    "End Station Name": "Station Name",
    "End Date":         "Timestamp",
})
arrivals["Timestamp"] = pd.to_datetime(arrivals["Timestamp"])
arrivals["Event"] = "arrival"

events = pd.concat([departures, arrivals], ignore_index=True)
events = events.sort_values("Timestamp").reset_index(drop=True)

# --- Summary ---
print(f"Trips after filtering & grace-period removal: {len(combined):,}")
print(f"  rides (customer): {len(combined[combined['Rider Type'] != 'TECH']):,}")
print(f"  operator trips:   {len(combined[combined['Rider Type'] == 'TECH']):,}")
print(f"Event rows (2x trips): {len(events):,}")
print(f"Date range: {events['Timestamp'].min()} -> {events['Timestamp'].max()}")
print(f"Stations covered: {events['Station Id'].nunique()}")

# --- 5. Hourly flow rates per station ---
combined["End Date"] = pd.to_datetime(combined["End Date"])

# Floor each timestamp to its hour window
combined["dep_window"] = combined["Start Date"].dt.floor("h")
combined["arr_window"] = combined["End Date"].dt.floor("h")

# Build station name lookup (normalized string id -> name)
_sn = pd.concat([
    combined[["Start Station Id", "Start Station Name"]].rename(columns={"Start Station Id": "sid", "Start Station Name": "station_name"}),
    combined[["End Station Id",   "End Station Name"  ]].rename(columns={"End Station Id":   "sid", "End Station Name":   "station_name"}),
]).dropna(subset=["sid"]).drop_duplicates("sid")
station_names = {
    str(int(float(sid))): sname
    for sid, sname in zip(_sn["sid"], _sn["station_name"])
    if str(sid) not in ("", "nan")
}

dep_counts = (
    combined.groupby(["dep_window", "Start Station Id"])
    .size()
    .reset_index(name="departures")
    .rename(columns={"dep_window": "window", "Start Station Id": "station_id"})
)

arr_counts = (
    combined.groupby(["arr_window", "End Station Id"])
    .size()
    .reset_index(name="arrivals")
    .rename(columns={"arr_window": "window", "End Station Id": "station_id"})
)

flow = (
    pd.merge(dep_counts, arr_counts, on=["window", "station_id"], how="outer")
    .fillna(0)
)
flow["departures"]  = flow["departures"].astype(int)
flow["arrivals"]    = flow["arrivals"].astype(int)
flow["station_id"]  = flow["station_id"].astype(str)

# flow_rates_hourly.json — only arrivals + departures per station
output = {}
for _, row in flow.iterrows():
    window_key = row["window"].strftime("%Y-%m-%d %H:%M")
    sid        = str(int(float(row["station_id"]))) if row["station_id"] else row["station_id"]
    output.setdefault(window_key, {})[sid] = {
        "arrivals":   row["arrivals"],
        "departures": row["departures"],
    }

OUTPUT_JSON = "flow_rates_hourly.json"
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2)

# station_names.json — station id -> station name
with open("station_names.json", "w", encoding="utf-8") as f:
    json.dump(station_names, f, indent=2, sort_keys=True)

print(f"\nHourly flow rates saved to {OUTPUT_JSON}")
print(f"  Time windows: {len(output):,}")
print(f"\nStation name lookup saved to station_names.json ({len(station_names)} stations)")
sample_window = next(iter(output))
print(f"\nSample ({sample_window}):")
for sid, stats in list(output[sample_window].items())[:3]:
    print(f"  station {sid}: {stats}")

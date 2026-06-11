# problem: records of occupancy data by station is too dense and will be very heavy during run time
# solution: condense existing files to lightweight "transactions"

# this python file condenses the dense folders of occupancy data and
# rather records the existing data based on 1) initial state at midnight
# and 2) each change in the station. Any state that's the same as previous
# state will be ignored
import os
import csv
import json
from datetime import datetime
from collections import defaultdict

script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
BASE_PATH = script_dir          # "Occupancy data" directory
OUTPUT_PATH = os.path.join(root_dir, 'Condensed Occupancy Data')

OUTPUT_FIELDS = [
    'Date Time', 'Station ID', 'Expected Station Size', 'Total Docks Installed',
    'Number of Faulty Docks', 'Total Bikes At Station Per Model',
    'Number of Available Bikes Per Model', 'Number of Inoperative Bikes Per Model',
    'Geofence Occupancy Ratio', 'Geofence Capacity', 'Geofence Total Bikes',
    'Geofence Available Bikes', 'Geofence Operative Bikes', 'Geofence Inoperative Bikes',
    'Station Groups', 'Station Cluster', 'Station Crown'
]

STATE_FIELDS = OUTPUT_FIELDS[2:]  # everything except Date Time and Station ID

# 1) Collect all "Week of ..." folders, ignore "Bedford and Memory - all"
weekly_folders = sorted([
    f for f in os.listdir(BASE_PATH)
    if f.startswith('Week of ')
])

print(f"Found {len(weekly_folders)} weekly folders")

# 2) Read every CSV, group rows by station ID
station_rows = defaultdict(list)
station_names = defaultdict(set)
seen = set()  # deduplicate by (station_id, datetime)

for folder in weekly_folders:
    folder_path = os.path.join(BASE_PATH, folder)
    csv_files = sorted([f for f in os.listdir(folder_path) if f.endswith('.csv')])
    for filename in csv_files:
        filepath = os.path.join(folder_path, filename)
        # files are encoded in UTF-16 LE (no BOM)
        with open(filepath, encoding='utf-16-le') as f:
            reader = csv.DictReader(f)
            for row in reader:
                station_id = row['Station ID'].strip()
                dt_str = row['Date Time'].strip()
                key = (station_id, dt_str)
                if key in seen:
                    continue
                seen.add(key)
                station_rows[station_id].append(row)
                name = row.get('Station Name', '').strip()
                if name:
                    station_names[station_id].add(name)

print(f"Found {len(station_rows)} stations across all weeks")

os.makedirs(OUTPUT_PATH, exist_ok=True)

# 3 & 4) For each station: sort chronologically, keep initial midnight state
#        and every row where any state field changed from the last kept row
def station_sort_key(sid):
    return int(sid) if sid.isdigit() else sid

for station_id in sorted(station_rows, key=station_sort_key):
    rows = station_rows[station_id]
    rows.sort(key=lambda r: r['Date Time'].strip())

    condensed = []
    last_date = None
    last_state = None

    for row in rows:
        dt_str = row['Date Time'].strip()
        try:
            dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
        current_date = dt.date()
        current_state = {f: row.get(f, '').strip() for f in STATE_FIELDS}

        # always record the first entry of a new calendar day (midnight baseline)
        # and any entry where station state actually changed
        if current_date != last_date or current_state != last_state:
            out_row = {'Date Time': dt_str, 'Station ID': station_id}
            out_row.update(current_state)
            condensed.append(out_row)
            last_date = current_date
            last_state = current_state

    # 5) Write condensed CSV per station
    out_path = os.path.join(OUTPUT_PATH, f'station {station_id}.csv')
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(condensed)

    print(f"  Station {station_id}: {len(rows):>6} rows -> {len(condensed):>5} condensed")

# Station Name is collapsed into a single JSON mapping station ID -> known names
names_json = {
    sid: sorted(station_names[sid])
    for sid in sorted(station_names, key=station_sort_key)
}
with open(os.path.join(OUTPUT_PATH, 'station_names.json'), 'w', encoding='utf-8') as f:
    json.dump(names_json, f, indent=2)

print(f"\nDone. Output written to: {OUTPUT_PATH}")

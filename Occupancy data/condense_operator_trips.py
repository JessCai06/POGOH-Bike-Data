# problem: the counterfactual ("what would the station look like if staff had
# not intervened") needs per-station operator rebalancing events, but the raw
# operator trips export is one big CSV spanning 2022-2026.
# solution: condense it to per-station bike pickup/dropoff events within the
# occupancy data window, written as one lightweight JSON the dashboard fetches.
#
# Each operator trip moves one bike:
#   start station -> bike picked up  (delta -1)
#   end station   -> bike dropped off (delta +1)
# Output: { station_id: [[epoch_seconds, delta, model], ...] } sorted by time.
import os
import csv
import json
from datetime import datetime
from collections import defaultdict

script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
TRIPS_CSV = os.path.join(root_dir, 'Station Sample Data', 'data-specialist-all-operator-trips.csv')
OUTPUT_PATH = os.path.join(root_dir, 'Condensed Occupancy Data', 'operator_trips.json')

# occupancy snapshots start 2025-11-30; events before that are useless to the chart
WINDOW_START = datetime(2025, 11, 30)


def parse_station(v):
    """Station ids appear as '29' or '29.0'; return canonical string or None."""
    v = (v or '').strip()
    if not v:
        return None
    try:
        return str(int(float(v)))
    except ValueError:
        return None


def parse_dt(v):
    try:
        return datetime.strptime(v.strip(), '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None


events = defaultdict(list)
kept = skipped = 0

with open(TRIPS_CSV, encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        model = (row.get('Bike Model') or '').strip().lower() or 'unknown'
        for sid_field, dt_field, delta in (
            ('Start Station Id', 'Start Date', -1),
            ('End Station Id', 'End Date', +1),
        ):
            sid = parse_station(row.get(sid_field))
            dt = parse_dt(row.get(dt_field, ''))
            if sid is None or dt is None or dt < WINDOW_START:
                skipped += 1
                continue
            events[sid].append([int(dt.timestamp()), delta, model])
            kept += 1

for sid in events:
    events[sid].sort(key=lambda e: e[0])

out = {sid: events[sid] for sid in sorted(events, key=lambda s: int(s))}
with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(out, f, separators=(',', ':'))

print(f"Kept {kept} events across {len(out)} stations ({skipped} outside window/unparsed)")
print(f"Output written to: {OUTPUT_PATH}")

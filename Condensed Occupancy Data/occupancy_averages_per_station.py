# Builds two summary files describing each station's typical occupancy:
#   occupancy_by_hour.json  -> hour-of-day patterns  (24-value arrays, hour 0..23)
#   occupancy_by_weekday.json -> day-of-week patterns ( 7-value arrays, Mon..Sun)
#
# "Occupancy" is the station occupancy ratio = total bikes at station / total
# docks installed (the same ratio the raw export calls "Station Occupancy Ratio").
#
# Because the condensed CSVs only record state *changes*, naively averaging the
# rows would over-weight busy hours. Instead we rebuild each station's occupancy
# as a step function (each reading holds until the next) and re-sample it once
# per hour on the hour. A sample is dropped if the most recent reading is more
# than 24h stale, so gaps in coverage don't inject phantom values.
#
#   hour-of-day:  each day contributes the value sampled at HH:00 to bucket HH
#   day-of-week:  each day contributes its mean occupancy to that weekday bucket
import os
import csv
import json
import re
from datetime import datetime, timedelta
from collections import defaultdict

script_dir = os.path.dirname(os.path.abspath(__file__))   # "Condensed Occupancy Data"
HOUR_OUT = os.path.join(script_dir, 'occupancy_by_hour.json')
WEEKDAY_OUT = os.path.join(script_dir, 'occupancy_by_weekday.json')

MAX_STALE = timedelta(hours=24)   # drop samples carried this far past the last reading


def station_sort_key(fname):
    m = re.search(r'(\d+)', fname)
    return int(m.group(1)) if m else 1 << 30


def sum_models(s):
    """'fit: 5, efit: 9' -> 14"""
    return sum(int(n) for n in re.findall(r':\s*(\d+)', s or ''))


def percentile(sorted_vals, q):
    """Linear-interpolation percentile (q in 0..1), matching numpy's default."""
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    pos = q * (n - 1)
    lo = int(pos)
    frac = pos - lo
    if lo + 1 < n:
        return sorted_vals[lo] * (1 - frac) + sorted_vals[lo + 1] * frac
    return sorted_vals[lo]


def summarize(buckets, size):
    """buckets: index -> list of values. Returns {mean, Q1, Q3} of length `size`."""
    mean, q1, q3 = [], [], []
    for i in range(size):
        vals = sorted(buckets.get(i, []))
        if vals:
            mean.append(round(sum(vals) / len(vals), 4))
            q1.append(round(percentile(vals, 0.25), 4))
            q3.append(round(percentile(vals, 0.75), 4))
        else:
            mean.append(None)
            q1.append(None)
            q3.append(None)
    return {'mean': mean, 'Q1': q1, 'Q3': q3}


def load_series(path):
    """Return sorted list of (datetime, occupancy_ratio) for one station file."""
    series = []
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            try:
                dt = datetime.strptime(row['Date Time'].strip(), '%Y-%m-%d %H:%M:%S')
            except (ValueError, KeyError):
                continue
            docks = _to_int(row.get('Total Docks Installed'))
            if not docks:
                continue
            total = sum_models(row.get('Total Bikes At Station Per Model', ''))
            series.append((dt, total / docks))
    series.sort(key=lambda x: x[0])
    return series


def _to_int(v):
    try:
        return int(str(v).strip())
    except (ValueError, TypeError):
        return 0


def sample_station(series):
    """Walk the step function hourly; return (hour_buckets, weekday_buckets)."""
    hour_buckets = defaultdict(list)
    weekday_buckets = defaultdict(list)
    if not series:
        return hour_buckets, weekday_buckets

    start = series[0][0].replace(minute=0, second=0, microsecond=0)
    end = series[-1][0]
    idx = 0           # pointer into series; advances as sample time moves forward
    cur_val = None    # occupancy reading currently "in effect"
    cur_dt = None

    t = start
    day_vals = []     # hourly samples accumulated for the current calendar day
    day_date = start.date()

    while t <= end:
        # advance the in-effect reading to the last one at or before t
        while idx < len(series) and series[idx][0] <= t:
            cur_dt, cur_val = series[idx]
            idx += 1

        if t.date() != day_date:
            if day_vals:
                weekday_buckets[day_date.weekday()].append(sum(day_vals) / len(day_vals))
            day_vals = []
            day_date = t.date()

        if cur_val is not None and (t - cur_dt) <= MAX_STALE:
            hour_buckets[t.hour].append(cur_val)
            day_vals.append(cur_val)

        t += timedelta(hours=1)

    if day_vals:
        weekday_buckets[day_date.weekday()].append(sum(day_vals) / len(day_vals))
    return hour_buckets, weekday_buckets


hour_result = {}
weekday_result = {}

station_files = sorted(
    (f for f in os.listdir(script_dir) if f.startswith('station ') and f.endswith('.csv')),
    key=station_sort_key,
)

for fname in station_files:
    sid = re.search(r'(\d+)', fname).group(1)
    series = load_series(os.path.join(script_dir, fname))
    hour_buckets, weekday_buckets = sample_station(series)
    hour_result[sid] = summarize(hour_buckets, 24)
    weekday_result[sid] = summarize(weekday_buckets, 7)
    print(f"  Station {sid}: {len(series):>6} readings summarized")

HOUR_README = ('Per-station hour-of-day occupancy patterns. occupancy ratio = '
               'total bikes / total docks installed. Each station maps to '
               '{mean, Q1, Q3}; every field is a 24-element array indexed by '
               'hour of day (0 = 00:00 .. 23 = 23:00). null = no data for that '
               'hour. Built by occupancy_averages_per_station.py.')

WEEKDAY_README = ('Per-station day-of-week occupancy patterns. occupancy ratio = '
                  'total bikes / total docks installed. Each station maps to '
                  '{mean, Q1, Q3}; every field is a 7-element array indexed by '
                  'weekday (0 = Monday .. 6 = Sunday), using each day\'s mean '
                  'occupancy. null = no data for that weekday. Built by '
                  'occupancy_averages_per_station.py.')

with open(HOUR_OUT, 'w', encoding='utf-8') as f:
    json.dump({'_readme': HOUR_README, 'stations': hour_result}, f, indent=1)

with open(WEEKDAY_OUT, 'w', encoding='utf-8') as f:
    json.dump({'_readme': WEEKDAY_README, 'stations': weekday_result}, f, indent=1)

print(f"\nWrote {HOUR_OUT}")
print(f"Wrote {WEEKDAY_OUT}")

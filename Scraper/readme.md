# POGOH Station Scraper — Implementation Documentation

**What this system does, in one sentence:** Every 5 minutes, a small program checks POGOH's public station-status feed and saves anything that changed to files on the office PC; once a day, those files are backed up to a private online repository — while a log records every run so we can prove when the scraper was (and wasn't) working.

**Audience note:** This document assumes no prior experience with the tools involved. Technical terms are defined the first time they appear.

---

## 1. System Overview

The system is two scheduled jobs sharing one folder:

**Job A — the scraper (every 5 minutes):**
1. **Fetcher** — downloads the current station data from POGOH's feed.
2. **Change detector** — compares the new data against what we last saved, and keeps only what actually changed.
3. **File writer** — appends changed rows to per-station files, organized by week.
4. **Run log** — writes one line per run whether or not anything changed, so gaps in the data can be told apart from gaps in the scraper.

**Job B — the uploader (once a day):**
5. **Uploader** — commits the day's file changes and pushes them to a private GitHub repository as an off-machine backup.

```
Task Scheduler, every 5 min          Task Scheduler, daily (e.g. 23:55)
        │                                     │
        ▼                                     ▼
   scraper.py                            push.py (or a .bat script)
        │                                     │
   1. fetch station_status.json          1. git add -A
   2. compare to last known state        2. git commit -m "data YYYY-MM-DD"
   3. append changes to weekly CSVs      3. git push
   4. write one line to the run log           │
        │                                     ▼
        ▼                                   exits
      exits
```

The program runs, does its job in a few seconds, and exits. It is **not** a program that stays open continuously. This matters: if the program crashes, only one 5-minute cycle is lost, and the next cycle starts fresh. If the PC reboots (e.g. for a Windows Update), the schedule resumes automatically.

---

## 2. The Data Source

**What GBFS is:** GBFS (General Bikeshare Feed Specification) is a standard format that bike-share systems use to publish their live status publicly. POGOH's station status feed lives at:

```
https://pittsburgh.publicbikesystem.net/customer/gbfs/v3.0/station_status
```

**What it contains:** A snapshot of every station *right now* — how many bikes are docked, how many docks are open, how many bikes/docks are disabled, and a breakdown by bike type (FIT, EFIT, ICONIC, CHLOE).

**The critical limitation:** the feed has no memory. It only ever shows the present moment. If nobody saves the snapshots, the history is gone forever. That is the entire reason this scraper exists.

**Fields we care about, per station:**

| Field in the feed | Plain meaning |
|---|---|
| `station_id` | Which station this row describes |
| `num_vehicles_available` | Bikes ready to ride right now |
| `num_vehicles_disabled` | Bikes present but out of service |
| `num_docks_available` | Empty docks a rider could return to |
| `num_docks_disabled` | Docks that are broken/blocked |
| `vehicle_types_available` | The bike count broken down by type (FIT, EFIT, etc.) |
| `is_installed` / `is_renting` / `is_returning` | Whether the station is operational |
| `last_reported` | When the *station itself* last phoned home |

**Timestamp gotcha:** the feed has a top-level `last_updated` (when the feed page was regenerated) and a per-station `last_reported` (when each station last sent data). Stations report independently, so always use `last_reported` for per-station logic. Neither timestamp is used when deciding whether a row "changed" — see Section 4.

---

## 3. The Scheduler (Windows Task Scheduler)

**What Task Scheduler is:** a built-in Windows tool that runs programs on a timetable, like cron on Linux. It works even when nobody is logged in, and it resumes after reboots.

**Why a scheduled task instead of a loop:** an alternative design would be one Python program that runs forever with a "sleep 5 minutes" loop. We deliberately avoid that, because a forever-program dies silently when the PC reboots or the program hits an unexpected error, and nothing restarts it. Task Scheduler restarts us from scratch every 5 minutes no matter what happened last time.

**Configuration (one-time setup):**

1. Open Task Scheduler → Create Task.
2. **General tab:** name it `POGOH GBFS Scraper`. Select *"Run whether user is logged on or not."*
3. **Triggers tab:** New → Daily, recur every 1 day, then check *"Repeat task every: 5 minutes"* for a duration of *"Indefinitely."*
4. **Actions tab:** Start a program →
   - Program: full path to `python.exe` (find it with `where python` in a terminal)
   - Arguments: full path to `scraper.py`
   - Start in: the scraper's folder (so relative file paths work)
5. **Settings tab:** check *"Run task as soon as possible after a scheduled start is missed"* (covers reboots) and *"If the task fails, restart every 1 minute, up to 3 times."*
6. **Power settings (separate, but essential):** Settings → System → Power → set *"When plugged in, put my device to sleep"* to **Never**. A sleeping PC runs no tasks.

---

## 4. The Fetcher and Change Detector

### 4.1 Fetching

The fetch step is a single HTTP request using Python's `requests` library (an "HTTP request" just means: ask a web address for its contents, the same thing a browser does). The response is JSON — a structured text format — which Python turns into ordinary dictionaries and lists.

Two safeguards:

- **Timeout:** the request is given at most ~20 seconds. Without a timeout, a hung network connection would leave the run stuck forever.
- **Failure handling:** if the request fails (network down, server error), we log the failure (Section 6) and exit. We do **not** retry in a loop — the next scheduled run in 5 minutes *is* the retry.

### 4.2 Change detection ("delta" storage)

**The problem it solves:** at 5-minute polling, quiet stations produce identical snapshots for hours, especially overnight. Storing every snapshot means storing mostly duplicates.

**The rule:** for each station, compare the newly fetched values against the last row we stored for that station. If every *occupancy-relevant* field is identical, store nothing. If anything differs, append the new row.

**What counts as a change:** any of the numeric counts (`num_vehicles_available`, `num_docks_available`, disabled counts, the per-type counts) or the operational flags (`is_renting`, etc.).

**What is deliberately ignored:** the timestamps. `last_reported` ticks forward even when nothing about the station changed; including it would make every row look "new" and defeat the whole approach.

**How "last known state" is remembered between runs:** the program keeps a small file, `state.json`, containing the most recent stored values for every station. Each run loads it, compares, appends any changes to the CSVs, and rewrites it. (Re-reading the tail of every CSV each run would work too, but a single state file is simpler and faster.)

**A consequence to understand:** with delta storage, "no rows for 3 hours" is normal for a quiet station. That's why the run log (Section 6) exists — it's the only way to distinguish *nothing changed* from *scraper wasn't running*.

---

## 5. File Layout and the Weekly Per-Station Files

**Format:** plain CSV (comma-separated values — a spreadsheet as plain text, one row per line). CSVs were chosen because the existing occupancy dashboard already reads them directly, they're human-inspectable, and they diff cleanly in GitHub.

**One file per station per week.** Weekly rotation keeps individual files small enough to open comfortably and gives GitHub tidy, bounded files instead of one ever-growing monster per station.

**Folder structure:**

```
pogoh-scraper/
├── scraper.py
├── state.json                  ← last known values per station
├── logs/
│   ├── runlog-2026-W27.csv     ← one line per run (Section 6)
│   └── runlog-2026-W28.csv
└── data/
    ├── station-0001/
    │   ├── 2026-W27.csv
    │   └── 2026-W28.csv
    ├── station-0012/
    │   └── ...
    └── ...
```

**Week naming:** files use ISO week numbers (`2026-W27`), which Python provides via `datetime.date.isocalendar()`. ISO weeks start on Monday. The "rotation" needs no special code: each run simply computes the current week and appends to that filename, creating it (with a header row) if it doesn't exist yet.

**Columns in each station CSV:**

```
fetched_at_utc, last_reported_utc, num_vehicles_available, num_vehicles_disabled,
num_docks_available, num_docks_disabled, is_installed, is_renting, is_returning,
fit_count, efit_count, iconic_count, chloe_count
```

- `fetched_at_utc` is *our* clock: when the scraper saw this state.
- All timestamps are stored in UTC (the universal reference timezone, the same format the feed uses, e.g. `2026-07-04T17:47:43Z`). Storing UTC avoids every daylight-saving headache; convert to Pittsburgh time only when displaying.
- The per-type counts are flattened from the feed's nested list into fixed columns, because CSVs can't hold nested structures and the four types are stable.

---

## 6. The Run Log (Downtime / Sanity Sheet)

**Purpose:** a heartbeat. Every single run writes exactly one line here, *even when nothing changed and even when the fetch failed*. Any missing 5-minute slot in this file means the scraper itself was down — the PC was off, asleep, or the task was broken.

**Location:** `logs/runlog-YYYY-Www.csv`, rotated weekly like the data files.

**Columns:**

```
run_at_utc, status, stations_seen, stations_changed, duration_ms, note
```

| Column | Meaning |
|---|---|
| `run_at_utc` | When this run started |
| `status` | `ok`, `fetch_failed`, `parse_failed`, or `push_failed` |
| `stations_seen` | How many stations were in the feed (a sudden drop is itself a red flag) |
| `stations_changed` | How many stations had a change worth storing |
| `duration_ms` | How long the run took |
| `note` | Error message text, if any |

**How to read it for sanity checking:** healthy operation is one row every ~5 minutes with `status = ok`. A gap between consecutive `run_at_utc` values much larger than 5 minutes = downtime window (its start and length are directly readable from the two rows around the gap). Rows with `fetch_failed` = the scraper was alive but POGOH's feed or the network wasn't. This distinction — *our* downtime vs. *their* downtime — is exactly what an analysis needs before trusting a quiet stretch of data.

---

## 7. GitHub Backup

**What GitHub is, in this context:** an online service for storing *repositories* — version-controlled folders. "Version-controlled" (via a tool called **git**) means every saved checkpoint (**commit**) is kept forever, so the full history of the files is preserved, not just the latest copy. A **private** repository is visible only to accounts you explicitly invite.

**Why we push there:** the office PC is a single point of failure — a dead disk or an IT reimage would erase months of data. Pushing to GitHub daily means the most we can ever lose is one day of data. It also lets other machines and tools (the dispatcher toolbox, the dashboard, your laptop) read the data from anywhere without touching the office machine — GitHub effectively doubles as the project's data-serving layer.

**One-time setup:**

1. Create a private repository (e.g. `pogoh-station-data`) on github.com.
2. Install git on the office PC ([git-scm.com](https://git-scm.com)).
3. Authenticate the PC to GitHub. Recommended: a **fine-grained Personal Access Token (PAT)** — essentially a long password scoped to *only this one repository* with *only* read/write-contents permission. If the token leaks, the blast radius is one data repo. Store it using git's credential manager (installed with git for Windows), not in the script.
4. In the scraper folder: `git init`, `git remote add origin <repo URL>`, add a `.gitignore` if any local-only files emerge, and make the first commit.

**Daily behavior:** the uploader is a *separate* scheduled task (see Section 3 — same setup, but triggered once daily at 23:55 instead of every 5 minutes). It is deliberately kept out of the scraper so that a GitHub problem can never interfere with data collection. All it does is:

```
git add -A
git commit -m "data 2026-07-04"   (exits quietly if nothing changed that day)
git push
```

This can be a tiny Python script (`push.py` using `subprocess`) or even a three-line Windows batch file — there is no logic in it worth a real program. It appends its own line to the run log with status `push_ok` / `push_failed`.

Notes on this design:

- **One commit per day** gives a clean, readable history: each commit is "here is everything that happened on this date," which makes it easy to diff one day against another or check when a given file last changed.
- **Push failures self-heal.** Data is on disk regardless. If tonight's push fails (network blip, GitHub outage, expired credentials), the commit still exists locally, and tomorrow's push carries it along automatically — git queues unpushed commits by design. The only real cost of a failed push is that the off-machine backup is temporarily one day staler.
- **Worst-case data loss** is now bounded by the push cadence: if the office PC's disk died at 23:00, up to ~24 hours of data since the last push would be lost. That's the trade against per-run pushing; it's acceptable for this project, but it's worth knowing the number.
- **Repo size:** delta-filtered CSVs for ~60 stations grow on the order of tens of megabytes per year — far below GitHub's soft limits. Nothing to worry about for the life of this project.
- **`state.json` and `logs/` are committed too.** The run log is arguably the most valuable thing to have off-machine, since it's the evidence of coverage.

---

## 8. Failure Modes — Quick Reference

| Symptom | Likely cause | Where you'd see it |
|---|---|---|
| No run-log rows for a period | PC asleep/off, task disabled, Windows Update reboot window | Gap in `runlog` timestamps |
| `fetch_failed` rows | POGOH feed or office network down | Run log `status` column |
| Runs happening but a station's file never grows | Normal (quiet station) — or station removed from feed | Check `stations_seen` count |
| `push_failed` on consecutive days | GitHub credentials expired (PATs have expiry dates) or firewall change | Run log; fix credentials, backlog pushes itself |
| Repo on GitHub is stale by more than a day | Daily uploader task disabled or failing silently | Compare newest commit date to today |
| Duplicate-looking rows | A field outside the comparison set changed (e.g. a flag flip) | Inspect the two rows' non-timestamp columns |

---

## 9. Design Decisions in One Place

| Decision | Choice | Why |
|---|---|---|
| Run model | Scheduled task, exit each run | Survives reboots/crashes; no babysitting |
| Interval | 5 minutes | Finer resolution than the previous 10-min plan; feed TTL (~29s) easily supports it |
| Change detection | Compare all occupancy fields, ignore timestamps | Avoids storing duplicates; timestamps always tick |
| Storage | CSV, one file per station per week | Dashboard-native, human-readable, bounded file sizes |
| Timezone | UTC everywhere in storage | Matches feed; no DST bugs; convert only at display time |
| Downtime tracking | One run-log row per cycle, no exceptions | Only way to tell "no change" from "not running" |
| Backup | Separate daily task commits + pushes to private GitHub repo | Clean one-commit-per-day history; scraper can't be broken by GitHub issues; ≤1 day max data loss |
| Auth to GitHub | Fine-grained PAT, single-repo scope | Minimal damage if leaked |
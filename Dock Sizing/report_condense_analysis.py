# reports how much space and runtime savings the condensed occupancy data achieves
import os
import csv

script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
ORIGINAL_PATH = os.path.join(root_dir, 'Occupancy data')
CONDENSED_PATH = os.path.join(root_dir, 'Condensed Occupancy Data')


def count_csv_stats(path, encoding, skip_prefix=None):
    """Walk a directory tree and return (total_bytes, total_data_rows, file_count)."""
    total_bytes = 0
    total_rows = 0
    file_count = 0
    for dirpath, _, filenames in os.walk(path):
        for fname in filenames:
            if not fname.endswith('.csv'):
                continue
            if skip_prefix and fname.startswith(skip_prefix):
                continue
            fpath = os.path.join(dirpath, fname)
            total_bytes += os.path.getsize(fpath)
            file_count += 1
            with open(fpath, encoding=encoding, errors='replace') as f:
                reader = csv.reader(f)
                next(reader, None)  # skip header
                total_rows += sum(1 for _ in reader)
    return total_bytes, total_rows, file_count


def fmt_bytes(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


print("Scanning original occupancy data (this may take a moment)...")
orig_bytes, orig_rows, orig_files = count_csv_stats(ORIGINAL_PATH, encoding='utf-16-le')

print("Scanning condensed occupancy data...")
cond_bytes, cond_rows, cond_files = count_csv_stats(CONDENSED_PATH, encoding='utf-8')

row_reduction = (1 - cond_rows / orig_rows) * 100 if orig_rows else 0
size_reduction = (1 - cond_bytes / orig_bytes) * 100 if orig_bytes else 0
row_speedup = orig_rows / cond_rows if cond_rows else float('inf')

print()
print("=" * 52)
print("  OCCUPANCY DATA CONDENSATION REPORT")
print("=" * 52)
print(f"  {'':30s} {'Original':>9}  {'Condensed':>9}")
print(f"  {'-'*50}")
print(f"  {'CSV files':30s} {orig_files:>9,}  {cond_files:>9,}")
print(f"  {'Total data rows':30s} {orig_rows:>9,}  {cond_rows:>9,}")
print(f"  {'Disk size':30s} {fmt_bytes(orig_bytes):>9}  {fmt_bytes(cond_bytes):>9}")
print(f"  {'-'*50}")
print(f"  {'Row reduction':30s} {row_reduction:>8.1f}%")
print(f"  {'Disk size reduction':30s} {size_reduction:>8.1f}%")
print(f"  {'Runtime speedup (row iteration)':30s} {row_speedup:>7.1f}x")
print("=" * 52)
print()
print(f"  Rows saved:  {orig_rows - cond_rows:,}  ({row_reduction:.1f}% fewer rows to iterate)")
print(f"  Space saved: {fmt_bytes(orig_bytes - cond_bytes)}  ({size_reduction:.1f}% smaller on disk)")
print()

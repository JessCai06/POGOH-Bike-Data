"""
Convert xlsx files to csv.

Usage:
    python xlsx_to_csv.py                          # convert all xlsx in default folder
    python xlsx_to_csv.py file.xlsx                # convert a specific file
    python xlsx_to_csv.py --folder "some/path"     # convert all xlsx in a given folder
    python xlsx_to_csv.py file.xlsx --out "output" # write csv to a specific output folder
    python xlsx_to_csv.py --sheet Sheet2           # target a specific sheet (default: first sheet)
"""

import argparse
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas is required: pip install pandas openpyxl")


DEFAULT_FOLDER = Path(__file__).parent / "Station Sample Data"


def convert(xlsx_path: Path, out_dir: Path, sheet: str | int) -> Path:
    df = pd.read_excel(xlsx_path, sheet_name=sheet, engine="openpyxl")
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / (xlsx_path.stem + ".csv")
    df.to_csv(csv_path, index=False)
    return csv_path


def main():
    parser = argparse.ArgumentParser(description="Convert xlsx files to csv.")
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to a specific xlsx file (optional — omit to convert all files in --folder).",
    )
    parser.add_argument(
        "--folder",
        default=str(DEFAULT_FOLDER),
        help=f"Folder to scan for xlsx files (default: {DEFAULT_FOLDER}).",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output folder for csv files (default: same folder as each source file).",
    )
    parser.add_argument(
        "--sheet",
        default=0,
        help="Sheet name or 0-based index to convert (default: 0, i.e. first sheet).",
    )
    args = parser.parse_args()

    # Resolve sheet: keep as int if numeric, otherwise use as string name
    try:
        sheet = int(args.sheet)
    except ValueError:
        sheet = args.sheet

    if args.file:
        xlsx_path = Path(args.file)
        if not xlsx_path.exists():
            sys.exit(f"File not found: {xlsx_path}")
        out_dir = Path(args.out) if args.out else xlsx_path.parent
        csv_path = convert(xlsx_path, out_dir, sheet)
        print(f"Converted: {csv_path}")
    else:
        folder = Path(args.folder)
        if not folder.exists():
            sys.exit(f"Folder not found: {folder}")
        xlsx_files = sorted(folder.glob("*.xlsx"))
        if not xlsx_files:
            sys.exit(f"No xlsx files found in: {folder}")
        for xlsx_path in xlsx_files:
            out_dir = Path(args.out) if args.out else xlsx_path.parent
            csv_path = convert(xlsx_path, out_dir, sheet)
            print(f"Converted: {csv_path}")


if __name__ == "__main__":
    main()

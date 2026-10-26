#!/usr/bin/env python
"""AAPM data validation script.

Scans a directory for DICOM series and outputs a table of found series.
Exits with code 2 if the directory doesn't exist or has no series.

Usage:
    python scripts/check_aapm.py <directory>
    python scripts/check_aapm.py C:/path/to/AAPM data
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from visualization.loaders.dicom import scan_series


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_aapm.py <directory>")
        print("Scans a directory for DICOM series and outputs a table.")
        sys.exit(2)

    directory = Path(sys.argv[1])

    # Check directory exists
    if not directory.exists():
        print(f"Error: Directory does not exist: {directory}", file=sys.stderr)
        sys.exit(2)

    if not directory.is_dir():
        print(f"Error: Not a directory: {directory}", file=sys.stderr)
        sys.exit(2)

    # Scan for series
    try:
        series_list = scan_series(directory)
    except ValueError as e:
        print(f"Error: No DICOM series found in {directory}", file=sys.stderr)
        sys.exit(2)

    # Print table header
    print(f"{'Patient ID':<15} {'Series Description':<30} {'Slices':<10} {'Dose Class'}")
    print("-" * 70)

    # Print each series
    unknown_count = 0
    for s in series_list:
        patient = s.patient_id or "Unknown"
        desc = s.series_description or "Unknown"
        slices = str(s.n_slices)
        dose = s.dose_class

        if dose == "unknown":
            unknown_count += 1

        print(f"{patient:<15} {desc:<30} {slices:<10} {dose}")

    # Warning if all series are unknown
    if unknown_count == len(series_list):
        print(f"\nWarning: All {len(series_list)} series have unknown dose classification", file=sys.stderr)

    print(f"\nTotal: {len(series_list)} series(s)")


if __name__ == "__main__":
    main()

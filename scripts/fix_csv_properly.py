#!/usr/bin/env python3
"""
Fix CSV by manually parsing and reconstructing with proper field boundaries.
"""

import csv
import sys
from pathlib import Path


def fix_csv_properly(input_path: Path, output_path: Path):
    """
    Fix CSV by treating everything after the 5th comma as the Description field.
    Expected format: Name,Address,City,State,ZIP,Description (with possible commas)
    """
    fixed_rows = []

    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        line = line.rstrip('\n\r')

        if i == 0:  # Header
            fixed_rows.append(['Name', 'Address', 'City', 'State', 'ZIP', 'Description'])
            continue

        if not line:  # Skip empty lines
            continue

        # Split on comma, but only take first 5 commas as field separators
        # Everything after the 5th comma is the Description
        parts = line.split(',')

        if len(parts) >= 6:
            # First 5 fields
            name = parts[0].strip()
            address = parts[1].strip()
            city = parts[2].strip()
            state = parts[3].strip()
            zip_code = parts[4].strip()

            # Everything else is the description (join back with commas)
            description = ','.join(parts[5:]).strip()

            fixed_rows.append([name, address, city, state, zip_code, description])
        else:
            print(f"Warning: Line {i+1} doesn't have enough fields: {line}")

    # Write with proper quoting
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        for row in fixed_rows:
            writer.writerow(row)

    print(f"✓ Fixed {len(fixed_rows)-1} sales")
    print(f"✓ Written to: {output_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python fix_csv_properly.py <input_csv> [output_csv]")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    fix_csv_properly(input_path, output_path)


if __name__ == "__main__":
    main()

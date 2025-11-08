#!/usr/bin/env python3
"""
Verify that KML output matches the source markdown and CSV data.
"""

import csv
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET


def parse_markdown_details(markdown_path: Path):
    """Extract all sales details from markdown."""
    sales = []

    with open(markdown_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by section headers
    sections = re.split(r'###\s+(\d+)\.\s+\[([^\]]+)\]\((https://[^\)]+)\)', content)

    # Process in groups of 4 (text before, number, name, url)
    for i in range(1, len(sections), 4):
        if i + 3 <= len(sections):
            number = sections[i]
            name = sections[i + 1]
            url = sections[i + 2]
            details = sections[i + 3]

            # Extract address
            addr_match = re.search(r'\*\*Address:\*\*\s+([^\n]+)', details)
            address = addr_match.group(1).strip() if addr_match else None

            sales.append({
                'number': int(number),
                'name': name,
                'url': url,
                'address': address
            })

    return sales


def parse_csv_data(csv_path: Path):
    """Extract all sales from CSV."""
    sales = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Name']:
                full_address = f"{row['Address']}, {row['City']}, {row['State']} {row['ZIP']}"
                sales.append({
                    'name': row['Name'],
                    'address': full_address,
                    'description': row['Description']
                })

    return sales


def parse_kml_data(kml_path: Path):
    """Extract all placemarks from KML."""
    tree = ET.parse(kml_path)
    root = tree.getroot()

    # Handle KML namespace
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}

    placemarks = []
    for placemark in root.findall('.//kml:Placemark', ns):
        name_elem = placemark.find('kml:name', ns)
        desc_elem = placemark.find('kml:description', ns)
        addr_elem = placemark.find('kml:address', ns)

        name = name_elem.text if name_elem is not None else None
        description = desc_elem.text if desc_elem is not None else None
        address = addr_elem.text if addr_elem is not None else None

        # Extract URL from description CDATA
        url = None
        if description:
            url_match = re.search(r'href="(https://[^"]+)"', description)
            if url_match:
                url = url_match.group(1)

        placemarks.append({
            'name': name,
            'address': address,
            'url': url,
            'description': description
        })

    return placemarks


def normalize_address(addr):
    """Normalize address for comparison."""
    if not addr:
        return ""
    return ' '.join(addr.lower().split()).replace(',', '')


def verify_kml(csv_path: Path, markdown_path: Path, kml_path: Path):
    """Perform comprehensive verification."""
    print("=" * 80)
    print("COMPREHENSIVE KML VERIFICATION")
    print("=" * 80)
    print()

    # Load all data
    print("Loading data files...")
    csv_sales = parse_csv_data(csv_path)
    md_sales = parse_markdown_details(markdown_path)
    kml_placemarks = parse_kml_data(kml_path)

    print(f"  CSV sales: {len(csv_sales)}")
    print(f"  Markdown sales: {len(md_sales)}")
    print(f"  KML placemarks: {len(kml_placemarks)}")
    print()

    # Check 1: Count verification
    print("CHECK 1: Count Verification")
    print("-" * 80)
    if len(csv_sales) == len(kml_placemarks):
        print(f"✓ PASS: KML has same count as CSV ({len(csv_sales)} sales)")
    else:
        print(f"✗ FAIL: Count mismatch - CSV: {len(csv_sales)}, KML: {len(kml_placemarks)}")

    if len(md_sales) == len(kml_placemarks):
        print(f"✓ PASS: KML has same count as markdown ({len(md_sales)} sales)")
    else:
        print(f"✗ FAIL: Count mismatch - Markdown: {len(md_sales)}, KML: {len(kml_placemarks)}")
    print()

    # Check 2: All CSV sales present in KML
    print("CHECK 2: CSV → KML Mapping")
    print("-" * 80)
    csv_in_kml = 0
    csv_missing = []

    for csv_sale in csv_sales:
        found = False
        for kml_pm in kml_placemarks:
            if normalize_address(csv_sale['address']) == normalize_address(kml_pm['address']):
                found = True
                csv_in_kml += 1
                break

        if not found:
            csv_missing.append(csv_sale['name'])

    print(f"✓ Found {csv_in_kml}/{len(csv_sales)} CSV sales in KML")
    if csv_missing:
        print(f"✗ Missing from KML:")
        for name in csv_missing:
            print(f"  - {name}")
    print()

    # Check 3: URL verification
    print("CHECK 3: URL Verification")
    print("-" * 80)

    # Build markdown URL lookup by address
    md_url_by_addr = {}
    for md_sale in md_sales:
        addr_key = normalize_address(md_sale['address'])
        md_url_by_addr[addr_key] = md_sale['url']

    urls_matched = 0
    urls_missing = 0
    url_mismatches = []

    for kml_pm in kml_placemarks:
        addr_key = normalize_address(kml_pm['address'])
        expected_url = md_url_by_addr.get(addr_key)

        if expected_url:
            if kml_pm['url'] == expected_url:
                urls_matched += 1
            elif kml_pm['url']:
                url_mismatches.append({
                    'name': kml_pm['name'],
                    'expected': expected_url,
                    'actual': kml_pm['url']
                })
            else:
                urls_missing += 1
        else:
            # URL not in markdown (shouldn't happen if counts match)
            pass

    print(f"✓ Correct URLs: {urls_matched}/{len(kml_placemarks)}")
    if urls_missing > 0:
        print(f"✗ Missing URLs: {urls_missing}")
    if url_mismatches:
        print(f"✗ Mismatched URLs: {len(url_mismatches)}")
        for mm in url_mismatches[:5]:  # Show first 5
            print(f"  {mm['name']}:")
            print(f"    Expected: {mm['expected']}")
            print(f"    Actual: {mm['actual']}")
    print()

    # Check 4: Address verification
    print("CHECK 4: Address Verification")
    print("-" * 80)

    addr_matches = 0
    addr_mismatches = []

    for csv_sale in csv_sales:
        for kml_pm in kml_placemarks:
            if csv_sale['name'] == kml_pm['name']:
                if normalize_address(csv_sale['address']) == normalize_address(kml_pm['address']):
                    addr_matches += 1
                else:
                    addr_mismatches.append({
                        'name': csv_sale['name'],
                        'csv_addr': csv_sale['address'],
                        'kml_addr': kml_pm['address']
                    })
                break

    print(f"✓ Matching addresses: {addr_matches}/{len(csv_sales)}")
    if addr_mismatches:
        print(f"✗ Address mismatches: {len(addr_mismatches)}")
        for am in addr_mismatches[:5]:  # Show first 5
            print(f"  {am['name']}:")
            print(f"    CSV: {am['csv_addr']}")
            print(f"    KML: {am['kml_addr']}")
    print()

    # Check 5: Sample detailed inspection
    print("CHECK 5: Sample Detailed Inspection (First 3 Sales)")
    print("-" * 80)

    for i in range(min(3, len(md_sales))):
        md_sale = md_sales[i]
        print(f"\nSale #{md_sale['number']}: {md_sale['name']}")
        print(f"  MD Address: {md_sale['address']}")
        print(f"  MD URL: {md_sale['url']}")

        # Find in CSV
        csv_match = None
        for csv_sale in csv_sales:
            if normalize_address(md_sale['address']) in normalize_address(csv_sale['address']):
                csv_match = csv_sale
                break

        if csv_match:
            print(f"  CSV Name: {csv_match['name']}")
            print(f"  CSV Address: {csv_match['address']}")
        else:
            print("  ✗ NOT FOUND IN CSV")

        # Find in KML
        kml_match = None
        for kml_pm in kml_placemarks:
            if normalize_address(md_sale['address']) == normalize_address(kml_pm['address']):
                kml_match = kml_pm
                break

        if kml_match:
            print(f"  KML Name: {kml_match['name']}")
            print(f"  KML Address: {kml_match['address']}")
            print(f"  KML URL: {kml_match['url']}")

            # Verify URL matches
            if kml_match['url'] == md_sale['url']:
                print("  ✓ URL MATCHES")
            else:
                print("  ✗ URL MISMATCH")
        else:
            print("  ✗ NOT FOUND IN KML")

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    total_checks = 4
    passed_checks = 0

    if len(csv_sales) == len(kml_placemarks):
        passed_checks += 1
    if csv_in_kml == len(csv_sales):
        passed_checks += 1
    if urls_matched == len(kml_placemarks):
        passed_checks += 1
    if addr_matches == len(csv_sales):
        passed_checks += 1

    print(f"Checks passed: {passed_checks}/{total_checks}")

    if passed_checks == total_checks:
        print("\n✓ ALL CHECKS PASSED - KML data is accurate!")
        return 0
    else:
        print("\n✗ SOME CHECKS FAILED - Please review issues above")
        return 1


def main():
    if len(sys.argv) < 4:
        print("Usage: python verify_kml.py <csv_file> <markdown_file> <kml_file>")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    markdown_path = Path(sys.argv[2])
    kml_path = Path(sys.argv[3])

    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        sys.exit(1)

    if not markdown_path.exists():
        print(f"Error: Markdown file not found: {markdown_path}")
        sys.exit(1)

    if not kml_path.exists():
        print(f"Error: KML file not found: {kml_path}")
        sys.exit(1)

    try:
        return verify_kml(csv_path, markdown_path, kml_path)
    except Exception as e:
        print(f"Error during verification: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())

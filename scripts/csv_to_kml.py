#!/usr/bin/env python3
"""
Convert estate sale CSV to KML format with hyperlinked titles.

This script reads a CSV file containing estate sale information and a markdown
file with detailed listings, then generates a KML file with placemarks for each
sale. The titles in the KML are hyperlinked to the estate sale websites.
"""

import csv
import re
import sys
from pathlib import Path
from typing import Dict, List
from xml.sax.saxutils import escape


def parse_markdown_urls(markdown_path: Path) -> Dict[str, str]:
    """
    Parse markdown file to extract URLs mapped by address.

    Args:
        markdown_path: Path to the markdown details file

    Returns:
        Dictionary mapping normalized addresses to their URLs
    """
    address_urls = {}

    with open(markdown_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by section headers
    sections = re.split(r'###\s+\d+\.', content)

    for section in sections[1:]:  # Skip first empty section
        # Extract URL from markdown link [text](url)
        url_match = re.search(r'\]\((https://[^\)]+)\)', section)
        if url_match:
            url = url_match.group(1)
            # Extract address from **Address:** line
            addr_match = re.search(r'\*\*Address:\*\*\s+([^\n]+)', section)
            if addr_match:
                address = addr_match.group(1).strip()
                # Normalize address for matching (lowercase, remove extra spaces/commas)
                address_key = ' '.join(address.lower().split()).replace(',', '')
                address_urls[address_key] = url

    return address_urls


def read_csv_data(csv_path: Path) -> List[Dict[str, str]]:
    """
    Read estate sale data from CSV file.

    Args:
        csv_path: Path to the CSV file

    Returns:
        List of dictionaries containing sale data
    """
    sales = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Name']:  # Skip empty rows
                sales.append(row)

    return sales


def find_url_for_sale(sale: Dict[str, str], address_urls: Dict[str, str]) -> str:
    """
    Find the URL for a sale by matching its address.

    Args:
        sale: Sale data dictionary with address fields
        address_urls: Dictionary of URLs mapped by address

    Returns:
        URL if found, empty string otherwise
    """
    # Build full address from CSV fields
    full_address = f"{sale['Address']}, {sale['City']}, {sale['State']} {sale['ZIP']}"
    # Normalize for matching
    address_key = ' '.join(full_address.lower().split()).replace(',', '')

    # Try exact match
    if address_key in address_urls:
        return address_urls[address_key]

    # Try just street address (sometimes city/state/zip format differs)
    street_key = ' '.join(sale['Address'].lower().split())
    for addr, url in address_urls.items():
        if street_key in addr:
            return url

    return ""


def create_kml_header() -> str:
    """Create KML header with proper XML declaration and styling."""
    return '''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Estate Sales</name>
    <description>Estate sale locations with details</description>

    <Style id="estateIcon">
      <IconStyle>
        <Icon>
          <href>http://maps.google.com/mapfiles/kml/paddle/red-circle.png</href>
        </Icon>
      </IconStyle>
    </Style>
'''


def create_placemark(sale: Dict[str, str], url: str) -> str:
    """
    Create a KML placemark for an estate sale.

    Args:
        sale: Dictionary containing sale data
        url: URL to the estate sale website

    Returns:
        KML placemark string
    """
    # Escape special XML characters
    name = escape(sale['Name'])
    description = escape(sale['Description'])
    address = escape(f"{sale['Address']}, {sale['City']}, {sale['State']} {sale['ZIP']}")

    # Parse description for times and notes
    # Description format: "Sat 10am-4pm, Sun 11am-4pm | Park on one side of street"
    desc_parts = description.split('|')
    times = desc_parts[0].strip() if len(desc_parts) > 0 else description
    notes = desc_parts[1].strip() if len(desc_parts) > 1 else ""

    # Create CDATA section for HTML content in description
    if url:
        html_description = f'''<![CDATA[
<h3><a href="{url}" target="_blank">{name}</a></h3>
<p><strong>Hours:</strong> {times}</p>'''
        if notes:
            html_description += f'''
<p><strong>Notes:</strong> {notes}</p>'''
        html_description += '''
]]>'''
    else:
        html_description = f'''<![CDATA[
<h3>{name}</h3>
<p><strong>Hours:</strong> {times}</p>'''
        if notes:
            html_description += f'''
<p><strong>Notes:</strong> {notes}</p>'''
        html_description += '''
]]>'''

    placemark = f'''    <Placemark>
      <name>{name}</name>
      <description>{html_description}</description>
      <styleUrl>#estateIcon</styleUrl>
      <address>{address}</address>
    </Placemark>
'''

    return placemark


def create_kml_footer() -> str:
    """Create KML footer."""
    return '''  </Document>
</kml>
'''


def convert_csv_to_kml(csv_path: Path, markdown_path: Path, output_path: Path) -> None:
    """
    Convert CSV estate sale data to KML format with hyperlinked titles.

    Args:
        csv_path: Path to input CSV file
        markdown_path: Path to markdown details file
        output_path: Path to output KML file
    """
    print(f"Reading URLs from {markdown_path}...")
    address_urls = parse_markdown_urls(markdown_path)
    print(f"Found {len(address_urls)} URLs in markdown file")

    print(f"Reading sales data from {csv_path}...")
    sales = read_csv_data(csv_path)
    print(f"Found {len(sales)} sales in CSV file")

    print(f"Generating KML file at {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(create_kml_header())

        matched = 0
        for sale in sales:
            url = find_url_for_sale(sale, address_urls)
            if url:
                matched += 1
            f.write(create_placemark(sale, url))

        f.write(create_kml_footer())

    print(f"✓ KML file created successfully!")
    print(f"  - Total sales: {len(sales)}")
    print(f"  - Matched URLs: {matched}")
    print(f"  - Output: {output_path}")


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: python csv_to_kml.py <csv_file> <markdown_file> [output_file]")
        print("\nExample:")
        print("  python csv_to_kml.py Estate_Sales.csv Estate_Sales_Details.md Estate_Sales.kml")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    markdown_path = Path(sys.argv[2])

    if len(sys.argv) > 3:
        output_path = Path(sys.argv[3])
    else:
        # Default output path
        output_path = csv_path.with_suffix('.kml')

    # Validate input files
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        sys.exit(1)

    if not markdown_path.exists():
        print(f"Error: Markdown file not found: {markdown_path}")
        sys.exit(1)

    try:
        convert_csv_to_kml(csv_path, markdown_path, output_path)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

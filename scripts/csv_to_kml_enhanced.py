#!/usr/bin/env python3
"""
Enhanced estate sale CSV to KML converter with nested folders and filtering.

This script creates a KML file with:
- Nested folder organization (Day -> Discount Level)
- Snippet previews for quick info
- Different icon styles for discount levels
- Duplicate placemarks for multi-day sales (toggle by day in Google Maps)
"""

import csv
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set
from xml.sax.saxutils import escape


# Icon URLs for different discount levels
ICON_STYLES = {
    '50%': 'http://maps.google.com/mapfiles/kml/paddle/red-stars.png',
    '25-30%': 'http://maps.google.com/mapfiles/kml/paddle/orange-circle.png',
    'no_discount': 'http://maps.google.com/mapfiles/kml/paddle/blu-circle.png',
}


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


def parse_days(description: str) -> Set[str]:
    """
    Extract which days a sale is open from the description.

    Args:
        description: Sale description with hours info

    Returns:
        Set of days: 'Friday', 'Saturday', 'Sunday'
    """
    days = set()
    desc_lower = description.lower()

    if re.search(r'\bfri\b', desc_lower):
        days.add('Friday')
    if re.search(r'\bsat\b', desc_lower):
        days.add('Saturday')
    if re.search(r'\bsun\b', desc_lower):
        days.add('Sunday')

    return days


def parse_discount_level(description: str) -> str:
    """
    Extract the maximum discount level from the description.

    Args:
        description: Sale description with discount info

    Returns:
        Discount level: '50%', '25-30%', or 'no_discount'
    """
    # Check for 50% off
    if re.search(r'50%\s*off', description, re.IGNORECASE):
        return '50%'

    # Check for 25-30% off
    if re.search(r'(25|30)%\s*off', description, re.IGNORECASE):
        return '25-30%'

    return 'no_discount'


def get_discount_for_day(description: str, day: str) -> str:
    """
    Get the discount level specifically for a given day.

    Args:
        description: Sale description with hours/discount info
        day: Day name ('Friday', 'Saturday', 'Sunday')

    Returns:
        Discount level for that specific day
    """
    # Day abbreviations
    day_abbr = {
        'Friday': r'\bFri\b',
        'Saturday': r'\bSat\b',
        'Sunday': r'\bSun\b'
    }

    # Find the line containing this day
    lines = description.split(',')
    for line in lines:
        if re.search(day_abbr[day], line, re.IGNORECASE):
            # Check for discount on this specific day
            if re.search(r'50%\s*off', line, re.IGNORECASE):
                return '50%'
            if re.search(r'(25|30)%\s*off', line, re.IGNORECASE):
                return '25-30%'

    # If no specific discount for this day, return overall discount
    return parse_discount_level(description)


def create_snippet(description: str, days: Set[str]) -> str:
    """
    Create a short snippet for list view.

    Args:
        description: Full sale description
        days: Set of days the sale is open

    Returns:
        Snippet text (concise info)
    """
    # Get discount level
    discount = parse_discount_level(description)
    discount_text = ""
    if discount == '50%':
        discount_text = "50% OFF | "
    elif discount == '25-30%':
        discount_text = "25-30% OFF | "

    # Format days
    day_abbr = []
    if 'Friday' in days:
        day_abbr.append('Fri')
    if 'Saturday' in days:
        day_abbr.append('Sat')
    if 'Sunday' in days:
        day_abbr.append('Sun')

    days_text = ', '.join(day_abbr)

    return f"{discount_text}{days_text}"


def create_kml_header() -> str:
    """Create KML header with proper XML declaration and styling."""
    header = '''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Estate Sales</name>
    <description>Estate sale locations organized by day and discount level</description>

'''

    # Add icon styles
    for style_name, icon_url in ICON_STYLES.items():
        header += f'''    <Style id="{style_name.replace('%', 'pct').replace('-', '_')}">
      <IconStyle>
        <Icon>
          <href>{icon_url}</href>
        </Icon>
      </IconStyle>
    </Style>
'''

    return header


def create_placemark(sale: Dict[str, str], url: str, discount_level: str) -> str:
    """
    Create a KML placemark for an estate sale.

    Args:
        sale: Dictionary containing sale data
        url: URL to the estate sale website
        discount_level: Discount level for style selection

    Returns:
        KML placemark string
    """
    # Escape special XML characters
    name = escape(sale['Name'])
    description = escape(sale['Description'])
    address = escape(f"{sale['Address']}, {sale['City']}, {sale['State']} {sale['ZIP']}")

    # Parse description for times and notes
    desc_parts = description.split('|')
    times = desc_parts[0].strip() if len(desc_parts) > 0 else description
    notes = desc_parts[1].strip() if len(desc_parts) > 1 else ""

    # Get days for snippet
    days = parse_days(sale['Description'])
    snippet = create_snippet(sale['Description'], days)

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

    # Determine style based on discount level
    style_id = discount_level.replace('%', 'pct').replace('-', '_')

    placemark = f'''      <Placemark>
        <name>{name}</name>
        <Snippet maxLines="1">{snippet}</Snippet>
        <description>{html_description}</description>
        <styleUrl>#{style_id}</styleUrl>
        <address>{address}</address>
      </Placemark>
'''

    return placemark


def organize_sales_by_day_and_discount(sales: List[Dict[str, str]], address_urls: Dict[str, str]) -> Dict[str, Dict[str, List[Tuple[Dict[str, str], str]]]]:
    """
    Organize sales into nested structure: Day -> Discount Level -> Sales list.

    Args:
        sales: List of sale dictionaries
        address_urls: Dictionary of URLs by address

    Returns:
        Nested dictionary: {day: {discount_level: [(sale, url)]}}
    """
    # Initialize structure
    organization = {
        'Friday': {'50%': [], '25-30%': [], 'no_discount': []},
        'Saturday': {'50%': [], '25-30%': [], 'no_discount': []},
        'Sunday': {'50%': [], '25-30%': [], 'no_discount': []}
    }

    for sale in sales:
        url = find_url_for_sale(sale, address_urls)
        days = parse_days(sale['Description'])

        # Add sale to each day it's open
        for day in days:
            if day in organization:
                # Get discount level for this specific day
                discount = get_discount_for_day(sale['Description'], day)
                # Default to no_discount if not recognized
                if discount not in organization[day]:
                    discount = 'no_discount'
                organization[day][discount].append((sale, url))

    return organization


def create_kml_footer() -> str:
    """Create KML footer."""
    return '''  </Document>
</kml>
'''


def convert_csv_to_kml_enhanced(csv_path: Path, markdown_path: Path, output_path: Path) -> None:
    """
    Convert CSV estate sale data to enhanced KML format with nested folders.

    Args:
        csv_path: Path to input CSV file
        markdown_path: Path to markdown details file
        output_path: Path to output KML file
    """
    print(f"Reading URLs from {markdown_path}...")
    address_urls = parse_markdown_urls(markdown_path)
    print(f"Found {len(address_urls)} URLs in markdown file")

    print(f"Reading sales data from {csv_path}...")
    sales = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Name']:  # Skip empty rows
                sales.append(row)
    print(f"Found {len(sales)} sales in CSV file")

    print(f"Organizing sales by day and discount level...")
    organization = organize_sales_by_day_and_discount(sales, address_urls)

    print(f"Generating enhanced KML file at {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(create_kml_header())

        # Create nested folders: Day -> Discount Level
        for day in ['Friday', 'Saturday', 'Sunday']:
            f.write(f'    <Folder>\n')
            f.write(f'      <name>{day} Sales</name>\n')

            for discount_level in ['50%', '25-30%', 'no_discount']:
                sales_list = organization[day][discount_level]

                if sales_list:  # Only create folder if there are sales
                    # Friendly folder name
                    folder_name = {
                        '50%': '50% Off',
                        '25-30%': '25-30% Off',
                        'no_discount': 'No Discount'
                    }[discount_level]

                    f.write(f'      <Folder>\n')
                    f.write(f'        <name>{folder_name}</name>\n')

                    for sale, url in sales_list:
                        f.write(create_placemark(sale, url, discount_level))

                    f.write(f'      </Folder>\n')

            f.write(f'    </Folder>\n')

        f.write(create_kml_footer())

    # Print statistics
    print(f"\n✓ Enhanced KML file created successfully!")
    print(f"  - Output: {output_path}")
    print(f"\nSales by day:")
    for day in ['Friday', 'Saturday', 'Sunday']:
        total = sum(len(organization[day][d]) for d in organization[day])
        print(f"  - {day}: {total} sales")
        for discount in ['50%', '25-30%', 'no_discount']:
            count = len(organization[day][discount])
            if count > 0:
                discount_name = '50% Off' if discount == '50%' else ('25-30% Off' if discount == '25-30%' else 'No Discount')
                print(f"    • {discount_name}: {count}")


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: python csv_to_kml_enhanced.py <csv_file> <markdown_file> [output_file]")
        print("\nExample:")
        print("  python csv_to_kml_enhanced.py Estate_Sales.csv Estate_Sales_Details.md Estate_Sales_Enhanced.kml")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    markdown_path = Path(sys.argv[2])

    if len(sys.argv) > 3:
        output_path = Path(sys.argv[3])
    else:
        # Default output path with _enhanced suffix
        output_path = csv_path.with_stem(csv_path.stem + '_enhanced').with_suffix('.kml')

    # Validate input files
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        sys.exit(1)

    if not markdown_path.exists():
        print(f"Error: Markdown file not found: {markdown_path}")
        sys.exit(1)

    try:
        convert_csv_to_kml_enhanced(csv_path, markdown_path, output_path)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

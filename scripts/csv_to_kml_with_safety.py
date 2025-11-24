#!/usr/bin/env python3
"""
Estate sale CSV to KML converter with neighborhood safety ratings.

Extends the enhanced KML converter to include:
- Neighborhood safety/quality ratings based on ZIP code demographics
- Color-coded pins by neighborhood quality OR discount level
- Safety info in placemark descriptions
- Sorting options by safety rating

Usage:
    python csv_to_kml_with_safety.py <csv> <markdown> [output.kml] [--sort-by-safety]
"""

import csv
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set
from xml.sax.saxutils import escape

# Import neighborhood lookup module
from neighborhood_lookup import (
    get_neighborhood_rating,
    format_rating_for_display,
    get_rating_emoji
)


# Icon URLs for different discount levels
DISCOUNT_ICONS = {
    '50%': 'http://maps.google.com/mapfiles/kml/paddle/red-stars.png',
    '25-30%': 'http://maps.google.com/mapfiles/kml/paddle/orange-circle.png',
    'no_discount': 'http://maps.google.com/mapfiles/kml/paddle/blu-circle.png',
}

# Icon URLs for neighborhood safety ratings
SAFETY_ICONS = {
    'excellent': 'http://maps.google.com/mapfiles/kml/paddle/grn-circle.png',
    'good': 'http://maps.google.com/mapfiles/kml/paddle/ltblu-circle.png',
    'fair': 'http://maps.google.com/mapfiles/kml/paddle/ylw-circle.png',
    'below_average': 'http://maps.google.com/mapfiles/kml/paddle/orange-circle.png',
    'poor': 'http://maps.google.com/mapfiles/kml/paddle/red-circle.png',
}

# Combined icons: safety outer, discount marker
# Format: safety_rating -> discount_level -> icon
COMBINED_ICONS = {
    'excellent': {
        '50%': 'http://maps.google.com/mapfiles/kml/paddle/grn-stars.png',
        '25-30%': 'http://maps.google.com/mapfiles/kml/paddle/grn-diamond.png',
        'no_discount': 'http://maps.google.com/mapfiles/kml/paddle/grn-circle.png',
    },
    'good': {
        '50%': 'http://maps.google.com/mapfiles/kml/paddle/ltblu-stars.png',
        '25-30%': 'http://maps.google.com/mapfiles/kml/paddle/ltblu-diamond.png',
        'no_discount': 'http://maps.google.com/mapfiles/kml/paddle/ltblu-circle.png',
    },
    'fair': {
        '50%': 'http://maps.google.com/mapfiles/kml/paddle/ylw-stars.png',
        '25-30%': 'http://maps.google.com/mapfiles/kml/paddle/ylw-diamond.png',
        'no_discount': 'http://maps.google.com/mapfiles/kml/paddle/ylw-circle.png',
    },
    'below_average': {
        '50%': 'http://maps.google.com/mapfiles/kml/paddle/orange-stars.png',
        '25-30%': 'http://maps.google.com/mapfiles/kml/paddle/orange-diamond.png',
        'no_discount': 'http://maps.google.com/mapfiles/kml/paddle/orange-circle.png',
    },
    'poor': {
        '50%': 'http://maps.google.com/mapfiles/kml/paddle/red-stars.png',
        '25-30%': 'http://maps.google.com/mapfiles/kml/paddle/red-diamond.png',
        'no_discount': 'http://maps.google.com/mapfiles/kml/paddle/red-circle.png',
    },
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

    sections = re.split(r'###\s+\d+\.', content)

    for section in sections[1:]:
        url_match = re.search(r'\]\((https://[^\)]+)\)', section)
        if url_match:
            url = url_match.group(1)
            addr_match = re.search(r'\*\*Address:\*\*\s+([^\n]+)', section)
            if addr_match:
                address = addr_match.group(1).strip()
                address_key = ' '.join(address.lower().split()).replace(',', '')
                address_urls[address_key] = url

    return address_urls


def find_url_for_sale(sale: Dict[str, str], address_urls: Dict[str, str]) -> str:
    """Find the URL for a sale by matching its address."""
    full_address = f"{sale['Address']}, {sale['City']}, {sale['State']} {sale['ZIP']}"
    address_key = ' '.join(full_address.lower().split()).replace(',', '')

    if address_key in address_urls:
        return address_urls[address_key]

    street_key = ' '.join(sale['Address'].lower().split())
    for addr, url in address_urls.items():
        if street_key in addr:
            return url

    return ""


def parse_days(description: str) -> Set[str]:
    """Extract which days a sale is open from the description."""
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
    """Extract the maximum discount level from the description."""
    if re.search(r'50%\s*off', description, re.IGNORECASE):
        return '50%'
    if re.search(r'(25|30)%\s*off', description, re.IGNORECASE):
        return '25-30%'
    return 'no_discount'


def get_discount_for_day(description: str, day: str) -> str:
    """Get the discount level specifically for a given day."""
    day_abbr = {
        'Friday': r'\bFri\b',
        'Saturday': r'\bSat\b',
        'Sunday': r'\bSun\b'
    }

    lines = description.split(',')
    for line in lines:
        if re.search(day_abbr[day], line, re.IGNORECASE):
            if re.search(r'50%\s*off', line, re.IGNORECASE):
                return '50%'
            if re.search(r'(25|30)%\s*off', line, re.IGNORECASE):
                return '25-30%'

    return parse_discount_level(description)


def create_snippet(description: str, days: Set[str], neighborhood: Dict) -> str:
    """
    Create a short snippet for list view including safety info.

    Args:
        description: Full sale description
        days: Set of days the sale is open
        neighborhood: Neighborhood rating data

    Returns:
        Snippet text with safety and discount info
    """
    discount = parse_discount_level(description)
    discount_text = ""
    if discount == '50%':
        discount_text = "50% OFF"
    elif discount == '25-30%':
        discount_text = "25-30% OFF"

    # Safety indicator
    safety_emoji = get_rating_emoji(neighborhood['rating'])

    # Format days
    day_abbr = []
    if 'Friday' in days:
        day_abbr.append('Fri')
    if 'Saturday' in days:
        day_abbr.append('Sat')
    if 'Sunday' in days:
        day_abbr.append('Sun')
    days_text = ', '.join(day_abbr)

    parts = [p for p in [safety_emoji, discount_text, days_text] if p]
    return ' | '.join(parts)


def create_kml_header(include_safety_styles: bool = True) -> str:
    """Create KML header with proper XML declaration and styling."""
    header = '''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Estate Sales with Safety Ratings</name>
    <description>Estate sales color-coded by neighborhood quality and discount level</description>

'''

    # Add combined styles for all safety/discount combinations
    for safety, discounts in COMBINED_ICONS.items():
        for discount, icon_url in discounts.items():
            style_id = f"{safety}_{discount.replace('%', 'pct').replace('-', '_')}"
            header += f'''    <Style id="{style_id}">
      <IconStyle>
        <Icon>
          <href>{icon_url}</href>
        </Icon>
      </IconStyle>
    </Style>
'''

    return header


def create_placemark(sale: Dict[str, str], url: str, discount_level: str, neighborhood: Dict) -> str:
    """
    Create a KML placemark for an estate sale with safety info.

    Args:
        sale: Dictionary containing sale data
        url: URL to the estate sale website
        discount_level: Discount level for style selection
        neighborhood: Neighborhood rating data

    Returns:
        KML placemark string
    """
    name = escape(sale['Name'])
    description = escape(sale['Description'])
    address = escape(f"{sale['Address']}, {sale['City']}, {sale['State']} {sale['ZIP']}")

    desc_parts = description.split('|')
    times = desc_parts[0].strip() if len(desc_parts) > 0 else description
    notes = desc_parts[1].strip() if len(desc_parts) > 1 else ""

    days = parse_days(sale['Description'])
    snippet = create_snippet(sale['Description'], days, neighborhood)

    # Safety rating info
    safety_rating = neighborhood['rating'].replace('_', ' ').title()
    safety_score = neighborhood['score']
    safety_desc = neighborhood['description']
    estimated_income = neighborhood['estimated_income']

    # Create CDATA section for HTML content
    if url:
        html_description = f'''<![CDATA[
<h3><a href="{url}" target="_blank">{name}</a></h3>
<p><strong>Neighborhood:</strong> {safety_rating} ({safety_score}/10)</p>
<p style="color: #666; font-size: 0.9em;">{safety_desc}</p>
<p><strong>Hours:</strong> {times}</p>'''
    else:
        html_description = f'''<![CDATA[
<h3>{name}</h3>
<p><strong>Neighborhood:</strong> {safety_rating} ({safety_score}/10)</p>
<p style="color: #666; font-size: 0.9em;">{safety_desc}</p>
<p><strong>Hours:</strong> {times}</p>'''

    if notes:
        html_description += f'''
<p><strong>Notes:</strong> {notes}</p>'''
    html_description += '''
]]>'''

    # Determine style based on safety and discount level
    safety = neighborhood['rating']
    style_id = f"{safety}_{discount_level.replace('%', 'pct').replace('-', '_')}"

    placemark = f'''      <Placemark>
        <name>{name}</name>
        <Snippet maxLines="1">{snippet}</Snippet>
        <description>{html_description}</description>
        <styleUrl>#{style_id}</styleUrl>
        <address>{address}</address>
      </Placemark>
'''

    return placemark


def organize_sales(
    sales: List[Dict[str, str]],
    address_urls: Dict[str, str],
    sort_by_safety: bool = False
) -> Dict:
    """
    Organize sales with neighborhood data.

    Args:
        sales: List of sale dictionaries
        address_urls: Dictionary of URLs by address
        sort_by_safety: If True, organize by safety first, then day

    Returns:
        Nested dictionary with sales organized by category
    """
    # Get neighborhood ratings for all unique ZIP codes
    zip_ratings = {}
    for sale in sales:
        zip_code = sale['ZIP']
        if zip_code not in zip_ratings:
            zip_ratings[zip_code] = get_neighborhood_rating(
                zip_code, sale['State'], sale['City']
            )

    if sort_by_safety:
        # Organization: Safety -> Day -> Discount -> Sales
        safety_levels = ['excellent', 'good', 'fair', 'below_average', 'poor']
        organization = {
            safety: {
                'Friday': {'50%': [], '25-30%': [], 'no_discount': []},
                'Saturday': {'50%': [], '25-30%': [], 'no_discount': []},
                'Sunday': {'50%': [], '25-30%': [], 'no_discount': []}
            }
            for safety in safety_levels
        }

        for sale in sales:
            url = find_url_for_sale(sale, address_urls)
            days = parse_days(sale['Description'])
            neighborhood = zip_ratings[sale['ZIP']]
            safety = neighborhood['rating']

            for day in days:
                if day in organization[safety]:
                    discount = get_discount_for_day(sale['Description'], day)
                    if discount not in organization[safety][day]:
                        discount = 'no_discount'
                    organization[safety][day][discount].append((sale, url, neighborhood))

        return {'type': 'by_safety', 'data': organization, 'zip_ratings': zip_ratings}

    else:
        # Organization: Day -> Discount -> Sales (original structure, with neighborhood added)
        organization = {
            'Friday': {'50%': [], '25-30%': [], 'no_discount': []},
            'Saturday': {'50%': [], '25-30%': [], 'no_discount': []},
            'Sunday': {'50%': [], '25-30%': [], 'no_discount': []}
        }

        for sale in sales:
            url = find_url_for_sale(sale, address_urls)
            days = parse_days(sale['Description'])
            neighborhood = zip_ratings[sale['ZIP']]

            for day in days:
                if day in organization:
                    discount = get_discount_for_day(sale['Description'], day)
                    if discount not in organization[day]:
                        discount = 'no_discount'
                    organization[day][discount].append((sale, url, neighborhood))

        return {'type': 'by_day', 'data': organization, 'zip_ratings': zip_ratings}


def create_kml_footer() -> str:
    """Create KML footer."""
    return '''  </Document>
</kml>
'''


def convert_csv_to_kml_with_safety(
    csv_path: Path,
    markdown_path: Path,
    output_path: Path,
    sort_by_safety: bool = False
) -> None:
    """
    Convert CSV estate sale data to KML with neighborhood safety ratings.

    Args:
        csv_path: Path to input CSV file
        markdown_path: Path to markdown details file
        output_path: Path to output KML file
        sort_by_safety: If True, organize folders by safety rating first
    """
    print(f"Reading URLs from {markdown_path}...")
    address_urls = parse_markdown_urls(markdown_path)
    print(f"Found {len(address_urls)} URLs in markdown file")

    print(f"Reading sales data from {csv_path}...")
    sales = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Name']:
                sales.append(row)
    print(f"Found {len(sales)} sales in CSV file")

    print(f"Looking up neighborhood ratings...")
    organized = organize_sales(sales, address_urls, sort_by_safety)

    print(f"Generating KML file with safety ratings at {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(create_kml_header())

        if organized['type'] == 'by_safety':
            # Safety -> Day -> Discount structure
            safety_names = {
                'excellent': 'Excellent Areas (Safe, Upscale)',
                'good': 'Good Areas (Nice Suburbs)',
                'fair': 'Fair Areas (Average)',
                'below_average': 'Below Average Areas (Use Caution)',
                'poor': 'Poor Areas (Be Aware)'
            }

            for safety in ['excellent', 'good', 'fair', 'below_average', 'poor']:
                safety_data = organized['data'][safety]
                total_in_safety = sum(
                    len(safety_data[day][disc])
                    for day in safety_data
                    for disc in safety_data[day]
                )

                if total_in_safety == 0:
                    continue

                f.write(f'    <Folder>\n')
                f.write(f'      <name>{safety_names[safety]}</name>\n')

                for day in ['Friday', 'Saturday', 'Sunday']:
                    total_in_day = sum(len(safety_data[day][d]) for d in safety_data[day])
                    if total_in_day == 0:
                        continue

                    f.write(f'      <Folder>\n')
                    f.write(f'        <name>{day}</name>\n')

                    for discount_level in ['50%', '25-30%', 'no_discount']:
                        sales_list = safety_data[day][discount_level]
                        if not sales_list:
                            continue

                        folder_name = {
                            '50%': '50% Off',
                            '25-30%': '25-30% Off',
                            'no_discount': 'No Discount'
                        }[discount_level]

                        f.write(f'        <Folder>\n')
                        f.write(f'          <name>{folder_name}</name>\n')

                        for sale, url, neighborhood in sales_list:
                            f.write(create_placemark(sale, url, discount_level, neighborhood))

                        f.write(f'        </Folder>\n')

                    f.write(f'      </Folder>\n')

                f.write(f'    </Folder>\n')

        else:
            # Day -> Discount structure (with safety in each placemark)
            for day in ['Friday', 'Saturday', 'Sunday']:
                f.write(f'    <Folder>\n')
                f.write(f'      <name>{day} Sales</name>\n')

                for discount_level in ['50%', '25-30%', 'no_discount']:
                    sales_list = organized['data'][day][discount_level]

                    if sales_list:
                        folder_name = {
                            '50%': '50% Off',
                            '25-30%': '25-30% Off',
                            'no_discount': 'No Discount'
                        }[discount_level]

                        f.write(f'      <Folder>\n')
                        f.write(f'        <name>{folder_name}</name>\n')

                        # Sort by safety rating within discount level
                        safety_order = {'excellent': 0, 'good': 1, 'fair': 2, 'below_average': 3, 'poor': 4}
                        sales_list_sorted = sorted(
                            sales_list,
                            key=lambda x: safety_order.get(x[2]['rating'], 5)
                        )

                        for sale, url, neighborhood in sales_list_sorted:
                            f.write(create_placemark(sale, url, discount_level, neighborhood))

                        f.write(f'      </Folder>\n')

                f.write(f'    </Folder>\n')

        f.write(create_kml_footer())

    # Print statistics
    print(f"\n{'='*60}")
    print(f"KML file created successfully with safety ratings!")
    print(f"Output: {output_path}")
    print(f"{'='*60}")

    # Safety distribution
    print(f"\nNeighborhood Safety Distribution:")
    zip_ratings = organized['zip_ratings']
    safety_counts = {}
    for sale in sales:
        rating = zip_ratings[sale['ZIP']]['rating']
        safety_counts[rating] = safety_counts.get(rating, 0) + 1

    for safety in ['excellent', 'good', 'fair', 'below_average', 'poor']:
        count = safety_counts.get(safety, 0)
        if count > 0:
            pct = count / len(sales) * 100
            emoji = get_rating_emoji(safety)
            print(f"  {emoji} {safety.replace('_', ' ').title()}: {count} ({pct:.0f}%)")

    # Icon legend
    print(f"\nIcon Legend:")
    print(f"  Color = Neighborhood Safety (Green=Best, Red=Caution)")
    print(f"  Shape: Stars=50% off, Diamond=25-30% off, Circle=No discount")


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: python csv_to_kml_with_safety.py <csv> <markdown> [output.kml] [--sort-by-safety]")
        print("\nOptions:")
        print("  --sort-by-safety  Organize folders by safety rating first, then by day")
        print("\nExample:")
        print("  python csv_to_kml_with_safety.py sales.csv details.md output.kml")
        print("  python csv_to_kml_with_safety.py sales.csv details.md --sort-by-safety")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    markdown_path = Path(sys.argv[2])

    # Parse remaining arguments
    sort_by_safety = '--sort-by-safety' in sys.argv
    output_path = None

    for arg in sys.argv[3:]:
        if not arg.startswith('--'):
            output_path = Path(arg)

    if output_path is None:
        suffix = '_with_safety' if not sort_by_safety else '_by_safety'
        output_path = csv_path.with_stem(csv_path.stem + suffix).with_suffix('.kml')

    # Validate input files
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        sys.exit(1)

    if not markdown_path.exists():
        print(f"Error: Markdown file not found: {markdown_path}")
        sys.exit(1)

    try:
        convert_csv_to_kml_with_safety(csv_path, markdown_path, output_path, sort_by_safety)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

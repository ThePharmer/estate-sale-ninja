#!/usr/bin/env python3
"""
Enrich estate sale CSV with neighborhood safety ratings.

Adds neighborhood quality information to each sale based on ZIP code.
Outputs an enriched CSV and a summary report.

Usage:
    python enrich_with_safety.py <input.csv> [output.csv]
"""

import csv
import sys
from pathlib import Path
from typing import List, Dict

from neighborhood_lookup import (
    get_neighborhood_rating,
    format_rating_for_display,
    get_rating_emoji
)


def enrich_csv_with_safety(input_path: Path, output_path: Path) -> List[Dict]:
    """
    Add neighborhood safety columns to a CSV file.

    Args:
        input_path: Path to input CSV file
        output_path: Path to output enriched CSV file

    Returns:
        List of enriched sale dictionaries
    """
    print(f"Reading sales from {input_path}...")

    # Read original CSV
    sales = []
    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        original_fieldnames = reader.fieldnames
        for row in reader:
            if row.get('Name'):
                sales.append(row)

    print(f"Found {len(sales)} sales")
    print(f"Looking up neighborhood ratings...")

    # Cache ratings by ZIP code
    zip_ratings = {}
    for sale in sales:
        zip_code = sale.get('ZIP', '')
        if zip_code and zip_code not in zip_ratings:
            rating = get_neighborhood_rating(
                zip_code,
                sale.get('State', ''),
                sale.get('City', '')
            )
            zip_ratings[zip_code] = rating

    # Enrich each sale
    enriched_sales = []
    for sale in sales:
        zip_code = sale.get('ZIP', '')
        if zip_code and zip_code in zip_ratings:
            rating = zip_ratings[zip_code]
            sale['Safety_Rating'] = rating['rating'].replace('_', ' ').title()
            sale['Safety_Score'] = str(rating['score'])
            sale['Est_Median_Income'] = str(rating['estimated_income'])
            sale['Safety_Note'] = rating['description']
        else:
            sale['Safety_Rating'] = 'Unknown'
            sale['Safety_Score'] = '0'
            sale['Est_Median_Income'] = '0'
            sale['Safety_Note'] = 'ZIP code not found'

        enriched_sales.append(sale)

    # Write enriched CSV
    new_fieldnames = list(original_fieldnames) + [
        'Safety_Rating', 'Safety_Score', 'Est_Median_Income', 'Safety_Note'
    ]

    print(f"Writing enriched CSV to {output_path}...")
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=new_fieldnames)
        writer.writeheader()
        writer.writerows(enriched_sales)

    return enriched_sales


def print_safety_report(sales: List[Dict]) -> None:
    """Print a summary report of neighborhood safety ratings."""
    print(f"\n{'='*60}")
    print("NEIGHBORHOOD SAFETY REPORT")
    print(f"{'='*60}\n")

    # Group by safety rating
    by_rating = {}
    for sale in sales:
        rating = sale.get('Safety_Rating', 'Unknown')
        if rating not in by_rating:
            by_rating[rating] = []
        by_rating[rating].append(sale)

    # Print summary
    rating_order = ['Excellent', 'Good', 'Fair', 'Below Average', 'Poor', 'Unknown']
    rating_emojis = {
        'Excellent': '★★★',
        'Good': '★★☆',
        'Fair': '★☆☆',
        'Below Average': '⚠',
        'Poor': '⚠⚠',
        'Unknown': '?'
    }

    print("SUMMARY BY RATING:\n")
    for rating in rating_order:
        if rating in by_rating:
            count = len(by_rating[rating])
            pct = count / len(sales) * 100
            emoji = rating_emojis.get(rating, '')
            print(f"  {emoji} {rating}: {count} sales ({pct:.0f}%)")

    # Detailed listing
    print(f"\n{'='*60}")
    print("DETAILED LISTING BY SAFETY LEVEL:")
    print(f"{'='*60}\n")

    for rating in rating_order:
        if rating not in by_rating:
            continue

        sales_in_rating = by_rating[rating]
        print(f"\n{rating_emojis.get(rating, '')} {rating.upper()} ({len(sales_in_rating)} sales)")
        print("-" * 40)

        for sale in sorted(sales_in_rating, key=lambda x: x.get('Name', '')):
            name = sale.get('Name', 'Unknown')[:30]
            city = sale.get('City', '')
            zip_code = sale.get('ZIP', '')
            income = sale.get('Est_Median_Income', '0')
            try:
                income_formatted = f"${int(income):,}"
            except ValueError:
                income_formatted = income
            print(f"  - {name:<30} | {city:<15} {zip_code} | {income_formatted}")

    # Recommendations
    print(f"\n{'='*60}")
    print("RECOMMENDATIONS:")
    print(f"{'='*60}\n")

    excellent_count = len(by_rating.get('Excellent', []))
    good_count = len(by_rating.get('Good', []))
    fair_count = len(by_rating.get('Fair', []))
    caution_count = len(by_rating.get('Below Average', [])) + len(by_rating.get('Poor', []))

    if excellent_count + good_count > 0:
        print(f"  PRIORITIZE: {excellent_count + good_count} sales in excellent/good areas")
        print(f"    - Likely higher-value items")
        print(f"    - Safer neighborhoods")
        print(f"    - Better parking/access")

    if caution_count > 0:
        print(f"\n  USE CAUTION: {caution_count} sales in below-average/poor areas")
        print(f"    - Consider going with a partner")
        print(f"    - Visit during daylight hours")
        print(f"    - Park in visible, well-lit areas")
        print(f"    - Trust your instincts")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python enrich_with_safety.py <input.csv> [output.csv]")
        print("\nAdds neighborhood safety ratings to estate sale CSV.")
        print("\nNew columns added:")
        print("  - Safety_Rating: Excellent, Good, Fair, Below Average, Poor")
        print("  - Safety_Score: 1-10 scale")
        print("  - Est_Median_Income: Estimated median household income")
        print("  - Safety_Note: Description of area")
        sys.exit(1)

    input_path = Path(sys.argv[1])

    if len(sys.argv) > 2:
        output_path = Path(sys.argv[2])
    else:
        output_path = input_path.with_stem(input_path.stem + '_with_safety')

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    try:
        enriched_sales = enrich_csv_with_safety(input_path, output_path)
        print_safety_report(enriched_sales)
        print(f"\nEnriched CSV saved to: {output_path}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

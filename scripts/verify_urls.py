#!/usr/bin/env python3
"""
Verify that data in KML matches the actual estate sale websites.
"""

import re
import sys
import time
from pathlib import Path
from xml.etree import ElementTree as ET
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def parse_kml_data(kml_path: Path):
    """Extract all placemarks with URLs from KML."""
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

        if url:  # Only include placemarks with URLs
            # Parse address components
            addr_parts = address.split(',') if address else []
            street = addr_parts[0].strip() if len(addr_parts) > 0 else ""
            city = addr_parts[1].strip() if len(addr_parts) > 1 else ""
            state_zip = addr_parts[2].strip() if len(addr_parts) > 2 else ""

            # Extract state and zip
            state_zip_parts = state_zip.split()
            state = state_zip_parts[0] if len(state_zip_parts) > 0 else ""
            zip_code = state_zip_parts[1] if len(state_zip_parts) > 1 else ""

            placemarks.append({
                'name': name,
                'address': address,
                'street': street,
                'city': city,
                'state': state,
                'zip': zip_code,
                'url': url
            })

    return placemarks


def fetch_url(url, retries=3):
    """Fetch URL content with retries."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    for attempt in range(retries):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=10) as response:
                return response.read().decode('utf-8', errors='ignore')
        except HTTPError as e:
            if e.code == 404:
                return None  # Page not found
            elif attempt == retries - 1:
                raise
            time.sleep(2)  # Wait before retry
        except URLError as e:
            if attempt == retries - 1:
                raise
            time.sleep(2)
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2)

    return None


def normalize_text(text):
    """Normalize text for comparison."""
    if not text:
        return ""
    # Remove extra whitespace, lowercase
    return ' '.join(text.lower().split())


def extract_sale_info(html):
    """Extract sale information from HTML."""
    if not html:
        return None

    info = {
        'title': None,
        'address': None,
        'city': None,
        'state': None,
        'zip': None
    }

    # Extract title - look for common patterns
    title_patterns = [
        r'<h1[^>]*>([^<]+)</h1>',
        r'<title>([^<]+)</title>',
        r'property="og:title"\s+content="([^"]+)"',
    ]

    for pattern in title_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            # Clean up common suffixes
            title = re.sub(r'\s*\|\s*EstateS.*$', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s*-\s*Estate Sales\.net.*$', '', title, flags=re.IGNORECASE)
            info['title'] = title
            break

    # Extract address - look for schema.org markup or common patterns
    addr_patterns = [
        r'itemprop="streetAddress"[^>]*>([^<]+)<',
        r'property="og:street-address"\s+content="([^"]+)"',
        r'class="[^"]*address[^"]*"[^>]*>([^<]+)<',
        r'"streetAddress"\s*:\s*"([^"]+)"',
    ]

    for pattern in addr_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            info['address'] = match.group(1).strip()
            break

    # Extract city
    city_patterns = [
        r'itemprop="addressLocality"[^>]*>([^<]+)<',
        r'property="og:locality"\s+content="([^"]+)"',
        r'"addressLocality"\s*:\s*"([^"]+)"',
    ]

    for pattern in city_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            info['city'] = match.group(1).strip()
            break

    # Extract state
    state_patterns = [
        r'itemprop="addressRegion"[^>]*>([^<]+)<',
        r'property="og:region"\s+content="([^"]+)"',
        r'"addressRegion"\s*:\s*"([^"]+)"',
    ]

    for pattern in state_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            info['state'] = match.group(1).strip()
            break

    # Extract ZIP
    zip_patterns = [
        r'itemprop="postalCode"[^>]*>([^<]+)<',
        r'property="og:postal-code"\s+content="([^"]+)"',
        r'"postalCode"\s*:\s*"([^"]+)"',
        r'\b(\d{5}(?:-\d{4})?)\b',  # Generic ZIP pattern
    ]

    for pattern in zip_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            info['zip'] = match.group(1).strip()
            break

    return info


def verify_sale(placemark, delay=1.0):
    """Verify a single sale against its URL."""
    url = placemark['url']

    try:
        # Fetch the page
        html = fetch_url(url)

        if html is None:
            return {
                'status': 'error',
                'error': '404 Not Found',
                'matches': {}
            }

        # Extract info from page
        web_info = extract_sale_info(html)

        # Compare data
        matches = {}

        # Check address (street)
        if web_info['address']:
            matches['address'] = normalize_text(placemark['street']) in normalize_text(web_info['address'])
        else:
            matches['address'] = None  # Could not extract

        # Check city
        if web_info['city']:
            matches['city'] = normalize_text(placemark['city']) == normalize_text(web_info['city'])
        else:
            matches['city'] = None

        # Check state
        if web_info['state']:
            matches['state'] = normalize_text(placemark['state']) == normalize_text(web_info['state'])
        else:
            matches['state'] = None

        # Check ZIP
        if web_info['zip']:
            matches['zip'] = placemark['zip'] in web_info['zip']
        else:
            matches['zip'] = None

        # Check title (fuzzy match - look for key words)
        if web_info['title']:
            # Check if key words from KML name appear in web title or vice versa
            kml_words = set(normalize_text(placemark['name']).split())
            web_words = set(normalize_text(web_info['title']).split())
            # Remove common words
            common_words = {'estate', 'sale', 'sales', 'the', 'a', 'an', 'and', 'or', 'in', 'at', 'of'}
            kml_words -= common_words
            web_words -= common_words

            # Check overlap
            overlap = kml_words & web_words
            matches['title'] = len(overlap) >= 2 or normalize_text(placemark['name']) in normalize_text(web_info['title'])
        else:
            matches['title'] = None

        return {
            'status': 'success',
            'web_info': web_info,
            'matches': matches
        }

    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'matches': {}
        }
    finally:
        # Be polite - wait between requests
        time.sleep(delay)


def verify_all_urls(kml_path: Path, delay=1.5):
    """Verify all URLs in KML file."""
    print("=" * 80)
    print("URL VERIFICATION - Checking data against live websites")
    print("=" * 80)
    print()

    placemarks = parse_kml_data(kml_path)
    print(f"Found {len(placemarks)} sales with URLs to verify")
    print(f"Estimated time: ~{int(len(placemarks) * delay / 60)} minutes")
    print()

    results = []

    for i, pm in enumerate(placemarks, 1):
        print(f"[{i}/{len(placemarks)}] Checking: {pm['name'][:50]}...")
        result = verify_sale(pm, delay=delay)
        results.append({
            'placemark': pm,
            'result': result
        })

        # Show quick status
        if result['status'] == 'error':
            print(f"  ✗ ERROR: {result['error']}")
        else:
            matches = result['matches']
            match_summary = []
            for key, val in matches.items():
                if val is True:
                    match_summary.append(f"{key}✓")
                elif val is False:
                    match_summary.append(f"{key}✗")
                else:
                    match_summary.append(f"{key}?")
            print(f"  → {' '.join(match_summary)}")

    # Generate summary report
    print()
    print("=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    print()

    total = len(results)
    errors = sum(1 for r in results if r['result']['status'] == 'error')
    successful = total - errors

    print(f"Total URLs checked: {total}")
    print(f"Successfully fetched: {successful}")
    print(f"Errors (404/timeout): {errors}")
    print()

    # Analyze matches
    if successful > 0:
        match_stats = {
            'address': {'match': 0, 'mismatch': 0, 'unknown': 0},
            'city': {'match': 0, 'mismatch': 0, 'unknown': 0},
            'state': {'match': 0, 'mismatch': 0, 'unknown': 0},
            'zip': {'match': 0, 'mismatch': 0, 'unknown': 0},
            'title': {'match': 0, 'mismatch': 0, 'unknown': 0},
        }

        for r in results:
            if r['result']['status'] == 'success':
                for field, matched in r['result']['matches'].items():
                    if matched is True:
                        match_stats[field]['match'] += 1
                    elif matched is False:
                        match_stats[field]['mismatch'] += 1
                    else:
                        match_stats[field]['unknown'] += 1

        print("Field-by-field verification:")
        for field, stats in match_stats.items():
            total_checked = stats['match'] + stats['mismatch'] + stats['unknown']
            if total_checked > 0:
                match_pct = (stats['match'] / successful) * 100
                print(f"  {field.capitalize():10s}: {stats['match']:2d} matched, {stats['mismatch']:2d} mismatched, {stats['unknown']:2d} unknown ({match_pct:.0f}%)")

    # Show problematic entries
    print()
    problems = [r for r in results if r['result']['status'] == 'error' or
                (r['result']['status'] == 'success' and
                 any(v is False for v in r['result']['matches'].values()))]

    if problems:
        print(f"Issues found ({len(problems)} sales):")
        print("-" * 80)
        for r in problems[:10]:  # Show first 10
            pm = r['placemark']
            result = r['result']
            print(f"\n{pm['name']}")
            print(f"  URL: {pm['url']}")
            if result['status'] == 'error':
                print(f"  ERROR: {result['error']}")
            else:
                for field, matched in result['matches'].items():
                    if matched is False:
                        print(f"  ✗ {field.upper()} mismatch")
                        print(f"    Expected: {pm.get(field, 'N/A')}")
                        if 'web_info' in result and result['web_info'].get(field):
                            print(f"    Found: {result['web_info'][field]}")

        if len(problems) > 10:
            print(f"\n... and {len(problems) - 10} more issues")
    else:
        print("✓ No issues found - all data matches!")

    print()
    print("=" * 80)

    # Overall pass/fail
    if errors == 0 and not problems:
        print("✓ VERIFICATION PASSED - All URLs accessible and data matches!")
        return 0
    elif successful > total * 0.9:  # 90% success rate
        print("⚠ VERIFICATION MOSTLY PASSED - Minor issues detected")
        return 0
    else:
        print("✗ VERIFICATION FAILED - Significant issues detected")
        return 1


def main():
    if len(sys.argv) < 2:
        print("Usage: python verify_urls.py <kml_file> [delay_seconds]")
        print("\nExample:")
        print("  python verify_urls.py Estate_Sales.kml")
        print("  python verify_urls.py Estate_Sales.kml 2.0")
        sys.exit(1)

    kml_path = Path(sys.argv[1])
    delay = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5

    if not kml_path.exists():
        print(f"Error: KML file not found: {kml_path}")
        sys.exit(1)

    try:
        return verify_all_urls(kml_path, delay=delay)
    except KeyboardInterrupt:
        print("\n\nVerification interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError during verification: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Neighborhood safety and quality lookup module.

Uses free data sources to estimate neighborhood quality based on:
- CrimeGrade.org crime statistics (A-F grades by ZIP)
- Median household income (Census data)
- ZIP code demographics

No API keys required - uses publicly available data.

Data source priority:
1. CrimeGrade.org via Playwright (if installed) - actual crime grades
2. CrimeGrade.org via urllib (may be blocked by bot protection)
3. Income estimates (Census-based) - always available fallback

To enable Playwright support (recommended for best results):
    pip install playwright
    playwright install chromium

Future enhancements (TODO):
- Census block group level crime data (more granular than ZIP)
- SpotCrime incident counts by address
- Zillow home value scraping
"""

import json
import re
import urllib.request
import urllib.error
import ssl
import time
from typing import Dict, Optional, Tuple
from pathlib import Path

# Check if Playwright is available
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# Cache for API responses to avoid repeated lookups
_zip_cache: Dict[str, Dict] = {}
_crime_cache: Dict[str, Dict] = {}

# Cache file path for persistent storage
CACHE_FILE = Path(__file__).parent / '.neighborhood_cache.json'
CRIME_CACHE_FILE = Path(__file__).parent / '.crimegrade_cache.json'


def load_cache() -> None:
    """Load cached neighborhood data from disk."""
    global _zip_cache, _crime_cache
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r') as f:
                _zip_cache = json.load(f)
        except (json.JSONDecodeError, IOError):
            _zip_cache = {}
    if CRIME_CACHE_FILE.exists():
        try:
            with open(CRIME_CACHE_FILE, 'r') as f:
                _crime_cache = json.load(f)
        except (json.JSONDecodeError, IOError):
            _crime_cache = {}


def save_cache() -> None:
    """Save neighborhood cache to disk."""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(_zip_cache, f, indent=2)
    except IOError:
        pass  # Silently fail if can't write cache
    try:
        with open(CRIME_CACHE_FILE, 'w') as f:
            json.dump(_crime_cache, f, indent=2)
    except IOError:
        pass


def fetch_zip_data(zip_code: str, timeout: int = 10) -> Optional[Dict]:
    """
    Fetch demographic data for a ZIP code from Zippopotam.us API.

    This free API provides basic location data. We supplement with
    income estimates based on state/region.

    Args:
        zip_code: 5-digit ZIP code
        timeout: Request timeout in seconds

    Returns:
        Dictionary with location data or None if lookup fails
    """
    zip_code = zip_code.strip()[:5]  # Ensure 5 digits

    if zip_code in _zip_cache:
        return _zip_cache[zip_code]

    url = f"https://api.zippopotam.us/us/{zip_code}"

    try:
        # Create SSL context that doesn't verify (some systems have cert issues)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(url, headers={'User-Agent': 'EstateSaleNinja/1.0'})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            data = json.loads(response.read().decode('utf-8'))
            _zip_cache[zip_code] = data
            return data
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError):
        return None


def fetch_crimegrade_playwright(zip_code: str) -> Optional[str]:
    """
    Fetch CrimeGrade.org page using Playwright (headless browser).

    This bypasses bot protection that blocks simple HTTP requests.
    Requires: pip install playwright && playwright install chromium

    Args:
        zip_code: 5-digit ZIP code

    Returns:
        HTML content of the page, or None if fetch fails
    """
    if not PLAYWRIGHT_AVAILABLE:
        return None

    url = f"https://crimegrade.org/safest-places-in-{zip_code}/"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
            )
            context = browser.new_context(
                ignore_https_errors=True,
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()

            try:
                response = page.goto(url, wait_until='domcontentloaded', timeout=20000)

                # Check for successful response
                if response and response.status == 200:
                    # Wait for content to render
                    page.wait_for_timeout(2000)
                    html = page.content()
                    return html
                else:
                    return None

            finally:
                browser.close()

    except Exception:
        # Any error - return None to fall back to other methods
        return None


def fetch_crimegrade_urllib(zip_code: str, timeout: int = 15) -> Optional[str]:
    """
    Fetch CrimeGrade.org page using urllib (may be blocked by bot protection).

    Args:
        zip_code: 5-digit ZIP code
        timeout: Request timeout in seconds

    Returns:
        HTML content of the page, or None if fetch fails
    """
    url = f"https://crimegrade.org/safest-places-in-{zip_code}/"

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            return response.read().decode('utf-8')

    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None


def fetch_crimegrade(zip_code: str, timeout: int = 15) -> Optional[Dict]:
    """
    Fetch crime grade data from CrimeGrade.org for a ZIP code.

    Tries multiple methods in order:
    1. Playwright (headless browser) - best success rate
    2. urllib with browser headers - may be blocked
    3. Returns None to fall back to income estimates

    Args:
        zip_code: 5-digit ZIP code
        timeout: Request timeout in seconds

    Returns:
        Dictionary with crime data:
        {
            'overall_grade': str,      # A+, A, A-, B+, B, B-, C+, C, C-, D+, D, D-, F
            'violent_grade': str,      # Grade for violent crime
            'property_grade': str,     # Grade for property crime
            'crime_description': str,  # Description like "lower than average"
        }
        Returns None if lookup fails.
    """
    zip_code = zip_code.strip()[:5]

    # Check cache first
    if zip_code in _crime_cache:
        return _crime_cache[zip_code]

    html = None

    # Try Playwright first (best success rate)
    if PLAYWRIGHT_AVAILABLE:
        html = fetch_crimegrade_playwright(zip_code)

    # Fall back to urllib if Playwright failed or unavailable
    if html is None:
        html = fetch_crimegrade_urllib(zip_code, timeout)

    # Parse the HTML if we got it
    if html:
        result = parse_crimegrade_html(html)
        if result:
            _crime_cache[zip_code] = result
            save_cache()
            return result

    return None


def parse_crimegrade_html(html: str) -> Optional[Dict]:
    """
    Parse CrimeGrade.org HTML to extract crime grades.

    Args:
        html: Raw HTML from CrimeGrade page

    Returns:
        Dictionary with parsed crime data or None if parsing fails
    """
    result = {
        'overall_grade': None,
        'violent_grade': None,
        'property_grade': None,
        'crime_description': None,
    }

    # Look for overall crime grade - usually in a prominent location
    # Pattern: grade like "A+", "B-", "C", "D+", "F" etc.
    # CrimeGrade shows grades in various formats

    # Try to find "Overall Crime Grade" or similar
    overall_match = re.search(
        r'(?:overall|total)\s*(?:crime)?\s*grade[:\s]*([A-F][+-]?)',
        html, re.IGNORECASE
    )
    if overall_match:
        result['overall_grade'] = overall_match.group(1).upper()

    # Look for letter grades in prominent positions (often in headers or large text)
    # CrimeGrade typically shows the grade prominently
    grade_pattern = re.search(
        r'<[^>]*class="[^"]*grade[^"]*"[^>]*>([A-F][+-]?)</[^>]*>',
        html, re.IGNORECASE
    )
    if grade_pattern and not result['overall_grade']:
        result['overall_grade'] = grade_pattern.group(1).upper()

    # Alternative: look for grade in title or h1/h2
    title_match = re.search(
        r'(?:crime\s+)?grade[:\s]+([A-F][+-]?)',
        html, re.IGNORECASE
    )
    if title_match and not result['overall_grade']:
        result['overall_grade'] = title_match.group(1).upper()

    # Look for violent crime grade
    violent_match = re.search(
        r'violent\s*crime[^A-F]*([A-F][+-]?)',
        html, re.IGNORECASE
    )
    if violent_match:
        result['violent_grade'] = violent_match.group(1).upper()

    # Look for property crime grade
    property_match = re.search(
        r'property\s*crime[^A-F]*([A-F][+-]?)',
        html, re.IGNORECASE
    )
    if property_match:
        result['property_grade'] = property_match.group(1).upper()

    # Look for crime rate description
    rate_match = re.search(
        r'crime\s+(?:rate\s+)?(?:is\s+)?(\d+%?\s+)?(?:lower|higher|average|below|above)[^.]*',
        html, re.IGNORECASE
    )
    if rate_match:
        result['crime_description'] = rate_match.group(0).strip()

    # If we found at least a grade, return the result
    if result['overall_grade'] or result['violent_grade'] or result['property_grade']:
        return result

    return None


def grade_to_score(grade: Optional[str]) -> int:
    """
    Convert letter grade to numeric score (1-10).

    Args:
        grade: Letter grade (A+, A, A-, B+, B, B-, C+, C, C-, D+, D, D-, F)

    Returns:
        Numeric score 1-10
    """
    if not grade:
        return 5  # Default to middle if no grade

    grade_map = {
        'A+': 10, 'A': 9, 'A-': 8,
        'B+': 7, 'B': 7, 'B-': 6,
        'C+': 5, 'C': 5, 'C-': 4,
        'D+': 3, 'D': 3, 'D-': 2,
        'F': 1
    }
    return grade_map.get(grade.upper(), 5)


def grade_to_rating(grade: Optional[str]) -> str:
    """
    Convert letter grade to rating category.

    Args:
        grade: Letter grade

    Returns:
        Rating string: 'excellent', 'good', 'fair', 'below_average', 'poor'
    """
    if not grade:
        return 'fair'

    grade = grade.upper()
    if grade in ('A+', 'A', 'A-'):
        return 'excellent'
    elif grade in ('B+', 'B', 'B-'):
        return 'good'
    elif grade in ('C+', 'C', 'C-'):
        return 'fair'
    elif grade in ('D+', 'D', 'D-'):
        return 'below_average'
    else:
        return 'poor'


# Median household income estimates by state (2023 data, rounded to nearest $1000)
# Source: US Census Bureau American Community Survey
STATE_MEDIAN_INCOME = {
    'AL': 59000, 'AK': 86000, 'AZ': 72000, 'AR': 56000, 'CA': 91000,
    'CO': 87000, 'CT': 90000, 'DE': 79000, 'FL': 67000, 'GA': 71000,
    'HI': 94000, 'ID': 70000, 'IL': 78000, 'IN': 67000, 'IA': 72000,
    'KS': 69000, 'KY': 60000, 'LA': 57000, 'ME': 68000, 'MD': 98000,
    'MA': 96000, 'MI': 68000, 'MN': 84000, 'MS': 52000, 'MO': 65000,
    'MT': 66000, 'NE': 74000, 'NV': 71000, 'NH': 90000, 'NJ': 97000,
    'NM': 58000, 'NY': 81000, 'NC': 66000, 'ND': 73000, 'OH': 66000,
    'OK': 61000, 'OR': 76000, 'PA': 73000, 'RI': 78000, 'SC': 63000,
    'SD': 69000, 'TN': 64000, 'TX': 73000, 'UT': 86000, 'VT': 74000,
    'VA': 87000, 'WA': 91000, 'WV': 53000, 'WI': 72000, 'WY': 72000,
    'DC': 101000
}

# Known affluent ZIP code prefixes by state (first 3 digits)
# These typically have 30-100% higher median income than state average
AFFLUENT_ZIP_PREFIXES = {
    # California
    '902': 1.5, '906': 1.4, '941': 1.3, '943': 1.5, '945': 1.3,
    # New York
    '100': 1.4, '104': 1.6, '105': 1.5, '106': 1.4,
    # New Jersey
    '070': 1.4, '074': 1.3, '076': 1.5,
    # Massachusetts
    '024': 1.4, '017': 1.3,
    # Connecticut
    '068': 1.5, '069': 1.3,
    # Texas
    '752': 1.3, '770': 1.2, '787': 1.2,
    # Florida
    '331': 1.3, '334': 1.2, '335': 1.2,
    # Illinois
    '600': 1.2, '604': 1.4, '605': 1.3,
    # Ohio - Toledo metro area
    '434': 1.0, '435': 1.1, '436': 0.9, '433': 1.2,
    # Michigan
    '480': 1.0, '481': 1.3, '482': 1.4, '483': 1.6, '484': 1.2,
    # Georgia
    '300': 1.2, '303': 1.0, '305': 1.1,
    # Virginia
    '201': 1.3, '220': 1.5, '221': 1.4, '222': 1.6,
    # Maryland
    '208': 1.2, '210': 0.9, '212': 0.8, '217': 1.4,
    # Pennsylvania
    '190': 1.3, '191': 0.9, '193': 1.2, '194': 1.4,
    # Colorado
    '801': 1.2, '802': 1.1, '803': 1.3,
    # Washington
    '980': 1.3, '981': 1.4, '982': 1.2,
}

# Known lower-income ZIP prefixes (typically 20-40% below state median)
LOWER_INCOME_ZIP_PREFIXES = {
    # Ohio - certain Toledo areas
    '436': 0.8,
    # Michigan - Detroit inner city
    '482': 0.7,
    # Pennsylvania - certain Philadelphia areas
    '191': 0.75,
    # Maryland - Baltimore inner city
    '212': 0.7,
    # Georgia - certain Atlanta areas
    '303': 0.8,
    # Illinois - certain Chicago areas
    '606': 0.75,
}


def estimate_median_income(zip_code: str, state: str) -> int:
    """
    Estimate median household income for a ZIP code.

    Uses state median as baseline, adjusted by known ZIP code patterns.

    Args:
        zip_code: 5-digit ZIP code
        state: 2-letter state abbreviation

    Returns:
        Estimated median household income
    """
    state = state.upper().strip()
    base_income = STATE_MEDIAN_INCOME.get(state, 70000)

    # Check for known affluent areas
    prefix = zip_code[:3]
    if prefix in AFFLUENT_ZIP_PREFIXES:
        multiplier = AFFLUENT_ZIP_PREFIXES[prefix]
        return int(base_income * multiplier)

    # Check for known lower-income areas
    if prefix in LOWER_INCOME_ZIP_PREFIXES:
        multiplier = LOWER_INCOME_ZIP_PREFIXES[prefix]
        return int(base_income * multiplier)

    # Default to state median
    return base_income


def calculate_safety_rating(estimated_income: int) -> Tuple[str, int, str]:
    """
    Calculate a safety/quality rating based on estimated income.

    This is a rough proxy - higher income areas generally have:
    - Lower property crime rates
    - Better maintained properties
    - More valuable estate sale items

    Args:
        estimated_income: Estimated median household income

    Returns:
        Tuple of (rating_label, rating_score, description)
        - rating_label: 'excellent', 'good', 'fair', 'poor', 'unknown'
        - rating_score: 1-10 scale
        - description: Brief description of the area
    """
    if estimated_income >= 100000:
        return ('excellent', 9, 'Upscale area - likely high-value items')
    elif estimated_income >= 80000:
        return ('good', 7, 'Nice suburban area - quality items expected')
    elif estimated_income >= 65000:
        return ('fair', 5, 'Average area - mixed quality')
    elif estimated_income >= 50000:
        return ('below_average', 4, 'Working class area - exercise caution')
    else:
        return ('poor', 2, 'Lower income area - be aware of surroundings')


def get_neighborhood_rating(zip_code: str, state: str, city: str = "",
                            use_crimegrade: bool = True) -> Dict:
    """
    Get comprehensive neighborhood rating for a location.

    Combines data from multiple sources:
    1. CrimeGrade.org (actual crime statistics) - if available
    2. Income estimates (Census-based) - as fallback/supplement

    Args:
        zip_code: 5-digit ZIP code
        state: 2-letter state abbreviation
        city: City name (optional, for display)
        use_crimegrade: Whether to attempt CrimeGrade lookup (default True)

    Returns:
        Dictionary with neighborhood analysis:
        {
            'zip_code': str,
            'state': str,
            'city': str,
            'estimated_income': int,
            'rating': str,          # 'excellent', 'good', 'fair', 'below_average', 'poor'
            'score': int,           # 1-10
            'description': str,
            'icon_color': str,      # For KML styling
            'crime_grade': str,     # Letter grade from CrimeGrade (if available)
            'data_source': str,     # 'crimegrade', 'income_estimate', or 'combined'
        }
    """
    zip_code = zip_code.strip()[:5]
    state = state.upper().strip()

    # Get income-based estimate as baseline/fallback
    estimated_income = estimate_median_income(zip_code, state)
    income_rating, income_score, income_desc = calculate_safety_rating(estimated_income)

    # Try to get actual crime data from CrimeGrade
    crime_data = None
    crime_grade = None
    if use_crimegrade:
        crime_data = fetch_crimegrade(zip_code)
        if crime_data:
            crime_grade = crime_data.get('overall_grade') or crime_data.get('violent_grade')

    # Determine final rating based on available data
    if crime_grade:
        # Use crime grade as primary source
        crime_score = grade_to_score(crime_grade)
        crime_rating = grade_to_rating(crime_grade)

        # Create description based on crime grade
        crime_descriptions = {
            'excellent': f'Low crime area (Grade {crime_grade}) - safe neighborhood',
            'good': f'Below average crime (Grade {crime_grade}) - generally safe',
            'fair': f'Average crime rate (Grade {crime_grade}) - typical area',
            'below_average': f'Above average crime (Grade {crime_grade}) - use caution',
            'poor': f'High crime area (Grade {crime_grade}) - exercise caution'
        }
        description = crime_descriptions.get(crime_rating, f'Crime Grade: {crime_grade}')

        # Blend with income data if available (crime weighted more heavily)
        # Final score = 70% crime + 30% income
        blended_score = int(crime_score * 0.7 + income_score * 0.3)

        rating = crime_rating
        score = blended_score
        data_source = 'crimegrade'
    else:
        # Fall back to income-based estimate
        rating = income_rating
        score = income_score
        description = income_desc
        data_source = 'income_estimate'

    # Map rating to icon colors for KML
    icon_colors = {
        'excellent': 'green',
        'good': 'ltblue',
        'fair': 'yellow',
        'below_average': 'orange',
        'poor': 'red'
    }

    return {
        'zip_code': zip_code,
        'state': state,
        'city': city,
        'estimated_income': estimated_income,
        'rating': rating,
        'score': score,
        'description': description,
        'icon_color': icon_colors.get(rating, 'blue'),
        'crime_grade': crime_grade,
        'data_source': data_source
    }


def get_rating_emoji(rating: str) -> str:
    """Get an emoji representation of the safety rating."""
    emojis = {
        'excellent': '★★★',
        'good': '★★☆',
        'fair': '★☆☆',
        'below_average': '⚠',
        'poor': '⚠⚠'
    }
    return emojis.get(rating, '?')


def format_rating_for_display(neighborhood_data: Dict) -> str:
    """
    Format neighborhood rating for text display.

    Args:
        neighborhood_data: Dictionary from get_neighborhood_rating()

    Returns:
        Formatted string for display
    """
    rating = neighborhood_data['rating'].replace('_', ' ').title()
    score = neighborhood_data['score']
    desc = neighborhood_data['description']
    income = neighborhood_data['estimated_income']
    crime_grade = neighborhood_data.get('crime_grade')
    data_source = neighborhood_data.get('data_source', 'unknown')

    if crime_grade:
        return f"{rating} ({score}/10) - Crime: {crime_grade} - ${income:,} income - {desc}"
    else:
        return f"{rating} ({score}/10) - ${income:,} median income - {desc} [est]"


def batch_lookup(locations: list) -> Dict[str, Dict]:
    """
    Look up neighborhood ratings for multiple locations.

    Args:
        locations: List of dicts with 'zip_code', 'state', 'city' keys

    Returns:
        Dictionary mapping ZIP codes to neighborhood data
    """
    load_cache()

    results = {}
    for loc in locations:
        zip_code = loc.get('ZIP', loc.get('zip_code', ''))
        state = loc.get('State', loc.get('state', ''))
        city = loc.get('City', loc.get('city', ''))

        if zip_code:
            results[zip_code] = get_neighborhood_rating(zip_code, state, city)

    save_cache()
    return results


# Demo/test function
def main():
    """Test the neighborhood lookup with sample data."""
    load_cache()

    test_locations = [
        {'zip_code': '43551', 'state': 'OH', 'city': 'Perrysburg'},      # Toledo suburb
        {'zip_code': '43615', 'state': 'OH', 'city': 'Toledo'},          # Toledo
        {'zip_code': '48323', 'state': 'MI', 'city': 'West Bloomfield'}, # Affluent Detroit suburb
        {'zip_code': '48201', 'state': 'MI', 'city': 'Detroit'},         # Inner Detroit
        {'zip_code': '90210', 'state': 'CA', 'city': 'Beverly Hills'},   # Famous affluent
        {'zip_code': '43537', 'state': 'OH', 'city': 'Maumee'},          # Toledo suburb
    ]

    print("Neighborhood Safety Rating Demo")
    print("=" * 70)
    print("Data sources: CrimeGrade.org (crime stats) + Census (income estimates)")
    print(f"Playwright: {'AVAILABLE - will use headless browser' if PLAYWRIGHT_AVAILABLE else 'Not installed - using urllib fallback'}")
    if not PLAYWRIGHT_AVAILABLE:
        print("  To enable: pip install playwright && playwright install chromium")
    print("=" * 70)

    for loc in test_locations:
        print(f"\nLooking up {loc['city']}, {loc['state']} {loc['zip_code']}...")
        rating = get_neighborhood_rating(loc['zip_code'], loc['state'], loc['city'])
        print(f"  {format_rating_for_display(rating)}")
        print(f"  Data source: {rating.get('data_source', 'unknown')}")
        print(f"  Icon color: {rating['icon_color']}")

    save_cache()
    print(f"\n{'=' * 70}")
    print("Cache saved for faster future lookups.")


if __name__ == "__main__":
    main()

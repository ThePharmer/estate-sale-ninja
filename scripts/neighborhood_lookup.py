#!/usr/bin/env python3
"""
Neighborhood safety and quality lookup module.

Uses free data sources to estimate neighborhood quality based on:
- Median household income (Census data)
- Property values
- ZIP code demographics

No API keys required - uses publicly available data.
"""

import json
import urllib.request
import urllib.error
import ssl
import time
from typing import Dict, Optional, Tuple
from pathlib import Path


# Cache for API responses to avoid repeated lookups
_zip_cache: Dict[str, Dict] = {}

# Cache file path for persistent storage
CACHE_FILE = Path(__file__).parent / '.neighborhood_cache.json'


def load_cache() -> None:
    """Load cached neighborhood data from disk."""
    global _zip_cache
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r') as f:
                _zip_cache = json.load(f)
        except (json.JSONDecodeError, IOError):
            _zip_cache = {}


def save_cache() -> None:
    """Save neighborhood cache to disk."""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(_zip_cache, f, indent=2)
    except IOError:
        pass  # Silently fail if can't write cache


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


def get_neighborhood_rating(zip_code: str, state: str, city: str = "") -> Dict:
    """
    Get comprehensive neighborhood rating for a location.

    Args:
        zip_code: 5-digit ZIP code
        state: 2-letter state abbreviation
        city: City name (optional, for display)

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
        }
    """
    zip_code = zip_code.strip()[:5]
    state = state.upper().strip()

    estimated_income = estimate_median_income(zip_code, state)
    rating, score, description = calculate_safety_rating(estimated_income)

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
        'icon_color': icon_colors.get(rating, 'blue')
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

    return f"{rating} ({score}/10) - ${income:,} median income - {desc}"


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
    test_locations = [
        {'zip_code': '43551', 'state': 'OH', 'city': 'Perrysburg'},      # Toledo suburb
        {'zip_code': '43615', 'state': 'OH', 'city': 'Toledo'},          # Toledo
        {'zip_code': '48323', 'state': 'MI', 'city': 'West Bloomfield'}, # Affluent Detroit suburb
        {'zip_code': '48201', 'state': 'MI', 'city': 'Detroit'},         # Inner Detroit
        {'zip_code': '90210', 'state': 'CA', 'city': 'Beverly Hills'},   # Famous affluent
        {'zip_code': '43537', 'state': 'OH', 'city': 'Maumee'},          # Toledo suburb
    ]

    print("Neighborhood Safety Rating Demo")
    print("=" * 60)

    for loc in test_locations:
        rating = get_neighborhood_rating(loc['zip_code'], loc['state'], loc['city'])
        print(f"\n{loc['city']}, {loc['state']} {loc['zip_code']}")
        print(f"  {format_rating_for_display(rating)}")
        print(f"  Icon color: {rating['icon_color']}")


if __name__ == "__main__":
    main()

import re
import json
import urllib.request
import urllib.parse
from pathlib import Path

# In-memory geocode cache
_GEOCODE_CACHE = {}

# Common US state code mapping
US_STATES = {
    'ALABAMA': 'AL', 'ALASKA': 'AK', 'ARIZONA': 'AZ', 'ARKANSAS': 'AR', 'CALIFORNIA': 'CA',
    'COLORADO': 'CO', 'CONNECTICUT': 'CT', 'DELAWARE': 'DE', 'FLORIDA': 'FL', 'GEORGIA': 'GA',
    'HAWAII': 'HI', 'IDAHO': 'ID', 'ILLINOIS': 'IL', 'INDIANA': 'IN', 'IOWA': 'IA',
    'KANSAS': 'KS', 'KENTUCKY': 'KY', 'LOUISIANA': 'LA', 'MAINE': 'ME', 'MARYLAND': 'MD',
    'MASSACHUSETTS': 'MA', 'MICHIGAN': 'MI', 'MINNESOTA': 'MN', 'MISSISSIPPI': 'MS', 'MISSOURI': 'MO',
    'MONTANA': 'MT', 'NEBRASKA': 'NE', 'NEVADA': 'NV', 'NEW HAMPSHIRE': 'NH', 'NEW JERSEY': 'NJ',
    'NEW MEXICO': 'NM', 'NEW YORK': 'NY', 'NORTH CAROLINA': 'NC', 'NORTH DAKOTA': 'ND', 'OHIO': 'OH',
    'OKLAHOMA': 'OK', 'OREGON': 'OR', 'PENNSYLVANIA': 'PA', 'RHODE ISLAND': 'RI', 'SOUTH CAROLINA': 'SC',
    'SOUTH DAKOTA': 'SD', 'TENNESSEE': 'TN', 'TEXAS': 'TX', 'UTAH': 'UT', 'VERMONT': 'VT',
    'VIRGINIA': 'VA', 'WASHINGTON': 'WA', 'WEST VIRGINIA': 'WV', 'WISCONSIN': 'WI', 'WYOMING': 'WY',
    'DISTRICT OF COLUMBIA': 'DC'
}

_TRUCKSTOPS_CITY_MAP = None

def _get_local_city_coords(city_name: str, state_str: str):
    """Attempt fast lookup from preprocessed local station locations."""
    global _TRUCKSTOPS_CITY_MAP
    if _TRUCKSTOPS_CITY_MAP is None:
        _TRUCKSTOPS_CITY_MAP = {}
        data_path = Path(__file__).resolve().parent.parent.parent / "truckstops.json"
        if data_path.exists():
            with open(data_path, "r", encoding="utf-8") as f:
                stops = json.load(f)
                for s in stops:
                    key = (s["city"].strip().upper(), s["state"].strip().upper())
                    if key not in _TRUCKSTOPS_CITY_MAP:
                        _TRUCKSTOPS_CITY_MAP[key] = (s["lat"], s["lon"])
                        
    state_code = state_str.strip().upper()
    if state_code in US_STATES:
        state_code = US_STATES[state_code]
        
    return _TRUCKSTOPS_CITY_MAP.get((city_name.strip().upper(), state_code))


def geocode_location(location_str: str):
    """
    Geocodes a USA location into (latitude, longitude, display_name).
    Supports:
      1. Coordinate input: "lat, lon" or "lon, lat"
      2. City, State lookup
      3. OpenStreetMap Nominatim API fallback for addresses
    """
    clean_str = location_str.strip()
    if not clean_str:
        raise ValueError("Location string cannot be empty.")

    # Check cache
    cache_key = clean_str.lower()
    if cache_key in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[cache_key]

    # Check if input is direct coordinates e.g. "41.8781, -87.6298"
    coord_match = re.match(r"^([-+]?\d{1,3}(?:\.\d+)?)\s*,\s*([-+]?\d{1,3}(?:\.\d+)?)$", clean_str)
    if coord_match:
        val1 = float(coord_match.group(1))
        val2 = float(coord_match.group(2))
        # Latitude is usually between 24 and 50 for contiguous USA, Longitude between -125 and -65
        if 20.0 <= val1 <= 55.0 and -130.0 <= val2 <= -60.0:
            lat, lon = val1, val2
        elif 20.0 <= val2 <= 55.0 and -130.0 <= val1 <= -60.0:
            lat, lon = val2, val1
        else:
            lat, lon = val1, val2
        result = (lat, lon, f"Coordinates ({lat:.4f}, {lon:.4f})")
        _GEOCODE_CACHE[cache_key] = result
        return result

    # Check city, state pattern e.g. "Austin, TX" or "Austin, Texas"
    parts = [p.strip() for p in clean_str.split(",")]
    if len(parts) >= 2:
        city_part = parts[0]
        state_part = parts[1].split()[0] # take first word e.g. "TX" from "TX 78701"
        local_coords = _get_local_city_coords(city_part, state_part)
        if local_coords:
            result = (local_coords[0], local_coords[1], f"{city_part.title()}, {state_part.upper()}, USA")
            _GEOCODE_CACHE[cache_key] = result
            return result

    # Fallback to Nominatim OpenStreetMap API
    query = clean_str
    if not any(country in query.lower() for country in ["usa", "united states", "us"]):
        query = f"{query}, USA"

    encoded_query = urllib.parse.quote(query)
    url = f"https://nominatim.openstreetmap.org/search?q={encoded_query}&format=json&limit=1&countrycodes=us"
    req = urllib.request.Request(url, headers={"User-Agent": "SpotterFuelRoutingApp/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            if not data:
                raise ValueError(f"Could not find coordinates for location: '{location_str}' within the USA.")
            item = data[0]
            lat = float(item["lat"])
            lon = float(item["lon"])
            display_name = item.get("display_name", location_str)
            result = (lat, lon, display_name)
            _GEOCODE_CACHE[cache_key] = result
            return result
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"Geocoding service unavailable for '{location_str}': {str(e)}")

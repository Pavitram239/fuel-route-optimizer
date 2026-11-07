import csv
import io
import json
import urllib.request

# Manual overrides for US cities not matching standard spelling
MANUAL_COORDS = {
    ("PORT WENTWORTH", "GA"): (32.1491, -81.1632),
    ("ELIZABETHPORT", "NJ"): (40.6565, -74.1912),
    ("BROOKPARK", "OH"): (41.4017, -81.8218),
    ("EVERGREEN", "AL"): (31.4338, -86.9547),
    ("HENRICO", "VA"): (37.5385, -77.3458),
    ("UNIVERSITY PARK", "IL"): (41.4428, -87.6975),
}


def load_us_cities():
    url = "https://raw.githubusercontent.com/kelvins/US-Cities-Database/main/csv/us_cities.csv"
    print("Downloading US cities reference database...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    content = urllib.request.urlopen(req).read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))

    city_map = {}
    for r in reader:
        city = r["CITY"].strip().upper()
        state = r["STATE_CODE"].strip().upper()
        key = (city, state)
        if key not in city_map:
            city_map[key] = (float(r["LATITUDE"]), float(r["LONGITUDE"]))

    city_map.update(MANUAL_COORDS)
    return city_map


def enrich_truckstops(
    input_csv="fuel-prices-for-be-assessment.csv", output_json="truckstops.json"
):
    city_map = load_us_cities()

    with open(input_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    enriched = []
    skipped = 0

    for r in rows:
        city = r["City"].strip().upper()
        state = r["State"].strip().upper()
        key = (city, state)

        coords = city_map.get(key)
        if coords:
            lat, lon = coords
            try:
                price = float(r["Retail Price"])
            except (ValueError, TypeError):
                continue

            enriched.append(
                {
                    "opis_id": r.get("OPIS Truckstop ID", "").strip(),
                    "name": r.get("Truckstop Name", "").strip(),
                    "address": r.get("Address", "").strip(),
                    "city": r.get("City", "").strip(),
                    "state": state,
                    "price": round(price, 4),
                    "lat": lat,
                    "lon": lon,
                }
            )
        else:
            skipped += 1

    print(f"Total rows in CSV: {len(rows)}")
    print(f"Successfully geocoded and enriched: {len(enriched)}")
    print(f"Skipped (non-US or unmapped): {skipped}")

    with open(output_json, "w", encoding="utf-8") as out:
        json.dump(enriched, out)

    print(f"Saved to {output_json} (size: {len(json.dumps(enriched))/1024:.1f} KB)")


if __name__ == "__main__":
    enrich_truckstops()

# Spotter Fuel & Route Optimizer API

A high-performance Django web application and REST API that calculates driving routes within the USA, plots them on an interactive map, and identifies the **optimal, cost-effective refueling stops** along the route based on real fuel prices.

---

## 🌟 Key Features & Requirements Met

* **Start and Finish Locations (within USA):** Accepts city/state names (e.g. `"Chicago, IL"`, `"Los Angeles, CA"`) or coordinates (`"lat, lon"`).
* **Free Map & Routing API:** Integrated with **OSRM (Open Source Routing Machine)**.
* **Minimal External Calls:** Makes **exactly 1 network call** to the routing API per request to fetch the entire route geometry, distance, and duration.
* **Blazing Fast Performance:**
  * Employs spatial grid indexing (`O(1)` cell lookups) to filter 7,500+ gas stations along thousands of route coordinates in **~20 milliseconds**.
  * Pre-geocoded local station repository eliminates external geocoding delays and API rate limits.
  * Average end-to-end API response time: **< 1.0 second**.
* **Vehicle & Fuel Economics:**
  * **Max Range:** $500\text{ miles}$ per full tank.
  * **Fuel Efficiency:** $10\text{ miles per gallon (MPG)}$ ($0.10\text{ gal/mile}$).
  * **Cost Minimization:** Evaluates station prices along the highway corridor and selects the cheapest stations without running out of fuel.
  * **Total Money Spent:** Calculates the exact dollar amount required for fuel consumption across the journey.
* **Interactive Map UI:** Built-in Leaflet.js dashboard with interactive pins, route drawing, and stop breakdowns.

---

## 🏗️ Architecture & How It Works

```
[ User Request ] 
       │ (Start, Finish)
       ▼
[ Geocoding Service ] ──> Fast local city cache / Nominatim fallback
       │ (Coordinates)
       ▼
[ Routing Service (OSRM) ] ──> Exactly 1 API call for full GeoJSON LineString
       │ (Route geometry & cumulative mileage)
       ▼
[ Spatial Corridor Filter ] ──> Fast 20ms Grid-Hash filtering (stations ≤ 10 mi from route)
       │ (Corridor candidate stations sorted by route mile)
       ▼
[ Fuel Optimizer Engine ] ──> Greedy reachability algorithm (500 mi range, 10 MPG, min price)
       │
       ├──> [ REST API JSON Response ]
       └──> [ Leaflet.js Interactive Web Map ]
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
* Python 3.10+ (Tested on Python 3.12, 3.13, 3.14)
* pip

### 2. Setup Virtual Environment & Install Dependencies
```bash
# Clone or navigate to the project directory
cd spotter

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. Run Migrations & Start Server
```bash
python manage.py migrate
python manage.py runserver
```

Open your browser to:
* **Interactive Web Map UI:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
* **REST API Endpoint:** [http://127.0.0.1:8000/api/route/?start=Chicago,IL&finish=Los+Angeles,CA](http://127.0.0.1:8000/api/route/?start=Chicago,IL&finish=Los+Angeles,CA)

---

## 📡 REST API Documentation

### **Endpoint:** `GET /api/route/` or `POST /api/route/`

#### **Parameters:**
| Parameter | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `start` | string | Yes | Start location within the USA | `"Chicago, IL"` or `"41.8781, -87.6298"` |
| `finish` | string | Yes | Destination within the USA | `"Los Angeles, CA"` or `"34.0522, -118.2437"` |

#### **Example GET Request:**
```http
GET /api/route/?start=Chicago,IL&finish=Los+Angeles,CA HTTP/1.1
Host: 127.0.0.1:8000
```

#### **Example POST Request:**
```http
POST /api/route/ HTTP/1.1
Host: 127.0.0.1:8000
Content-Type: application/json

{
  "start": "Chicago, IL",
  "finish": "Los Angeles, CA"
}
```

#### **Sample JSON Response:**
```json
{
  "status": "success",
  "origin": {
    "query": "Chicago, IL",
    "name": "Chicago, IL, USA",
    "latitude": 41.881832,
    "longitude": -87.623177
  },
  "destination": {
    "query": "Los Angeles, CA",
    "name": "Los Angeles, CA, USA",
    "latitude": 34.0549076,
    "longitude": -118.242643
  },
  "total_distance_miles": 2018.0,
  "estimated_duration_hours": 35.4,
  "total_fuel_cost_usd": 631.51,
  "total_gallons_consumed": 201.8,
  "fuel_stops_count": 7,
  "fuel_stops": [
    {
      "stop_number": 1,
      "opis_id": "8482",
      "name": "KUM & GO #0370",
      "address": "11910 S 216TH ST & I-80 EXIT 439",
      "city": "Gretna",
      "state": "NE",
      "price_per_gallon": 2.921,
      "distance_from_start_miles": 483.5,
      "gallons_refilled": 48.35,
      "stop_cost_usd": 141.2,
      "latitude": 41.1394,
      "longitude": -96.2483
    },
    {
      "stop_number": 2,
      "opis_id": "4020",
      "name": "AKAL TRAVEL CENTER",
      "address": "1004 LINCOLN HWY & I-80 EXIT 360",
      "city": "Waco",
      "state": "NE",
      "price_per_gallon": 2.799,
      "distance_from_start_miles": 557.9,
      "gallons_refilled": 7.44,
      "stop_cost_usd": 20.82,
      "latitude": 40.8986,
      "longitude": -97.4589
    }
  ],
  "route_geometry": {
    "type": "LineString",
    "coordinates": [
      [-87.623177, 41.881832],
      [-87.625121, 41.881845],
      "..."
    ]
  }
}
```

---

## 🧪 Running Unit & Integration Tests

The test suite validates geocoding accuracy, routing handling, edge cases (short trips vs. cross-country trips), and API responses:

```bash
python manage.py test
```

Expected output:
```
Ran 8 tests in 0.846s

OK
```

---

## 📂 Project Structure

```
spotter/
├── config/                         # Django project configuration
│   ├── settings.py                 # Settings & installed apps
│   ├── urls.py                     # Main URL dispatcher
│   └── wsgi.py
├── routing/                        # Routing & Fuel optimization application
│   ├── services/
│   │   ├── geocoding.py            # Fast offline & fallback geocoder
│   │   ├── routing.py              # OSRM routing & 20ms corridor spatial grid
│   │   └── optimizer.py            # Greedy reachability fuel optimizer
│   ├── templates/
│   │   └── routing/
│   │       └── map.html            # Leaflet.js interactive map & dashboard
│   ├── tests.py                    # Comprehensive test suite (8 tests)
│   ├── urls.py                     # App routing URLs
│   └── views.py                    # REST API view & Web Map view
├── fuel-prices-for-be-assessment.csv # Original fuel prices dataset
├── truckstops.json                 # Pre-enriched coordinates dataset (1.2 MB)
├── preprocess_stations.py          # Script used to generate truckstops.json
├── manage.py
├── requirements.txt
└── README.md
```

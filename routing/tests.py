from django.test import TestCase, Client
from django.urls import reverse
import json

from .services.geocoding import geocode_location
from .services.optimizer import FuelOptimizer

class FuelRoutingTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def test_geocoding_coordinates(self):
        lat, lon, name = geocode_location("41.8781, -87.6298")
        self.assertAlmostEqual(lat, 41.8781, places=2)
        self.assertAlmostEqual(lon, -87.6298, places=2)

    def test_geocoding_city_state(self):
        lat, lon, name = geocode_location("Chicago, IL")
        self.assertIsNotNone(lat)
        self.assertIsNotNone(lon)
        self.assertIn("Chicago", name)

    def test_geocoding_empty(self):
        with self.assertRaises(ValueError):
            geocode_location("")

    def test_fuel_optimizer_short_trip(self):
        # 300 miles trip (<= 500 miles)
        corridor_stations = [
            {
                "opis_id": "1",
                "name": "Cheapest Station",
                "address": "123 Main",
                "city": "Midtown",
                "state": "IL",
                "price": 3.00,
                "lat": 41.0,
                "lon": -87.0,
                "route_mile": 150.0
            },
            {
                "opis_id": "2",
                "name": "Pricier Station",
                "address": "456 Oak",
                "city": "Highway",
                "state": "IL",
                "price": 3.50,
                "lat": 41.5,
                "lon": -87.5,
                "route_mile": 200.0
            }
        ]
        res = FuelOptimizer.optimize(corridor_stations, 300.0)
        self.assertEqual(res["total_distance_miles"], 300.0)
        self.assertEqual(res["total_gallons_consumed"], 30.0)
        # 30 gallons * $3.00 = $90.00
        self.assertEqual(res["total_fuel_cost_usd"], 90.0)
        self.assertEqual(res["fuel_stops_count"], 1)

    def test_fuel_optimizer_long_trip(self):
        # 1200 miles trip (> 500 miles, at least 2 stops required)
        corridor_stations = [
            {"opis_id": "1", "name": "Stop 1", "address": "A", "city": "C1", "state": "S1", "price": 3.20, "lat": 40, "lon": -80, "route_mile": 400.0},
            {"opis_id": "2", "name": "Stop 2", "address": "B", "city": "C2", "state": "S2", "price": 3.10, "lat": 39, "lon": -85, "route_mile": 800.0},
            {"opis_id": "3", "name": "Stop 3", "address": "C", "city": "C3", "state": "S3", "price": 3.40, "lat": 38, "lon": -90, "route_mile": 1100.0},
        ]
        res = FuelOptimizer.optimize(corridor_stations, 1200.0)
        self.assertEqual(res["total_distance_miles"], 1200.0)
        self.assertEqual(res["total_gallons_consumed"], 120.0)
        self.assertGreaterEqual(res["fuel_stops_count"], 2)
        # Verify no hop between stops exceeds 500 miles
        stops = res["fuel_stops"]
        prev_mile = 0.0
        for s in stops:
            hop = s["distance_from_start_miles"] - prev_mile
            self.assertLessEqual(hop, 500.0)
            prev_mile = s["distance_from_start_miles"]

    def test_api_missing_params(self):
        response = self.client.get(reverse("api_route"))
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)

    def test_api_valid_get_request(self):
        response = self.client.get(reverse("api_route"), {
            "start": "Chicago, IL",
            "finish": "Detroit, MI"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("total_distance_miles", data)
        self.assertIn("total_fuel_cost_usd", data)
        self.assertIn("fuel_stops", data)
        self.assertIn("route_geometry", data)
        self.assertEqual(data["route_geometry"]["type"], "LineString")

    def test_map_page_loads(self):
        response = self.client.get(reverse("map_view"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Spotter Fuel Route Optimizer")

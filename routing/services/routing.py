import json
import math
import urllib.request
import urllib.parse
from pathlib import Path

def haversine_miles(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points in miles."""
    r = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c

class RouteService:
    _STATIONS_CACHE = None

    @classmethod
    def get_all_stations(cls):
        if cls._STATIONS_CACHE is None:
            data_path = Path(__file__).resolve().parent.parent.parent / "truckstops.json"
            if not data_path.exists():
                raise FileNotFoundError(f"Truck stops dataset not found at {data_path}")
            with open(data_path, "r", encoding="utf-8") as f:
                cls._STATIONS_CACHE = json.load(f)
        return cls._STATIONS_CACHE

    @classmethod
    def get_route(cls, start_lat: float, start_lon: float, dest_lat: float, dest_lon: float):
        """
        Calls OSRM to get driving route geometry and distance.
        Returns dict with:
          - distance_miles
          - duration_hours
          - coordinates (GeoJSON LineString)
          - cum_dist (miles at each coordinate)
        """
        url = (
            f"http://router.project-osrm.org/route/v1/driving/"
            f"{start_lon},{start_lat};{dest_lon},{dest_lat}"
            f"?overview=full&geometries=geojson"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "SpotterFuelRoutingApp/1.0"})
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as e:
            raise RuntimeError(f"Routing API failed: {str(e)}")

        if data.get("code") != "Ok" or not data.get("routes"):
            raise ValueError(f"OSRM could not find route: {data.get('message', 'No route')}")

        route = data["routes"][0]
        distance_meters = route["distance"]
        duration_seconds = route["duration"]
        coords = route["geometry"]["coordinates"] # [[lon, lat], ...]

        # Compute cumulative distance along route
        cum_dist = [0.0]
        for i in range(1, len(coords)):
            prev_lon, prev_lat = coords[i-1]
            cur_lon, cur_lat = coords[i]
            d = haversine_miles(prev_lat, prev_lon, cur_lat, cur_lon)
            cum_dist.append(cum_dist[-1] + d)

        total_distance_miles = distance_meters * 0.000621371
        duration_hours = duration_seconds / 3600.0

        return {
            "distance_miles": round(total_distance_miles, 2),
            "duration_hours": round(duration_hours, 2),
            "coordinates": coords,
            "cum_dist": cum_dist
        }

    @classmethod
    def find_corridor_stations(cls, route_info, max_corridor_miles: float = 10.0):
        """
        Finds all fuel stations within max_corridor_miles of the route.
        Uses bounding box + spatial grid for sub-50ms execution.
        """
        all_stations = cls.get_all_stations()
        coords = route_info["coordinates"]
        cum_dist = route_info["cum_dist"]

        # 1. Bounding box filter
        lats = [c[1] for c in coords]
        lons = [c[0] for c in coords]
        pad = (max_corridor_miles / 69.0) + 0.1 # convert miles to degrees roughly
        min_lat, max_lat = min(lats) - pad, max(lats) + pad
        min_lon, max_lon = min(lons) - pad, max(lons) + pad

        bbox_stations = [
            s for s in all_stations
            if min_lat <= s["lat"] <= max_lat and min_lon <= s["lon"] <= max_lon
        ]

        if not bbox_stations:
            return []

        # 2. Build spatial grid index on downsampled route coordinates
        # Step size roughly every 1.5 miles
        sample_step = max(1, len(coords) // 1000)
        grid_cell_size = 0.25 # ~17 miles
        grid = {}
        for idx in range(0, len(coords), sample_step):
            lon, lat = coords[idx]
            cell = (int(lat / grid_cell_size), int(lon / grid_cell_size))
            grid.setdefault(cell, []).append((lon, lat, idx))

        # Include the very last coordinate
        last_idx = len(coords) - 1
        last_cell = (int(coords[last_idx][1] / grid_cell_size), int(coords[last_idx][0] / grid_cell_size))
        grid.setdefault(last_cell, []).append((coords[last_idx][0], coords[last_idx][1], last_idx))

        corridor_stations = []

        for s in bbox_stations:
            slat, slon = s["lat"], s["lon"]
            scell = (int(slat / grid_cell_size), int(slon / grid_cell_size))

            # Find nearby route points from neighboring cells
            candidate_points = []
            for dlat in (-1, 0, 1):
                for dlon in (-1, 0, 1):
                    neighbor = (scell[0] + dlat, scell[1] + dlon)
                    if neighbor in grid:
                        candidate_points.extend(grid[neighbor])

            if not candidate_points:
                continue

            # Find closest candidate route point
            best_dist = 999999.0
            best_idx = 0
            for clon, clat, idx in candidate_points:
                d = haversine_miles(slat, slon, clat, clon)
                if d < best_dist:
                    best_dist = d
                    best_idx = idx

            # Local refinement within range [best_idx - sample_step, best_idx + sample_step]
            local_start = max(0, best_idx - sample_step)
            local_end = min(len(coords), best_idx + sample_step + 1)
            for i in range(local_start, local_end):
                clon, clat = coords[i]
                d = haversine_miles(slat, slon, clat, clon)
                if d < best_dist:
                    best_dist = d
                    best_idx = i

            if best_dist <= max_corridor_miles:
                corridor_stations.append({
                    "opis_id": s["opis_id"],
                    "name": s["name"],
                    "address": s["address"],
                    "city": s["city"],
                    "state": s["state"],
                    "price": s["price"],
                    "lat": s["lat"],
                    "lon": s["lon"],
                    "dist_from_route": round(best_dist, 2),
                    "route_mile": round(cum_dist[best_idx], 2)
                })

        # Sort stations along the route
        corridor_stations.sort(key=lambda x: x["route_mile"])
        return corridor_stations

import json
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View

from .services.geocoding import geocode_location
from .services.routing import RouteService
from .services.optimizer import FuelOptimizer

class RoutePlanAPIView(View):
    """
    API Endpoint: /api/route/
    Methods: GET, POST
    Parameters:
      - start: Start location within USA (e.g. "Chicago, IL" or "41.8781, -87.6298")
      - finish: Finish location within USA (e.g. "Los Angeles, CA" or "34.0522, -118.2437")
    """

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_params(self, request):
        if request.method == "POST":
            try:
                data = json.loads(request.body.decode("utf-8")) if request.body else {}
            except Exception:
                data = request.POST.dict()
            start = data.get("start")
            finish = data.get("finish")
        else:
            start = request.GET.get("start")
            finish = request.GET.get("finish")
        return start, finish

    def handle_request(self, request):
        start_input, finish_input = self.get_params(request)

        if not start_input or not finish_input:
            return JsonResponse({
                "error": "Both 'start' and 'finish' parameters are required within the USA.",
                "example": {
                    "start": "New York, NY",
                    "finish": "Miami, FL"
                }
            }, status=400)

        try:
            # 1. Geocode start and finish
            start_lat, start_lon, start_name = geocode_location(start_input)
            dest_lat, dest_lon, dest_name = geocode_location(finish_input)

            # 2. Get route from OSRM (1 network call)
            route_info = RouteService.get_route(start_lat, start_lon, dest_lat, dest_lon)

            # 3. Find fuel stations within route corridor
            corridor_stations = RouteService.find_corridor_stations(route_info, max_corridor_miles=10.0)

            # 4. Optimize fuel stops
            optimization_result = FuelOptimizer.optimize(
                corridor_stations,
                route_info["distance_miles"]
            )

            response_data = {
                "status": "success",
                "origin": {
                    "query": start_input,
                    "name": start_name,
                    "latitude": start_lat,
                    "longitude": start_lon
                },
                "destination": {
                    "query": finish_input,
                    "name": dest_name,
                    "latitude": dest_lat,
                    "longitude": dest_lon
                },
                "total_distance_miles": route_info["distance_miles"],
                "estimated_duration_hours": route_info["duration_hours"],
                "total_fuel_cost_usd": optimization_result["total_fuel_cost_usd"],
                "total_gallons_consumed": optimization_result["total_gallons_consumed"],
                "fuel_stops_count": optimization_result["fuel_stops_count"],
                "fuel_stops": optimization_result["fuel_stops"],
                "route_geometry": {
                    "type": "LineString",
                    "coordinates": route_info["coordinates"]
                }
            }

            return JsonResponse(response_data, status=200)

        except ValueError as ve:
            return JsonResponse({"error": str(ve)}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"Internal error calculating route: {str(e)}"}, status=500)

    def get(self, request):
        return self.handle_request(request)

    def post(self, request):
        return self.handle_request(request)


def map_view(request):
    """Interactive Leaflet UI for plotting the route and stops."""
    return render(request, "routing/map.html")

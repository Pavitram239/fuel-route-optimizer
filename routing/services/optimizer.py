from typing import List, Dict, Any

class FuelOptimizer:
    MAX_RANGE_MILES = 500.0
    MPG = 10.0
    TANK_CAPACITY_GALLONS = 50.0 # 500 miles / 10 mpg

    @classmethod
    def optimize(cls, corridor_stations: List[Dict[str, Any]], total_distance_miles: float) -> Dict[str, Any]:
        """
        Determines the optimal fuel stops and total money spent on fuel.
        
        Assumptions:
          - Maximum vehicle range is 500 miles per full tank.
          - Vehicle fuel efficiency is 10 miles per gallon.
          - Vehicle starts journey with a full tank (500 miles range).
          - Tank is replenished at selected optimal stations along the route.
        """
        total_gallons_consumed = round(total_distance_miles / cls.MPG, 2)

        # Remove duplicate/expensive stations in the same small geographical bucket
        # Bucket by 20-mile segments, keeping the cheapest station in each bucket
        bucket_size = 20.0
        buckets = {}
        for s in corridor_stations:
            b_key = int(s["route_mile"] // bucket_size)
            if b_key not in buckets or s["price"] < buckets[b_key]["price"]:
                buckets[b_key] = s

        pruned_stations = sorted(buckets.values(), key=lambda x: x["route_mile"])

        # Case 1: Trip is within vehicle's single-tank range (<= 500 miles)
        if total_distance_miles <= cls.MAX_RANGE_MILES:
            if pruned_stations:
                # Find cheapest station on the route to calculate cost to replenish fuel
                cheapest_station = min(pruned_stations, key=lambda s: s["price"])
                fuel_cost = round(total_gallons_consumed * cheapest_station["price"], 2)
                stops = [{
                    "stop_number": 1,
                    "opis_id": cheapest_station["opis_id"],
                    "name": cheapest_station["name"],
                    "address": cheapest_station["address"],
                    "city": cheapest_station["city"],
                    "state": cheapest_station["state"],
                    "price_per_gallon": cheapest_station["price"],
                    "distance_from_start_miles": cheapest_station["route_mile"],
                    "gallons_refilled": total_gallons_consumed,
                    "stop_cost_usd": fuel_cost,
                    "latitude": cheapest_station["lat"],
                    "longitude": cheapest_station["lon"]
                }]
            else:
                # Default national average if no station found directly on corridor
                default_price = 3.25
                fuel_cost = round(total_gallons_consumed * default_price, 2)
                stops = []

            return {
                "total_distance_miles": total_distance_miles,
                "total_gallons_consumed": total_gallons_consumed,
                "total_fuel_cost_usd": fuel_cost,
                "fuel_stops_count": len(stops),
                "fuel_stops": stops
            }

        # Case 2: Multi-stop trip (> 500 miles)
        stops = []
        current_pos = 0.0
        current_fuel = cls.MAX_RANGE_MILES
        total_cost = 0.0

        safety_margin = 15.0 # avoid running on exact 0 miles

        while current_pos + current_fuel < total_distance_miles:
            # Find reachable stations within current_fuel range
            max_reachable_mile = current_pos + current_fuel - safety_margin
            reachable = [
                s for s in pruned_stations
                if current_pos < s["route_mile"] <= max_reachable_mile
            ]

            if not reachable:
                # If safety margin was too conservative, try full reach
                reachable = [
                    s for s in pruned_stations
                    if current_pos < s["route_mile"] <= current_pos + current_fuel
                ]

            if not reachable:
                # If still no station (corridor gap), pick the closest station ahead
                ahead = [s for s in pruned_stations if s["route_mile"] > current_pos]
                if ahead:
                    best_station = ahead[0]
                else:
                    break
            else:
                # To minimize stops and cost, prefer candidates in the upper half of the reachable range
                # that have lower prices
                min_progress = current_pos + (cls.MAX_RANGE_MILES * 0.40)
                progress_candidates = [s for s in reachable if s["route_mile"] >= min_progress]
                candidates_pool = progress_candidates if progress_candidates else reachable

                # Select station with the best price, breaking ties by distance
                best_station = min(candidates_pool, key=lambda s: (s["price"], -s["route_mile"]))

            # Drive to the selected station
            dist_leg = best_station["route_mile"] - current_pos
            current_pos = best_station["route_mile"]
            gallons_leg = dist_leg / cls.MPG

            # Refill tank back to full (500 miles)
            gallons_to_refill = round(gallons_leg, 2)
            leg_cost = round(gallons_to_refill * best_station["price"], 2)
            total_cost += leg_cost
            current_fuel = cls.MAX_RANGE_MILES

            stops.append({
                "stop_number": len(stops) + 1,
                "opis_id": best_station["opis_id"],
                "name": best_station["name"],
                "address": best_station["address"],
                "city": best_station["city"],
                "state": best_station["state"],
                "price_per_gallon": best_station["price"],
                "distance_from_start_miles": best_station["route_mile"],
                "gallons_refilled": gallons_to_refill,
                "stop_cost_usd": leg_cost,
                "latitude": best_station["lat"],
                "longitude": best_station["lon"]
            })

        # Final leg to destination
        remaining_dist = total_distance_miles - current_pos
        if remaining_dist > 0:
            final_gallons = round(remaining_dist / cls.MPG, 2)
            last_price = stops[-1]["price_per_gallon"] if stops else 3.25
            final_cost = round(final_gallons * last_price, 2)
            total_cost += final_cost

        return {
            "total_distance_miles": total_distance_miles,
            "total_gallons_consumed": total_gallons_consumed,
            "total_fuel_cost_usd": round(total_cost, 2),
            "fuel_stops_count": len(stops),
            "fuel_stops": stops
        }

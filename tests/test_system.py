"""
Automated Test Suite for Andhra Pradesh Ambulance Optimization System.
Validates dataset integrity, mathematical optimization solvers,
dispatch simulator, and API endpoints.
"""
import unittest
import os
import sys
import json

# Add project root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.algorithms.distance_matrix import (
    haversine_km, estimate_road_distance, estimate_travel_time_minutes
)
from src.algorithms.mclp import MCLPSolver
from src.algorithms.p_median import PMedianSolver
from src.algorithms.hybrid_optimizer import HybridAmbulanceOptimizer
from src.simulation.dispatch_engine import DispatchEngine
from src.simulation.golden_hour_evaluator import GoldenHourEvaluator
from src.api.app import app, DATA_CACHE, load_data

class TestAPAmbulanceOptimizer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        load_data()

    def test_01_dataset_integrity(self):
        """Verify all 26 districts and 679 mandals of Andhra Pradesh."""
        districts = DATA_CACHE.get("districts", [])
        mandals = DATA_CACHE.get("mandals", [])
        blackspots = DATA_CACHE.get("blackspots", [])

        self.assertEqual(len(districts), 26, f"Expected 26 districts, got {len(districts)}")
        self.assertEqual(len(mandals), 679, f"Expected 679 mandals, got {len(mandals)}")
        self.assertGreater(len(blackspots), 100, f"Expected >100 blackspots, got {len(blackspots)}")

        # Geographic boundary sanity check for Andhra Pradesh (Lat: 12.6 to 19.5, Lng: 76.5 to 85.0)
        for m in mandals:
            self.assertTrue(12.5 <= m["lat"] <= 19.5, f"Mandal {m['mandal_name']} lat {m['lat']} out of AP bounds")
            self.assertTrue(76.5 <= m["lng"] <= 85.0, f"Mandal {m['mandal_name']} lng {m['lng']} out of AP bounds")

    def test_02_distance_and_eta_calculations(self):
        """Test Haversine and road network distance and ETA estimations."""
        # Distance between Vijayawada (16.5062, 80.6480) and Guntur (16.3067, 80.4365) ~ 31 km
        straight_dist = haversine_km(16.5062, 80.6480, 16.3067, 80.4365)
        self.assertTrue(25.0 <= straight_dist <= 38.0, f"Unexpected straight distance: {straight_dist}")

        road_dist = estimate_road_distance(16.5062, 80.6480, 16.3067, 80.4365, "National Highway")
        self.assertGreater(road_dist, straight_dist, "Road distance should include circuity factor")

        eta = estimate_travel_time_minutes(16.5062, 80.6480, 16.3067, 80.4365, "National Highway")
        self.assertGreater(eta, 0.0)
        self.assertLess(eta, 60.0)

    def test_03_mclp_solver(self):
        """Test Maximal Covering Location Problem solver."""
        # Use Guntur mandals as a test case
        guntur_mandals = [m for m in DATA_CACHE["mandals"] if m["district"] == "Guntur"]
        self.assertGreater(len(guntur_mandals), 0)

        demands = [{
            "id": m["mandal_id"], "name": m["mandal_name"],
            "lat": m["lat"], "lng": m["lng"], "weight": m.get("demand_weight", 1.0)
        } for m in guntur_mandals]

        candidates = [{
            "id": f"CAND-{m['mandal_id']}", "name": m["mandal_name"],
            "lat": m["lat"], "lng": m["lng"], "mandal": m["mandal_name"], "district": "Guntur"
        } for m in guntur_mandals]

        solver = MCLPSolver(demands, candidates, radius_km=15.0)
        res = solver.solve(p_ambulances=8)

        self.assertEqual(len(res["selected_stations"]), 8)
        self.assertGreater(res["node_coverage_pct"], 50.0, "8 ambulances with 15km radius should cover >50% of Guntur")
        self.assertGreater(res["weighted_coverage_pct"], 50.0)

    def test_04_p_median_solver(self):
        """Test p-Median response time minimization solver."""
        krishna_mandals = [m for m in DATA_CACHE["mandals"] if m["district"] == "Krishna"]
        self.assertGreater(len(krishna_mandals), 0)

        demands = [{
            "id": m["mandal_id"], "name": m["mandal_name"],
            "lat": m["lat"], "lng": m["lng"], "weight": m.get("demand_weight", 1.0)
        } for m in krishna_mandals]

        candidates = [{
            "id": f"CAND-{m['mandal_id']}", "name": m["mandal_name"],
            "lat": m["lat"], "lng": m["lng"], "mandal": m["mandal_name"], "district": "Krishna"
        } for m in krishna_mandals]

        solver = PMedianSolver(demands, candidates)
        res = solver.solve(p_ambulances=10)

        self.assertEqual(len(res["selected_stations"]), 10)
        self.assertLess(res["average_response_time_minutes"], 25.0)
        self.assertGreater(res["golden_hour_compliance_pct"], 50.0)

    def test_05_dispatch_engine(self):
        """Test live incident dispatch and route calculation."""
        test_stations = [
            {"station_id": "AMB-01", "name": "Vijayawada Center", "lat": 16.5062, "lng": 80.6480, "district": "NTR", "mandal": "Vijayawada", "allocated_vehicle_type": "ALS"},
            {"station_id": "AMB-02", "name": "Mangalagiri Base", "lat": 16.4382, "lng": 80.5631, "district": "Guntur", "mandal": "Mangalagiri", "allocated_vehicle_type": "BLS"}
        ]
        engine = DispatchEngine(test_stations)

        # Accident near Mangalagiri (16.4400, 80.5650)
        dispatch_result = engine.dispatch_nearest_ambulance(16.4400, 80.5650, severity="Critical")

        self.assertEqual(dispatch_result["dispatched_ambulance"]["station_id"], "AMB-02")
        self.assertLess(dispatch_result["response_metrics"]["estimated_eta_minutes"], 10.0)
        self.assertEqual(dispatch_result["response_metrics"]["golden_hour_status"], "GOLDEN_HOUR_MET")
        self.assertGreater(len(dispatch_result["route_waypoints"]), 2)

    def test_06_flask_api_endpoints(self):
        """Test Flask REST API routes."""
        client = app.test_client()

        # 1. Test index page
        res = client.get("/")
        self.assertEqual(res.status_code, 200)

        # 2. Test get districts
        res = client.get("/api/districts")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["total_districts"], 26)

        # 3. Test get mandals
        res = client.get("/api/mandals?district=Visakhapatnam")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["district"], "Visakhapatnam")
        self.assertEqual(data["count"], 11)

        # 4. Test optimization API
        res = client.post("/api/optimize", json={
            "district": "Visakhapatnam",
            "num_ambulances": 6,
            "radius_km": 10.0,
            "algorithm": "hybrid"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["optimization"]["selected_stations"]), 6)

        # 5. Test dispatch API
        res = client.post("/api/dispatch", json={
            "lat": 17.6868, "lng": 83.2185, "severity": "Critical"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertIn("dispatched_ambulance", data["dispatch"])

    def test_07_village_apis(self):
        """Test Village dataset coverage and autocomplete search API."""
        villages = DATA_CACHE.get("villages", [])
        self.assertGreaterEqual(len(villages), 10000, f"Expected >=10000 villages, got {len(villages)}")

        client = app.test_client()

        # 1. Test villages endpoint by district
        res = client.get("/api/villages?district=Guntur&limit=50")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertGreater(data["total"], 0)
        self.assertLessEqual(len(data["villages"]), 50)
        self.assertEqual(data["villages"][0]["district"], "Guntur")

        # 2. Test autocomplete search
        res = client.get("/api/search_village?q=kaza")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertGreater(len(data["results"]), 0)
        first_result = data["results"][0]
        self.assertIn("village_name", first_result)
        self.assertIn("mandal", first_result)
        self.assertIn("district", first_result)
        self.assertIn("lat", first_result)
        self.assertIn("lng", first_result)

if __name__ == "__main__":
    unittest.main()

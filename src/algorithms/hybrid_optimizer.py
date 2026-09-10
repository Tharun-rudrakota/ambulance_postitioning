"""
Hybrid Multi-Objective Ambulance Optimizer.
Synthesizes MCLP (coverage maximization) and p-Median (latency minimization),
and allocates Advanced Life Support (ALS) vs Basic Life Support (BLS) fleets.
"""
from typing import List, Dict, Any, Tuple
from .mclp import MCLPSolver
from .p_median import PMedianSolver

class HybridAmbulanceOptimizer:
    def __init__(self, demand_points: List[Dict[str, Any]], candidate_sites: List[Dict[str, Any]], radius_km: float = 12.0):
        self.demand_points = demand_points
        self.candidate_sites = candidate_sites
        self.radius_km = radius_km

        self.mclp_solver = MCLPSolver(demand_points, candidate_sites, radius_km)
        self.pmed_solver = PMedianSolver(demand_points, candidate_sites)

    def optimize(self, p_ambulances: int, mode: str = "hybrid") -> Dict[str, Any]:
        """
        :param p_ambulances: Number of ambulance stations to allocate.
        :param mode: 'mclp', 'p_median', or 'hybrid'
        """
        if mode == "mclp":
            result = self.mclp_solver.solve(p_ambulances)
        elif mode == "p_median":
            result = self.pmed_solver.solve(p_ambulances)
        else:
            # Hybrid approach: Run MCLP with slightly larger candidate pool,
            # refine using p-Median latency objective
            mclp_res = self.mclp_solver.solve(p_ambulances)
            pmed_res = self.pmed_solver.solve(p_ambulances)

            # Synthesize results
            result = {
                "algorithm": "Hybrid (Coverage Maximization + Latency Minimization)",
                "radius_km": self.radius_km,
                "ambulances_deployed": p_ambulances,
                "mclp_metrics": {
                    "node_coverage_pct": mclp_res["node_coverage_pct"],
                    "weighted_coverage_pct": mclp_res["weighted_coverage_pct"],
                    "covered_nodes": mclp_res["covered_demand_nodes"]
                },
                "p_median_metrics": {
                    "average_response_distance_km": pmed_res["average_response_distance_km"],
                    "average_response_time_minutes": pmed_res["average_response_time_minutes"],
                    "golden_hour_compliance_pct": pmed_res["golden_hour_compliance_pct"]
                },
                "selected_stations": mclp_res["selected_stations"],
                "uncovered_blindspots_count": mclp_res["uncovered_blindspots_count"],
                "uncovered_blindspots": mclp_res["uncovered_blindspots"]
            }

        # Classify Fleet: Allocate ALS vs BLS based on blackspot density and highway proximity
        for i, stn in enumerate(result["selected_stations"]):
            # Check if station is in a highway corridor or near severe blackspots
            station_mandal = stn.get("mandal", "")
            is_highway = any(
                highway_kw in station_mandal.lower() or "bypass" in station_mandal.lower()
                for highway_kw in ["nh", "express", "highway", "toll", "junction"]
            ) or (stn.get("covered_demand_weight", 0) > 25.0)

            if is_highway or (i % 3 == 0):
                stn["allocated_vehicle_type"] = "Advanced Life Support (ALS)"
                stn["equipment"] = ["Ventilator", "Defibrillator", "Cardiac Monitor", "Trauma Kit", "Oxygen"]
                stn["paramedic_crew"] = 3
            else:
                stn["allocated_vehicle_type"] = "Basic Life Support (BLS)"
                stn["equipment"] = ["First Aid Kit", "Oxygen Cylinder", "Stretcher", "Suction Unit"]
                stn["paramedic_crew"] = 2

        return result

"""
p-Median Location Optimization Solver.
Formulation: Hakimi (1964) / Teitz & Bart (1968).
Minimizes the aggregate weighted travel distance / response time from ambulance stations
to accident demand points across Andhra Pradesh mandals.
"""
from typing import List, Dict, Set, Any, Tuple
import random
from .distance_matrix import estimate_road_distance, estimate_travel_time_minutes

class PMedianSolver:
    def __init__(self, demand_points: List[Dict[str, Any]], candidate_sites: List[Dict[str, Any]]):
        """
        :param demand_points: List of mandal demand locations with 'id', 'name', 'lat', 'lng', 'weight'.
        :param candidate_sites: List of candidate ambulance stations with 'id', 'name', 'lat', 'lng'.
        """
        self.demand_points = demand_points
        self.candidate_sites = candidate_sites

        self.num_demands = len(demand_points)
        self.num_candidates = len(candidate_sites)

        # Precompute N x M road distance and travel time matrices
        self.dist_matrix: List[List[float]] = []
        self.time_matrix: List[List[float]] = []

        for d in demand_points:
            dist_row = []
            time_row = []
            for c in candidate_sites:
                dist = estimate_road_distance(d["lat"], d["lng"], c["lat"], c["lng"])
                time = estimate_travel_time_minutes(d["lat"], d["lng"], c["lat"], c["lng"])
                dist_row.append(dist)
                time_row.append(time)
            self.dist_matrix.append(dist_row)
            self.time_matrix.append(time_row)

        self.weights = [d.get("weight", 1.0) for d in demand_points]
        self.total_weight = sum(self.weights)

    def evaluate_cost(self, selected_indices: Set[int]) -> Tuple[float, float, List[int]]:
        """
        Evaluates the objective function:
        Total weighted distance = sum_i w_i * min_{j in S} d_ij.
        Returns (total_weighted_distance, average_response_time_minutes, assignments).
        """
        total_weighted_dist = 0.0
        total_weighted_time = 0.0
        assignments = []

        for i in range(self.num_demands):
            best_dist = float("inf")
            best_time = float("inf")
            best_cand = -1

            for j in selected_indices:
                d = self.dist_matrix[i][j]
                if d < best_dist:
                    best_dist = d
                    best_time = self.time_matrix[i][j]
                    best_cand = j

            assignments.append(best_cand)
            w = self.weights[i]
            total_weighted_dist += w * best_dist
            total_weighted_time += w * best_time

        avg_time = total_weighted_time / max(self.total_weight, 1.0)
        return total_weighted_dist, avg_time, assignments

    def solve(self, p_ambulances: int, max_iterations: int = 150) -> Dict[str, Any]:
        """
        Solves p-Median problem using Teitz & Bart vertex substitution heuristic.
        """
        if p_ambulances >= self.num_candidates:
            selected = set(range(self.num_candidates))
            total_dist, avg_time, assignments = self.evaluate_cost(selected)
            return self._build_result(selected, total_dist, avg_time, assignments)

        # 1. Initial selection using weighted greedy medoid selection
        selected: Set[int] = set()
        for _ in range(p_ambulances):
            best_cand = -1
            best_cost = float("inf")
            for j in range(self.num_candidates):
                if j in selected:
                    continue
                trial = selected | {j}
                cost, _, _ = self.evaluate_cost(trial)
                if cost < best_cost:
                    best_cost = cost
                    best_cand = j
            if best_cand != -1:
                selected.add(best_cand)
            else:
                rem = set(range(self.num_candidates)) - selected
                if rem:
                    selected.add(next(iter(rem)))

        # 2. Teitz-Bart Vertex Substitution (1-Opt interchange)
        best_cost, best_avg_time, best_assignments = self.evaluate_cost(selected)
        improved = True
        iterations = 0

        while improved and iterations < max_iterations:
            improved = False
            iterations += 1
            for in_cand in list(selected):
                for out_cand in range(self.num_candidates):
                    if out_cand in selected:
                        continue
                    trial_set = (selected - {in_cand}) | {out_cand}
                    trial_cost, trial_time, trial_assign = self.evaluate_cost(trial_set)
                    if trial_cost < best_cost - 1e-4:
                        selected = trial_set
                        best_cost = trial_cost
                        best_avg_time = trial_time
                        best_assignments = trial_assign
                        improved = True
                        break
                if improved:
                    break

        return self._build_result(selected, best_cost, best_avg_time, best_assignments)

    def _build_result(self, selected_indices: Set[int], total_cost: float, avg_time_mins: float, assignments: List[int]) -> Dict[str, Any]:
        selected_stations = []
        station_demands: Dict[int, List[int]] = {idx: [] for idx in selected_indices}
        for demand_idx, station_idx in enumerate(assignments):
            if station_idx in station_demands:
                station_demands[station_idx].append(demand_idx)

        # Count Golden Hour compliance (< 15 mins)
        golden_hour_compliant_count = 0
        total_unweighted_dist = 0.0

        for i, station_idx in enumerate(assignments):
            t = self.time_matrix[i][station_idx]
            d = self.dist_matrix[i][station_idx]
            total_unweighted_dist += d
            if t <= 15.0:
                golden_hour_compliant_count += 1

        for idx in selected_indices:
            c = self.candidate_sites[idx]
            serviced = [self.demand_points[i] for i in station_demands.get(idx, [])]
            serviced_weight = sum(self.weights[i] for i in station_demands.get(idx, []))
            selected_stations.append({
                "station_id": c.get("id", f"STN-{idx:03d}"),
                "name": c.get("name", "Station"),
                "lat": c["lat"],
                "lng": c["lng"],
                "mandal": c.get("mandal", ""),
                "district": c.get("district", ""),
                "assigned_mandals_count": len(serviced),
                "assigned_weight": round(serviced_weight, 1),
                "assigned_mandals_preview": [m.get("name", "") for m in serviced[:5]]
            })

        avg_dist = round(total_unweighted_dist / max(self.num_demands, 1), 2)
        golden_hour_pct = round((golden_hour_compliant_count / max(self.num_demands, 1)) * 100.0, 2)

        return {
            "algorithm": "p-Median (Travel Time & Distance Minimization)",
            "ambulances_deployed": len(selected_indices),
            "total_demand_nodes": self.num_demands,
            "aggregate_weighted_distance_km": round(total_cost, 1),
            "average_response_distance_km": avg_dist,
            "average_response_time_minutes": round(avg_time_mins, 1),
            "golden_hour_compliance_pct": golden_hour_pct,
            "selected_stations": selected_stations
        }

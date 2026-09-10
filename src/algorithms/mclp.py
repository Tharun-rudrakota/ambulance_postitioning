"""
Maximal Covering Location Problem (MCLP) Solver.
Formulation: Church & ReVelle (1974).
Maximizes the total demand/accident risk covered within a Golden Hour distance threshold R
using P ambulance base stations.
"""
from typing import List, Dict, Set, Any, Tuple
import math
from .distance_matrix import estimate_road_distance

class MCLPSolver:
    def __init__(self, demand_points: List[Dict[str, Any]], candidate_sites: List[Dict[str, Any]], radius_km: float = 12.0):
        """
        :param demand_points: List of mandals or blackspots with 'id', 'name', 'lat', 'lng', 'weight'.
        :param candidate_sites: List of possible ambulance base locations with 'id', 'name', 'lat', 'lng'.
        :param radius_km: Maximum response distance for Golden Hour coverage.
        """
        self.demand_points = demand_points
        self.candidate_sites = candidate_sites
        self.radius_km = radius_km

        # Precompute coverage map:
        # coverage_set[j] = set of demand point indices covered by candidate site j
        self.coverage_sets: List[Set[int]] = []
        for c in candidate_sites:
            covered = set()
            for i, d in enumerate(demand_points):
                dist = estimate_road_distance(d["lat"], d["lng"], c["lat"], c["lng"])
                if dist <= radius_km:
                    covered.add(i)
            self.coverage_sets.append(covered)

        self.total_demand_weight = sum(d.get("weight", 1.0) for d in demand_points)

    def evaluate_solution(self, selected_indices: Set[int]) -> Tuple[float, Set[int]]:
        """Calculates total covered weight and set of covered demand indices."""
        covered_demands: Set[int] = set()
        for idx in selected_indices:
            covered_demands.update(self.coverage_sets[idx])
        covered_weight = sum(self.demand_points[i].get("weight", 1.0) for i in covered_demands)
        return covered_weight, covered_demands

    def solve(self, p_ambulances: int, max_iterations: int = 200) -> Dict[str, Any]:
        """
        Solves MCLP using Greedy Adaptive Selection followed by 1-Opt Local Search (Neighborhood Exchange).
        Guarantees fast, robust, and near-optimal solution.
        """
        num_candidates = len(self.candidate_sites)
        if p_ambulances >= num_candidates:
            selected_indices = set(range(num_candidates))
            covered_weight, covered_demands = self.evaluate_solution(selected_indices)
            return self._build_result(selected_indices, covered_weight, covered_demands)

        # 1. Greedy Initialization: Iteratively pick candidate that adds the maximum uncovered weight
        selected: Set[int] = set()
        currently_covered: Set[int] = set()

        for _ in range(p_ambulances):
            best_cand = -1
            best_additional_weight = -1.0
            for j in range(num_candidates):
                if j in selected:
                    continue
                new_demands = self.coverage_sets[j] - currently_covered
                add_weight = sum(self.demand_points[i].get("weight", 1.0) for i in new_demands)
                if add_weight > best_additional_weight:
                    best_additional_weight = add_weight
                    best_cand = j

            if best_cand != -1:
                selected.add(best_cand)
                currently_covered.update(self.coverage_sets[best_cand])
            else:
                # If all covered or no improvement, pick arbitrary unselected
                remaining = set(range(num_candidates)) - selected
                if remaining:
                    selected.add(next(iter(remaining)))

        # 2. Local Search (1-Opt Exchange): Swap one selected station with an unselected candidate
        improved = True
        iterations = 0
        best_weight, best_covered = self.evaluate_solution(selected)

        while improved and iterations < max_iterations:
            improved = False
            iterations += 1
            for in_cand in list(selected):
                for out_cand in range(num_candidates):
                    if out_cand in selected:
                        continue
                    # Trial swap
                    trial_selected = (selected - {in_cand}) | {out_cand}
                    trial_weight, trial_covered = self.evaluate_solution(trial_selected)
                    if trial_weight > best_weight:
                        selected = trial_selected
                        best_weight = trial_weight
                        best_covered = trial_covered
                        improved = True
                        break
                if improved:
                    break

        return self._build_result(selected, best_weight, best_covered)

    def _build_result(self, selected_indices: Set[int], covered_weight: float, covered_demands: Set[int]) -> Dict[str, Any]:
        """Formats comprehensive optimization output."""
        selected_stations = []
        for idx in selected_indices:
            c = self.candidate_sites[idx]
            covered_points = [self.demand_points[i] for i in self.coverage_sets[idx]]
            selected_stations.append({
                "station_id": c.get("id", f"STN-{idx:03d}"),
                "name": c.get("name", "Station"),
                "lat": c["lat"],
                "lng": c["lng"],
                "mandal": c.get("mandal", ""),
                "district": c.get("district", ""),
                "coverage_radius_km": self.radius_km,
                "covered_demand_count": len(covered_points),
                "covered_demand_weight": round(sum(p.get("weight", 1.0) for p in covered_points), 1),
                "covered_points_preview": [p.get("name", "") for p in covered_points[:5]]
            })

        uncovered_indices = set(range(len(self.demand_points))) - covered_demands
        uncovered_demands = [self.demand_points[i] for i in uncovered_indices]

        coverage_percentage = round((covered_weight / max(self.total_demand_weight, 1.0)) * 100.0, 2)
        node_coverage_pct = round((len(covered_demands) / max(len(self.demand_points), 1)) * 100.0, 2)

        return {
            "algorithm": "MCLP (Maximal Covering Location Problem)",
            "radius_km": self.radius_km,
            "ambulances_deployed": len(selected_indices),
            "total_demand_nodes": len(self.demand_points),
            "covered_demand_nodes": len(covered_demands),
            "node_coverage_pct": node_coverage_pct,
            "total_demand_weight": round(self.total_demand_weight, 1),
            "covered_demand_weight": round(covered_weight, 1),
            "weighted_coverage_pct": coverage_percentage,
            "selected_stations": selected_stations,
            "uncovered_blindspots_count": len(uncovered_demands),
            "uncovered_blindspots": uncovered_demands[:10]  # top 10 blind spots
        }

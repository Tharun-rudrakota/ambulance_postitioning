"""
Comparative Evaluator: Baseline vs Optimized Ambulance Deployment.
Quantifies Golden Hour coverage gain, response latency reduction,
and high-risk blackspot protection across Andhra Pradesh.
"""
from typing import List, Dict, Any
from ..algorithms.distance_matrix import estimate_road_distance, estimate_travel_time_minutes

class GoldenHourEvaluator:
    def __init__(self, mandals: List[Dict[str, Any]], blackspots: List[Dict[str, Any]]):
        self.mandals = mandals
        self.blackspots = blackspots

    def evaluate_fleet(self, fleet: List[Dict[str, Any]], threshold_minutes: float = 15.0) -> Dict[str, Any]:
        """
        Evaluates an ambulance fleet across all mandals and blackspots.
        """
        if not fleet:
            return {"error": "Fleet is empty"}

        # 1. Mandal coverage evaluation
        mandal_times = []
        mandal_distances = []
        covered_mandals_count = 0
        severely_delayed_mandals = []

        total_weighted_time = 0.0
        total_mandal_weight = 0.0

        for m in self.mandals:
            w = m.get("demand_weight", 1.0)
            total_mandal_weight += w

            best_time = float("inf")
            best_dist = float("inf")
            for amb in fleet:
                d = estimate_road_distance(m["lat"], m["lng"], amb["lat"], amb["lng"])
                t = estimate_travel_time_minutes(m["lat"], m["lng"], amb["lat"], amb["lng"])
                if t < best_time:
                    best_time = t
                    best_dist = d

            mandal_times.append(best_time)
            mandal_distances.append(best_dist)
            total_weighted_time += w * best_time

            if best_time <= threshold_minutes:
                covered_mandals_count += 1
            elif best_time > 25.0:
                severely_delayed_mandals.append({
                    "mandal": m.get("mandal_name", ""),
                    "district": m.get("district", ""),
                    "response_time_minutes": best_time,
                    "risk_score": m.get("risk_score", 0)
                })

        avg_mandal_time = total_weighted_time / max(total_mandal_weight, 1.0)
        avg_mandal_dist = sum(mandal_distances) / max(len(mandal_distances), 1)
        golden_hour_coverage_pct = (covered_mandals_count / max(len(self.mandals), 1)) * 100.0

        # 2. Blackspot protection evaluation
        blackspot_covered_count = 0
        total_blackspot_weight = sum(b.get("weight", 1.0) for b in self.blackspots)
        covered_bs_weight = 0.0

        for b in self.blackspots:
            best_time = min(
                estimate_travel_time_minutes(b["lat"], b["lng"], amb["lat"], amb["lng"])
                for amb in fleet
            )
            if best_time <= threshold_minutes:
                blackspot_covered_count += 1
                covered_bs_weight += b.get("weight", 1.0)

        bs_coverage_pct = (blackspot_covered_count / max(len(self.blackspots), 1)) * 100.0 if self.blackspots else 100.0
        bs_weight_coverage_pct = (covered_bs_weight / max(total_blackspot_weight, 1.0)) * 100.0 if self.blackspots else 100.0

        return {
            "ambulances_deployed": len(fleet),
            "golden_hour_threshold_mins": threshold_minutes,
            "average_response_time_minutes": round(avg_mandal_time, 1),
            "average_response_distance_km": round(avg_mandal_dist, 1),
            "max_response_time_minutes": round(max(mandal_times) if mandal_times else 0, 1),
            "golden_hour_mandal_coverage_pct": round(golden_hour_coverage_pct, 1),
            "covered_mandals_count": covered_mandals_count,
            "total_mandals": len(self.mandals),
            "blackspot_coverage_pct": round(bs_coverage_pct, 1),
            "blackspot_weight_coverage_pct": round(bs_weight_coverage_pct, 1),
            "covered_blackspots_count": blackspot_covered_count,
            "total_blackspots": len(self.blackspots),
            "severely_delayed_mandals_count": len(severely_delayed_mandals),
            "severely_delayed_mandals_sample": severely_delayed_mandals[:6]
        }

    def compare(self, baseline_fleet: List[Dict[str, Any]], optimized_fleet: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Computes comparative deltas between baseline and optimized fleet.
        """
        base_metrics = self.evaluate_fleet(baseline_fleet)
        opt_metrics = self.evaluate_fleet(optimized_fleet)

        time_reduction_mins = round(base_metrics["average_response_time_minutes"] - opt_metrics["average_response_time_minutes"], 1)
        time_reduction_pct = round((time_reduction_mins / max(base_metrics["average_response_time_minutes"], 0.1)) * 100.0, 1)

        coverage_gain_pct = round(opt_metrics["golden_hour_mandal_coverage_pct"] - base_metrics["golden_hour_mandal_coverage_pct"], 1)
        bs_gain_pct = round(opt_metrics["blackspot_coverage_pct"] - base_metrics["blackspot_coverage_pct"], 1)

        return {
            "baseline": base_metrics,
            "optimized": opt_metrics,
            "deltas": {
                "response_time_reduction_minutes": time_reduction_mins,
                "response_time_reduction_pct": time_reduction_pct,
                "coverage_gain_pct": coverage_gain_pct,
                "blackspot_protection_gain_pct": bs_gain_pct,
                "blindspots_eliminated": base_metrics["severely_delayed_mandals_count"] - opt_metrics["severely_delayed_mandals_count"]
            }
        }

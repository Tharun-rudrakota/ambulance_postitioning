#!/usr/bin/env python3
"""
Command-Line Interface (CLI) for Andhra Pradesh Ambulance Optimization System.
Provides headless optimization, batch reporting, Golden Hour evaluation,
and command-center web server launcher.
"""
import argparse
import sys
import os
import json

# Ensure project root is in python path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.algorithms.hybrid_optimizer import HybridAmbulanceOptimizer
from src.simulation.golden_hour_evaluator import GoldenHourEvaluator
from src.simulation.dispatch_engine import DispatchEngine
from src.api.app import app, load_data, DATA_CACHE

def run_cli_optimization(district: str, ambulances: int, radius: float, algorithm: str, export_path: str = None):
    """Executes optimization and outputs a comprehensive executive summary."""
    load_data()

    print("\n" + "=" * 80)
    print(" AMBULANCE POSITIONING OPTIMIZATION SYSTEM ")
    print("=" * 80)
    print(f" Target District : {district}")
    print(f" Algorithm       : {algorithm.upper()}")
    print(f" Fleet Size (P)  : {ambulances} ambulances")
    print(f" Coverage Radius : {radius} km (Golden Hour Threshold)")
    print("-" * 80)

    # Filter data
    if district and district.upper() != "ALL":
        mandals = [m for m in DATA_CACHE["mandals"] if m["district"].lower() == district.lower()]
        blackspots = [b for b in DATA_CACHE["blackspots"] if b["district"].lower() == district.lower()]
        base_fleet = [a for a in DATA_CACHE["baseline_ambulances"] if a["district"].lower() == district.lower()]
    else:
        mandals = DATA_CACHE["mandals"]
        blackspots = DATA_CACHE["blackspots"]
        base_fleet = DATA_CACHE["baseline_ambulances"]

    if not mandals:
        print(f"[Error] District '{district}' not found. Please check district name.")
        return

    # Build demand and candidate structures
    demand_points = []
    for m in mandals:
        demand_points.append({
            "id": m["mandal_id"],
            "name": f"{m['mandal_name']} Mandal",
            "lat": m["lat"],
            "lng": m["lng"],
            "weight": m.get("demand_weight", 1.0)
        })

    for b in blackspots:
        demand_points.append({
            "id": b["blackspot_id"],
            "name": b["location_name"],
            "lat": b["lat"],
            "lng": b["lng"],
            "weight": b.get("weight", 2.5)
        })

    candidate_sites = []
    for m in mandals:
        candidate_sites.append({
            "id": f"STN-{m['mandal_id']}",
            "name": f"{m['mandal_name']} Station Base",
            "lat": m["lat"],
            "lng": m["lng"],
            "mandal": m["mandal_name"],
            "district": m["district"]
        })

    print(f"[*] Analyzing {len(mandals)} Mandals and {len(blackspots)} Accident Blackspots...")
    opt = HybridAmbulanceOptimizer(demand_points, candidate_sites, radius)
    p_to_solve = min(ambulances, len(candidate_sites))
    res = opt.optimize(p_to_solve, mode=algorithm)

    # Run comparative evaluation
    evaluator = GoldenHourEvaluator(mandals, blackspots)
    active_fleet = [
        {"ambulance_id": s["station_id"], "lat": s["lat"], "lng": s["lng"]}
        for s in res["selected_stations"]
    ]
    comparison = evaluator.compare(base_fleet, active_fleet)

    b = comparison["baseline"]
    o = comparison["optimized"]
    d = comparison["deltas"]

    # Display Metrics Table
    print("\n" + "-" * 80)
    print(" PERFORMANCE BENCHMARK: BASELINE vs AI-OPTIMIZED")
    print("-" * 80)
    print(f"{'Performance Metric':<35} | {'Baseline (Current)':<18} | {'AI Optimized':<18} | {'Improvement'}")
    print("-" * 80)
    print(f"{'Golden Hour Mandal Coverage (%)':<35} | {b['golden_hour_mandal_coverage_pct']:<17}% | {o['golden_hour_mandal_coverage_pct']:<17}% | +{d['coverage_gain_pct']}%")
    print(f"{'Average Emergency ETA (mins)':<35} | {b['average_response_time_minutes']:<17}m | {o['average_response_time_minutes']:<17}m | -{d['response_time_reduction_minutes']} mins")
    print(f"{'Blackspots Shielded (%)':<35} | {b['blackspot_coverage_pct']:<17}% | {o['blackspot_coverage_pct']:<17}% | +{d['blackspot_protection_gain_pct']}%")
    print(f"{'Covered Mandals (<15 min)':<35} | {b['covered_mandals_count']}/{b['total_mandals']:<15} | {o['covered_mandals_count']}/{o['total_mandals']:<15} | +{o['covered_mandals_count'] - b['covered_mandals_count']} mandals")
    print(f"{'Severely Delayed Blindspots':<35} | {b['severely_delayed_mandals_count']:<18} | {o['severely_delayed_mandals_count']:<18} | -{d['blindspots_eliminated']} resolved")
    print("-" * 80)

    # Display Recommended Station Placements
    print("\n[*] TOP RECOMMENDED AMBULANCE BASE LOCATIONS:")
    print(f"{'#':<3} | {'Station Name':<30} | {'Mandal':<18} | {'Coords (Lat, Lng)':<20} | {'Fleet Class'}")
    print("-" * 88)
    for idx, stn in enumerate(res["selected_stations"][:15], 1):
        coords = f"({stn['lat']:.4f}, {stn['lng']:.4f})"
        v_class = stn.get("allocated_vehicle_type", "BLS")
        print(f"{idx:<3} | {stn['name'][:28]:<30} | {stn['mandal'][:16]:<18} | {coords:<20} | {v_class}")

    if len(res["selected_stations"]) > 15:
        print(f"    ... and {len(res['selected_stations']) - 15} additional stationed units.")

    # Export if requested
    if export_path:
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump({
                "district": district,
                "algorithm": algorithm,
                "parameters": {"ambulances": ambulances, "radius_km": radius},
                "comparison": comparison,
                "stations": res["selected_stations"]
            }, f, indent=2)
        print(f"\n[+] Full optimization report exported to: {export_path}")

    print("\n" + "=" * 80)
    print(" To launch the interactive visual dashboard, run: python optimize.py --serve")
    print("=" * 80 + "\n")

def main():
    parser = argparse.ArgumentParser(
        description="Andhra Pradesh Optimal Ambulance Positioning System CLI"
    )
    parser.add_argument("--district", type=str, default="Guntur",
                        help="Target district name (e.g., 'Guntur', 'Visakhapatnam', 'NTR', 'Chittoor') or 'ALL'")
    parser.add_argument("--ambulances", "-p", type=int, default=14,
                        help="Number of ambulances to position (default: 14)")
    parser.add_argument("--radius", "-r", type=float, default=12.0,
                        help="Golden Hour coverage radius in km (default: 12.0 km)")
    parser.add_argument("--algorithm", "-a", type=str, default="hybrid",
                        choices=["hybrid", "mclp", "p_median"],
                        help="Optimization algorithm: 'hybrid', 'mclp', or 'p_median'")
    parser.add_argument("--export", type=str, default=None,
                        help="Path to export results as JSON")
    parser.add_argument("--serve", action="store_true",
                        help="Launch the interactive Web Command Center dashboard")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5000)),
                        help="Port for web dashboard (default: 5000 or $PORT)")

    args = parser.parse_args()

    if args.serve:
        print(f"\n[+] Launching AP 108 Emergency Command Center on http://127.0.0.1:{args.port}")
        app.run(host="0.0.0.0", port=args.port, debug=False)
    else:
        run_cli_optimization(
            district=args.district,
            ambulances=args.ambulances,
            radius=args.radius,
            algorithm=args.algorithm,
            export_path=args.export
        )

if __name__ == "__main__":
    main()

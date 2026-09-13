"""
Flask Web Application and REST API for Andhra Pradesh Ambulance Optimizer.
Serves interactive Leaflet Command Center Dashboard and API endpoints.
"""
import os
import sys
import json
from flask import Flask, render_template, request, jsonify, send_file
import io
import csv

from ..algorithms.mclp import MCLPSolver
from ..algorithms.p_median import PMedianSolver
from ..algorithms.hybrid_optimizer import HybridAmbulanceOptimizer
from ..simulation.dispatch_engine import DispatchEngine, MAJOR_TRAUMA_CENTERS
from ..simulation.golden_hour_evaluator import GoldenHourEvaluator

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)

# Global in-memory cache
DATA_CACHE = {
    "districts": [],
    "mandals": [],
    "blackspots": [],
    "baseline_ambulances": [],
    "active_fleet": []
}

def load_data():
    """Loads AP datasets from JSON files."""
    dm_path = os.path.join(DATA_DIR, "ap_districts_mandals.json")
    bs_path = os.path.join(DATA_DIR, "ap_highways_blackspots.json")
    amb_path = os.path.join(DATA_DIR, "ap_baseline_ambulances.json")

    if not os.path.exists(dm_path) or not os.path.exists(bs_path):
        from ..data.dataset_generator import generate_complete_dataset
        generate_complete_dataset(DATA_DIR)

    with open(dm_path, "r", encoding="utf-8") as f:
        dm_data = json.load(f)
        DATA_CACHE["districts"] = dm_data.get("districts", [])
        DATA_CACHE["mandals"] = dm_data.get("mandals", [])

    with open(bs_path, "r", encoding="utf-8") as f:
        bs_data = json.load(f)
        DATA_CACHE["blackspots"] = bs_data.get("blackspots", [])

    with open(amb_path, "r", encoding="utf-8") as f:
        amb_data = json.load(f)
        DATA_CACHE["baseline_ambulances"] = amb_data.get("ambulances", [])
        DATA_CACHE["active_fleet"] = DATA_CACHE["baseline_ambulances"].copy()

# Initialize data on startup
load_data()
dispatch_engine = DispatchEngine(DATA_CACHE["active_fleet"])

@app.route("/")
def index():
    """Renders the main Command Center dashboard."""
    district_names = [d["district_name"] for d in DATA_CACHE["districts"]]
    return render_template(
        "index.html",
        districts=sorted(district_names),
        total_districts=len(DATA_CACHE["districts"]),
        total_mandals=len(DATA_CACHE["mandals"]),
        total_blackspots=len(DATA_CACHE["blackspots"]),
        baseline_ambulances_count=len(DATA_CACHE["baseline_ambulances"])
    )

@app.route("/api/districts", methods=["GET"])
def get_districts():
    """Returns all 26 Andhra Pradesh districts."""
    return jsonify({
        "status": "success",
        "total_districts": len(DATA_CACHE["districts"]),
        "districts": DATA_CACHE["districts"]
    })

@app.route("/api/mandals", methods=["GET"])
def get_mandals():
    """Returns mandals filtered by district or all 679 mandals."""
    district = request.args.get("district", "ALL")
    if district and district != "ALL":
        filtered = [m for m in DATA_CACHE["mandals"] if m["district"].lower() == district.lower()]
    else:
        filtered = DATA_CACHE["mandals"]
    return jsonify({
        "status": "success",
        "count": len(filtered),
        "district": district,
        "mandals": filtered
    })

@app.route("/api/blackspots", methods=["GET"])
def get_blackspots():
    """Returns accident blackspots filtered by district or all."""
    district = request.args.get("district", "ALL")
    if district and district != "ALL":
        filtered = [b for b in DATA_CACHE["blackspots"] if b["district"].lower() == district.lower()]
    else:
        filtered = DATA_CACHE["blackspots"]
    return jsonify({
        "status": "success",
        "count": len(filtered),
        "district": district,
        "blackspots": filtered
    })

@app.route("/api/baseline", methods=["GET"])
def get_baseline_ambulances():
    """Returns baseline 108 ambulance deployment."""
    district = request.args.get("district", "ALL")
    if district and district != "ALL":
        filtered = [a for a in DATA_CACHE["baseline_ambulances"] if a["district"].lower() == district.lower()]
    else:
        filtered = DATA_CACHE["baseline_ambulances"]
    return jsonify({
        "status": "success",
        "count": len(filtered),
        "ambulances": filtered
    })

@app.route("/api/trauma_centers", methods=["GET"])
def get_trauma_centers():
    """Returns major Apex and Regional Trauma Centers."""
    return jsonify({
        "status": "success",
        "trauma_centers": MAJOR_TRAUMA_CENTERS
    })

@app.route("/api/optimize", methods=["POST"])
def optimize_positioning():
    """
    Solves ambulance positioning using MCLP, p-Median, or Hybrid model.
    JSON payload:
    {
        "district": "Guntur" or "ALL",
        "num_ambulances": 14,
        "radius_km": 12.0,
        "algorithm": "mclp" | "p_median" | "hybrid"
    }
    """
    data = request.get_json() or {}
    district = data.get("district", "ALL")
    num_ambulances = int(data.get("num_ambulances", 12))
    radius_km = float(data.get("radius_km", 12.0))
    algorithm = data.get("algorithm", "hybrid").lower()

    # Filter demand points (mandals + blackspots) and candidate sites
    if district and district != "ALL":
        mandals = [m for m in DATA_CACHE["mandals"] if m["district"].lower() == district.lower()]
        blackspots = [b for b in DATA_CACHE["blackspots"] if b["district"].lower() == district.lower()]
    else:
        mandals = DATA_CACHE["mandals"]
        blackspots = DATA_CACHE["blackspots"]

    # Format demand points: combine mandal centroids and highway blackspots
    demand_points = []
    for m in mandals:
        demand_points.append({
            "id": m["mandal_id"],
            "name": f"{m['mandal_name']} Mandal HQ",
            "lat": m["lat"],
            "lng": m["lng"],
            "weight": m.get("demand_weight", 1.0),
            "type": "Mandal Node"
        })

    for b in blackspots:
        demand_points.append({
            "id": b["blackspot_id"],
            "name": b["location_name"],
            "lat": b["lat"],
            "lng": b["lng"],
            "weight": b.get("weight", 2.0),
            "type": "Accident Blackspot"
        })

    # Candidate sites: all mandal headquarters and major highway nodal intersections
    candidate_sites = []
    for m in mandals:
        candidate_sites.append({
            "id": f"CAND-{m['mandal_id']}",
            "name": f"{m['mandal_name']} CHC/Base",
            "lat": m["lat"],
            "lng": m["lng"],
            "mandal": m["mandal_name"],
            "district": m["district"]
        })

    # Run optimizer
    hybrid_opt = HybridAmbulanceOptimizer(demand_points, candidate_sites, radius_km)
    opt_result = hybrid_opt.optimize(p_ambulances=min(num_ambulances, len(candidate_sites)), mode=algorithm)

    # Update active fleet in cache and dispatch engine
    active_fleet = []
    for stn in opt_result["selected_stations"]:
        active_fleet.append({
            "ambulance_id": stn["station_id"],
            "name": stn["name"],
            "lat": stn["lat"],
            "lng": stn["lng"],
            "district": stn["district"],
            "mandal": stn["mandal"],
            "allocated_vehicle_type": stn.get("allocated_vehicle_type", "Basic Life Support (BLS)")
        })
    DATA_CACHE["active_fleet"] = active_fleet
    dispatch_engine.update_fleet(active_fleet)

    # Run comparative evaluation against baseline
    evaluator = GoldenHourEvaluator(mandals, blackspots)
    base_fleet_district = [
        a for a in DATA_CACHE["baseline_ambulances"]
        if district == "ALL" or a["district"].lower() == district.lower()
    ]
    comparison = evaluator.compare(base_fleet_district, active_fleet)

    return jsonify({
        "status": "success",
        "district": district,
        "optimization": opt_result,
        "evaluation": comparison
    })

@app.route("/api/dispatch", methods=["POST"])
def dispatch_incident():
    """
    Simulates real-time accident dispatch.
    JSON payload:
    {
        "lat": 16.312,
        "lng": 80.451,
        "severity": "Critical"
    }
    """
    data = request.get_json() or {}
    lat = float(data.get("lat", 16.312))
    lng = float(data.get("lng", 80.451))
    severity = data.get("severity", "Critical")

    dispatch_res = dispatch_engine.dispatch_nearest_ambulance(lat, lng, severity)
    return jsonify({
        "status": "success",
        "dispatch": dispatch_res
    })

@app.route("/api/export_report", methods=["GET"])
def export_report():
    """Exports the current optimal station recommendations as a CSV file."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Station ID", "Station Name", "District", "Mandal", "Latitude", "Longitude",
        "Vehicle Type", "Paramedics", "Equipment", "Covered Demands Count"
    ])

    for stn in DATA_CACHE["active_fleet"]:
        writer.writerow([
            stn.get("ambulance_id", ""),
            stn.get("name", ""),
            stn.get("district", ""),
            stn.get("mandal", ""),
            stn.get("lat", ""),
            stn.get("lng", ""),
            stn.get("allocated_vehicle_type", "Basic Life Support (BLS)"),
            3 if "ALS" in stn.get("allocated_vehicle_type", "") else 2,
            "Ventilator, Defibrillator, Cardiac Monitor" if "ALS" in stn.get("allocated_vehicle_type", "") else "Oxygen, First Aid Kit, Stretcher",
            stn.get("covered_demand_count", "N/A")
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="AP_Optimal_Ambulance_Recommendations.csv"
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting AP Ambulance Optimizer Web Command Center on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)

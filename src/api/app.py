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
import time

from ..algorithms.mclp import MCLPSolver
from ..algorithms.p_median import PMedianSolver
from ..algorithms.hybrid_optimizer import HybridAmbulanceOptimizer
from ..simulation.dispatch_engine import DispatchEngine, MAJOR_TRAUMA_CENTERS
from ..simulation.golden_hour_evaluator import GoldenHourEvaluator

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
from data.dataset_generator import clamp_to_ap_land

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
    "active_fleet": [],
    "villages": [],
    "manual_ambulances": []
}

def load_data():
    """Loads AP datasets from JSON files."""
    dm_path = os.path.join(DATA_DIR, "ap_districts_mandals.json")
    bs_path = os.path.join(DATA_DIR, "ap_highways_blackspots.json")
    amb_path = os.path.join(DATA_DIR, "ap_baseline_ambulances.json")
    vil_path = os.path.join(DATA_DIR, "ap_villages.json")
    man_path = os.path.join(DATA_DIR, "ap_manual_ambulances.json")

    if not os.path.exists(dm_path) or not os.path.exists(bs_path) or not os.path.exists(vil_path):
        from data.dataset_generator import generate_complete_dataset
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

    if os.path.exists(vil_path):
        with open(vil_path, "r", encoding="utf-8") as f:
            vil_data = json.load(f)
            DATA_CACHE["villages"] = vil_data.get("villages", [])

    # Load persistent manually placed ambulances
    if os.path.exists(man_path):
        try:
            with open(man_path, "r", encoding="utf-8") as f:
                DATA_CACHE["manual_ambulances"] = json.load(f)
        except Exception as e:
            print(f"Warning: Error loading manual ambulances: {e}")
            DATA_CACHE["manual_ambulances"] = []
    else:
        DATA_CACHE["manual_ambulances"] = []
        with open(man_path, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

    # Prepend manually placed ambulances to active fleet
    for man_stn in DATA_CACHE["manual_ambulances"]:
        DATA_CACHE["active_fleet"].insert(0, man_stn)

    # Build statewide ambulance pool: baseline 108 stations + every mandal's CHC/PHC 108 emergency station
    statewide = list(DATA_CACHE["baseline_ambulances"])
    for m in DATA_CACHE.get("mandals", []):
        statewide.append({
            "station_id": f"MDL-108-{m['mandal_id']}",
            "name": f"{m['mandal_name']} 108 Emergency Post",
            "district": m["district"],
            "mandal": m["mandal_name"],
            "lat": m["lat"],
            "lng": m["lng"],
            "allocated_vehicle_type": "Basic Life Support (BLS)",
            "is_mandal_post": True
        })
    DATA_CACHE["statewide_ambulances"] = statewide

# Initialize data on startup
load_data()
dispatch_engine = DispatchEngine(
    DATA_CACHE["active_fleet"],
    statewide_stations=DATA_CACHE.get("statewide_ambulances", [])
)
dispatch_engine.set_custom_stations(DATA_CACHE.get("manual_ambulances", []))

@app.route("/")
def index():
    """Renders the main Command Center dashboard."""
    district_names = [d["district_name"] for d in DATA_CACHE["districts"]]
    return render_template(
        "index.html",
        districts=sorted(district_names),
        total_districts=len(DATA_CACHE["districts"]),
        total_mandals=len(DATA_CACHE["mandals"]),
        total_villages=len(DATA_CACHE["villages"]),
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

def match_district(district1: str, district2: str) -> bool:
    """Case-insensitive and alias-resilient district matching."""
    if not district1 or not district2:
        return False
    aliases = {
        "nellore": "sps nellore",
        "sps nellore": "sps nellore",
        "sri potti sriramulu nellore": "sps nellore",
        "kadapa": "ysr kadapa",
        "ysr kadapa": "ysr kadapa",
        "ysr": "ysr kadapa",
        "konaseema": "dr. b.r. ambedkar konaseema",
        "dr. b.r. ambedkar konaseema": "dr. b.r. ambedkar konaseema",
        "manyam": "parvathipuram manyam",
        "parvathipuram manyam": "parvathipuram manyam",
        "alluri": "alluri sitharama raju",
        "asr": "alluri sitharama raju",
        "alluri sitharama raju": "alluri sitharama raju"
    }
    k1 = aliases.get(district1.strip().lower(), district1.strip().lower())
    k2 = aliases.get(district2.strip().lower(), district2.strip().lower())
    return k1 == k2

@app.route("/api/mandals", methods=["GET"])
def get_mandals():
    """Returns mandals filtered by district or all 679 mandals."""
    district = request.args.get("district", "ALL")
    if district and district != "ALL":
        filtered = [m for m in DATA_CACHE["mandals"] if match_district(m["district"], district)]
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
        filtered = [b for b in DATA_CACHE["blackspots"] if match_district(b["district"], district)]
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
        filtered = [a for a in DATA_CACHE["baseline_ambulances"] if match_district(a["district"], district)]
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

def compute_district_hull(points):
    """Computes 2D convex hull of coordinates for district boundary polygon."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]

@app.route("/api/district_details", methods=["GET"])
def get_district_details():
    """Returns total district summary, mandals, village counts, and perimeter hull."""
    district = request.args.get("district", "ALL")
    if not district or district == "ALL":
        return jsonify({
            "status": "success",
            "is_statewide": True,
            "total_districts": len(DATA_CACHE["districts"]),
            "total_mandals": len(DATA_CACHE["mandals"]),
            "total_villages": len(DATA_CACHE["villages"])
        })

    dist_info = next((d for d in DATA_CACHE["districts"] if match_district(d["district_name"], district)), None)
    mandals = [m for m in DATA_CACHE["mandals"] if match_district(m["district"], district)]
    villages = [v for v in DATA_CACHE["villages"] if match_district(v["district"], district)]
    blackspots = [b for b in DATA_CACHE["blackspots"] if match_district(b["district"], district)]
    baseline_ambs = [a for a in DATA_CACHE["baseline_ambulances"] if match_district(a["district"], district)]

    coords = [(v["lat"], v["lng"]) for v in villages] + [(m["lat"], m["lng"]) for m in mandals]
    hull = compute_district_hull(coords)

    mandal_stats = []
    for m in mandals:
        m_vils = [v for v in villages if v["mandal"].lower() == m["mandal_name"].lower()]
        mandal_stats.append({
            "mandal_id": m["mandal_id"],
            "mandal_name": m["mandal_name"],
            "lat": m["lat"],
            "lng": m["lng"],
            "population": m.get("population", 0),
            "tier": m.get("tier", "Rural"),
            "village_count": len(m_vils),
            "danger_spots_count": sum(1 for v in m_vils if "danger_spot" in v),
            "risk_score": m.get("risk_score", 5.0)
        })

    return jsonify({
        "status": "success",
        "is_statewide": False,
        "district": dist_info["district_name"] if dist_info else district,
        "headquarters": dist_info.get("headquarters", "") if dist_info else "",
        "lat": dist_info.get("lat", mandals[0]["lat"] if mandals else 0) if dist_info else 0,
        "lng": dist_info.get("lng", mandals[0]["lng"] if mandals else 0) if dist_info else 0,
        "highways": dist_info.get("highways", []) if dist_info else [],
        "total_mandals": len(mandals),
        "total_villages": len(villages),
        "total_danger_spots": sum(1 for v in villages if "danger_spot" in v),
        "total_blackspots": len(blackspots),
        "total_baseline_ambulances": len(baseline_ambs),
        "boundary_hull": hull,
        "mandals": mandal_stats
    })

@app.route("/api/villages", methods=["GET"])
def get_villages():
    """Returns villages filtered by district and optional mandal."""
    district = request.args.get("district", "ALL")
    mandal = request.args.get("mandal", "ALL")
    default_limit = 10000 if (district and district != "ALL") else 2500
    limit = int(request.args.get("limit", default_limit))

    villages = DATA_CACHE.get("villages", [])
    if district and district != "ALL":
        villages = [v for v in villages if match_district(v["district"], district)]
    if mandal and mandal != "ALL":
        villages = [v for v in villages if v["mandal"].lower() == mandal.lower()]

    return jsonify({
        "status": "success",
        "total": len(villages),
        "district": district,
        "mandal": mandal,
        "villages": villages[:limit]
    })

@app.route("/api/search_village", methods=["GET"])
def search_village():
    """Autocomplete search for any village in Andhra Pradesh by name."""
    query = request.args.get("q", "").strip().lower()
    if not query or len(query) < 2:
        return jsonify({"status": "success", "results": []})

    results = []
    for v in DATA_CACHE.get("villages", []):
        if query in v["village_name"].lower() or query in v["mandal"].lower():
            results.append({
                "village_id": v["village_id"],
                "village_name": v["village_name"],
                "mandal": v["mandal"],
                "district": v["district"],
                "lat": v["lat"],
                "lng": v["lng"],
                "population": v["population"],
                "gram_panchayat": v.get("gram_panchayat", ""),
                "has_phc": v.get("has_phc", False),
                "label": f"{v['village_name']} ({v['mandal']} Mdl, {v['district']} Dt)"
            })
            if len(results) >= 25:
                break

    return jsonify({
        "status": "success",
        "query": query,
        "results": results
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
        mandals = [m for m in DATA_CACHE["mandals"] if match_district(m["district"], district)]
        blackspots = [b for b in DATA_CACHE["blackspots"] if match_district(b["district"], district)]
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
    p_alloc = min(num_ambulances, len(candidate_sites))
    opt_result = hybrid_opt.optimize(p_ambulances=p_alloc, mode=algorithm)

    # For the selected district, generate ready stations for ALL mandals so NO village is left uncovered!
    selected_mandals = {stn["mandal"].lower() for stn in opt_result["selected_stations"]}
    ready_stations = []
    for m in mandals:
        if m["mandal_name"].lower() not in selected_mandals:
            ready_stations.append({
                "station_id": f"READY-{m['mandal_id']}",
                "name": f"{m['mandal_name']} 108 Ready Emergency Station",
                "lat": m["lat"],
                "lng": m["lng"],
                "district": m["district"],
                "mandal": m["mandal_name"],
                "allocated_vehicle_type": "Basic Life Support (BLS) - Ready Post",
                "paramedic_crew": 2,
                "equipment": ["Oxygen Cylinder", "First Aid Kit", "Stretcher", "Suction Unit"],
                "is_ready_station": True,
                "coverage_radius_km": radius_km
            })

    opt_result["ready_mandal_stations"] = ready_stations

    # Update active fleet in cache and dispatch engine:
    # Combine manual custom stations + selected priority ALS stations + all complementary ready mandal stations!
    active_fleet = []
    # 1. Custom manually placed ambulances have highest priority
    for stn in DATA_CACHE.get("manual_ambulances", []):
        active_fleet.append({
            "ambulance_id": stn["station_id"],
            "name": stn["name"],
            "lat": stn["lat"],
            "lng": stn["lng"],
            "district": stn.get("district", ""),
            "mandal": stn.get("mandal", ""),
            "allocated_vehicle_type": stn.get("allocated_vehicle_type", "Advanced Life Support (ALS)"),
            "is_manual": True
        })

    for stn in opt_result["selected_stations"]:
        active_fleet.append({
            "ambulance_id": stn["station_id"],
            "name": stn["name"],
            "lat": stn["lat"],
            "lng": stn["lng"],
            "district": stn["district"],
            "mandal": stn["mandal"],
            "allocated_vehicle_type": stn.get("allocated_vehicle_type", "Advanced Life Support (ALS)")
        })
    for stn in ready_stations:
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
    dispatch_engine.set_custom_stations(DATA_CACHE.get("manual_ambulances", []))
    opt_result["manual_stations"] = DATA_CACHE.get("manual_ambulances", [])

    # Run comparative evaluation against baseline
    evaluator = GoldenHourEvaluator(mandals, blackspots)
    base_fleet_district = [
        a for a in DATA_CACHE["baseline_ambulances"]
        if district == "ALL" or match_district(a["district"], district)
    ]
    comparison = evaluator.compare(base_fleet_district, active_fleet)

    return jsonify({
        "status": "success",
        "district": district,
        "optimization": opt_result,
        "evaluation": comparison
    })

def save_manual_ambulances_to_disk():
    """Persists all manually placed ambulances to data/ap_manual_ambulances.json."""
    man_path = os.path.join(DATA_DIR, "ap_manual_ambulances.json")
    try:
        with open(man_path, "w", encoding="utf-8") as f:
            json.dump(DATA_CACHE.get("manual_ambulances", []), f, indent=2)
    except Exception as e:
        print(f"Error saving manual ambulances: {e}")

def find_nearest_mandal(lat: float, lng: float):
    """Finds the closest mandal for any given coordinates."""
    best_mandal = None
    min_d = float("inf")
    for m in DATA_CACHE.get("mandals", []):
        d = (m["lat"] - lat)**2 + (m["lng"] - lng)**2
        if d < min_d:
            min_d = d
            best_mandal = m
    return best_mandal

@app.route("/api/manual_ambulances", methods=["GET"])
def get_manual_ambulances():
    """Returns all saved manually placed 108 ambulances."""
    district = request.args.get("district", "ALL")
    manual_ambs = DATA_CACHE.get("manual_ambulances", [])
    if district and district != "ALL":
        filtered = [a for a in manual_ambs if match_district(a.get("district", ""), district)]
    else:
        filtered = manual_ambs

    return jsonify({
        "status": "success",
        "total": len(filtered),
        "district": district,
        "ambulances": filtered
    })

@app.route("/api/manual_ambulances", methods=["POST"])
def add_manual_ambulance():
    """
    Permanently saves a manually placed 108 ambulance to disk and registers in active fleet.
    JSON payload:
    {
        "lat": float,
        "lng": float,
        "name": str,
        "district": str (optional),
        "mandal": str (optional),
        "vehicle_type": str (optional),
        "radius_km": float (optional)
    }
    """
    data = request.get_json() or {}
    raw_lat = float(data.get("lat", 16.312))
    raw_lng = float(data.get("lng", 80.451))
    safe_lat = round(raw_lat, 5)
    safe_lng = clamp_to_ap_land(safe_lat, raw_lng)

    mandal = data.get("mandal", "").strip()
    district = data.get("district", "").strip()

    # Automatically resolve nearest mandal and district if missing or generic
    if not mandal or mandal in ["Local", "General", ""] or not district or district in ["General", ""]:
        nearest_m = find_nearest_mandal(safe_lat, safe_lng)
        if nearest_m:
            mandal = nearest_m["mandal_name"]
            district = nearest_m["district"]
        else:
            mandal = mandal or "Local Mandal"
            district = district or "Andhra Pradesh"

    custom_name = data.get("name", "").strip()
    if not custom_name:
        custom_name = f"{mandal} Custom 108 Base Station"

    vehicle_type = data.get("vehicle_type", "Advanced Life Support (ALS) - Custom Base")
    radius_km = float(data.get("radius_km", 12.0))
    station_id = f"MANUAL-108-{int(time.time()*1000)%1000000}"

    new_stn = {
        "station_id": station_id,
        "ambulance_id": station_id,
        "name": custom_name,
        "district": district,
        "mandal": mandal,
        "lat": safe_lat,
        "lng": safe_lng,
        "allocated_vehicle_type": vehicle_type,
        "paramedic_crew": 3 if "ALS" in vehicle_type else 2,
        "equipment": ["Ventilator", "Defibrillator", "Oxygen Cylinder", "Stretcher", "Suction Unit"] if "ALS" in vehicle_type else ["Oxygen Cylinder", "First Aid Kit", "Stretcher"],
        "coverage_radius_km": radius_km,
        "is_manual": True,
        "created_at": int(time.time() * 1000)
    }

    # Store in memory cache
    manual_list = DATA_CACHE.get("manual_ambulances", [])
    # Replace existing station if same coordinates or ID
    manual_list = [s for s in manual_list if s.get("station_id") != station_id]
    manual_list.insert(0, new_stn)
    DATA_CACHE["manual_ambulances"] = manual_list

    # Update active fleet
    if "active_fleet" in DATA_CACHE:
        DATA_CACHE["active_fleet"] = [s for s in DATA_CACHE["active_fleet"] if s.get("station_id") != station_id]
        DATA_CACHE["active_fleet"].insert(0, new_stn)

    # Register into live dispatch engine
    dispatch_engine.add_custom_station(new_stn)

    # Save permanently to disk
    save_manual_ambulances_to_disk()

    return jsonify({
        "status": "success",
        "message": f"108 Ambulance permanently stationed at {custom_name}!",
        "ambulance": new_stn,
        "total_manual": len(manual_list)
    })

@app.route("/api/manual_ambulances/<station_id>", methods=["DELETE"])
def delete_manual_ambulance(station_id):
    """Permanently deletes a manually placed ambulance from disk and memory."""
    manual_list = DATA_CACHE.get("manual_ambulances", [])
    initial_len = len(manual_list)
    updated_list = [s for s in manual_list if s.get("station_id") != station_id and s.get("ambulance_id") != station_id]

    if len(updated_list) == initial_len:
        return jsonify({
            "status": "error",
            "message": f"Ambulance station {station_id} not found."
        }), 404

    DATA_CACHE["manual_ambulances"] = updated_list
    if "active_fleet" in DATA_CACHE:
        DATA_CACHE["active_fleet"] = [s for s in DATA_CACHE["active_fleet"] if s.get("station_id") != station_id and s.get("ambulance_id") != station_id]

    dispatch_engine.remove_custom_station(station_id)
    save_manual_ambulances_to_disk()

    return jsonify({
        "status": "success",
        "message": f"Ambulance station {station_id} deleted permanently.",
        "total_manual": len(updated_list)
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

@app.route("/api/place_ambulance_nearer", methods=["POST"])
def place_ambulance_nearer():
    """
    Positions a Rapid Response 108 Ambulance right at or near
    a village or danger spot to immediately reduce response time and save the Golden Hour.
    Permanently persists the station so it never disappears on refresh.
    """
    data = request.get_json() or {}
    raw_lat = float(data.get("lat", 16.312))
    raw_lng = float(data.get("lng", 80.451))
    safe_lat = round(raw_lat, 5)
    safe_lng = clamp_to_ap_land(safe_lat, raw_lng)

    location_name = data.get("location_name", "Village Danger Spot")
    district = data.get("district", "General")
    mandal = data.get("mandal", "Local")

    if not mandal or mandal in ["Local", "General"] or not district or district in ["General"]:
        nearest_m = find_nearest_mandal(safe_lat, safe_lng)
        if nearest_m:
            mandal = nearest_m["mandal_name"]
            district = nearest_m["district"]

    stn_id = f"RAPID-108-{int(time.time()*1000)%100000}"
    new_stn = {
        "station_id": stn_id,
        "ambulance_id": stn_id,
        "name": f"{location_name} Rapid 108 Post",
        "district": district,
        "mandal": mandal,
        "lat": safe_lat,
        "lng": safe_lng,
        "allocated_vehicle_type": "Advanced Life Support (ALS) - Rapid Post",
        "paramedic_crew": 3,
        "equipment": ["Ventilator", "Defibrillator", "Oxygen Cylinder", "Stretcher", "Suction Unit"],
        "coverage_radius_km": 12.0,
        "is_custom_nearer": True,
        "is_manual": True,
        "created_at": int(time.time() * 1000)
    }

    # Add to custom stations and save persistently
    dispatch_engine.add_custom_station(new_stn)
    manual_list = DATA_CACHE.get("manual_ambulances", [])
    manual_list = [s for s in manual_list if s.get("station_id") != stn_id]
    manual_list.insert(0, new_stn)
    DATA_CACHE["manual_ambulances"] = manual_list

    if "active_fleet" in DATA_CACHE:
        DATA_CACHE["active_fleet"].insert(0, new_stn)

    save_manual_ambulances_to_disk()

    # Immediately re-run dispatch for this spot
    dispatch_res = dispatch_engine.dispatch_nearest_ambulance(safe_lat, safe_lng, severity="Critical")

    return jsonify({
        "status": "success",
        "station": new_stn,
        "dispatch": dispatch_res,
        "total_manual": len(manual_list),
        "message": f"Rapid 108 Ambulance stationed permanently at {location_name}!"
    })

@app.route("/api/village_danger_spots", methods=["GET"])
def get_village_danger_spots():
    """Returns danger spots for villages filtered by district."""
    district = request.args.get("district", "ALL")
    default_limit = 10000 if (district and district != "ALL") else 2500
    limit = int(request.args.get("limit", default_limit))
    villages = DATA_CACHE.get("villages", [])
    if district and district != "ALL":
        villages = [v for v in villages if match_district(v["district"], district)]

    danger_spots = []
    for v in villages[:limit]:
        if "danger_spot" in v:
            ds = dict(v["danger_spot"])
            ds["village_id"] = v.get("village_id")
            ds["village_name"] = v.get("village_name")
            ds["mandal"] = v.get("mandal")
            ds["district"] = v.get("district")
            ds["population"] = v.get("population")
            danger_spots.append(ds)

    return jsonify({
        "status": "success",
        "total": len(danger_spots),
        "district": district,
        "danger_spots": danger_spots
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

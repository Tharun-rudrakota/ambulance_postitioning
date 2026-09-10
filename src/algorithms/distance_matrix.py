"""
Distance, Road Network Circuity, and Travel Time Estimation Engine.
Accounts for Andhra Pradesh highway speeds, ghat road curvatures,
and rural road circuity factors.
"""
import math
from typing import List, Tuple, Dict

# Road network circuity factor: real road distance vs great-circle haversine
ROAD_CIRCUITY_FACTORS = {
    "National Highway": 1.18,
    "State Highway": 1.28,
    "Mandal / Rural Road": 1.38,
    "Ghat / Hill Section": 1.65,
    "Default": 1.25
}

# Average emergency response speeds in km/h with sirens
EMERGENCY_SPEEDS_KMH = {
    "National Highway": 75.0,
    "State Highway": 55.0,
    "Urban Corridors": 38.0,
    "Rural Road": 45.0,
    "Ghat Section": 32.0,
    "Default": 50.0
}

# Turn-out dispatch reaction time (sirens on, crew ready)
DISPATCH_LATENCY_MINUTES = 1.5

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two geographic coordinates in km."""
    R = 6371.0  # Earth's radius in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return R * c

def estimate_road_distance(lat1: float, lon1: float, lat2: float, lon2: float, road_type: str = "Default") -> float:
    """
    Estimates actual road travel distance in kilometers incorporating
    topographical circuity and road curvature factors.
    """
    straight_km = haversine_km(lat1, lon1, lat2, lon2)
    circuity = ROAD_CIRCUITY_FACTORS.get(road_type, ROAD_CIRCUITY_FACTORS["Default"])
    return round(straight_km * circuity, 2)

def estimate_travel_time_minutes(lat1: float, lon1: float, lat2: float, lon2: float, road_type: str = "Default") -> float:
    """
    Calculates Estimated Time of Arrival (ETA) in minutes for an emergency ambulance.
    """
    road_km = estimate_road_distance(lat1, lon1, lat2, lon2, road_type)
    speed = EMERGENCY_SPEEDS_KMH.get(road_type, EMERGENCY_SPEEDS_KMH["Default"])
    transit_minutes = (road_km / speed) * 60.0
    return round(transit_minutes + DISPATCH_LATENCY_MINUTES, 1)

def compute_distance_matrix(demand_coords: List[Tuple[float, float]], candidate_coords: List[Tuple[float, float]]) -> List[List[float]]:
    """
    Constructs an N x M distance matrix between N demand points and M candidate stations.
    """
    matrix = []
    for d_lat, d_lng in demand_coords:
        row = []
        for c_lat, c_lng in candidate_coords:
            dist = estimate_road_distance(d_lat, d_lng, c_lat, c_lng)
            row.append(dist)
        matrix.append(row)
    return matrix

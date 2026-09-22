"""
Live Emergency Incident Dispatch and Ambulance Routing Engine.
Matches incoming road accident emergency calls with the optimal
nearest ambulance and computes response route, ETA, Golden Hour status,
and the closest referral hospital (Area Hospital / District Hospital / Apex GGH).
"""
from typing import List, Dict, Any, Optional
import time
import math
from ..algorithms.distance_matrix import estimate_road_distance, estimate_travel_time_minutes

# Comprehensive Network of Referral Hospitals Across ALL 26 Districts of Andhra Pradesh
# Includes District Hospitals (DH), Area Hospitals (AH), Govt Medical Colleges (GGH/RIMS),
# and Apex Trauma Centers so that every mandal has a nearby emergency center within 5-25 km.
ALL_AP_EMERGENCY_HOSPITALS = [
    # Srikakulam
    {"name": "RIMS Govt General Hospital", "district": "Srikakulam", "town": "Srikakulam", "lat": 18.2969, "lng": 83.8968, "level": "Level-2 Regional Trauma"},
    {"name": "District Hospital Tekkali", "district": "Srikakulam", "town": "Tekkali", "lat": 18.6120, "lng": 84.2310, "level": "District Hospital"},
    {"name": "Area Hospital Palasa", "district": "Srikakulam", "town": "Palasa", "lat": 18.7710, "lng": 84.4120, "level": "Area Hospital"},
    {"name": "Area Hospital Sompeta", "district": "Srikakulam", "town": "Sompeta", "lat": 18.9320, "lng": 84.5920, "level": "Area Hospital"},

    # Vizianagaram
    {"name": "Govt Medical College & GGH Vizianagaram", "district": "Vizianagaram", "town": "Vizianagaram", "lat": 18.1133, "lng": 83.4072, "level": "Level-2 Regional Trauma"},
    {"name": "Area Hospital Bobbili", "district": "Vizianagaram", "town": "Bobbili", "lat": 18.5720, "lng": 83.3650, "level": "Area Hospital"},
    {"name": "Area Hospital Cheepurupalli", "district": "Vizianagaram", "town": "Cheepurupalli", "lat": 18.3120, "lng": 83.5710, "level": "Area Hospital"},

    # Parvathipuram Manyam
    {"name": "District Hospital Parvathipuram", "district": "Parvathipuram Manyam", "town": "Parvathipuram", "lat": 18.7796, "lng": 83.4284, "level": "District Hospital"},
    {"name": "Area Hospital Palakonda", "district": "Parvathipuram Manyam", "town": "Palakonda", "lat": 18.6010, "lng": 83.7540, "level": "Area Hospital"},
    {"name": "Area Hospital Salur", "district": "Parvathipuram Manyam", "town": "Salur", "lat": 18.5280, "lng": 83.2120, "level": "Area Hospital"},

    # Alluri Sitharama Raju
    {"name": "District Hospital Paderu", "district": "Alluri Sitharama Raju", "town": "Paderu", "lat": 18.0827, "lng": 82.6657, "level": "District Hospital"},
    {"name": "Area Hospital Rampachodavaram", "district": "Alluri Sitharama Raju", "town": "Rampachodavaram", "lat": 17.4420, "lng": 81.7750, "level": "Area Hospital"},
    {"name": "Area Hospital Araku Valley", "district": "Alluri Sitharama Raju", "town": "Araku", "lat": 18.3280, "lng": 82.8810, "level": "Area Hospital"},
    {"name": "CHC Chintoor", "district": "Alluri Sitharama Raju", "town": "Chintoor", "lat": 17.7280, "lng": 81.3920, "level": "Community Health Centre"},

    # Visakhapatnam
    {"name": "King George Hospital (KGH) & Apex Trauma Center", "district": "Visakhapatnam", "town": "Visakhapatnam", "lat": 17.7088, "lng": 83.3052, "level": "Level-1 Apex Trauma Center"},
    {"name": "VIMS Institute of Medical Sciences", "district": "Visakhapatnam", "town": "Gopalapatnam", "lat": 17.7380, "lng": 83.2450, "level": "Level-1 Super Speciality"},
    {"name": "Area Hospital Bheemunipatnam", "district": "Visakhapatnam", "town": "Bheemili", "lat": 17.8920, "lng": 83.4520, "level": "Area Hospital"},

    # Anakapalli
    {"name": "District Hospital Anakapalli", "district": "Anakapalli", "town": "Anakapalli", "lat": 17.6913, "lng": 83.0039, "level": "District Hospital"},
    {"name": "Area Hospital Narsipatnam", "district": "Anakapalli", "town": "Narsipatnam", "lat": 17.6680, "lng": 82.6120, "level": "Area Hospital"},
    {"name": "Area Hospital Yelamanchili", "district": "Anakapalli", "town": "Yelamanchili", "lat": 17.5510, "lng": 82.8580, "level": "Area Hospital"},

    # Kakinada
    {"name": "Govt General Hospital (GGH) Kakinada", "district": "Kakinada", "town": "Kakinada", "lat": 16.9891, "lng": 82.2475, "level": "Level-2 Regional Trauma"},
    {"name": "Area Hospital Tuni", "district": "Kakinada", "town": "Tuni", "lat": 17.3540, "lng": 82.5480, "level": "Area Hospital"},
    {"name": "Area Hospital Peddapuram", "district": "Kakinada", "town": "Peddapuram", "lat": 17.0780, "lng": 82.1380, "level": "Area Hospital"},
    {"name": "Area Hospital Pithapuram", "district": "Kakinada", "town": "Pithapuram", "lat": 17.1120, "lng": 82.2580, "level": "Area Hospital"},

    # East Godavari
    {"name": "Govt General Hospital (GGH) Rajahmundry", "district": "East Godavari", "town": "Rajahmundry", "lat": 17.0005, "lng": 81.8040, "level": "Level-2 Regional Trauma"},
    {"name": "Area Hospital Kovvur", "district": "East Godavari", "town": "Kovvur", "lat": 17.0120, "lng": 81.7320, "level": "Area Hospital"},
    {"name": "Area Hospital Nidadavole", "district": "East Godavari", "town": "Nidadavole", "lat": 16.9120, "lng": 81.6710, "level": "Area Hospital"},
    {"name": "Area Hospital Anaparthi", "district": "East Godavari", "town": "Anaparthi", "lat": 16.9350, "lng": 81.9520, "level": "Area Hospital"},

    # Dr. B.R. Ambedkar Konaseema
    {"name": "Area Hospital Amalapuram", "district": "Dr. B.R. Ambedkar Konaseema", "town": "Amalapuram", "lat": 16.5787, "lng": 82.0061, "level": "District Hospital"},
    {"name": "Area Hospital Ramachandrapuram", "district": "Dr. B.R. Ambedkar Konaseema", "town": "Ramachandrapuram", "lat": 16.8520, "lng": 82.0250, "level": "Area Hospital"},
    {"name": "Area Hospital Razole", "district": "Dr. B.R. Ambedkar Konaseema", "town": "Razole", "lat": 16.4820, "lng": 81.8350, "level": "Area Hospital"},
    {"name": "Area Hospital Ravulapalem", "district": "Dr. B.R. Ambedkar Konaseema", "town": "Ravulapalem", "lat": 16.7520, "lng": 81.8450, "level": "Area Hospital"},

    # Eluru
    {"name": "Govt Medical College & GGH Eluru", "district": "Eluru", "town": "Eluru", "lat": 16.7107, "lng": 81.0952, "level": "Level-2 Regional Trauma"},
    {"name": "Area Hospital Jangareddygudem", "district": "Eluru", "town": "Jangareddygudem", "lat": 17.1250, "lng": 81.2950, "level": "Area Hospital"},
    {"name": "Area Hospital Nuzvid", "district": "Eluru", "town": "Nuzvid", "lat": 16.7850, "lng": 80.8460, "level": "Area Hospital"},
    {"name": "CHC Chintalapudi", "district": "Eluru", "town": "Chintalapudi", "lat": 17.0650, "lng": 80.9850, "level": "Community Health Centre"},

    # West Godavari
    {"name": "District Hospital Bhimavaram", "district": "West Godavari", "town": "Bhimavaram", "lat": 16.5449, "lng": 81.5212, "level": "District Hospital"},
    {"name": "Area Hospital Tadepalligudem", "district": "West Godavari", "town": "Tadepalligudem", "lat": 16.8120, "lng": 81.5280, "level": "Area Hospital"},
    {"name": "Area Hospital Tanuku", "district": "West Godavari", "town": "Tanuku", "lat": 16.7580, "lng": 81.6820, "level": "Area Hospital"},
    {"name": "Area Hospital Palacole", "district": "West Godavari", "town": "Palacole", "lat": 16.5210, "lng": 81.7350, "level": "Area Hospital"},
    {"name": "Area Hospital Narasapuram", "district": "West Godavari", "town": "Narasapuram", "lat": 16.4420, "lng": 81.7010, "level": "Area Hospital"},

    # NTR
    {"name": "Govt General Hospital (GGH) Vijayawada", "district": "NTR", "town": "Vijayawada", "lat": 16.5122, "lng": 80.6415, "level": "Level-1 Trauma Care"},
    {"name": "Area Hospital Nandigama", "district": "NTR", "town": "Nandigama", "lat": 16.7720, "lng": 80.2980, "level": "Area Hospital"},
    {"name": "Area Hospital Jaggayyapeta", "district": "NTR", "town": "Jaggayyapeta", "lat": 16.8920, "lng": 80.0980, "level": "Area Hospital"},
    {"name": "Area Hospital Tiruvuru", "district": "NTR", "town": "Tiruvuru", "lat": 17.1120, "lng": 80.6120, "level": "Area Hospital"},

    # Krishna
    {"name": "Govt Medical College & District Hospital Machilipatnam", "district": "Krishna", "town": "Machilipatnam", "lat": 16.1875, "lng": 81.1389, "level": "Level-2 Regional Trauma"},
    {"name": "Area Hospital Gudivada", "district": "Krishna", "town": "Gudivada", "lat": 16.4320, "lng": 80.9950, "level": "Area Hospital"},
    {"name": "Area Hospital Avanigadda", "district": "Krishna", "town": "Avanigadda", "lat": 16.0210, "lng": 80.9150, "level": "Area Hospital"},
    {"name": "CHC Pamarru", "district": "Krishna", "town": "Pamarru", "lat": 16.3280, "lng": 80.9650, "level": "Community Health Centre"},

    # Palnadu
    {"name": "District Hospital Narasaraopet", "district": "Palnadu", "town": "Narasaraopet", "lat": 16.2359, "lng": 80.0494, "level": "District Hospital"},
    {"name": "Area Hospital Sattenapalle", "district": "Palnadu", "town": "Sattenapalle", "lat": 16.3980, "lng": 80.1780, "level": "Area Hospital"},
    {"name": "Area Hospital Macherla", "district": "Palnadu", "town": "Macherla", "lat": 16.4810, "lng": 79.2980, "level": "Area Hospital"},
    {"name": "Area Hospital Piduguralla", "district": "Palnadu", "town": "Piduguralla", "lat": 16.4810, "lng": 79.8890, "level": "Area Hospital"},
    {"name": "Area Hospital Vinukonda", "district": "Palnadu", "town": "Vinukonda", "lat": 16.0520, "lng": 79.7420, "level": "Area Hospital"},
    {"name": "Area Hospital Chilakaluripet", "district": "Palnadu", "town": "Chilakaluripet", "lat": 16.0820, "lng": 80.1740, "level": "Area Hospital"},

    # Guntur
    {"name": "Govt General Hospital (GGH) Guntur", "district": "Guntur", "town": "Guntur", "lat": 16.3025, "lng": 80.4421, "level": "Level-1 Apex Trauma Care"},
    {"name": "AIIMS Mangalagiri Emergency Medicine", "district": "Guntur", "town": "Mangalagiri", "lat": 16.4382, "lng": 80.5631, "level": "Level-1 Apex Trauma Center"},
    {"name": "Area Hospital Tenali", "district": "Guntur", "town": "Tenali", "lat": 16.2420, "lng": 80.6450, "level": "Area Hospital"},
    {"name": "Area Hospital Ponnur", "district": "Guntur", "town": "Ponnur", "lat": 16.0680, "lng": 80.5560, "level": "Area Hospital"},

    # Bapatla
    {"name": "Area Hospital Bapatla", "district": "Bapatla", "town": "Bapatla", "lat": 15.9042, "lng": 80.4674, "level": "District Hospital"},
    {"name": "Area Hospital Chirala", "district": "Bapatla", "town": "Chirala", "lat": 15.8240, "lng": 80.3520, "level": "Area Hospital"},
    {"name": "Area Hospital Addanki", "district": "Bapatla", "town": "Addanki", "lat": 15.8120, "lng": 79.9780, "level": "Area Hospital"},
    {"name": "Area Hospital Repalle", "district": "Bapatla", "town": "Repalle", "lat": 16.0210, "lng": 80.8450, "level": "Area Hospital"},

    # Prakasam
    {"name": "Govt General Hospital (GGH) & GMC Ongole", "district": "Prakasam", "town": "Ongole", "lat": 15.5057, "lng": 80.0499, "level": "Level-2 Regional Trauma"},
    {"name": "Area Hospital Markapur", "district": "Prakasam", "town": "Markapur", "lat": 15.7350, "lng": 79.2710, "level": "Area Hospital"},
    {"name": "Area Hospital Kandukur", "district": "Prakasam", "town": "Kandukur", "lat": 15.2150, "lng": 79.9050, "level": "Area Hospital"},
    {"name": "Area Hospital Giddalur", "district": "Prakasam", "town": "Giddalur", "lat": 15.3780, "lng": 78.9250, "level": "Area Hospital"},
    {"name": "CHC Podili", "district": "Prakasam", "town": "Podili", "lat": 15.6020, "lng": 79.6050, "level": "Community Health Centre"},

    # SPS Nellore
    {"name": "Govt General Hospital (GGH) & ACSR GMC Nellore", "district": "SPS Nellore", "town": "Nellore", "lat": 14.4426, "lng": 79.9865, "level": "Level-2 Regional Trauma"},
    {"name": "Area Hospital Kavali", "district": "SPS Nellore", "town": "Kavali", "lat": 14.9120, "lng": 79.9910, "level": "Area Hospital"},
    {"name": "Area Hospital Gudur", "district": "SPS Nellore", "town": "Gudur", "lat": 14.1520, "lng": 79.8450, "level": "Area Hospital"},
    {"name": "Area Hospital Atmakur", "district": "SPS Nellore", "town": "Atmakur", "lat": 14.6120, "lng": 79.6250, "level": "Area Hospital"},

    # Kurnool
    {"name": "Govt General Hospital (GGH) Kurnool", "district": "Kurnool", "town": "Kurnool", "lat": 15.8281, "lng": 78.0373, "level": "Level-1 Apex Trauma Care"},
    {"name": "Area Hospital Adoni", "district": "Kurnool", "town": "Adoni", "lat": 15.6320, "lng": 77.2750, "level": "Area Hospital"},
    {"name": "Area Hospital Yemmiganur", "district": "Kurnool", "town": "Yemmiganur", "lat": 15.7650, "lng": 77.4850, "level": "Area Hospital"},
    {"name": "Area Hospital Dhone", "district": "Kurnool", "town": "Dhone", "lat": 15.3950, "lng": 77.8680, "level": "Area Hospital"},
    {"name": "CHC Pattikonda", "district": "Kurnool", "town": "Pattikonda", "lat": 15.4020, "lng": 77.5120, "level": "Community Health Centre"},

    # Nandyal
    {"name": "Govt Medical College & District Hospital Nandyal", "district": "Nandyal", "town": "Nandyal", "lat": 15.4886, "lng": 78.4836, "level": "District Hospital & Trauma"},
    {"name": "Area Hospital Allagadda", "district": "Nandyal", "town": "Allagadda", "lat": 15.1320, "lng": 78.5120, "level": "Area Hospital"},
    {"name": "Area Hospital Banaganapalle", "district": "Nandyal", "town": "Banaganapalle", "lat": 15.3180, "lng": 78.2320, "level": "Area Hospital"},
    {"name": "Area Hospital Nandikotkur", "district": "Nandyal", "town": "Nandikotkur", "lat": 15.8650, "lng": 78.2650, "level": "Area Hospital"},
    {"name": "CHC Atmakur Nandyal", "district": "Nandyal", "town": "Atmakur", "lat": 15.8820, "lng": 78.5850, "level": "Community Health Centre"},

    # Ananthapuramu
    {"name": "Govt General Hospital (GGH) Anantapur", "district": "Ananthapuramu", "town": "Anantapur", "lat": 14.6819, "lng": 77.6006, "level": "Level-2 Regional Trauma"},
    {"name": "Area Hospital Guntakal", "district": "Ananthapuramu", "town": "Guntakal", "lat": 15.1680, "lng": 77.3750, "level": "Area Hospital"},
    {"name": "Area Hospital Tadpatri", "district": "Ananthapuramu", "town": "Tadpatri", "lat": 14.9120, "lng": 78.0120, "level": "Area Hospital"},
    {"name": "Area Hospital Gooty", "district": "Ananthapuramu", "town": "Gooty", "lat": 15.1120, "lng": 77.6320, "level": "Area Hospital"},
    {"name": "CHC Kalyandurg", "district": "Ananthapuramu", "town": "Kalyandurg", "lat": 14.5520, "lng": 77.1050, "level": "Community Health Centre"},

    # Sri Sathya Sai
    {"name": "SSSIHMS Super Speciality Hospital Puttaparthi", "district": "Sri Sathya Sai", "town": "Puttaparthi", "lat": 14.1681, "lng": 77.8105, "level": "Level-1 Super Speciality"},
    {"name": "District Hospital Hindupur", "district": "Sri Sathya Sai", "town": "Hindupur", "lat": 13.8280, "lng": 77.4920, "level": "District Hospital"},
    {"name": "Area Hospital Kadiri", "district": "Sri Sathya Sai", "town": "Kadiri", "lat": 14.1120, "lng": 78.1620, "level": "Area Hospital"},
    {"name": "Area Hospital Penukonda", "district": "Sri Sathya Sai", "town": "Penukonda", "lat": 14.0850, "lng": 77.6250, "level": "Area Hospital"},
    {"name": "CHC Madakasira", "district": "Sri Sathya Sai", "town": "Madakasira", "lat": 13.9350, "lng": 77.2710, "level": "Community Health Centre"},

    # YSR Kadapa
    {"name": "RIMS Govt General Hospital Kadapa", "district": "YSR Kadapa", "town": "Kadapa", "lat": 14.4673, "lng": 78.8242, "level": "Level-2 Regional Trauma"},
    {"name": "District Hospital Proddatur", "district": "YSR Kadapa", "town": "Proddatur", "lat": 14.7520, "lng": 78.5520, "level": "District Hospital"},
    {"name": "Area Hospital Pulivendula", "district": "YSR Kadapa", "town": "Pulivendula", "lat": 14.4180, "lng": 78.2320, "level": "Area Hospital"},
    {"name": "Area Hospital Jammalamadugu", "district": "YSR Kadapa", "town": "Jammalamadugu", "lat": 14.8520, "lng": 78.3850, "level": "Area Hospital"},
    {"name": "Area Hospital Badvel", "district": "YSR Kadapa", "town": "Badvel", "lat": 14.7450, "lng": 79.0550, "level": "Area Hospital"},

    # Annamayya
    {"name": "Govt Medical College & District Hospital Rayachoti", "district": "Annamayya", "town": "Rayachoti", "lat": 14.0560, "lng": 78.7523, "level": "District Hospital & Trauma"},
    {"name": "Area Hospital Madanapalle", "district": "Annamayya", "town": "Madanapalle", "lat": 13.5510, "lng": 78.5020, "level": "Area Hospital"},
    {"name": "Area Hospital Rajampet", "district": "Annamayya", "town": "Rajampet", "lat": 14.1950, "lng": 79.1620, "level": "Area Hospital"},
    {"name": "Area Hospital Pileru", "district": "Annamayya", "town": "Pileru", "lat": 13.7120, "lng": 78.9950, "level": "Area Hospital"},

    # Tirupati
    {"name": "SVIMS & Ruia Govt General Hospital Tirupati", "district": "Tirupati", "town": "Tirupati", "lat": 13.6341, "lng": 79.4045, "level": "Level-1 Apex Trauma Center"},
    {"name": "Area Hospital Srikalahasti", "district": "Tirupati", "town": "Srikalahasti", "lat": 13.7540, "lng": 79.7120, "level": "Area Hospital"},
    {"name": "Area Hospital Sullurpeta", "district": "Tirupati", "town": "Sullurpeta", "lat": 13.7020, "lng": 80.0210, "level": "Area Hospital"},
    {"name": "Area Hospital Puttur", "district": "Tirupati", "town": "Puttur", "lat": 13.4420, "lng": 79.5520, "level": "Area Hospital"},
    {"name": "Area Hospital Gudur", "district": "Tirupati", "town": "Gudur", "lat": 14.1520, "lng": 79.8450, "level": "Area Hospital"},

    # Chittoor
    {"name": "Govt Medical College & GGH Chittoor", "district": "Chittoor", "town": "Chittoor", "lat": 13.2172, "lng": 79.1003, "level": "District Hospital & Trauma"},
    {"name": "Area Hospital Palamaner", "district": "Chittoor", "town": "Palamaner", "lat": 13.2020, "lng": 78.7520, "level": "Area Hospital"},
    {"name": "Area Hospital Nagari", "district": "Chittoor", "town": "Nagari", "lat": 13.3320, "lng": 79.5850, "level": "Area Hospital"},
    {"name": "PES Institute of Medical Sciences Kuppam", "district": "Chittoor", "town": "Kuppam", "lat": 12.7520, "lng": 78.3650, "level": "Level-1 Super Speciality Hospital"}
]

# Legacy alias for backward compatibility
MAJOR_TRAUMA_CENTERS = ALL_AP_EMERGENCY_HOSPITALS

class DispatchEngine:
    def __init__(self, active_ambulance_stations: List[Dict[str, Any]], statewide_stations: Optional[List[Dict[str, Any]]] = None):
        self.stations = active_ambulance_stations or []
        self.statewide_stations = statewide_stations or []
        self.custom_stations = []

    def update_fleet(self, new_stations: List[Dict[str, Any]]):
        self.stations = new_stations

    def set_statewide_stations(self, stations: List[Dict[str, Any]]):
        self.statewide_stations = stations

    def add_custom_station(self, station: Dict[str, Any]):
        self.custom_stations.insert(0, station)

    def dispatch_nearest_ambulance(self, accident_lat: float, accident_lng: float, severity: str = "Critical") -> Dict[str, Any]:
        """
        Dispatches the closest ambulance to the accident coordinates.
        Checks custom nearer stations, optimized stations, and all statewide 108 stations,
        guaranteeing that the closest ambulance is always dispatched.
        """
        candidate_pool = []
        seen_coords = set()

        for s in (self.custom_stations + self.stations + self.statewide_stations):
            coord = (round(s["lat"], 4), round(s["lng"], 4))
            if coord not in seen_coords:
                seen_coords.add(coord)
                candidate_pool.append(s)

        if not candidate_pool:
            return {"error": "No active ambulance stations available."}

        best_station = None
        min_dist_km = float("inf")
        min_eta_mins = float("inf")

        for stn in candidate_pool:
            dist = estimate_road_distance(accident_lat, accident_lng, stn["lat"], stn["lng"])
            eta = estimate_travel_time_minutes(accident_lat, accident_lng, stn["lat"], stn["lng"])
            if dist < min_dist_km:
                min_dist_km = dist
                min_eta_mins = eta
                best_station = stn

        # Golden Hour Status (<15 mins = Optimal, 15-25 mins = Extended, >25 mins = Critical Delay)
        if min_eta_mins <= 15.0:
            golden_hour_status = "GOLDEN_HOUR_MET"
            status_label = "Optimal Response (< 15 min)"
            status_color = "#10b981"  # Emerald green
        elif min_eta_mins <= 25.0:
            golden_hour_status = "EXTENDED_RESPONSE"
            status_label = "Extended Response (15 - 25 min)"
            status_color = "#f59e0b"  # Amber
        else:
            golden_hour_status = "CRITICAL_DELAY"
            status_label = "Critical Delay (> 25 min)"
            status_color = "#ef4444"  # Red

        # Generate ambulance -> accident route waypoints
        ambulance_route = self._generate_route_waypoints(
            (best_station["lat"], best_station["lng"]),
            (accident_lat, accident_lng)
        )

        # IDENTIFY THE STRICTLY NEAREST LOCAL REFERRAL HOSPITAL (Area Hospital / District Hospital / GGH)
        nearest_hospital = None
        min_hospital_dist = float("inf")
        for hosp in ALL_AP_EMERGENCY_HOSPITALS:
            d = estimate_road_distance(accident_lat, accident_lng, hosp["lat"], hosp["lng"])
            if d < min_hospital_dist:
                min_hospital_dist = d
                nearest_hospital = hosp

        hospital_eta = estimate_travel_time_minutes(
            accident_lat, accident_lng, nearest_hospital["lat"], nearest_hospital["lng"]
        )

        # Generate accident -> hospital transfer route waypoints
        hospital_transfer_route = self._generate_route_waypoints(
            (accident_lat, accident_lng),
            (nearest_hospital["lat"], nearest_hospital["lng"])
        )

        # Identify nearest Apex / Tertiary center (Level-1) if polytrauma surgery is needed
        nearest_apex = None
        min_apex_dist = float("inf")
        for hosp in ALL_AP_EMERGENCY_HOSPITALS:
            if "Level-1" in hosp["level"]:
                d = estimate_road_distance(accident_lat, accident_lng, hosp["lat"], hosp["lng"])
                if d < min_apex_dist:
                    min_apex_dist = d
                    nearest_apex = hosp

        return {
            "accident_location": {"lat": accident_lat, "lng": accident_lng},
            "dispatched_ambulance": {
                "station_id": best_station.get("station_id", "AMB-STN"),
                "name": best_station.get("name", "Ambulance Base"),
                "lat": best_station["lat"],
                "lng": best_station["lng"],
                "district": best_station.get("district", ""),
                "mandal": best_station.get("mandal", ""),
                "vehicle_type": best_station.get("allocated_vehicle_type", "Basic Life Support (BLS)")
            },
            "response_metrics": {
                "road_distance_km": min_dist_km,
                "estimated_eta_minutes": min_eta_mins,
                "golden_hour_status": golden_hour_status,
                "status_label": status_label,
                "status_color": status_color
            },
            "route_waypoints": ambulance_route,
            "hospital_transfer_waypoints": hospital_transfer_route,
            "nearest_hospital": {
                "name": nearest_hospital["name"],
                "district": nearest_hospital["district"],
                "town": nearest_hospital.get("town", ""),
                "level": nearest_hospital["level"],
                "distance_km": round(min_hospital_dist, 1),
                "eta_minutes": hospital_eta,
                "lat": nearest_hospital["lat"],
                "lng": nearest_hospital["lng"]
            },
            "apex_referral_center": {
                "name": nearest_apex["name"] if nearest_apex else "Apex Trauma Center",
                "district": nearest_apex["district"] if nearest_apex else "",
                "level": nearest_apex["level"] if nearest_apex else "Level-1 Super Speciality",
                "distance_km": round(min_apex_dist, 1)
            },
            # Legacy field for backward compatibility
            "recommended_trauma_center": {
                "name": f"{nearest_hospital['name']} ({round(min_hospital_dist, 1)} km)",
                "district": nearest_hospital["district"],
                "level": nearest_hospital["level"],
                "distance_km": round(min_hospital_dist, 1)
            }
        }

    def _generate_route_waypoints(self, start: tuple, end: tuple, num_segments: int = 6) -> List[List[float]]:
        """
        Creates realistic road route waypoints between ambulance and accident scene
        with natural road bends.
        """
        lat1, lng1 = start
        lat2, lng2 = end
        waypoints = [[lat1, lng1]]

        # Midpoint perpendicular perturbation to simulate highway curvature
        d_lat = lat2 - lat1
        d_lng = lng2 - lng1
        perp_lat = -d_lng * 0.08
        perp_lng = d_lat * 0.08

        for step in range(1, num_segments):
            fraction = step / float(num_segments)
            bend = math.sin(fraction * math.pi)
            w_lat = round(lat1 + fraction * d_lat + bend * perp_lat, 5)
            w_lng = round(lng1 + fraction * d_lng + bend * perp_lng, 5)
            waypoints.append([w_lat, w_lng])

        waypoints.append([lat2, lng2])
        return waypoints

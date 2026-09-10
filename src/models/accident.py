"""
Domain models for Accident Blackspots and Live Emergency Incidents.
"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class AccidentBlackspot:
    blackspot_id: str
    corridor: str
    location_name: str
    district: str
    lat: float
    lng: float
    fatalities_annual: int
    injuries_annual: int
    severity_index: float
    accident_causes: str
    peak_time_window: str
    weight: float

    def to_dict(self) -> dict:
        return {
            "blackspot_id": self.blackspot_id,
            "corridor": self.corridor,
            "location_name": self.location_name,
            "district": self.district,
            "lat": self.lat,
            "lng": self.lng,
            "fatalities_annual": self.fatalities_annual,
            "injuries_annual": self.injuries_annual,
            "severity_index": self.severity_index,
            "accident_causes": self.accident_causes,
            "peak_time_window": self.peak_time_window,
            "weight": self.weight
        }

@dataclass
class IncidentReport:
    incident_id: str
    lat: float
    lng: float
    district: str
    nearest_mandal: str
    severity: str  # Critical / High / Moderate
    timestamp: str
    dispatched_ambulance_id: Optional[str] = None
    response_distance_km: Optional[float] = None
    estimated_response_mins: Optional[float] = None
    is_golden_hour_met: Optional[bool] = None

    def to_dict(self) -> dict:
        return {
            "incident_id": self.incident_id,
            "lat": self.lat,
            "lng": self.lng,
            "district": self.district,
            "nearest_mandal": self.nearest_mandal,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "dispatched_ambulance_id": self.dispatched_ambulance_id,
            "response_distance_km": self.response_distance_km,
            "estimated_response_mins": self.estimated_response_mins,
            "is_golden_hour_met": self.is_golden_hour_met
        }

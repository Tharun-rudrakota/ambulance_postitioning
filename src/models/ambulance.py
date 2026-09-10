"""
Domain models for Ambulance Stations and Deployed Units.
"""
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class AmbulanceUnit:
    unit_id: str
    vehicle_registration: str
    vehicle_type: str  # Advanced Life Support (ALS) vs Basic Life Support (BLS)
    status: str  # AVAILABLE / DISPATCHED / MAINTENANCE
    crew_members: int
    has_ventilator: bool
    has_defibrillator: bool

    def to_dict(self) -> dict:
        return {
            "unit_id": self.unit_id,
            "vehicle_registration": self.vehicle_registration,
            "vehicle_type": self.vehicle_type,
            "status": self.status,
            "crew_members": self.crew_members,
            "has_ventilator": self.has_ventilator,
            "has_defibrillator": self.has_defibrillator
        }

@dataclass
class AmbulanceStation:
    station_id: str
    name: str
    district: str
    lat: float
    lng: float
    is_recommended: bool
    station_type: str  # Primary Highway Post, Community Health Centre (CHC), Mandal Base
    assigned_mandal: str
    coverage_radius_km: float = 12.0
    units: List[AmbulanceUnit] = field(default_factory=list)
    covered_mandals: List[str] = field(default_factory=list)
    covered_blackspots: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "station_id": self.station_id,
            "name": self.name,
            "district": self.district,
            "lat": self.lat,
            "lng": self.lng,
            "is_recommended": self.is_recommended,
            "station_type": self.station_type,
            "assigned_mandal": self.assigned_mandal,
            "coverage_radius_km": self.coverage_radius_km,
            "unit_count": len(self.units),
            "units": [u.to_dict() for u in self.units],
            "covered_mandals_count": len(self.covered_mandals),
            "covered_mandals": self.covered_mandals,
            "covered_blackspots_count": len(self.covered_blackspots),
            "covered_blackspots": self.covered_blackspots
        }

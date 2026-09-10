"""
Domain models for Mandals and Districts in Andhra Pradesh.
"""
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Mandal:
    mandal_id: str
    district: str
    mandal_name: str
    lat: float
    lng: float
    population: int
    tier: str
    is_highway_corridor: bool
    annual_accidents: int
    risk_score: float
    primary_roads: List[str] = field(default_factory=list)

    @property
    def demand_weight(self) -> float:
        """
        Computes composite demand weight combining accident history,
        highway vulnerability multiplier, and population density.
        """
        highway_bonus = 1.6 if self.is_highway_corridor else 1.0
        return round((self.risk_score * 1.5 + (self.annual_accidents / 10.0)) * highway_bonus, 2)

    def to_dict(self) -> dict:
        return {
            "mandal_id": self.mandal_id,
            "district": self.district,
            "mandal_name": self.mandal_name,
            "lat": self.lat,
            "lng": self.lng,
            "population": self.population,
            "tier": self.tier,
            "is_highway_corridor": self.is_highway_corridor,
            "annual_accidents": self.annual_accidents,
            "risk_score": self.risk_score,
            "demand_weight": self.demand_weight,
            "primary_roads": self.primary_roads
        }

@dataclass
class District:
    district_name: str
    headquarters: str
    lat: float
    lng: float
    mandal_count: int
    highways: List[str] = field(default_factory=list)
    mandals: List[Mandal] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "district_name": self.district_name,
            "headquarters": self.headquarters,
            "lat": self.lat,
            "lng": self.lng,
            "mandal_count": self.mandal_count,
            "highways": self.highways,
            "mandals": [m.to_dict() for m in self.mandals]
        }

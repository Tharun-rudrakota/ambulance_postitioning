"""
Domain models for the Andhra Pradesh Ambulance Optimization System.
"""
from .mandal import Mandal, District
from .accident import AccidentBlackspot, IncidentReport
from .ambulance import AmbulanceStation, AmbulanceUnit

__all__ = [
    "Mandal",
    "District",
    "AccidentBlackspot",
    "IncidentReport",
    "AmbulanceStation",
    "AmbulanceUnit"
]

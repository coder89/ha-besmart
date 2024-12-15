from typing import List, Dict, TypedDict

class WifiBox(TypedDict):
    id: str

class Devices(TypedDict):
    boiler: Dict
    thermostats: List[Dict]

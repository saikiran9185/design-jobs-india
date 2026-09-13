"""City coordinates, so listings can be drawn on a map and sorted by distance.

Almost every listing gives a city and nothing more, so geocoding each one through an
API would be 2,000 requests to learn what a lookup table already knows. Precise street
addresses are rare enough to not be worth the dependency.
"""
from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

# lat, lng
CITIES: dict[str, tuple[float, float]] = {
    # --- India: metros and NCR ---
    "bengaluru": (12.9716, 77.5946), "mumbai": (19.0760, 72.8777),
    "new delhi": (28.6139, 77.2090), "gurugram": (28.4595, 77.0266),
    "noida": (28.5355, 77.3910), "ghaziabad": (28.6692, 77.4538),
    "faridabad": (28.4089, 77.3178), "greater noida": (28.4744, 77.5040),
    "hyderabad": (17.3850, 78.4867), "chennai": (13.0827, 80.2707),
    "pune": (18.5204, 73.8567), "kolkata": (22.5726, 88.3639),
    "ahmedabad": (23.0225, 72.5714), "gandhinagar": (23.2156, 72.6369),
    # --- India: tier 2 ---
    "jaipur": (26.9124, 75.7873), "lucknow": (26.8467, 80.9462),
    "indore": (22.7196, 75.8577), "bhopal": (23.2599, 77.4126),
    "chandigarh": (30.7333, 76.7794), "mohali": (30.7046, 76.7179),
    "surat": (21.1702, 72.8311), "vadodara": (22.3072, 73.1812),
    "nagpur": (21.1458, 79.0882), "coimbatore": (11.0168, 76.9558),
    "kochi": (9.9312, 76.2673), "thiruvananthapuram": (8.5241, 76.9366),
    "mysuru": (12.2958, 76.6394), "mangaluru": (12.9141, 74.8560),
    "visakhapatnam": (17.6868, 83.2185), "vijayawada": (16.5062, 80.6480),
    "bhubaneswar": (20.2961, 85.8245), "guwahati": (26.1445, 91.7362),
    "patna": (25.5941, 85.1376), "ranchi": (23.3441, 85.3096),
    "raipur": (21.2514, 81.6296), "dehradun": (30.3165, 78.0322),
    "jodhpur": (26.2389, 73.0243), "udaipur": (24.5854, 73.7125),
    "nashik": (19.9975, 73.7898), "aurangabad": (19.8762, 75.3433),
    "rajkot": (22.3039, 70.8022), "madurai": (9.9252, 78.1198),
    "tiruchirappalli": (10.7905, 78.7047), "goa": (15.2993, 74.1240),
    "panaji": (15.4909, 73.8278), "shillong": (25.5788, 91.8933),
    "jammu": (32.7266, 74.8570), "srinagar": (34.0837, 74.7973),
    "amritsar": (31.6340, 74.8723), "ludhiana": (30.9010, 75.8573),
    "kanpur": (26.4499, 80.3319), "varanasi": (25.3176, 82.9739),
    "agra": (27.1767, 78.0081), "prayagraj": (25.4358, 81.8463),
    "manipal": (13.3525, 74.7868), "vellore": (12.9165, 79.1325),
    "kharagpur": (22.3460, 87.2320), "roorkee": (29.8543, 77.8880),
    "warangal": (17.9689, 79.5941), "salem": (11.6643, 78.1460),
    "jalandhar": (31.3260, 75.5762), "meerut": (28.9845, 77.7064),
    # --- common non-India anchors, for the global view ---
    "remote": (0.0, 0.0), "london": (51.5072, -0.1276), "new york": (40.7128, -74.0060),
    "san francisco": (37.7749, -122.4194), "berlin": (52.5200, 13.4050),
    "singapore": (1.3521, 103.8198), "dubai": (25.2048, 55.2708),
    "toronto": (43.6532, -79.3832), "sydney": (-33.8688, 151.2093),
    "amsterdam": (52.3676, 4.9041), "paris": (48.8566, 2.3522),
}

# Where "India" is the only location given — used as a neutral centroid, never as a
# claim about where the role actually is.
INDIA_CENTROID = (22.5937, 78.9629)


def locate(city: str | None, location: str | None = None,
           is_india: bool = False) -> tuple[float, float] | tuple[None, None]:
    for candidate in (city, location):
        if not candidate:
            continue
        low = candidate.strip().lower()
        if low in CITIES:
            return CITIES[low]
        for name, coords in CITIES.items():          # "Bengaluru, Karachi Road"
            if len(name) > 4 and name in low:
                return coords
    if is_india:
        return INDIA_CENTROID
    return (None, None)


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (*a, *b))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * asin(sqrt(h))

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

# Neighbourhoods and suburbs that listings name instead of the city. Mapping them
# is the difference between a job showing in Mumbai and vanishing off the map.
LOCALITIES: dict[str, str] = {
    # Mumbai / MMR
    "andheri": "mumbai", "powai": "mumbai", "bandra": "mumbai", "borivali": "mumbai",
    "malad": "mumbai", "goregaon": "mumbai", "lower parel": "mumbai", "worli": "mumbai",
    "bkc": "mumbai", "bandra kurla": "mumbai", "dadar": "mumbai", "chembur": "mumbai",
    "vikhroli": "mumbai", "kurla": "mumbai", "santacruz": "mumbai", "juhu": "mumbai",
    "thane": "mumbai", "navi mumbai": "mumbai", "vashi": "mumbai", "mahape": "mumbai",
    "belapur": "mumbai", "airoli": "mumbai", "ghatkopar": "mumbai", "mulund": "mumbai",
    # Delhi NCR
    "saket": "new delhi", "okhla": "new delhi", "connaught place": "new delhi",
    "dwarka": "new delhi", "rohini": "new delhi", "janakpuri": "new delhi",
    "nehru place": "new delhi", "vasant kunj": "new delhi", "hauz khas": "new delhi",
    "karol bagh": "new delhi", "pitampura": "new delhi", "mayur vihar": "new delhi",
    "lajpat nagar": "new delhi", "rajouri garden": "new delhi", "netaji subhash place": "new delhi",
    "udyog vihar": "gurugram", "cyber city": "gurugram", "cyber hub": "gurugram",
    "golf course road": "gurugram", "sohna road": "gurugram", "manesar": "gurugram",
    # Bengaluru
    "koramangala": "bengaluru", "indiranagar": "bengaluru", "whitefield": "bengaluru",
    "electronic city": "bengaluru", "hsr layout": "bengaluru", "hsr": "bengaluru",
    "marathahalli": "bengaluru", "jayanagar": "bengaluru", "btm layout": "bengaluru",
    "hebbal": "bengaluru", "yelahanka": "bengaluru", "bellandur": "bengaluru",
    "sarjapur": "bengaluru", "banashankari": "bengaluru", "rajajinagar": "bengaluru",
    "malleshwaram": "bengaluru", "jp nagar": "bengaluru", "bommanahalli": "bengaluru",
    # Hyderabad
    "gachibowli": "hyderabad", "hitec city": "hyderabad", "hitech city": "hyderabad",
    "madhapur": "hyderabad", "kondapur": "hyderabad", "malkajgiri": "hyderabad",
    "secunderabad": "hyderabad", "kukatpally": "hyderabad", "banjara hills": "hyderabad",
    "jubilee hills": "hyderabad", "begumpet": "hyderabad", "ameerpet": "hyderabad",
    # Chennai
    "guindy": "chennai", "velachery": "chennai", "adyar": "chennai", "vandalur": "chennai",
    "sholinganallur": "chennai", "perungudi": "chennai", "tambaram": "chennai",
    "porur": "chennai", "nungambakkam": "chennai", "t nagar": "chennai", "omr": "chennai",
    # Pune
    "hinjewadi": "pune", "kharadi": "pune", "viman nagar": "pune", "baner": "pune",
    "wakad": "pune", "hadapsar": "pune", "magarpatta": "pune", "kothrud": "pune",
    "pimpri": "pune", "chinchwad": "pune", "aundh": "pune",
    # Kolkata / Ahmedabad
    "salt lake": "kolkata", "new town": "kolkata", "rajarhat": "kolkata",
    "sector v": "kolkata", "satellite": "ahmedabad", "prahlad nagar": "ahmedabad",
    "sg highway": "ahmedabad", "bopal": "ahmedabad",
    "parel": "mumbai", "byculla": "mumbai", "sion": "mumbai", "wadala": "mumbai",
    "kalyan": "mumbai", "dombivli": "mumbai", "panvel": "mumbai",
    "greater kailash": "new delhi", "south extension": "new delhi",
    "kalkaji": "new delhi", "shahdara": "new delhi", "narela": "new delhi",
}

# Additional cities that turn up in listings.
CITIES.update({
    "gwalior": (26.2183, 78.1828), "cuttack": (20.4625, 85.8830),
    "jamshedpur": (22.8046, 86.2029), "siliguri": (26.7271, 88.3953),
    "dhanbad": (23.7957, 86.4304), "jabalpur": (23.1815, 79.9864),
    "gorakhpur": (26.7606, 83.3732), "bareilly": (28.3670, 79.4304),
    "aligarh": (27.8974, 78.0880), "moradabad": (28.8386, 78.7733),
    "solapur": (17.6599, 75.9064), "kolhapur": (16.7050, 74.2433),
    "sangli": (16.8524, 74.5815), "amravati": (20.9320, 77.7523),
    "tirupati": (13.6288, 79.4192), "guntur": (16.3067, 80.4365),
    "nellore": (14.4426, 79.9865), "rourkela": (22.2604, 84.8536),
    "bilaspur": (22.0797, 82.1409), "ajmer": (26.4499, 74.6399),
    "bikaner": (28.0229, 73.3119), "kota": (25.2138, 75.8648),
    "shimla": (31.1048, 77.1734), "pondicherry": (11.9416, 79.8083),
    "puducherry": (11.9416, 79.8083), "hubli": (15.3647, 75.1240),
    "belgaum": (15.8497, 74.4977), "davangere": (14.4644, 75.9218),
    "thrissur": (10.5276, 76.2144), "kozhikode": (11.2588, 75.7804),
    "kollam": (8.8932, 76.6141), "kannur": (11.8745, 75.3704),
    "anand": (22.5645, 72.9289), "bhavnagar": (21.7645, 72.1519),
    "jamnagar": (22.4707, 70.0577),
    "ernakulam": (9.9816, 76.2999), "hosur": (12.7409, 77.8253),
    "dharmapuri": (12.1211, 78.1582), "tiruppur": (11.1085, 77.3411),
    "erode": (11.3410, 77.7172), "tirunelveli": (8.7139, 77.7567),
    "karur": (10.9601, 78.0766), "namakkal": (11.2189, 78.1677),
    "valsad": (20.5992, 72.9342), "navsari": (20.9467, 72.9520),
    "bhilai": (21.1938, 81.3509), "durgapur": (23.5204, 87.3119),
    "asansol": (23.6739, 86.9524), "haldwani": (29.2183, 79.5130),
    "haridwar": (29.9457, 78.1642), "rishikesh": (30.0869, 78.2676),
    "panipat": (29.3909, 76.9635), "karnal": (29.6857, 76.9905),
    "hisar": (29.1492, 75.7217), "rohtak": (28.8955, 76.6066),
    "sonipat": (28.9931, 77.0151), "bathinda": (30.2110, 74.9455),
    "patiala": (30.3398, 76.3869), "ambala": (30.3752, 76.7821),
})


def locate(city: str | None, location: str | None = None,
           is_india: bool = False) -> tuple[float, float] | tuple[None, None]:
    """Return real coordinates or nothing.

    There is deliberately no country-centroid fallback. Pinning a thousand
    location-unknown jobs to the middle of the country puts a phantom cluster on
    the map where no job exists, which is worse than leaving them off it.
    """
    for candidate in (city, location):
        if not candidate:
            continue
        low = candidate.strip().lower()
        if low in CITIES:
            return CITIES[low]
        if low in LOCALITIES:
            return CITIES[LOCALITIES[low]]
        for name, target in LOCALITIES.items():      # "Andheri East, Mumbai"
            if len(name) > 4 and name in low:
                return CITIES[target]
        for name, coords in CITIES.items():          # "Bengaluru, Karachi Road"
            if len(name) > 4 and name in low:
                return coords
    return (None, None)


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (*a, *b))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * asin(sqrt(h))

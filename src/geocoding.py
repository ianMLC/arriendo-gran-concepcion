import re
import unicodedata
from pathlib import Path

import pandas as pd
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim

ROOT = Path(__file__).resolve().parents[1]
CACHE_FILE = ROOT / "data" / "processed" / "geocode_cache.csv"

# Box around Gran Concepción: (north, west) and (south, east) corners.
GRAN_CONCEPCION_BOX = [(-36.50, -73.25), (-37.15, -72.85)]

USER_AGENT = "arriendos-gran-concepcion (student research project)"
CACHE_COLUMNS = ["location", "lat", "lon", "precision", "query", "matched_address"]

ABBREVIATIONS = {
    r"\bAv(da)?\.?\s+": "Avenida ",
    r"\bP(s)?je\.?\s+": "Pasaje ",
    r"\bGral\.?\s+": "General ",
    r"\bOte\.?(?=\s|,|$)": "Oriente",
    r"\bPte\.?(?=\s|,|$)": "Poniente",
}


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def normalize(text):
    """Lowercase and remove accents: 'Hualpén' -> 'hualpen'."""
    text = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def clean_street(street, commune=""):
    """Expand abbreviations, drop noise and keep only the first street of an intersection."""
    for pattern, replacement in ABBREVIATIONS.items():
        street = re.sub(pattern, replacement, street, flags=re.IGNORECASE)
    # "Calle Almena" -> "Almena", but keep "Calle 8 Oriente" (numbered streets need it)
    street = re.sub(r"^\s*calle\s+(?=[^\d\s])", "", street, flags=re.IGNORECASE)
    if commune:
        # "Almena 2195 Concepción" -> "Almena 2195"
        street = re.sub(rf"\s+{re.escape(commune)}\s*$", "", street, flags=re.IGNORECASE)
    return street.split("/")[0].strip()


def candidate_queries(location, commune, neighborhood):
    """Search queries from most to least precise, each with its precision label."""
    parts = [p.strip() for p in str(location).split(",") if p.strip()]
    area_names = {commune.lower(), "chile"}
    queries = []

    # 1. Street, with and without the house number
    street = clean_street(parts[0], commune) if parts else ""
    if street and street.lower() not in area_names:
        if re.search(r"\d", street):
            queries.append((f"{street}, {commune}, Chile", "address"))
            without_number = re.sub(r"\s+#?\d+\s*$", "", street).strip()
            if without_number and without_number != street:
                queries.append((f"{without_number}, {commune}, Chile", "street"))
        else:
            queries.append((f"{street}, {commune}, Chile", "street"))

    # 2. Any other part that isn't the commune can be a neighborhood.
    #    Compound zones like "Barrio Oriente - Las Tres Pascualas" are also tried by parts.
    areas = [p for p in parts[1:] if p.lower() not in area_names]
    if isinstance(neighborhood, str) and neighborhood.lower() not in area_names:
        areas.insert(0, neighborhood)
    for area in areas:
        queries.append((f"{area}, {commune}, Chile", "neighborhood"))
        if " - " in area:
            for piece in area.split(" - "):
                queries.append((f"{piece.strip()}, {commune}, Chile", "neighborhood"))

    # Remove repeated queries, keeping the order
    return list(dict.fromkeys(queries))


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

def build_geocoder():
    """Nominatim with a rate limiter: max 1 request per second, with retries."""
    geolocator = Nominatim(user_agent=USER_AGENT, timeout=10)
    return RateLimiter(
        geolocator.geocode,
        min_delay_seconds=1.1,
        max_retries=2,
        error_wait_seconds=5,
        swallow_exceptions=True,
    )


def in_commune(result, commune):
    """True if Nominatim's full address mentions the listing's commune."""
    address = normalize(result.address)
    # Every result says "Provincia de Concepción"; remove it so it doesn't fake a match
    address = address.replace("provincia de concepcion", "")
    return normalize(commune) in address


def geocode_one(geocode, location, commune, neighborhood):
    """Try each query until one is found inside the listing's commune."""
    for query, precision in candidate_queries(location, commune, neighborhood):
        result = geocode(query, country_codes="cl",
                         viewbox=GRAN_CONCEPCION_BOX, bounded=True)
        if result and in_commune(result, commune):
            return {"location": location, "lat": result.latitude,
                    "lon": result.longitude, "precision": precision, "query": query,
                    "matched_address": result.address}

    return {"location": location, "lat": None, "lon": None,
            "precision": "not_found", "query": None, "matched_address": None}


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def update_cache(df, save_every=25):
    """Geocode only locations not already in the cache. Saves progress often."""
    if CACHE_FILE.exists():
        cache = pd.read_csv(CACHE_FILE)
    else:
        cache = pd.DataFrame(columns=CACHE_COLUMNS)

    pending = (
        df[["location", "commune", "neighborhood"]]
        .dropna(subset=["location"])
        .drop_duplicates(subset=["location"])
    )
    pending = pending[~pending["location"].isin(cache["location"])]

    print(f"In cache: {len(cache)} | new to geocode: {len(pending)} "
          f"(about {len(pending) * 1.5 / 60:.0f} min)")
    if pending.empty:
        return cache

    geocode = build_geocoder()
    new_rows = []
    for i, row in enumerate(pending.itertuples(index=False), start=1):
        new_rows.append(geocode_one(geocode, row.location, row.commune, row.neighborhood))

        if i % save_every == 0 or i == len(pending):
            cache = pd.concat([cache, pd.DataFrame(new_rows)], ignore_index=True)
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            cache.to_csv(CACHE_FILE, index=False, encoding="utf-8")
            new_rows = []
            print(f"  {i}/{len(pending)} done")

    return cache


def forget_not_found():
    """Remove failed lookups from the cache so they are retried next time."""
    cache = pd.read_csv(CACHE_FILE)
    kept = cache[cache["precision"] != "not_found"]
    kept.to_csv(CACHE_FILE, index=False, encoding="utf-8")
    print(f"Removed {len(cache) - len(kept)} not_found entries from the cache")


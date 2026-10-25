import json
from datetime import date
from pathlib import Path

from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
CACHE_FILE= ROOT / "data" / "uf_cache.json"

API_URL = "https://mindicador.cl/api/uf/{day}" # day => DD-MM-YYYY

def _load_cache():
    if CACHE_FILE.exists():
       return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def _save_cache(cache):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    

def get_uf(day):
    day = date.fromisoformat(str(day)[:10])
    key = day.isoformat()
    
    cache = _load_cache()
    if key in cache:
        return cache[key]
    
    url= API_URL.format(day=day.strftime("%d-%m-%Y"))
    request = Request(url, headers={"User-Agent": "arriendos-gran-concepcion"})
    with urlopen(request, timeout=15) as response:
        data = json.load(response)
    
    if not data.get("serie"):
        raise ValueError(f"No data for {day}")
    
    value = data["serie"][0]["valor"]
    cache[key] = value
    _save_cache(cache)
    return value
    
from typing import Any, Optional, List
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("weather-global")

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
UA = "weather-mcp/1.0 (+github.com/example)"

# --------- yardımcılar ---------
async def http_get_json(url: str, params: dict[str, Any]) -> Optional[dict]:
    headers = {"User-Agent": UA, "Accept": "application/json"}
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        try:
            r = await client.get(url, params=params)
            r.raise_for_status()
            return r.json()
        except Exception:
            return None

def _normalize_country_hint(country_hint: Optional[str]) -> Optional[str]:
    if not country_hint:
        return None
    h = country_hint.strip().lower()
    # Türkçe kullanımda “SA” genelde Güney Afrika kastedilir. ISO2: ZA
    if h in {"sa", "south africa", "güney afrika", "rsa", "za"}:
        return "ZA"
    if h in {"suudi arabistan", "saudi", "saudi arabia", "ksa"}:
        return "SA"
    # diğerleri: doğrudan 2 harfli ISO kod denenir (ör. TR, US, DE)
    if len(h) == 2:
        return h.upper()
    return None

def format_current(name: str, country_code: str, current: dict) -> str:
    t = current.get("temperature")
    ws = current.get("windspeed")
    wd = current.get("winddirection")
    dt = current.get("time")
    parts = [f"Konum: {name} ({country_code})"]
    if t is not None: parts.append(f"Anlık sıcaklık: {t}°C")
    if ws is not None: parts.append(f"Rüzgar: {ws} km/s, yön {wd}°")
    if dt: parts.append(f"Zaman damgası: {dt}")
    return " | ".join(parts)

def format_daily(daily: dict, days: int) -> str:
    lines = []
    dates = daily.get("time", [])
    tmax = daily.get("temperature_2m_max", [])
    tmin = daily.get("temperature_2m_min", [])
    prcp = daily.get("precipitation_sum", [])
    prprob = daily.get("precipitation_probability_max", [])
    wsmax = daily.get("windspeed_10m_max", []) or daily.get("wind_speed_10m_max", [])

    n = min(days, len(dates))
    for i in range(n):
        line = f"{dates[i]}: max {tmax[i]}°C, min {tmin[i]}°C"
        if i < len(prcp):   line += f", yağış toplamı {prcp[i]} mm"
        if i < len(prprob): line += f", yağış olasılığı %{prprob[i]}"
        if i < len(wsmax):  line += f", rüzgar maks {wsmax[i]} km/s"
        lines.append(line)
    return "\n".join(lines)

# --------- MCP tools ---------

@mcp.tool()
async def get_weather_for_place(
    place: str,
    country_hint: Optional[str] = None,
    days: int = 3,
    language: str = "tr",
) -> str:
    """
    Bir yer adıyla (örn. 'Cape Town', 'Johannesburg', 'Pretoria') hava durumu ver.
    country_hint: ISO2 veya ad (örn. 'ZA', 'Güney Afrika', 'SA'->ZA varsayılır).
    days: 1-7 arası günlük özet sayısı.
    """

    if not place or not place.strip():
        return "Lütfen bir yer adı belirtin (örn. 'Cape Town')."

    if days < 1 or days > 7:
        days = max(1, min(days, 7))

    cc = _normalize_country_hint(country_hint)

    # 1) Geocoding (çoklu eşleşmeleri ülke filtresiyle daralt)
    geo_params = {"name": place, "count": 5, "language": language, "format": "json"}
    geo = await http_get_json(GEOCODE_URL, geo_params)
    if not geo or not geo.get("results"):
        return f"Eşleşme bulunamadı: {place}"

    candidates = geo["results"]
    if cc:
        candidates = [c for c in candidates if c.get("country_code") == cc] or geo["results"]

    best = candidates[0]
    lat, lon = best["latitude"], best["longitude"]
    disp_name = ", ".join([p for p in [best.get("name"), best.get("admin1"), best.get("country")] if p])
    country_code = best.get("country_code", "")

    # 2) Forecast (anlık + günlük)
    fc_params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": "true",
        "daily": ",".join([
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "precipitation_probability_max",
            "windspeed_10m_max",
        ]),
        "forecast_days": days,
        "timezone": "auto",
    }
    fc = await http_get_json(FORECAST_URL, fc_params)
    if not fc:
        return "Tahmin verisi alınamadı."

    parts: List[str] = []
    if "current_weather" in fc:
        parts.append(format_current(disp_name, country_code, fc["current_weather"]))
    if "daily" in fc and fc["daily"]:
        parts.append("\nGünlük özet:\n" + format_daily(fc["daily"], days))

    return "\n".join(parts) if parts else "Veri bulunamadı."

@mcp.tool()
async def get_weather_by_coords(
    latitude: float,
    longitude: float,
    days: int = 3
) -> str:
    """
    Koordinatla hava durumu ver (örn. lat= -33.9249, lon=18.4241 → Cape Town).
    """
    if days < 1 or days > 7:
        days = max(1, min(days, 7))

    fc_params = {
        "latitude": latitude,
        "longitude": longitude,
        "current_weather": "true",
        "daily": ",".join([
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "precipitation_probability_max",
            "windspeed_10m_max",
        ]),
        "forecast_days": days,
        "timezone": "auto",
    }
    fc = await http_get_json(FORECAST_URL, fc_params)
    if not fc:
        return "Tahmin verisi alınamadı."

    name = f"{latitude:.4f}, {longitude:.4f}"
    parts: List[str] = []
    if "current_weather" in fc:
        parts.append(format_current(name, "", fc["current_weather"]))
    if "daily" in fc and fc["daily"]:
        parts.append("\nGünlük özet:\n" + format_daily(fc["daily"], days))
    return "\n".join(parts)

if __name__ == "__main__":
    mcp.run(transport="stdio")

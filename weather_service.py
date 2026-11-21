"""
Weather and Solar Position Service for SolarMonitor.
Provides:
- Exact astronomical solar position (Elevation, Azimuth) via NOAA algorithm
- Local weather data (Temperature, Cloud Cover, Rain) via Open-Meteo API using requests
"""

import math
import time
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
import pandas as pd
import requests

logger = logging.getLogger(__name__)

# Default coordinates: Oestrich-Winkel, Hessen, Germany
DEFAULT_LOCATION_NAME = "Oestrich-Winkel"
DEFAULT_LATITUDE = 50.0085
DEFAULT_LONGITUDE = 8.0199

# In-memory cache for weather to minimize API calls (cached for 5 minutes)
_weather_cache = {
    "last_fetched": 0,
    "current": None,
    "hourly": None,
    "lat": None,
    "lon": None
}


def get_solar_position(lat: float, lon: float, dt: Optional[datetime] = None) -> Tuple[float, float]:
    """
    Computes solar elevation and azimuth angle using standard NOAA algorithm.
    - Elevation: degrees above horizon (-90 to +90).
    - Azimuth: degrees from True North clockwise (0=North, 90=East, 180=South, 270=West).
    """
    if dt is None:
        dt = datetime.now()

    if dt.tzinfo is None:
        dt_utc = dt.astimezone(timezone.utc)
    else:
        dt_utc = dt.astimezone(timezone.utc)

    year = dt_utc.year
    month = dt_utc.month
    day = dt_utc.day
    hour = dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0

    if month <= 2:
        year -= 1
        month += 12

    a = math.floor(year / 100)
    b = 2 - a + math.floor(a / 4)
    jd = math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1)) + day + b - 1524.5 + hour / 24.0

    t = (jd - 2451545.0) / 36525.0
    l0 = (280.46646 + t * (36000.76983 + 0.0003032 * t)) % 360.0
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    m_rad = math.radians(m)

    c = math.sin(m_rad) * (1.914602 - t * (0.004817 + 0.000014 * t)) + \
        math.sin(2 * m_rad) * (0.019993 - 0.000101 * t) + \
        math.sin(3 * m_rad) * 0.000289

    true_long = l0 + c
    apparent_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(125.04 - 1934.136 * t))
    apparent_long_rad = math.radians(apparent_long)

    eps0 = 23.0 + (26.0 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60.0) / 60.0
    eps = eps0 + 0.00256 * math.cos(math.radians(125.04 - 1934.136 * t))
    eps_rad = math.radians(eps)

    decl = math.asin(math.sin(eps_rad) * math.sin(apparent_long_rad))

    y = math.tan(eps_rad / 2.0) ** 2
    l0_rad = math.radians(l0)
    eot = 4.0 * math.degrees(
        y * math.sin(2.0 * l0_rad) -
        2.0 * 0.016708634 * math.sin(m_rad) +
        4.0 * 0.016708634 * y * math.sin(m_rad) * math.cos(2.0 * l0_rad) -
        0.5 * (y ** 2) * math.sin(4.0 * l0_rad) -
        1.25 * (0.016708634 ** 2) * math.sin(2.0 * m_rad)
    )

    time_offset = eot + 4.0 * lon
    tst = (dt_utc.hour * 60.0 + dt_utc.minute + dt_utc.second / 60.0 + time_offset) % 1440.0
    ha = (tst / 4.0) - 180.0
    if ha < -180.0:
        ha += 360.0
    ha_rad = math.radians(ha)

    lat_rad = math.radians(lat)
    cos_zenith = math.sin(lat_rad) * math.sin(decl) + math.cos(lat_rad) * math.cos(decl) * math.cos(ha_rad)
    cos_zenith = max(-1.0, min(1.0, cos_zenith))
    zenith = math.acos(cos_zenith)
    elevation = 90.0 - math.degrees(zenith)

    sin_zenith = math.sin(zenith)
    if abs(sin_zenith) > 1e-6:
        cos_azimuth = (math.sin(decl) - math.sin(lat_rad) * cos_zenith) / (math.cos(lat_rad) * sin_zenith)
        cos_azimuth = max(-1.0, min(1.0, cos_azimuth))
        azimuth = math.degrees(math.acos(cos_azimuth))
        if ha > 0:
            azimuth = 360.0 - azimuth
    else:
        azimuth = 180.0

    return round(elevation, 1), round(azimuth, 1)


def get_azimuth_direction(deg: float) -> str:
    """Returns human-readable compass direction for an azimuth angle in degrees."""
    deg = deg % 360.0
    val = int((deg / 22.5) + 0.5)
    directions = [
        "N (Nord)", "NNO (Nord-Nordost)", "NO (Nordost)", "ONO (Ost-Nordost)",
        "O (Ost)", "OSO (Ost-Südost)", "SO (Südost)", "SSO (Süd-Südost)",
        "S (Süd)", "SSW (Süd-Südwest)", "SW (Südwest)", "WSW (West-Südwest)",
        "W (West)", "WNW (West-Nordwest)", "NW (Nordwest)", "NNW (Nord-Nordwest)"
    ]
    return directions[val % 16]


def fetch_open_meteo_weather(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Fetches weather data from Open-Meteo API using requests with connection pooling.
    Uses in-memory cache to avoid repeated requests (cached for 5 minutes).
    """
    now_ts = time.time()
    if (
        _weather_cache["current"] is not None
        and _weather_cache["lat"] == lat
        and _weather_cache["lon"] == lon
        and (now_ts - _weather_cache["last_fetched"]) < 300
    ):
        return _weather_cache

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,rain,cloud_cover,weather_code",
        "hourly": "temperature_2m,cloud_cover,rain,direct_normal_irradiance",
        "timezone": "auto",
        "past_days": 7
    }

    try:
        resp = requests.get(
            url,
            params=params,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=6
        )
        if resp.status_code == 200:
            data = resp.json()
            _weather_cache["last_fetched"] = now_ts
            _weather_cache["current"] = data.get("current", {})
            _weather_cache["hourly"] = data.get("hourly", {})
            _weather_cache["lat"] = lat
            _weather_cache["lon"] = lon
            return _weather_cache
        else:
            logger.warning(f"Open-Meteo returned status {resp.status_code}")
            return _weather_cache if _weather_cache["current"] is not None else None
    except Exception as e:
        logger.warning(f"Open-Meteo weather fetch error: {e}")
        return _weather_cache if _weather_cache["current"] is not None else None


def get_current_weather(lat: float, lon: float) -> Dict[str, Any]:
    """Returns current temperature, cloud cover, rain, and solar position."""
    elev, azim = get_solar_position(lat, lon)
    weather_data = fetch_open_meteo_weather(lat, lon)

    temp = None
    clouds = None
    rain = None

    if weather_data and weather_data.get("current"):
        cur = weather_data["current"]
        temp = cur.get("temperature_2m")
        clouds = cur.get("cloud_cover")
        rain = cur.get("rain")

    return {
        "temperature": temp,
        "clouds": clouds,
        "rain": rain,
        "solar_elevation": elev,
        "solar_azimuth": azim
    }


def get_weather_dataframe_for_date(lat: float, lon: float, target_date_str: str) -> pd.DataFrame:
    """
    Returns an hourly DataFrame for target_date_str (YYYY-MM-DD)
    containing: timestamp, temperature, clouds, rain, direct_irradiance, solar_elevation, solar_azimuth.
    """
    weather_data = fetch_open_meteo_weather(lat, lon)
    rows = []

    if weather_data and weather_data.get("hourly"):
        h = weather_data["hourly"]
        times = h.get("time", [])
        temps = h.get("temperature_2m", [])
        clouds = h.get("cloud_cover", [])
        rains = h.get("rain", [])
        irrad = h.get("direct_normal_irradiance", [])

        for i, t_str in enumerate(times):
            if t_str.startswith(target_date_str):
                dt_obj = datetime.fromisoformat(t_str)
                elev, azim = get_solar_position(lat, lon, dt_obj)

                rows.append({
                    "timestamp": dt_obj,
                    "Temperatur (°C)": temps[i] if i < len(temps) else None,
                    "Bewölkung (%)": clouds[i] if i < len(clouds) else None,
                    "Regen (mm)": rains[i] if i < len(rains) else None,
                    "Direkte Einstrahlung (W/m²)": irrad[i] if i < len(irrad) else None,
                    "Sonnenhöhe (°)": max(0.0, elev),
                    "Sonnenazimuth (°)": azim
                })

    # If offline or API failed, still generate the exact astronomical solar curve for each hour
    if not rows:
        target_day = datetime.strptime(target_date_str, "%Y-%m-%d")
        for hour in range(24):
            dt_obj = target_day.replace(hour=hour, minute=0, second=0)
            elev, azim = get_solar_position(lat, lon, dt_obj)
            rows.append({
                "timestamp": dt_obj,
                "Temperatur (°C)": None,
                "Bewölkung (%)": None,
                "Regen (mm)": None,
                "Direkte Einstrahlung (W/m²)": None,
                "Sonnenhöhe (°)": max(0.0, elev),
                "Sonnenazimuth (°)": azim
            })

    return pd.DataFrame(rows)

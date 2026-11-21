"""
Generates synthetic solar production and weather data for today to test the dashboard,
verify charts, and inspect the correlation between solar production, clouds, and solar elevation.
"""

import math
import random
from datetime import datetime, timedelta
import sqlite3
from db import init_db, DB_FILE
from weather_service import get_solar_position
from config_manager import load_config


def generate_today_solar_curve(points: int = 150):
    init_db()
    cfg = load_config()
    lat = float(cfg.get("latitude", 50.0085))
    lon = float(cfg.get("longitude", 8.0199))

    now = datetime.now()
    start_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
    end_time = now if now.hour >= 8 else start_time + timedelta(hours=10)
    total_duration_sec = (end_time - start_time).total_seconds()
    if total_duration_sec <= 0:
        total_duration_sec = 8 * 3600

    step_sec = total_duration_sec / max(points, 10)

    conn = sqlite3.connect(DB_FILE)
    records = []

    for i in range(points):
        current = start_time + timedelta(seconds=i * step_sec)
        hour_frac = current.hour + current.minute / 60.0

        # Exact astronomical solar position
        elev, azim = get_solar_position(lat, lon, current)
        elev_clamped = max(0.0, elev)

        # Weather simulation
        # Cloud cover with a dip / spike at midday
        base_cloud = 20.0 + 35.0 * math.sin((hour_frac - 7.0) / 12.0 * math.pi)
        if 11.0 <= hour_frac <= 12.5:
            cloud_pct = min(100.0, base_cloud + 45.0 + random.uniform(-10, 10))  # Passing cloud front
        else:
            cloud_pct = max(5.0, min(100.0, base_cloud + random.uniform(-15, 15)))

        # Temperature rises through the day (e.g. from 9°C up to 16°C)
        temp_c = 9.0 + 7.0 * (1.0 - math.cos((hour_frac - 6.0) / 14.0 * math.pi)) / 2.0 + random.uniform(-0.3, 0.3)
        rain_mm = 0.5 if (11.5 <= hour_frac <= 12.0) else 0.0

        # Solar factor based on elevation and cloud cover
        if elev_clamped > 1.0:
            sun_factor = (math.sin(math.radians(elev_clamped)) ** 1.1) * ((100.0 - cloud_pct * 0.8) / 100.0)
            sun_factor = max(0.0, sun_factor)
        else:
            sun_factor = 0.0

        # Azimuth alignment:
        # PV1: South-East (optimal ~135°)
        diff1 = abs(azim - 135.0)
        eff1 = max(0.2, math.cos(math.radians(min(85.0, diff1))))
        pv1 = max(0.0, sun_factor * 340.0 * eff1)

        # PV2: South (optimal 180°)
        diff2 = abs(azim - 180.0)
        eff2 = max(0.2, math.cos(math.radians(min(85.0, diff2))))
        pv2 = max(0.0, sun_factor * 420.0 * eff2)

        # PV3: South (optimal 180°)
        pv3 = max(0.0, sun_factor * 390.0 * eff2)

        # PV4: South-West (optimal 225°)
        diff4 = abs(azim - 225.0)
        eff4 = max(0.2, math.cos(math.radians(min(85.0, diff4))))
        pv4 = max(0.0, sun_factor * 350.0 * eff4)

        total = pv1 + pv2 + pv3 + pv4

        records.append((
            current.strftime("%Y-%m-%d %H:%M:%S"),
            round(pv1, 1),
            round(pv2, 1),
            round(pv3, 1),
            round(pv4, 1),
            round(total, 1),
            round(temp_c, 1),
            round(cloud_pct, 0),
            round(rain_mm, 2),
            round(elev, 1),
            round(azim, 1)
        ))

    with conn:
        conn.executemany("""
            INSERT INTO pv_measurements (timestamp, pv1, pv2, pv3, pv4, total, temp, clouds, rain, solar_elev, solar_azimuth)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, records)
    conn.close()


if __name__ == "__main__":
    generate_today_solar_curve(150)
    print("Demo data with weather & solar metrics generated!")

"""
Database handler for SolarMonitor (Marstek Venus A)
Stores timestamped PV power readings in SQLite and calculates daily statistics.
"""

import sqlite3
import os
from datetime import datetime, date
import pandas as pd

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "solar_data.db")


def get_connection(db_path=DB_FILE):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=DB_FILE):
    """Initializes SQLite database and tables."""
    conn = get_connection(db_path)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pv_measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                pv1 REAL NOT NULL,
                pv2 REAL NOT NULL,
                pv3 REAL NOT NULL,
                pv4 REAL NOT NULL,
                total REAL NOT NULL,
                temp REAL,
                clouds REAL,
                rain REAL,
                solar_elev REAL,
                solar_azimuth REAL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pv_timestamp ON pv_measurements (timestamp)
        """)
        # Ensure optional weather and solar columns exist for existing databases
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(pv_measurements)")
        existing_cols = [row[1] for row in cur.fetchall()]
        for col_name in ["temp", "clouds", "rain", "solar_elev", "solar_azimuth"]:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE pv_measurements ADD COLUMN {col_name} REAL")
    conn.close()


def insert_measurement(
    pv1: float,
    pv2: float,
    pv3: float,
    pv4: float,
    total: float = None,
    temp: float = None,
    clouds: float = None,
    rain: float = None,
    solar_elev: float = None,
    solar_azimuth: float = None,
    db_path=DB_FILE
):
    """Inserts a single measurement record."""
    if total is None:
        total = pv1 + pv2 + pv3 + pv4
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO pv_measurements (timestamp, pv1, pv2, pv3, pv4, total, temp, clouds, rain, solar_elev, solar_azimuth)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    round(pv1, 2),
                    round(pv2, 2),
                    round(pv3, 2),
                    round(pv4, 2),
                    round(total, 2),
                    round(temp, 1) if temp is not None else None,
                    round(clouds, 0) if clouds is not None else None,
                    round(rain, 2) if rain is not None else None,
                    round(solar_elev, 1) if solar_elev is not None else None,
                    round(solar_azimuth, 1) if solar_azimuth is not None else None
                )
            )
    finally:
        conn.close()


def get_measurements_for_date(target_date: str = None, db_path=DB_FILE) -> pd.DataFrame:
    """
    Returns all measurements for a specific date (YYYY-MM-DD) as a DataFrame.
    Defaults to today if target_date is None.
    """
    if target_date is None:
        target_date = date.today().strftime("%Y-%m-%d")

    conn = get_connection(db_path)
    query = """
        SELECT timestamp, pv1, pv2, pv3, pv4, total, temp, clouds, rain, solar_elev, solar_azimuth
        FROM pv_measurements
        WHERE date(timestamp) = ?
        ORDER BY timestamp ASC
    """
    df = pd.read_sql_query(query, conn, params=(target_date,))
    conn.close()

    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def get_measurements_between(start_ts=None, end_ts=None, db_path=DB_FILE) -> pd.DataFrame:
    """
    Returns all measurements between start_ts and end_ts (datetime objects or 'YYYY-MM-DD HH:MM:SS' strings).
    """
    conn = get_connection(db_path)
    conditions = []
    params = []
    if start_ts is not None:
        if isinstance(start_ts, (datetime, date)):
            start_ts = start_ts.strftime("%Y-%m-%d %H:%M:%S")
        conditions.append("timestamp >= ?")
        params.append(start_ts)
    if end_ts is not None:
        if isinstance(end_ts, (datetime, date)):
            end_ts = end_ts.strftime("%Y-%m-%d %H:%M:%S")
        conditions.append("timestamp <= ?")
        params.append(end_ts)

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    query = f"""
        SELECT timestamp, pv1, pv2, pv3, pv4, total, temp, clouds, rain, solar_elev, solar_azimuth
        FROM pv_measurements
        {where_clause}
        ORDER BY timestamp ASC
    """
    df = pd.read_sql_query(query, conn, params=tuple(params))
    conn.close()

    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def get_latest_measurement(db_path=DB_FILE):
    """Returns the most recent measurement as a dict or None."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT timestamp, pv1, pv2, pv3, pv4, total, temp, clouds, rain, solar_elev, solar_azimuth
        FROM pv_measurements
        ORDER BY id DESC LIMIT 1
    """)
    row = cur.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def calculate_daily_energy(df: pd.DataFrame) -> dict:
    """
    Calculates energy produced in Watt-hours (Wh) for each PV channel
    using numerical trapezoidal integration over time.
    """
    results = {
        "pv1_wh": 0.0,
        "pv2_wh": 0.0,
        "pv3_wh": 0.0,
        "pv4_wh": 0.0,
        "total_wh": 0.0,
        "pv1_max": 0.0,
        "pv2_max": 0.0,
        "pv3_max": 0.0,
        "pv4_max": 0.0,
        "total_max": 0.0,
        "best_pv": None,
        "best_pv_key": None,
        "best_pv_wh": 0.0,
        "count": 0,
    }

    if df.empty or len(df) < 1:
        return results

    results["count"] = len(df)
    results["pv1_max"] = float(df["pv1"].max())
    results["pv2_max"] = float(df["pv2"].max())
    results["pv3_max"] = float(df["pv3"].max())
    results["pv4_max"] = float(df["pv4"].max())
    results["total_max"] = float(df["total"].max())

    if len(df) == 1:
        # Just 1 point, assume small slice or 0 Wh
        return results

    # Compute time delta in hours between consecutive records
    # Cap gaps longer than 15 minutes (e.g. night or script stopped) to prevent over-estimation
    time_diff_hours = df["timestamp"].diff().dt.total_seconds().fillna(0) / 3600.0
    time_diff_hours = time_diff_hours.clip(upper=0.25)  # max 15 mins

    for ch in ["pv1", "pv2", "pv3", "pv4"]:
        # Trapezoidal rule: (P_i + P_{i-1})/2 * delta_t_hours
        p_avg = (df[ch] + df[ch].shift(1).fillna(df[ch])) / 2.0
        wh = (p_avg * time_diff_hours).sum()
        results[f"{ch}_wh"] = round(float(wh), 2)

    results["total_wh"] = round(
        results["pv1_wh"] + results["pv2_wh"] + results["pv3_wh"] + results["pv4_wh"], 2
    )

    # Determine winning PV
    pv_energy = {
        "pv1": results["pv1_wh"],
        "pv2": results["pv2_wh"],
        "pv3": results["pv3_wh"],
        "pv4": results["pv4_wh"],
    }
    best_key = max(pv_energy, key=pv_energy.get)
    results["best_pv_key"] = best_key
    results["best_pv"] = best_key.upper()
    results["best_pv_wh"] = pv_energy[best_key]

    return results


def clear_database(db_path=DB_FILE):
    """Clears all records from the pv_measurements table."""
    conn = get_connection(db_path)
    with conn:
        conn.execute("DELETE FROM pv_measurements")
    conn.close()


calculate_energy = calculate_daily_energy


def get_available_dates(db_path=DB_FILE):
    """Returns list of distinct dates (YYYY-MM-DD) stored in the database."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT date(timestamp) as dt
        FROM pv_measurements
        ORDER BY dt DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [r["dt"] for r in rows if r["dt"]]

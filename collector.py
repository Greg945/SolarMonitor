"""
Background service that polls Marstek Venus A at regular intervals
and writes readings into the SQLite database.
"""

import time
import argparse
import logging
from db import init_db, insert_measurement
from venus_client import query_venus_status, parse_pv_powers, DEFAULT_IP, DEFAULT_PORT
from config_manager import load_config
from weather_service import get_current_weather

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("Collector")


def run_collector(
    ip: str = DEFAULT_IP,
    port: int = DEFAULT_PORT,
    interval: float = 5.0,
    pv1_divisor: float = 10.0,
    lat: float = None,
    lon: float = None,
    stop_event=None
):
    """Polls Venus A in a loop and stores measurements."""
    init_db()
    logger.info(f"Starting collector for Venus A at {ip}:{port} (interval: {interval}s)")

    consecutive_failures = 0
    while True:
        if stop_event and stop_event.is_set():
            logger.info("Collector received stop signal.")
            break

        resp = query_venus_status(ip=ip, port=port)
        powers = parse_pv_powers(resp, pv1_divisor=pv1_divisor)

        if powers:
            consecutive_failures = 0
            cfg_now = load_config()
            cur_lat = lat if lat is not None else float(cfg_now.get("latitude", 50.0085))
            cur_lon = lon if lon is not None else float(cfg_now.get("longitude", 8.0199))
            w = get_current_weather(cur_lat, cur_lon)

            insert_measurement(
                pv1=powers["pv1"],
                pv2=powers["pv2"],
                pv3=powers["pv3"],
                pv4=powers["pv4"],
                total=powers["total"],
                temp=w.get("temperature"),
                clouds=w.get("clouds"),
                rain=w.get("rain"),
                solar_elev=w.get("solar_elevation"),
                solar_azimuth=w.get("solar_azimuth")
            )
            p_names = cfg_now.get("panel_names", {})
            n1 = p_names.get("pv1", "PV1")
            n2 = p_names.get("pv2", "PV2")
            n3 = p_names.get("pv3", "PV3")
            n4 = p_names.get("pv4", "PV4")

            logger.info(
                f"{n1}: {powers['pv1']:6.1f}W | {n2}: {powers['pv2']:6.1f}W | "
                f"{n3}: {powers['pv3']:6.1f}W | {n4}: {powers['pv4']:6.1f}W | Total: {powers['total']:6.1f}W"
            )
        else:
            consecutive_failures += 1
            if consecutive_failures == 1 or consecutive_failures % 30 == 0:
                logger.warning(
                    f"No response from Venus A at {ip}:{port} (offline/sleep or unreachable). Retrying..."
                )

        time.sleep(interval)


if __name__ == "__main__":
    cfg = load_config()
    default_ip = cfg.get("ip", DEFAULT_IP)
    default_port = int(cfg.get("port", DEFAULT_PORT))
    default_interval = float(cfg.get("interval", 5.0))
    default_div = float(cfg.get("pv1_divisor", 10.0))

    parser = argparse.ArgumentParser(description="Venus A Solar Data Collector")
    parser.add_argument("--ip", default=default_ip, help=f"Venus A IP address (default: {default_ip})")
    parser.add_argument("--port", type=int, default=default_port, help=f"Venus A Port (default: {default_port})")
    parser.add_argument("--interval", type=float, default=default_interval, help=f"Polling interval in seconds (default: {default_interval})")
    parser.add_argument("--pv1-div", type=float, default=default_div, help=f"Divisor for PV1 power (default: {default_div})")

    args = parser.parse_args()

    try:
        run_collector(
            ip=args.ip,
            port=args.port,
            interval=args.interval,
            pv1_divisor=args.pv1_div
        )
    except KeyboardInterrupt:
        logger.info("Collector stopped by user.")

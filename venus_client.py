"""
Client for communicating with Marstek Venus A via local UDP API.
"""

import socket
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

DEFAULT_IP = "192.168.178.160"
DEFAULT_PORT = 30000


def query_venus_status(ip: str = DEFAULT_IP, port: int = DEFAULT_PORT, timeout: float = 2.5) -> Optional[Dict[str, Any]]:
    """
    Sends 'PV.GetStatus' command to Marstek Venus A via UDP.
    Returns the parsed JSON response or None on failure.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)

    request = {
        "id": 1,
        "method": "PV.GetStatus",
        "params": {
            "id": 0
        }
    }

    try:
        sock.sendto(json.dumps(request).encode("utf-8"), (ip, port))
        data, _ = sock.recvfrom(4096)
        response = json.loads(data.decode("utf-8"))
        return response
    except socket.timeout:
        return None
    except Exception as e:
        logger.error(f"Error querying Venus A at {ip}:{port}: {e}")
        return None
    finally:
        sock.close()


def parse_pv_powers(response: Optional[Dict[str, Any]], pv1_divisor: float = 10.0) -> Optional[Dict[str, float]]:
    """
    Extracts pv1, pv2, pv3, pv4 power values (in Watts) from the API response.
    """
    if not response or "result" not in response:
        return None

    pv = response["result"]

    raw_pv1 = pv.get("pv1_power", 0) or 0
    raw_pv2 = pv.get("pv2_power", 0) or 0
    raw_pv3 = pv.get("pv3_power", 0) or 0
    raw_pv4 = pv.get("pv4_power", 0) or 0

    pv1 = raw_pv1 / pv1_divisor if pv1_divisor > 0 else raw_pv1
    pv2 = float(raw_pv2)
    pv3 = float(raw_pv3)
    pv4 = float(raw_pv4)
    total = pv1 + pv2 + pv3 + pv4

    return {
        "pv1": round(pv1, 2),
        "pv2": round(pv2, 2),
        "pv3": round(pv3, 2),
        "pv4": round(pv4, 2),
        "total": round(total, 2)
    }

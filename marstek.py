import socket
import json
import time
import os

# Marstek Venus A
IP = "192.168.178.160"
PORT = 30000

def get_solar():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3)

    request = {
        "id": 1,
        "method": "PV.GetStatus",
        "params": {
            "id": 0
        }
    }

    try:
        sock.sendto(
            json.dumps(request).encode("utf-8"),
            (IP, PORT)
        )

        data, _ = sock.recvfrom(4096)
        response = json.loads(data.decode("utf-8"))

        if "result" not in response:
            print("API Fehler:", response)
            return

        pv = response["result"]

        # PV-Leistungen auslesen
        pv1 = (pv.get("pv1_power", 0) or 0) / 10
        pv2 = pv.get("pv2_power", 0) or 0
        pv3 = pv.get("pv3_power", 0) or 0
        pv4 = pv.get("pv4_power", 0) or 0

        # Gesamtleistung
        total = pv1 + pv2 + pv3 + pv4

        # Anzeige aktualisieren
        os.system("cls" if os.name == "nt" else "clear")

        print("=" * 35)
        print("       MARSTEK VENUS A")
        print("=" * 35)

        print(f"PV Eingang 1: {pv1:8.1f} W")
        print(f"PV Eingang 2: {pv2:8.1f} W")
        print(f"PV Eingang 3: {pv3:8.1f} W")
        print(f"PV Eingang 4: {pv4:8.1f} W")

        print("-" * 35)
        print(f"SOLAR GESAMT: {total:8.1f} W")
        print("=" * 35)

        print("\nAktualisierung alle 2 Sekunden")
        print("Beenden mit STRG + C")

    except socket.timeout:
        print("Keine Antwort von Venus A!")

    except Exception as e:
        print("Fehler:", e)

    finally:
        sock.close()


try:
    while True:
        get_solar()
        time.sleep(2)

except KeyboardInterrupt:
    print("\nProgramm beendet.")
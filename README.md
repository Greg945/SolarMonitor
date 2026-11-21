# ☀️ Marstek Venus A – Solar Monitor & Einzelkanal-Dashboard

Ein lokales Web-Dashboard zur Überwachung der einzelnen PV-Eingänge (PV 1, PV 2, PV 3, PV 4) des **Marstek Venus A** Speichersystems inklusive automatischer Ermittlung des täglichen Sieger-Panels.

Die offizielle Marstek-App zeigt standardmäßig nur die summierte Gesamtleistung aller Panels an. Dieses Dashboard schlüsselt die Daten auf, visualisiert den Tagesverlauf und berechnet den genauen Energieertrag pro Eingang.

---

## 🚀 Raspberry Pi: Installation und Autostart

Auf einem Raspberry Pi mit aktuellem **Raspberry Pi OS (64-Bit)** genügt nach der Ersteinrichtung dieser Befehl. Er klont das Projekt, legt eine virtuelle Python-Umgebung an, installiert alle Pakete und richtet den Autostart ein:

```bash
git clone https://github.com/Greg945/SolarMonitor.git && cd SolarMonitor && bash install_pi.sh
```

Das Dashboard startet danach automatisch bei jedem Einschalten des Pi. Öffne es von einem Gerät im selben Heimnetz unter `http://<IP-Adresse-des-Pi>:8501`. Die IP-Adresse zeigt das Installationsskript am Ende an.

### Updates vom Laptop übernehmen

Wenn du Änderungen auf dem Laptop nach GitHub pushst, lädt der Pi sie beim nächsten Start automatisch. Für ein sofortiges Update ohne Neustart genügt auf dem Pi:

```bash
sudo systemctl restart solar-monitor
```

Das Update holt den neuesten Stand des ausgecheckten Branches und installiert geänderte Requirements, bevor die App startet. Einstellungen und Messdaten auf dem Pi bleiben lokal erhalten. App-Einstellungen werden in `config.local.json` gespeichert; die Messdaten liegen in `solar_data.db`.

Nützliche Befehle auf dem Pi:

```bash
sudo systemctl status solar-monitor
sudo journalctl -u solar-monitor -f
```

### Lokal starten

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Unter Windows lässt sich die Umgebung so erstellen:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

---

## 🏆 Warum Streamlit? (Vergleich mit Gradio & Flask)

| Modul | Bewertung für diesen Anwendungsfall |
|---|---|
| **Streamlit** (Gewählt) | ⭐ **Ideal**: Bereits in deiner Umgebung installiert. Entwickelt genau für Live-Dashboards, Zeitreihen-Diagramme, Metriken und Tabellen. Kein manuelles HTML/CSS/JavaScript nötig. Besitzt automatischen Auto-Refresh. |
| **Gradio** | ⚠️ Eher für KI/Machine-Learning-Modelle gedacht (Eingabe-Formular $\rightarrow$ Ausgabe). Weniger flexibel für kontinuierliche IoT-Live-Dashboards mit Hintergrund-Logging. |
| **Flask / FastAPI** | ⚠️ Erfordert das komplette manuelle Schreiben von Frontend (HTML5, CSS, Chart.js / Plotly.js) und WebSocket/Polling-Logik. Deutlich höherer Wartungsaufwand. |

---

## ✨ Features

1. **Echte Einzelkanal-Messung & individuelle Panel-Namen**:
   - Zeigt aktuelle Watt-Leistung für alle 4 Eingänge und Gesamt.
   - Die Namen der Panels können im Tab **⚙️ Einstellungen** frei benannt werden (z. B. *"Neben Batterie"*, *"Richtung Kirschbaum"*, etc.) und werden dauerhaft in `config.local.json` gesichert.
   - Berücksichtigt den Firmware-Skalierungsfaktor (z.B. PV1 $\div 10$).
2. **🏆 Tagessieger & flexibler Zeitraum für Panel-Ertrag & Anteile**:
   - Berechnet über numerische Integration (Trapezregel) den tatsächlichen Energieertrag in **Wattstunden (Wh)** bzw. **Kilowattstunden (kWh)** pro Eingang.
   - Im Tab **📊 Panel-Ertrag & Anteile** kann der Zeitraum flexibel gewählt werden:
     - ⏱️ **Letzte Stunde**
     - 📅 **Heute (bzw. ausgewählter Tag)**
     - ⏳ **Letzte 24 Stunden**
     - 📆 **Letzte 7 Tage (Woche)**
     - ♾️ **Gesamter Zeitraum**
   - Balkendiagramm, Donut-Diagramm und die Ertragstabelle passen sich sofort an und heben den jeweiligen Spitzenreiter hervor.
3. **🌤️ 2. Graph: Wetter & Sonnenstand (Einfluss auf die PV-Leistung)**:
   - **Sonnenhöhe (°):** Exakte astronomische Sonnenhöhe über dem Horizont (NOAA-Algorithmus).
   - **Sonnenazimuth (°):** Sonnenkompasswinkel (z. B. 135° = Südost, 180° = Süd/Höchststand, 225° = Südwest) mit Himmelsrichtungsanzeige.
   - **Wetterdaten:** Temperatur (°C), Bewölkung (%) und Regen (mm) über die Open-Meteo API.
   - Ermöglicht den direkten Vergleich: Warum bricht die Leistung um 11:30 ein? (Bewölkungsspitze!) Welches Panel profitiert vom aktuellen Sonnenwinkel?
4. **📍 Konfigurierbarer Standort**:
   - Voreingestellt auf **Oestrich-Winkel** (50.0085° N, 8.0199° E).
   - Koordinaten können in den Einstellungen beliebig angepasst werden.
5. **Automatischer Logger-Start & eingeklappte Seitenleiste**:
   - Beim Öffnen des Dashboards ist die Seitenleiste standardmäßig **eingeklappt** für eine aufgeräumte Vollbild-Sicht.
   - Der Datenlogger startet beim Aufrufen der Seite **sofort automatisch** im Hintergrund (konfigurierbar).
6. **Lokale Speicherung & Einstellungen (`config.local.json` & `solar_data.db`)**:
   - Alle Einstellungen (IP, Port, Namen, Koordinaten, Intervalle) werden lokal in `config.local.json` gespeichert.
   - Messwerte inklusive Umwelt- und Sonnendaten liegen persistent in SQLite (`solar_data.db`).
   - CSV-Download für Excel / Auswertungen.
5. **Integrierter oder separater Datenlogger**:
   - Kann direkt in der Sidebar der Web-App gestartet werden (`▶️ Starten`).
   - Oder als Standalone-Dienst im Hintergrund laufen:
     ```bash
     python collector.py --interval 5.0
     ```
6. **Demo-Daten-Generator**:
   - Wenn die Sonne nicht scheint oder der Wechselrichter im Standby ist: Ein Klick auf *"📊 Demo-Tageskurve erzeugen"* generiert realistische Solarkurven zum Testen.

---

## 📁 Projektstruktur

- `app.py` – Die Streamlit-Webanwendung (Dashboard, Graphen, Metriken)
- `venus_client.py` – Kommunikation mit der Venus A über das lokale UDP-Protokoll (`PV.GetStatus`)
- `db.py` – SQLite-Speicherung und Energieberechnungen ($\int P\,dt$)
- `collector.py` – Standalone-Hintergrunddienst zum kontinuierlichen Aufzeichnen
- `generate_demo_data.py` – Testdaten-Generator
- `install_pi.sh` – Einrichtung der virtuellen Umgebung und des systemd-Autostarts auf Raspberry Pi OS
- `update_pi.sh` – Git- und Requirement-Update vor jedem Dienststart

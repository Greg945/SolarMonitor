# ☀️ Marstek Venus A – Solar Monitor & Einzelkanal-Dashboard

Ein lokales Web-Dashboard zur Überwachung der einzelnen PV-Eingänge (PV 1, PV 2, PV 3, PV 4) des **Marstek Venus A** Speichersystems inklusive automatischer Ermittlung des täglichen Sieger-Panels.

Die offizielle Marstek-App zeigt standardmäßig nur die summierte Gesamtleistung aller Panels an. Dieses Dashboard schlüsselt die Daten auf, visualisiert den Tagesverlauf und berechnet den genauen Energieertrag pro Eingang.

---

## 🚀 Schnellstart

Das Dashboard kann direkt per Befehl oder per Doppelklick gestartet werden:

```bash
streamlit run app.py
```
*Oder einfach per Doppelklick auf [start_dashboard.bat](file:///c:/Users/winde/Documents/GitHub/SolarMonitor/start_dashboard.bat).*

Das Dashboard öffnet sich anschließend automatisch im Browser unter `http://localhost:8501`.

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
   - Die Namen der Panels können im Tab **⚙️ Einstellungen** frei benannt werden (z. B. *"Neben Batterie"*, *"Richtung Kirschbaum"*, etc.) und werden dauerhaft in `config.json` gesichert.
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
6. **Lokale Speicherung & Einstellungen (`config.json` & `solar_data.db`)**:
   - Alle Einstellungen (IP, Port, Namen, Koordinaten, Intervalle) werden lokal in `config.json` gespeichert.
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

- [app.py](file:///c:/Users/winde/Documents/GitHub/SolarMonitor/app.py) – Die Streamlit Webanwendung (Dashboard, Graphen, Metriken)
- [venus_client.py](file:///c:/Users/winde/Documents/GitHub/SolarMonitor/venus_client.py) – Kommunikation mit der Venus A über das lokale UDP-Protokoll (`PV.GetStatus`)
- [db.py](file:///c:/Users/winde/Documents/GitHub/SolarMonitor/db.py) – SQLite-Speicherung & Energieberechnungen ($\int P\,dt$)
- [collector.py](file:///c:/Users/winde/Documents/GitHub/SolarMonitor/collector.py) – Standalone-Hintergrunddienst zum kontinuierlichen Aufzeichnen
- [generate_demo_data.py](file:///c:/Users/winde/Documents/GitHub/SolarMonitor/generate_demo_data.py) – Testdaten-Generator
- [marstek.py](file:///c:/Users/winde/Documents/GitHub/SolarMonitor/marstek.py) – Dein ursprüngliches Terminal-Skript

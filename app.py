"""
Streamlit Web Dashboard for Marstek Venus A Solar Monitor
Displays real-time and daily PV metrics per channel (PV1-PV4), highlights the best performing panel,
and provides weather, solar azimuth, and solar elevation correlation charts for Oestrich-Winkel or custom coordinates.
"""

import streamlit as st
import pandas as pd
import altair as alt
import threading
import time
from datetime import date, datetime, timedelta

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

from db import (
    init_db,
    insert_measurement,
    get_measurements_for_date,
    get_measurements_between,
    get_latest_measurement,
    calculate_daily_energy,
    get_available_dates,
    clear_database,
    DB_FILE,
)
from venus_client import query_venus_status, parse_pv_powers
from generate_demo_data import generate_today_solar_curve
from config_manager import load_config, save_config, DEFAULT_CONFIG
from weather_service import (
    get_solar_position,
    get_azimuth_direction,
    get_current_weather,
    get_weather_dataframe_for_date,
    DEFAULT_LOCATION_NAME,
    DEFAULT_LATITUDE,
    DEFAULT_LONGITUDE
)

# Initialize Database
init_db()

# Load Configuration
cfg = load_config()
loc_name = cfg.get("location_name", DEFAULT_LOCATION_NAME)
loc_lat = float(cfg.get("latitude", DEFAULT_LATITUDE))
loc_lon = float(cfg.get("longitude", DEFAULT_LONGITUDE))

# Page configuration - Sidebar is collapsed by default as requested
st.set_page_config(
    page_title="Venus A Solar Monitor",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Styling
st.markdown("""
<style>
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 14px;
        text-align: center;
        transition: transform 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
    }
    .winner-card {
        background: linear-gradient(135deg, rgba(255, 193, 7, 0.15), rgba(255, 152, 0, 0.25));
        border: 2px solid rgba(255, 193, 7, 0.5);
        border-radius: 14px;
        padding: 18px;
        margin-bottom: 18px;
        text-align: center;
    }
    .winner-title {
        font-size: 1.35rem;
        font-weight: 700;
        color: #ffc107;
        margin-bottom: 6px;
    }
    .winner-body {
        font-size: 1.05rem;
    }
    .env-banner {
        background: rgba(33, 150, 243, 0.08);
        border: 1px solid rgba(33, 150, 243, 0.25);
        border-radius: 12px;
        padding: 12px 18px;
        margin-bottom: 18px;
    }
</style>
""", unsafe_allow_html=True)


# --- Background Poller Thread Management ---
@st.cache_resource
def get_poller_state():
    return {
        "thread": None,
        "stop_event": threading.Event(),
        "is_running": False,
        "last_status": "Noch nicht gestartet",
        "last_poll_time": None
    }

poller_state = get_poller_state()


def background_worker(ip, port, interval, pv1_div, lat, lon, stop_event):
    while not stop_event.is_set():
        try:
            resp = query_venus_status(ip=ip, port=port, timeout=2.5)
            powers = parse_pv_powers(resp, pv1_divisor=pv1_div)
            if powers:
                w = get_current_weather(lat, lon)
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
                poller_state["last_status"] = f"OK: {powers['total']} W empfangen"
            else:
                poller_state["last_status"] = "Keine Antwort (Venus A offline/schläft)"
            poller_state["last_poll_time"] = datetime.now().strftime("%H:%M:%S")
        except Exception as e:
            poller_state["last_status"] = f"Fehler: {e}"

        # Sleep in small increments to be responsive to stop_event
        for _ in range(max(1, int(interval * 2))):
            if stop_event.is_set():
                break
            time.sleep(0.5)


def start_poller(ip, port, interval, pv1_div, lat, lon):
    if not poller_state["is_running"]:
        poller_state["stop_event"].clear()
        t = threading.Thread(
            target=background_worker,
            args=(ip, port, interval, pv1_div, lat, lon, poller_state["stop_event"]),
            daemon=True
        )
        poller_state["thread"] = t
        poller_state["is_running"] = True
        t.start()


def stop_poller():
    if poller_state["is_running"]:
        poller_state["stop_event"].set()
        poller_state["is_running"] = False
        poller_state["last_status"] = "Gestoppt"


# --- Auto-Start Logger on App Launch ---
if cfg.get("auto_start_logger", True) and not poller_state["is_running"]:
    start_poller(
        ip=cfg.get("ip", "192.168.178.160"),
        port=int(cfg.get("port", 30000)),
        interval=float(cfg.get("interval", 5.0)),
        pv1_div=float(cfg.get("pv1_divisor", 10.0)),
        lat=loc_lat,
        lon=loc_lon
    )


# --- Sidebar (Collapsed by default, available for quick status & tools) ---
st.sidebar.title("☀️ Schnellzugriff")

status_color = "🟢" if poller_state["is_running"] else "⚪"
st.sidebar.markdown(f"**Logger-Status:** {status_color} {'Aktiv (automatisch gestartet)' if poller_state['is_running'] else 'Inaktiv'}")
if poller_state["last_poll_time"]:
    st.sidebar.caption(f"Letzter Poll ({poller_state['last_poll_time']}): {poller_state['last_status']}")

st.sidebar.caption(f"📍 Standort: **{loc_name}** ({loc_lat:.3f}° N, {loc_lon:.3f}° E)")

col_side_start, col_side_stop = st.sidebar.columns(2)
if col_side_start.button("▶️ Start", width="stretch", disabled=poller_state["is_running"]):
    start_poller(cfg["ip"], int(cfg["port"]), float(cfg["interval"]), float(cfg["pv1_divisor"]), loc_lat, loc_lon)
    st.sidebar.success("Gestartet")
    st.rerun()

if col_side_stop.button("⏹️ Stop", width="stretch", disabled=not poller_state["is_running"]):
    stop_poller()
    st.sidebar.info("Gestoppt")
    st.rerun()

if st.sidebar.button("⚡ Jetzt 1x abfragen", width="stretch"):
    with st.spinner("Frage Venus A ab..."):
        resp = query_venus_status(ip=cfg["ip"], port=int(cfg["port"]), timeout=2.0)
        powers = parse_pv_powers(resp, pv1_divisor=float(cfg["pv1_divisor"]))
        if powers:
            w = get_current_weather(loc_lat, loc_lon)
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
            st.sidebar.success(f"{powers['total']} W gemessen!")
            st.rerun()
        else:
            st.sidebar.warning("Keine Antwort von Venus A.")

# Auto-refresh component
if cfg.get("auto_refresh", True) and st_autorefresh:
    st_autorefresh(
        interval=int(cfg.get("refresh_seconds", 5)) * 1000,
        key="pv_dashboard_autorefresh"
    )

# Date selector in sidebar
available_dates = get_available_dates()
today_str = date.today().strftime("%Y-%m-%d")
if today_str not in available_dates:
    available_dates.insert(0, today_str)

st.sidebar.markdown("---")
st.sidebar.subheader("📅 Tag auswählen")
selected_date = st.sidebar.selectbox("Historie", options=available_dates, index=0)

# Sidebar Tools
st.sidebar.markdown("---")
st.sidebar.subheader("🛠️ Daten-Tools")
with st.sidebar.expander("🗑️ Datenbank leeren", expanded=False):
    st.caption("Löscht alle Messwerte unwiderruflich.")
    confirm_del = st.checkbox("Wirklich alle Messwerte löschen?")
    if st.button("Datenbank jetzt leeren", width="stretch", disabled=not confirm_del):
        clear_database()
        st.success("Datenbank geleert!")
        st.rerun()

with st.sidebar.expander("🧪 Demo-Daten generieren", expanded=False):
    st.caption("Erzeugt realistische Solarkurven inkl. Wetter- und Sonnendaten.")
    if st.button("📊 Demo-Kurve erzeugen", width="stretch"):
        generate_today_solar_curve(150)
        st.success("Testdaten generiert!")
        st.rerun()


# --- Main Navigation Tabs ---
tab_dashboard, tab_settings = st.tabs(["📊 Solar Dashboard", "⚙️ Einstellungen & Panel-Namen"])


# ==============================================================================
# TAB 1: SOLAR DASHBOARD
# ==============================================================================
with tab_dashboard:
    # Panel display names from config
    p_names = cfg.get("panel_names", DEFAULT_CONFIG["panel_names"])
    name_pv1 = p_names.get("pv1", "PV 1")
    name_pv2 = p_names.get("pv2", "PV 2")
    name_pv3 = p_names.get("pv3", "PV 3")
    name_pv4 = p_names.get("pv4", "PV 4")

    st.title("☀️ Marstek Venus A – Solar & Umwelt Monitor")
    st.caption(
        f"📅 **{selected_date}** | 📍 Standort: **{loc_name}** ({loc_lat:.3f}° N, {loc_lon:.3f}° E) | "
        f"Auto-Refresh: **{cfg.get('refresh_seconds', 5)}s** | Logger: **{'Aktiv 🟢' if poller_state['is_running'] else 'Inaktiv ⚪'}**"
    )

    # Load data for selected date
    df = get_measurements_for_date(selected_date)
    stats = calculate_daily_energy(df)
    latest = get_latest_measurement()

    # Calculate real-time solar position & current weather
    live_elev, live_azim = get_solar_position(loc_lat, loc_lon)
    live_azim_dir = get_azimuth_direction(live_azim)
    live_weather = get_current_weather(loc_lat, loc_lon)

    # Live weather values with fallback to latest DB measurement
    w_temp = live_weather.get("temperature") if live_weather else None
    if w_temp is None and latest and latest.get("temp") is not None:
        w_temp = latest.get("temp")

    w_clouds = live_weather.get("clouds") if live_weather else None
    if w_clouds is None and latest and latest.get("clouds") is not None:
        w_clouds = latest.get("clouds")

    w_rain = live_weather.get("rain") if live_weather else None
    if w_rain is None and latest and latest.get("rain") is not None:
        w_rain = latest.get("rain")

    # Show Winner Banner
    if stats["count"] > 0 and stats.get("best_pv_key"):
        best_key = stats["best_pv_key"]
        best_name = p_names.get(best_key, best_key.upper())
        best_wh = stats["best_pv_wh"]
        total_wh = stats["total_wh"]
        share = (best_wh / total_wh * 100) if total_wh > 0 else 0

        st.markdown(f"""
        <div class="winner-card">
            <div class="winner-title">🏆 Tagessieger: <b>{best_name}</b> ({best_key.upper()})</div>
            <div class="winner-body">
                Mit <b>{best_wh:.1f} Wh ({best_wh/1000:.2f} kWh)</b> hat <b>{best_name}</b> heute am meisten Strom erzeugt!
                <br>
                Das entspricht <b>{share:.1f}%</b> des heutigen Gesamtertrags von <b>{total_wh:.1f} Wh ({total_wh/1000:.2f} kWh)</b>.
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Noch keine Messdaten für diesen Tag vorhanden. Der automatische Logger läuft im Hintergrund.")

    # --- Live Environment & Sun Status Header ---
    env_col1, env_col2, env_col3, env_col4, env_col5 = st.columns(5)
    env_col1.metric("☀️ Sonnenhöhe", f"{live_elev:.1f}°", delta="Über Horizont" if live_elev > 0 else "Unter Horizont")
    env_col2.metric("🧭 Sonnenazimuth", f"{live_azim:.1f}°", delta=live_azim_dir)
    env_col3.metric("🌡️ Temperatur", f"{w_temp:.1f} °C" if w_temp is not None else "-- °C")
    env_col4.metric("☁️ Bewölkung", f"{w_clouds:.0f} %" if w_clouds is not None else "-- %")
    env_col5.metric("🌧️ Regen", f"{w_rain:.1f} mm" if w_rain is not None else "0.0 mm")

    st.markdown("---")

    # --- Metric Cards Row: PV Channels ---
    st.subheader("⚡ Aktuelle Panel-Leistung & Tagesertrag")
    m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)

    def render_pv_metric(col, pv_key, display_label):
        live_w = latest[pv_key] if latest else 0.0
        day_wh = stats.get(f"{pv_key}_wh", 0.0)
        max_w = stats.get(f"{pv_key}_max", 0.0)
        col.metric(
            label=display_label,
            value=f"{live_w:.1f} W",
            delta=f"Max: {max_w:.0f} W"
        )
        col.caption(f"Ertrag: **{day_wh:.1f} Wh** ({day_wh/1000:.2f} kWh)")

    render_pv_metric(m_col1, "pv1", f"⚡ {name_pv1}")
    render_pv_metric(m_col2, "pv2", f"⚡ {name_pv2}")
    render_pv_metric(m_col3, "pv3", f"⚡ {name_pv3}")
    render_pv_metric(m_col4, "pv4", f"⚡ {name_pv4}")

    # Total metric
    total_live = latest["total"] if latest else 0.0
    total_wh = stats["total_wh"]
    total_max = stats["total_max"]
    m_col5.metric(
        label="☀️ Gesamt",
        value=f"{total_live:.1f} W",
        delta=f"Max: {total_max:.0f} W"
    )
    m_col5.caption(f"Gesamt: **{total_wh:.1f} Wh** ({total_wh/1000:.2f} kWh)")

    st.divider()

    # --- Visualizations ---
    tab_graphs, tab_bar, tab_table = st.tabs([
        "📈 Zeitreihen-Vergleich (PV & Wetter)",
        "📊 Panel-Ertrag & Anteile",
        "📋 Messdaten-Tabelle"
    ])

    # Mapping and color scales for PV charts
    channel_label_map = {
        "pv1": name_pv1,
        "pv2": name_pv2,
        "pv3": name_pv3,
        "pv4": name_pv4,
        "total": "Gesamt"
    }
    all_channel_labels = [name_pv1, name_pv2, name_pv3, name_pv4, "Gesamt"]
    pv_color_range = ["#f39c12", "#e74c3c", "#3498db", "#2ecc71", "#9b59b6"]
    pv_color_scale = alt.Scale(domain=all_channel_labels, range=pv_color_range)

    # ==========================================================================
    # SUB-TAB 1: DUAL CHARTS (PV POWER + WEATHER / SUN)
    # ==========================================================================
    with tab_graphs:
        # Time Axis Synchronization Controls
        st.markdown("#### ⏱️ Zeitachsen-Synchronisation für beide Graphen")
        col_t1, col_t2 = st.columns([3, 2])
        with col_t1:
            time_mode = st.radio(
                "Zeitbereich für beide Diagramme festlegen:",
                options=[
                    "🎯 Messzeitraum (exakter Zoom auf die aufgezeichneten PV-Werte)",
                    "☀️ Sonnenstunden (07:00 – 19:00)",
                    "🌍 Ganzer Tag (00:00 – 23:59)"
                ],
                index=0,
                horizontal=True
            )
        with col_t2:
            graph_layout = st.radio(
                "Darstellung:",
                options=[
                    "📊 2 synchrone Graphen untereinander",
                    "🔀 Kombinierte Überlagerung (PV vs. Wetter)"
                ],
                index=0,
                horizontal=True
            )

        # Compute synchronized shared time scale
        target_day = datetime.strptime(selected_date, "%Y-%m-%d")
        if "Messzeitraum" in time_mode and not df.empty:
            min_ts = df["timestamp"].min()
            max_ts = df["timestamp"].max()
            diff_min = (max_ts - min_ts).total_seconds() / 60.0
            pad_min = 10 if diff_min > 30 else 3
            start_dt = min_ts - timedelta(minutes=pad_min)
            end_dt = max_ts + timedelta(minutes=pad_min)
        elif "Sonnenstunden" in time_mode:
            start_dt = target_day.replace(hour=7, minute=0, second=0)
            end_dt = target_day.replace(hour=19, minute=0, second=0)
        else:  # Ganzer Tag
            start_dt = target_day.replace(hour=0, minute=0, second=0)
            end_dt = target_day.replace(hour=23, minute=59, second=59)

        shared_x_scale = alt.Scale(domain=[start_dt, end_dt])

        # Prepare weather dataset
        df_weather = get_weather_dataframe_for_date(loc_lat, loc_lon, selected_date)

        # --- VIEW OPTION 1: TWO SYNCHRONIZED CHARTS STACKED ---
        if graph_layout == "📊 2 synchrone Graphen untereinander":
            st.markdown("### 1️⃣ PV-Leistungskurve (Watt)")

            if not df.empty:
                selected_channels = st.multiselect(
                    "Angezeigte PV-Kanäle auswählen:",
                    options=all_channel_labels,
                    default=all_channel_labels,
                    key="pv_channel_selector"
                )

                df_melted = df.melt(
                    id_vars=["timestamp"],
                    value_vars=["pv1", "pv2", "pv3", "pv4", "total"],
                    var_name="channel_raw",
                    value_name="power"
                )
                df_melted["Kanal"] = df_melted["channel_raw"].map(channel_label_map)
                df_pv_filtered = df_melted[df_melted["Kanal"].isin(selected_channels)]

                chart_pv = alt.Chart(df_pv_filtered).mark_line(strokeWidth=2.2).encode(
                    x=alt.X(
                        "timestamp:T",
                        title="Uhrzeit",
                        axis=alt.Axis(format="%H:%M"),
                        scale=shared_x_scale
                    ),
                    y=alt.Y("power:Q", title="Leistung (Watt)"),
                    color=alt.Color("Kanal:N", scale=pv_color_scale, title="Eingang / Panel"),
                    tooltip=[
                        alt.Tooltip("timestamp:T", title="Zeit", format="%H:%M:%S"),
                        alt.Tooltip("Kanal:N", title="Panel"),
                        alt.Tooltip("power:Q", title="Leistung (W)", format=".1f")
                    ]
                ).properties(height=320).interactive()

                st.altair_chart(chart_pv, use_container_width=True)
            else:
                st.info("Keine PV-Messwerte für diesen Tag vorhanden.")

            st.markdown("---")

            # --- 2nd Graph: Synchronized Weather & Sun ---
            st.markdown("### 2️⃣ Wetter- & Sonnenstand-Kurve (Gleiche Uhrzeit synchronisiert)")
            st.caption(
                "Die Zeitachse ist **exakt auf die gleiche Uhrzeit wie Graph 1 synchronisiert**, "
                "sodass du Bewölkung, Temperatur und Sonnenwinkel direkt vergleichen kannst."
            )

            weather_metrics_options = [
                "☀️ Sonnenhöhe (°)",
                "☁️ Bewölkung (%)",
                "🌡️ Temperatur (°C)",
                "🌧️ Regen (mm)",
                "🧭 Sonnenazimuth (°)"
            ]

            selected_weather_metrics = st.multiselect(
                "Umweltparameter im 2. Graphen anzeigen:",
                options=weather_metrics_options,
                default=["☀️ Sonnenhöhe (°)", "☁️ Bewölkung (%)", "🌡️ Temperatur (°C)"],
                key="weather_metrics_selector"
            )

            # Build synchronized weather chart
            col_rename = {
                "Sonnenhöhe (°)": "☀️ Sonnenhöhe (°)",
                "Bewölkung (%)": "☁️ Bewölkung (%)",
                "Temperatur (°C)": "🌡️ Temperatur (°C)",
                "Regen (mm)": "🌧️ Regen (mm)",
                "Sonnenazimuth (°)": "🧭 Sonnenazimuth (°)"
            }
            df_w_renamed = df_weather.rename(columns=col_rename)

            valid_selected = [c for c in selected_weather_metrics if c in df_w_renamed.columns]
            if valid_selected:
                df_w_melted = df_w_renamed.melt(
                    id_vars=["timestamp"],
                    value_vars=valid_selected,
                    var_name="Parameter",
                    value_name="Wert"
                ).dropna(subset=["Wert"])

                weather_color_scale = alt.Scale(
                    domain=[
                        "☀️ Sonnenhöhe (°)",
                        "☁️ Bewölkung (%)",
                        "🌡️ Temperatur (°C)",
                        "🌧️ Regen (mm)",
                        "🧭 Sonnenazimuth (°)"
                    ],
                    range=["#f1c40f", "#95a5a6", "#e67e22", "#3498db", "#8e44ad"]
                )

                chart_weather = alt.Chart(df_w_melted).mark_line(strokeWidth=2.2, point=alt.OverlayMarkDef(size=25)).encode(
                    x=alt.X(
                        "timestamp:T",
                        title="Uhrzeit",
                        axis=alt.Axis(format="%H:%M"),
                        scale=shared_x_scale
                    ),
                    y=alt.Y("Wert:Q", title="Messwert (Skala)"),
                    color=alt.Color("Parameter:N", scale=weather_color_scale, title="Umweltparameter"),
                    tooltip=[
                        alt.Tooltip("timestamp:T", title="Uhrzeit", format="%H:%M"),
                        alt.Tooltip("Parameter:N", title="Parameter"),
                        alt.Tooltip("Wert:Q", title="Wert", format=".1f")
                    ]
                ).properties(height=320).interactive()

                st.altair_chart(chart_weather, use_container_width=True)

        # --- VIEW OPTION 2: COMBINED OVERLAY CHART (DUAL AXIS) ---
        else:
            st.markdown("### 🔀 Kombinierte Überlagerung: PV-Gesamtleistung vs. Bewölkung & Sonnenhöhe")
            st.caption("Beide Kurven liegen direkt übereinander: Gelb = PV Leistung (Watt, linke Achse) | Grau/Gold = Bewölkung & Sonnenhöhe (Skala 0-100, rechte Achse).")

            if not df.empty:
                # Base chart for PV power (Left Y-Axis)
                base = alt.Chart(df).encode(
                    x=alt.X(
                        "timestamp:T",
                        title="Uhrzeit",
                        axis=alt.Axis(format="%H:%M"),
                        scale=shared_x_scale
                    )
                )

                area_pv = base.mark_area(opacity=0.3, color="#f39c12").encode(
                    y=alt.Y("total:Q", title="PV Gesamtleistung (Watt)", axis=alt.Axis(titleColor="#f39c12")),
                    tooltip=[
                        alt.Tooltip("timestamp:T", title="Zeit", format="%H:%M:%S"),
                        alt.Tooltip("total:Q", title="Gesamtleistung (W)", format=".1f")
                    ]
                )

                line_pv = base.mark_line(color="#e67e22", strokeWidth=2.5).encode(
                    y=alt.Y("total:Q")
                )

                # Weather overlay line (Right Y-Axis)
                col_rename = {
                    "Sonnenhöhe (°)": "☀️ Sonnenhöhe (°)",
                    "Bewölkung (%)": "☁️ Bewölkung (%)"
                }
                df_w_renamed = df_weather.rename(columns=col_rename)
                df_w_combo = df_w_renamed.melt(
                    id_vars=["timestamp"],
                    value_vars=["☀️ Sonnenhöhe (°)", "☁️ Bewölkung (%)"],
                    var_name="Umweltparameter",
                    value_name="Skala_0_100"
                ).dropna(subset=["Skala_0_100"])

                line_weather = alt.Chart(df_w_combo).mark_line(strokeWidth=2.2, strokeDash=[4, 4]).encode(
                    x=alt.X(
                        "timestamp:T",
                        scale=shared_x_scale
                    ),
                    y=alt.Y(
                        "Skala_0_100:Q",
                        title="Bewölkung (%) / Sonnenhöhe (°)",
                        scale=alt.Scale(domain=[0, 100]),
                        axis=alt.Axis(titleColor="#34495e")
                    ),
                    color=alt.Color(
                        "Umweltparameter:N",
                        scale=alt.Scale(
                            domain=["☀️ Sonnenhöhe (°)", "☁️ Bewölkung (%)"],
                            range=["#f1c40f", "#7f8c8d"]
                        ),
                        title="Umweltfaktor"
                    ),
                    tooltip=[
                        alt.Tooltip("timestamp:T", title="Uhrzeit", format="%H:%M"),
                        alt.Tooltip("Umweltparameter:N"),
                        alt.Tooltip("Skala_0_100:Q", title="Wert", format=".1f")
                    ]
                )

                combo_chart = alt.layer(area_pv + line_pv, line_weather).resolve_scale(
                    y="independent"
                ).properties(height=420).interactive()

                st.altair_chart(combo_chart, use_container_width=True)
            else:
                st.info("Keine PV-Messwerte für die Überlagerung vorhanden.")

        with st.expander("ℹ️ Hinweise zur Interpretation der Kurven", expanded=False):
            st.markdown("""
            * **☀️ Sonnenhöhe (°):** Gibt an, wie hoch die Sonne über dem Horizont steht (0° = Sonnenauf-/-untergang, ~25° = Maximum im Herbst/Winter, bis zu 63° im Sommer). Je höher die Sonne, desto senkrechter fällt das Licht ein.
            * **🧭 Sonnenazimuth (°):** Der Sonnenkompasswinkel (90° = Ost, 135° = Süd-Ost, 180° = Süd/Solar Noon, 225° = Süd-West, 270° = West). Hilft dir zu erkennen, welches Panel (je nach Ausrichtung) gerade optimal angestrahlt wird!
            * **☁️ Bewölkung (%):** Je höher dieser Wert, desto weniger direkte Sonnenstrahlen erreichen die Module. Plötzliche Einbrüche in Graph 1 korrelieren fast immer mit Spitzen in dieser Kurve.
            * **🌡️ Temperatur (°C):** PV-Module verlieren bei steigender Zelltemperatur ca. 0,35–0,4% Wirkungsgrad pro Grad über 25°C.
            """)

    # ==========================================================================
    # SUB-TAB 2: BAR & DONUT COMPARISON (WITH TIMEFRAME SELECTOR)
    # ==========================================================================
    with tab_bar:
        st.markdown("#### 📊 Panel-Ertrag & Anteilsauswertung")

        yield_timeframe = st.radio(
            "Zeitraum für die Ertragsberechnung auswählen:",
            options=[
                "⏱️ Letzte Stunde",
                "📅 Heute (bzw. ausgewählter Tag)",
                "⏳ Letzte 24 Stunden",
                "📆 Letzte 7 Tage (Woche)",
                "♾️ Gesamter Zeitraum"
            ],
            index=1,
            horizontal=True
        )

        now_dt = datetime.now()
        if "Letzte Stunde" in yield_timeframe:
            df_yield = get_measurements_between(now_dt - timedelta(hours=1), now_dt)
            tf_label = "der letzten Stunde"
        elif "Heute" in yield_timeframe:
            df_yield = df  # current selected date dataframe
            tf_label = f"von heute ({selected_date})"
        elif "24 Stunden" in yield_timeframe:
            df_yield = get_measurements_between(now_dt - timedelta(hours=24), now_dt)
            tf_label = "der letzten 24 Stunden"
        elif "7 Tage" in yield_timeframe:
            df_yield = get_measurements_between(now_dt - timedelta(days=7), now_dt)
            tf_label = "der letzten 7 Tage"
        else:
            df_yield = get_measurements_between(None, None)
            tf_label = "des gesamten Aufzeichnungszeitraums"

        stats_yield = calculate_daily_energy(df_yield)

        # Highlight winner for this selected timeframe
        if stats_yield["count"] > 0 and stats_yield.get("best_pv_key"):
            win_key = stats_yield["best_pv_key"]
            win_name = p_names.get(win_key, win_key.upper())
            win_wh = stats_yield["best_pv_wh"]
            tot_wh = stats_yield["total_wh"]
            win_pct = (win_wh / tot_wh * 100) if tot_wh > 0 else 0

            st.markdown(f"""
            <div style="background: rgba(46, 204, 113, 0.12); border: 1.5px solid rgba(46, 204, 113, 0.4); border-radius: 10px; padding: 12px 18px; margin: 12px 0 18px 0;">
                🏆 <b>Spitzenreiter {tf_label}:</b> <b>{win_name}</b> ({win_key.upper()}) mit <b>{win_wh:.1f} Wh ({win_wh/1000:.3f} kWh)</b> – das sind <b>{win_pct:.1f}%</b> des Gesamtertrags ({tot_wh:.1f} Wh).
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info(f"Keine Messdaten {tf_label} vorhanden.")

        col_bar, col_pie = st.columns(2)

        bar_data = pd.DataFrame({
            "Panel": [name_pv1, name_pv2, name_pv3, name_pv4],
            "Kanal_ID": ["PV 1", "PV 2", "PV 3", "PV 4"],
            "Ertrag_Wh": [stats_yield["pv1_wh"], stats_yield["pv2_wh"], stats_yield["pv3_wh"], stats_yield["pv4_wh"]],
            "Ertrag_kWh": [
                round(stats_yield["pv1_wh"] / 1000, 3),
                round(stats_yield["pv2_wh"] / 1000, 3),
                round(stats_yield["pv3_wh"] / 1000, 3),
                round(stats_yield["pv4_wh"] / 1000, 3)
            ]
        })

        with col_bar:
            st.markdown(f"**Energieertrag pro Panel {tf_label} (Wh)**")
            bar_chart = alt.Chart(bar_data).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
                x=alt.X("Panel:N", title="Panel", sort=None),
                y=alt.Y("Ertrag_Wh:Q", title="Ertrag (Wh)"),
                color=alt.Color("Panel:N", scale=pv_color_scale, legend=None),
                tooltip=[
                    alt.Tooltip("Panel:N", title="Panel"),
                    alt.Tooltip("Kanal_ID:N", title="Eingang"),
                    alt.Tooltip("Ertrag_Wh:Q", title="Ertrag (Wh)", format=".1f"),
                    alt.Tooltip("Ertrag_kWh:Q", title="Ertrag (kWh)", format=".3f")
                ]
            ).properties(height=350)

            text_labels = bar_chart.mark_text(
                align="center",
                baseline="bottom",
                dy=-5,
                fontSize=13,
                fontWeight="bold"
            ).encode(
                text=alt.Text("Ertrag_Wh:Q", format=".1f")
            )

            st.altair_chart(bar_chart + text_labels, use_container_width=True)

        with col_pie:
            st.markdown(f"**Prozentualer Anteil {tf_label}**")
            sum_wh = bar_data["Ertrag_Wh"].sum()
            bar_data["Prozent"] = (bar_data["Ertrag_Wh"] / sum_wh * 100).round(1) if sum_wh > 0 else 0

            donut = alt.Chart(bar_data).mark_arc(innerRadius=65).encode(
                theta=alt.Theta("Ertrag_Wh:Q"),
                color=alt.Color("Panel:N", scale=pv_color_scale, title="Panel"),
                tooltip=[
                    alt.Tooltip("Panel:N", title="Panel"),
                    alt.Tooltip("Ertrag_Wh:Q", title="Wh", format=".1f"),
                    alt.Tooltip("Prozent:Q", title="Anteil", format=".1f")
                ]
            ).properties(height=350)

            st.altair_chart(donut, use_container_width=True)

        # Detailed breakdown table for this timeframe
        with st.expander(f"📋 Ertrags-Tabelle {tf_label} anzeigen", expanded=False):
            t_rows = []
            for ch_key, p_lbl, ch_lbl in [
                ("pv1", name_pv1, "PV 1"),
                ("pv2", name_pv2, "PV 2"),
                ("pv3", name_pv3, "PV 3"),
                ("pv4", name_pv4, "PV 4"),
                ("total", "Gesamt", "Alle")
            ]:
                e_wh = stats_yield.get(f"{ch_key}_wh", 0.0)
                m_pk = stats_yield.get(f"{ch_key}_max", 0.0)
                avg_p = df_yield[ch_key].mean() if not df_yield.empty else 0.0
                sh_pct = (e_wh / stats_yield["total_wh"] * 100) if stats_yield["total_wh"] > 0 and ch_key != "total" else (100.0 if ch_key == "total" else 0.0)
                t_rows.append({
                    "Panel-Name": p_lbl,
                    "Eingang": ch_lbl,
                    "Ertrag (Wh)": round(e_wh, 1),
                    "Ertrag (kWh)": round(e_wh / 1000.0, 3),
                    "Anteil (%)": f"{sh_pct:.1f}%",
                    "Max Peak (W)": round(m_pk, 1),
                    "Durchschnitt (W)": round(avg_p, 1),
                    "Status": "🏆 Spitzenreiter" if ch_key == stats_yield.get("best_pv_key") else ""
                })
            st.dataframe(pd.DataFrame(t_rows), width="stretch", hide_index=True)

    # ==========================================================================
    # SUB-TAB 3: DATA TABLES & CSV EXPORT
    # ==========================================================================
    with tab_table:
        st.markdown("#### Detaillierte Zusammenfassung der Panels")
        summary_rows = []
        for ch, name, ch_id in [
            ("pv1", name_pv1, "PV 1"),
            ("pv2", name_pv2, "PV 2"),
            ("pv3", name_pv3, "PV 3"),
            ("pv4", name_pv4, "PV 4"),
            ("total", "Gesamt", "Alle")
        ]:
            wh = stats.get(f"{ch}_wh", 0.0)
            max_val = stats.get(f"{ch}_max", 0.0)
            avg_val = df[ch].mean() if not df.empty else 0.0
            share_pct = (wh / stats["total_wh"] * 100) if stats["total_wh"] > 0 and ch != "total" else (100.0 if ch == "total" else 0.0)
            is_best = "🏆 Tagessieger" if ch == stats.get("best_pv_key") else ""

            summary_rows.append({
                "Panel-Name": name,
                "Eingang": ch_id,
                "Aktuell (W)": latest.get(ch, 0.0) if latest else 0.0,
                "Max Peak (W)": round(max_val, 1),
                "Durchschnitt (W)": round(avg_val, 1),
                "Ertrag (Wh)": round(wh, 1),
                "Ertrag (kWh)": round(wh / 1000.0, 3),
                "Anteil (%)": f"{share_pct:.1f}%",
                "Status": is_best
            })

        st.dataframe(pd.DataFrame(summary_rows), width="stretch", hide_index=True)

        st.markdown("---")
        st.markdown("#### Letzte 50 Rohmessungen (inkl. Umwelt- & Sonnendaten)")
        st.dataframe(
            df.sort_values(by="timestamp", ascending=False).head(50),
            width="stretch",
            hide_index=True
        )

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Messdaten als CSV herunterladen",
            data=csv,
            file_name=f"marstek_venus_a_{selected_date}.csv",
            mime="text/csv",
            width="stretch"
        )


# ==============================================================================
# TAB 2: EINSTELLUNGEN & PANEL-NAMEN
# ==============================================================================
with tab_settings:
    st.header("⚙️ Einstellungen")
    st.caption("Alle Änderungen werden dauerhaft in der lokalen Datei `config.json` gespeichert.")

    with st.form("settings_form"):
        # Section 1: Custom Panel Names
        st.subheader("🏷️ PV-Panel Namen")
        st.markdown("Vergib hier aussagekräftige Namen für deine einzelnen Solarmodule (z.B. nach Ausrichtung oder Montageort):")

        col_n1, col_n2 = st.columns(2)
        with col_n1:
            input_pv1 = st.text_input("Name für PV 1:", value=cfg.get("panel_names", {}).get("pv1", "PV 1"))
            input_pv3 = st.text_input("Name für PV 3:", value=cfg.get("panel_names", {}).get("pv3", "PV 3"))
        with col_n2:
            input_pv2 = st.text_input("Name für PV 2:", value=cfg.get("panel_names", {}).get("pv2", "PV 2"))
            input_pv4 = st.text_input("Name für PV 4:", value=cfg.get("panel_names", {}).get("pv4", "PV 4"))

        st.divider()

        # Section 2: Location & Coordinates for Solar / Weather
        st.subheader("📍 Standort & Koordinaten (für Sonnenstand & Wetter)")
        st.markdown(
            "Anhand deiner Koordinaten werden der genaue Sonnenstand (Sonnenhöhe & Azimuth) "
            "sowie lokale Wetterdaten (Temperatur, Bewölkung, Regen über Open-Meteo) ermittelt:"
        )
        col_loc1, col_loc2, col_loc3 = st.columns(3)
        with col_loc1:
            input_loc_name = st.text_input("Standort-Name:", value=loc_name)
        with col_loc2:
            input_lat = st.number_input("Breitengrad (Latitude °N):", value=loc_lat, format="%.5f")
        with col_loc3:
            input_lon = st.number_input("Längengrad (Longitude °E):", value=loc_lon, format="%.5f")

        st.caption("💡 *Tipp: Für Oestrich-Winkel ist 50.0085° N / 8.0199° E voreingestellt.*")

        st.divider()

        # Section 3: Connection settings
        st.subheader("🔌 Marstek Venus A Verbindung")
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            input_ip = st.text_input("IP-Adresse:", value=cfg.get("ip", "192.168.178.160"))
        with col_c2:
            input_port = st.number_input("UDP Port:", value=int(cfg.get("port", 30000)), min_value=1, max_value=65535)
        with col_c3:
            div_options = [10.0, 1.0]
            current_div = float(cfg.get("pv1_divisor", 10.0))
            div_idx = div_options.index(current_div) if current_div in div_options else 0
            input_pv1_div = st.selectbox(
                "PV 1 Teiler:",
                options=div_options,
                index=div_idx,
                help="10.0 falls deine Firmware PV 1 in Zehntel-Watt liefert, sonst 1.0."
            )

        st.divider()

        # Section 4: Logger & Auto-Refresh
        st.subheader("⏱️ Datenlogger & Dashboard-Aktualisierung")
        col_l1, col_l2 = st.columns(2)
        with col_l1:
            input_interval = st.slider("Abfrageintervall Venus A (Sekunden):", min_value=2, max_value=60, value=int(cfg.get("interval", 5)))
            input_autostart = st.checkbox(
                "Logger beim Starten automatisch aktivieren",
                value=cfg.get("auto_start_logger", True),
                help="Startet die Aufzeichnung sofort automatisch, wenn das Dashboard geöffnet wird."
            )
        with col_l2:
            input_refresh_sec = st.slider("Dashboard Auto-Refresh (Sekunden):", min_value=2, max_value=60, value=int(cfg.get("refresh_seconds", 5)))
            input_auto_refresh = st.checkbox("Auto-Refresh der Webseite aktivieren", value=cfg.get("auto_refresh", True))

        st.divider()

        # Save Button inside form
        col_btn1, col_btn2 = st.columns([1, 4])
        with col_btn1:
            save_clicked = st.form_submit_button("💾 Speichern", width="stretch")

        if save_clicked:
            new_cfg = {
                "ip": input_ip.strip(),
                "port": int(input_port),
                "interval": int(input_interval),
                "pv1_divisor": float(input_pv1_div),
                "auto_start_logger": bool(input_autostart),
                "auto_refresh": bool(input_auto_refresh),
                "refresh_seconds": int(input_refresh_sec),
                "location_name": input_loc_name.strip() or "Oestrich-Winkel",
                "latitude": float(input_lat),
                "longitude": float(input_lon),
                "panel_names": {
                    "pv1": input_pv1.strip() or "PV 1",
                    "pv2": input_pv2.strip() or "PV 2",
                    "pv3": input_pv3.strip() or "PV 3",
                    "pv4": input_pv4.strip() or "PV 4",
                }
            }
            save_config(new_cfg)

            # If logger is running and connection or location settings changed, restart logger
            if poller_state["is_running"]:
                stop_poller()
                time.sleep(0.5)
                start_poller(
                    new_cfg["ip"],
                    new_cfg["port"],
                    new_cfg["interval"],
                    new_cfg["pv1_divisor"],
                    new_cfg["latitude"],
                    new_cfg["longitude"]
                )

            st.success("✅ Einstellungen wurden erfolgreich in `config.json` gespeichert!")
            time.sleep(0.8)
            st.rerun()

    # Reset to defaults
    with st.expander("🔄 Standardeinstellungen wiederherstellen"):
        if st.button("Auf Werkseinstellungen zurücksetzen"):
            save_config(DEFAULT_CONFIG)
            st.success("Standardeinstellungen wiederhergestellt!")
            time.sleep(0.8)
            st.rerun()

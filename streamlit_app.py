from __future__ import annotations

import json
from datetime import datetime

import requests
import streamlit as st


st.set_page_config(page_title="Flight & Temperature Chat", page_icon="✈️", layout="wide")

BACKEND_URL = "http://127.0.0.1:8000"
CONNECT_TIMEOUT_SECONDS = 5
READ_TIMEOUT_SECONDS = 90

THEMES: dict[str, dict[str, str]] = {
    "Light": {
        "bg": "#f5f7fb",
        "surface": "rgba(255, 255, 255, 0.92)",
        "surface_strong": "#ffffff",
        "text": "#0f172a",
        "muted": "#475569",
        "accent": "#0f766e",
        "accent_soft": "rgba(15, 118, 110, 0.12)",
        "border": "rgba(15, 23, 42, 0.10)",
        "shadow": "0 18px 45px rgba(15, 23, 42, 0.08)",
        "gradient": "linear-gradient(135deg, #eff6ff 0%, #eefdf7 48%, #fff7ed 100%)",
    },
    "Dark": {
        "bg": "#0b1220",
        "surface": "rgba(15, 23, 42, 0.90)",
        "surface_strong": "#111827",
        "text": "#e5eefb",
        "muted": "#94a3b8",
        "accent": "#22c55e",
        "accent_soft": "rgba(34, 197, 94, 0.16)",
        "border": "rgba(148, 163, 184, 0.18)",
        "shadow": "0 18px 48px rgba(2, 6, 23, 0.42)",
        "gradient": "linear-gradient(135deg, #07111f 0%, #0f172a 45%, #111827 100%)",
    },
}

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "last_prompt" not in st.session_state:
    st.session_state.last_prompt = ""

if "ui_theme" not in st.session_state:
    st.session_state.ui_theme = "Light"


def get_theme() -> dict[str, str]:
    return THEMES.get(st.session_state.ui_theme, THEMES["Light"])


def apply_theme() -> None:
    theme = get_theme()
    st.markdown(
        f"""
        <style>
        .stApp {{
            background:
                radial-gradient(circle at top left, {theme['accent_soft']} 0%, transparent 32%),
                radial-gradient(circle at top right, {theme['accent_soft']} 0%, transparent 24%),
                {theme['gradient']};
            color: {theme['text']};
        }}

        html, body, [class*="css"] {{
            font-family: "Segoe UI", "Aptos", "Inter", sans-serif;
            color: {theme['text']};
        }}

        p, span, label, li, div, h1, h2, h3, h4, h5, h6 {{
            color: {theme['text']};
        }}

        .stMarkdown, .stMarkdown p, .stMarkdown span, .stText, .stCaption, .st-emotion-cache-10trblm {{
            color: {theme['text']} !important;
        }}

        [data-testid="stCaptionContainer"] p {{
            color: {theme['muted']} !important;
        }}

        [data-testid="stSidebar"] *, [data-testid="stRadio"] *, [data-testid="stSelectbox"] * {{
            color: {theme['text']} !important;
        }}

        .main .block-container {{
            max-width: 1180px;
            padding-top: 1.2rem;
            padding-bottom: 2.5rem;
        }}

        [data-testid="stSidebar"] {{
            background: {theme['surface']};
            border-right: 1px solid {theme['border']};
            backdrop-filter: blur(18px);
        }}

        [data-testid="stHeader"] {{
            background: transparent;
        }}

        .hero-shell {{
            background: {theme['surface']};
            border: 1px solid {theme['border']};
            box-shadow: {theme['shadow']};
            border-radius: 24px;
            padding: 1.4rem 1.5rem;
            margin-bottom: 1rem;
            backdrop-filter: blur(16px);
        }}

        .eyebrow {{
            display: inline-flex;
            gap: 0.45rem;
            align-items: center;
            padding: 0.35rem 0.7rem;
            border-radius: 999px;
            background: {theme['accent_soft']};
            color: {theme['accent']};
            font-size: 0.8rem;
            font-weight: 700;
            letter-spacing: 0.02em;
            text-transform: uppercase;
        }}

        .hero-title {{
            color: {theme['text']};
            font-size: 2.2rem;
            line-height: 1.05;
            margin: 0.6rem 0 0.35rem;
            font-weight: 800;
        }}

        .hero-subtitle {{
            color: {theme['muted']};
            font-size: 0.98rem;
            line-height: 1.5;
            margin: 0;
        }}

        .metric-card, .response-card, .section-card {{
            background: {theme['surface']};
            border: 1px solid {theme['border']};
            border-radius: 20px;
            padding: 1rem 1rem 0.9rem;
            box-shadow: {theme['shadow']};
            backdrop-filter: blur(16px);
        }}

        .metric-label {{
            color: {theme['muted']};
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 0.35rem;
        }}

        .metric-value {{
            color: {theme['text']};
            font-size: 1.5rem;
            font-weight: 800;
            margin-bottom: 0.15rem;
        }}

        .metric-meta {{
            color: {theme['muted']};
            font-size: 0.85rem;
        }}

        div[data-testid="stChatMessage"] {{
            border-radius: 20px;
        }}

        div[data-testid="stChatMessageContent"] {{
            background: {theme['surface']};
            border: 1px solid {theme['border']};
            box-shadow: {theme['shadow']};
            border-radius: 20px;
            padding: 1rem 1.05rem;
        }}

        .stButton button {{
            border-radius: 12px;
            border: 1px solid {theme['border']};
            background: {theme['surface_strong']};
            color: {theme['text']};
            font-weight: 700;
            padding: 0.55rem 0.9rem;
        }}

        .stButton button:hover {{
            border-color: {theme['accent']};
            color: {theme['accent']};
        }}

        .stChatInput textarea {{
            background: {theme['surface']};
            color: {theme['text']};
            border: 1px solid {theme['border']};
            border-radius: 18px;
            box-shadow: {theme['shadow']};
        }}

        .stMetric {{
            background: {theme['surface']};
            border: 1px solid {theme['border']};
            border-radius: 18px;
            padding: 0.75rem 0.9rem;
            box-shadow: {theme['shadow']};
        }}

        .stInfo, .stWarning, .stSuccess, .stError {{
            border-radius: 16px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


apply_theme()

st.sidebar.title("Display")
st.sidebar.radio(
    "Theme",
    options=list(THEMES.keys()),
    key="ui_theme",
    horizontal=True,
)
st.sidebar.caption("Switch the interface between light and dark presentation.")

st.markdown('<div class="hero-shell">', unsafe_allow_html=True)
st.markdown('<span class="eyebrow">Flight intelligence</span>', unsafe_allow_html=True)
st.markdown('<div class="hero-title">Flight and Temperature Chatbot</div>', unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)


def call_chat_api(base_url: str, user_prompt: str) -> dict[str, object]:
    endpoint = f"{base_url.rstrip('/')}/chat"
    response = requests.post(
        endpoint,
        json={"prompt": user_prompt},
        timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
    )
    response.raise_for_status()
    return response.json()


def render_tool_runs(tool_runs: list[dict[str, object]]) -> None:
    if not tool_runs:
        return

    with st.container(border=True):
        st.markdown("**MCP tool execution details**")
        for item in tool_runs:
            tool_name = item.get("tool_name", "unknown")
            duration = item.get("duration_ms", "-")
            status = item.get("status", "unknown")
            summary = item.get("summary") or ""
            st.write(f"- {tool_name} | {duration} ms | {status} {summary}")


def format_datetime(value: object) -> str:
    if not value:
        return "Unknown"

    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")

    return str(value)


def render_flight_summary(flight: dict[str, object]) -> None:
    status = flight.get("flight_status") or "unknown"
    flight_data = flight.get("flight") if isinstance(flight.get("flight"), dict) else {}
    flight_number = flight.get("flight_number") or flight_data.get("number") or flight_data.get("iata")
    airline = flight.get("airline") if isinstance(flight.get("airline"), dict) else {}
    departure = flight.get("departure") if isinstance(flight.get("departure"), dict) else {}
    arrival = flight.get("arrival") if isinstance(flight.get("arrival"), dict) else {}
    live = flight.get("live") if isinstance(flight.get("live"), dict) else {}

    with st.container(border=True):
        st.subheader("Flight status")
        st.markdown(f"**{flight_number or 'Flight'}** - {status.title()}")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.markdown('<div class="metric-label">Departure</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-value">{departure.get("airport") or departure.get("iata") or "Unknown"}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-meta">Scheduled: {format_datetime(departure.get("scheduled"))}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-meta">Terminal: {departure.get("terminal") or "Unknown"} | Gate: {departure.get("gate") or "Unknown"}</div>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.markdown('<div class="metric-label">Arrival</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-value">{arrival.get("airport") or arrival.get("iata") or "Unknown"}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-meta">Scheduled: {format_datetime(arrival.get("scheduled"))}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-meta">Terminal: {arrival.get("terminal") or "Unknown"} | Gate: {arrival.get("gate") or "Unknown"}</div>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        airline_name = airline.get("name") or airline.get("iata") or "Unknown"
        st.caption(f"Airline: {airline_name}")

        if live:
            live_bits = []
            if live.get("speed_horizontal") is not None:
                live_bits.append(f"Speed: {live.get('speed_horizontal')} km/h")
            if live.get("altitude") is not None:
                live_bits.append(f"Altitude: {live.get('altitude')}")
            if live.get("direction") is not None:
                live_bits.append(f"Heading: {live.get('direction')}")
            if live_bits:
                st.caption("Live data: " + " | ".join(live_bits))


def render_weather_summary(weather: dict[str, object]) -> None:
    with st.container(border=True):
        st.subheader("Weather")
        city = weather.get("city") or "Unknown city"
        country = weather.get("country")
        temperature = weather.get("temperature_celsius")
        condition = weather.get("condition") or "Unknown conditions"
        humidity = weather.get("humidity")
        wind_speed = weather.get("wind_speed_mps")

        st.markdown(f"**{city}**{f', {country}' if country else ''}")
        if temperature is not None:
            st.metric("Temperature", f"{temperature:.1f} °C")
        else:
            st.write("Temperature: unavailable")
        st.caption(f"Condition: {condition}")

        extra = []
        if humidity is not None:
            extra.append(f"Humidity: {humidity}%")
        if wind_speed is not None:
            extra.append(f"Wind: {wind_speed} m/s")
        if extra:
            st.caption(" | ".join(extra))


def render_route_summary(route_result: dict[str, object]) -> None:
    query = route_result.get("query") if isinstance(route_result.get("query"), dict) else {}
    origin = query.get("origin") or "Unknown origin"
    destination = query.get("destination") or "Unknown destination"
    flights = route_result.get("flights") or []
    warnings = route_result.get("warnings") or []

    with st.container(border=True):
        st.subheader("Route search")
        st.markdown(f"**{origin} → {destination}**")

        if warnings:
            for warning in warnings:
                st.info(str(warning))

        if not flights:
            st.warning("No flights were found for this route.")
            return

        for flight in flights[:5]:
            if not isinstance(flight, dict):
                continue
            dep_airport = flight.get("departure_airport") or flight.get("departure_iata") or "Unknown departure"
            arr_airport = flight.get("arrival_airport") or flight.get("arrival_iata") or "Unknown arrival"
            flight_code = flight.get("flight_iata") or "Unknown flight"
            airline_name = flight.get("airline_name") or "Unknown airline"
            status = flight.get("flight_status") or "unknown"

            with st.container(border=True):
                st.markdown(f"**{flight_code}** - {airline_name}")
                st.write(f"{dep_airport} → {arr_airport}")
                st.caption(f"Status: {status.title()} | Departure: {format_datetime(flight.get('departure_scheduled'))} | Arrival: {format_datetime(flight.get('arrival_scheduled'))}")


def render_chat_result(result: dict[str, object]) -> None:
    with st.container(border=True):
        st.write(result.get("answer", "No answer returned."))

        intent = result.get("intent", "unknown")
        tools_used = result.get("tools_used") or []
        if not tools_used and result.get("tool"):
            tools_used = [result.get("tool")]
        st.caption(f"Intent: {intent} | Tools used: {', '.join(tools_used) if tools_used else 'none'}")

        if result.get("requires_clarification"):
            st.warning(result.get("clarification_question") or "More details are required to continue.")

        flight = result.get("flight")
        if isinstance(flight, dict):
            render_flight_summary(flight)

        weather = result.get("weather")
        if isinstance(weather, dict):
            render_weather_summary(weather)

        route_results = result.get("route_results") or []
        for route_result in route_results:
            if isinstance(route_result, dict):
                render_route_summary(route_result)

        render_tool_runs(result.get("tool_runs") or [])

        with st.expander("Show raw response"):
            st.code(json.dumps(result, indent=2), language="json")


def submit_prompt(user_prompt: str) -> None:
    if not user_prompt.strip():
        st.warning("Please enter a prompt.")
        return

    try:
        with st.spinner("Analyzing prompt and running tools..."):
            result = call_chat_api(BACKEND_URL, user_prompt.strip())

        st.session_state.last_prompt = user_prompt.strip()
        st.session_state.chat_history.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "prompt": user_prompt.strip(),
                "result": result,
            }
        )
    except requests.HTTPError as exc:
        details = exc.response.text if exc.response is not None else str(exc)
        if exc.response is not None:
            try:
                payload = exc.response.json()
                if isinstance(payload, dict):
                    error_obj = payload.get("error")
                    if isinstance(error_obj, dict) and isinstance(error_obj.get("message"), str):
                        details = error_obj["message"]
            except ValueError:
                pass
        st.error(f"API request failed: {details}")
    except requests.Timeout:
        st.error(
            "Backend response timed out. Please try a simpler prompt or wait and retry. "
            "Long multi-intent prompts may take longer because they run LLM analysis and multiple tools."
        )
    except requests.RequestException as exc:
        st.error(f"Could not connect to backend: {exc}")


action_cols = st.columns([1, 3])
with action_cols[0]:
    if st.button("Clear History", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.last_prompt = ""
        st.rerun()

prompt = st.chat_input("Ask about flight status, weather, or both in one prompt")
if prompt:
    submit_prompt(prompt)


if st.session_state.chat_history:
    for item in st.session_state.chat_history:
        with st.chat_message("user"):
            st.write(item["prompt"])

        result = item["result"]
        with st.chat_message("assistant"):
            render_chat_result(result)

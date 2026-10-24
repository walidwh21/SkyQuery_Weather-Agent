"""Streamlit chat front-end.   Run:  streamlit run app.py"""

from __future__ import annotations

import streamlit as st

from weather_agent import ConfigError, Settings, build_agent

st.set_page_config(page_title="Weather Agent", page_icon="🌤️", layout="centered")

EXAMPLES = [
    "What's the weather in Paris right now?",
    "Forecast for Tokyo for the next 3 days",
    "Past 5 days in London",
    "Compare Madrid and Berlin for the next 4 days",
    "Weather in Cairo on 2026-12-25",
]


@st.cache_resource(show_spinner=False)
def get_agent():
    return build_agent(Settings.from_env())


# ---- sidebar ---------------------------------------------------------------
with st.sidebar:
    st.header("How it works")
    st.markdown(
        "1. An LLM turns your sentence into a structured plan\n"
        "2. The agent calls a weather API for each city\n"
        "3. Results are rendered as tables"
    )
    st.divider()
    st.caption("Quick examples")
    for i, text in enumerate(EXAMPLES):
        if st.button(text, key=f"ex{i}", use_container_width=True):
            st.session_state["pending"] = text
    st.divider()
    if st.button("Clear conversation", use_container_width=True):
        st.session_state["history"] = []
        st.rerun()

# ---- main ------------------------------------------------------------------
st.title("🌤️ Weather Agent")
st.caption("Ask in plain English — current conditions, forecasts, or past days, for one city or several.")

try:
    agent = get_agent()
except ConfigError as exc:
    st.error(str(exc))
    st.stop()

history: list[dict] = st.session_state.setdefault("history", [])

for turn in history:
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])

typed = st.chat_input("e.g. Will it rain in Lima this week?")
question = st.session_state.pop("pending", None) or typed

if question:
    history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Checking the skies…"):
            state = agent.ask(question)
        answer = state.get("answer", "Something went wrong.")
        (st.markdown if state.get("status") == "ok" else st.warning)(answer)
    history.append({"role": "assistant", "content": answer})

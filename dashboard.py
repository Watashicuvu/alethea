import streamlit as st
import json
import pandas as pd
from datetime import datetime

# streamlit run dashboard.py

st.set_page_config(layout="wide", page_title="RAG Pipeline Debugger")

LOG_FILE = "debug_stream.jsonl"

def load_logs():
    data = []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data.append(json.loads(line))
                except: pass
    except FileNotFoundError:
        return []
    return list(reversed(data)) # Новые сверху

# Auto-refresh
if st.button('Refresh Logs') or True: # Trick for basic reactivity
    logs = load_logs()

if not logs:
    st.warning("No logs found. Waiting for pipeline...")
    st.stop()

# --- SIDEBAR: Фильтры ---
st.sidebar.title("Filters")
types = list(set(l['type'] for l in logs))
selected_types = st.sidebar.multiselect("Event Type", types, default=types)

filtered_logs = [l for l in logs if l['type'] in selected_types]

# --- MAIN: Timeline ---
st.title("🧠 Pipeline Live Monitor")

for event in filtered_logs:
    ts = datetime.fromtimestamp(event['unixtime']).strftime('%H:%M:%S')
    
    with st.container():
        # Цветные заголовки в зависимости от типа
        icon = "🔹"
        color = "blue"
        if event['type'] == 'LLM_REQUEST': icon, color = "📤", "orange"
        if event['type'] == 'LLM_RESPONSE': icon, color = "📥", "green"
        if event['type'] == 'ERROR': icon, color = "❌", "red"
        if event['type'] == 'STATE_SNAPSHOT': icon, color = "💾", "violet"

        col1, col2 = st.columns([1, 6])
        with col1:
            st.caption(f"{ts}")
            st.markdown(f"**{event['type']}**")
        
        with col2:
            with st.expander(f"{icon} {event['title']}", expanded=(event['type'] == 'ERROR')):
                # Визуализация данных
                data = event['data']
                
                # Специальный рендер для LLM
                if 'prompt' in data:
                    st.subheader("Prompt")
                    st.text(data['prompt'])
                
                if 'output' in data:
                    st.subheader("Generated Output")
                    st.json(data['output'])
                    
                if 'tokens' in data:
                    st.caption(f"Tokens: {data['tokens']}")
                    
                # Рендер для состояния
                if event['type'] == 'STATE_SNAPSHOT':
                    st.json(data)
                    
        st.divider()

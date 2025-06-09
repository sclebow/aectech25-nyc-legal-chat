# streamlit_gui.py
# Streamlit GUI based on gradio_gui.py
# requirements: streamlit, requests

import streamlit as st
import requests
import subprocess
import os
import time
import threading
import datetime
import server.config as config
from logger_setup import setup_logger
import networkx as nx
import plotly.graph_objects as go
from streamlit_gui_flowchart import parse_log_flowchart, plot_flowchart

# === Constants and Config ===
FLASK_URL = "http://127.0.0.1:5000/llm_call"
default_rag_mode = "LLM only"
MODE_OPTIONS = ["local", "openai", "cloudflare"]
MODE_URL = "http://127.0.0.1:5000/set_mode"
sample_questions = [
    "What are some cost modeling best practices?",
    "What is the cost benchmark of six concrete column footings for a 10,000 sq ft commercial building?",
    "What is the typical cost per sqft for structural steel options?  Let's assume a four-story apartment building.  Make assumptions on the loading.",
    "How do steel frame structures compare to concrete frame structures, considering cost and durability?",
    "What are the ROI advantages of using precast concrete in construction projects?",
    "Can you provide a cost estimate for a 10,000 sq ft commercial building?",
    "What are the key factors affecting the cost of a residential building?",
    "How many windows are in the IFC model and what is the total cost of the windows?",
    "What is the cost benefit of triple glazing compared to double glazing?",
    "Using only the project data and the ifc, estimate the building's cost",
    "",
]
cloudflare_models = [
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
    "@cf/meta/llama-3.1-70b-instruct",
    "@cf/qwen/qwen2.5-coder-32b-instruct",
    "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b",
    "@cf/deepseek-ai/deepseek-math-7b-instruct",
]
cloudflare_embedding_models = [
    "@cf/baai/bge-base-en-v1.5",
    "@cf/baai/bge-large-en-v1.5",
    "@cf/baai/bge-small-en-v1.5",
    "@cf/baai/bge-m3",
]

logger = setup_logger(log_file="streamlit_app.log")

# === Global State ===
flask_process = None
flask_status_placeholder = None

# === Utility Functions (adapted from gradio_gui.py) ===
def query_llm(user_input, rag_mode, stream_mode, max_tokens=1500):
    url = FLASK_URL
    try:
        if stream_mode == "Streaming":
            response = requests.post(url, json={"input": user_input, "stream": True, "max_tokens": int(max_tokens)}, stream=True)
            if response.status_code == 200:
                streamed_text = ""
                data_context = ""
                logs = ""
                response_text = ""
                section = None
                chat_container = st.container()
                with chat_container:
                    with st.expander("Show Data Context", expanded=False):
                        placeholder_data_context = st.empty()
                    with st.expander("Show Logs", expanded=False):
                        placeholder_logs = st.empty()
                    # Match the column setup as in the main chat display
                    col_flowchart, col_response = st.columns([1, 3], vertical_alignment="bottom")
                    with col_flowchart:
                        flowchart_placeholder = st.empty()
                    with col_response:
                        placeholder_response = st.empty()
                for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                    if not chunk:
                        continue
                    streamed_text += chunk
                    # Parse tags for new log format
                    # Handle multiple tags in a single chunk
                    while chunk:
                        if "[DATA CONTEXT]:" in chunk:
                            before, tag, after = chunk.partition("[DATA CONTEXT]:")
                            if section == "data_context" and before.strip():
                                data_context += before
                                render_data_context_table(data_context, placeholder_data_context)
                            section = "data_context"
                            data_context = after.strip()
                            render_data_context_table(data_context, placeholder_data_context)
                            chunk = ""
                        elif "[RESPONSE]:" in chunk:
                            before, tag, after = chunk.partition("[RESPONSE]:")
                            if section == "response" and before.strip():
                                response_text += before
                                placeholder_response.markdown(response_text)
                            section = "response"
                            response_text += after
                            placeholder_response.markdown(response_text)
                            chunk = ""
                        elif "[LOG]:" in chunk:
                            before, tag, after = chunk.partition("[LOG]:")
                            if section == "logs" and before.strip():
                                logs += before
                                # Show logs as bullet points
                                log_lines_display = [f"- {line}" for line in logs.splitlines() if line.strip()]
                                placeholder_logs.markdown("\n".join(log_lines_display))
                            section = "logs"
                            # Support multiple log lines in a single chunk
                            log_lines = after.split("[LOG]:")
                            logs += log_lines[0].strip() + "\n"
                            # Show logs as bullet points
                            log_lines_display = [f"- {line}" for line in logs.splitlines() if line.strip()]
                            placeholder_logs.markdown("\n".join(log_lines_display))
                            # --- Progressive flowchart update ---
                            from streamlit_gui_flowchart import parse_log_flowchart, plot_flowchart
                            G = parse_log_flowchart(logs)
                            fig, flowchart_key = plot_flowchart(G)
                            if fig is not None and G is not None and len(G.nodes) > 0:
                                flowchart_placeholder.plotly_chart(fig, use_container_width=True, key=flowchart_key)
                            # If more [LOG]: tags, process them in next loop
                            chunk = "[LOG]:".join(log_lines[1:]) if len(log_lines) > 1 else ""
                        else:
                            # No tag found, append to current section
                            if section == "data_context":
                                data_context += chunk
                                render_data_context_table(data_context, placeholder_data_context)
                            elif section == "response":
                                response_text += chunk
                                placeholder_response.markdown(response_text)
                            elif section == "logs":
                                logs += chunk
                                # Show logs as bullet points
                                log_lines_display = [f"- {line}" for line in logs.splitlines() if line.strip()]
                                placeholder_logs.markdown("\n".join(log_lines_display))
                                # --- Progressive flowchart update for log tail ---
                                from streamlit_gui_flowchart import parse_log_flowchart, plot_flowchart
                                G = parse_log_flowchart(logs)
                                fig, flowchart_key = plot_flowchart(G)
                                if fig is not None and G is not None and len(G.nodes) > 0:
                                    flowchart_placeholder.plotly_chart(fig, use_container_width=True, key=flowchart_key)
                            chunk = ""
                    time.sleep(0.02)
                return {"data_context": data_context, "response": response_text, "logs": logs}
            else:
                return {"data_context": "", "response": f"Error: {response.status_code} - {response.text}", "logs": ""}
        else:
            response = requests.post(url, json={"input": user_input, "max_tokens": int(max_tokens)})
            if response.status_code == 200:
                data = response.json()
                data_context = data.get("data_context", "No data context returned.")
                response_text = data.get('response', 'No response from server.')
                logs = data.get('logs', '')
                result = {"data_context": data_context, "response": response_text, "logs": logs}
                return result
            else:
                return {"data_context": "", "response": f"Error: {response.status_code} - {response.text}", "logs": ""}
    except Exception as e:
        return {"data_context": "", "response": f"Exception: {str(e)}", "logs": ""}

def run_flask_server():
    global flask_process
    if flask_process is None or flask_process.poll() is not None:
        flask_process = subprocess.Popen(
            ["python", "-u", "gh_server.py"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stream_subprocess_output(flask_process) # Uncomment to stream output to console for debugging
        return "Flask server started."
    else:
        return "Flask server is already running."

def stream_subprocess_output(process):
    def stream(pipe):
        for line in iter(pipe.readline, b''):
            print("Flask Server:", line.decode(errors="replace").rstrip())
        pipe.close()
    threading.Thread(target=stream, args=(process.stdout,), daemon=True).start()
    threading.Thread(target=stream, args=(process.stderr,), daemon=True).start()

def stop_flask_server():
    global flask_process
    if flask_process is not None and flask_process.poll() is None:
        flask_process.terminate()
        flask_process = None
        return "Flask server stopped."
    else:
        return "Flask server is not running."

def set_mode_on_server(selected_mode):
    try:
        response = requests.post(MODE_URL, json={"mode": selected_mode})
        if response.status_code == 200:
            return f"Mode set to: {selected_mode}"
        else:
            return f"Error setting mode: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Exception: {str(e)}"

def poll_flask_status(max_retries=20, delay=0.5):
    url = "http://127.0.0.1:5000/status"
    for _ in range(max_retries):
        try:
            resp = requests.get(url, timeout=1)
            if resp.status_code == 200:
                return "Flask server is running."
        except Exception:
            pass
        time.sleep(delay)
    return "Flask server did not respond in time. Check logs."

def start_flask_and_wait():
    status = run_flask_server()
    if "started" in status:
        status = poll_flask_status()
    return status

def get_cloudflare_model_status():
    try:
        resp = requests.get("http://127.0.0.1:5000/status")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("mode") == "cloudflare":
                return f"Cloudflare Text Gen Model: {data.get('cf_gen_model', 'N/A')}\nCloudflare Embedding Model: {data.get('cf_emb_model', 'N/A')}"
            else:
                return "Cloudflare models not active (mode: %s)" % data.get("mode", "unknown")
        else:
            return f"Error: {resp.status_code}"
    except Exception as e:
        return f"Exception: {str(e)}"

def set_cloudflare_models(mode, gen_model, emb_model):
    try:
        requests.post(MODE_URL, json={
            "mode": mode,
            "cf_gen_model": gen_model,
            "cf_emb_model": emb_model
        })
    except Exception as e:
        logger.error(f"Failed to set Cloudflare models: {e}")

def render_data_context_table(data_context, placeholder=None):
    import pandas as pd
    import re
    headers = ["rsmeans", "ifc", "project data", "knowledge base", "value model", "cost model"]
    # Build a regex pattern to match all headers and their values
    pattern = r"'(" + "|".join(re.escape(h) for h in headers) + r")':(.*?)(?=(?:'(" + "|".join(re.escape(h) for h in headers) + r")':)|$)"
    matches = re.findall(pattern, data_context, re.DOTALL)
    data_dict = {header: value.strip() for header, value, _ in matches}
    df = pd.DataFrame(list(data_dict.items()), columns=["Context Key", "Value"])
    if placeholder:
        placeholder.dataframe(df, use_container_width=True)
    else:
        st.dataframe(df, use_container_width=True)

# --- Streamlit Chat Interface with Sample Questions ---
st.set_page_config(page_title="ROI LLM Assistant", layout="wide")
st.title("ROI LLM Assistant")
st.markdown("This is a Streamlit GUI for the ROI LLM Assistant.")

start_message = st.warning("Starting Flask server...")
if poll_flask_status() != "Flask server is running.":
    # Start the Flask server in a separate thread
    start_flask_and_wait()

# Wait for the Flask server to be ready
while poll_flask_status() != "Flask server is running.":
    time.sleep(0.5)

# Update the start message
start_message.empty()

with st.expander("LLM Configuration", expanded=False):
    st.markdown("## LLM Mode Selection")
    mode = st.segmented_control("Select LLM Mode", MODE_OPTIONS, default=MODE_OPTIONS[2], key="mode_radio", selection_mode="single")
    mode_status = set_mode_on_server(mode)
    st.text(mode_status)

    # Cloudflare model selectors
    if mode == "cloudflare":
        st.markdown("### Cloudflare Model Selection")
        cf_gen_model = st.selectbox("Cloudflare Text Generation Model", cloudflare_models, key="cf_gen_model")
        cf_emb_model = st.selectbox("Cloudflare Embedding Model", cloudflare_embedding_models, key="cf_emb_model")
        set_cloudflare_models(mode, cf_gen_model, cf_emb_model)
        cf_model_status = get_cloudflare_model_status()
        st.text_area("Current Cloudflare Models (Backend Verified)", cf_model_status, height=68)

    st.markdown("## LLM Call Type")
    stream_mode = st.segmented_control("Response Mode", ["Standard", "Streaming"], default="Streaming", key="stream_radio", selection_mode="single")
    max_tokens = st.number_input("Max Tokens", min_value=100, max_value=4096, value=1500, step=1, key="max_tokens_input")

# --- Streamlit Chat Interface with Sample Questions ---
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "sample_input" not in st.session_state:
    st.session_state["sample_input"] = ""

chat_message_container = st.container(border=True, height=400)
with chat_message_container:
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            if isinstance(msg["content"], dict):
                # Show data context in expander above the response
                with st.expander("Show Data Context", expanded=False):
                    data_context = msg["content"].get("data_context", "No data context returned.")
                    render_data_context_table(data_context)
                # Show logs in expander below the response
                with st.expander("Show Logs", expanded=False):
                    logs = msg["content"].get("logs", "No logs available.")
                    if logs and logs.strip():
                        for log_line in logs.splitlines():
                            if "[id=" in log_line:
                                st.markdown(f"- {log_line}")
                    else:
                        st.markdown("No logs available.")
                # --- Flowchart visualization ---
                logs = msg["content"].get("logs", "")
                G = None
                fig = None
                if logs and logs.strip():
                    G = parse_log_flowchart(logs)
                    fig, flowchart_key = plot_flowchart(G)
                col_flowchart, col_response = st.columns([1, 3], vertical_alignment="bottom")
                with col_flowchart:
                    if fig is not None and G is not None and len(G.nodes) > 0:
                        st.plotly_chart(fig, use_container_width=True, key=flowchart_key)
                    else:
                        st.info("No flowchart data available for these logs.")
                with col_response:
                    st.markdown(msg["content"].get("response", ""))
            else:
                st.markdown(msg["content"])
with st.container():
    user_input = st.chat_input("Type your question or select a sample below...", key="chat_input")

col1, col2 = st.columns([3, 1], vertical_alignment="bottom")
with col1:
    sample = st.selectbox("Or select a sample question", sample_questions, key="sample_dropdown")
with col2:
    send_sample = st.button("Send Sample Question")

# Handle sending a sample question
if send_sample and sample:
    st.session_state["messages"].append({"role": "user", "content": sample})
    with chat_message_container:
        with st.chat_message("user"):
            st.markdown(sample)
        with st.chat_message("assistant"):
            st.markdown("_Processing..._")
            output = query_llm(sample, default_rag_mode, stream_mode, max_tokens)
    st.session_state["messages"].append({"role": "assistant", "content": output})

# Handle freeform chat input
if user_input:
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with chat_message_container:
        with st.chat_message("user"):
            st.markdown(user_input)
        with st.chat_message("assistant"):
            st.markdown("_Processing..._")
            output = query_llm(user_input, default_rag_mode, stream_mode, max_tokens)
    st.session_state["messages"].append({"role": "assistant", "content": output})
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
import pandas as pd
import re
import ifcopenshell
import tempfile
import pyvista as pv
import streamlit.components.v1 as components

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
    "@cf/meta/llama-3.1-70b-instruct",
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
    "@cf/qwen/qwen2.5-coder-32b-instruct",
    "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b",
    "@cf/deepseek-ai/deepseek-math-7b-instruct",
    "@cf/qwen/qwq-32b",
    "@cf/microsoft/phi-2",
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
vite_process = None  # Track Vite server process
flask_status_placeholder = None

# === Utility Functions (adapted from gradio_gui.py) ===
def _llm_post_request(url, payload, stream=False):
    """Send a POST request to the LLM server."""
    try:
        if stream:
            return requests.post(url, json=payload, stream=True)
        else:
            return requests.post(url, json=payload)
    except Exception as e:
        return e


def _handle_streaming_response(response, st, render_data_context_table, render_token_usage_report):
    """Handle streaming LLM response and update UI accordingly."""
    import time as _time
    start_time = _time.time()
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
        col_flowchart, col_response = st.columns([1, 3], vertical_alignment="bottom")
        with col_flowchart:
            flowchart_placeholder = st.empty()
        with col_response:
            placeholder_response = st.empty()
            # Add a placeholder for token usage report
            placeholder_token_usage = st.empty()
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
                    # st.markdown("##### Backend Flowchart")
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
                    # --- Token Usage Report (streaming) ---
                    # Only show after all logs are received (i.e., after the streaming loop)
    # After streaming loop ends, show the final token usage report
    with col_response:
        elapsed_time = _time.time() - start_time
        render_token_usage_report(logs, elapsed_time=elapsed_time)
    return {"data_context": data_context, "response": response_text, "logs": logs, "elapsed_time": elapsed_time}


def _handle_standard_response(response):
    """Handle standard (non-streaming) LLM response."""
    if isinstance(response, Exception):
        return {"data_context": "", "response": f"Exception: {str(response)}", "logs": ""}
    if response.status_code == 200:
        data = response.json()
        data_context = data.get("data_context", "No data context returned.")
        response_text = data.get('response', 'No response from server.')
        logs = data.get('logs', '')
        return {"data_context": data_context, "response": response_text, "logs": logs}
    else:
        return {"data_context": "", "response": f"Error: {response.status_code} - {response.text}", "logs": ""}


def query_llm(user_input, rag_mode, stream_mode, max_tokens=1500):
    """Query the LLM server and handle the response, streaming or standard."""
    url = FLASK_URL
    payload = {"input": user_input, "max_tokens": int(max_tokens)}
    if stream_mode == "Streaming":
        payload["stream"] = True
        response = _llm_post_request(url, payload, stream=True)
        if isinstance(response, Exception):
            return {"data_context": "", "response": f"Exception: {str(response)}", "logs": ""}
        if response.status_code == 200:
            return _handle_streaming_response(response, st, render_data_context_table, render_token_usage_report)
        else:
            return {"data_context": "", "response": f"Error: {response.status_code} - {response.text}", "logs": ""}
    else:
        response = _llm_post_request(url, payload)
        return _handle_standard_response(response)

def run_flask_server():
    global flask_process, vite_process
    # Start Flask server
    if flask_process is None or flask_process.poll() is not None:
        flask_process = subprocess.Popen(
            ["python", "-u", "gh_server.py"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stream_subprocess_output(flask_process)
    # Start Vite server (if not already running)
    vite_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ifc_viewer_vite")
    if vite_process is None or vite_process.poll() is not None:
        if not os.path.isdir(vite_dir):
            st.error(f"Vite directory not found: {vite_dir}. Please ensure 'ifc_viewer_vite' exists.")
            return "Vite directory missing."
        try:
            vite_process = subprocess.Popen(
                "npm run dev -- --host",
                cwd=vite_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True  # Use shell=True for Windows compatibility
            )
            stream_subprocess_output(vite_process)
        except FileNotFoundError as e:
            st.error(f"Failed to start Vite server: {e}\nIs npm installed and on your PATH?")
            return f"Failed to start Vite: {e}"
        except Exception as e:
            st.error(f"Unexpected error starting Vite: {e}")
            return f"Failed to start Vite: {e}"
    return "Flask and Vite servers started."

def stream_subprocess_output(process):
    def stream(pipe):
        for line in iter(pipe.readline, b''):
            print("Flask Server:", line.decode(errors="replace").rstrip())
        pipe.close()
    threading.Thread(target=stream, args=(process.stdout,), daemon=True).start()
    threading.Thread(target=stream, args=(process.stderr,), daemon=True).start()

def stop_flask_server():
    global flask_process, vite_process
    if flask_process is not None and flask_process.poll() is None:
        flask_process.terminate()
        flask_process = None
    if vite_process is not None and vite_process.poll() is None:
        vite_process.terminate()
        vite_process = None
    return "Flask and Vite servers stopped."

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

def render_token_usage_report(logs, elapsed_time=None):
    """Extracts and displays the total LLM token usage from logs, and optionally the elapsed time."""
    import re
    report_lines = []
    if logs and logs.strip():
        token_usages = re.findall(r"\[usage=CompletionUsage\(.*?total_tokens=(\d+)", logs)
        total_tokens = sum(int(t) for t in token_usages)
        report_lines.append(f"**Total LLM tokens used in this response:** {total_tokens}")
    if elapsed_time is not None:
        report_lines.append(f"**Elapsed time:** {elapsed_time:.2f} seconds")
    if report_lines:
        st.info("\n".join(report_lines))

def handle_chat_interaction(message, chat_message_container, default_rag_mode, stream_mode, max_tokens):
    """Handles sending a chat message (user or sample), querying the LLM, and displaying the result."""
    st.session_state["messages"].append({"role": "user", "content": message})
    with chat_message_container:
        with st.chat_message("user"):
            st.markdown(message)
        with st.chat_message("assistant") as assistant_placeholder:
            msg_placeholder = st.empty()
            msg_placeholder.markdown("_Processing..._")
            output = query_llm(message, default_rag_mode, stream_mode, max_tokens)
            msg_placeholder.empty()
            elapsed_time = None
            if isinstance(output, dict):
                # Try to get elapsed_time from output (added in _handle_streaming_response)
                elapsed_time = output.get("elapsed_time")
                st.session_state["messages"].append({"role": "assistant", "content": output, "elapsed_time": elapsed_time})
                if "response" in output and (output["response"].startswith("Error") or output["response"].startswith("Exception")):
                    st.error(output["response"])
            elif isinstance(output, str) and (output.startswith("Error") or output.startswith("Exception")):
                st.session_state["messages"].append({"role": "assistant", "content": output, "elapsed_time": elapsed_time})
                st.error(output)

def ifc_file_upload(uploaded_ifc):
    """Handles uploading an IFC file to the backend server."""
    if uploaded_ifc is not None:
        with st.spinner("Uploading IFC file..."):
            files = {"file": (uploaded_ifc.name, uploaded_ifc, "application/octet-stream")}
            try:
                response = requests.post("http://127.0.0.1:5000/upload_ifc", files=files)
                if response.status_code == 200:
                    st.success(f"File '{uploaded_ifc.name}' uploaded successfully.")
                else:
                    st.error(f"Upload failed: {response.json().get('message', response.text)}")
            except Exception as e:
                st.error(f"Exception during upload: {e}")

def ifc_file_download():
    """Handles downloading the latest IFC file from the backend server."""
    with st.spinner("Fetching latest IFC file..."):
        try:
            response = requests.get("http://127.0.0.1:5000/download_latest_ifc", stream=True)
            if response.status_code == 200:
                content_disp = response.headers.get('content-disposition', '')
                filename = "latest.ifc"
                if 'filename=' in content_disp:
                    filename = content_disp.split('filename=')[1].strip('"')
                file_bytes = response.content
                st.download_button(
                    label=f"Click to download {filename}",
                    data=file_bytes,
                    file_name=filename,
                    mime="application/octet-stream"
                )
            else:
                st.error(f"Download failed: {response.json().get('message', response.text)}")
        except Exception as e:
            st.error(f"Exception during download: {e}")

def visualize_ifc_3d(uploaded_ifc):
    """Visualize IFC geometry in 3D using ifcopenshell and plotly (interactive)."""
    if uploaded_ifc is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ifc") as tmp:
            tmp.write(uploaded_ifc.getbuffer())
            tmp_path = tmp.name
        try:
            import ifcopenshell.geom
            import numpy as np
            import plotly.graph_objects as go
            settings = ifcopenshell.geom.settings()
            settings.set(settings.USE_WORLD_COORDS, True)
            ifc = ifcopenshell.open(tmp_path)
            all_verts = []
            all_faces = []
            vert_offset = 0
            for product in ifc.by_type("IfcProduct"):
                try:
                    shape = ifcopenshell.geom.create_shape(settings, product)
                    verts = np.array(shape.geometry.verts).reshape(-1, 3)
                    faces = np.array(shape.geometry.faces, dtype=np.int32)
                    # faces: [3, v0, v1, v2, 3, v0, v1, v2, ...]
                    i = 0
                    while i < len(faces):
                        n = faces[i]
                        if n == 3:
                            all_faces.append([
                                faces[i+1] + vert_offset,
                                faces[i+2] + vert_offset,
                                faces[i+3] + vert_offset
                            ])
                        # skip non-triangles
                        i += n + 1
                    all_verts.extend(verts)
                    vert_offset += len(verts)
                except Exception:
                    continue
            if not all_verts or not all_faces:
                st.info("No geometry found in IFC file for 3D visualization.")
                return
            all_verts = np.array(all_verts)
            x, y, z = all_verts[:,0], all_verts[:,1], all_verts[:,2]
            i, j, k = zip(*all_faces)
            fig = go.Figure(data=[go.Mesh3d(x=x, y=y, z=z, i=i, j=j, k=k, color='lightgrey', opacity=1.0)])
            fig.update_layout(
                scene=dict(aspectmode='data'),
                margin=dict(l=0, r=0, b=0, t=0),
                title="IFC 3D Interactive View"
            )
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Failed to render 3D IFC: {e}")

def visualize_ifc_summary(uploaded_ifc):
    """Parse IFC and show a summary table of element types and counts."""
    if uploaded_ifc is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ifc") as tmp:
            tmp.write(uploaded_ifc.getbuffer())
            tmp_path = tmp.name
        try:
            ifc = ifcopenshell.open(tmp_path)
            products = ifc.by_type("IfcProduct")
            type_counts = {}
            for el in products:
                t = el.is_a()
                type_counts[t] = type_counts.get(t, 0) + 1
            import pandas as pd
            df = pd.DataFrame(list(type_counts.items()), columns=["IFC Type", "Count"])
            st.markdown("#### IFC File Summary")
            st.dataframe(df, use_container_width=True)
            # Removed 3D visualization (plotly)
        except Exception as e:
            st.error(f"Failed to parse IFC: {e}")

def show_ifcjs_viewer_vite(height=600):
    """Embed the local Vite IFC viewer in Streamlit via iframe, passing the latest IFC file URL."""
    vite_url = "http://localhost:5173/?ifcUrl=http://127.0.0.1:5000/download_latest_ifc"
    components.html(f"""
        <iframe src='{vite_url}' width='100%' height='{height}' style='border:none;'></iframe>
    """, height=height)

# --- Streamlit Chat Interface with Sample Questions ---
st.set_page_config(page_title="ROI LLM Assistant", layout="wide")
st.title("ROI LLM Assistant")
# st.markdown("This is a Streamlit GUI for the ROI LLM Assistant.")

start_message = st.warning("Starting Flask server...")
if poll_flask_status() != "Flask server is running.":
    # Start the Flask server in a separate thread
    start_flask_and_wait()

# Wait for the Flask server to be ready
while poll_flask_status() != "Flask server is running.":
    time.sleep(0.5)

# Update the start message
start_message.empty()

llm_col, ifc_col = st.columns([1, 1], vertical_alignment="top")

with llm_col:
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

with ifc_col:
    # --- IFC File Upload Section ---
    with st.expander("IFC File Management", expanded=False):
        st.markdown("## Upload Your IFC File")
        with st.form("ifc_upload_form", clear_on_submit=True):
            uploaded_ifc = st.file_uploader("Choose an IFC file to upload", type=["ifc"], key="ifc_file_uploader")
            upload_button = st.form_submit_button("Upload IFC File")
            if upload_button:
                ifc_file_upload(uploaded_ifc)
        # Always refresh summary and BIM viewer if a file is loaded
        if uploaded_ifc is not None:
            visualize_ifc_summary(uploaded_ifc)
            st.markdown("#### Full BIM Viewer (Vite)")
            show_ifcjs_viewer_vite()

        st.markdown("## Download Latest IFC File")
        download_latest = st.button("Download Latest IFC File")
        if download_latest:
            ifc_file_download()

# --- Streamlit Chat Interface with Sample Questions ---
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "sample_input" not in st.session_state:
    st.session_state["sample_input"] = ""

chat_message_container = st.container(border=True, height=550)
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
                        st.markdown("##### Backend Flowchart")
                        st.plotly_chart(fig, use_container_width=True, key=flowchart_key)
                    else:
                        st.info("No flowchart data available for these logs.")
                with col_response:
                    st.markdown(msg["content"].get("response", ""))
                    # --- Token Usage Report ---
                    logs = msg["content"].get("logs", "")
                    elapsed_time = msg.get("elapsed_time")
                    render_token_usage_report(logs, elapsed_time=elapsed_time)
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
    handle_chat_interaction(sample, chat_message_container, default_rag_mode, stream_mode, max_tokens)

# Handle freeform chat input
if user_input:
    handle_chat_interaction(user_input, chat_message_container, default_rag_mode, stream_mode, max_tokens)


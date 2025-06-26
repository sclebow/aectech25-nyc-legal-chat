# streamlit_gui.py
# Streamlit GUI based on gradio_gui.py
# requirements: streamlit, requests

import streamlit as st
import requests
import subprocess
import os
import time
import threading
from logger_setup import setup_logger
# import plotly.graph_objects as go
from streamlit_gui_flowchart import parse_log_flowchart, plot_flowchart
import pandas as pd
import re
import ifcopenshell
import tempfile
import pyvista as pv
import streamlit.components.v1 as components
import socket
import numpy as np
import plotly.graph_objects as go

def find_open_port(preferred_port, max_tries=20):
    """Find an open port, starting from preferred_port, up to max_tries."""
    port = preferred_port
    for _ in range(max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                port += 1
    raise RuntimeError(f"No open port found in range {preferred_port}-{port}")

# === Constants and Config ===
default_flask_port = 5000
default_vite_port = 5173

default_rag_mode = "LLM only"
MODE_OPTIONS = ["local", "cloudflare"]
sample_questions = [
    "What is the cost of the columns in the IFC model?",
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
    "What is the predicted value of a 2 bedroom apartment on the 3rd floor of 800 square feet in Boston MA?"
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
cloudflare_sml_models = [
    "@cf/meta/llama-4-scout-17b-16e-instruct",
    "@cf/meta/llama-3.1-8b-instruct-fast",
    "@cf/microsoft/phi-2"
]
cloudflare_embedding_models = [
    "@cf/baai/bge-base-en-v1.5",
    "@cf/baai/bge-large-en-v1.5",
    "@cf/baai/bge-small-en-v1.5",
    "@cf/baai/bge-m3",
]

# Define color palette
COLORS = ['#e18989', '#d2e189', '#89e1b4', '#89b4e1', '#d289e1', '#ffa600', '#ff69b4']

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
    start_time = time.time()
    streamed_text = ""
    data_context = ""
    logs = ""
    response_text = ""
    ifc_viewer_params = ""
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
                idx = chunk.index("[DATA CONTEXT]:")
                rest = chunk[idx + len("[DATA CONTEXT]:"):]

                data_context = rest.strip()
                placeholder_data_context.markdown(data_context)
                chunk = ""
            elif "[RESPONSE]:" in chunk:
                idx = chunk.index("[RESPONSE]:")
                rest = chunk[idx + len("[RESPONSE]:"):]

                response_text += rest
                placeholder_response.markdown(response_text)
                chunk = ""
            elif "[IFC_VIEWER_PARAMS]:" in chunk:
                idx = chunk.index("[IFC_VIEWER_PARAMS]:")
                rest = chunk[idx + len("[IFC_VIEWER_PARAMS]:"):].strip()
                ifc_viewer_params = rest
                # Save chat history and viewer params before rerun
                st.session_state["vite_url"] = f"http://localhost:{VITE_PORT}/?ifcUrl=http://127.0.0.1:{FLASK_PORT}/download_latest_ifc" + (ifc_viewer_params if ifc_viewer_params else "")
                print(f"Vite URL updated: {st.session_state['vite_url']}")
                # Save chat messages if not already
                if "messages" not in st.session_state:
                    st.session_state["messages"] = []
                # Save the current assistant message (if not already appended)
                elapsed_time = time.time() - start_time
                if (not st.session_state["messages"] or
                    not (isinstance(st.session_state["messages"][-1]["content"], dict) and st.session_state["messages"][-1]["content"].get("response", "") == response_text)):
                    st.session_state["messages"].append({
                        "role": "assistant",
                        "content": {
                            "data_context": data_context,
                            "response": response_text,
                            "logs": logs,
                            "elapsed_time": elapsed_time,
                            "ifc_viewer_params": ifc_viewer_params
                        },
                        "elapsed_time": elapsed_time
                    })
                st.rerun()
                chunk = ""
            elif "[LOG]:" in chunk:
                idx = chunk.index("[LOG]:")
                rest = chunk[idx + len("[LOG]:"):]

                logs += rest + "\n"
                placeholder_logs.markdown(logs)
                chunk = ""
            else:
                break
    # After streaming loop ends, show the final token usage report
    with col_response:
        elapsed_time = time.time() - start_time
        render_token_usage_report(logs, elapsed_time=elapsed_time)
    return {"data_context": data_context, "response": response_text, "logs": logs, "elapsed_time": elapsed_time, "ifc_viewer_params": ifc_viewer_params}


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
    url = f"http://127.0.0.1:{FLASK_PORT}/llm_call"
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
            ["python", "-u", "gh_server.py", str(FLASK_PORT)],
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
        response = requests.post(f"http://127.0.0.1:{FLASK_PORT}/set_mode", json={"mode": selected_mode})
        if response.status_code == 200:
            return f"Mode set to: {selected_mode}"
        else:
            return f"Error setting mode: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Exception: {str(e)}"

def poll_flask_status(max_retries=20, delay=0.5):
    url = f"http://127.0.0.1:{FLASK_PORT}/status"
    print(f"Polling Flask status at {url}...")
    for _ in range(max_retries):
        try:
            resp = requests.get(url, timeout=1)
            print(f"Flask status response: {resp.status_code}")
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
        resp = requests.get(f"http://127.0.0.1:{FLASK_PORT}/status")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("mode") == "cloudflare":
                return f"Cloudflare Text Gen Model: {data.get('cf_gen_model', 'N/A')}\n Cloudflare small model: {data.get('cf_sml_model', 'N/A')}\nCloudflare Embedding Model: {data.get('cf_emb_model', 'N/A')}"
            else:
                return "Cloudflare models not active (mode: %s)" % data.get("mode", "unknown")
        else:
            return f"Error: {resp.status_code}"
    except Exception as e:
        return f"Exception: {str(e)}"

def set_cloudflare_models(mode, gen_model, sml_model, emb_model):
    try:
        requests.post(f"http://127.0.0.1:{FLASK_PORT}/set_mode", json={
            "mode": mode,
            "cf_gen_model": gen_model,
            "cf_sml_model": sml_model,
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
                response = requests.post(f"http://127.0.0.1:{FLASK_PORT}/upload_ifc", files=files)
                if response.status_code == 200:
                    st.success(f"File '{uploaded_ifc.name}' uploaded successfully.")
                else:
                    st.error(f"Upload failed: {response.json().get('message', response.text)}")
            except Exception as e:
                st.error(f"Exception during upload: {e}")

def get_latest_ifc_filename():
    """Fetch the filename of the latest IFC file from the backend server."""
    try:
        resp = requests.get(f"http://127.0.0.1:{FLASK_PORT}/latest_ifc_filename")
        if resp.status_code == 200:
            data = resp.json()
            return data.get("filename", None)
        else:
            return None
    except Exception:
        return None

def ifc_file_download():
    """Handles downloading the latest IFC file from the backend server."""
    with st.spinner("Fetching latest IFC file..."):
        try:
            filename = get_latest_ifc_filename() or "latest.ifc"
            response = requests.get(f"http://127.0.0.1:{FLASK_PORT}/download_latest_ifc", stream=True)
            if response.status_code == 200:
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

@st.cache_data
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

@st.cache_data
def visualize_ifc_summary(uploaded_ifc):
    """Parse IFC and show a summary table of element types and counts."""
    if uploaded_ifc is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ifc") as tmp:
            # Handle both bytes and UploadedFile
            if hasattr(uploaded_ifc, 'getbuffer'):
                tmp.write(uploaded_ifc.getbuffer())
            else:
                tmp.write(uploaded_ifc)  # Assume bytes
            tmp_path = tmp.name
        try:
            ifc = ifcopenshell.open(tmp_path)
            products = ifc.by_type("IfcProduct")
            type_counts = {}
            for el in products:
                t = el.is_a()
                type_counts[t] = type_counts.get(t, 0) + 1
            import pandas as pd
            # st.write(f"Filename: {get_latest_ifc_filename()}")
            df = pd.DataFrame(list(type_counts.items()), columns=["IFC Type", "Count"])
            st.dataframe(df, use_container_width=True)
            # Removed 3D visualization (plotly)
        except Exception as e:
            st.error(f"Failed to parse IFC: {e}")

def show_ifcjs_viewer_vite(height=600):
    """Embed the local Vite IFC viewer in Streamlit via iframe, passing the latest IFC file URL and any params."""
    st.write(f"**Model Viewer**: {get_latest_ifc_filename()}")
    vite_url = st.session_state.get("vite_url")
    if not vite_url:
        vite_url = f"http://localhost:{VITE_PORT}/?ifcUrl=http://127.0.0.1:{FLASK_PORT}/download_latest_ifc"
    print(f"Vite URL: {vite_url}")
    components.html(f"""
        <iframe src='{vite_url}' width='100%' height='{height}' style='border:none;'></iframe>
    """, height=height)

# Helper functions for dashboard components
def get_mock_building_metrics():
    """Get mock building metrics data"""
    return {
        "estimated_cost": 4200000,
        "projected_value": 6100000,
        "roi": 312,
        "floor_area_ratio": 3.8,
        "units": {"total": 48, "2br": 32, "1br": 16},
        "circulation_ratio": 18.2
    }

def get_mock_cost_components():
    """Get mock cost components data"""
    return {
        "Structure": 1200000,
        "Facade": 850000,
        "MEP": 750000,
        "Interior": 600000,
        "Site Work": 400000,
        "Other": 400000
    }

def create_pie_chart(data, title):
    """Create a pie chart with custom colors"""
    fig = go.Figure(data=[go.Pie(
        labels=list(data.keys()),
        values=list(data.values()),
        marker_colors=COLORS[:len(data)],
        textinfo='label+percent',
        textposition='inside'
    )])
    fig.update_layout(
        title=title,
        showlegend=True,
        height=400,
        font=dict(size=12)
    )
    return fig

def create_bar_chart(data, title, x_label, y_label):
    """Create a bar chart with custom colors"""
    fig = go.Figure(data=[go.Bar(
        x=list(data.keys()),
        y=list(data.values()),
        marker_color=COLORS[0]
    )])
    fig.update_layout(
        title=title,
        xaxis_title=x_label,
        yaxis_title=y_label,
        height=400
    )
    return fig

def create_roi_sensitivity_curve():
    """Create ROI sensitivity curve"""
    # Mock data for sensitivity analysis
    cost_variations = np.linspace(-20, 30, 50)
    roi_values = []
    base_cost = 4200000
    base_value = 6100000
    
    for variation in cost_variations:
        adjusted_cost = base_cost * (1 + variation/100)
        roi = ((base_value - adjusted_cost) / adjusted_cost) * 100
        roi_values.append(roi)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=cost_variations,
        y=roi_values,
        mode='lines',
        line=dict(color=COLORS[3], width=3),
        name='ROI Sensitivity'
    ))
    fig.update_layout(
        title='ROI Sensitivity Analysis',
        xaxis_title='Cost Variation (%)',
        yaxis_title='ROI (%)',
        height=400,
        showlegend=False
    )
    return fig

# --- Streamlit Chat Interface with Sample Questions ---
st.set_page_config(page_title="ROI LLM Assistant", layout="wide")
st.markdown('<div style="display:flex;align-items:center;gap:1em;"><h3 style="margin:0;">Yield Copilot</h3><span>Home • Cost • Value • Returns</span></div>', unsafe_allow_html=True)

# Add css to make st.expander text smaller
st.markdown("""
    <style>
        .streamlit-expanderHeader {
            font-size: 0.2em;
        }
    </style>
""", unsafe_allow_html=True)

start_message = st.warning("Starting Flask server...")
if "FLASK_PORT" not in st.session_state:
    st.session_state["FLASK_PORT"] = default_flask_port
if "VITE_PORT" not in st.session_state:
    st.session_state["VITE_PORT"] = default_vite_port

FLASK_PORT = st.session_state["FLASK_PORT"]
VITE_PORT = st.session_state["VITE_PORT"]

if poll_flask_status() != "Flask server is running.":
    # Start the Flask server in a separate thread
    print("Starting Flask server...")
    # Try to find open ports if the defaults are not available
    try:
        FLASK_PORT = find_open_port(default_flask_port)
    except RuntimeError:
        FLASK_PORT = default_flask_port
    try:
        VITE_PORT = find_open_port(default_vite_port)
    except RuntimeError:
        VITE_PORT = default_vite_port

    print(f"Using Flask port: {FLASK_PORT}")
    print(f"Using Vite port: {VITE_PORT}")

    st.session_state["FLASK_PORT"] = FLASK_PORT
    st.session_state["VITE_PORT"] = VITE_PORT

    start_flask_and_wait()

# Wait for the Flask server to be ready
while poll_flask_status() != "Flask server is running.":
    print("Waiting for Flask server to be ready...")
    time.sleep(0.5)

# Update the start message
start_message.empty()

# In the main UI, before rendering chat history:
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "vite_url" not in st.session_state:
    st.session_state["vite_url"] = f"http://localhost:{VITE_PORT}/?ifcUrl=http://127.0.0.1:{FLASK_PORT}/download_latest_ifc"

with st.expander("LLM Configuration", expanded=False):
    st.markdown("## LLM Mode Selection")
    mode = st.segmented_control("Select LLM Mode", MODE_OPTIONS, default=MODE_OPTIONS[1], key="mode_radio", selection_mode="single")
    mode_status = set_mode_on_server(mode)
    st.text(mode_status)

    # Cloudflare model selectors
    if mode == "cloudflare":
        st.markdown("### Cloudflare Model Selection")
        cf_gen_model = st.selectbox("Cloudflare Text Generation Model", cloudflare_models, key="cf_gen_model")
        cf_sml_model = st.selectbox("Cloudflare Small Task Model", cloudflare_sml_models, key="cf_sml_model")
        cf_emb_model = st.selectbox("Cloudflare Embedding Model", cloudflare_embedding_models, key="cf_emb_model")
        set_cloudflare_models(mode, cf_gen_model, cf_sml_model, cf_emb_model)
        cf_model_status = get_cloudflare_model_status()
        st.text_area("Current Cloudflare Models (Backend Verified)", cf_model_status, height=68)

    st.markdown("## LLM Call Type")
    stream_mode = st.segmented_control("Response Mode", ["Standard", "Streaming"], default="Streaming", key="stream_radio", selection_mode="single")
    max_tokens = st.number_input("Max Tokens", min_value=100, max_value=4096, value=1500, step=1, key="max_tokens_input")

core_window_height = 650

# Create two Tabs:
viewer_chat_tab, metrics_tab = st.tabs(["Viewer and Chat", "Explanation and Metrics (Aspirational)"])
with viewer_chat_tab:
    ifc_col, chat_col = st.columns([2, 4], vertical_alignment="top")
    with ifc_col:
        with st.container(height=core_window_height):
            # --- IFC File Upload Section ---
            show_ifcjs_viewer_vite(height=core_window_height - 200)

            with st.form("ifc_upload_form", clear_on_submit=True):
                uploaded_ifc = st.file_uploader("Choose an IFC file to upload", type=["ifc"], key="ifc_file_uploader")
                upload_button = st.form_submit_button("Upload IFC File")
                if upload_button:
                    ifc_file_upload(uploaded_ifc)
            download_latest = st.button("Download Latest IFC File")
            if download_latest:
                ifc_file_download()
            
            # summary_col, viewer_col = st.columns([1, 3], vertical_alignment="top")
            # Always refresh summary and BIM viewer if a file is loaded
            # if uploaded_ifc is not None:
            filename = get_latest_ifc_filename()
            if filename:
                current_ifc_url = f"http://127.0.0.1:{FLASK_PORT}/download_ifc/{filename}"
                current_ifc = requests.get(current_ifc_url).content
                st.caption(f"Showing summary for: {filename}")
                visualize_ifc_summary(current_ifc)
            else:
                st.info("No IFC file found.")

    # --- Streamlit Chat Interface with Sample Questions ---
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "sample_input" not in st.session_state:
        st.session_state["sample_input"] = ""

    with chat_col:
        with st.container(height=core_window_height):
            st.markdown("*Ask any question related to the project, including 'what if' scenarios or test my skills with some of the pre-defined areas of expertise below*")
            chat_message_container = st.container(border=True, height=450)
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

with metrics_tab:
    # Mock key metrics display
    metrics = get_mock_building_metrics()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Estimated Cost", f"${metrics['estimated_cost']:,.0f}")
    with col2:
        st.metric("Projected Value", f"${metrics['projected_value']:,.0f}")
    with col3:
        st.metric("ROI", f"{metrics['roi']}%")

    # Section 2: Yield Principles
    st.markdown("---")
    st.markdown("## Yield Principles")
    st.markdown("Here we briefly explain how the 3 main principles of our idea work:")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### 1. Construction Cost")
        st.markdown("Construction costs include labor, materials, permits, and other costs that form the project budget. Without careful planning, costs often exceed budgets by significant margins, making accurate estimation critical")

    with col2:
        st.markdown("#### 2. Market Value")
        st.markdown("Market value is the price buyers will pay, usually estimated by comparing similar property sales. It depends on factors like location, features, and market conditions, defining the project's value")

    with col3:
        st.markdown("#### 3. Returns")
        st.markdown("ROI is the project’s profit divided by its total investment cost. Developers find it hard to predict ROI accurately because it requires forecasting future values and costs under uncertain conditions")

    # Section 5: Live Design Companion
    st.markdown("---")
    st.markdown("## Live Design Companion")
    st.markdown("Here we describe the Current Key metrics of the model as it currently is.")

    # Key Metrics with Pie Chart
    col_metrics, col_pie = st.columns([1, 1])

    with col_metrics:
        st.markdown("#### Key Metrics")
        st.metric("Estimated Cost", f"${metrics['estimated_cost']:,.0f}")
        st.metric("Projected Value", f"${metrics['projected_value']:,.0f}")
        st.metric("ROI", f"{metrics['roi']}%")

    with col_pie:
        # Create pie chart for cost breakdown
        cost_data = get_mock_cost_components()
        pie_fig = create_pie_chart(cost_data, "Cost Components Breakdown")
        st.plotly_chart(pie_fig, use_container_width=True, key="cost_breakdown_pie")

    # Design Impact with Bar Chart
    col_bar, col_design_metrics = st.columns([1, 1])

    with col_bar:
        # Create bar chart for design metrics
        design_data = {
            "Floor Area Ratio": metrics['floor_area_ratio'],
            "Total Units": metrics['units']['total'],
            "Circulation %": metrics['circulation_ratio']
        }
        bar_fig = create_bar_chart(design_data, "Design Impact Metrics", "Metric", "Value")
        st.plotly_chart(bar_fig, use_container_width=True, key="design_impact_bar")

    with col_design_metrics:
        st.markdown("#### Design Impact")
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Floor Area Ratio", f"{metrics['floor_area_ratio']}")
            st.metric("Total Units", f"{metrics['units']['total']}")
        with col_b:
            st.metric("2BR Units", f"{metrics['units']['2br']}")
            st.metric("1BR Units", f"{metrics['units']['1br']}")
        st.metric("Circulation Ratio", f"{metrics['circulation_ratio']}%")

    # Section 6: Scenario Comparison
    st.markdown("---")
    st.markdown("## Scenario Comparison")
    st.markdown("Where we test our copilot's capacity to guide us through different design iterations")

    col_scenario_a, col_scenario_b = st.columns(2)

    with col_scenario_a:
        st.markdown("#### Scenario A")
        st.markdown("**Brick & Glass Facade**")
        
        # Scenario A controls
        floors_a = st.slider("Floors", 3, 15, 8, key="floors_a")
        units_a = st.slider("Units", 20, 100, 45, key="units_a")
        facade_a = st.selectbox("Facade Type", ["Brick & Glass", "Full Glass", "Concrete"], key="facade_a")
        structure_a = st.selectbox("Structure", ["Steel", "Concrete", "Hybrid"], key="structure_a")
        
        # Mock calculations for Scenario A
        cost_a = 5600000
        roi_a = 131
        
        st.metric("Cost", f"${cost_a:,.0f}")
        st.metric("ROI", f"{roi_a}%")
        
        # Pros and Cons
        st.markdown("**Pros:**")
        st.markdown("- High Finishes")
        st.markdown("- Local Materials")
        st.markdown("- No Delays")
        
        st.markdown("**Cons:**")
        st.markdown("- Cost Limited Units")
        st.markdown("- Not the target ratios")

    with col_scenario_b:
        st.markdown("#### Scenario B")
        st.markdown("**Full Glass Facade**")
        
        # Scenario B controls
        floors_b = st.slider("Floors", 3, 15, 10, key="floors_b")
        units_b = st.slider("Units", 20, 100, 55, key="units_b")
        facade_b = st.selectbox("Facade Type", ["Full Glass", "Brick & Glass", "Concrete"], key="facade_b")
        structure_b = st.selectbox("Structure", ["Concrete", "Steel", "Hybrid"], key="structure_b")
        
        # Mock calculations for Scenario B
        cost_b = 7300000
        roi_b = 107
        
        st.metric("Cost", f"${cost_b:,.0f}")
        st.metric("ROI", f"{roi_b}%")
        
        # Pros and Cons
        st.markdown("**Pros:**")
        st.markdown("- Hits the Targets")
        st.markdown("- Increases unit count by 10%")
        st.markdown("- Affordable Finishes")
        
        st.markdown("**Cons:**")
        st.markdown("- Quality gets compromised")
        st.markdown("- Importing Materials")
        st.markdown("- Will Face severe delays")

    # Scenario comparison chart
    st.markdown("#### Scenario Comparison Chart")
    comparison_data = {
        "Scenario A": [cost_a/1000000, roi_a],
        "Scenario B": [cost_b/1000000, roi_b]
    }

    fig_comparison = go.Figure()
    fig_comparison.add_trace(go.Bar(
        name='Cost (M$)',
        x=['Scenario A', 'Scenario B'],
        y=[cost_a/1000000, cost_b/1000000],
        marker_color=COLORS[0],
        yaxis='y'
    ))
    fig_comparison.add_trace(go.Bar(
        name='ROI (%)',
        x=['Scenario A', 'Scenario B'],
        y=[roi_a, roi_b],
        marker_color=COLORS[1],
        yaxis='y2'
    ))

    fig_comparison.update_layout(
        title='Scenario Comparison: Cost vs ROI',
        xaxis_title='Scenario',
        yaxis=dict(title='Cost (Million $)', side='left'),
        yaxis2=dict(title='ROI (%)', side='right', overlaying='y'),
        barmode='group',
        height=400
    )

    st.plotly_chart(fig_comparison, use_container_width=True, key="scenario_comparison_chart")

    # Section 7: Cost & ROI Analysis
    st.markdown("---")
    st.markdown("## Cost + ROI Analysis")
    st.markdown("Where we draw the conclusions from the current analysis")

    # Cost Components and ROI Sensitivity
    col_cost_chart, col_roi_curve = st.columns(2)

    with col_cost_chart:
        st.markdown("#### Cost Components")
        cost_data = get_mock_cost_components()
        cost_fig = create_pie_chart(cost_data, "Cost Components Breakdown")
        st.plotly_chart(cost_fig, use_container_width=True, key="final_cost_breakdown_pie")

    with col_roi_curve:
        st.markdown("#### ROI Sensitivity Curve")
        roi_fig = create_roi_sensitivity_curve()
        st.plotly_chart(roi_fig, use_container_width=True, key="roi_sensitivity_curve")

    # Current Chosen Scenario Summary
    st.markdown("#### Current Chosen Scenario")

    col_summary_metrics, col_summary_text = st.columns([1, 2])

    with col_summary_metrics:
        st.metric("Cost per Sqft", "$310")
        st.metric("Value per Sqft", "$462")
        st.metric("ROI Yield", "181%")

    with col_summary_text:
        st.markdown('**"Overall project cost increased by 14% compared to baseline scenario."**')
        st.markdown('**"Façade choice contributes 22% of total cost – consider alternative finishes."**')
        st.markdown('**"Parking ratio exceeds minimum requirements; reducing it could save $480k."**')

    # Detailed Analysis Sections
    st.markdown("#### Detailed Analysis")

    col_analysis_1, col_analysis_2 = st.columns(2)

    with col_analysis_1:
        # Cost Analysis
        st.markdown("##### Cost Analysis")
        st.markdown("• Façade choice contributes 22% of total cost – consider alternative finishes.")
        st.markdown("• Parking ratio exceeds minimum requirements; reducing it could save $480k.")
        st.markdown("• Changing structure to hybrid timber/steel saves 9% on construction costs.")
        st.markdown("• Structural spans exceed standard limits; may require redesign or increased cost.")
        
        # Strategic Design
        st.markdown("##### Strategic Design")
        st.markdown("• Reducing circulation area by 4% unlocks one additional rentable unit per floor.")
        st.markdown("• Current configuration exceeds FAR limits for the site — zoning adjustment required.")
        st.markdown("• East-facing units have the highest value per sq ft; prioritize views and daylight.")
        st.markdown("• Courtyard reduces unit count but boosts perceived value — consider hybrid typology.")

    with col_analysis_2:
        # ROI & Value
        st.markdown("##### ROI & Value")
        st.markdown("• Projected ROI is 28.6%, a 3.2% improvement over the previous version.")
        st.markdown("• Value per square meter improved by 7% due to unit mix optimization.")
        st.markdown("• Adding 2 floors increases cost by 11% but ROI only improves by 1.5% — diminishing returns.")
        st.markdown("• Net revenue per unit increased with smaller 1BR units, despite lower rent/unit.")
        
        # Financial Strategy
        st.markdown("##### Financial Strategy")
        st.markdown("• This scenario may require updated financing strategy due to increased CAPEX.")
        st.markdown("• Flagged as high-design, high-cost — recommended for premium rental tier.")
        st.markdown("• Consider tenant amenity trade-off: rooftop deck vs. rentable floor area.")
        st.markdown("• Feasibility rating: Green (Design within financial target envelope).")

    # Constructability & Phasing
    st.markdown("##### Constructability & Phasing")
    st.markdown("• Phased construction strategy recommended: podium + tower staging reduces financial exposure.")
    st.markdown("• Selected materials may require longer lead times — impact on delivery schedule.")
    st.markdown("• Structural spans exceed standard limits; may require redesign or increased cost.")


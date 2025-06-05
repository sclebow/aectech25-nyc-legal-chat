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

# === Constants and Config ===
FLASK_URL = "http://127.0.0.1:5000/llm_call"
RAG_OPTIONS = ["LLM only", "LLM + RAG"]
RAG_URLS = {
    "LLM only": FLASK_URL,
    "LLM + RAG": "http://127.0.0.1:5000/llm_rag_call"
}
MODE_OPTIONS = ["local", "openai", "cloudflare"]
MODE_URL = "http://127.0.0.1:5000/set_mode"
sample_questions = [
    "What is the cost benchmark of six concrete column footings for a 10,000 sq ft commercial building?",
    "What is the typical cost per sqft for structural steel options?  Let's assume a four-story apartment building.  Make assumptions on the loading.",
    "How do steel frame structures compare to concrete frame structures, considering cost and durability?",
    "What are the ROI advantages of using precast concrete in construction projects?",
    "Can you provide a cost estimate for a 10,000 sq ft commercial building?",
    "What are the key factors affecting the cost of a residential building?",
    "What are some cost modeling best practices?",
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
def query_llm(user_input):
    try:
        response = requests.post(FLASK_URL, json={"input": user_input})
        if response.status_code == 200:
            return response.json().get("response", "No response from server.")
        else:
            return f"Error: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Exception: {str(e)}"

def query_llm_with_rag(user_input, rag_mode, stream_mode, max_tokens=1500):
    mode = config.get_mode() if hasattr(config, 'get_mode') else 'unknown'
    gen_model = None
    emb_model = None
    try:
        if mode == "cloudflare":
            gen_model = st.session_state.get("cf_gen_model", cloudflare_models[0])
            emb_model = st.session_state.get("cf_emb_model", cloudflare_embedding_models[0])
        else:
            gen_model = getattr(config, 'completion_model', None)
            emb_model = getattr(config, 'embedding_model', None)
    except Exception:
        gen_model = None
        emb_model = None
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # output_header_markdown = f"### Input: {user_input}\n\n"
    url = RAG_URLS.get(rag_mode, FLASK_URL)
    try:
        if stream_mode == "Streaming":
            response = requests.post(url, json={"input": user_input, "stream": True, "max_tokens": int(max_tokens)}, stream=True)
            if response.status_code == 200:
                streamed_text = ""
                placeholder = st.empty()
                for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                    if chunk:
                        streamed_text += chunk
                        placeholder.markdown(streamed_text)
                        time.sleep(0.05)
                logger.info({
                    "timestamp": timestamp,
                    "prompt": user_input,
                    "mode": mode,
                    "text_generation_model": gen_model,
                    "embedding_model": emb_model,
                    "rag_state": rag_mode,
                    "output": streamed_text
                })
                return streamed_text
            else:
                return f"Error: {response.status_code} - {response.text}"
        else:
            response = requests.post(url, json={"input": user_input, "max_tokens": int(max_tokens)})
            if response.status_code == 200:
                data = response.json()
                if "sources" in data:
                    response_text = data.get('response', 'No response from server.')
                    output = (
                        f"{response_text}\n\n**Sources:**\n{data['sources']}"
                    )
                else:
                    response_text = data.get("response", "No response from server.")
                    output = response_text
            else:
                response_text = f"Error: {response.status_code} - {response.text}"
                output = response_text
            logger.info({
                "timestamp": timestamp,
                "prompt": user_input,
                "mode": mode,
                "text_generation_model": gen_model,
                "embedding_model": emb_model,
                "rag_state": rag_mode,
                "output": response_text
            })
            return output
    except Exception as e:
        response_text = f"Exception: {str(e)}"
        output = response_text
        logger.info({
            "timestamp": timestamp,
            "prompt": user_input,
            "mode": mode,
            "text_generation_model": gen_model,
            "embedding_model": emb_model,
            "rag_state": rag_mode,
            "output": response_text
        })
        return output

def run_flask_server():
    global flask_process
    if flask_process is None or flask_process.poll() is not None:
        flask_process = subprocess.Popen(
            ["python", "-u", "gh_server.py"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stream_subprocess_output(flask_process)
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

# === Streamlit UI ===
st.set_page_config(page_title="ROI LLM Assistant", layout="wide")
st.title("ROI LLM Assistant")
st.markdown("This is a Streamlit GUI for the ROI LLM Assistant. It allows you to interact with the LLM and RAG system.")
# Start the Flask server if not already running
if "flask_status" not in st.session_state:
    st.session_state["flask_status"] = "Default Status: Not Running"
    start_flask_and_wait()
# Flask server controls
with st.expander("Flask Server Controls", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Start Flask Server"):
            status = start_flask_and_wait()
            st.session_state["flask_status"] = status
    with col2:
        if st.button("Stop Flask Server"):
            status = stop_flask_server()
            st.session_state["flask_status"] = status
flask_status = st.session_state.get("flask_status", "Default Status: Not Running")

col1, col2 = st.columns([3, 1], vertical_alignment="center")

with col2:
    # Add a refresh button
    if st.button("Refresh Status"):
        try:
            resp = requests.get("http://127.0.0.1:5000/status", timeout=1)
            if resp.status_code == 200:
                st.session_state["flask_status"] = "Flask server is running."
            else:
                st.session_state["flask_status"] = "Flask server is not running."
        except Exception:
            st.session_state["flask_status"] = "Flask server is not running."

with col1:
    flask_status_info = st.info(f"Flask Server Status: {flask_status}")

if "running" in flask_status.lower() and "not" not in flask_status.lower():
    # Update the status placeholder
    flask_status_info.info(f"Flask Server Status: {flask_status}", icon="✅")
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
        rag_mode = st.segmented_control("Choose LLM Call Type", RAG_OPTIONS, default=RAG_OPTIONS[0], key="rag_radio", selection_mode="single")
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
                output = query_llm_with_rag(sample, rag_mode, stream_mode, max_tokens)
        st.session_state["messages"].append({"role": "assistant", "content": output})

    # Handle freeform chat input
    if user_input:
        st.session_state["messages"].append({"role": "user", "content": user_input})
        with chat_message_container:
            with st.chat_message("user"):
                st.markdown(user_input)
            with st.chat_message("assistant"):
                st.markdown("_Processing..._")
                output = query_llm_with_rag(user_input, rag_mode, stream_mode, max_tokens)
        st.session_state["messages"].append({"role": "assistant", "content": output})
else:
    st.warning("The Flask server must be running to get a response.")

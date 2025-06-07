from flask import Flask, request, jsonify, Response
# import ghhops_server as hs
import llm_calls
from project_utils import rag_utils
from server import config
import uuid
import logging
import time

app = Flask(__name__)

# Set up logging
logging.basicConfig(
    filename='llm_server.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

collection, ranker = rag_utils.init_rag(mode=config.get_mode())

@app.route('/llm_call', methods=['POST'])
def llm_call():
    data = request.get_json()
    input_string = data.get('input', '')
    stream = data.get('stream', False)
    max_tokens = data.get('max_tokens', 1500)
    request_id = str(uuid.uuid4())
    logging.info(f"Received /llm_call request | id={request_id} | input={input_string}")

    if stream:
        def generate():
            data_context, response = llm_calls.route_query_to_function(input_string, stream=True, max_tokens=max_tokens, request_id=request_id)
            # Prepend data_context at the start of the stream
            yield f"[DATA CONTEXT]: {data_context}\n\n"
            if hasattr(response, '__iter__') and not isinstance(response, str):
                for chunk in response:
                    yield chunk
            else:
                yield str(response)
        return Response(generate(), mimetype='text/plain')
    else:
        data_context, response = llm_calls.route_query_to_function(input_string, max_tokens=max_tokens, request_id=request_id)
        return jsonify({'data_context': data_context, 'response': response, 'request_id': request_id})

@app.route('/set_mode', methods=['POST'])
def set_mode():
    data = request.get_json()
    mode = data.get('mode', None)
    cf_gen_model = data.get('cf_gen_model', None)
    cf_emb_model = data.get('cf_emb_model', None)
    if mode not in ["local", "openai", "cloudflare"]:
        return jsonify({'status': 'error', 'message': 'Invalid mode'}), 400
    # Pass model overrides to config
    config.set_mode(mode, cf_gen_model=cf_gen_model, cf_emb_model=cf_emb_model)
    # Optionally, re-initialize RAG collection/ranker if needed
    global collection, ranker
    collection, ranker = rag_utils.init_rag(mode=mode)
    return jsonify({'status': 'success', 'mode': mode, 'cf_gen_model': cf_gen_model, 'cf_emb_model': cf_emb_model})

@app.route('/status', methods=['GET'])
def status():
    # Return current mode and models for UI polling
    return jsonify({
        'status': 'ok',
        'mode': config.get_mode(),
        'cf_gen_model': getattr(config, 'completion_model', None),
        'cf_emb_model': getattr(config, 'embedding_model', None)
    }), 200

@app.route('/log_stream', methods=['GET'])
def log_stream():
    def generate():
        log_path = 'llm_server.log'
        try:
            with open(log_path, 'r') as f:
                f.seek(0, 2)  # Move to end of file
                while True:
                    line = f.readline()
                    if line:
                        yield line
                    else:
                        time.sleep(0.5)
        except Exception as e:
            yield f'Error reading log: {str(e)}\n'
    return Response(generate(), mimetype='text/plain')

if __name__ == '__main__':
    app.run(debug=False, use_reloader=False)


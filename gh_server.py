from flask import Flask, request, jsonify, Response
# import ghhops_server as hs
import llm_calls
from project_utils import rag_utils
from server import config
import uuid
import logging
import time
import threading
import queue
from logger_setup import setup_logger, set_request_id

app = Flask(__name__)

# Set up logging
logger = setup_logger(name="app_logger", log_dir="logs", log_file="app.log")
logging.basicConfig(level=logging.DEBUG)  # Ensure root logger is DEBUG

collection, ranker = rag_utils.init_rag(mode=config.get_mode())

class QueueLogHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg)

@app.route('/llm_call', methods=['POST'])
def llm_call():
    data = request.get_json()
    input_string = data.get('input', '')
    stream = data.get('stream', False)
    max_tokens = data.get('max_tokens', 1500)
    request_id = str(uuid.uuid4())
    set_request_id(request_id)  # Set thread-local request_id for all logs in this request
    thread_id = threading.get_ident()
    parent_thread_id = getattr(threading.current_thread(), '_parent_ident', None)
    thread_id_str = str(thread_id) if parent_thread_id else "main"
    logger.info(f"[id={request_id}] [thread={thread_id_str}] [function=llm_call] [description=Received /llm_call request | input={input_string}]")

    if stream:
        def generate():
            set_request_id(request_id)
            log_q = queue.Queue()
            queue_handler = QueueLogHandler(log_q)
            queue_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
            # Attach to root logger to capture all logs
            root_logger = logging.getLogger()
            root_logger.addHandler(queue_handler)
            root_logger.setLevel(logging.DEBUG)
            logger.debug(f"[id={request_id}] [thread={thread_id_str}] [function=llm_call] [description=Streaming started.]")
            try:
                data_context, response = llm_calls.route_query_to_function(input_string, stream=True, max_tokens=max_tokens, request_id=request_id)
                yield f"[DATA CONTEXT]: {data_context}\n"
                yield "[RESPONSE]:\n"
                if hasattr(response, '__iter__') and not isinstance(response, str):
                    for chunk in response:
                        # Always prefix response chunks with [RESPONSE]:
                        if chunk.strip():
                            yield f"[RESPONSE]:{chunk}"
                        # Drain log queue after each chunk
                        while not log_q.empty():
                            log_line = log_q.get()
                            if log_line != "__END__":
                                yield f"[LOG]: {log_line}\n"
                else:
                    yield f"[RESPONSE]:{str(response)}"
                # Drain any remaining logs
                log_q.put("__END__")
                while not log_q.empty():
                    log_line = log_q.get()
                    if log_line != "__END__":
                        yield f"[LOG]: {log_line}\n"
            finally:
                root_logger.removeHandler(queue_handler)
        return Response(generate(), mimetype='text/plain')
    else:
        data_context, response = llm_calls.route_query_to_function(input_string, max_tokens=max_tokens, request_id=request_id)
        # For non-streaming, collect logs from the in-memory handler as before
        if hasattr(logger, 'memory_handler'):
            logs = '\n'.join(logger.memory_handler.get_logs(50, request_id=request_id))
        else:
            logs = '[No in-memory logs available]'
        return jsonify({'data_context': data_context, 'response': response, 'request_id': request_id, 'logs': logs})

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

if __name__ == '__main__':
    app.run(debug=False, use_reloader=False)


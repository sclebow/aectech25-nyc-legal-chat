from flask import Flask, request, jsonify, Response
# import ghhops_server as hs
import llm_calls
from utils import rag_utils
from server import config

app = Flask(__name__)

collection, ranker = rag_utils.init_rag(mode=config.get_mode())

@app.route('/llm_call', methods=['POST'])
def llm_call():
    data = request.get_json()
    input_string = data.get('input', '')
    stream = data.get('stream', False)
    max_tokens = data.get('max_tokens', 1500)

    if stream:
        def generate():
            for chunk in llm_calls.route_query_to_function(input_string, stream=True, max_tokens=max_tokens):
                yield chunk
        return Response(generate(), mimetype='text/plain')
    else:
        answer = llm_calls.route_query_to_function(input_string, max_tokens=max_tokens)
        return jsonify({'response': answer})

@app.route('/llm_rag_call', methods=['POST'])
def llm_rag_call():
    data = request.get_json()
    input_string = data.get('input', '')
    stream = data.get('stream', False)
    max_tokens = data.get('max_tokens', 1500)

    if stream:
        def generate():
            answer, sources = llm_calls.route_query_to_function(input_string, collection, ranker, True, stream=True, max_tokens=max_tokens)
            # If answer is a generator, yield from it
            if hasattr(answer, '__iter__') and not isinstance(answer, str):
                for chunk in answer:
                    yield chunk
            else:
                yield str(answer)
            # Optionally, yield sources at the end (as JSON or plain text)
            if sources:
                yield f"\n\n[SOURCES]: {sources}"
        return Response(generate(), mimetype='text/plain')
    else:
        answer, sources = llm_calls.route_query_to_function(input_string, collection, ranker, True, max_tokens=max_tokens)
        return jsonify({'response': answer, 'sources': sources})

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


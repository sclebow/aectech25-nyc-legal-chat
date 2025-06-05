from flask import Flask, request, jsonify, Response
# import ghhops_server as hs
import llm_calls
from project_utils import rag_utils
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
            data_context, response = llm_calls.route_query_to_function(input_string, stream=True, max_tokens=max_tokens)
            # Prepend data_context at the start of the stream
            yield f"[DATA CONTEXT]: {data_context}\n\n"
            if hasattr(response, '__iter__') and not isinstance(response, str):
                for chunk in response:
                    yield chunk
            else:
                yield str(response)
        return Response(generate(), mimetype='text/plain')
    else:
        data_context, response = llm_calls.route_query_to_function(input_string, max_tokens=max_tokens)
        return jsonify({'data_context': data_context, 'response': response})

@app.route('/llm_rag_call', methods=['POST'])
def llm_rag_call():
    data = request.get_json()
    input_string = data.get('input', '')
    stream = data.get('stream', False)
    max_tokens = data.get('max_tokens', 1500)

    if stream:
        def generate():
            (data_context, response), sources = llm_calls.route_query_to_function(input_string, collection, ranker, True, stream=True, max_tokens=max_tokens)
            yield f"[DATA CONTEXT]: {data_context}\n\n"
            if hasattr(response, '__iter__') and not isinstance(response, str):
                for chunk in response:
                    yield chunk
            else:
                yield str(response)
            if sources:
                yield f"\n\n[SOURCES]: {sources}"
        return Response(generate(), mimetype='text/plain')
    else:
        (data_context, response), sources = llm_calls.route_query_to_function(input_string, collection, ranker, True, max_tokens=max_tokens)
        return jsonify({'data_context': data_context, 'response': response, 'sources': sources})

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


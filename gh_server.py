from flask import Flask, request, jsonify

import llm_calls
from utils import rag_utils
from server import config

app = Flask(__name__)

collection, ranker = rag_utils.init_rag(mode=config.get_mode())

@app.route('/llm_call', methods=['POST'])
def llm_call():
    data = request.get_json()
    input_string = data.get('input', '')

    # router_output = llm_calls.classify_input(input_string)
    # if "Refuse to answer" in router_output:
    #     answer = "Sorry, I can only answer questions about cost estimating and roi."
    # else:
    #     answer = llm_calls.suggest_cost_optimizations(input_string)
    answer = llm_calls.route_query_to_function(input_string)

    return jsonify({'response': answer})

@app.route('/llm_rag_call', methods=['POST'])
def llm_rag_call():
    data = request.get_json()
    input_string = data.get('input', '')

    # router_output = llm_calls.classify_input(input_string)
    # if "Refuse to answer" in router_output:
    #     answer = "Sorry, I can only answer questions about cost estimating and roi."
    # else:
    # answer, sources = rag_utils.rag_call_alt(input_string, collection, ranker)
    answer, sources = llm_calls.route_query_to_function(input_string, collection, ranker, True)

    return jsonify({'response': answer, 'sources': sources})

@app.route('/set_mode', methods=['POST'])
def set_mode():
    data = request.get_json()
    mode = data.get('mode', None)
    if mode not in ["local", "openai", "cloudflare"]:
        return jsonify({'status': 'error', 'message': 'Invalid mode'}), 400
    config.set_mode(mode)
    # Optionally, re-initialize RAG collection/ranker if needed
    global collection, ranker
    collection, ranker = rag_utils.init_rag(mode=mode)
    return jsonify({'status': 'success', 'mode': mode})

@app.route('/status', methods=['GET'])
def status():
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    app.run(debug=True)


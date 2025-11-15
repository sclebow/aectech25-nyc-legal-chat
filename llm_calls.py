import server.config as config  

import concurrent.futures
import logging
import inspect
import threading
from logger_setup import get_request_id, set_request_id

import ast, re
import urllib.parse

# Routing Functions Below
from project_utils import rag_utils

import json

from llm_query import run_llm_query


# def run_llm_query(system_prompt: str, user_input: str, stream: bool = False, max_tokens: int = 1500, max_retries: int = 15, retry_delay: int = 2, request_id: str = None, large_model=True) -> str:
#     """ Run a query against the LLM with a system prompt and user input.
#     If stream is True, returns a generator for streaming output.
#     If stream is False, returns the full response as a string.
#     If the LLM call fails, it will retry up to max_retries times with a delay of retry_delay seconds between retries.
#     """
#     attempt = 0
#     caller = inspect.stack()[1].function
#     thread_id = threading.get_ident()
#     parent_thread_id = getattr(threading.current_thread(), '_parent_ident', None)
#     thread_id_str = str(thread_id)
#     parent_thread_str = str(parent_thread_id) if parent_thread_id else "main"
#     log_prefix = f"[id={request_id}] [thread={thread_id_str}] [parent={parent_thread_str}] [function=run_llm_query] [called_by={caller}]"
#     # Truncate and format long/multiline strings for logging
#     def format_log_string(label, value):
#         if not isinstance(value, str):
#             value = str(value)
#         # Replace newlines for log readability
#         value = value.replace('\n', '\\n')
#         return f"{label}={value}"
#     if large_model:
#         model = config.completion_model
#     else:
#         model = config.completion_model_sml
#     if request_id:
#         set_request_id(request_id)
#     while attempt < max_retries:
#         try:
#             if not stream:
#                 response = config.client.chat.completions.create(
#                     model=model,
#                     messages=[
#                         {"role": "system", "content": system_prompt},
#                         {"role": "user", "content": user_input}
#                     ],
#                     temperature=0.0,
#                     max_tokens=max_tokens,
#                 )
#                 logging.info(f"{log_prefix} [description=LLM query successful on attempt {attempt+1} | {format_log_string('system_prompt', system_prompt)} | {format_log_string('user_input', user_input)} | response={str(response.choices[0].message.content).strip()}] [usage={response.usage}]")
#                 return str(response.choices[0].message.content).strip()
#             else:
#                 response = config.client.chat.completions.create(
#                     model=config.completion_model,
#                     messages=[
#                         {"role": "system", "content": system_prompt},
#                         {"role": "user", "content": user_input}
#                     ],
#                     temperature=0.0,
#                     max_tokens=max_tokens,
#                     stream=True,
#                 )
#                 def generator():
#                     full_message = ""
#                     usage_data = None
#                     for chunk in response:
#                         delta = getattr(chunk.choices[0], 'delta', None)
#                         if delta and hasattr(delta, 'content') and delta.content:
#                             full_message += delta.content
#                             yield delta.content
#                         if hasattr(chunk, 'usage') and chunk.usage:
#                             usage_data = chunk.usage
#                     logging.info(f"{log_prefix} [description=LLM streaming query finished on attempt {attempt+1} | {format_log_string('system_prompt', system_prompt)} | {format_log_string('user_input', user_input)} | full_message={full_message}] [usage={usage_data}]")
#                 return generator()
#         except Exception as e:
#             if hasattr(e, "status_code") and e.status_code == 429 or "rate limit" in str(e).lower():
#                 logging.warning(f"{log_prefix} [description=Rate limit hit, retrying in {retry_delay} seconds... (attempt {attempt+1}/{max_retries})]")
#             else:
#                 logging.error(f"{log_prefix} [description=Error in LLM call: {e}. Retrying in {retry_delay} seconds... (attempt {attempt+1}/{max_retries}) | {format_log_string('system_prompt', system_prompt)} | {format_log_string('user_input', user_input)}]")
#                 logging.error(f"{log_prefix} [description=System prompt: {system_prompt}]")
#                 logging.error(f"{log_prefix} [description=User input: {user_input}]")
#             time.sleep(retry_delay)
#             attempt += 1
#     logging.critical(f"{log_prefix} [description=LLM call failed after {max_retries} attempts. | {format_log_string('system_prompt', system_prompt)} | {format_log_string('user_input', user_input)}]")
#     raise RuntimeError(f"LLM call failed after {max_retries} attempts due to repeated errors or rate limits.")

def classify_data_sources(message: str, data_sources: dict, request_id: str = None) -> dict:
    """
    Classify the user message into one of the five core data sources.
    Returns a dictionary with boolean values indicating which data sources are relevant.
    """
    system_prompt = (
        "You are a data source classification agent for a building project assistant.\n"
        "Classify the user's query into one or more of the following data sources:\n"
        + "\n".join([f"{key}: {value}" for key, value in data_sources.items()]) + "\n"
        "Return ONLY a comma-separated list of the relevant data sources, or 'None' if none apply.\n\n"
        "Examples:\n"
        "Query: What is the typical cost per sqft for concrete in NYC?\nOutput: rsmeans\n"
        "Query: What is the value of this building based on its size and type?\nOutput: value model\n"
        "Query: How can I reduce construction costs without changing the layout?\nOutput: knowledge base\n"
        "Query: What is the total concrete cost for this project?\nOutput: ifc\n"
        "Query: What is the estimated valuation of this 3 bedroom, 1 bathroom unit? \n Output: valuation model\n"
        "Remember, return ONLY the comma-separated list of the relevant data sources."
    )

    thread_id = threading.get_ident()
    parent_thread_id = getattr(threading.current_thread(), '_parent_ident', None)
    caller = inspect.stack()[1].function
    thread_id_str = str(thread_id)
    parent_thread_str = str(parent_thread_id) if parent_thread_id else "main"
    log_prefix = f"[id={request_id}] [thread={thread_id_str}] [parent={parent_thread_str}] [function=classify_data_sources] [called_by={caller}]"
    # logging.info(f"{log_prefix} [description=Classifying message: {message}]")
    response = config.client.chat.completions.create(
        model=config.completion_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ],
        temperature=0.0,
    )

    
    
    classification = response.choices[0].message.content.strip()
    
    logging.info(f"{log_prefix} [description=Classification result: {classification}] [usage={response.usage}]")
    if classification.lower() == "none":
        return {key: False for key in data_sources.keys()}
    
    # Split the classification into a list and create a dictionary with boolean values
    classified_sources = classification.split(", ")
    return {key: (key in classified_sources) for key in data_sources.keys()}

def get_rsmeans_context(message: str, request_id: str = None, thread_id: int = None) -> str:
    """
    Get the RSMeans context for the user message.
    Returns a string with the RSMeans data or a prompt to use RSMeans.
    """
    if request_id:
        set_request_id(request_id)
    thread_id_val = thread_id if thread_id is not None else threading.get_ident()
    parent_thread_id = getattr(threading.current_thread(), '_parent_ident', None)
    caller = inspect.stack()[1].function
    thread_id_str = str(thread_id_val)
    parent_thread_str = str(parent_thread_id) if parent_thread_id else "main"
    logging.info(f"[id={request_id}] [thread={thread_id_str}] [parent={parent_thread_str}] [function=get_rsmeans_context] [called_by={caller}] [description=message: {message}]")
    # from cost_data.rsmeans_utils import get_rsmeans_context_from_prompt
    rsmeans_context = get_rsmeans_context_from_prompt(message, request_id=request_id)
    return rsmeans_context

def get_ifc_context(message: str, request_id: str = None, thread_id: int = None) -> str:
    """
    Get the IFC context for the user message.
    Returns a string with the IFC data or a prompt to use IFC.
    """
    if request_id:
        set_request_id(request_id)
    thread_id_val = thread_id if thread_id is not None else threading.get_ident()
    parent_thread_id = getattr(threading.current_thread(), '_parent_ident', None)
    caller = inspect.stack()[1].function
    thread_id_str = str(thread_id_val)
    parent_thread_str = str(parent_thread_id) if parent_thread_id else "main"
    logging.info(f"[id={request_id}] [thread={thread_id_str}] [parent={parent_thread_str}] [function=get_ifc_context] [called_by={caller}] [description=message: {message}]")
    return ifc_utils.get_ifc_context_from_query(message, request_id=request_id)

def get_knowledge_base_context(message: str, request_id: str = None, thread_id: int = None) -> str:
    """
    Get the knowledge base context for the user message.
    Returns a string with the knowledge base data or a prompt to use the knowledge base.
    """
    if request_id:
        set_request_id(request_id)
    thread_id_val = thread_id if thread_id is not None else threading.get_ident()
    parent_thread_id = getattr(threading.current_thread(), '_parent_ident', None)
    caller = inspect.stack()[1].function
    thread_id_str = str(thread_id_val)
    parent_thread_str = str(parent_thread_id) if parent_thread_id else "main"
    logging.info(f"[id={request_id}] [thread={thread_id_str}] [parent={parent_thread_str}] [function=get_knowledge_base_context] [called_by={caller}] [description=message: {message}]")
    return rag_utils.get_rag_context_from_query(message)

def get_value_model_context(message: str, request_id: str = None, thread_id: int = None) -> str:
    """
    Get the value model context for the user message.
    Returns a string with the value model data or a prompt to use the value model.
    """
    if request_id:
        set_request_id(request_id)
    thread_id_val = thread_id if thread_id is not None else threading.get_ident()
    parent_thread_id = getattr(threading.current_thread(), '_parent_ident', None)
    caller = inspect.stack()[1].function
    thread_id_str = str(thread_id_val)
    parent_thread_str = str(parent_thread_id) if parent_thread_id else "main"
    logging.info(f"[id={request_id}] [thread={thread_id_str}] [parent={parent_thread_str}] [function=get_value_model_context] [called_by={caller}] [description=message: {message}]")

    with open('./valuation_model/freq_mappings.json') as f:
        valuation_model_dict = json.load(f)
    bldg_types = str(valuation_model_dict['BLDG_TYPE'].keys())

    # prompt = str(f'You have access to a model which will return a valuation estimate when passed a python dict \n which requires the following fields: \n LIVING_AREA: the living area in square feet, \n GROSS_AREA: the total area of the building in square feet, \n LAND_SF: the land area in square feet, \n FULL_BTH: the number of full bathrooms, \n CD_FLOOR: the floor number of the property, \n BLDG_TYPE: the building type, options are {bldg_types}, \n RES_FLOOR: the number of residential floors, \n TT_RMS: the total number of rooms, \n Based on the users query, provide a Python dict with just the keys and values, no comments or explanations. Output ONLY the dict, for example:{"LIVING_AREA": 1200, "GROSS_AREA": 1500, "LAND_SF": 2000, "FULL_BTH": 2, "CD_FLOOR": 3, "BLDG_TYPE": "Condo", "RES_FLOOR": 5, "TT_RMS": 6}\n')
    prompt = f"""You have access to a model which will return a valuation estimate when passed a Python dict with the following fields:
        - LIVING_AREA: the living area in square feet
        - GROSS_AREA: the total area of the building in square feet
        - LAND_SF: the land area in square feet
        - FULL_BTH: the number of full bathrooms
        - CD_FLOOR: the floor number of the property
        - BLDG_TYPE: the building type, options are: {bldg_types}
        - RES_FLOOR: the number of residential floors
        - TT_RMS: the total number of rooms

        Example:
        {{"LIVING_AREA": 1200, "GROSS_AREA": 1500, "LAND_SF": 2000, "FULL_BTH": 2, "CD_FLOOR": 3, "BLDG_TYPE": "CM - Condo Main", "RES_FLOOR": 5, "TT_RMS": 6}}

        Based on the user's query, output ONLY the Python dict with just the keys and values. 
        Fill in any missing data with your best estimate.
        Do not include any explanations, comments, or extra text. 
        Output ONLY the dict, and nothing else.
        """
    
    valuation_dict = run_llm_query(prompt, message, large_model=False)
    match = re.search(r"\{.*\}", valuation_dict, re.DOTALL)
    if match:
        feat_dict = ast.literal_eval(match.group())
        predicted_value = predict_property_value(feat_dict) 
        print(f'the valuation model predicted value is ${predicted_value:.0f}')
    else:
        predicted_value = ""
        raise ValueError("No dict found in LLM output")
    
    return f'the valuation model predicted value is ${predicted_value:.0f}'

def classify_and_get_context(message: str, request_id: str = None):
    """
    Classify the user message and retrieve the relevant context from all data sources.
    Returns a dictionary with the classification result and the context from each data source.
    """
    data_sources = {
        "rsmeans": "This is a database for construction cost data, including unit costs for various materials and labor.  It is used to answer cost benchmark questions, such as the cost per square foot of concrete. If the user asks about a specific material cost, this source will be used.",
        "ifc": "This is a database for the user's building model in IFC format, which includes detailed information about the building's components and quantities.  It also includes the dollar and hourly cost of different components.",
        "knowledge base": "This is a knowledge base for architecture and construction, which includes general information about design, materials, and construction practices.",
        "value model": "This is a machine learning model that predicts the value of a building based some of its features, such as size, and type.",
    }

    # Classify the data sources needed for the query
    data_sources_needed_dict = classify_data_sources(message, data_sources, request_id=request_id)

    # If project data is needed, do not use rsmeans
    if data_sources_needed_dict.get("project data"):
        data_sources_needed_dict["rsmeans"] = False

    # Prepare a dictionary to hold the context from each data source
    data_context = {}

    # For each data source that is needed, retrieve the relevant context
    if data_sources_needed_dict.get("rsmeans"):
        data_context["rsmeans"] = get_rsmeans_context(message, request_id=request_id)
    if data_sources_needed_dict.get("ifc"):
        data_context["ifc"] = get_ifc_context(message, request_id=request_id)
    if data_sources_needed_dict.get("knowledge base"):
        data_context["knowledge base"] = get_knowledge_base_context(message, request_id=request_id)
    if data_sources_needed_dict.get("value model"):
        data_context["value model"] = get_value_model_context(message, request_id=request_id)

    return {
        "classification": data_sources_needed_dict,
        "context": data_context
    }

def get_ifc_viewer_url_params(response):
    """
    Given the LLM response and data_sources_needed_dict, return the IFC Viewer URL params string (or empty string).
    """
    ifc_settings_str = ""
    system_prompt = (
        "You are an assistant that helps configure a web-based IFC Viewer for BIM models. "
        "Given a LLM's response to a user query, output a JSON object with urlParams to control the viewer. "
        "The IFC Viewer accepts the following urlParams:\n"
        "- visibleCategories: a comma-separated list of IFC element types to make visible (e.g., 'IFCWALL,IFCSLAB').\n"
        "- categoryColors: a comma-separated list of 'IFCType:hexcolor' pairs (e.g., 'IFCWALL:ff0000,IFCSLAB:00ff00').\n"
        "- categoryOpacity: a comma-separated list of 'IFCType:value' pairs, where value is between 0 and 1 (e.g., 'IFCWALL:0.8,IFCSLAB:0.5').\n"
        "Only include keys that are relevant for the current response. "
        "Respond ONLY with a JSON object, for example:\n"
        "{\n"
        '  "visibleCategories": "IFCWALL,IFCSLAB",\n'
        '  "categoryColors": "IFCWALL:ff0000,IFCSLAB:00ff00",\n'
        '  "categoryOpacity": "IFCWALL:0.8,IFCSLAB:0.5"\n'
        "}\n"
        "You must always suggest an adaptation of the IFC Viewer URL params based on the LLM response. "
        # "If no adaptation is needed, respond with an empty JSON object: {}"
    )
    print(f"Received response for IFC Viewer URL params: {response}")
    print("Generating IFC Viewer URL params from response...")
    logging.info(f"[id={get_request_id()}] [function=get_ifc_viewer_url_params] [description=Generating IFC Viewer URL params from response] [response={response}]")
    ifc_response = run_llm_query(
        system_prompt=system_prompt,
        user_input=response,
    )
    print(f"IFC Viewer URL params response: {ifc_response}")
    
    try:
        params = json.loads(ifc_response)
        if params:
            ifc_settings_str = "&" + "&".join(
                f"{urllib.parse.quote_plus(str(k))}={urllib.parse.quote_plus(str(v))}"
                for k, v in params.items() if v
            )
        else:
            ifc_settings_str = ""
    except Exception as e:
        logging.info(f"[id={get_request_id()}] [function=get_ifc_viewer_url_params] [description=Error parsing IFC Viewer URL params: {e}]")
        ifc_settings_str = ""
    logging.info(f"[id={get_request_id()}] [function=get_ifc_viewer_url_params] [description=IFC Viewer URL params generated: {ifc_settings_str}]")
    return ifc_settings_str

def route_query_to_function(message: str, collection=None, ranker=None, use_rag: bool=False, stream: bool = False, max_tokens: int = 1500, request_id: str = None):
    thread_id = threading.get_ident()
    parent_thread_id = getattr(threading.current_thread(), '_parent_ident', None)
    caller = inspect.stack()[1].function
    thread_id_str = str(thread_id)
    parent_thread_str = str(parent_thread_id) if parent_thread_id else "main"
    log_prefix = f"[id={request_id}] [thread={thread_id_str}] [parent={parent_thread_str}] [function=route_query_to_function] [called_by={caller}]"
    logging.info(f"{log_prefix} [description=Routing message: {message}]")
    data_sources = {
        "rsmeans": "This is a database for construction cost data, including unit costs for various materials and labor.  It is used to answer cost benchmark questions, such as the cost per square foot of concrete. If the user asks about a specific material cost, this source will be used.",
        "ifc": "This is a database for the user's building model in IFC format, which includes detailed information about the building's components and quantities.  It also includes the dollar and hourly cost of different components.",
        "knowledge base": "This is a knowledge base for architecture and construction, which includes general information about design, materials, and construction practices.",
        "value model": "This is a machine learning model that predicts the value of a building based some of its features, such as size, and type.",
    }

    # Run the query through the classification function
    data_sources_needed_dict = classify_data_sources(message, data_sources, request_id=request_id)

    # If project data is needed, do not use rsmeans
    if data_sources_needed_dict.get("project data"):
        data_sources_needed_dict["rsmeans"] = False

    # Debugging output
    logging.info(f"{log_prefix} [description=Data sources needed: {data_sources_needed_dict}]")

    # Create a data context dictionary based on the classification
    data_context = {}

    # Map data source keys to their context functions
    context_functions = {
        "rsmeans": get_rsmeans_context,
        "ifc": get_ifc_context,
        "knowledge base": get_knowledge_base_context,
        "value model": get_value_model_context,
    }

    # Prepare futures for relevant data sources
    futures = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for key, needed in data_sources_needed_dict.items():
            if needed and key in context_functions:
                futures[key] = executor.submit(context_functions[key], message, request_id, thread_id=threading.get_ident())
        # Collect results as they complete
        for key, future in futures.items():
            data_context[key] = future.result()

    # Use utf-8 encoding to avoid UnicodeEncodeError in Windows console
    # print(f"Data context: {data_context}".encode("utf-8", errors="replace").decode("utf-8"))

    # Now that we have the data context, we can provide it with the system prompt and user input
    system_prompt = (
        "You are an expert in building cost estimation, ROI analysis, and project data analysis.\n"
        "Your task is to answer the user's question using the provided relevant context. "
        "The user is a designer or project manager, tailor the level of detail and technicality to their expertise.\n"
        "Use the relevant context to inform your answer, and always explicitly list out any assumptions you are making (such as location, year, unit, or scope). "
        "If the question is not related to cost, ROI, or project data, politely refuse to answer.\n"
        "Provide a summary of the relavent context used in your answer, and if applicable, include a markdown table with the data.\n"
        "Respond in markdown format, include any formulas in LaTeX format\n"
        "Ignore any mathmatical information or example cost data or calculations in the knowledge base, as it is not relevant to the user's question\n"
        "You must cite your sources and page number.  However, if you have no sources, you can say 'No sources found'.\n"
        "Format references as: [Source: filename, Page: X]\n"
        f"Relevant context: {data_context}\n"
    )

    response = run_llm_query(
        system_prompt=system_prompt,
        user_input=message,
        stream=stream,
        max_tokens=max_tokens,
        request_id=request_id,
        large_model=False
    )

    if not stream:
        ifc_settings_str = get_ifc_viewer_url_params(response, data_sources_needed_dict)
        # Optionally, you can return ifc_settings_str as part of the return value if needed
    else:
        pass # For streaming, the IFC Viewer URL params will be handled in the streaming generator

    logging.info(f"{log_prefix} [description=Finished routing and LLM call.]")

    return data_context, response
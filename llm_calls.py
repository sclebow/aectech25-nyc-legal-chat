import server.config as config  
from cost_data.rsmeans_utils import get_rsmeans_context_from_prompt
from project_utils.rag_utils import rag_call_alt
import time
import concurrent.futures
import logging
import inspect

# Routing Functions Below
from project_utils import rag_utils, ifc_utils
from bdg_data import bdg_utils

def run_llm_query(system_prompt: str, user_input: str, stream: bool = False, max_tokens: int = 1500, max_retries: int = 15, retry_delay: int = 2, request_id: str = None) -> str:
    """ Run a query against the LLM with a system prompt and user input.
    If stream is True, returns a generator for streaming output.
    If stream is False, returns the full response as a string.
    If the LLM call fails, it will retry up to max_retries times with a delay of retry_delay seconds between retries.
    """
    import server.config as config
    attempt = 0
    caller = inspect.stack()[1].function
    log_prefix = f"[id={request_id}] [run_llm_query] [called_by={caller}]"
    logging.info(f"{log_prefix} Starting LLM query | system_prompt_len={len(system_prompt)} | user_input={user_input}")
    while attempt < max_retries:
        try:
            if not stream:
                response = config.client.chat.completions.create(
                    model=config.completion_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_input}
                    ],
                    temperature=0.0,
                    max_tokens=max_tokens,
                )
                logging.info(f"{log_prefix} LLM query successful on attempt {attempt+1}")
                return str(response.choices[0].message.content).strip()
            else:
                response = config.client.chat.completions.create(
                    model=config.completion_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_input}
                    ],
                    temperature=0.0,
                    max_tokens=max_tokens,
                    stream=True,
                )
                def generator():
                    full_message = ""
                    usage_data = None
                    for chunk in response:
                        delta = getattr(chunk.choices[0], 'delta', None)
                        if delta and hasattr(delta, 'content') and delta.content:
                            full_message += delta.content
                            yield delta.content
                        # Try to extract usage data if present in chunk
                        if hasattr(chunk, 'usage') and chunk.usage:
                            usage_data = chunk.usage
                    logging.info(f"{log_prefix} LLM streaming query started on attempt {attempt+1}")
                    logging.info(f"{log_prefix} LLM streaming query full message: {full_message}")
                    if usage_data:
                        logging.info(f"{log_prefix} LLM streaming usage data: {usage_data}")
                return generator()
        except Exception as e:
            if hasattr(e, "status_code") and e.status_code == 429 or "rate limit" in str(e).lower():
                logging.warning(f"{log_prefix} Rate limit hit, retrying in {retry_delay} seconds... (attempt {attempt+1}/{max_retries})")
            else:
                logging.error(f"{log_prefix} Error in LLM call: {e}. Retrying in {retry_delay} seconds... (attempt {attempt+1}/{max_retries})")
                logging.error(f"{log_prefix} System prompt: {system_prompt}")
                logging.error(f"{log_prefix} User input: {user_input}")
            time.sleep(retry_delay)
            attempt += 1
    logging.critical(f"{log_prefix} LLM call failed after {max_retries} attempts.")
    raise RuntimeError(f"LLM call failed after {max_retries} attempts due to repeated errors or rate limits.")

def classify_data_sources(message: str, data_sources: dict, request_id: str = None) -> dict:
    """
    Classify the user message into one of the five core data sources.
    Returns a dictionary with boolean values indicating which data sources are relevant.
    """
    system_prompt = (
        "You are a data source classification agent for a building project assistant.\n"
        "Classify the user's query into one or more of the following data sources:\n"
        + "\n".join([f"{key}: {value}" for key, value in data_sources.items()]) + "\n"
        "Return a comma-separated list of the relevant data sources, or 'None' if none apply.\n\n"
        "rsmeans and project data are mutually exclusive, so if project data is needed, do not include rsmeans.\n"
        "Examples:\n"
        "Query: What is the typical cost per sqft for concrete in NYC?\nOutput: rsmeans\n"
        "Query: How many units does my current project support and what’s the total cost of concrete?\nOutput: project data\n"
        "Query: What is the value of this building based on its size and type?\nOutput: value model\n"
        "Query: How can I reduce construction costs without changing the layout?\nOutput: knowledge base, cost model\n"
        "Query: What is the total concrete cost for this project?\nOutput: project data\n"
    )

    log_prefix = f"[id={request_id}] [classify_data_sources]"
    logging.info(f"{log_prefix} Classifying message: {message}")
    response = config.client.chat.completions.create(
        model=config.completion_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ],
        temperature=0.0,
    )
    
    classification = response.choices[0].message.content.strip()
    logging.info(f"{log_prefix} Classification result: {classification}")
    if classification.lower() == "none":
        return {key: False for key in data_sources.keys()}
    
    # Split the classification into a list and create a dictionary with boolean values
    classified_sources = classification.split(", ")
    return {key: (key in classified_sources) for key in data_sources.keys()}

def get_rsmeans_context(message: str, request_id: str = None) -> str:
    """
    Get the RSMeans context for the user message.
    Returns a string with the RSMeans data or a prompt to use RSMeans.
    """
    logging.info(f"[id={request_id}] [get_rsmeans_context] message: {message}")
    rsmeans_context = get_rsmeans_context_from_prompt(message)
    return rsmeans_context


def get_ifc_context(message: str, request_id: str = None) -> str:
    """
    Get the IFC context for the user message.
    Returns a string with the IFC data or a prompt to use IFC.
    """
    logging.info(f"[id={request_id}] [get_ifc_context] message: {message}")
    return ifc_utils.get_ifc_context_from_query(message)

def get_project_data_context(message: str, request_id: str = None) -> str:
    """
    Get the project data context for the user message.
    Returns a string with the project data or a prompt to use project data.
    """
    logging.info(f"[id={request_id}] [get_project_data_context] message: {message}")
    return bdg_utils.get_project_data_context_from_query(message)

def get_knowledge_base_context(message: str, request_id: str = None) -> str:
    """
    Get the knowledge base context for the user message.
    Returns a string with the knowledge base data or a prompt to use the knowledge base.
    """
    logging.info(f"[id={request_id}] [get_knowledge_base_context] message: {message}")
    return rag_utils.get_rag_context_from_query(message)

def get_value_model_context(message: str, request_id: str = None) -> str:
    """
    Get the value model context for the user message.
    Returns a string with the value model data or a prompt to use the value model.
    """
    logging.info(f"[id={request_id}] [get_value_model_context] message: {message}")
    return "Value model is not implemented yet."  # Placeholder

def get_cost_model_context(message: str, request_id: str = None) -> str:
    """
    Get the cost model context for the user message.
    Returns a string with the cost model data or a prompt to use the cost model.
    """
    logging.info(f"[id={request_id}] [get_cost_model_context] message: {message}")
    return "Cost model is not implemented yet."  # Placeholder

def route_query_to_function(message: str, collection=None, ranker=None, use_rag: bool=False, stream: bool = False, max_tokens: int = 1500, request_id: str = None):
    logging.info(f"[id={request_id}] [route_query_to_function] Routing message: {message}")
    data_sources = {
        "rsmeans": "This is a database for construction cost data, including unit costs for various materials and labor.  It is used to answer cost benchmark questions, such as the cost per square foot of concrete. If the user asks about a specific material cost, this source will be used.",
        "ifc": "This is a database for the user's building model in IFC format, which includes detailed information about the building's components and quantities.",
        "project data": "This is a database for this specific building's data, which includes quantities and costs of materials and labor.  If the user describes a project or asks a general cost question, this source will not be used. Only use this source if the user asks about the current project data.",
        "knowledge base": "This is a knowledge base for architecture and construction, which includes general information about design, materials, and construction practices.",
        "value model": "This is a machine learning model that predicts the value of a building based some of its features, such as size, and type.",
        "cost model": "This is a machine learning model that predicts the cost of a building based on some of its features, such as size, and type.",
    }

    # Run the query through the classification function
    data_sources_needed_dict = classify_data_sources(message, data_sources, request_id=request_id)

    # If project data is needed, do not use rsmeans
    if data_sources_needed_dict.get("project data"):
        data_sources_needed_dict["rsmeans"] = False

    # Debugging output
    logging.info(f"[id={request_id}] Data sources needed: {data_sources_needed_dict}")

    # Create a data context dictionary based on the classification
    data_context = {}

    # Map data source keys to their context functions
    context_functions = {
        "rsmeans": get_rsmeans_context,
        "ifc": get_ifc_context,
        "project data": get_project_data_context,
        "knowledge base": get_knowledge_base_context,
        "value model": get_value_model_context,
        "cost model": get_cost_model_context,
    }

    # Prepare futures for relevant data sources
    futures = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for key, needed in data_sources_needed_dict.items():
            if needed and key in context_functions:
                futures[key] = executor.submit(context_functions[key], message, request_id)
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
        request_id=request_id
    )

    # response = str(data_sources_needed_dict) + "\n" + str(data_context) + "\n" + response # For debugging purposes, uncomment this line to see the data sources and context used in the response

    logging.info(f"[id={request_id}] [route_query_to_function] Finished routing and LLM call.")
    return data_context, response
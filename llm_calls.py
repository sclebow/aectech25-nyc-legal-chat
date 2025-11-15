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

import streamlit as st

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

def classify_prompt_type(message: str, prompt_types: dict):
    """
    Classify the user message into one of the prompt types.
    Returns the prompt type as a string.
    """
    system_prompt = (
        "You are a prompt classification agent to assist an architect.\n"
        "Classify the user's query into one of the following prompt types:\n"
        + "\n".join([f"{key}: {value}" for key, value in prompt_types.items()]) + "\n"
        "Return ONLY the prompt type that best matches the user's query.\n\n"
        "Examples:\n"
        "Query: Please provide the scope of work for an architectural design contract.\nOutput: scope_of_work\n"
        "Query: What are the standard clauses in an Architect Owner Agreement?\nOutput: contract_language\n"
        "Remember, return ONLY the prompt type."
    )

    thread_id = threading.get_ident()
    parent_thread_id = getattr(threading.current_thread(), '_parent_ident', None)
    caller = inspect.stack()[1].function
    thread_id_str = str(thread_id)
    parent_thread_str = str(parent_thread_id) if parent_thread_id else "main"
    log_prefix = f"[id={get_request_id()}] [thread={thread_id_str}] [parent={parent_thread_str}] [function=classify_prompt_type] [called_by={caller}]"
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
    
    logging.info(f"{log_prefix} [description=Prompt type classification result: {classification}] [usage={response.usage}]")
    return classification

def ask_contract_language_prompt(message: str):
    """
    Ask the LLM a contract language related prompt.
    Returns the LLM response as a string.
    """
    system_prompt = "You are an AI assistant helping architects with contract language for AEC contracts. Be helpful, professional, and detail-oriented."
    response = run_llm_query(system_prompt=system_prompt, user_input=message)
    return response

def ask_scope_of_work_prompt(message: str):
    """
    Ask the LLM a scope of work related prompt.
    Returns the LLM response as a string.
    """
    current_scope_of_work = st.session_state.get("scope_of_work")

    current_scope_of_work = str(current_scope_of_work)
    print(f"Current Scope of Work: {current_scope_of_work}")

    system_prompt = "\n".join(
        [
            "You are helping define a comprehensive scope of work for an Architect Owner Agreement.",
            "Here is a dictionary of deliverables and associated scope items defined so far:",
            f"{current_scope_of_work}",
        ]
    )
    print(f"System Prompt: {system_prompt}")
    response = run_llm_query(system_prompt=system_prompt, user_input=message)
    return response

def ask_scope_of_work_change_prompt(message: str):
    """
    Ask the LLM a scope of work change related prompt.
    Returns the LLM response as a string.
    """
    current_scope_of_work = st.session_state.get("scope_of_work")

    current_scope_of_work = str(current_scope_of_work)
    print(f"Current Scope of Work: {current_scope_of_work}")

    system_prompt = "\n".join(
        [
            "You are helping modify and expand a comprehensive scope of work for an Architect Owner Agreement.",
            "Here is a dictionary of deliverables and associated scope items defined so far:",
            f"{current_scope_of_work}",
            "Respond only with an updated dictionary including the requested changes.",
            "Focus on accuracy and completeness.",
            "Do not include any explanations or additional text.",
            ""
        ]
    )
    print(f"System Prompt: {system_prompt}")
    modified_dictionary = run_llm_query(system_prompt=system_prompt, user_input=message)

    # Check if the response is a valid dictionary
    try:
        updated_scope_of_work = ast.literal_eval(modified_dictionary)
        if isinstance(updated_scope_of_work, dict):
            # Update the session state with the new scope of work
            st.session_state["scope_of_work"] = updated_scope_of_work
            print(f"Updated Scope of Work: {updated_scope_of_work}")
            response = "Scope of work updated successfully."
        else:
            print("LLM response is not a valid dictionary.")
            response = "I'm sorry, I could not process the changes to the scope of work. Please ensure your request is clear."

    except (ValueError, SyntaxError) as e:
        print(f"Error parsing LLM response: {e}")
        response = "I'm sorry, I could not process the changes to the scope of work. Please ensure your request is clear."

    return response

def complete_contact_draft(message: str):
    with open("templates/contract-template-short.md", "r") as f:
        contract_template = f.read()

    system_prompt = "The content below is a contract template for an Architect Owner Agreement. Use the template to generate a complete contract draft based on the user's requirements."
    system_prompt += f"\n\nContract Template:\n{contract_template}"

    response = run_llm_query(system_prompt=system_prompt, user_input=message)
    return response

def classify_and_get_context(message: str):
    """
    Classify the user message and retrieve the relevant context from all data sources.
    Returns a dictionary with the classification result and the context from each data source.
    """
    prompt_types = {
        "contract_language": "This is a typical Architect Owner Agreement contract template, including scope of work, deliverables, payment terms, and legal clauses.",
        "scope_of_work": "This is a detailed scope for the project the architect is working on, including deliverables, tasks, and timelines.",
        "complete_contract_draft": "This a request to generate a complete contract draft based on previous conservation and a template.",
        "scope_of_work_question": "This is for questions about the scope of work for the current project.",
        "scope_of_work_change": "The user wants to modify or expand the current scope of work for the project.",
    }

    # Classify the user prompt for routing
    prompt_type = classify_prompt_type(message, prompt_types)

    print(f"Classified prompt type: {prompt_type}")

    response = "I'm sorry, I can only assist with contract language and scope of work related queries at this time."

    if prompt_type == "contract_language":
        response = ask_contract_language_prompt(message)
    elif prompt_type == "scope_of_work_question":
        response = ask_scope_of_work_prompt(message)
    elif prompt_type == "scope_of_work_change":
        response = ask_scope_of_work_change_prompt(message)
    elif prompt_type == "complete_contract_draft":
        response = complete_contact_draft(message)

    # data_sources = {
    #     "rsmeans": "This is a database for construction cost data, including unit costs for various materials and labor.  It is used to answer cost benchmark questions, such as the cost per square foot of concrete. If the user asks about a specific material cost, this source will be used.",
    #     "ifc": "This is a database for the user's building model in IFC format, which includes detailed information about the building's components and quantities.  It also includes the dollar and hourly cost of different components.",
    #     "knowledge base": "This is a knowledge base for architecture and construction, which includes general information about design, materials, and construction practices.",
    #     "value model": "This is a machine learning model that predicts the value of a building based some of its features, such as size, and type.",
    # }

    # # Classify the data sources needed for the query
    # data_sources_needed_dict = classify_data_sources(message, data_sources, request_id=request_id)

    # # Prepare a dictionary to hold the context from each data source
    # data_context = {}

    # # For each data source that is needed, retrieve the relevant context
    # if data_sources_needed_dict.get("rsmeans"):
    #     data_context["rsmeans"] = get_rsmeans_context(message, request_id=request_id)
    # if data_sources_needed_dict.get("ifc"):
    #     data_context["ifc"] = get_ifc_context(message, request_id=request_id)
    # if data_sources_needed_dict.get("knowledge base"):
    #     data_context["knowledge base"] = get_knowledge_base_context(message, request_id=request_id)
    # if data_sources_needed_dict.get("value model"):
    #     data_context["value model"] = get_value_model_context(message, request_id=request_id)

    return response

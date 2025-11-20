import server.config as config  

# import concurrent.futures
import logging
import inspect
import threading
from logger_setup import get_request_id, set_request_id

import ast, re
# import urllib.parse

# Routing Functions Below
# from project_utils import rag_utils

# import json

from llm_query import run_llm_query

import streamlit as st
import base64

import pandas as pd

def auto_download_csv(csv_data, filename="categories_list.csv"):
    b64 = base64.b64encode(csv_data.encode()).decode()
    href = f'''
        <a id="auto_download" href="data:text/csv;base64,{b64}" download="{filename}" style="display:none"></a>
        <script>
        document.getElementById('auto_download').click();
        </script>
    '''
    st.components.v1.html(href, height=0)

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
    system_prompt = "\n".join(
        [
            "You are an AI assistant helping architects with contract language for AEC contracts. ",
            "Be helpful, professional, and detail-oriented.",
            "Pretend you are a legal expert in architecture contracts.",
            "Assume the user is a Senior Architect with 10+ years of experience.",
            "Make suggestions regarding contract language that is favorable to the architect.",
            "The current project scope of work is as follows:",
            f"{st.session_state.get('scope_of_work')}",
            ""
        ]
    )
    response = run_llm_query(system_prompt=system_prompt, user_input=message)
    return response

def ask_scope_of_work_prompt(message: str):
    """
    Ask the LLM a scope of work related prompt.
    Returns the LLM response as a string.
    """
    current_scope_of_work = st.session_state.get("scope_of_work")

    current_scope_of_work = str(current_scope_of_work)
    
    system_prompt = "\n".join(
        [
            "You are helping define a comprehensive scope of work for an Architect Owner Agreement.",
            "Here is a dictionary of deliverables and associated scope items defined so far:",
            f"{current_scope_of_work}",
            "Here is the corresponding assumptions and exclusions for the project:",
            f"{st.session_state.get('ASSUMPTIONS_AND_EXCLUSIONS')}",
        ]
    )
    response = run_llm_query(system_prompt=system_prompt, user_input=message)
    return response

def ask_scope_of_work_change_prompt(message: str, update_assumptions: bool = True):
    """
    Ask the LLM a scope of work change related prompt.
    Returns the LLM response as a string.
    """
    current_scope_of_work = st.session_state.get("scope_of_work")

    current_scope_of_work = str(current_scope_of_work)
    print(f"Current Scope of Work: {current_scope_of_work}")

    system_prompt = "\n".join(
        [
            "You are helping modify a comprehensive scope of work for an Architect Owner Agreement.",
            "Here is a dictionary of deliverables and associated scope items defined so far:",
            f"{current_scope_of_work}",
            "The dictionary is structured as {phase: {discipline: [items]}}.",
            "The structure must be preserved in your response, but the content can be modified as needed.",
            "You may need to add new phases or disciplines based on the user's request.",
            "Respond only with an updated dictionary including the requested changes.",
            "Focus on accuracy and completeness.",
            "Do not include any explanations or additional text.",
            ""
        ]
    )
    print(f"System Prompt: {system_prompt}")
    modified_dictionary = run_llm_query(system_prompt=system_prompt, user_input=message, temp=0.2)

    # Check if the response is a valid dictionary
    try:
        updated_scope_of_work = ast.literal_eval(modified_dictionary)

        # Clean the string representation of the dictionary
        updated_scope_of_work = str(updated_scope_of_work).replace("\n", " ").replace("\r", " ").strip()

        # Check that the string starts with '{' and add if missing
        if not updated_scope_of_work.startswith("{"):
            updated_scope_of_work = "{" + updated_scope_of_work

        # Check that the string ends with '}' and add if missing
        if not updated_scope_of_work.endswith("}"):
            updated_scope_of_work = updated_scope_of_work + "}"

        if isinstance(updated_scope_of_work, dict):
            # Update the session state with the new scope of work
            st.session_state["scope_of_work"] = updated_scope_of_work
            print(f"Updated Scope of Work: {updated_scope_of_work}")
            response = "Scope of work updated successfully."

            if update_assumptions:
                # Also update the assumptions and exclusions 
                message = f"Update the assumptions and exclusions to be consistent with the following scope of work: {updated_scope_of_work}. Here is the current assumptions and exclusions: {st.session_state.get('ASSUMPTIONS_AND_EXCLUSIONS')}. Respond only with the updated assumptions and exclusions dictionary."
                ask_assumptions_and_exclusions_change_prompt(message, update_scope=False)
            
        else:
            print("LLM response is not a valid dictionary.")
            print(f"LLM Response for Scope of Work Update: {modified_dictionary}")
            response = "I'm sorry, I could not process the changes to the scope of work. Please ensure your request is clear."

    except (ValueError, SyntaxError) as e:
        print(f"Error parsing LLM response: {e}")
        print(f"LLM Response for Scope of Work Update: {modified_dictionary}")
        response = "I'm sorry, I could not process the changes to the scope of work. Please ensure your request is clear."

    print("Adding scope of work assistant message to session state.")
    st.session_state.messages.append({
        "role": "assistant",
        "content": response
    })
    # print("Rerunning Streamlit app to reflect updated scope of work.")
    # st.rerun()
    return response

def complete_contact_draft(message: str):
    with open("./template/contact-template-short.md", "r") as f:
        contract_template = f.read()

    system_prompt = "\n".join(
        [
            "The content below is a contract template for an Architect Owner Agreement. ",
            "Use the template to generate a complete contract draft based on the user's requirements and the project's scope of work.",
            f"Contract Template:\n{contract_template}",
            f"Project Scope of Work:\n{st.session_state.get('scope_of_work')}",
            "Provide only the edited sections and add notations to indicate where changes were made.",
            "Use markdown formatting, and show edited text in bold red.",
            "Do not show unchanged sections of the contract, just indicate they are unchanged.",
            ""
        ]
    )
    system_prompt += f"\n\nContract Template:\n{contract_template}"

    response = run_llm_query(system_prompt=system_prompt, user_input=message)
    return response

def update_categories_list():
    """
    Update the categories list in the sidebar based on the current scope of work, using an llm call
    """
    full_categories_list = st.session_state.get("FULL_CATEGORIES_LIST")

    current_scope_of_work = st.session_state.get("scope_of_work")

    # Call LLM to update categories list
    system_prompt = "\n".join(
        [
            "You are an AI assistant that creates a list of categories that should be expected in a BIM design model based on the scope of work for an architectural project.",
            "Given the scope of work dictionary, generate a comprehensive list of categories that should be included by selecting from the provided categories list.",
            f"Scope of Work:\n{current_scope_of_work}",
            f"Available Categories:\n{full_categories_list}",
            "Return ONLY a Python list of the selected categories that match the scope of work.",
            "All categories must be selected from the provided list.",
            "Response should start with '[' and end with ']'.",
            ""
        ]
    )
    print(f"System Prompt for Categories Update: {system_prompt}")
    llm_response = run_llm_query(system_prompt=system_prompt, user_input="Generate the categories list.")
    print(f"LLM Response for Categories Update: {llm_response}")
    # Parse the LLM response to get the list
    try:
        updated_categories = ast.literal_eval(llm_response)
        if isinstance(updated_categories, list):
            # Update the session state with the new categories list
            st.session_state["categories_list"] = updated_categories
            print(f"Updated Categories List: {updated_categories}")
            auto_download_csv(",".join(updated_categories), filename="categories_list.csv")
        else:
            print("LLM response is not a valid list.")
            print(f"LLM Response for Categories Update: {llm_response}")
    except (ValueError, SyntaxError) as e:
        print(f"Error parsing LLM response: {e}")
        print(f"LLM Response for Categories Update: {llm_response}")

def default_query(message: str):
    """
    Default LLM query when no specific classification is made.
    Returns the LLM response as a string.
    """
    system_prompt = "\n".join(
        [
            "You are a helpful AI assistant for architects working on AEC contracts and scopes of work.",
            "The question the user asked is not specifically about contract language or scope of work.",
            "Prompt the user to clarify their request or provide more details so you can assist them better.",
            "If possible, use their query to help improve the scope of work being developed.",
        ]
    )
    response = run_llm_query(system_prompt=system_prompt, user_input=message)
    return response

def ask_assumptions_and_exclusions_change_prompt(message: str, update_scope: bool = True):
    """
    Ask the LLM an assumptions and exclusions change related prompt.
    Returns the LLM response as a string.
    """
    current_assumptions_and_exclusions = st.session_state.get("ASSUMPTIONS_AND_EXCLUSIONS")
    current_assumptions_and_exclusions = str(current_assumptions_and_exclusions)

    system_prompt = "\n".join(
        [
            "You are helping modify a comprehensive assumptions and exclusions list for an Architect Owner Agreement.",
            "These assumptions and exclusions should not conflict with the current scope of work, and in fact should protect the designer from liability.",
            "Here is a dictionary of disciplines and associated assumptions and exclusions defined so far:",
            f"{current_assumptions_and_exclusions}",
            "The dictionary is structured as {discipline: [items]}.",
            "The structure must be preserved in your response, but the content can be modified as needed.",
            "Here is the corresponding scope of work for the project:",
            f"{st.session_state.get('scope_of_work')}",
            "Respond only with an updated dictionary including the requested changes to the assumptions and exclusions.",
            "Focus on accuracy and completeness.",
            "Do not include any explanations or additional text.",
            ""
        ]
    )
    print(f"System Prompt: {system_prompt}")
    modified_dictionary = run_llm_query(system_prompt=system_prompt, user_input=message)

    response = "I'm sorry, I could not process the changes to the assumptions and exclusions. Please ensure your request is clear."

    # Check if the response is a valid dictionary
    try:
        updated_assumptions_and_exclusions = ast.literal_eval(modified_dictionary)
        if isinstance(updated_assumptions_and_exclusions, dict):
            # Update the session state with the new assumptions and exclusions
            st.session_state["ASSUMPTIONS_AND_EXCLUSIONS"] = updated_assumptions_and_exclusions
            response = "Assumptions and exclusions updated successfully."
            if update_scope:
                # Also update the scope of work 
                message = f"Update the scope of work to be consistent with the following assumptions and exclusions: {updated_assumptions_and_exclusions}. Here is the current scope of work: {st.session_state.get('scope_of_work')}. Respond only with the updated scope of work dictionary."
                ask_scope_of_work_change_prompt(message, update_assumptions=False)

        else:
            print("LLM response is not a valid dictionary.")
            print(f"LLM Response for Assumptions and Exclusions Update: {modified_dictionary}")
    except (ValueError, SyntaxError) as e:
        print(f"Error parsing LLM response: {e}")
        print(f"LLM Response for Assumptions and Exclusions Update: {modified_dictionary}")

    print("Adding assumptions and exclusions assistant message to session state.")
    st.session_state.messages.append({
        "role": "assistant",
        "content": response
    })
    # print("Rerunning Streamlit app to reflect updated assumptions and exclusions.")
    # st.rerun()
    return response

def classify_and_get_context(message: str):
    """
    Classify the user message and retrieve the relevant context from all data sources.
    Returns a dictionary with the classification result and the context from each data source.
    """
    prompt_types = {
        "contract_language": "This is a typical Architect Owner Agreement contract template, including scope of work, deliverables, payment terms, and legal clauses.",
        # "scope_of_work": "This is a detailed scope with assumptions and exclusions for the project the architect is working on, including deliverables, tasks, and timelines.",
        "complete_contract_draft": "This a request to generate a complete contract draft based on previous conservation and a template.",
        "scope_of_work_question": "This is for questions about the scope of work or assumptions and exclusions for the current project.",
        "scope_of_work_change": "The user wants to modify or expand the current scope of work for the project.",
        "assumptions_and_exclusions_change": "The user wants to modify or expand the current assumptions and exclusions for the project.",
    }

    # Classify the user prompt for routing
    prompt_type = classify_prompt_type(message, prompt_types)

    print(f"Classified prompt type: {prompt_type}")
    st.session_state.messages.append({
        "role": "assistant",
        "content": f"I think your request is related to {prompt_type}. Let me process that for you."
    })
    if "contract_language" in prompt_type:
        response = ask_contract_language_prompt(message)
    elif "scope_of_work_question" in prompt_type:
        response = ask_scope_of_work_prompt(message)
    elif "scope_of_work_change" in prompt_type:
        response = ask_scope_of_work_change_prompt(message)
    elif "complete_contract_draft" in prompt_type:
        response = complete_contact_draft(message)
    elif "assumptions_and_exclusions_change" in prompt_type:
        response = ask_assumptions_and_exclusions_change_prompt(message)
    else:
        response = default_query(message)

    return response

import server.config as config  

import time
import logging
import inspect
import threading
from logger_setup import get_request_id, set_request_id

import streamlit as st

def run_llm_query(system_prompt: str, user_input: str, stream: bool = False, max_tokens: int = 1500, max_retries: int = 15, retry_delay: int = 2, request_id: str = None, large_model=True) -> str:
    """ Run a query against the LLM with a system prompt and user input.
    If stream is True, returns a generator for streaming output.
    If stream is False, returns the full response as a string.
    If the LLM call fails, it will retry up to max_retries times with a delay of retry_delay seconds between retries.
    
    Args:
        conversation_history: Optional list of previous messages in format [{"role": "user"/"assistant", "content": "..."}, ...]
                            System prompt should NOT be included in conversation_history.
    """
    attempt = 0
    caller = inspect.stack()[1].function
    thread_id = threading.get_ident()
    parent_thread_id = getattr(threading.current_thread(), '_parent_ident', None)
    thread_id_str = str(thread_id)
    parent_thread_str = str(parent_thread_id) if parent_thread_id else "main"
    log_prefix = f"[id={request_id}] [thread={thread_id_str}] [parent={parent_thread_str}] [function=run_llm_query] [called_by={caller}]"
    # Truncate and format long/multiline strings for logging
    def format_log_string(label, value):
        if not isinstance(value, str):
            value = str(value)
        # Replace newlines for log readability
        value = value.replace('\n', '\\n')
        return f"{label}={value}"
    if large_model:
        model = config.completion_model
    else:
        model = config.completion_model_sml
    if request_id:
        set_request_id(request_id)
    
    # Build messages list with conversation history
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(st.session_state.conversation_history)
    messages.append({"role": "user", "content": user_input})
    
    while attempt < max_retries:
        try:
            if not stream:
                response = config.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.0,
                    max_tokens=max_tokens,
                )
                logging.info(f"{log_prefix} [description=LLM query successful on attempt {attempt+1} | {format_log_string('system_prompt', system_prompt)} | {format_log_string('user_input', user_input)} | response={str(response.choices[0].message.content).strip()}] [usage={response.usage}]")
                return str(response.choices[0].message.content).strip()
            else:
                response = config.client.chat.completions.create(
                    model=config.completion_model,
                    messages=messages,
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
                        if hasattr(chunk, 'usage') and chunk.usage:
                            usage_data = chunk.usage
                    logging.info(f"{log_prefix} [description=LLM streaming query finished on attempt {attempt+1} | {format_log_string('system_prompt', system_prompt)} | {format_log_string('user_input', user_input)} | full_message={full_message}] [usage={usage_data}]")
                return generator()
        except Exception as e:
            if hasattr(e, "status_code") and e.status_code == 429 or "rate limit" in str(e).lower():
                logging.warning(f"{log_prefix} [description=Rate limit hit, retrying in {retry_delay} seconds... (attempt {attempt+1}/{max_retries})]")
            else:
                logging.error(f"{log_prefix} [description=Error in LLM call: {e}. Retrying in {retry_delay} seconds... (attempt {attempt+1}/{max_retries}) | {format_log_string('system_prompt', system_prompt)} | {format_log_string('user_input', user_input)}]")
                logging.error(f"{log_prefix} [description=System prompt: {system_prompt}]")
                logging.error(f"{log_prefix} [description=User input: {user_input}]")
            time.sleep(retry_delay)
            attempt += 1
    logging.critical(f"{log_prefix} [description=LLM call failed after {max_retries} attempts. | {format_log_string('system_prompt', system_prompt)} | {format_log_string('user_input', user_input)}]")
    raise RuntimeError(f"LLM call failed after {max_retries} attempts due to repeated errors or rate limits.")
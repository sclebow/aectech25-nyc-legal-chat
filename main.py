# import server.config as config
import llm_calls
from project_utils import rag_utils
import json
import tkinter as tk
from tkinter import simpledialog
import datetime
from logger_setup import setup_logger

# Get timestamp in UTC timezone
timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
print(f"Timestamp: {timestamp}")

logger = setup_logger()

# user_message = "How do architects balance form and function?"
def get_user_message():
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    width = 800
    default_prompt = "Compare the Return on Investment (ROI) of a steel frame vs. a concrete frame building."
    user_message = simpledialog.askstring("Input", "Enter your message:             ", initialvalue=default_prompt, parent=root)

    root.destroy()
    return user_message

user_message = get_user_message()
if user_message is None:
    logger.info({"event": "no_input_provided"})
    print("No input provided.")
    exit()
logger.info({"event": "user_message", "message": user_message})

### EXAMPLE 1: Router ###
# Classify the user message to see if we should answer or not
router_output = llm_calls.classify_input(user_message)
logger.info({"event": "router_output", "output": router_output})

if "Refuse to answer" in router_output:
    llm_answer = "Sorry, I can only answer questions about architecture."
else:
    llm_answer = llm_calls.route_query_to_function(message=user_message, collection=None, ranker=None, use_rag=False)
logger.info({
    "event": "llm_answer",
    "answer": llm_answer
})

print(f"LLM answer: {llm_answer}")

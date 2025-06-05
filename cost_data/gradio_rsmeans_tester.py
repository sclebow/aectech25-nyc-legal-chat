# Set path to the parent directory
import os
import sys
from pathlib import Path
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

import gradio as gr
import pandas as pd
from cost_data.rsmeans_utils import find_by_section_code, find_by_description, get_cost_data, list_sections

# Gradio functions
def format_tabbed_output(tab_name, prompt=None, result=None):
    output = f"**Tab:** {tab_name}\n\n"
    if prompt is not None:
        output += f"**Prompt:** {prompt}\n\n"
    if result is None or (hasattr(result, 'empty') and result.empty):
        output += "_No results found._"
    elif hasattr(result, 'to_markdown'):
        output += result.to_markdown(index=False)
    else:
        output += str(result)
    return output

def search_by_code(section_code):
    result = find_by_section_code(section_code)
    return format_tabbed_output("Search by Section Code", prompt=section_code, result=result)

def search_by_description(description):
    result = find_by_description(description)
    return format_tabbed_output("Search by Description", prompt=description, result=result)

def get_cost(section_code_or_desc):
    result = get_cost_data(section_code_or_desc)
    return format_tabbed_output("Get Cost Data (Code or Description)", prompt=section_code_or_desc, result=result)

def show_sections():
    result = list_sections()
    result = result.sort_values(['Masterformat Section Code', 'Section Name'])
    return format_tabbed_output("List All Sections", result=result)

def ask_cost_question(question):
    from llm_calls import route_query_to_function
    result = route_query_to_function(question)
    return format_tabbed_output("Ask Cost Question", prompt=question, result=result)

with gr.Blocks() as demo:
    gr.Markdown("# RSMeans Utility Tester")
    with gr.Tab("Search by Description"):
        desc_input = gr.Textbox(label="Description", value="Concrete Footing")
        desc_btn = gr.Button("Search")
        gr.Markdown("### Result: ")
        desc_output = gr.Markdown("_Enter a description and click 'Search' to see results here._", label="Result")
        desc_btn.click(search_by_description, inputs=desc_input, outputs=desc_output)
    with gr.Tab("Ask Cost Question"):
        question_input = gr.Textbox(label="Cost Question (natural language)", value="What is the typical cost per sqft for structural steel options?  Let's assume a four-story apartment building.  Make assumptions on the loading.")
        question_btn = gr.Button("Ask")
        gr.Markdown("### Result: ")
        question_output = gr.Markdown("_Enter a cost question and click 'Ask' to see results here._", label="Result")
        question_btn.click(ask_cost_question, inputs=question_input, outputs=question_output)
    with gr.Tab("Search by Section Code"):
        code_input = gr.Textbox(label="Masterformat Section Code", value="03 05 13.25")
        code_btn = gr.Button("Search")
        gr.Markdown("### Result: ")
        code_output = gr.Markdown("_Enter a section code and click 'Search' to see results here._", label="Result")
        code_btn.click(search_by_code, inputs=code_input, outputs=code_output)
    with gr.Tab("Get Cost Data (Code or Description)"):
        cost_input = gr.Textbox(label="Section Code or Description", value="03 05 13.25")
        cost_btn = gr.Button("Get Cost Data")
        gr.Markdown("### Result: ")
        cost_output = gr.Markdown("_Enter a section code or description and click 'Get Cost Data' to see results here._", label="Result")
        cost_btn.click(get_cost, inputs=cost_input, outputs=cost_output)
    with gr.Tab("List All Sections"):
        gr.Markdown(label="Sections", value=show_sections())

if __name__ == "__main__":
    demo.launch()

import os
import sys
from pathlib import Path
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

import streamlit as st
import pandas as pd
from cost_data.rsmeans_utils import find_by_section_code, find_by_description, get_cost_data, list_sections

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

st.title("RSMeans Utility Tester")
tabs = st.tabs([
    "Ask Cost Question",
    "Search by Description",
    "Search by Section Code",
    "Get Cost Data (Code or Description)",
    "List All Sections"
])

with tabs[0]:
    question_input = st.text_input("Cost Question (natural language)", value="What is the typical cost per sqft for structural steel options?  Let's assume a four-story apartment building.  Make assumptions on the loading.")
    if st.button("Ask", key="ask_question"):
        st.markdown("### Result:")
        st.markdown(ask_cost_question(question_input))
    else:
        st.markdown("_Enter a cost question and click 'Ask' to see results here._")

with tabs[1]:
    desc_input = st.text_input("Description", value="Concrete Footing")
    if st.button("Search", key="desc_search"):
        st.markdown("### Result:")
        st.markdown(search_by_description(desc_input))
    else:
        st.markdown("_Enter a description and click 'Search' to see results here._")

with tabs[2]:
    code_input = st.text_input("Masterformat Section Code", value="03 05 13.25")
    if st.button("Search", key="code_search"):
        st.markdown("### Result:")
        st.markdown(search_by_code(code_input))
    else:
        st.markdown("_Enter a section code and click 'Search' to see results here._")

with tabs[3]:
    cost_input = st.text_input("Section Code or Description", value="03 05 13.25")
    if st.button("Get Cost Data", key="cost_data"):
        st.markdown("### Result:")
        st.markdown(get_cost(cost_input))
    else:
        st.markdown("_Enter a section code or description and click 'Get Cost Data' to see results here._")

with tabs[4]:
    st.markdown(show_sections())

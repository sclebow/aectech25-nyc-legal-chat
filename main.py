# This is a LLM chatbot that allows architects to develop a scope of work for AEC contracts.
# Each interaction with the chatbot refines the scope of work, ultimately producing a comprehensive
# list of deliverables,
# along with associated scope items for each deliverable.

import pandas as pd
import streamlit as st
from llm_calls import classify_and_get_context, update_categories_list
from scope_visualizer import display_scope_of_work
from ui_styles import apply_custom_styles

default_scope_of_work_dict_file = "default_scope_of_work.dict"
default_scope_of_work_string = open(default_scope_of_work_dict_file, "r").read()
default_scope_of_work = eval(default_scope_of_work_string)

st.session_state["FULL_CATEGORIES_LIST"] = [
            "Structural Framing",
            "Structural Columns",
            "Structural Foundations",
            "Walls",
            "Floors",
            "Roofs",
            "Ceilings",
            "Doors",
            "Windows",
            "Stairs",
            "Railings",
            "Curtain Panels",
            "Curtain Wall Mullions",
            "Furniture",
            "Mechanical Equipment",
            "Plumbing Fixtures",
            "Lighting Fixtures",
            "Electrical Equipment",
            "Ducts",
            "Pipes",
]

print("\n" * 5)
print("Starting AEC Contract Assistant...")

st.set_page_config(
    page_title="ContractCadence",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Apply custom CSS styling
# apply_custom_styles()

# Build the chat interface
st.title("ContractCadence 🤖")
scope_column, chat_column = st.columns([3, 3])

# The chat window allows the user to have a conversation with the AI assistant
# This conversation would generate a dictionary of deliverables, and associated lists of scope items

st.session_state.setdefault("messages", [])
st.session_state.setdefault("scope_of_work", default_scope_of_work)
st.session_state.setdefault("conversation_history", [])

st.session_state.setdefault("first_run", True)

if st.session_state.first_run:
    print("First run - updating categories list")
    update_categories_list()
    st.session_state.first_run = False

with st.sidebar:
    st.markdown("##### Upload Reference Documents 📄")
    uploaded_files = st.file_uploader(
        "Upload architectural plans, contracts, or other reference documents to assist the AI in understanding your project requirements. Note: This feature is currently disabled.",
        accept_multiple_files=True,
        type=["pdf", "docx", "txt"],
    )
    if uploaded_files:
        st.markdown("**Uploaded Files:**")
        for uploaded_file in uploaded_files:
            st.markdown(f"- {uploaded_file.name}")
            
# The scope window displays the current scope of work being developed
# It shows a list of deliverables, each with associated scope items
with scope_column:

    # Use DEFAULT_SCOPE_OF_WORK for testing
    scope_to_display = st.session_state.scope_of_work
    table_height = display_scope_of_work(scope_to_display)

    categories_list = st.session_state["categories_list"]
    categories_list_csv = pd.Series(categories_list).to_csv(index=False, header=False)

    cols = st.columns(2)
    with cols[0]:
        # Add a download button for the scope of work
        scope_of_work_df = pd.DataFrame(st.session_state.scope_of_work)
        download_button = st.download_button(
            label="Download scope of work as CSV",
            data=scope_of_work_df.to_csv(index=False),
            file_name="scope_of_work.csv",
            mime="text/csv",
            width="stretch",
        )
    with cols[1]:
        # Add a download button for the categories list
        download_button = st.download_button(
            label="Download categories list as CSV",
            data=categories_list_csv,
            file_name="categories_list.csv",
            mime="text/csv",
            width="stretch",
        )

with chat_column:
    st.markdown("##### Chat with your AEC Contract Assistant 💬")
    message_container = st.container(height=table_height, border=True)

    if st.session_state.messages == []:
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": "Hello! I'm your AEC Contract Assistant. Describe your project and requirements, and I'll help you build a comprehensive scope of work."
            }
        )

    with message_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    if prompt := st.chat_input("Describe your project and requirements..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with message_container:
            with st.chat_message("user"):
                st.markdown(prompt)

            # Call LLM with conversation history for context, with streaming enabled
            response_generator = classify_and_get_context(prompt)

            # Display streaming response
            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                full_response = ""
                
                # Stream the response
                for chunk in response_generator:
                    full_response += chunk
                    response_placeholder.markdown(full_response + "▌")
                
                # Final update without cursor
                response_placeholder.markdown(full_response)

        # Update conversation history with user message and assistant response
        st.session_state.conversation_history.append({"role": "user", "content": prompt})
        st.session_state.conversation_history.append({"role": "assistant", "content": full_response})

        st.session_state.messages.append({"role": "assistant", "content": full_response})
            
str_list = []
str_list.append("This information should not be considered legal advice. Consult a qualified attorney for legal matters.\n")
str_list.append("Github Repository: https://github.com/sclebow/aectech25-nyc-legal-chat/ \n")
str_list.append("Contributers: ")
contributers_list = ["Scott Lebow, https://www.linkedin.com/in/sclebow/",
                     "Chu Ding, https://www.linkedin.com/in/chuding/",
                     "Yufei Wang, https://www.linkedin.com/in/yufei-wang-faye/",
                     "Douglas Kim, https://www.linkedin.com/in/dkim19/",
                     "Janez Mikec, https://www.linkedin.com/in/janezmikec/"]

# Randomize contributers order
import random
random.shuffle(contributers_list)

for contributer in contributers_list:
    str_list.append(f"- {contributer}")

disclaimer_text = "\n".join(str_list)
with st.expander("Disclaimer & Contributers"):
    st.markdown(disclaimer_text)
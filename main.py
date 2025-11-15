# This is a LLM chatbot that allows architects to develop a scope of work for AEC contracts.
# Each interaction with the chatbot refines the scope of work, ultimately producing a comprehensive
# list of deliverables,
# along with associated scope items for each deliverable.

import pandas as pd
import streamlit as st
from llm_calls import classify_and_get_context, run_llm_query

st.set_page_config(
    page_title="AEC Contract Assistant",
    page_icon="🤖",
    layout="wide",
)

# CSS to make the left column sticky
st.markdown("""
    <style>
        /* Make the parent container use relative positioning */
        .main .block-container {
            max-width: 100%;
        }
            
        /* Target the column wrapper and first column */
        div[data-testid="stHorizontalBlock"] {
            align-items: flex-start !important;
        }
        
        div[data-testid="stHorizontalBlock"] > div:first-child {
            position: sticky !important;
            top: 3.5rem;
            align-self: flex-start !important;
            z-index: 100;
        }
    </style>
""", unsafe_allow_html=True)

# Build the chat interface
scope_column, chat_column = st.columns([1, 3])

# The chat window allows the user to have a conversation with the AI assistant
# This conversation would generate a dictionary of deliverables, and associated lists of scope items

st.session_state.setdefault("messages", [])
st.session_state.setdefault("scope_of_work", {})

with chat_column:
    st.title("AEC Contract Assistant 🤖")
    st.write(
        "Welcome to the AEC Contract Assistant! This chatbot will help you develop a comprehensive scope of work for your architecture, engineering, and construction contracts. Start by describing your project and requirements."
    )

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Describe your project and requirements..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Here you would call your LLM to get a response based on the conversation
        # For demonstration purposes, we'll use a placeholder response
        # response = "Thank you for the details. Based on your input, here are some initial deliverables and scope items..."
        response = run_llm_query(system_prompt="", user_input=prompt)

        st.session_state.messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)
            
            
# The scope window displays the current scope of work being developed
# It shows a list of deliverables, each with associated scope items
with scope_column:
    # Container with fixed height and its own scrolling
    with st.container(height=700, border=True):
        st.subheader("Scope of Work")
        
        if st.session_state.scope_of_work:
            # For a simple dict:
            df = pd.DataFrame(list(st.session_state.scope_of_work.items()), 
                             columns=['Deliverable', 'Scope Items'])
            st.dataframe(df, use_container_width=True)
        else:
            st.write("No scope items yet")
            
            # Example of adding more content to demonstrate scrolling
            st.markdown("---")
            st.write("**Instructions:**")
            st.write("- Describe your project requirements")
            st.write("- The AI will help build your scope")
            st.write("- Items will appear here as you chat")
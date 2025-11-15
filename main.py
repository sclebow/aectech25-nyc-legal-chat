# This is a LLM chatbot that allows architects to develop a scope of work for AEC contracts.
# Each interaction with the chatbot refines the scope of work, ultimately producing a comprehensive
# list of deliverables,
# along with associated scope items for each deliverable.

import streamlit as st
from llm_calls import classify_and_get_context, run_llm_query

st.set_page_config(
    page_title="AEC Contract Assistant",
    page_icon="🤖",
    layout="wide",
)

# Build the chat interface
scope_column, chat_column = st.columns([1, 3])

# The chat window allows the user to have a conversation with the AI assistant
# This conversation would generate a dictionary of deliverables, and associated lists of scope items

st.session_state.setdefault("messages", [])
st.session_state.setdefault("scope_of_work", {})
st.session_state.setdefault("conversation_history", [])

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

        # Call LLM with conversation history for context
        response = classify_and_get_context(prompt)

        # Update conversation history with user message and assistant response
        st.session_state.conversation_history.append({"role": "user", "content": prompt})
        st.session_state.conversation_history.append({"role": "assistant", "content": response})

        st.session_state.messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)
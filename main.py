# This is a LLM chatbot that allows architects to develop a scope of work for AEC contracts.
# Each interaction with the chatbot refines the scope of work, ultimately producing a comprehensive
# list of deliverables,
# along with associated scope items for each deliverable.

import pandas as pd
import streamlit as st
from llm_calls import classify_and_get_context, update_categories_list
from scope_visualizer import display_scope_of_work
from ui_styles import apply_custom_styles

print("\n" * 5)
print("Starting AEC Contract Assistant...")

st.set_page_config(
    page_title="ContractCadence",
    page_icon="🤖",
    layout="wide",
)

# Apply custom CSS styling
apply_custom_styles()

# Build the chat interface
file_upload_column, scope_column, chat_column = st.columns([1, 3, 3])

# The chat window allows the user to have a conversation with the AI assistant
# This conversation would generate a dictionary of deliverables, and associated lists of scope items

DEFAULT_SCOPE_OF_WORK = {
    "Schematic Design": {
        "Architectural": [
            "Preliminary floor plans",
            "Exterior elevations",
            "Renderings",
        ],
        "Electrical": [
            "Narrative description of electrical systems",
        ],
        "Mechanical": [
            "Narrative description of mechanical systems",
        ],
    },
    "Design Development": {
        "Architectural": [
            "Refined floor plans",
            "Building sections",
            "Preliminary material selections",
        ],
        "Structural": [
            "Preliminary structural system design",
        ],
        "Electrical": [
            "Preliminary electrical plans",
        ],
        "Mechanical": [
            "Preliminary mechanical plans",
        ],
    },
    "Construction Documents": {
        "Architectural": [
            "Detailed floor plans",
            "Wall sections",
            "Door and window schedules",
            "Finish schedules",
        ],
        "Structural": [
            "Final structural drawings and specifications",
        ],
        "Electrical": [
            "Complete electrical plans and details",
        ],
        "Mechanical": [
            "Complete mechanical plans and details",
        ],
    },
    "Construction Administration": {
        "Architectural": [
            "Site visits",
            "Review of shop drawings",
            "Response to RFIs",
        ],
    },
}

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

st.session_state.setdefault("messages", [])
st.session_state.setdefault("scope_of_work", DEFAULT_SCOPE_OF_WORK)
st.session_state.setdefault("conversation_history", [])

update_categories_list()

with chat_column:
    message_container = st.container(height=550, border=True)

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
            
            
# The scope window displays the current scope of work being developed
# It shows a list of deliverables, each with associated scope items
with scope_column:
    st.subheader("ContractCadence 🤖")

    # Use DEFAULT_SCOPE_OF_WORK for testing
    scope_to_display = st.session_state.scope_of_work or DEFAULT_SCOPE_OF_WORK
    display_scope_of_work(scope_to_display)

    categories_list = st.session_state["categories_list"]
    categories_list_csv = pd.Series(categories_list).to_csv(index=False, header=False)
    # Add a download button for the categories list
    download_button = st.download_button(
        label="Download categories list as CSV",
        data=categories_list_csv,
        file_name="categories_list.csv",
        mime="text/csv",
    )

with file_upload_column:
    st.subheader("Upload Reference Documents 📄")
    uploaded_files = st.file_uploader(
        "Upload architectural plans, contracts, or other reference documents to assist the AI in understanding your project requirements.",
        accept_multiple_files=True,
        type=["pdf", "docx", "txt"],
    )
    if uploaded_files:
        st.markdown("**Uploaded Files:**")
        for uploaded_file in uploaded_files:
            st.markdown(f"- {uploaded_file.name}")
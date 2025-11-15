# This is a LLM chatbot that allows architects to develop a scope of work for AEC contracts.
# Each interaction with the chatbot refines the scope of work, ultimately producing a comprehensive
# list of deliverables,
# along with associated scope items for each deliverable.

import pandas as pd
import streamlit as st
from llm_calls import classify_and_get_context, run_llm_query

print("\n" * 5)
print("Starting AEC Contract Assistant...")

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
            margin-top: 10;
        }
    </style>
""", unsafe_allow_html=True)

# Build the chat interface
scope_column, chat_column = st.columns([2, 3])

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

st.session_state.setdefault("messages", [])
st.session_state.setdefault("scope_of_work", DEFAULT_SCOPE_OF_WORK)
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
            
            
# The scope window displays the current scope of work being developed
# It shows a list of deliverables, each with associated scope items
with scope_column:
    # Container with fixed height and its own scrolling
    with st.container(height=600, border=False):
        st.subheader("Scope of Work")
        
        # Use DEFAULT_SCOPE_OF_WORK for testing
        scope_to_display = st.session_state.scope_of_work or DEFAULT_SCOPE_OF_WORK
        
        if scope_to_display:
            # Flatten the nested dictionary structure
            rows = []
            for phase, disciplines in scope_to_display.items():
                for discipline, items in disciplines.items():
                    for item in items:
                        rows.append({
                            'Phase': phase,
                            'Discipline': discipline,
                            'Scope Item': item
                        })
            
            if rows:
                df = pd.DataFrame(rows)
                st.data_editor(df, use_container_width=True, hide_index=True)
            else:
                st.write("No scope items yet")
        else:
            st.write("No scope items yet")
            
            # Example of adding more content to demonstrate scrolling
            st.markdown("---")
            st.write("**Instructions:**")
            st.write("- Describe your project requirements")
            st.write("- The AI will help build your scope")
            st.write("- Items will appear here as you chat")
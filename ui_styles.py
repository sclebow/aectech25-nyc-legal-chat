"""
UI styling utilities for Streamlit application.
"""

import streamlit as st


def apply_custom_styles():
    """Apply custom CSS styling to the Streamlit app."""
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

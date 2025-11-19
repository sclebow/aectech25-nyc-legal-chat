"""
Utility functions for visualizing scope of work data in Streamlit.
"""

import pandas as pd
import streamlit as st


def get_color_palette():
    """Returns a predefined palette of visually distinct pastel colors."""
    return [
        (255, 179, 186),  # Light pink
        (255, 223, 186),  # Light peach
        (255, 255, 186),  # Light yellow
        (186, 255, 201),  # Light mint
        (186, 225, 255),  # Light blue
        (220, 198, 255),  # Light purple
        (255, 198, 255),  # Light magenta
        (255, 214, 165),  # Light orange
        (198, 255, 198),  # Light green
        (198, 226, 255),  # Light sky blue
        (255, 198, 214),  # Light rose
        (234, 209, 220),  # Light mauve
        (255, 204, 153),  # Light apricot
        (204, 255, 229),  # Light aqua
        (229, 204, 255),  # Light lavender
        (255, 229, 204),  # Light cream
    ]


def assign_colors_globally(unique_phases, unique_disciplines):
    """
    Assign colors globally to phases and disciplines, ensuring no color is reused.
    
    Args:
        unique_phases: Array of unique phase names
        unique_disciplines: Array of unique discipline names
        
    Returns:
        Tuple of (phase_color_map, discipline_color_map)
    """
    color_palette = get_color_palette()
    used_color_indices = set()
    phase_color_map = {}
    discipline_color_map = {}
    
    # Assign colors to phases first
    for phase in unique_phases:
        color_index = 0
        while color_index in used_color_indices and len(used_color_indices) < len(color_palette):
            color_index += 1
        used_color_indices.add(color_index)
        color = color_palette[color_index % len(color_palette)]
        phase_color_map[phase] = f"rgba({color[0]}, {color[1]}, {color[2]}, 0.3)"
    
    # Assign colors to disciplines, avoiding already used colors
    for discipline in unique_disciplines:
        color_index = 0
        while color_index in used_color_indices and len(used_color_indices) < len(color_palette):
            color_index += 1
        used_color_indices.add(color_index)
        color = color_palette[color_index % len(color_palette)]
        discipline_color_map[discipline] = f"rgba({color[0]}, {color[1]}, {color[2]}, 0.3)"
    
    return phase_color_map, discipline_color_map


def flatten_scope_to_dataframe(scope_of_work):
    """
    Flatten nested scope of work dictionary into a pandas DataFrame.
    
    Args:
        scope_of_work: Dictionary with structure {phase: {discipline: [items]}}
        
    Returns:
        pandas DataFrame with columns: Phase, Discipline, Scope Item
    """
    rows = []
    for phase, disciplines in scope_of_work.items():
        for discipline, items in disciplines.items():
            for item in items:
                rows.append({
                    'Phase': phase,
                    'Discipline': discipline,
                    'Scope Item': item
                })
    
    if rows:
        return pd.DataFrame(rows)
    return None


def display_scope_of_work(scope_of_work):
    """
    Display the scope of work as a styled dataframe with color-coded phases and disciplines.
    
    Args:
        scope_of_work: Dictionary with structure {phase: {discipline: [items]}}
    """
    st.markdown("##### Scope of Work")
    
    if not scope_of_work:
        st.write("No scope items yet")
        st.markdown("---")
        st.write("**Instructions:**")
        st.write("- Describe your project requirements")
        st.write("- The AI will help build your scope")
        st.write("- Items will appear here as you chat")
        return
    
    # Flatten the nested dictionary structure
    df = flatten_scope_to_dataframe(scope_of_work)
    
    if df is None or df.empty:
        st.write("No scope items yet")
        return
    
    # Get unique phases and disciplines
    unique_phases = df['Phase'].unique()
    unique_disciplines = df['Discipline'].unique()
    
    # Assign colors globally
    phase_color_map, discipline_color_map = assign_colors_globally(unique_phases, unique_disciplines)
    
    def get_color_for_value(value, color_map):
        return color_map.get(value, "rgba(255, 255, 255, 0.3)")
    
    # Style the dataframe
    def highlight_columns(row):
        phase_color = get_color_for_value(row['Phase'], phase_color_map)
        discipline_color = get_color_for_value(row['Discipline'], discipline_color_map)
        return [
            f'background-color: {phase_color}',
            f'background-color: {discipline_color}',
            ''
        ]
    
    styled_df = df.style.apply(highlight_columns, axis=1)
    num_rows = len(df)
    height = min(550, 35 * num_rows + 40)  # Dynamic height based on number of rows
    edited_df = st.data_editor(styled_df, width='stretch', hide_index=True, height=height)

    edited_dict = edited_df.to_dict(orient='records')
    # Convert back to nested dictionary
    new_scope_of_work = {}
    for entry in edited_dict:
        phase = entry['Phase']
        discipline = entry['Discipline']
        item = entry['Scope Item']
        if phase not in new_scope_of_work:
            new_scope_of_work[phase] = {}
        if discipline not in new_scope_of_work[phase]:
            new_scope_of_work[phase][discipline] = []
        new_scope_of_work[phase][discipline].append(item)

    # Update the original scope_of_work dictionary
    st.session_state["scope_of_work"] = new_scope_of_work

    return height
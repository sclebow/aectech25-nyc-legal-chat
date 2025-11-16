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
    st.subheader("Scope of Work")
    
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
    st.dataframe(styled_df, use_container_width=True, hide_index=True)


def rgba_to_rgb(rgba_string, lighten=True):
    """
    Convert rgba color string to rgb hex format, optionally lightening it.
    
    Args:
        rgba_string: String like "rgba(255, 179, 186, 0.3)"
        lighten: If True, blend the color with white to make it lighter
        
    Returns:
        Hex color string like "#ffb3ba"
    """
    # Extract RGB values from rgba string
    import re
    match = re.match(r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*[\d.]+\)', rgba_string)
    if match:
        r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
        
        # If lightening, blend with white (255, 255, 255) at 70% white / 30% color
        # This makes colors much lighter while keeping them distinct
        if lighten:
            r = int(r * 0.2 + 255 * 0.8)
            g = int(g * 0.2 + 255 * 0.8)
            b = int(b * 0.2 + 255 * 0.8)
        
        return f"#{r:02x}{g:02x}{b:02x}"
    return "#ffffff"


def scope_to_markdown(scope_of_work, phase_color_map=None, discipline_color_map=None):
    """
    Convert scope of work dictionary to markdown format with color highlighting.
    
    Args:
        scope_of_work: Dictionary with structure {phase: {discipline: [items]}}
        phase_color_map: Optional dictionary mapping phases to rgba colors
        discipline_color_map: Optional dictionary mapping disciplines to rgba colors
        
    Returns:
        String containing markdown formatted scope of work with HTML styling
    """
    if not scope_of_work:
        return "No scope items yet."
    
    markdown_lines = []
    
    for phase, disciplines in scope_of_work.items():
        # Apply phase color if available
        if phase_color_map and phase in phase_color_map:
            color = rgba_to_rgb(phase_color_map[phase])
            markdown_lines.append(f'<h3 style="background-color: {color}; padding: 8px; border-radius: 4px; font-weight: bold;"><strong>{phase}</strong></h3>\n')
        else:
            markdown_lines.append(f"### {phase}\n")
        
        for discipline, items in disciplines.items():
            # Apply discipline color if available
            if discipline_color_map and discipline in discipline_color_map:
                color = rgba_to_rgb(discipline_color_map[discipline])
                markdown_lines.append(f'<h4 style="background-color: {color}; padding: 6px; border-radius: 4px; font-weight: bold;"><strong>{discipline}</strong></h4>\n')
            else:
                markdown_lines.append(f"#### {discipline}\n")
            
            for item in items:
                markdown_lines.append(f"- {item}")
            
            markdown_lines.append("")  # Empty line after each discipline
        
        markdown_lines.append("")  # Empty line after each phase
    
    return "\n".join(markdown_lines)


def display_scope_as_markdown(scope_of_work):
    """
    Display the scope of work in markdown format with color-coded phases and disciplines.
    
    Args:
        scope_of_work: Dictionary with structure {phase: {discipline: [items]}}
    """
    if not scope_of_work:
        st.write("No scope items yet")
        return
    
    # Get unique phases and disciplines for color assignment
    unique_phases = list(scope_of_work.keys())
    unique_disciplines = list(set(
        discipline 
        for disciplines in scope_of_work.values() 
        for discipline in disciplines.keys()
    ))
    
    # Assign colors globally
    phase_color_map, discipline_color_map = assign_colors_globally(unique_phases, unique_disciplines)
    
    # Generate and display markdown with colors
    markdown_text = scope_to_markdown(scope_of_work, phase_color_map, discipline_color_map)
    st.markdown(markdown_text, unsafe_allow_html=True)
    

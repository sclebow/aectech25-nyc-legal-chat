# This is a utility module for handling RSMeans csv data.
# It includes functions to read, filter, and process the data for use in cost estimation tasks.

import pandas as pd
import server.config as config
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

# For reference, the following are the columns in the RSMeans DataFrame:
# ['Masterformat Section Code', 'Section Name', 'ID', 'Name', 'Crew', 'Daily Output', 'Labor-Hours','Unit', 'Material', 'Labor', 'Equipment', 'Total', 'Total Incl O&P']
# Generally we use Total Incl O&P for cost estimation

# We want the user to be able to find the cost data by searching for a masterformat section code or description of the work
# We can use LLM calls to find the best match for a given description

RSMEANS_CSV_DIR = "cost_data/rsmeans/"

# def load_rsmeans_data(csv_path=None):
#     """
#     Load RSMeans CSV data into a pandas DataFrame.
#     If csv_path is None, use the default from config.
#     """
#     if csv_path is None:
#         csv_path = RSMEANS_CSV_PATH
#     return pd.read_csv(csv_path)


def list_chapter_csvs():
    """
    List all available RSMeans chapter CSVs and their chapter names.
    Returns a list of (filename, chapter_name) tuples.
    """
    csvs = []
    for fname in os.listdir(RSMEANS_CSV_DIR):
        if fname.endswith(".csv"):
            # Chapter name is the part before the first underscore or the number prefix
            chapter = fname.split("_")[0]
            csvs.append((fname, chapter))
    return csvs


def find_by_section_code(df, section_code):
    """
    Filter the DataFrame by Masterformat Section Code (exact match or fuzzy match).
    Fuzzy match: if no exact match, return rows where the code starts with or contains the input (ignoring whitespace/case).
    Handles NaN values in the code column.
    """
    # Exact match first
    match = df[df['Masterformat Section Code'] == section_code]
    if not match.empty:
        return match
    # Fuzzy match: ignore case/whitespace, allow startswith or contains
    code_norm = section_code.replace(' ', '').lower()
    code_series = df['Masterformat Section Code'].fillna('').str.replace(' ', '').str.lower()
    fuzzy = df[code_series.str.startswith(code_norm)]
    if not fuzzy.empty:
        return fuzzy
    fuzzy_contains = df[code_series.str.contains(code_norm)]
    return fuzzy_contains

def get_rsmeans_context_from_prompt(prompt, max_tokens=1500):
    """
    Use an LLM to extract relevant materials from a prompt.
    The materials will be used to extract data from the RSMeans CSV files.
    """
    from llm_calls import run_llm_query  # Import here to avoid circular dependency
    system_prompt = (
        "You are an expert at extracting relevant materials from construction task descriptions. "
        "Given a user's description, extract the most relevant materials that can be used to look up costs in RSMeans data. "
        "Be descriptive and include all materials that might be relevant. "
        "Return your answer as a comma-separated list of materials."
        "Provide only the comma-separated list of materials, no other text and no explanations. "
        "Example: 'concrete, steel, wood, insulation, drywall'. "
    )
    user_input = f"Description: {prompt}"
    materials = run_llm_query(system_prompt, user_input, max_tokens=max_tokens)
    # print(f'materials output: {materials}')
    # Clean up the materials string
    materials = materials.split("\n")[-1].strip()  # Get the last line in case of multiple lines
    materials = [m.strip() for m in materials.split(",") if m.strip()]
    # print(f"{materials}")

    rsmeans_strings = [] # List to hold the RSMeans strings for each material
    for material in materials:
        # For each material, we will search the RSMeans data
        # We will use the find_by_description function to get the relevant section codes
        # and then format them into a string for the LLM
        section_df = find_by_description(material)
        if not section_df.empty:
            # Create a string representation of the section codes and names
            section_codes = section_df['Masterformat Section Code'].unique()
            section_names = section_df['Section Name'].unique()
            rsmeans_strings.append(f"{material}: {', '.join(section_codes)} ({', '.join(section_names)})")
        else:
            rsmeans_strings.append(f"{material}: No relevant sections found")
    # Join all the RSMeans strings into a single string
    rsmeans_context = "\n".join(rsmeans_strings)
    return rsmeans_context

def find_by_description(description, section_confidence_threshold=0.6, row_confidence_threshold=0.6):
    """
    Use LLM to select the most appropriate Masterformat CHAPTERS first, then section codes from those chapters.
    For each relevant chapter, send a separate LLM call for section selection.
    Only loads the relevant chapter CSVs for section selection.
    Instead of sending Masterformat codes to the LLM, send only the section descriptions (Section Name).
    """
    from llm_calls import run_llm_query  # Import here to avoid circular dependency
    import pandas as pd

    # 1. List all chapters
    chapter_csvs = list_chapter_csvs()
    chapter_list = [f"{chapter}: {fname}" for fname, chapter in chapter_csvs]
    print(f"Found {len(chapter_list)} Masterformat chapters.")

    # 2. Ask LLM which chapter(s) are relevant
    system_prompt = (
        "You are an expert at mapping construction task descriptions to Masterformat chapters. "
        "Given a list of Masterformat chapters, select all relevant chapters for a user's description. "
        "Consider exact matches first, then partial matches based on the description. "
        "Return your answer as a comma-separated list of chapter numbers (e.g. 03, 04, 10, etc)."
        "Return only the chapter numbers, no other text. "
    )
    user_input = (
        f"Masterformat chapters list:\n{chr(10).join(chapter_list)}\n"
        f"Description: {description}"
    )
    selected_chapters_str = run_llm_query(system_prompt, user_input)
    selected_chapters = [c.strip() for c in selected_chapters_str.split(",") if c.strip()]
    print(f"Selected chapters: {', '.join(selected_chapters)}")

    # 3. For each relevant chapter, send a separate LLM call for section selection (using only descriptions)
    import re
    code_confidence = {}
    dfs = []
    for fname, chapter in chapter_csvs:
        if str(chapter) in str(selected_chapters):
            print(f"Processing chapter {chapter} from file {fname}")
            df = pd.read_csv(os.path.join(RSMEANS_CSV_DIR, fname))
            dfs.append(df)
            unique_sections = df[['Masterformat Section Code', 'Section Name']].drop_duplicates().reset_index(drop=True)
            # Only send the section descriptions (Section Name) to the LLM
            section_names = unique_sections['Section Name'].tolist()
            # LLM call for this chapter's section descriptions
            system_prompt = (
                "You are an expert at mapping construction task descriptions to Masterformat section names. "
                "Given a list of Masterformat section names, you will select all relevant names for a user's description. "
                "Return your answer as a comma-separated list of section names with a confidence percentage (0-100) for each, in the format: name1:confidence1, name2:confidence2, ... "
                "Return only the section names and confidence percentages, no other text. "
            )
            user_input = (
                f"Masterformat section names list:\n{chr(10).join(section_names)}\n"
                f"Description: {description}"
            )
            selected_names_str = run_llm_query(system_prompt, user_input)
            print(f"Selected section names for chapter {chapter}: {selected_names_str}")
            for part in selected_names_str.split(','):
                match = re.match(r"(.+?):\s*(\d{1,3})", part.strip())
                if match:
                    name = match.group(1).strip()
                    confidence = int(match.group(2)) / 100.0
                    # Map section name back to code(s) in this chapter
                    codes = unique_sections[unique_sections['Section Name'] == name]['Masterformat Section Code'].tolist()
                    for code in codes:
                        if code in code_confidence:
                            code_confidence[code] = max(code_confidence[code], confidence)
                        else:
                            code_confidence[code] = confidence
    if not dfs:
        # fallback: load all
        dfs = [pd.read_csv(os.path.join(RSMEANS_CSV_DIR, fname)) for fname, _ in chapter_csvs]
    df = pd.concat(dfs, ignore_index=True)
    # Filter by confidence threshold
    filtered_codes = [code for code, conf in code_confidence.items() if conf >= section_confidence_threshold]
    match = df[df['Masterformat Section Code'].isin(filtered_codes)]
    if not match.empty:
        match = match.copy()
    output_df = None
    if not match.empty:
        match.loc[:, 'Confidence'] = match['Masterformat Section Code'].map(code_confidence)
        match = match[match['Confidence'] >= section_confidence_threshold]
        match = match.sort_values(by='Confidence', ascending=False)
        match = match.reset_index(drop=True)
        # Print the matched codes and their confidence levels
        print("Matched section codes with confidence levels:")
        for code, conf in code_confidence.items():
            if conf >= section_confidence_threshold:
                print(f"{code}: {conf:.2f}")
        print(f"Found {len(match)} exact matches for section codes above threshold: {', '.join(str(code) for code in filtered_codes)}")
        output_df = match
    
    if output_df is None:
        # Fuzzy match: try to find section names that contain the description (case-insensitive)
        desc_norm = description.strip().lower()
        fuzzy = df[df['Section Name'].str.lower().str.contains(desc_norm)]
        if not fuzzy.empty:
            print(f"Found {len(fuzzy)} fuzzy matches: {', '.join(fuzzy['Section Name'].unique())}")
            output_df = fuzzy
    if output_df is None:
        # Also try fuzzy match on Masterformat Section Code (in case user enters a partial code as description)
        code_fuzzy = df[df['Masterformat Section Code'].fillna('').str.replace(' ', '').str.lower().str.contains(desc_norm.replace(' ', ''))]
        print(f"Found {len(code_fuzzy)} fuzzy matches for section codes: {', '.join(code_fuzzy['Masterformat Section Code'].unique())}")
        output_df = code_fuzzy

    # return output_df

    # --- New LLM pass for further filtering by Name and Section Name ---
    if output_df is not None and not output_df.empty:
        from llm_calls import run_llm_query
        # Prepare a list of combined Name and Section Name values
        combined_list = [
            f"Section: {row['Section Name']}, Name: {row['Name']}" for _, row in output_df.iterrows()
        ]
        system_prompt = (
            "You are an expert at mapping construction task descriptions to specific RSMeans line items. "
            "Given a list of line items (with both Name and Section Name), select all that are most relevant for a user's description. "
            "Return your answer as a ||-separated list of the exact 'Name' values (not Section Name) with a confidence percentage (0-100) for each, in the format: Name1::confidence1||Name2::confidence2||... "
            "Return only the names and confidence percentages, no other text. "
        )
        user_input = (
            f"Line items list:\n{chr(10).join(combined_list)}\n"
            f"Description: {description}"
        )
        selected_names_str = run_llm_query(system_prompt, user_input)
        print(f"Selected names from LLM: {selected_names_str}")
        # Parse names and confidences
        name_conf_pairs = [n.strip() for n in selected_names_str.split("||") if n.strip()]
        selected_names = []
        for pair in name_conf_pairs:
            match = re.match(r"(.+?)::\s*(\d{1,3})", pair)
            if match:
                name = match.group(1).strip()
                confidence = int(match.group(2)) / 100.0
                if confidence >= row_confidence_threshold:
                    selected_names.append(name)
        filtered_df = output_df[output_df['Name'].isin(selected_names)]
        if not filtered_df.empty:
            print(f"Further filtered to {len(filtered_df)} line items by LLM pass on Name/Section Name with confidence threshold {row_confidence_threshold}.")
            output_df = filtered_df
        else:
            print("No further matches found in LLM Name/Section filter, returning previous output.")
            
    # Remove the 'Confidence' column if it exists
    if 'Confidence' in output_df.columns:
        output_df = output_df.drop(columns=['Confidence'])
    return output_df

def get_cost_data(section_code_or_desc):
    """
    Retrieve cost data for a given section code or description.
    """
    # Try to interpret as a section code (search all chapters)
    chapter_csvs = list_chapter_csvs()
    import pandas as pd
    dfs = [pd.read_csv(os.path.join(RSMEANS_CSV_DIR, fname)) for fname, _ in chapter_csvs]
    df = pd.concat(dfs, ignore_index=True)
    match = find_by_section_code(df, section_code_or_desc)
    if not match.empty:
        return match
    # Otherwise, try description match (which will select chapters)
    return find_by_description(section_code_or_desc)


def list_sections():
    """
    List all available Masterformat section codes and names from all chapter CSVs.
    """
    import os
    import pandas as pd
    RSMEANS_CSV_DIR = "cost_data/rsmeans/"
    csvs = [f for f in os.listdir(RSMEANS_CSV_DIR) if f.endswith(".csv")]
    dfs = [pd.read_csv(os.path.join(RSMEANS_CSV_DIR, f)) for f in csvs]
    df = pd.concat(dfs, ignore_index=True)
    return df[['Masterformat Section Code', 'Section Name']].drop_duplicates().reset_index(drop=True)


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


def find_by_description(description, section_chunk_size=500, confidence_threshold=0.5):
    """
    Use LLM to select the most appropriate Masterformat CHAPTERS first, then section codes from those chapters.
    Only loads the relevant chapter CSVs for section selection.
    """
    from llm_calls import run_llm_query  # Import here to avoid circular dependency
    import pandas as pd

    # 1. List all chapters
    chapter_csvs = list_chapter_csvs()
    chapter_list = [f"{chapter}: {fname}" for fname, chapter in chapter_csvs]

    # 2. Ask LLM which chapter(s) are relevant
    system_prompt = (
        "You are an expert at mapping construction task descriptions to Masterformat chapters. "
        "Given a list of Masterformat chapters, select all relevant chapters for a user's description. "
        "Return your answer as a comma-separated list of chapter numbers (e.g. 03, 04, 10, etc)."
    )
    user_input = (
        f"Masterformat chapters list:\n{chr(10).join(chapter_list)}\n"
        f"Description: {description}"
    )
    selected_chapters_str = run_llm_query(system_prompt, user_input)
    selected_chapters = [c.strip() for c in selected_chapters_str.split(",") if c.strip()]

    # 3. Load only the relevant chapter CSVs
    dfs = []
    for fname, chapter in chapter_csvs:
        if chapter in selected_chapters:
            df = pd.read_csv(os.path.join(RSMEANS_CSV_DIR, fname))
            dfs.append(df)
    if not dfs:
        # fallback: load all
        dfs = [pd.read_csv(os.path.join(RSMEANS_CSV_DIR, fname)) for fname, _ in chapter_csvs]
    df = pd.concat(dfs, ignore_index=True)

    # 4. Build section list and proceed as before
    unique_sections = df[['Masterformat Section Code', 'Section Name']].drop_duplicates().reset_index(drop=True)
    section_list = unique_sections.apply(lambda row: f"{row['Masterformat Section Code']}: {row['Section Name']}", axis=1).tolist()
    # Chunk the section list if it's too long, the chunks should overlap to ensure no sections are missed
    if len(section_list) > section_chunk_size:
        chunked_sections = []
        for i in range(0, len(section_list), section_chunk_size):
            start = max(0, i - section_chunk_size // 2)
            chunk = section_list[start:i + section_chunk_size]
            chunked_sections.append(chunk)
    else:
        chunked_sections = [section_list]

    def llm_chunk_query(chunk):
        system_prompt = (
            "You are an expert at mapping construction task descriptions to Masterformat section codes. "
            "First, simplify the description to its core elements, "
            "then select the most relevant Masterformat section codes from the provided list. "
            "Given a list of Masterformat sections, you will select all relevant codes for a user's description. "
            "Return your answer as a comma-separated list of section codes with a confidence percentage (0-100) for each, in the format: code1:confidence1, code2:confidence2, ... "
        )
        user_input = (
            f"Masterformat sections list:\n{chr(10).join(chunk)}\n"
            f"Description: {description}"
        )
        return run_llm_query(system_prompt, user_input)

    import re
    code_confidence = {}
    with ThreadPoolExecutor() as executor:
        future_to_chunk = {executor.submit(llm_chunk_query, chunk): chunk for chunk in chunked_sections}
        for future in as_completed(future_to_chunk):
            selected_codes_str = future.result()
            # Parse LLM response: expect format like "03 30 00:90, 04 20 00:60"
            for part in selected_codes_str.split(','):
                match = re.match(r"([\w .-]+):\s*(\d{1,3})", part.strip())
                if match:
                    code = match.group(1).strip()
                    confidence = int(match.group(2)) / 100.0
                    if code in code_confidence:
                        code_confidence[code] = max(code_confidence[code], confidence)
                    else:
                        code_confidence[code] = confidence
    # Filter by confidence threshold
    filtered_codes = [code for code, conf in code_confidence.items() if conf >= confidence_threshold]
    match = df[df['Masterformat Section Code'].isin(filtered_codes)]
    if not match.empty:
        # Print the matched section codes and their confidence levels
        match['Confidence'] = match['Masterformat Section Code'].map(code_confidence)
        match = match[match['Confidence'] >= confidence_threshold]
        match = match.sort_values(by='Confidence', ascending=False)
        match = match.reset_index(drop=True)
        # Print the matched codes and their confidence levels
        print("Matched section codes with confidence levels:")
        for code, conf in code_confidence.items():
            if conf >= confidence_threshold:
                print(f"{code}: {conf:.2f}")
        print(f"Found {len(match)} exact matches for section codes above threshold: {', '.join(filtered_codes)}")
        return match
    # Fuzzy match: try to find section names that contain the description (case-insensitive)
    desc_norm = description.strip().lower()
    fuzzy = df[df['Section Name'].str.lower().str.contains(desc_norm)]
    if not fuzzy.empty:
        print(f"Found {len(fuzzy)} fuzzy matches: {', '.join(fuzzy['Section Name'].unique())}")
        return fuzzy
    # Also try fuzzy match on Masterformat Section Code (in case user enters a partial code as description)
    code_fuzzy = df[df['Masterformat Section Code'].fillna('').str.replace(' ', '').str.lower().str.contains(desc_norm.replace(' ', ''))]
    print(f"Found {len(code_fuzzy)} fuzzy matches for section codes: {', '.join(code_fuzzy['Masterformat Section Code'].unique())}")
    return code_fuzzy


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


def list_sections(df):
    """
    List all available Masterformat section codes and names.
    """
    return df[['Masterformat Section Code', 'Section Name']].drop_duplicates().reset_index(drop=True)


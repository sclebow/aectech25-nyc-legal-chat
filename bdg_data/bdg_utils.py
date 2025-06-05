# This is a utility module for handling BDG (Building Data Generator) Export files.

import os
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    import cost_data.rsmeans_utils as rsmeans_utils
except ImportError:
    # Move the path directory to the parent directory
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import cost_data.rsmeans_utils as rsmeans_utils

material_export_csv_filename = "material_data_export.csv"
material_export_csv_filepath = os.path.join("bdg_data", material_export_csv_filename)

bdg_cost_database_filename = "BDG_Cost database_v04.xlsx"
bdg_cost_database_filepath = os.path.join("bdg_data", bdg_cost_database_filename)

cost_data_from_rsmeans_csv_filename = "cost_data_from_rsmeans.csv"
cost_data_from_rsmeans_csv_filepath = os.path.join("bdg_data", cost_data_from_rsmeans_csv_filename)

def read_material_export_csv():
    """
    Reads the material export CSV file and returns a DataFrame.
    If the file does not exist, it returns None.
    """
    if os.path.exists(material_export_csv_filepath):
        df = pd.read_csv(material_export_csv_filepath, header=0)
    else:
        print(f"File {material_export_csv_filepath} does not exist.")
        return None
    
    # Get the last row of the DataFrame (excluding the first column)
    last_row = df.iloc[-1, 1:]
    # Convert to DataFrame with two columns: index and value
    df = pd.DataFrame({
        "Source Qty": last_row.index,
        "Value": last_row.values
    })

    return df
    
def read_bdg_cost_database():
    """
    Reads the BDG cost database Excel file and returns a DataFrame.
    If the file does not exist, it returns None.
    """
    if os.path.exists(bdg_cost_database_filepath):
        df = pd.read_excel(bdg_cost_database_filepath)
    else:
        print(f"File {bdg_cost_database_filepath} does not exist.")
        return None
    
    # Filter to just columns: 'Code, 5', 'Description', 'Unit', 'Source Qty'
    df = df[['Code, 5', 'Description', 'Unit', 'Source Qty']]

    df.dropna(subset=['Code, 5', 'Description', 'Unit', 'Source Qty'], inplace=True)
    df.reset_index(drop=True, inplace=True)

    def extract_code(val):
        numbers = val.split('.')
        num_strs = [num.strip() for num in numbers if num.strip().isdigit()]
        return str(' '.join(num_strs[0:3]) if num_strs else val.strip())
    
    df['Code, 5'] = df['Code, 5'].apply(extract_code)
    # print(df.head())  # Display the first few rows of the DataFrame for verification

    return df

def build_rsmeans_cost_data():
    """
    Builds the RSMeans cost data by reading the bdg_cost_database and using the rsmeans_utils module.
    It saves the resulting DataFrame to a CSV file and returns the DataFrame.
    Now uses parallel processing for faster cost lookup.
    """
    bdg_df = read_bdg_cost_database()
    unique_descriptions = bdg_df['Description'].unique()
    total_costs = {}

    def get_cost(description):
        print(f"\n\n\nFinding cost for description: {description}\n\n\n")
        cost_data = rsmeans_utils.find_by_description(description)
        print(f"Cost dataframe")
        print(cost_data)
        if cost_data.empty:
            print(f"No cost data found for description: {description}")
            return (description, "No cost data found")
        cost_data['Total Incl O&P'] = pd.to_numeric(cost_data['Total Incl O&P'], errors='coerce')
        # Drop rows with NaN values in 'Total Incl O&P'
        cost_data.dropna(subset=['Total Incl O&P'], inplace=True)
        total_cost = cost_data['Total Incl O&P'].median()
        return (description, total_cost)

    # Use ThreadPoolExecutor for parallel processing with progress reporting
    total = len(unique_descriptions)
    processed = 0
    print(f"Starting RSMeans cost lookup for {total} descriptions...")
    with ThreadPoolExecutor() as executor:
        future_to_desc = {executor.submit(get_cost, desc): desc for desc in unique_descriptions}
        for future in as_completed(future_to_desc):
            desc, total_cost = future.result()
            total_costs[desc] = total_cost
            processed += 1
            print(f"Processed {processed}/{total} descriptions ({processed/total:.1%})")

    # Create a DataFrame from the total costs
    rsmeans_df = pd.DataFrame(list(total_costs.items()), columns=['Description', 'Total Cost'])
    # Save the DataFrame to a CSV file
    rsmeans_df.to_csv(cost_data_from_rsmeans_csv_filepath, index=False)
    return rsmeans_df

def get_project_data_context_from_query(message) -> str:
    """
    Retrieves project data context by reading the material export CSV and BDG cost database,
    merging them on 'Source Qty', and returning a string representation of the DataFrame.
    If either file is missing, it returns an error message.
    Use an LLM call to filter the data based on the message.
    If the cost data from RSMeans CSV does not exist, it builds it.
    """
    from llm_calls import run_llm_query

    material_df = read_material_export_csv()
    bdg_df = read_bdg_cost_database()

    if material_df is None or bdg_df is None:
        output = ""
        if material_df is None:
            output += "Material export CSV file is missing.\n"
        if bdg_df is None:
            output += "BDG cost database Excel file is missing.\n"
        return output

    # Add a new columns from bdg_df to material_df, matching on 'Source Qty'
    material_df = material_df.merge(bdg_df, on='Source Qty', how='left')
    material_df.rename(columns={'Code, 5': 'Code', 'Description': 'Description', 'Unit': 'Unit'}, inplace=True)

    # Check if the cost_data_from_rsmeans_csv exists
    if os.path.exists(cost_data_from_rsmeans_csv_filepath):
        # Read the cost data from RSMeans CSV
        rsmeans_df = pd.read_csv(cost_data_from_rsmeans_csv_filepath, header=0)
    else:
        # If the cost data from RSMeans CSV does not exist, we need to create it
        print(f"Cost data from RSMeans CSV file {cost_data_from_rsmeans_csv_filepath} does not exist. Building it now.")
        rsmeans_df = build_rsmeans_cost_data()

    # Merge the material_df with rsmeans_df on 'Description'
    material_df = material_df.merge(rsmeans_df, on='Description', how='left')

    # Drop rows where 'Value' is NaN or 'Value' is 0
    material_df.dropna(subset=['Value'], inplace=True)
    material_df = material_df[material_df['Value'] != 0]

    # Ensure Description column is string type
    material_df['Description'] = material_df['Description'].astype(str)

    # Get the unique descriptions from the material_df
    unique_descriptions = material_df['Description'].unique()

    # Ask the LLM to filter the data based on the message
    system_prompt = (
        "You are an expert at mapping construction task descriptions to specific descriptiions in a table. "
        "Given a list of line items (with both Name and Section Name), select all that are most relevant for a user's description. "
        "Return your answer as a ||-separated list of the exact 'Name' values (not Section Name) with a confidence percentage (0-100) for each, in the format: Name1::confidence1||Name2::confidence2||... "
        "Return only the names and confidence percentages, no other text. "
        f"Here are the descriptions: {', '.join(unique_descriptions)}"
    )
    user_prompt = (
        f"Please filter the following descriptions based on the user's message: {message}. "
        "Return only the most relevant descriptions."
    )
    response = run_llm_query(system_prompt, user_prompt)
    confidence_threshold = 0.5  # Set a confidence threshold for filtering
    filtered_descriptions = []
    for item in response.split('||'):
        if '::' in item:
            name, confidence = item.split('::')
            confidence = float(confidence)
            if confidence >= confidence_threshold:
                filtered_descriptions.append(name.strip())

    # Filter the material_df to only include rows with descriptions in the filtered_descriptions
    material_df = material_df[material_df['Description'].isin(filtered_descriptions)]

    # Print the headers for debugging
    print("Headers of the final DataFrame:")
    print(material_df.columns.tolist())

    # Add a new column 'Total Cost Amount', that is the product of 'Value' and 'Total Cost'
    if 'Total Cost' in material_df.columns:
        material_df['Total Cost Amount'] = material_df['Value'] * material_df['Total Cost']
        # Rename 'Total Cost' to 'Cost (per Unit)'
        material_df.rename(columns={'Total Cost': 'Cost (per Unit)'}, inplace=True)

    # Write the final DataFrame as a description string
    output_strings = []
    for index, row in material_df.iterrows():
        output_strings.append(
            f"Description: {row['Description']}, "
            f"Total Amount: {row['Value']}, "
            f"Amount Unit: {row['Unit']},"
            f"Cost (per Unit): {row['Total Cost'] if 'Total Cost' in row else 'N/A'}",
            f"Total Cost Amount: {row['Total Cost Amount'] if 'Total Cost Amount' in row else 'N/A'}"
        )

    output = "\n".join(output_strings)
    return output

# if __name__ == "__main__":
#     output = get_project_data_context_from_query()
#     print(output)

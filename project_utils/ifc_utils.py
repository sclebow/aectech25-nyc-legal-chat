import os
import ifcopenshell
# import ifcopenshell.util
# import ifcopenshell.util.shape
# import ifcopenshell.util.element
# import ifcopenshell.geom
# import multiprocessing
import logging
import threading
import inspect

# Global variables for IFC data
# These are used to cache IFC-related data across function calls

element_data_df = None
total_costs_per_name = None
total_costs_per_level = None
total_costs_sum = None
total_work_hours_sum = None

# Lets get the total wall volume from the geometry itself

# Load IFC file
ifc_directory = os.path.join(os.getcwd(), "ifc_files")
files = [os.path.join(ifc_directory, f) for f in os.listdir(ifc_directory) if f.endswith('.ifc')]
if files:
    latest_file = max(files, key=os.path.getmtime)
    print("Most recently modified file:", latest_file)
else:
    print("No files found.")

ifc = ifcopenshell.open(latest_file)

def get_ifc_context_from_query(query, request_id):
    global element_data_df, total_costs_per_name, total_costs_per_level, total_costs_sum, total_work_hours_sum
    """
    Use an LLM call to determine the IFC context from a query.
    """
    from llm_calls import run_llm_query
    import ifc_processing.ifc_processing as ifc_processing

    if element_data_df is None or total_costs_per_name is None or total_costs_per_level is None or total_costs_sum is None or total_work_hours_sum is None:
        # If the data is not already loaded, load it from the IFC file
        print("Loading IFC data...")
        # Load the data from the IFC file
        element_data_df, total_costs_per_name, total_costs_per_level, total_costs_sum, total_work_hours_sum = ifc_processing.process_ifc_file(ifc)

    system_prompt = f"""
        Provide context from a preprocessed IFC file based on the following query.:
        {query}
        There are a variety of preprocessed Data Sources available:
        - element_data_df: A DataFrame containing element data from the IFC file, including IFC type, name, cost, and work hours, and geometry.
        - total_costs_per_name: A dictionary containing total dollar and hourly costs per element name.
        - total_costs_per_level: A dictionary containing total dollar and hourly costs per level.
        - total_costs_sum: The total dollar costs for the entire IFC file.
        - total_work_hours_sum: The total work hours for the entire IFC file.

        Request the relevant IFC context sources from the query.
        The response should be a comma-separated list of the relevant IFC context sources.
        If no relevant context is found, return an empty string.
    """
    
    thread_id = threading.get_ident()
    parent_thread_id = getattr(threading.current_thread(), '_parent_ident', None)
    caller = inspect.stack()[1].function
    thread_id_str = str(thread_id)
    parent_thread_str = str(parent_thread_id) if parent_thread_id else "main"
    log_prefix = f"[id={request_id}] [thread={thread_id_str}] [parent={parent_thread_str}] [function=get_ifc_context_from_query] [called_by={caller}]"
    logging.info(f"{log_prefix} [description=Determine relevant IFC context from query]")

    # Run the LLM query to get the relevant IFC context sources
    context_sources_string = run_llm_query(system_prompt, query, max_tokens=1500)
    logging.info(f"{log_prefix} [context_sources_string={context_sources_string}]")

    # Extract the relevant context sources from the LLM response
    context_sources = [source.strip() for source in context_sources_string.split(',') if source.strip()]
    logging.info(f"{log_prefix} [context_sources={context_sources}]")

    ifc_context_output_strings = []

    filtered_df_string = ""  # Ensure this variable is always defined

    # If the element_data_df is requested, make another LLM call to get the names, types and columns to filter and return 
    if 'element_data_df' in context_sources:
        unique_names = element_data_df['name'].unique().tolist()
        unique_types = element_data_df['type'].unique().tolist()
        columns = element_data_df.columns.tolist()
        
        system_prompt = f"""
            The element_data_df DataFrame contains the following columns: {columns}.
            The unique names in the DataFrame are: {unique_names}.
            The unique types in the DataFrame are: {unique_types}.

            Based on the query, return three lists:
            1. A list of names to filter the DataFrame by.
            2. A list of types to filter the DataFrame by.
            3. A list of columns to return from the DataFrame.
            
            If no names or types are specified, return an empty list for those.
            If no columns are specified, return an empty list for that.

            Example response format:
            ```json
            {{                "names": ["Wall", "Door"],
                "types": ["IfcWall", "IfcDoor"],
                "columns": ["name", "type", "cost", "work_hours"]
            }}
            ```
        """  

        # Run the LLM query to get the names, types, and columns to filter and return
        filter_response = run_llm_query(system_prompt, query, max_tokens=1500)
        logging.info(f"{log_prefix} [filter_response={filter_response}]")

        import json
        try:
            filter_data = json.loads(filter_response)

            try:
                names = filter_data.get('names', [])
            except:
               names = []
            try:
                types = filter_data.get('types', [])
            except:
               types = []
            try:
                columns = filter_data.get('columns', [])
            except:
               columns = []
            logging.info(f"{log_prefix} [names={names}, types={types}, columns={columns}]")

            # Filter the DataFrame based on the names and types
            filtered_df = element_data_df.copy()
            if names:
                filtered_df = filtered_df[filtered_df['name'].isin(names)]
            if types:
                filtered_df = filtered_df[filtered_df['type'].isin(types)]
            if columns:
                filtered_df = filtered_df[columns]
            else:
                filtered_df = filtered_df[['name', 'type', 'cost', 'work_hours']]
            logging.info(f"{log_prefix} [filtered_df_shape={filtered_df.shape}]")

            # Convert the filtered DataFrame to a string representation
            filtered_df_string = filtered_df.to_string(index=False)
            logging.info(f"{log_prefix} [filtered_df_string={filtered_df_string}]")
        except Exception as e:
            logging.error(f"{log_prefix} [error=JSONDecodeError] [message={str(e)}]")
            filtered_df_string = ""

    ifc_context_output_strings.append(filtered_df_string)

    # If the total_costs_per_name is requested, return it as a string
    if 'total_costs_per_name' in context_sources:
        total_costs_per_name_string = str(total_costs_per_name)
        logging.info(f"{log_prefix} [total_costs_per_name_string={total_costs_per_name_string}]")
        ifc_context_output_strings.append(total_costs_per_name_string)

    # If the total_costs_per_level is requested, return it as a string
    if 'total_costs_per_level' in context_sources:
        total_costs_per_level_string = str(total_costs_per_level)
        logging.info(f"{log_prefix} [total_costs_per_level_string={total_costs_per_level_string}]")
        ifc_context_output_strings.append(total_costs_per_level_string)

    # If the total_costs_sum is requested, return it as a string
    if 'total_costs_sum' in context_sources:
        unique_names = total_costs_per_name['name'].unique().tolist()
        total_costs_sum_string = "Total Cost for the entire IFC file: $" + str(total_costs_sum)
        total_costs_sum_string += f" (Based on the names: {', '.join(unique_names)})"
        logging.info(f"{log_prefix} [total_costs_sum_string={total_costs_sum_string}]")
        ifc_context_output_strings.append(total_costs_sum_string)

    # If the total_work_hours_sum is requested, return it as a string
    if 'total_work_hours_sum' in context_sources:
        unique_names = total_costs_per_name['name'].unique().tolist()
        total_work_hours_sum_string = "Total Construction Work Hours for the entire IFC file: " + str(total_work_hours_sum)
        total_work_hours_sum_string += f" (Based on the names: {', '.join(unique_names)})"
        logging.info(f"{log_prefix} [total_work_hours_sum_string={total_work_hours_sum_string}]")
        ifc_context_output_strings.append(total_work_hours_sum_string)

    # Add a final message explaining the costs
    ifc_context_output_strings.append(
        "The costs are based on the total costs per name and level, and the total costs and work hours for the entire IFC file. "
        "The costs are calculated based on the geometry and properties of the elements in the IFC file. "
        "Only the provided types and names are included in the costs and work hours calculations. "
        "The costs are in US dollars and the work hours are in hours. "
        "The costs include material, labor, profit and overhead for the names and types provided. "
    )

    # Join all the context output strings into a single string with two newlines between each section
    ifc_context_output = "\n\n".join(ifc_context_output_strings)
    logging.info(f"{log_prefix} [ifc_context_output={ifc_context_output}]")
    return ifc_context_output

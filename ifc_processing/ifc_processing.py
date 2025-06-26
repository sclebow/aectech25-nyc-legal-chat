import ifcopenshell
from ifcopenshell.util.element import get_pset
import ifcopenshell.geom
import ifcopenshell.util.shape
import ifcopenshell.util.selector
from pprint import pprint
import os

import multiprocessing

import numpy as np
import pandas as pd

from sklearn.cluster import DBSCAN

def build_ifc_df(ifc_file):
    """
    Build a DataFrame from an IFC file containing element data.
    This function extracts relevant information from the IFC file and organizes it into a pandas DataFrame.
    The DataFrame includes element type, name, length, area, volume, and coordinates (x, y, z).
    Args:
        ifc_file: An IFC file object opened with ifcopenshell.
    Returns:
        pd.DataFrame: A DataFrame containing element data.
    """
    # Initialize an empty dictionary to store element data
    element_data_dict = {}
    # Create geometry settings once
    settings = ifcopenshell.geom.settings()
    unit_scale = ifcopenshell.util.unit.calculate_unit_scale(ifc_file)
    # Get all types of elements in the model using ifcopenshell
    all_types_in_model = ifc_file.by_type("IfcProduct")

    iterator = ifcopenshell.geom.iterator(settings, ifc_file, multiprocessing.cpu_count(), include=all_types_in_model)

    for i, shape_geo in enumerate(iterator):
        geometry = shape_geo.geometry
        (x, y, z) = ifcopenshell.util.shape.get_shape_bbox_centroid(shape_geo, geometry)
        # objInfo = all_types_in_model[i].get_info()
        name = ifc_file.by_guid(shape_geo.guid).get_info()
        if 'LongName' in name:
            nameOut = name['LongName']
        elif name['Name'] is None:
            nameOut = "unknown"
        else:
            nameOut = name['Name']
        element_data_dict[shape_geo.id] = {
            "type": shape_geo.type,
            # "name": shape_geo.name,
            "name" : nameOut,
            'length': ifcopenshell.util.shape.get_max_xyz(geometry)*unit_scale*3.28,  # Convert to feet
            'area': ifcopenshell.util.shape.get_max_side_area(geometry)*unit_scale**2 * 3.28**2,  # Convert to square feet
            'volume': ifcopenshell.util.shape.get_volume(geometry)*unit_scale**3 * 1.09**3,  # Convert to cubic yards
            "x": x,
            "y": y,
            "z": z,
        }

    element_data_df = pd.DataFrame.from_dict(element_data_dict, orient='index')
    return element_data_df

def assign_levels(element_data_df, threshold=0.1):
    """
    Assign levels to elements in the DataFrame based on their Z-coordinate using clustering.
    Adds a 'level' column to the DataFrame.

    :param element_data_df: DataFrame of all elements with a 'z' column.
    :param threshold: Clustering threshold for DBSCAN (in Z units).
    :return: DataFrame with a new 'level' column.
    """
    # Extract Z-coordinates from the DataFrame
    z_coordinates = element_data_df['z'].values.reshape(-1, 1)
    # print(len(z_coordinates), "Z-coordinates extracted from elements.")
    # Use DBSCAN to cluster elements based on their Z-coordinates
    clustering = DBSCAN(eps=threshold, min_samples=2).fit(z_coordinates)
    labels = clustering.labels_

    # Reorder cluster labels so that level 1 is the lowest Z cluster
    import collections
    label_to_zs = collections.defaultdict(list)
    for label, z in zip(labels, element_data_df['z'].values):
        if label != -1:
            label_to_zs[label].append(z)
    # Compute mean Z for each cluster label
    label_mean_z = {label: np.mean(zs) for label, zs in label_to_zs.items()}
    # Sort labels by mean Z (ascending)
    sorted_labels = sorted(label_mean_z, key=lambda l: label_mean_z[l])
    # Map old labels to new levels (starting from 1)
    label_to_level = {label: i+1 for i, label in enumerate(sorted_labels)}

    # Assign new levels
    levels = []
    for label in labels:
        if label == -1:
            levels.append(-1)
        else:
            levels.append(label_to_level[label])
    element_data_df = element_data_df.copy()
    element_data_df['level'] = levels

    return element_data_df

def process_ifc_file(ifc_file):
    """
    Process an IFC file to extract relevant data.
    Args:
        ifc_file: An IFC file object opened with ifcopenshell.
    Returns:
        pd.DataFrame: element_data_df with total_work_hours column added
    """
    wbs_dir = "./bdg_data/wbs"
    wbs_df = load_wbs(wbs_dir)
    
    element_data_df = build_ifc_df(ifc_file)

    # Assign levels to elements based on their Z-coordinate
    element_data_df = assign_levels(element_data_df, threshold=0.4)

    # Add time data to the DataFrame
    # Replace 'Parent.Quantity' with None in 'Source Qty' column
    wbs_df['Source Qty'] = wbs_df['Source Qty'].replace('Parent.Quantity', None)
    wbs_df['Source Qty'] = wbs_df['Source Qty'].ffill()
    wbs_df['Input Unit'] = wbs_df['Units'].apply(
        lambda x: x.split('/')[-1] if isinstance(x, str) else None
    )

    wbs_df = wbs_df[['Source Qty', 'Unit', 'Input Unit', 'Consumption', 'RS $ cons.', 'Description']]

    # Clean up 'Source Qty' column
    unique_names = element_data_df['name'].unique().tolist()  # Get unique names from element_data_df

    wbs_df['Source Qty'] = wbs_df['Source Qty'].astype(str).str.split('.').str[:-1].str.join('.')  # Remove the last part after the last dot
    wbs_df = wbs_df[wbs_df['Source Qty'].apply(lambda x: any(name in str(x) for name in unique_names))]  # Filter rows where 'Source Qty' contains any of the names in element_data_df
    # Drop rows where 'Input Unit' is 'TON', '-', or None
    wbs_df = wbs_df[~wbs_df['Input Unit'].isin(['TON', '-', None])]

    # Replace input units in FT with LF
    wbs_df['Input Unit'] = wbs_df['Input Unit'].replace('FT', 'LF')

    # Calculate total work hours and total cost for each element in a single loop
    wbs_df['Consumption'] = pd.to_numeric(wbs_df['Consumption'], errors='coerce')
    wbs_df['RS $ cons.'] = pd.to_numeric(wbs_df['RS $ cons.'], errors='coerce')
    total_work_hours = wbs_df.groupby(['Source Qty', 'Input Unit'])['Consumption'].sum().reset_index()
    total_costs = wbs_df.groupby(['Source Qty', 'Input Unit'])['RS $ cons.'].sum().reset_index()

    element_data_df['total_work_hours'] = None
    element_data_df['total_cost'] = None
    for idx, element in element_data_df.iterrows():
        name = element['name']
        # Work hours
        mask_length = (
            (total_work_hours['Source Qty'] == name) &
            (total_work_hours['Input Unit'] == 'LF')
        )
        length_consumption = total_work_hours.loc[mask_length, 'Consumption'].sum()
        mask_area = (
            (total_work_hours['Source Qty'] == name) &
            (total_work_hours['Input Unit'] == 'SF')
        )
        area_consumption = total_work_hours.loc[mask_area, 'Consumption'].sum()
        mask_volume = (
            (total_work_hours['Source Qty'] == name) &
            (total_work_hours['Input Unit'] == 'CY')
        )
        volume_consumption = total_work_hours.loc[mask_volume, 'Consumption'].sum()
        quantity_mask = (
            (total_work_hours['Source Qty'] == name) &
            (total_work_hours['Input Unit'] == 'EA')
        )
        quantity_consumption = total_work_hours.loc[quantity_mask, 'Consumption'].sum()
        length_hours = length_consumption * element.get('length', 0)
        area_hours = area_consumption * element.get('area', 0)
        volume_hours = volume_consumption * element.get('volume', 0)
        quantity_hours = quantity_consumption * 1
        total_hours = length_hours + area_hours + volume_hours + quantity_hours
        element_data_df.at[idx, 'total_work_hours'] = total_hours
        # Costs
        mask_length_c = (
            (total_costs['Source Qty'] == name) &
            (total_costs['Input Unit'] == 'LF')
        )
        length_cost = total_costs.loc[mask_length_c, 'RS $ cons.'].sum()
        mask_area_c = (
            (total_costs['Source Qty'] == name) &
            (total_costs['Input Unit'] == 'SF')
        )
        area_cost = total_costs.loc[mask_area_c, 'RS $ cons.'].sum()
        mask_volume_c = (
            (total_costs['Source Qty'] == name) &
            (total_costs['Input Unit'] == 'CY')
        )
        volume_cost = total_costs.loc[mask_volume_c, 'RS $ cons.'].sum()
        quantity_mask_c = (
            (total_costs['Source Qty'] == name) &
            (total_costs['Input Unit'] == 'EA')
        )
        quantity_cost = total_costs.loc[quantity_mask_c, 'RS $ cons.'].sum()
        length_total = length_cost * element.get('length', 0)
        area_total = area_cost * element.get('area', 0)
        volume_total = volume_cost * element.get('volume', 0)
        quantity_total = quantity_cost * 1
        total_cost = length_total + area_total + volume_total + quantity_total
        element_data_df.at[idx, 'total_cost'] = total_cost

    # Replace zero work hours and costs with "Unknown"
    element_data_df['total_work_hours'] = element_data_df['total_work_hours'].replace(0, "Unknown")
    element_data_df['total_cost'] = element_data_df['total_cost'].replace(0, "Unknown")

    # Create a total cost and work hours per element name dataframe, handle strings and NaNs just for this calculation
    element_data_df_for_grouping = element_data_df.copy()
    element_data_df_for_grouping['total_cost'] = pd.to_numeric(element_data_df_for_grouping['total_cost'], errors='coerce').fillna(0)
    element_data_df_for_grouping['total_work_hours'] = pd.to_numeric(element_data_df_for_grouping['total_work_hours'], errors='coerce').fillna(0)
    total_costs_per_name = element_data_df_for_grouping.groupby('name').agg(
        total_cost=('total_cost', 'sum'),
        total_work_hours=('total_work_hours', 'sum')
    ).reset_index()

    # Drop zero total costs and work hours
    total_costs_per_name = total_costs_per_name[total_costs_per_name['total_cost'] != 0]
    total_costs_per_name = total_costs_per_name[total_costs_per_name['total_work_hours'] != 0]
    # Drop empty names
    total_costs_per_name = total_costs_per_name[total_costs_per_name['name'] != '']
    # Reindex the DataFrame
    total_costs_per_name = total_costs_per_name.reset_index(drop=True)

    # Create a total cost and work hours per level dataframe, group by 'level' and 'name' and aggregate, handle strings and NaNs
    total_costs_per_level = element_data_df_for_grouping.groupby(['level', 'name']).agg(
        total_cost=('total_cost', 'sum'),
        total_work_hours=('total_work_hours', 'sum')
    ).reset_index()
    # Drop zero total costs and work hours
    total_costs_per_level = total_costs_per_level[total_costs_per_level['total_cost'] != 0]
    total_costs_per_level = total_costs_per_level[total_costs_per_level['total_work_hours'] != 0]
    # Drop empty names
    total_costs_per_level = total_costs_per_level[total_costs_per_level['name'] != '']
    # Reindex the DataFrame
    total_costs_per_level = total_costs_per_level.reset_index(drop=True)
    # Renumber the levels to start from 0 and step by 1
    unique_names = total_costs_per_level['name'].unique()
    level_mapping = {name: i for i, name in enumerate(unique_names)}
    total_costs_per_level['level'] = total_costs_per_level['level'].map(level_mapping)

    # Total costs and work hours sum
    total_costs_sum = total_costs_per_name['total_cost'].sum()
    total_work_hours_sum = total_costs_per_name['total_work_hours'].sum()

    # # Print the final DataFrame
    # print("Final Element Data DataFrame:")
    # pprint(element_data_df.head())

    # # Print the final Dataframe for total costs and work hours per element name
    # print("Final Total Costs and Work Hours per Element Name DataFrame:")
    # pprint(total_costs_per_name)

    # # Print the final Dataframe for total costs and work hours per level
    # print("Final Total Costs and Work Hours per Level DataFrame:")
    # pprint(total_costs_per_level)

    # # Save the final DataFrame to a CSV file
    # output_file = os.path.join(os.path.dirname(__file__), 'element_data.csv')
    # element_data_df.to_csv(output_file, index=False)
    # print(f"Element data saved to {output_file}")

    # # Save the final WBS DataFrame to a CSV file
    # wbs_output_file = os.path.join(os.path.dirname(__file__), 'wbs_data.csv')
    # wbs_df.to_csv(wbs_output_file, index=False)
    # print(f"WBS data saved to {wbs_output_file}")

    return element_data_df, total_costs_per_name, total_costs_per_level, total_costs_sum, total_work_hours_sum

def get_wbs_from_directory(directory):
    """
    Get the latest WBS file from the specified directory.
    This function searches for CSV or Excel files in the given directory and returns the path to the most recently modified file.
    If no WBS files are found, it raises a FileNotFoundError.
    If the directory does not exist, it raises a FileNotFoundError.

    :param directory: Directory to search for WBS files.
    :return: Path to the latest WBS file.    
    """

    import os
    import glob

    # Ensure the directory exists
    if not os.path.exists(directory):
        raise FileNotFoundError(f"The directory '{directory}' does not exist.")

    # Get all CSV or excel files in the directory
    wbs_files = glob.glob(os.path.join(directory, '*.csv')) + glob.glob(os.path.join(directory, '*.xlsx'))
    # print(f"Found {len(wbs_files)} WBS files in the directory: {directory}")

    if not wbs_files:
        raise FileNotFoundError("No WBS files found in the specified directory.")

    # Sort files by modification time and return the latest one
    latest_file = max(wbs_files, key=os.path.getmtime)
    # print(f"Latest WBS file: {latest_file}")
    return latest_file

def load_wbs(directory):
    """
    Load the Work Breakdown Structure (WBS) from a file in the specified directory.
    This function retrieves the latest WBS file from the directory, reads it into a pandas DataFrame,
    and returns the DataFrame. It also prints some information about the loaded data.
    If the file cannot be loaded, it prints an error message and returns None.

    :param directory: Directory where the WBS file is located.
    :return: DataFrame containing the WBS data.
    """
    # Get the latest WBS file from the specified directory
    file_path = get_wbs_from_directory(directory)
    # print(f"Loading WBS from file: {file_path}")

    try:
        if file_path.lower().endswith('.csv'):
            wbs_df = pd.read_csv(file_path)
        elif file_path.lower().endswith('.xlsx'):
            wbs_df = pd.read_excel(file_path)
        else:
            raise ValueError("Unsupported file format for WBS. Only .csv and .xlsx are supported.")

        # Print some information about the loaded DataFrame
        # print(f"WBS loaded successfully with {len(wbs_df)} rows and {len(wbs_df.columns)} columns.")
        # print("Columns in WBS:", wbs_df.columns.tolist())
        # # Optionally, display the first few rows of the DataFrame
        # print("First few rows of WBS:")
        # print(wbs_df.head())

        return wbs_df
    except Exception as e:
        # print(f"Error loading WBS file: {e}")
        return None

# def build_ifc_df_by_apartment(ifc_file):
#     """
#     Build a pandas Dataframe from an IFC file containing the information about the apartments in a building.
#     This is suitable for using with a valuation prediction model
#     """
#     # Initialize an empty dictionary to store element data
#     element_data_dict = {}
#     # Create geometry settings once
#     settings = ifcopenshell.geom.settings()
#     # unit_scale = ifcopenshell.util.unit.calculate_unit_scale(ifc_file)
#     # Get all types of elements in the model using ifcopenshell
#     apartments = ifc_file.by_type("IfcSpace")

#     iterator = ifcopenshell.geom.iterator(settings, ifc_file, multiprocessing.cpu_count(), include=apartments)

#     for shape_geo in iterator:
#         geometry = shape_geo.geometry
#         (x, y, z) = ifcopenshell.util.shape.get_shape_bbox_centroid(shape_geo, geometry)
#         element_data_dict[shape_geo.id] = {
#             "type": shape_geo.type,
#             "name": shape_geo.name,
#             'length': ifcopenshell.util.shape.get_max_xyz(geometry)*3.28,  # Convert to feet
#             'area': ifcopenshell.util.shape.get_max_side_area(geometry)**2 * 3.28**2,  # Convert to square feet
#             'volume': ifcopenshell.util.shape.get_volume(geometry)**3 * 1.09**3,  # Convert to cubic yards
#             "x": x,
#             "y": y,
#             "z": z,
#         }

#     element_data_df = pd.DataFrame.from_dict(element_data_dict, orient='index')

    return element_data_df
# if __name__ == "__main__":
#     # Change path to root directory of the project which is one level up from this script
#     current_dir = os.path.dirname(os.path.abspath(__file__))
#     project_root = os.path.abspath(os.path.join(current_dir, os.pardir))
#     # Add the project root to the system path
#     if project_root not in os.sys.path:
#         os.sys.path.append(project_root)
#     # from project_utils.ifc_utils import ifc
#     # Define the path to the IFC file
#     # process_ifc_file(ifc)
#     ifc = ifcopenshell.open('./ifc_files/aia25_graphml_g4_ifc.ifc')
#     # df = build_ifc_df_by_apartment(ifc)
#     df, total_costs_per_name, total_costs_per_level, total_costs_sum, total_work_hours_sum = process_ifc_file(ifc)
#     df = df[df['type']=='IfcSpace']
#     # df = df.dropna(subset=['name'], inplace=True)
#     df.to_csv('./testOutSpaces.csv')
import ifcopenshell
from ifcopenshell.util.element import get_pset
import ifcopenshell.geom
import ifcopenshell.util.shape
from pprint import pprint
import os

import multiprocessing

import numpy as np
import pandas as pd

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

    for shape_geo in iterator:
        geometry = shape_geo.geometry
        (x, y, z) = ifcopenshell.util.shape.get_shape_bbox_centroid(shape_geo, geometry)
        element_data_dict[shape_geo.id] = {
            "type": shape_geo.type,
            "name": shape_geo.name,
            'length': ifcopenshell.util.shape.get_max_xyz(geometry)*unit_scale*3.28,  # Convert to feet
            'area': ifcopenshell.util.shape.get_max_side_area(geometry)*unit_scale**2 * 3.28**2,  # Convert to square feet
            'volume': ifcopenshell.util.shape.get_volume(geometry)*unit_scale**3 * 1.09**3,  # Convert to cubic yards
            "x": x,
            "y": y,
            "z": z,
        }

    element_data_df = pd.DataFrame.from_dict(element_data_dict, orient='index')
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


    # Add time data to the DataFrame
    # Replace 'Parent.Quantity' with None in 'Source Qty' column
    wbs_df['Source Qty'] = wbs_df['Source Qty'].replace('Parent.Quantity', None)
    wbs_df['Source Qty'] = wbs_df['Source Qty'].ffill()
    wbs_df['Input Unit'] = wbs_df['Units'].apply(
        lambda x: x.split('/')[-1] if isinstance(x, str) else None
    )

    wbs_df = wbs_df[['Source Qty', 'Unit', 'Input Unit', 'Consumption', 'RS $ cons.']]

    # Drop rows where 'Input Unit' is 'TON', '-', or None
    wbs_df = wbs_df[~wbs_df['Input Unit'].isin(['TON', '-', None])]

    # Replace input units in FT with LF
    wbs_df['Input Unit'] = wbs_df['Input Unit'].replace('FT', 'LF')

    # Debug: Print all the unique input units in the WBS DataFrame
    print("Unique Input Units in WBS DataFrame:")
    pprint(wbs_df['Input Unit'].unique())

    # Calculate total work hours and total cost for each element in a single loop
    wbs_df['Consumption'] = pd.to_numeric(wbs_df['Consumption'], errors='coerce')
    wbs_df['RS $ cons.'] = pd.to_numeric(wbs_df['RS $ cons.'], errors='coerce')
    total_work_hours = wbs_df.groupby(['Source Qty', 'Input Unit'])['Consumption'].sum().reset_index()
    total_costs = wbs_df.groupby(['Source Qty', 'Input Unit'])['RS $ cons.'].sum().reset_index()

    element_data_df['total_work_hours'] = 0.0
    element_data_df['total_cost'] = 0.0
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

    return element_data_df

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
    print(f"Found {len(wbs_files)} WBS files in the directory: {directory}")

    if not wbs_files:
        raise FileNotFoundError("No WBS files found in the specified directory.")

    # Sort files by modification time and return the latest one
    latest_file = max(wbs_files, key=os.path.getmtime)
    print(f"Latest WBS file: {latest_file}")
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
    print(f"Loading WBS from file: {file_path}")

    try:
        if file_path.lower().endswith('.csv'):
            wbs_df = pd.read_csv(file_path)
        elif file_path.lower().endswith('.xlsx'):
            wbs_df = pd.read_excel(file_path)
        else:
            raise ValueError("Unsupported file format for WBS. Only .csv and .xlsx are supported.")

        # Print some information about the loaded DataFrame
        print(f"WBS loaded successfully with {len(wbs_df)} rows and {len(wbs_df.columns)} columns.")
        # print("Columns in WBS:", wbs_df.columns.tolist())
        # # Optionally, display the first few rows of the DataFrame
        # print("First few rows of WBS:")
        # print(wbs_df.head())

        return wbs_df
    except Exception as e:
        print(f"Error loading WBS file: {e}")
        return None

if __name__ == "__main__":
    # Change path to root directory of the project which is one level up from this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, os.pardir))
    # Add the project root to the system path
    if project_root not in os.sys.path:
        os.sys.path.append(project_root)
    from project_utils.ifc_utils import ifc
    # Define the path to the IFC file
    process_ifc_file(ifc)
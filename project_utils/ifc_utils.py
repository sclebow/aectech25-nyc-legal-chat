import os
import ifcopenshell
import ifcopenshell.util
import ifcopenshell.util.shape
import ifcopenshell.util.element
import ifcopenshell.geom
import multiprocessing

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

def get_ifc_context_from_query(query):
    """
    Use an LLM call to determine the IFC context from a query.
    """
    from llm_calls import run_llm_query

    valid_shapes_dict = {
        'column':'IfcColumn',
        'wall':'IfcWall',
        'slab':'IfcSlab',
        'beam':'IfcBeam',
        'roof':'IfcRoof',
        'stair':'IfcStair',
        'door':'IfcDoor',
        'window':'IfcWindow',
        'curtain wall':'IfcCurtainWall'
    }
    valid_shapes_keys = list(valid_shapes_dict.keys())

    system_prompt = f"""
        Provide the most relevant items from the following list based on the user's query:
        {valid_shapes_keys}
        The user may refer to these items by their common names, such as 'wall', 'door', etc.
        If the user refers to an item not in the list, respond with 'unknown'.
        The response should be a single string containing the item names, separated by commas.
        If the user refers to multiple items, return all of them.
    """

    shapes_string = run_llm_query(system_prompt, query, max_tokens=1500)
    print("Shapes string from LLM:", shapes_string)

    shapes_list = [shape.strip().lower() for shape in shapes_string.split(',') if shape.strip()]
    print("Shapes list after processing:", shapes_list)
    print(f'type(shapes_list): {type(shapes_list)}')

    shape_statistics = []
    for shape in shapes_list:
        if shape in valid_shapes_dict:
            shape_statistics.append(get_shape_statistics(valid_shapes_dict[shape]))

    shape_statistics_string = "\n".join(shape_statistics)
    if not shape_statistics_string:
        # shape_statistics_string = "No valid shapes found in the query."
        # Return all shapes statistics
        shape_statistics_string = "\n".join([get_shape_statistics(shape) for shape in valid_shapes_dict.values()])
    
    return shape_statistics_string    

def get_shape_statistics(shape):
    global ifc
    """Calculate and return the number, total volume and surface area of a shape."""
    valid_shapes = {
        'column':'IfcColumn',
        'wall':'IfcWall',
        'slab':'IfcSlab',
        'beam':'IfcBeam',
        'roof':'IfcRoof',
        'stair':'IfcStair',
        'door':'IfcDoor',
        'window':'IfcWindow',
        'curtain wall':'IfcCurtainWall'
    }
    if shape not in valid_shapes.values():
        try:
            shape = valid_shapes[shape.lower()]
        except KeyError:
            raise ValueError(f"Invalid shape type: {shape}. Valid types are: {', '.join(valid_shapes.values())}")

    ifc_shapes = ifc.by_type(shape)
    settings = ifcopenshell.geom.settings()

    iterator = ifcopenshell.geom.iterator(settings, ifc, multiprocessing.cpu_count(), include=ifc_shapes)

    total_count = len(ifc_shapes)
    total_volume = 0
    total_surface_area = 0
    # for ifc_shape in iterator:
    #     # initiate settings (you can use this to control coordinates in respect to origin, units, etc)
        

    #     # get the geometry of the shape
    #     shape_geo = ifcopenshell.geom.create_shape(settings, ifc_shape)
    #     print(shape_geo.guid)
    #     occ_shape = shape_geo.geometry

    #     # calculate volume and surface area
    #     volume = ifcopenshell.util.shape.get_volume(occ_shape)
    #     area = ifcopenshell.util.shape.get_area(occ_shape)

    #     total_volume += volume
    #     total_surface_area += area

    # for ifc_shape in ifc_shapes:
    #     shape_geo = ifcopenshell.geom.create_shape(settings, ifc_shape)
    #     print(shape_geo.guid)
    #     occ_shape = shape_geo.geometry

    #     # calculate volume and surface area
    #     volume = ifcopenshell.util.shape.get_volume(occ_shape)
    #     area = ifcopenshell.util.shape.get_area(occ_shape)

    #     total_volume += volume
    #     total_surface_area += area

    for shape_geo in iterator:
        # print(shape_geo.guid)
        occ_shape = shape_geo.geometry

        # calculate volume and surface area
        volume = ifcopenshell.util.shape.get_volume(occ_shape)
        area = ifcopenshell.util.shape.get_area(occ_shape)

        total_volume += volume
        total_surface_area += area

    return f'{shape} statistics: count: {total_count}, total volume: {total_volume} m3, total surface area: {total_surface_area} m2'
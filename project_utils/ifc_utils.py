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

    return {f'{shape} statistics: count: {total_count}, total volume: {total_volume} m3, total surface area: {total_surface_area} m2'}
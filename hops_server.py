from flask import Flask, request, jsonify

import llm_calls
from project_utils import rag_utils
from server import config
import ghhops_server as hs
import os
import json

import ifcopenshell
import networkx as nx
import plotly.graph_objects as go

import pandas as pd

# import rhinoinside
# rhinoinside.load("C:\Program Files\Rhino 8\System")
# import Rhino
# import System



app = Flask(__name__)
hops = hs.Hops(app)
mode = 'local'
config.set_mode(mode)
collection, ranker = rag_utils.init_rag(mode=config.get_mode())

@hops.component(
    '/studio_copilot',
    name="Yield copilot",
    description="Yeild cost and value design copilot",
    inputs = [
        hs.HopsString("query", "Q", "Query to the copilot"),
        # hs.HopsMesh("mesh", "M", "mesh geometry", access=hs.HopsParamAccess.LIST, optional = True),
        hs.HopsBoolean("send", "s", "Send to copilot", default=False),
    ],
    outputs = [
        hs.HopsString("response", "R", "Response from the copilot"),
        hs.HopsString("source", "S", "Source of the response"),
        hs.HopsString("status", "St", "Status of the response"),
    ]
)
def yield_copilot(query, send=False):
    if send:
        answer, sources = llm_calls.route_query_to_function(str(query), collection, ranker, False)
    return jsonify({'response': answer, 'sources': sources})

    
@hops.component(
    '/mesh_to_obj',
    name="Mesh to OBJ",
    description="Convert Rhino meshes to OBJ string format",
    inputs=[
        hs.HopsMesh("meshIn", "M", "Input meshes", access=hs.HopsParamAccess.LIST)
    ],
    outputs=[
        hs.HopsString("objString", "O", "OBJ format string")
    ]
)
def mesh_to_obj(meshIn):
    # Store lines in a list instead of string concatenation
    obj_lines = ["# List of geometric vertices, with (x, y, z, [w]) coordinates"]
    vertex_offset = 1  # OBJ indices start at 1
    
    for mesh in meshIn:
        # Add vertices
        for v in mesh.Vertices:
            obj_lines.append(f"v {v.X:.6f} {v.Y:.6f} {v.Z:.6f}")
        
        # Add faces
        for i in range(mesh.Faces.Count):
            face = mesh.Faces[i]
            if face[2] == face[3]:  # Triangle face
                obj_lines.append(f"f {face[0] + vertex_offset} {face[1] + vertex_offset} {face[2] + vertex_offset}")
            else:  # Quad face
                obj_lines.append(f"f {face[0] + vertex_offset} {face[1] + vertex_offset} {face[2] + vertex_offset} {face[3] + vertex_offset}")
        
        # Update vertex offset for next mesh
        vertex_offset += len(mesh.Vertices)
    
    # Join lines with system-appropriate line separator
    return '\n'.join(obj_lines)

@hops.component(
    '/ifc_call',
    name='llm query with ifc file info',
    description="send query to LLM with IFC data",
    inputs=[
        hs.HopsString("Query", "Q", "Query to send to LLM"),
        hs.HopsString("ifc", "IFC path", "IFC path")
    ],
    outputs=[
        hs.HopsString("Response", "R", "Response from LLM")
    ]
)
def ifc_call(query, filepath):
    # include_types=["IfcSpace", "IfcSlab", "IfcRoof", "IfcWall", "IfcWallStandardCase", "IfcDoor", "IfcWindow"]

    ifc_file = ifcopenshell.open(filepath)
    rooms = ifc_file.by_type("IfcSpace")
    space_boundaries = ifc_file.by_type("IfcRelSpaceBoundary")
    # Identify element types in space boundaries
    element_types = set()
    for rel in space_boundaries:
        if rel.RelatedBuildingElement:
            element_types.add(rel.RelatedBuildingElement.is_a())
    def get_node_color(ifc_type):
        """Return a color based on the IFC type or default to gray."""
        # Define categories and colors
        categories = {room.is_a(): "red" for room in rooms}
        for rel in space_boundaries:
            if rel.RelatedBuildingElement:
                categories.setdefault(
                    rel.RelatedBuildingElement.is_a(),
                    f"#{hash(rel.RelatedBuildingElement.is_a()) & 0xFFFFFF:06x}"
                )       
        return categories.get(ifc_type, "gray")
    
    G = nx.Graph()
    # Add Rooms
    for room in rooms:
        room_id = room.GlobalId
        G.add_node(room_id, **extract_properties(room), category="IfcSpace")
    
#     Add Room-Element Connections
#    (Any building element bounding a room goes here with 'SURROUNDS'.)
    for rel in space_boundaries:
        room = rel.RelatingSpace
        element = rel.RelatedBuildingElement
        if room and element:
            if element.GlobalId not in G.nodes:
                G.add_node(element.GlobalId, **extract_properties(element), category=element.is_a())
            # Connect the room to this element
            G.add_edge(room.GlobalId, element.GlobalId, relation="SURROUNDS")

    # Add Wall-Window/Door Connections
    #    (Direct 'VOIDS' edge from IfcWall* types to IfcDoor or IfcWindow.)
    for rel in ifc_file.by_type("IfcRelVoidsElement"):
        wall = rel.RelatingBuildingElement
        opening = rel.RelatedOpeningElement

        for fill_rel in ifc_file.by_type("IfcRelFillsElement"):
            if fill_rel.RelatingOpeningElement == opening:
                filled_element = fill_rel.RelatedBuildingElement
                # Strict check: IfcWall*, IfcWallStandardCase, IfcCurtainWall --> [IfcDoor | IfcWindow]
                if (
                    wall
                    and filled_element
                    and "Wall" in wall.is_a()
                    and filled_element.is_a() in ["IfcDoor", "IfcWindow"]
                ):
                    # Ensure both nodes (Wall + Door/Window) exist in the graph
                    if wall.GlobalId not in G.nodes:
                        G.add_node(wall.GlobalId, **extract_properties(wall), category=wall.is_a())
                    if filled_element.GlobalId not in G.nodes:
                        G.add_node(filled_element.GlobalId, **extract_properties(filled_element), category=filled_element.is_a())

                    # Create a direct connection for the wall-door/window
                    # print(f"VOIDS edge found: {wall.GlobalId} -> {filled_element.GlobalId}")
                    G.add_edge(wall.GlobalId, filled_element.GlobalId, relation="VOIDS")    
    #Remove unconnected nodes
    unconnected_nodes = [node for node, degree in G.degree() if degree == 0]
    G.remove_nodes_from(unconnected_nodes)

    # Recalculate layout (3D)
    pos = nx.spring_layout(G, dim=3, seed=42)

    # Extract updated node positions and colors
    x_nodes, y_nodes, z_nodes = zip(*[pos[node] for node in G.nodes])
    colors = [get_node_color(G.nodes[node].get("IfcType", "Undefined")) for node in G.nodes]

    # Separate edge coordinates by relation type
    voids_x, voids_y, voids_z = [], [], []
    surrounds_x, surrounds_y, surrounds_z = [], [], []
    other_x, other_y, other_z = [], [], []

    for u, v, data in G.edges(data=True):
        x0, y0, z0 = pos[u]
        x1, y1, z1 = pos[v]

        # Add coordinates in Plotly "line segment" style: [x0, x1, None] so lines don't connect across edges
        if data.get("relation") == "VOIDS":
            voids_x.extend([x0, x1, None])
            voids_y.extend([y0, y1, None])
            voids_z.extend([z0, z1, None])
        elif data.get("relation") == "SURROUNDS":
            surrounds_x.extend([x0, x1, None])
            surrounds_y.extend([y0, y1, None])
            surrounds_z.extend([z0, z1, None])
        else:
            other_x.extend([x0, x1, None])
            other_y.extend([y0, y1, None])
            other_z.extend([z0, z1, None])

    # Create separate edge traces
    voids_trace = go.Scatter3d(
        x=voids_x, y=voids_y, z=voids_z,
        mode='lines',
        line=dict(width=2, color='red'),
        hoverinfo='none'
    )

    surrounds_trace = go.Scatter3d(
        x=surrounds_x, y=surrounds_y, z=surrounds_z,
        mode='lines',
        line=dict(width=2, color='gray'),
        opacity=0.5,
        hoverinfo='none'
    )

    other_trace = go.Scatter3d(
        x=other_x, y=other_y, z=other_z,
        mode='lines',
        line=dict(width=2, color='lightgray'),
        hoverinfo='none'
    )

    # Create the node trace
    node_trace = go.Scatter3d(
        x=x_nodes, y=y_nodes, z=z_nodes,
        mode='markers',
        marker=dict(size=5, color=colors, opacity=0.8),
        text=[
            f"{G.nodes[node].get('Name', 'N/A')} (" \
            f"{G.nodes[node].get('IfcType', 'Undefined')})"
            for node in G.nodes
        ],
        hoverinfo='text'
    )

    # Build figure
    layout = go.Layout(
        title="3D IFC Wall-Door/Window Visualization",
        width=1200, height=800,
        scene=dict(xaxis=dict(title='X'),
                yaxis=dict(title='Y'),
                zaxis=dict(title='Z')),
        showlegend=False
    )

    fig = go.Figure(
        data=[voids_trace, surrounds_trace, other_trace, node_trace],
        layout=layout
    )
    fig.show()

    # Remove unconnected nodes
    unconnected_nodes = [node for node, degree in G.degree() if degree == 0]
    G.remove_nodes_from(unconnected_nodes)

    # Recalculate layout (3D)
    pos = nx.spring_layout(G, dim=3, seed=42)

    # Extract node positions and colors (only for Walls, Doors, Windows)
    wall_door_window_nodes = [
        node
        for node in G.nodes
        if G.nodes[node].get("IfcType") in [
            "IfcWall", "IfcWallStandardCase", "IfcCurtainWall", "IfcDoor", "IfcWindow"
        ]
    ]

    x_nodes, y_nodes, z_nodes = zip(*[pos[node] for node in wall_door_window_nodes])
    colors = [
        get_node_color(G.nodes[node].get("IfcType", "Undefined"))
        for node in wall_door_window_nodes
    ]

    # Separate edge coordinates by relation type
    voids_x, voids_y, voids_z = [], [], []
    surrounds_x, surrounds_y, surrounds_z = [], [], []
    other_x, other_y, other_z = [], [], []

    for u, v, data in G.edges(data=True):
        x0, y0, z0 = pos[u]
        x1, y1, z1 = pos[v]

        # Add coordinates in Plotly "line segment" style: [x0, x1, None] so lines don't connect across edges
        if data.get("relation") == "VOIDS":
            voids_x.extend([x0, x1, None])
            voids_y.extend([y0, y1, None])
            voids_z.extend([z0, z1, None])
        elif data.get("relation") == "SURROUNDS":
            surrounds_x.extend([x0, x1, None])
            surrounds_y.extend([y0, y1, None])
            surrounds_z.extend([z0, z1, None])
        else:
            other_x.extend([x0, x1, None])
            other_y.extend([y0, y1, None])
            other_z.extend([z0, z1, None])

    # Create separate edge traces
    voids_trace = go.Scatter3d(
        x=voids_x, y=voids_y, z=voids_z,
        mode='lines',
        line=dict(width=2, color='red'),
        hoverinfo='none'
    )

    surrounds_trace = go.Scatter3d(
        x=surrounds_x, y=surrounds_y, z=surrounds_z,
        mode='lines',
        line=dict(width=2, color='gray'),
        opacity=0.05,
        hoverinfo='none'
    )

    other_trace = go.Scatter3d(
        x=other_x, y=other_y, z=other_z,
        mode='lines',
        line=dict(width=2, color='lightgray'),
        hoverinfo='none'
    )

    # Create the node trace
    node_trace = go.Scatter3d(
        x=x_nodes, y=y_nodes, z=z_nodes,
        mode='markers',
        marker=dict(size=5, color=colors, opacity=0.8),
        text=[
            f"{G.nodes[node].get('Name', 'N/A')} (" \
            f"{G.nodes[node].get('IfcType', 'Undefined')})"
            for node in wall_door_window_nodes
        ],
        hoverinfo='text'
    )

    #  Build figure
    layout = go.Layout(
        title="3D IFC Wall-Door/Window Visualization",
        width=1200, height=800,
        scene=dict(xaxis=dict(title='X'),
                yaxis=dict(title='Y'),
                zaxis=dict(title='Z')),
        showlegend=False
    )

    fig = go.Figure(
        data=[voids_trace, surrounds_trace, other_trace, node_trace],
        layout=layout
    )
    fig.show()

    return "did that work?"


def extract_properties(entity):
    """Extracts general properties and quantities from an IFC entity."""
    data = {
        "GlobalId": entity.GlobalId,
        "Name": entity.Name,  # Initialize with entity.Name
        "Description": getattr(entity, "Description", None),
        "ObjectType": getattr(entity, "ObjectType", None),
        "IfcType": entity.is_a()
    }

    if data["Name"] is None and hasattr(entity, "IsDefinedBy"):
        for rel in entity.IsDefinedBy:
            if rel.is_a("IfcRelDefinesByProperties") and hasattr(rel, "RelatingPropertyDefinition"):
                prop_def = rel.RelatingPropertyDefinition
                if prop_def.is_a("IfcPropertySet"):
                    # Check if it's Pset_SpaceCommon
                    if prop_def.Name == "Pset_SpaceCommon":
                        for prop in prop_def.HasProperties:
                            if prop.is_a("IfcPropertySingleValue") and prop.Name == "Name":
                                data["Name"] = getattr(prop.NominalValue, "wrappedValue", None)
                                break  # Stop searching if found
                    else:  # Otherwise, try to find the name in other property sets
                        for prop in prop_def.HasProperties:
                            if prop.is_a("IfcPropertySingleValue"):
                                if prop.Name in ["Name", "name", "LongName", "longname"]:
                                    data["Name"] = getattr(prop.NominalValue, "wrappedValue", None)
                                    break  # Stop searching if found
                                property_value = getattr(prop.NominalValue, "wrappedValue", None)
                                if property_value in ["Name", "LongName"]:
                                    for inner_prop in prop_def.HasProperties:
                                        if inner_prop.is_a("IfcPropertySingleValue") and inner_prop.Name == property_value:
                                            data["Name"] = getattr(inner_prop.NominalValue, "wrappedValue", None)
                                            break
                                    break  # Stop searching if found
    # Check if Name is still None and LongName is available
    if data["Name"] is None and hasattr(entity, 'LongName'):
        data["Name"] = entity.LongName  # Assign LongName to Name if Name is None

    return data

if __name__ == '__main__':
    app.run(debug=True, port=6767)


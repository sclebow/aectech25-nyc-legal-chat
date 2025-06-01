import ifcopenshell
import networkx as nx
import plotly.graph_objects as go
import pandas as pd
import os
from neo4j import GraphDatabase
import networkx as nx
from tqdm import tqdm
from collections import defaultdict

def extract_properties(entity):
    """Extracts general and identity-related properties from an IFC entity."""
    data = {
        "GlobalId": entity.GlobalId,
        "Name": entity.Name,
        "Description": getattr(entity, "Description", None),
        "ObjectType": getattr(entity, "ObjectType", None),
        "IfcType": entity.is_a()
    }

    # Fallback naming and identity-related property extraction
    if hasattr(entity, "IsDefinedBy"):
        for rel in entity.IsDefinedBy:
            if not rel.is_a("IfcRelDefinesByProperties"):
                continue
            prop_def = getattr(rel, "RelatingPropertyDefinition", None)
            if not prop_def or not prop_def.is_a("IfcPropertySet"):
                continue

            for prop in prop_def.HasProperties:
                if not prop.is_a("IfcPropertySingleValue"):
                    continue

                name = prop.Name
                value = getattr(prop.NominalValue, "wrappedValue", None)

                # Try to extract identity-related properties
                if name.lower() in ["locationx", "locationy", "locationz", "solarrad"]:
                    data[name] = value

                # Set name if not yet set
                if data["Name"] is None and name.lower() in ["name", "longname"]:
                    data["Name"] = value

                # Handle cases where value is a pointer to another property name
                if isinstance(value, str) and value.lower() in ["name", "longname"]:
                    for inner_prop in prop_def.HasProperties:
                        if inner_prop.is_a("IfcPropertySingleValue") and inner_prop.Name.lower() == value.lower():
                            data["Name"] = getattr(inner_prop.NominalValue, "wrappedValue", None)
                            break

    # Fallback: try LongName attribute directly
    if data["Name"] is None and hasattr(entity, "LongName"):
        data["Name"] = entity.LongName

    # Extract direct Tag attribute if not already set
    if hasattr(entity, "Tag") and "Tag" not in data:
        data["Tag"] = entity.Tag

    return data

def get_node_color(ifc_type, categories):
    """Return a color based on the IFC type or default to gray."""
    return categories.get(ifc_type, "gray")

ifc_directory = os.path.join(os.getcwd(), "ifc_files")
files = [os.path.join(ifc_directory, f) for f in os.listdir(ifc_directory) if f.endswith('.ifc')]
if files:
    latest_file = max(files, key=os.path.getmtime)
    print("Most recently modified file:", latest_file)
else:
    print("No files found.")

ifc_file = ifcopenshell.open(latest_file)
rooms = ifc_file.by_type("IfcSpace")
space_boundaries = ifc_file.by_type("IfcRelSpaceBoundary")

# Identify element types in space boundaries
element_types = set()
for rel in space_boundaries:
    if rel.RelatedBuildingElement:
        element_types.add(rel.RelatedBuildingElement.is_a())

print("Unique element types in space boundaries:")
for element_type in sorted(element_types):
    print("-", element_type)

# Define categories and colors
categories = {room.is_a(): "red" for room in rooms}
for rel in space_boundaries:
    if rel.RelatedBuildingElement:
        categories.setdefault(
            rel.RelatedBuildingElement.is_a(),
            f"#{hash(rel.RelatedBuildingElement.is_a()) & 0xFFFFFF:06x}"
        )

# build graph
G = nx.Graph()

# Add Rooms
for room in rooms:
    room_id = room.GlobalId
    G.add_node(room_id, **extract_properties(room), category="IfcSpace")

# Add Room-Element Connections
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

# Find nodes missing any of the required position attributes
nodes_missing_location = [
    node for node in G.nodes
    if not all(k in G.nodes[node] for k in ("LocationX", "LocationY", "LocationZ"))
]

print("Nodes missing LocationX, LocationY, or LocationZ:")
for node in nodes_missing_location:
    print(f"- {node}: {G.nodes[node]}")

# Remove unconnected nodes
unconnected_nodes = [node for node, degree in G.degree() if degree == 0]
G.remove_nodes_from(unconnected_nodes)

# Assign positions from node attributes
pos = {
    node: (
        G.nodes[node].get("LocationX", 0),
        G.nodes[node].get("LocationY", 0),
        G.nodes[node].get("LocationZ", 0)
    )
    for node in G.nodes
}

# Extract node positions and colors (only for Walls, Doors, Windows)
wall_door_window_nodes = [
    node
    for node in G.nodes
    if G.nodes[node].get("IfcType") in [
        "IfcWall", "IfcDoor", "IfcWindow"
    ]
]
x_nodes, y_nodes, z_nodes = zip(*[pos[node] for node in wall_door_window_nodes])
colors = [
    get_node_color(G.nodes[node].get("IfcType", "Undefined"), categories)
    for node in wall_door_window_nodes
]
# Extract updated node positions and colors
x_nodes, y_nodes, z_nodes = zip(*[pos[node] for node in G.nodes])
colors = [get_node_color(G.nodes[node].get("IfcType", "Undefined"), categories) for node in G.nodes]

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

# # Create separate edge traces
# voids_trace = go.Scatter3d(
#     x=voids_x, y=voids_y, z=voids_z,
#     mode='lines',
#     line=dict(width=2, color='red'),
#     hoverinfo='none'
# )

# surrounds_trace = go.Scatter3d(
#     x=surrounds_x, y=surrounds_y, z=surrounds_z,
#     mode='lines',
#     line=dict(width=2, color='gray'),
#     opacity=0.05,
#     hoverinfo='none'
# )

# other_trace = go.Scatter3d(
#     x=other_x, y=other_y, z=other_z,
#     mode='lines',
#     line=dict(width=2, color='lightgray'),
#     hoverinfo='none'
# )

# # Create the node trace
# node_trace = go.Scatter3d(
#     x=x_nodes, y=y_nodes, z=z_nodes,
#     mode='markers',
#     marker=dict(size=5, color=colors, opacity=0.8),
#     text=[
#         f"{G.nodes[node].get('Name', 'N/A')} (" \
#         f"{G.nodes[node].get('IfcType', 'Undefined')})"
#         for node in wall_door_window_nodes
#     ],
#     hoverinfo='text'
# )

# # Build figure
# layout = go.Layout(
#     title="3D IFC Wall-Door/Window Visualization",
#     width=1200, height=800,
#     scene=dict(xaxis=dict(title='X'),
#                yaxis=dict(title='Y'),
#                zaxis=dict(title='Z')),
#     showlegend=False
# )

# fig = go.Figure(
#     data=[voids_trace, surrounds_trace, other_trace, node_trace],
#     layout=layout
# )
# fig.show()

nodes = pd.DataFrame.from_dict(dict(G.nodes(data=True)), orient='index')
nodes[nodes['LocationX'].notna()]['IfcType'].value_counts()
nodes[nodes['SolarRad'].notna()]['IfcType'].value_counts()

# print(nodes.info())

def replace_nans(df):
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            # df[col].fillna(0, inplace=True)
            df.fillna({col: 0}, inplace=True)
        else:
            # df[col].fillna('N/A', inplace=True)
            df.fillna({col: 'N/A'}, inplace=True)
    return df

nodes = replace_nans(nodes)

edges = pd.DataFrame(G.edges(data=True), columns=['source', 'target', 'attributes'])
# Check for edges types
edges['relation_type'] = edges['attributes'].apply(lambda x: x.get('relation', None))

# ________________________________________________________________________________________________________________________________
# load nodes and edges into neo4j

# Connect to Neo4j
URI = "bolt://localhost:7687"

USERNAME = "neo4j"
PASSWORD = "macad2025"

# Create a Neo4j driver
driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))

# Verify connectivity
try:
    driver.verify_connectivity()
    print("Connection successful!")
except Exception as e:
    print("Connection failed:", e)

def batch_merge_nodes(tx, batch):
    """
    Merges a batch of nodes into Neo4j with dynamic labels from 'IfcType'
    """

    label_groups = defaultdict(list)
    for row in batch:
        label = row.get("IfcType")
        if label:
            label_groups[label].append(row)

    for label, records in label_groups.items():
        query = f"""
        UNWIND $rows AS row
        MERGE (n:{label} {{GlobalId: row.GlobalId}})
        SET n += row
        """
        tx.run(query, rows=records)

batch_size = 500
with driver.session() as session:
    for i in tqdm(range(0, len(nodes), batch_size), desc="Batch merging nodes"):
        batch = nodes.iloc[i:i+batch_size].to_dict('records')
        session.execute_write(batch_merge_nodes, batch)

# driver.close()
print("Nodes loaded successfully!")

# print(edges.info())
# print(edges.head())

def batch_merge_edges_without_apoc(tx, relation_type, batch):
    query = f"""
    UNWIND $rows AS row
    MATCH (a {{GlobalId: row.source}})
    MATCH (b {{GlobalId: row.target}})
    MERGE (a)-[r:{str(relation_type)}]->(b)
    SET r += row.props
    """
    tx.run(query, rows=batch)

# edges_data = []
# for _, row in edges.iterrows():
#     props = row.drop(['source', 'target', 'relation_type']).dropna().to_dict()
#     edges_data.append({
#         'source': row['source'],
#         'target': row['target'],
#         'relation_type': row['relation_type'],
#         'props': props
#     })
edges_data = []
for _, row in edges.iterrows():
    # Flatten the attributes dictionary into the props dictionary
    props = {}
    if isinstance(row['attributes'], dict):
        props.update(row['attributes'])
    # Add any other columns you want as properties (excluding source, target, relation_type, attributes)
    for col in row.index:
        if col not in ['source', 'target', 'relation_type', 'attributes']:
            props[col] = row[col]
    edges_data.append({
        'source': row['source'],
        'target': row['target'],
        'relation_type': row['relation_type'],
        'props': props
    })

grouped_edges = defaultdict(list)
for row in edges_data:
    grouped_edges[row['relation_type']].append(row)

with driver.session() as session:
    for relation_type, group in grouped_edges.items():
        for i in tqdm(range(0, len(group), batch_size), desc=f"Merging {relation_type}"):
            batch = group[i:i+batch_size]
            session.execute_write(batch_merge_edges_without_apoc, relation_type, batch)

# driver.close()
print("Edges loaded successfully!")

def batch_merge_edges(tx, batch):
    query = """
    UNWIND $rows AS row
    MATCH (a {GlobalId: row.source})
    MATCH (b {GlobalId: row.target})
    MERGE (a)-[r:RELATED_TO]->(b)
    SET r += row.props
    """
    tx.run(query, rows=batch)

# Prepare data with source, target, and optional properties
# edges_data = []
# for _, row in edges.iterrows():
#     edges_data.append({
#         'source': row['source'],
#         'target': row['target'],
#         'props': row.drop(['source', 'target']).dropna().to_dict()
#     })
edges_data = []
for _, row in edges.iterrows():
    props = {}
    # Flatten the 'attributes' dictionary if present
    if isinstance(row['attributes'], dict):
        props.update(row['attributes'])
    # Add other columns as properties, except for source, target, relation_type, attributes
    for col in row.index:
        if col not in ['source', 'target', 'relation_type', 'attributes']:
            props[col] = row[col]
    edges_data.append({
        'source': row['source'],
        'target': row['target'],
        'props': props
    })

# Batch size
batch_size = 500
with driver.session() as session:
    for i in tqdm(range(0, len(edges_data), batch_size), desc="Merging edges"):
        batch = edges_data[i:i + batch_size]
        session.execute_write(batch_merge_edges, batch)

print("Edges loaded successfully!")

# Retrieve data from Neo4j database
def get_nodes(tx):
    """
    Retrieve all nodes with all their properties.
    """
    query = "MATCH (n) RETURN properties(n) AS props"
    return [record["props"] for record in tx.run(query)]

def get_edges(tx):
    """
    Retrieve all relationships (edges) between nodes using GlobalId.
    """
    query = "MATCH (a)-[r]->(b) RETURN a.GlobalId AS source, b.GlobalId AS target"
    return [{"source": record["source"], "target": record["target"]} for record in tx.run(query)]

# Start session and fetch data
with driver.session() as session:
    nodes_data = session.execute_read(get_nodes)
    edges = session.execute_read(get_edges)

# Build NetworkX graph
G = nx.Graph()

# Add nodes with all their properties
for node in nodes_data:
    node_id = node.get("GlobalId")
    if node_id:
        G.add_node(node_id, **node)

# Add edges if both endpoints exist
for edge in edges:
    source = edge["source"]
    target = edge["target"]
    if source in G.nodes and target in G.nodes:
        G.add_edge(source, target)

# Remove isolated nodes (no edges)
isolated_nodes = list(nx.isolates(G))
G.remove_nodes_from(isolated_nodes)

# 3D spring layout
pos = {
    node: (
        G.nodes[node].get("LocationX", 0),
        G.nodes[node].get("LocationY", 0),
        G.nodes[node].get("LocationZ", 0)
    )
    for node in G.nodes
}

def get_color_for_ifc_type(ifc_type):
    """
    Generate a hex color from IfcType string.
    """
    return f"#{hash(ifc_type) & 0xFFFFFF:06x}"

# Build edge traces
edge_x, edge_y, edge_z = [], [], []
for edge in G.edges():
    x0, y0, z0 = pos[edge[0]]
    x1, y1, z1 = pos[edge[1]]
    edge_x.extend([x0, x1, None])
    edge_y.extend([y0, y1, None])
    edge_z.extend([z0, z1, None])

edge_trace = go.Scatter3d(
    x=edge_x, y=edge_y, z=edge_z,
    mode='lines',
    line=dict(color='gray', width=2),
    hoverinfo='none'
)
# Build node traces
node_x, node_y, node_z = [], [], []
node_colors = []
node_text = []

for nid, attr in G.nodes(data=True):
    x, y, z = pos[nid]
    node_x.append(x)
    node_y.append(y)
    node_z.append(z)
    ifc_type = attr.get("IfcType", "Unknown")
    node_colors.append(get_color_for_ifc_type(ifc_type))
    # Full attribute hover info
    hover_info = "<br>".join(f"{k}: {v}" for k, v in attr.items())
    node_text.append(hover_info)

# node_trace = go.Scatter3d(
#     x=node_x, y=node_y, z=node_z,
#     mode='markers',
#     marker=dict(
#         size=6,
#         color=node_colors,
#         line=dict(width=0)
#     ),
#     hoverinfo='text',
#     text=node_text
# )

# # Create the 3D figure
# fig = go.Figure(data=[edge_trace, node_trace],
#                 layout=go.Layout(
#                     title=dict(text="3D Graph Visualization from Neo4j", font=dict(size=16)),
#                     showlegend=False,
#                     width=1200, height=800,
#                     margin=dict(l=0, r=0, b=0, t=40),
#                     scene=dict(
#                         xaxis=dict(showbackground=True, showticklabels=True, title=''),
#                         yaxis=dict(showbackground=True, showticklabels=True, title=''),
#                         zaxis=dict(showbackground=True, showticklabels=True, title='')
#                     )
#                 ))

# fig.show()

driver.close()
from flask import Flask, request, jsonify

import llm_calls
from utils import rag_utils
from server import config
import ghhops_server as hs
import os

from topologicpy import Topology, CellComplex

# import rhinoinside
# rhinoinside.load("C:\Program Files\Rhino 8\System", "net48")
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

# @hops.component(
#     '/generate_graph',
#     name="Generate graph",
#     inputs = [
#         hs.HopsMesh("meshIn", "M", "mesh geometry", access=hs.HopsParamAccess.LIST)
#     ]
# )
# def generate_graph(meshIn):
#     # topologies = [tpy.topology.topology.ByGeometry(m.Vertices) for m in meshIn]
#     meshVerts = [m.Vertices for m in meshIn]
#     print(meshVerts[0])
#     # topoList = [Topology.Topology.ByGeometry(mt.ToFloatArray()) for mt in meshVerts]
#     # print(len(topoList))
@hops.component(
    '/generate_graph',
    name="Generate graph",
    inputs = [
        hs.HopsMesh("meshIn", "M", "mesh geometry", access=hs.HopsParamAccess.LIST),
        hs.HopsBoolean("run", "r", "run the graph generation")
    ]
)
def generate_graph(meshIn, run: bool):
    # Create mesh data dictionary with cells
    mesh_data = {
        'vertices': [],
        'faces': [],
        'edges': [],
        'cells': []  # List of face indices that form each cell
    }
    
    vertex_offset = 0
    for mesh_index, mesh in enumerate(meshIn):
        # Get vertices
        vertices = [[v.X, v.Y, v.Z] for v in mesh.Vertices]
        
        # Get faces
        faces = []
        for i in range(mesh.Faces.Count):
            face = mesh.Faces[i]
            if face.IsTriangle:
                faces.append([face.A + vertex_offset, face.B + vertex_offset, face.C + vertex_offset])
            else:
                faces.append([face.A + vertex_offset, face.B + vertex_offset, 
                            face.C + vertex_offset, face.D + vertex_offset])
        
        # Get edges
        edges = [[edge.FromIndex + vertex_offset, edge.ToIndex + vertex_offset] 
                for edge in mesh.TopologyEdges]
        
        # Create a cell from all faces in this mesh
        face_indices = list(range(len(mesh_data['faces']), len(mesh_data['faces']) + len(faces)))
        mesh_data['cells'].append(face_indices)
        
        # Update the mesh data
        mesh_data['vertices'].extend(vertices)
        mesh_data['faces'].extend(faces)
        mesh_data['edges'].extend(edges)
        
        # Update vertex offset for next mesh
        vertex_offset += len(vertices)
    
    # Create topology using ByMeshData
    try:
        topology = Topology.Topology.ByMeshData(mesh_data)
        print(f"Created topology with {len(mesh_data['cells'])} cells")
        return topology
    except Exception as e:
        print(f"Error creating topology: {str(e)}")
        print(f"Mesh data stats:")
        print(f"Vertices: {len(mesh_data['vertices'])}")
        print(f"Faces: {len(mesh_data['faces'])}")
        print(f"Edges: {len(mesh_data['edges'])}")
        print(f"Cells: {len(mesh_data['cells'])}")
        return None
    
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

if __name__ == '__main__':
    app.run(debug=False)


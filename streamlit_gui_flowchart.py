import networkx as nx
import plotly.graph_objects as go
import streamlit as st
import re

def parse_log_flowchart(logs):
    """
    Parse logs to extract flow steps and threads, and build a directed graph.
    Handles log lines in the format:
    timestamp [INFO] [id=...] [thread=...] [function=...] [description=...]
    Each log line becomes a node, connected to the previous node in the same thread if possible.
    If a new thread appears, connect its first node to the last node in any other thread with the same id.
    Returns a networkx DiGraph.
    """
    G = nx.DiGraph()
    thread_last_node = {}  # thread -> last node_id
    id_last_node = {}      # id -> last node_id (across all threads)
    log_dicts = []
    # Regex to parse the log line (fixed escaping)
    log_re = re.compile(r"^(.*?) \[INFO\] \[id=([^\]]+)\] \[thread=([^\]]+)\] \[function=([^\]]+)\] \[description=([^\]]*)\]")
    for line in logs.splitlines():
        m = log_re.match(line)
        if m:
            timestamp, log_id, thread, function, description = m.groups()
            log_dicts.append({
                'timestamp': timestamp.strip(),
                'id': log_id.strip(),
                'thread': thread.strip(),
                'function': function.strip(),
                'description': description.strip(),
                'raw': line.strip()
            })
    # Build nodes and edges
    for i, log in enumerate(log_dicts):
        node_id = f"{log['id']}:{log['thread']}:{i}"
        # node_label = f"{log['description']}\n({log['function']}, {log['thread']})"
        node_label = f"{log['function']}"
        G.add_node(node_id, label=node_label, thread=log['thread'], log_id=log['id'], function=log['function'], timestamp=log['timestamp'])
        # Connect to previous node in the same thread
        if log['thread'] in thread_last_node:
            G.add_edge(thread_last_node[log['thread']], node_id)
        else:
            # If this is the first node in this thread, connect to last node in any other thread with same id
            if log['id'] in id_last_node:
                G.add_edge(id_last_node[log['id']], node_id)
        thread_last_node[log['thread']] = node_id
        id_last_node[log['id']] = node_id
    return G

def plot_flowchart(G):
    if len(G.nodes) == 0:
        return None, None
    # --- Top-down layout without graphviz ---
    # Assign y by node order (top to bottom), x by thread (group nodes by thread)
    threads = list({G.nodes[n]['thread'] for n in G.nodes})
    thread_x = {thread: i for i, thread in enumerate(sorted(threads))}
    node_order = list(G.nodes)
    node_pos = {}
    for idx, node in enumerate(node_order):
        thread = G.nodes[node]['thread']
        x = thread_x[thread]
        y = -idx  # negative so top node is at top
        node_pos[node] = (x, y)
    pos = node_pos
    edge_x = []
    edge_y = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=1, color='#888'),
        hoverinfo='none',
        mode='lines')
    node_x = []
    node_y = []
    node_text = []
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_text.append(G.nodes[node]['label'])
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        text=node_text,
        textposition='top center',
        marker=dict(size=20, color='LightSkyBlue'),
        hoverinfo='text')
    fig = go.Figure(data=[edge_trace, node_trace],
                    layout=go.Layout(
                        showlegend=False,
                        hovermode='closest',
                        margin=dict(b=20,l=5,r=5,t=40),
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)))
    st.session_state["flowchart_count"] = st.session_state.get("flowchart_count", 0) + 1
    flowchart_key = f"flowchart_{st.session_state['flowchart_count']}"
    return fig, flowchart_key

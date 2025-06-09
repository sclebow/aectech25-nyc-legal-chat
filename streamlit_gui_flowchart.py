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
    # Sort log_dicts by timestamp (oldest to newest)
    from datetime import datetime
    def parse_ts(ts):
        # Try to parse common timestamp formats, fallback to string
        for fmt in ("%Y-%m-%d %H:%M:%S,%f", "%Y-%m-%d %H:%M:%S", "%H:%M:%S,%f", "%H:%M:%S"):
            try:
                return datetime.strptime(ts, fmt)
            except Exception:
                continue
        return ts
    log_dicts.sort(key=lambda d: parse_ts(d['timestamp']))

    # Build the graph: each log line is a node, in order
    prev_node = None
    for idx, log in enumerate(log_dicts):
        node_id = idx  # simple integer node id in order
        label = log["function"]
        G.add_node(node_id, label=label, **log)
        if prev_node is not None:
            G.add_edge(prev_node, node_id)
        prev_node = node_id

    return G

def plot_flowchart(G):
    if len(G.nodes) == 0:
        return None, None
    # --- Layout: columns for threads, y by global timestamp difference ---
    node_order = list(G.nodes)
    node_pos = {}
    from datetime import datetime
    # Gather thread info and timestamps
    thread_first_ts = {}
    node_thread = {}
    timestamps = []
    for node in node_order:
        ts = G.nodes[node].get('timestamp', None)
        thread = G.nodes[node].get('thread', 'default')
        node_thread[node] = thread
        # Parse timestamp
        parsed = None
        for fmt in ("%Y-%m-%d %H:%M:%S,%f", "%Y-%m-%d %H:%M:%S", "%H:%M:%S,%f", "%H:%M:%S"):
            try:
                parsed = datetime.strptime(ts, fmt)
                break
            except Exception:
                continue
        timestamps.append(parsed)
        if thread not in thread_first_ts and parsed is not None:
            thread_first_ts[thread] = parsed
    # Order threads by first timestamp (main/earliest on left)
    ordered_threads = sorted(thread_first_ts.items(), key=lambda x: x[1] if x[1] is not None else datetime.max)
    thread_to_x = {t[0]: i for i, t in enumerate(ordered_threads)}
    # For threads with no timestamp, put them at the end
    for thread in set(node_thread.values()):
        if thread not in thread_to_x:
            thread_to_x[thread] = len(thread_to_x)
    # Calculate global y positions: evenly spaced by timestamp group
    # Use a threshold to group nodes with similar timestamps
    from datetime import timedelta
    time_threshold = timedelta(seconds=0.0001)  # You can adjust this threshold
    node_ts_pairs = list(zip(node_order, timestamps))
    # Sort by timestamp, fallback to original order if missing
    node_ts_pairs_sorted = sorted(node_ts_pairs, key=lambda x: x[1] if x[1] is not None else datetime.max)
    y_group = 0
    last_ts = None
    node_to_ygroup = {}
    for node, ts in node_ts_pairs_sorted:
        if ts is None:
            # If no timestamp, treat as new group
            y_group += 1
            node_to_ygroup[node] = y_group
            last_ts = None
        else:
            if last_ts is None or (ts - last_ts) > time_threshold:
                y_group += 1
            node_to_ygroup[node] = y_group
            last_ts = ts
    # Assign node positions
    for idx, node in enumerate(node_order):
        x = thread_to_x[node_thread[node]]
        y = -node_to_ygroup[node]  # Evenly spaced by group
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
    node_y_list = []
    node_text = []
    node_color = []
    # Assign a color to each thread using a plotly color scale
    threads = [G.nodes[node].get('thread', 'default') for node in G.nodes()]
    unique_threads = list(sorted(set(threads)))
    import plotly.colors
    color_scale = plotly.colors.sample_colorscale('Plasma', [i/(max(1,len(unique_threads)-1)) for i in range(len(unique_threads))])
    thread_to_color = {t: color_scale[i % len(color_scale)] for i, t in enumerate(unique_threads)}
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y_list.append(y)
        node_text.append(G.nodes[node]['label'])
        thread = G.nodes[node].get('thread', 'default')
        node_color.append(thread_to_color.get(thread, '#cccccc'))
    node_trace = go.Scatter(
        x=node_x, y=node_y_list,
        mode='markers+text',
        text=node_text,
        textposition='top center',
        marker=dict(size=20, color=node_color),
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

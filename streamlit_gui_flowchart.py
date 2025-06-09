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
    # Build edges: connect each node to the next in the same thread
    # If a node is the last in its thread and not in the main thread, connect to the next node in the main thread
    # Assume the main thread is the first in ordered_threads
    main_thread = ordered_threads[0][0] if ordered_threads else None
    thread_nodes = {}
    for idx, node in enumerate(node_order):
        thread = node_thread[node]
        thread_nodes.setdefault(thread, []).append((idx, node))
    edges = []
    for thread, nodes in thread_nodes.items():
        nodes_sorted = sorted(nodes, key=lambda x: x[0])
        for i in range(len(nodes_sorted) - 1):
            edges.append((nodes_sorted[i][1], nodes_sorted[i+1][1]))
        # If not main thread, connect last node to next node in main thread (by y-group)
        if thread != main_thread and main_thread in thread_nodes:
            last_idx, last_node = nodes_sorted[-1]
            # Find the next main thread node with a higher y-group
            last_ygroup = node_to_ygroup[last_node]
            main_nodes = thread_nodes[main_thread]
            for main_idx, main_node in main_nodes:
                if node_to_ygroup[main_node] > last_ygroup:
                    edges.append((last_node, main_node))
                    break
    # Add: first node of a non-main thread connects to closest previous node of main thread
    for thread, nodes in thread_nodes.items():
        if thread != main_thread and main_thread in thread_nodes:
            first_idx, first_node = sorted(nodes, key=lambda x: x[0])[0]
            first_ygroup = node_to_ygroup[first_node]
            main_nodes = thread_nodes[main_thread]
            # Find the main thread node with the highest y-group less than or equal to first_ygroup
            prev_main = None
            prev_main_ygroup = -1
            for main_idx, main_node in main_nodes:
                main_ygroup = node_to_ygroup[main_node]
                if main_ygroup <= first_ygroup and main_ygroup > prev_main_ygroup:
                    prev_main = main_node
                    prev_main_ygroup = main_ygroup
            if prev_main is not None:
                edges.append((prev_main, first_node))
    edge_x = []
    edge_y = []
    for src, dst in edges:
        x0, y0 = pos[src]
        x1, y1 = pos[dst]
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

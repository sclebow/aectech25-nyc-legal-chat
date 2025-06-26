import networkx as nx
import plotly.graph_objects as go
import streamlit as st
import re

def parse_log_line(line):
    # Example: 2025-06-08 22:04:14,439 [INFO] [id=...] [thread=...] [function=...] [called_by=...] [description=...]
    parts = line.split('[')
    timestamp = parts[0].strip()
    fields = {}
    for part in parts[1:]:
        if '=' in part:
            key, value = part.split('=', 1)
            fields[key.strip('] ')] = value.strip('] ')
    return {
        'timestamp': timestamp,
        **fields,
        'raw': line.strip()
    }

def parse_log_flowchart(logs):
    """
    Parse logs to extract flow steps and threads, and build a directed graph.
    Handles log lines in the format:
    timestamp [INFO] [id=...] [thread=...] [parent=...] [function=...] [called_by=...] [description=...]
    Each log line becomes a node. Edges are formed based on parent thread relationships and intra-thread order.
    Returns a networkx DiGraph.
    """
    G = nx.DiGraph()
    log_dicts = []
    for line in logs.splitlines():
        if '[INFO]' not in line:
            continue
        log = parse_log_line(line)
        # Only add if required fields are present
        if all(k in log for k in ('id', 'thread', 'function', 'description', 'parent', 'called_by')):
            log_dicts.append(log)
    # Sort log_dicts by timestamp (oldest to newest)
    from datetime import datetime
    def parse_ts(ts):
        for fmt in ("%Y-%m-%d %H:%M:%S,%f", "%Y-%m-%d %H:%M:%S", "%H:%M:%S,%f", "%H:%M:%S"):
            try:
                return datetime.strptime(ts, fmt)
            except Exception:
                continue
        return ts
    log_dicts.sort(key=lambda d: parse_ts(d['timestamp']))
    # Build the graph: each log line is a node, in order
    for idx, log in enumerate(log_dicts):
        node_id = idx
        label = log["function"]
        G.add_node(node_id, label=label, **log)
    # Build thread index: thread -> list of node indices (in order)
    from collections import defaultdict
    thread_nodes = defaultdict(list)
    for idx, log in enumerate(log_dicts):
        thread_nodes[log['thread']].append(idx)
    # Build parent mapping: thread -> parent thread
    thread_parent = {}
    for log in log_dicts:
        thread = log['thread']
        parent = log['parent']
        if thread not in thread_parent:
            thread_parent[thread] = parent
    # 1. Intra-thread edges (prev/next)
    for thread, nodes in thread_nodes.items():
        for i, node in enumerate(nodes):
            if i > 0:
                G.add_edge(nodes[i-1], node)  # prev -> curr
            if i < len(nodes)-1:
                G.add_edge(node, nodes[i+1])  # curr -> next
    # 2. First node in thread: connect to closest previous node in parent thread
    for thread, nodes in thread_nodes.items():
        first_node = nodes[0]
        parent_thread = thread_parent.get(thread, None)
        if parent_thread and parent_thread in thread_nodes:
            # Find the closest previous node in parent thread (by index)
            parent_indices = [idx for idx in thread_nodes[parent_thread] if idx < first_node]
            if parent_indices:
                closest_prev = max(parent_indices)
                G.add_edge(closest_prev, first_node)
    # 3. Last node in thread: connect to next node in parent thread, or recursively up
    def find_next_in_parent_chain(curr_idx, parent_thread):
        # Find the next node in parent_thread after curr_idx
        while parent_thread:
            if parent_thread in thread_nodes:
                parent_indices = [idx for idx in thread_nodes[parent_thread] if idx > curr_idx]
                if parent_indices:
                    return min(parent_indices)
                # If not found, go up the parent chain
                parent_thread = thread_parent.get(parent_thread, None)
            else:
                break
        return None
    for thread, nodes in thread_nodes.items():
        last_node = nodes[-1]
        parent_thread = thread_parent.get(thread, None)
        next_in_parent = find_next_in_parent_chain(last_node, parent_thread)
        if next_in_parent is not None:
            G.add_edge(last_node, next_in_parent, weight=3.)
    # Check for first node in each thread and connect to the most recent node in the parent thread, if that node is not already connected upstream
    for thread, nodes in thread_nodes.items():
        if not nodes:
            continue
        first_node = nodes[0]
        parent_thread = thread_parent.get(thread, None)
        if parent_thread and parent_thread in thread_nodes:
            # Find the most recent node in parent thread
            parent_indices = [idx for idx in thread_nodes[parent_thread] if idx < first_node]
            if parent_indices:
                closest_prev = max(parent_indices)
                # Only connect if only connected to one node
                if G.in_degree(closest_prev) == 1 and G.out_degree(first_node) == 0:
                    G.add_edge(closest_prev, first_node, weight=2.)
    return G

def plot_flowchart(G):
    if len(G.nodes) == 0:
        return None, None
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
    # Build thread parent mapping
    thread_parent = {}
    for node in G.nodes:
        thread = G.nodes[node].get('thread', 'default')
        parent = G.nodes[node].get('parent', None)
        if thread not in thread_parent and parent is not None:
            thread_parent[thread] = parent
    # Build parent -> children mapping
    from collections import defaultdict
    parent_to_children = defaultdict(list)
    for thread, parent in thread_parent.items():
        if parent is not None:
            parent_to_children[parent].append(thread)
    # Find root threads (no parent or parent not in thread_first_ts)
    all_threads = set(node_thread.values())
    root_threads = [t for t in all_threads if thread_parent.get(t, None) not in all_threads]
    # Recursively order threads: for each parent, order children by first_ts DESC (latest first)
    def order_threads(parent, x_list):
        children = parent_to_children.get(parent, [])
        # Sort children by first_ts DESC (latest first)
        children_sorted = sorted(children, key=lambda t: thread_first_ts.get(t, datetime.max), reverse=True)
        for child in children_sorted:
            x_list.append(child)
            order_threads(child, x_list)
    # Start with root threads, order by first_ts ASC (earliest first)
    root_threads_sorted = sorted(root_threads, key=lambda t: thread_first_ts.get(t, datetime.max))
    ordered_threads = []
    for root in root_threads_sorted:
        ordered_threads.append(root)
        order_threads(root, ordered_threads)
    # For threads with no timestamp, put them at the end
    for thread in all_threads:
        if thread not in ordered_threads:
            ordered_threads.append(thread)
    thread_to_x = {t: i for i, t in enumerate(ordered_threads)}
    # Calculate global y positions: evenly spaced by timestamp order (no threshold)
    node_ts_pairs = list(zip(node_order, timestamps))
    # Sort by timestamp, fallback to original order if missing
    node_ts_pairs_sorted = sorted(node_ts_pairs, key=lambda x: x[1] if x[1] is not None else datetime.max)
    node_to_ygroup = {node: i for i, (node, _) in enumerate(node_ts_pairs_sorted)}
    # Assign node positions
    for idx, node in enumerate(node_order):
        x = thread_to_x[node_thread[node]]
        y = -node_to_ygroup[node]  # Evenly spaced by timestamp order
        node_pos[node] = (x, y)
    pos = node_pos
    # Extract edges from the graph
    edges = list(G.edges())
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
    color_scale = plotly.colors.sample_colorscale('jet', [i/(max(1,len(unique_threads)-1)) for i in range(len(unique_threads))])
    thread_to_color = {t: color_scale[i % len(color_scale)] for i, t in enumerate(unique_threads)}
    # Calculate time elapsed from the very first node's timestamp
    # Find the minimum (earliest) timestamp among all nodes
    valid_timestamps = [ts for ts in timestamps if ts is not None]
    if valid_timestamps:
        min_timestamp = min(valid_timestamps)
    else:
        min_timestamp = None
    for idx, node in enumerate(G.nodes()):
        x, y = pos[node]
        node_x.append(x)
        node_y_list.append(y)
        # Updated hover text to show thread, parent, called_by, description, and elapsed time
        thread = G.nodes[node].get('thread', 'default')
        parent = G.nodes[node].get('parent', 'N/A')
        called_by = G.nodes[node].get('called_by', 'N/A')
        description = G.nodes[node].get('description', 'No description')
        timestamp = G.nodes[node].get('timestamp', 'N/A')
        label = G.nodes[node]['label']
        # Calculate elapsed time from the first node
        elapsed_str = 'N/A'
        node_ts = timestamps[idx]
        if min_timestamp is not None and node_ts is not None:
            elapsed = node_ts - min_timestamp
            # Format as H:MM:SS.sss
            total_seconds = elapsed.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            seconds = total_seconds % 60
            elapsed_str = f"{hours}:{minutes:02d}:{seconds:06.3f}"
        hover_text = f"{label}<br>Thread: {thread}<br>Parent: {parent}<br>Called by: {called_by}<br>Description: {description}<br>Elapsed: {elapsed_str}"
        node_text.append(hover_text)
        node_color.append(thread_to_color.get(thread, '#cccccc'))
    node_trace = go.Scatter(
        x=node_x, y=node_y_list,
        mode='markers+text',
        text=[G.nodes[node]['label'] for node in G.nodes()],
        textposition='top center',
        marker=dict(size=20, color=node_color),
        hoverinfo='text',
        hovertext=node_text
    )
    fig = go.Figure(data=[edge_trace, node_trace],
                    layout=go.Layout(
                        showlegend=False,
                        hovermode='closest',
                        margin=dict(b=20,l=5,r=5,t=40),
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        height=800  # Set the height of the flow chart here
                    ))
    st.session_state["flowchart_count"] = st.session_state.get("flowchart_count", 0) + 1
    flowchart_key = f"flowchart_{st.session_state['flowchart_count']}"
    return fig, flowchart_key

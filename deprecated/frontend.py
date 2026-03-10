import streamlit as st
from streamlit_mermaid import st_mermaid
import requests
import json
import re
import base64

# --- PAGE CONFIG ---
st.set_page_config(layout="wide", page_title="AutoGraph")

# --- CSS STYLING ---
st.markdown("""
<style>
    .stApp { background-color: white; color: black; }
    .block-container { padding-top: 1rem !important; }
    .stMarkdown hr { margin-top: 0.5rem !important; margin-bottom: 0.5rem !important; }
    h2 { margin-top: 0.5rem !important; }
    
    /* Force the component to take 100% of the column */
    iframe[title*="mermaid"] {
        width: 100% !important;
        min-width: 100% !important;
        display: block !important;
        border: 1px solid #ddd;
        border-radius: 8px;
        background-color: #f9f9f9;
    }
    
    /* Button centering styles */
    .center-btn {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# --- STATE MANAGEMENT ---
if "run_id" not in st.session_state:
    st.session_state.run_id = 0
if "mermaid_code" not in st.session_state:
    st.session_state.mermaid_code = 'graph TD\n A["Start"] --> B["Your Flowchart"]'

st.title("AutoGraph - Automated Diagramming Engine")

# --- HELPER FUNCTIONS ---
def get_node_info(code):
    """Parse node IDs and types (action/decision) from Mermaid code."""
    lines = code.strip().split("\n")
    if not lines:
        return [], [], set()
    
    node_ids = []
    decision_nodes = set()
    seen = set()
    
    node_def_pattern = re.compile(r'\b([A-Za-z_]\w*)\s*[\[{(]')
    diamond_pattern = re.compile(r'\b([A-Za-z_]\w*)\s*\{')
    
    for line in lines[1:]:
        for match in node_def_pattern.finditer(line):
            node_id = match.group(1)
            if node_id not in seen and node_id not in ("graph", "flowchart", "style", "classDef", "click"):
                seen.add(node_id)
                node_ids.append(node_id)
        for match in diamond_pattern.finditer(line):
            decision_nodes.add(match.group(1))
    
    outgoing = set()
    arrow_pattern = re.compile(r'\b([A-Za-z_]\w*)\s*--')
    for line in lines[1:]:
        for match in arrow_pattern.finditer(line):
            outgoing.add(match.group(1))
    
    terminal_nodes = set(node_ids) - outgoing
    
    return node_ids, terminal_nodes, decision_nodes

def apply_colors_to_mermaid(code, action_color, decision_color, start_color, end_color):
    """Append style lines to Mermaid code for dynamic coloring."""
    node_ids, terminal_nodes, decision_nodes = get_node_info(code)
    
    if not node_ids:
        return code
    
    lines = code.strip().split("\n")
    lines = [l for l in lines if not l.strip().startswith("style ")]
    
    start_node = node_ids[0] if node_ids else None
    style_lines = []
    
    for node_id in node_ids:
        if node_id == start_node:
            color = start_color
        elif node_id in terminal_nodes:
            color = end_color
        elif node_id in decision_nodes:
            color = decision_color
        else:
            color = action_color
        style_lines.append(f"style {node_id} fill:{color},color:#fff,stroke:{color}")
    
    return "\n".join(lines + style_lines)

# --- TOP SECTION: INPUT ---
with st.expander("Configuration & Input Logic", expanded=True):
    user_text = st.text_area(
        "Paste process text:", 
        height=300, 
        value="To make coffee: Grind beans. Boil water. Pour water over grounds."
    )
    
    col_opt1, col_opt2 = st.columns([1, 3])
    with col_opt1:
        orientation = st.selectbox("Orientation", ["Top-Down (Vertical)", "Left-Right (Horizontal)"])
        orientation_code = "TD" if "Top-Down" in orientation else "LR"
    with col_opt2:
        color_cols = st.columns(4)
        action_color = color_cols[0].color_picker("Action", "#4CAF50")
        decision_color = color_cols[1].color_picker("Decision", "#2196F3")
        start_color = color_cols[2].color_picker("Start", "#9C27B0")
        end_color = color_cols[3].color_picker("End", "#F44336")

    if st.button("Generate Flowchart", type="primary", use_container_width=True):
        with st.spinner("Talking to Backend..."):
            try:
                # IMPORTANT: Ensure this port (5000 or 8000) matches your FastAPI backend
                response = requests.post(
                    "http://127.0.0.1:5000/generate",
                    json={"text": user_text, "orientation": orientation_code}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    st.session_state.mermaid_code = data["mermaid_code"]
                    
                    # Handle backend warnings/info if your backend sends them
                    attempts = data.get("attempts", 1)
                    if attempts > 1:
                        st.info(f"Generated after {attempts} validation attempt(s)")
                    if "warning" in data:
                        st.warning(f"{data['warning']}")
                        
                    st.session_state.run_id += 1
                    st.rerun()
                else:
                    st.error(f"Backend Error: {response.text}")
            except Exception as e:
                st.error(f"Connection Error: {e}")

st.markdown("---")

# --- MERMAID LIVE EDITOR LAYOUT ---
# 30/70 split: Code takes 30% width, Diagram takes 70% width
col_code, col_diagram = st.columns([3, 7], gap="large")

with col_code:
    st.markdown("### Code")
    def update_code():
        new_val = st.session_state[f"editor_{st.session_state.run_id}"]
        st.session_state.mermaid_code = new_val

    st.text_area(
        label="Mermaid Code",
        height=550,
        value=st.session_state.mermaid_code,
        key=f"editor_{st.session_state.run_id}",
        on_change=update_code,
        label_visibility="collapsed"
    )

with col_diagram:
    st.markdown("### Preview")
    colored_code = apply_colors_to_mermaid(
        st.session_state.mermaid_code,
        action_color, decision_color, start_color, end_color
    )
    
    try:
        st_mermaid(colored_code, height="550px")
    except Exception:
        st.warning("Syntax Error in code")

st.markdown("---")

# --- CENTERED EXPORT BUTTONS ---
spacer_left, center_buttons, spacer_right = st.columns([1, 1, 1])

with center_buttons:
    btn_col1, btn_col2 = st.columns(2)
    
    with btn_col1:
        # We export the colored_code (without the forced 100% width config)
        mermaid_b64 = base64.urlsafe_b64encode(colored_code.encode("utf-8")).decode("utf-8")
        img_url = f"https://mermaid.ink/img/{mermaid_b64}"
        
        try:
            img_response = requests.get(img_url, timeout=15)
            if img_response.status_code == 200:
                st.download_button(
                    label="Download PNG",
                    data=img_response.content,
                    file_name="flowchart.png",
                    mime="image/png",
                    use_container_width=True
                )
            else:
                st.warning("Render failed. Try simplifying.")
        except Exception:
            st.warning("Download unavailable.")
    
    with btn_col2:
        state = {"code": colored_code, "mermaid": {"theme": "default"}}
        b64_str = base64.b64encode(json.dumps(state).encode("utf-8")).decode("utf-8")
        href = f"https://mermaid.live/edit#base64:{b64_str}"
        st.markdown(
            f'<a href="{href}" target="_blank" class="center-btn">'
            f'<button style="background:#4CAF50;color:white;border:none;padding:10px;border-radius:4px;cursor:pointer;width:100%;">'
            f'Open in Mermaid Live</button></a>', 
            unsafe_allow_html=True
        )
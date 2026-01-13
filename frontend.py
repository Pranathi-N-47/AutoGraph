import streamlit as st
from streamlit_mermaid import st_mermaid
import requests
import json
import base64

# --- PAGE CONFIG ---
st.set_page_config(layout="wide", page_title="AutoGraph Pro")
st.markdown("<style>.stApp { background-color: white; color: black; }</style>", unsafe_allow_html=True)

# --- STATE MANAGEMENT ---
# We use 'run_id' to force the text box to refresh
if "run_id" not in st.session_state:
    st.session_state.run_id = 0
if "mermaid_code" not in st.session_state:
    st.session_state.mermaid_code = "graph TD\n A[Start] --> B[Your Flowchart]"

st.title("⚡ AutoGraph Pro")

# --- SIDEBAR ---
api_key = st.sidebar.text_input("Groq API Key", type="password")

# --- UI LAYOUT ---
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Input Logic")
    user_text = st.text_area("Paste process text:", height=300, 
        value="To make coffee: Grind beans. Boil water. Pour water over grounds.")
    
    if st.button("✨ Generate Flowchart", type="primary"):
        if not api_key:
            st.warning("Please enter API Key.")
        else:
            with st.spinner("Talking to Backend..."):
                try:
                    response = requests.post(
                        "http://127.0.0.1:8000/generate",
                        json={"text": user_text, "api_key": api_key}
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # 1. Update the Data
                        st.session_state.mermaid_code = data["mermaid_code"]
                        
                        # 2. Increment run_id (This is the MAGIC FIX)
                        # This tells Streamlit: "The next text box is a totally new widget"
                        st.session_state.run_id += 1
                        
                        st.rerun()
                    else:
                        st.error(f"Backend Error: {response.text}")
                except Exception as e:
                    st.error(f"Connection Error: {e}")

with col2:
    st.subheader("2. Visual Diagram")
    
    # 1. VISUAL RENDER
    try:
        st_mermaid(st.session_state.mermaid_code, height="400px")
    except Exception:
        st.warning("Syntax Error in code")

    st.markdown("---")
    
    # 2. EDITABLE CODE
    st.markdown("**Mermaid Code (Editable):**")
    
    # CALLBACK: Updates state when you type manually
    def update_code():
        # We read the value from the specific dynamic key
        new_val = st.session_state[f"editor_{st.session_state.run_id}"]
        st.session_state.mermaid_code = new_val

    # DYNAMIC WIDGET
    # The key changes (editor_0, editor_1) every time the AI runs.
    # This forces the 'value' to actually update.
    st.text_area(
        label="Mermaid Code",
        height=200,
        value=st.session_state.mermaid_code,
        key=f"editor_{st.session_state.run_id}", # <--- DYNAMIC KEY
        on_change=update_code,
        label_visibility="collapsed"
    )

    # 3. EXPORT BUTTON
    if st.session_state.mermaid_code:
        state = {"code": st.session_state.mermaid_code, "mermaid": {"theme": "default"}}
        b64_str = base64.b64encode(json.dumps(state).encode("utf-8")).decode("utf-8")
        href = f"https://mermaid.live/edit#base64:{b64_str}"
        st.markdown(f'<a href="{href}" target="_blank"><button style="background:#4CAF50;color:white;border:none;padding:8px;border-radius:4px;">📥 Export Image</button></a>', unsafe_allow_html=True)
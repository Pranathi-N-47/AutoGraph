from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from groq import Groq
import uvicorn
import os
import re
import logging
import dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

dotenv.load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AutoGraph")

app = FastAPI(title="AutoGraph API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows any frontend to connect
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class FlowchartRequest(BaseModel):
    text: str
    orientation: str = "TD"  # TD (vertical) or LR (horizontal)

def clean_mermaid_code(raw_text):
    # Strip DeepSeek R1 / Qwen reasoning/thinking block
    raw_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
    
    # Remove markdown code fences
    clean = raw_text.replace("```mermaid", "").replace("```", "")
    
    lines = clean.split('\n')
    valid_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Strip inline comments
        line = re.sub(r'\s*%%.*$', '', line).strip()
        if not line:
            continue
        # Fix common special character issues in node text
        # Replace & with 'and' inside quoted text
        line = re.sub(r'(?<=")([^"]*?)&([^"]*?)(?=")', lambda m: m.group(1) + ' and ' + m.group(2), line)
        valid_lines.append(line)
    return "\n".join(valid_lines)

def strip_quoted_text(line):
    """Remove all quoted strings from a line for bracket analysis."""
    return re.sub(r'"[^"]*"', '""', line)

def validate_mermaid(code):
    """Validate Mermaid syntax and return (is_valid, list_of_errors)."""
    errors = []
    lines = code.strip().split("\n")
    
    if not lines or (len(lines) == 1 and not lines[0].strip()):
        return False, ["Empty code"]
    
    # 1. Check graph declaration
    first_line = lines[0].strip()
    if not re.match(r"^(graph|flowchart)\s+(TD|TB|BT|RL|LR)", first_line):
        errors.append(f"Invalid graph declaration: '{first_line}'. Must start with 'graph TD', 'flowchart LR', etc.")
    
    # 2. Check bracket balance (ignoring content inside quotes)
    for i, line in enumerate(lines[1:], start=2):
        stripped = strip_quoted_text(line)
        for open_char, close_char in [("[", "]"), ("{", "}"), ("(", ")")]:
            if stripped.count(open_char) != stripped.count(close_char):
                errors.append(f"Line {i}: Unbalanced '{open_char}{close_char}' in: {line.strip()}")
    
    # 3. Check for valid arrows (at least one connection should exist)
    arrow_pattern = re.compile(r"-->|---|==>|\-\.\->")
    has_arrows = any(arrow_pattern.search(line) for line in lines[1:])
    if not has_arrows and len(lines) > 1:
        errors.append("No valid arrows found. Use '-->', '---', '-.->',  or '==>' to connect nodes.")
    
    # 4. Check for empty node text like A[] or B{}
    empty_node = re.compile(r'[A-Za-z_]\w*\[\s*\]|[A-Za-z_]\w*\{\s*\}')
    for i, line in enumerate(lines, start=1):
        if empty_node.search(line):
            errors.append(f"Line {i}: Empty node text found in: {line.strip()}")
    
    # 5. Check for pipe issues in arrow labels (e.g., missing closing |)
    label_pattern = re.compile(r'-->\|[^|]*$')  # opening | without closing |
    for i, line in enumerate(lines[1:], start=2):
        if label_pattern.search(line):
            errors.append(f"Line {i}: Unclosed arrow label (missing '|') in: {line.strip()}")
    
    return (len(errors) == 0, errors)

# --- SYSTEM PROMPT TEMPLATE ---
_SYSTEM_PROMPT_TEMPLATE = """You are a strict code generator. Output ONLY Mermaid.js code.
IMPORTANT: Start the code with 'graph __ORIENTATION__'.

--- 1. NODE & TEXT RULES ---
- DEFAULT to Rectangle Nodes []: for steps (e.g., A["Open app"]).
- USE Diamond Nodes {} ONLY for checks/questions (e.g., B{"Is it valid?"}).
- TEXT: Keep it concise but retain keywords. Remove redundant words and pronouns like it, him, her, etc. Retain all important mentions though.
- QUOTES: ALWAYS wrap node text in quotes "".
- COMMENTS: DO NOT add any comments to the code.
- ESCAPE: Retain special chars like '?' or '!' inside the quotes.
- Always start with an action node and end with an action node.
- An action node can branch into multiple nodes if there are parallel actions happening simultaneously.

--- 2. ARROW RULES ---
- Action -> Action: Plain arrow (A --> B)
- Decision -> Action: Labeled arrow (B -->|Yes| C)
- Decision -> Decision: Labeled arrow (B -->|No| D)
- Labels: Use comparison operators like '<' and '>=' in place of words. Mention the quantity measured in the LHS with value in RHS.

--- 3. LOOPING LOGIC (HIGHEST PRIORITY) ---
- CRITICAL: If the text implies "repeat", "try again", "go back", "re-do", or "retry":
  1. Find the Node ID of the step we are returning to (e.g., Node A).
  2. Draw an arrow pointing to THAT ID (e.g., C --> A).
  3. DO NOT create a new node with duplicate text. NEVER duplicate a node that already exists.
  4. A loop means reusing an existing node ID, NOT creating a new node with the same label.

--- 4. EXAMPLES ---

Input: "Wake up. Eat. Work."
Output:
graph __ORIENTATION__
A["Wake up"] --> B["Eat"]
B --> C["Work"]

Input: "Check connection. If failed, wait 5s and check again. If success, login."
Output:
graph __ORIENTATION__
A{"Check connection"} -->|Failed| B["Wait 5s"]
B --> A
A -->|Success| C["Login"]

Input: "Submit form. Validate input. If invalid, show error and go back to form. If valid, save data."
Output:
graph __ORIENTATION__
A["Submit form"] --> B{"Validate input"}
B -->|Invalid| C["Show error"]
C --> A
B -->|Valid| D["Save data"]
"""

def get_system_prompt(orientation="TD"):
    return _SYSTEM_PROMPT_TEMPLATE.replace("__ORIENTATION__", orientation)

MAX_RETRIES = 3

@app.post("/generate")
def generate_flowchart(request: FlowchartRequest):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not set in .env file")
    
    try:
        client = Groq(api_key=api_key)
        
        orientation = request.orientation.upper()
        if orientation not in ("TD", "TB", "LR", "RL", "BT"):
            orientation = "TD"
        
        messages = [
            {"role": "system", "content": get_system_prompt(orientation)},
            {"role": "user", "content": f"Convert logic:\n{request.text}"}
        ]
        
        for attempt in range(1, MAX_RETRIES + 1):
            logger.info(f"--- Attempt {attempt}/{MAX_RETRIES} ---")
            
            response = client.chat.completions.create(
                model="qwen/qwen3-32b",
                messages=messages,
                temperature=0.0
            )
            
            raw_output = response.choices[0].message.content
            final_code = clean_mermaid_code(raw_output)
            
            logger.info(f"Generated code:\n{final_code}")
            
            is_valid, errors = validate_mermaid(final_code)
            
            if is_valid:
                # Ensure correct orientation in output
                final_code = re.sub(r'^(graph|flowchart)\s+(TD|TB|BT|RL|LR)', f'graph {orientation}', final_code)
                logger.info(f"Valid on attempt {attempt}")
                return {"mermaid_code": final_code, "attempts": attempt}
            
            logger.warning(f"Validation errors on attempt {attempt}:")
            for err in errors:
                logger.warning(f"  - {err}")
            
            if attempt < MAX_RETRIES:
                # Ask the model to fix its own output
                error_feedback = "\n".join(f"- {e}" for e in errors)
                messages.append({"role": "assistant", "content": raw_output})
                messages.append({
                    "role": "user",
                    "content": (
                        f"The Mermaid code you generated has syntax errors:\n{error_feedback}\n\n"
                        f"Please fix these errors and output ONLY the corrected Mermaid.js code."
                    )
                })
                logger.info(f"Requesting retry with error feedback...")
        
        # All retries exhausted — return best effort with a warning
        logger.warning(f"All {MAX_RETRIES} attempts exhausted. Returning best effort.")
        return {
            "mermaid_code": final_code,
            "attempts": MAX_RETRIES,
            "warning": f"Code may have syntax issues after {MAX_RETRIES} attempts: {'; '.join(errors)}"
        }

    except Exception as e:
        logger.error(f"Exception: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5000)
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from groq import Groq
import uvicorn

app = FastAPI(title="AutoGraph API")

class FlowchartRequest(BaseModel):
    text: str
    api_key: str

def clean_mermaid_code(raw_text):
    clean = raw_text.replace("```mermaid", "").replace("```", "")
    lines = clean.split('\n')
    valid_lines = []
    for line in lines:
        line = line.strip()
        if line:
            valid_lines.append(line)
    return "\n".join(valid_lines)

@app.post("/generate")
def generate_flowchart(request: FlowchartRequest):
    if not request.api_key:
        raise HTTPException(status_code=400, detail="API Key is missing")
    
    try:
        client = Groq(api_key=request.api_key)
        
        # UPDATED PROMPT: Specific Logic for Labels
        system_prompt = """
        You are a strict code generator. Output ONLY Mermaid.js code.
        
        CRITICAL SYNTAX RULES:
        1. Start with 'graph TD'.
        2. NODES:
           - Use quotes for ALL text.
           - Action: A["Do Something"]
           - Decision: B{"Is it working?"}
        
        3. ARROW LOGIC (FOLLOW STRICTLY):
           - IF the starting node is a DECISION {}:
             Use LABELS. Format: B -->|Yes| C
           
           - IF the starting node is an ACTION []:
             Use PLAIN arrows. Format: A --> B
             DO NOT put labels on action arrows.
        
        4. No intro text. No outro text.
        """
        
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Convert logic:\n{request.text}"}
            ],
            temperature=0.0
        )
        
        raw_output = response.choices[0].message.content
        final_code = clean_mermaid_code(raw_output)
        
        return {"mermaid_code": final_code}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
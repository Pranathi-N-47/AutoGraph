import re
import logging

logger = logging.getLogger("AutoGraph")

# ---------------------------------------------------------------------------
# Mermaid cleaning & validation
# ---------------------------------------------------------------------------

def clean_mermaid_code(raw_text: str) -> str:
    """Strip reasoning blocks, fences, comments, and fix common issues."""
    # Strip Qwen thinking blocks
    raw_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()

    # Remove markdown code fences
    clean = raw_text.replace("```mermaid", "").replace("```", "")

    lines = clean.split("\n")
    valid_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Strip inline comments
        line = re.sub(r"\s*%%.*$", "", line).strip()
        if not line:
            continue
        # Replace & with 'and' inside quoted text
        line = re.sub(
            r'(?<=")([^"]*?)&([^"]*?)(?=")',
            lambda m: m.group(1) + " and " + m.group(2),
            line,
        )
        valid_lines.append(line)
    return "\n".join(valid_lines)


def _strip_quoted_text(line: str) -> str:
    """Remove all quoted strings from a line for bracket analysis."""
    return re.sub(r'"[^"]*"', '""', line)


def validate_mermaid(code: str) -> tuple[bool, list[str]]:
    """Validate Mermaid syntax. Returns (is_valid, list_of_errors)."""
    errors = []
    lines = code.strip().split("\n")

    if not lines or (len(lines) == 1 and not lines[0].strip()):
        return False, ["Empty code"]

    # 1. Graph declaration
    first_line = lines[0].strip()
    if not re.match(r"^(graph|flowchart)\s+(TD|TB|BT|RL|LR)", first_line):
        errors.append(
            f"Invalid graph declaration: '{first_line}'. "
            "Must start with 'graph TD', 'flowchart LR', etc."
        )

    # 2. Bracket balance (ignoring quoted content)
    for i, line in enumerate(lines[1:], start=2):
        stripped = _strip_quoted_text(line)
        for open_char, close_char in [("[", "]"), ("{", "}"), ("(", ")")]:
            if stripped.count(open_char) != stripped.count(close_char):
                errors.append(
                    f"Line {i}: Unbalanced '{open_char}{close_char}' in: {line.strip()}"
                )

    # 3. At least one arrow
    arrow_pattern = re.compile(r"-->|---|==>|\-\.\->")
    has_arrows = any(arrow_pattern.search(line) for line in lines[1:])
    if not has_arrows and len(lines) > 1:
        errors.append(
            "No valid arrows found. Use '-->', '---', '-.->',  or '==>' to connect nodes."
        )

    # 4. No empty node text
    empty_node = re.compile(r"[A-Za-z_]\w*\[\s*\]|[A-Za-z_]\w*\{\s*\}")
    for i, line in enumerate(lines, start=1):
        if empty_node.search(line):
            errors.append(f"Line {i}: Empty node text found in: {line.strip()}")

    # 5. Unclosed arrow labels
    label_pattern = re.compile(r"-->\|[^|]*$")
    for i, line in enumerate(lines[1:], start=2):
        if label_pattern.search(line):
            errors.append(
                f"Line {i}: Unclosed arrow label (missing '|') in: {line.strip()}"
            )

    return (len(errors) == 0, errors)


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

# Mermaid syntax rules shared by both prompts — node shapes and arrow syntax.
_MERMAID_SYNTAX_RULES = """--- MERMAID SYNTAX RULES ---
- Rectangle nodes [] for actions/steps:   A["Label"]
- Diamond nodes {} for decisions/checks:  B{"Label?"}
_ NODE IDs: MUST be simple, single alphanumeric letters/words (e.g., A, B, Node1). NEVER use spaces, math symbols, or the full label text as the ID.
- Decision nodes must have atleast 2 outgoing arrows.
- ALWAYS wrap node text in double quotes.
- LINE BREAKS: Use <br> inside node labels (e.g., ["i=0<br>swapped=false"]). NEVER use \\n.
- DO NOT add comments to the code.
- Action → Action:            plain arrow:           A --> B
- Decision → Action/Decision: labeled arrow:         B -->|Yes| C  /  B -->|No| D
- Edge labels on decisions MUST use the condition value, not words where possible.
  e.g. prefer -->|< 3 attempts| over -->|retry limit not reached|
- Loop-back: reuse the existing node ID — never create a duplicate node with the same label."""


# Extra rules that only apply when interpreting natural language input.
_TEXT_DESIGN_RULES = """--- TEXT INTERPRETATION RULES ---
- Keep node labels concise: remove filler words and pronouns, retain all keywords.
- Retain special characters like '?' and '!' inside quotes.
- Always start with an action node and end with an action node.
- An action node may branch into multiple parallel nodes when the text implies simultaneous actions.
- If the text implies "repeat", "retry", "go back", or "try again", draw an arrow back
  to the existing node being revisited — do NOT create a new node with the same label."""


# Single loop-back example — the one behaviour worth showing rather than just describing.
_TEXT_EXAMPLES = """--- EXAMPLE (loop-back) ---

Input: "Check connection. If failed, wait 5s and check again. If success, login."
Output:
graph __ORIENTATION__
A{"Check connection"} -->|Failed| B["Wait 5s"]
B --> A
A -->|Success| C["Login"]"""


_VISION_RULES = """--- VISION TRANSCRIPTION RULES ---
1. EXACT CONTENT: Copy text/math exactly (e.g., "swap(A[i], A[i+1])") into ONE node. Do not split equations into floating nodes.
2. SHAPES: Rectangles/rounded → []. Nodes branching with Yes/No/True/False are ALWAYS diamonds {}.
3. EDGE LABELS: Words floating near lines (Yes, No, Then, Else) are edge labels (e.g., -->|Yes|), NOT standalone nodes.
4. STRICT TRACING: Connect nodes ONLY if physically linked by an arrow. Trace strictly from tail to head. Ignore visual proximity.
5. LOOPS: Carefully trace long lines (especially up the left/right margins) connecting back to earlier nodes.
6. ARROW-TO-ARROW: If arrow from a node points to another arrow's line, connect to the target node of that arrow.
7. TERMINAL NODES: Nodes with no outgoing physical arrows are terminal."""

_VISION_THINKING_BLOCK = (
    "--- REQUIRED THINKING PROCESS ---\n"
    "You MUST begin your response with a <think> block, but KEEP IT EXTREMELY BRIEF using SHORTHAND to minimize latency:\n\n"
    "<think>\n"
    "SHAPES: [R]=\"Text\", {D}=\"Text\"\n"
    "PATHS: [A] -> [B], {C} ->|Yes| [D]\n"
    "MARGINS: Note bottom-to-top loop lines.\n"
    "</think>\n\n"
    "After </think>, output ONLY the raw Mermaid.js code. No formatting ticks, no markdown."
)


def get_text_system_prompt(orientation: str = "TD") -> str:
    return (
        "You are a strict Mermaid.js code generator. Output ONLY Mermaid.js code.\n"
        f"Start the code with 'graph {orientation}'.\n\n"
        + _MERMAID_SYNTAX_RULES
        + "\n\n"
        + _TEXT_DESIGN_RULES
        + "\n\n"
        + _TEXT_EXAMPLES.replace("__ORIENTATION__", orientation)
    )


def get_vision_system_prompt(orientation: str = "TD") -> str:
    return (
        "You are a strict Mermaid.js transcriber. You convert flowchart images into Mermaid.js code.\n"
        f"Start the Mermaid code with 'graph {orientation}'.\n\n"
        + _VISION_THINKING_BLOCK
        + "\n"
        + _MERMAID_SYNTAX_RULES
        + "\n\n"
        + _VISION_RULES
    )
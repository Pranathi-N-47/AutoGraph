import re
import logging
import os

from groq import Groq
from shared import clean_mermaid_code, validate_mermaid, get_text_system_prompt

logger = logging.getLogger("AutoGraph.TextService")

MAX_RETRIES = 3


def generate_from_text(text: str, orientation: str = "TD") -> dict:
    """
    Convert a natural-language process description into Mermaid.js code.

    Returns a dict with keys:
        mermaid_code  – the generated (or best-effort) Mermaid code
        attempts      – number of LLM calls made
        warning       – present only when all retries are exhausted with errors
    """
    api_key = os.getenv("GROQ_API_KEY")
    client = Groq(api_key=api_key)

    messages = [
        {"role": "system", "content": get_text_system_prompt(orientation)},
        {"role": "user", "content": f"Convert logic:\n{text}"},
    ]

    final_code = ""
    errors: list[str] = []

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info(f"[TextService] Attempt {attempt}/{MAX_RETRIES}")

        response = client.chat.completions.create(
            model="qwen/qwen3-32b",
            messages=messages,
            temperature=0.0,
        )

        raw_output = response.choices[0].message.content
        final_code = clean_mermaid_code(raw_output)
        logger.info(f"[TextService] Generated:\n{final_code}")

        is_valid, errors = validate_mermaid(final_code)
        if is_valid:
            final_code = re.sub(
                r"^(graph|flowchart)\s+(TD|TB|BT|RL|LR)",
                f"graph {orientation}",
                final_code,
            )
            logger.info(f"[TextService] Valid on attempt {attempt}")
            return {"mermaid_code": final_code, "attempts": attempt}

        logger.warning(f"[TextService] Errors on attempt {attempt}: {errors}")

        if attempt < MAX_RETRIES:
            error_feedback = "\n".join(f"- {e}" for e in errors)
            messages.append({"role": "assistant", "content": raw_output})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"The Mermaid code you generated has syntax errors:\n{error_feedback}\n\n"
                        "Please fix these errors and output ONLY the corrected Mermaid.js code."
                    ),
                }
            )

    logger.warning(f"[TextService] All {MAX_RETRIES} attempts exhausted.")
    return {
        "mermaid_code": final_code,
        "attempts": MAX_RETRIES,
        "warning": f"Code may have syntax issues after {MAX_RETRIES} attempts: {'; '.join(errors)}",
    }
import re
import logging
import os
import io
import base64
from pathlib import Path

from openai import OpenAI
from shared import clean_mermaid_code, validate_mermaid, get_vision_system_prompt

logger = logging.getLogger("AutoGraph.VisionService")

VISION_MODEL = "qwen/qwen2.5-vl-72b-instruct"
MAX_RETRIES = 3

# Resize images to this width before sending — cuts image tokens significantly.
# Flowchart diagrams are readable at 1200px; going lower risks losing arrow details.
MAX_IMAGE_WIDTH = 1200

# Supported MIME types for uploaded images
SUPPORTED_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def _resize_image(image_bytes: bytes) -> tuple[bytes, str]:
    """
    Resize image to MAX_IMAGE_WIDTH if wider, preserving aspect ratio.
    Returns (image_bytes, mime_type) — always PNG after resize.
    Returns original bytes and detected mime if small enough or Pillow unavailable.
    """
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        if img.width <= MAX_IMAGE_WIDTH:
            fmt = img.format or "PNG"
            return image_bytes, f"image/{fmt.lower()}"
        ratio = MAX_IMAGE_WIDTH / img.width
        new_size = (MAX_IMAGE_WIDTH, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        resized = buf.getvalue()
        logger.info(
            f"[VisionService] Resized image → {MAX_IMAGE_WIDTH}px wide "
            f"({len(image_bytes) // 1024}KB → {len(resized) // 1024}KB)"
        )
        return resized, "image/png"
    except ImportError:
        logger.warning("[VisionService] Pillow not installed — skipping resize. Run: pip install Pillow")
        return image_bytes, "image/png"
    except Exception as e:
        logger.warning(f"[VisionService] Resize failed ({e}) — using original image.")
        return image_bytes, "image/png"


def generate_from_image(
    image_bytes: bytes,
    mime_type: str,
    orientation: str = "TD",
) -> dict:
    """
    Convert a flowchart image into Mermaid.js code using Qwen via OpenRouter.

    Args:
        image_bytes:  Raw bytes of the uploaded image file.
        mime_type:    MIME type string, e.g. 'image/png'.
        orientation:  Mermaid graph orientation ('TD', 'LR', etc.).

    Returns a dict with keys:
        mermaid_code  – the generated (or best-effort) Mermaid code
        attempts      – number of LLM calls made
        warning       – present only when all retries are exhausted with errors
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set in environment variables")

    # Initialize OpenAI client pointed to OpenRouter
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    # Resize before sending to reduce image token cost
    image_bytes, mime_type = _resize_image(image_bytes)

    # Convert bytes to Base64 data URI format for the API
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    image_url = f"data:{mime_type};base64,{base64_image}"

    user_prompt = (
        "This image contains a flowchart or process diagram.\n\n"
        "Follow the system instructions exactly:\n"
        "1. Start your response with a <think> block where you list every node "
        "and every arrow (tracing each arrowhead to its precise target), then "
        "perform the terminal check.\n"
        "2. After </think>, output ONLY the Mermaid.js code — no explanation, "
        "no markdown fences.\n\n"
        "Pay special attention to arrows that travel far across the diagram "
        "or point against the main flow direction — these must not be omitted."
    )

    system_prompt = get_vision_system_prompt(orientation)

    # Setup the conversation history using standard OpenAI formatting
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        }
    ]

    final_code = ""
    errors: list[str] = []

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info(f"[VisionService] Attempt {attempt}/{MAX_RETRIES}")

        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=messages,
            temperature=0.0,
            max_tokens=2048,
        )

        raw_output = response.choices[0].message.content

        # Log the thinking block separately for easier debugging
        think_match = re.search(r"<think>(.*?)</think>", raw_output, re.DOTALL)
        if think_match:
            logger.info(f"[VisionService] Reasoning:\n{think_match.group(1).strip()}")

        final_code = clean_mermaid_code(raw_output)
        logger.info(f"[VisionService] Generated:\n{final_code}")

        is_valid, errors = validate_mermaid(final_code)
        if is_valid:
            final_code = re.sub(
                r"^(graph|flowchart)\s+(TD|TB|BT|RL|LR)",
                f"graph {orientation}",
                final_code,
            )
            logger.info(f"[VisionService] Valid on attempt {attempt}")
            return {"mermaid_code": final_code, "attempts": attempt}

        logger.warning(f"[VisionService] Errors on attempt {attempt}: {errors}")

        if attempt < MAX_RETRIES:
            # Extend conversation history with model reply + correction request
            error_feedback = "\n".join(f"- {e}" for e in errors)
            
            # Add the model's broken output to context
            messages.append({"role": "assistant", "content": raw_output})
            
            # Add the user's correction prompt
            messages.append({
                "role": "user",
                "content": (
                    f"The Mermaid code you generated has syntax errors:\n{error_feedback}\n\n"
                    "Please fix these errors and output ONLY the corrected Mermaid.js code "
                    "(no <think> block needed this time)."
                )
            })

    logger.warning(f"[VisionService] All {MAX_RETRIES} attempts exhausted.")
    return {
        "mermaid_code": final_code,
        "attempts": MAX_RETRIES,
        "warning": f"Code may have syntax issues after {MAX_RETRIES} attempts: {'; '.join(errors)}",
    }


def mime_from_filename(filename: str) -> str:
    """Infer MIME type from a filename. Raises ValueError for unsupported types."""
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_MIME:
        raise ValueError(
            f"Unsupported image type '{ext}'. "
            f"Supported: {', '.join(SUPPORTED_MIME.keys())}"
        )
    return SUPPORTED_MIME[ext]
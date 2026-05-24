# """
# Gemini AI Client — shared utility for all AI service routes.
# Import this wherever you need Gemini in Python.

# Usage:
#     from utils.gemini_client import ask_gemini_sync, describe_image_with_gemini
# """
# import os
# import io

# # ── Singleton model instance ─────────────────────────────────────────────────
# _model = None

# def get_model(model_name: str = "gemini-2.0-flash"):
#     """Return cached Gemini model, initializing on first call."""
#     global _model
#     if _model is not None:
#         return _model

#     api_key = os.getenv("GEMINI_API_KEY", "").strip()
#     if not api_key or api_key == "your_gemini_key_here":
#         raise ValueError("GEMINI_API_KEY not set in ai-service/.env")

#     import google.generativeai as genai
#     genai.configure(api_key=api_key)

#     _model = genai.GenerativeModel(
#         model_name=model_name,
#         generation_config=genai.types.GenerationConfig(
#             max_output_tokens=1024,
#             temperature=0.75,
#             top_p=0.9,
#         )
#     )
#     print(f"✅ Gemini model initialized: {model_name}")
#     return _model


# def ask_gemini_sync(prompt: str, system: str = "", history: list = []) -> str:
#     """
#     Synchronous Gemini call — use in regular Python functions.

#     Example:
#         result = ask_gemini_sync(
#             prompt="What outfit goes with navy trousers?",
#             system="You are a fashion stylist."
#         )
#     """
#     model = get_model()
#     chat  = model.start_chat(history=[
#         {"role": h["role"], "parts": [h["parts"]]} for h in history
#     ])
#     full_prompt = f"{system}\n\n{prompt}" if system and not history else prompt
#     response    = chat.send_message(full_prompt)
#     return response.text


# async def ask_gemini_async(prompt: str, system: str = "", history: list = []) -> str:
#     """
#     Async Gemini call — use inside FastAPI async endpoints.

#     Example:
#         result = await ask_gemini_async(
#             prompt="Show me red shirts under Rs 1500",
#             system="You are ARIA, a fashion AI."
#         )
#     """
#     model = get_model()
#     chat  = model.start_chat(history=[
#         {"role": h["role"], "parts": [h["parts"]]} for h in history
#     ])
#     full_prompt = f"{system}\n\n{prompt}" if system and not history else prompt
#     response    = await chat.send_message_async(full_prompt)
#     return response.text


# def describe_image(image_bytes: bytes, prompt: str) -> str:
#     """
#     Gemini Vision — analyze an image with a text prompt.
#     Use for: outfit color detection, style analysis, garment description.

#     Example:
#         with open("shirt.jpg", "rb") as f:
#             desc = describe_image(f.read(), "Describe this garment's color and style.")
#     """
#     import google.generativeai as genai
#     import PIL.Image

#     api_key = os.getenv("GEMINI_API_KEY", "").strip()
#     if not api_key:
#         raise ValueError("GEMINI_API_KEY not set")

#     genai.configure(api_key=api_key)
#     vision_model = genai.GenerativeModel("gemini-2.0-flash")
#     img          = PIL.Image.open(io.BytesIO(image_bytes)).convert("RGB")
#     response     = vision_model.generate_content([prompt, img])
#     return response.text


# def analyze_outfit(image_bytes: bytes) -> dict:
#     """
#     Analyze uploaded clothing image — returns color, style, category, occasion.
#     Useful for the virtual try-on to auto-detect garment properties.

#     Returns dict like:
#         {"color": "red", "style": "casual", "category": "shirts", "occasion": "everyday"}
#     """
#     prompt = """Analyze this clothing item and respond ONLY with JSON (no markdown):
# {
#   "color": "primary color of the garment",
#   "style": "casual|formal|semi-formal|sportswear|ethnic",
#   "category": "shirts|pants|shoes|watches|accessories|jackets|dresses",
#   "occasion": "everyday|office|party|wedding|sport|ethnic",
#   "description": "one sentence description"
# }"""
#     try:
#         raw  = describe_image(image_bytes, prompt)
#         # Strip markdown code fences if present
#         clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
#         import json
#         return json.loads(clean)
#     except Exception as e:
#         print(f"Outfit analysis error: {e}")
#         return {
#             "color": "unknown", "style": "casual",
#             "category": "shirts", "occasion": "everyday",
#             "description": "Fashion item"
#         }
import os
import io
import json
import base64
import requests
from PIL import Image

def ask_openrouter(prompt: str, system: str = "", history: list = [], model: str = "google/gemini-1.5"):
    """Call OpenRouter API using requests."""
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    
    for h in history:
        role = "assistant" if h.get("role") == "model" or h.get("role") == "assistant" else "user"
        messages.append({"role": role, "content": h.get("parts", [{}])[0].get("text", h.get("content", ""))})
    
    messages.append({"role": "user", "content": prompt})

    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        data=json.dumps({
            "model": model,
            "messages": messages,
            "temperature": 0.75,
            "max_tokens": 1024
        })
    )
    
    if response.status_code != 200:
        raise Exception(f"OpenRouter Error: {response.text}")
    
    return response.json()['choices'][0]['message']['content']

async def ask_gemini_async(prompt: str, system: str = "", history: list = []) -> str:
    """Async wrapper that prefers OpenRouter if available."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key and openrouter_key != "your_openrouter_key_here":
        return ask_openrouter(prompt, system, history)
    
    # Fallback to direct Gemini (Original Logic)
    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    response = await model.generate_content_async(full_prompt)
    return response.text

def describe_image(image_bytes: bytes, prompt: str) -> str:
    """Analyze image using OpenRouter (Base64) or Gemini Vision."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key and openrouter_key != "your_openrouter_key_here":
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {openrouter_key}", "Content-Type": "application/json"},
            data=json.dumps({
                "model": "google/gemini-1.5",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }]
            })
        )
        return response.json()['choices'][0]['message']['content']

    # Fallback to direct Gemini Vision
    import google.generativeai as genai
    import PIL.Image
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")
    img = PIL.Image.open(io.BytesIO(image_bytes)).convert("RGB")
    response = model.generate_content([prompt, img])
    return response.text

# Maintain original function names for compatibility
def ask_gemini_sync(prompt: str, system: str = "", history: list = []) -> str:
    return ask_openrouter(prompt, system, history)

def analyze_outfit(image_bytes: bytes) -> dict:
    prompt = "Analyze this clothing item and respond ONLY with JSON: { \"color\": \"...\", \"style\": \"...\", \"category\": \"...\", \"description\": \"...\" }"
    try:
        raw = describe_image(image_bytes, prompt)
        clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return json.loads(clean)
    except:
        return {"color": "unknown", "style": "casual", "category": "shirts"}

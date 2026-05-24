"""
Gemini AI Route — Python/FastAPI endpoints that use Gemini directly.
These complement the Node.js chatController which also calls Gemini.
"""
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import os

router = APIRouter()

# ── Request models ────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    system:  Optional[str] = ""
    history: Optional[list] = []

class AnalyzeRequest(BaseModel):
    text: str


# ── Test endpoint — verify Gemini works ──────────────────────────────────────
@router.get("/status")
async def gemini_status():
    """Check if Gemini API key is configured and working."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your_gemini_key_here":
        return JSONResponse({
            "configured": False,
            "reason": "GEMINI_API_KEY not set in ai-service/.env"
        })
    try:
        from utils.gemini_client import ask_gemini_sync
        response = ask_gemini_sync("Say exactly: Gemini is working!")
        return JSONResponse({
            "configured": True,
            "model": "gemini-2.0-flash",
            "test_response": response.strip(),
        })
    except Exception as e:
        return JSONResponse({"configured": False, "error": str(e)})


# ── General chat endpoint ─────────────────────────────────────────────────────
@router.post("/chat")
async def gemini_chat(req: ChatRequest):
    """
    Send any prompt to Gemini and get a response.
    Used for: outfit advice, style questions, product descriptions.
    """
    try:
        from utils.gemini_client import ask_gemini_async
        response = await ask_gemini_async(
            prompt=req.message,
            system=req.system,
            history=req.history
        )
        return JSONResponse({"success": True, "response": response})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini error: {str(e)}")


# ── Analyze garment image ─────────────────────────────────────────────────────
@router.post("/analyze-garment")
async def analyze_garment(image: UploadFile = File(...)):
    """
    Upload a garment image — Gemini Vision returns color, style, category.
    Used by virtual try-on to auto-detect product properties.
    """
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if image.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Use JPEG, PNG, or WEBP")

    image_bytes = await image.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 10MB)")

    try:
        from utils.gemini_client import analyze_outfit
        result = analyze_outfit(image_bytes)
        return JSONResponse({"success": True, "analysis": result})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")


# ── Generate outfit description ───────────────────────────────────────────────
@router.post("/outfit-description")
async def outfit_description(
    image:        UploadFile = File(...),
    product_name: str = "Fashion Item",
    brand:        str = "",
):
    """
    Generate an elegant curator's note for a product image using Gemini Vision.
    """
    image_bytes = await image.read()
    prompt = f"""You are an expert fashion curator at a premium store.
Look at this image of '{product_name}'{f' by {brand}' if brand else ''}.
Write one sophisticated paragraph (2-3 sentences) describing:
- The garment's construction and material quality
- Its aesthetic characteristics
- Who it's perfect for

Write as a luxury fashion curator. Be concise and elegant."""

    try:
        from utils.gemini_client import describe_image
        description = describe_image(image_bytes, prompt)
        return JSONResponse({
            "success":     True,
            "description": description.strip(),
            "product":     product_name,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Style advice endpoint ─────────────────────────────────────────────────────
@router.post("/style-advice")
async def style_advice(req: AnalyzeRequest):
    """
    Get Gemini-powered style advice for any question.
    E.g. 'What shoes go with navy chinos for an office setting?'
    """
    system = """You are ARIA, an expert AI fashion stylist.
Give specific, actionable style advice in 2-3 sentences.
Focus on Pakistani fashion context. Mention specific items and color combinations."""

    try:
        from utils.gemini_client import ask_gemini_async
        advice = await ask_gemini_async(prompt=req.text, system=system)
        return JSONResponse({"success": True, "advice": advice.strip()})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

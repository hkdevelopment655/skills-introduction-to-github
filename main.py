import sys
import os
from pathlib import Path

# ── Python version guard ─────────────────────────────────────────────────────
_major, _minor = sys.version_info[:2]
if (_major, _minor) < (3, 10):
    print(f"ERROR: Python {_major}.{_minor} detected. Requires 3.10+")
    sys.exit(1)

# ── Load .env ────────────────────────────────────────────────────────────────
from dotenv import load_dotenv
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)
print(f"📁 .env path      : {env_path}")
print(f"🔑 GEMINI_API_KEY : {'SET ✅ → ' + os.getenv('GEMINI_API_KEY','')[:12]+'...' if os.getenv('GEMINI_API_KEY') else 'NOT SET ⚠️'}")
print(f"🎨 STABILITY_KEY  : {'SET ✅' if os.getenv('STABILITY_API_KEY') else 'NOT SET (fallback overlay)'}")

# ── MediaPipe check ───────────────────────────────────────────────────────────
try:
    import mediapipe as mp
    _ = mp.solutions.pose
    print(f"✅ MediaPipe {mp.__version__} (solutions API) loaded")
except Exception as e:
    print(f"⚠️  MediaPipe not available: {e}")

# ── FastAPI app ───────────────────────────────────────────────────────────────
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from routes.tryon import router as tryon_router
from routes.height import router as height_router

# Optional: Gemini-powered chat endpoint
try:
    from routes.gemini import router as gemini_router
    GEMINI_ROUTER = True
except Exception as e:
    print(f"⚠️  Gemini router skipped: {e}")
    GEMINI_ROUTER = False

print("📦 Loading FastAPI app...")
app = FastAPI(
    title="Smart AI — AI Service",
    description="Virtual Try-On (MediaPipe + Stable Diffusion) + Height Estimation + Gemini",
    version="2.1.0"
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Covers both the Vite dev server (5173) and any Node backend (5000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5000",
        "http://localhost:5173",
        "http://127.0.0.1:5000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
# tryon_router defines its own @router.post("/")  →  served at POST /api/tryon
# The new MediaPipe endpoint is @router.post("/") inside routes/tryon.py
app.include_router(tryon_router, prefix="/api/tryon", tags=["Virtual Try-On"])
app.include_router(height_router, prefix="/height",   tags=["Height Estimation"])
if GEMINI_ROUTER:
    app.include_router(gemini_router, prefix="/gemini", tags=["Gemini AI"])

# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    sd_key  = os.getenv("STABILITY_API_KEY", "")
    gem_key = os.getenv("GEMINI_API_KEY", "")
    try:
        import mediapipe as mp
        mp_version = mp.__version__
        mp_ok = True
    except Exception:
        mp_version = "not installed"
        mp_ok = False
    return {
        "status":             "OK",
        "python":             f"{_major}.{_minor}",
        "mediapipe":          mp_version,
        "mediapipe_ok":       mp_ok,
        "sd_configured":      bool(sd_key  and sd_key  != "your_stability_key_here"),
        "gemini_configured":  bool(gem_key and gem_key != "your_gemini_key_here"),
    }

# ── Startup ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sd_key  = os.getenv("STABILITY_API_KEY", "")
    gem_key = os.getenv("GEMINI_API_KEY", "")
    print(f"✅ Python {_major}.{_minor} confirmed")
    print(f"{'✅' if gem_key else '⚠️ '} Gemini AI     : {'CONFIGURED' if gem_key else 'NOT SET'}")
    print(f"{'✅' if sd_key  else '⚠️ '} Stability AI  : {'CONFIGURED' if sd_key  else 'NOT SET — overlay fallback'}")
    print(f"🌐 CORS origins  : localhost:5173 (Vite), localhost:5000 (Node)")
    print(f"🔗 Try-On route  : POST http://localhost:8000/api/tryon")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
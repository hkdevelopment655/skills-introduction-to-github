"""
Height Estimation Module
Uses MediaPipe pose landmarks to estimate height from uploaded images.
"""
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import numpy as np
import cv2

router = APIRouter()

# ── MediaPipe ────────────────────────────────────────────────────────────────
MEDIAPIPE_AVAILABLE = False
mp_pose             = None   # holds mp.solutions.pose.Pose CLASS

try:
    import mediapipe as mp
    if hasattr(mp, "solutions") and hasattr(mp.solutions, "pose"):
        mp_pose             = mp.solutions.pose.Pose   # ← CLASS, not module
        MEDIAPIPE_AVAILABLE = True
        print(f"✅ MediaPipe {mp.__version__} loaded (height module)")
    else:
        print(f"WARNING: MediaPipe {mp.__version__} — no compatible pose API")
except ImportError:
    print("WARNING: mediapipe not installed. Height estimation disabled.")
except Exception as exc:
    print(f"WARNING: MediaPipe import error: {exc}")


def get_landmarks(image_np: np.ndarray) -> dict:
    """Extract visible pose landmarks from image."""
    if not MEDIAPIPE_AVAILABLE or mp_pose is None:
        return {}
    try:
        img_h, img_w = image_np.shape[:2]
        with mp_pose(
            static_image_mode=True,
            model_complexity=1,
            min_detection_confidence=0.4,
        ) as pose:
            rgb     = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb)
            if not results.pose_landmarks:
                return {}
            out = {}
            for idx, lm in enumerate(results.pose_landmarks.landmark):
                if lm.visibility > 0.3:
                    out[idx] = {
                        "x": lm.x * img_w,
                        "y": lm.y * img_h,
                        "visibility": lm.visibility,
                    }
            return out
    except Exception as exc:
        print(f"Pose detection error: {exc}")
        return {}


def estimate_height(landmarks: dict, img_h: int, img_w: int) -> dict:
    if not landmarks or len(landmarks) < 5:
        return {"estimated_height_cm": None, "confidence": "low",
                "method": "insufficient_data", "recommended_size": "M"}

    nose = landmarks.get(0)
    ls   = landmarks.get(11)
    rs   = landmarks.get(12)
    lh   = landmarks.get(23)
    rh   = landmarks.get(24)
    la   = landmarks.get(27)
    ra   = landmarks.get(28)

    estimated_px = None
    method       = "unknown"

    if nose and la and ra:
        avg_ankle_y = (la["y"] + ra["y"]) / 2
        shoulder_y  = ((ls["y"] + rs["y"]) / 2) if (ls and rs) else nose["y"]
        head_offset = abs(nose["y"] - shoulder_y) * 0.55
        estimated_px = avg_ankle_y - (nose["y"] - head_offset)
        method = "full_body"
    elif nose and lh and rh:
        avg_hip_y   = (lh["y"] + rh["y"]) / 2
        shoulder_y  = ((ls["y"] + rs["y"]) / 2) if (ls and rs) else nose["y"]
        head_offset = abs(nose["y"] - shoulder_y) * 0.55
        upper_px    = avg_hip_y - (nose["y"] - head_offset)
        estimated_px = upper_px / 0.57
        method = "upper_body_extrapolation"
    elif ls and rs and lh and rh:
        torso_px     = ((lh["y"] + rh["y"]) / 2) - ((ls["y"] + rs["y"]) / 2)
        estimated_px = torso_px / 0.32
        method = "torso_ratio"

    if not estimated_px or estimated_px <= 0:
        return {"estimated_height_cm": None, "confidence": "low",
                "method": "failed", "recommended_size": "M"}

    pixels_per_cm = (img_h * 0.85) / 175
    estimated_cm  = round(max(140, min(220, estimated_px / pixels_per_cm)))
    confidence    = ("high"   if method == "full_body" else
                     "medium" if method == "upper_body_extrapolation" else "low")
    size          = ("S" if estimated_cm < 165 else
                     "M" if estimated_cm < 175 else
                     "L" if estimated_cm < 183 else "XL")

    return {
        "estimated_height_cm": estimated_cm,
        "confidence":          confidence,
        "method":              method,
        "recommended_size":    size,
        "landmarks_used":      len(landmarks),
    }


@router.post("/")
async def estimate_height_endpoint(image: UploadFile = File(...)):
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if image.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Use JPEG, PNG, or WEBP image.")

    contents = await image.read()
    nparr    = np.frombuffer(contents, np.uint8)
    img_np   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img_np is None:
        raise HTTPException(status_code=400, detail="Could not decode image")

    img_h, img_w = img_np.shape[:2]
    landmarks    = get_landmarks(img_np)
    result       = estimate_height(landmarks, img_h, img_w)
    return JSONResponse({"success": True, **result})
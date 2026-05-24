import asyncio
import base64
import io
import json
import os
import sys

import cv2
import httpx
import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
# pyrefly: ignore [missing-import]
from PIL import Image, ImageEnhance, ImageFilter
from typing import Optional, List, Tuple

# ── sd_client (img2img fallback) ─────────────────────────────────────────────
try:
    _ai_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _ai_root not in sys.path:
        sys.path.insert(0, _ai_root)
    from utils.sd_client import call_sd_api_img2img
    _SDCLIENT_AVAILABLE = True
except ImportError as _e:
    print(f"⚠️  sd_client not importable: {_e}")
    _SDCLIENT_AVAILABLE = False
    async def call_sd_api_img2img(*a, **kw): return None

router = APIRouter()

# ── MediaPipe and Measurement Helpers ────────────────────────────────────────
def detect_landmarks(image_np: np.ndarray) -> dict:
    """Extract visible pose landmarks from image using MediaPipe."""
    try:
        # pyrefly: ignore [missing-import]
        import mediapipe as mp
        if not hasattr(mp, "solutions") or not hasattr(mp.solutions, "pose"):
            return {}
        mp_pose = mp.solutions.pose.Pose
        img_h, img_w = image_np.shape[:2]
        with mp_pose(
            static_image_mode=True,
            model_complexity=1,
            min_detection_confidence=0.4,
        ) as pose:
            rgb = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb)
            if not results.pose_landmarks:
                return {}
            out = {}
            for idx, lm in enumerate(results.pose_landmarks.landmark):
                out[idx] = {
                    "x": lm.x * img_w,
                    "y": lm.y * img_h,
                    "visibility": lm.visibility,
                }
            return out
    except Exception as exc:
        print(f"Pose detection error in tryon: {exc}")
        return {}


def get_measurements(landmarks: dict, img_h: int, img_w: int) -> dict:
    """Calculate body measurements and predict sizes from landmarks."""
    ls = landmarks.get(11) # Left Shoulder
    rs = landmarks.get(12) # Right Shoulder
    lh = landmarks.get(23) # Left Hip
    rh = landmarks.get(24) # Right Hip
    
    measurements = {
        "shoulder_span_cm": None,
        "shoulder_span_str": "N/A",
        "predicted_size": "M",
        "fit_analysis": 85,
        "fit_type": "Relaxed",
        "torso_alignment": "ESTIMATED"
    }
    
    if ls and rs:
        pixels_per_cm = (img_h * 0.85) / 175
        shoulder_px = np.sqrt((ls["x"] - rs["x"])**2 + (ls["y"] - rs["y"])**2)
        shoulder_cm = round(shoulder_px / pixels_per_cm, 1)
        measurements["shoulder_span_cm"] = shoulder_cm
        measurements["shoulder_span_str"] = f"{shoulder_cm}CM"
        
        if shoulder_cm < 38.0:
            measurements["predicted_size"] = "S"
        elif shoulder_cm < 43.0:
            measurements["predicted_size"] = "M"
        elif shoulder_cm < 48.0:
            measurements["predicted_size"] = "L"
        else:
            measurements["predicted_size"] = "XL"
            
        if lh and rh:
            shoulder_tilt = abs(ls["y"] - rs["y"])
            hip_tilt = abs(lh["y"] - rh["y"])
            if shoulder_tilt < 15 and hip_tilt < 15:
                measurements["torso_alignment"] = "OPTIMAL"
                measurements["fit_analysis"] = 92
            else:
                measurements["torso_alignment"] = "TILTED"
                measurements["fit_analysis"] = 78
                
    return measurements


# ── Delaunay Triangulation Warping ───────────────────────────────────────────

def extract_person_keypoints(lm: dict, img_w: int, img_h: int) -> Optional[List[Tuple[float, float]]]:
    """
    Extract 10 body anchor points from MediaPipe pose landmarks.
    
    Returns list of (x, y) tuples mapped to torso region:
      0: left shoulder
      1: right shoulder
      2: left armpit (slightly below shoulder)
      3: right armpit
      4: left hip
      5: right hip
      6: shirt collar center top
      7: shirt collar center bottom (approx sternum)
      8: left hem bottom
      9: right hem bottom
    Returns None if critical landmarks are missing.
    """
    ls = lm.get(11)  # Left shoulder
    rs = lm.get(12)  # Right shoulder
    lh = lm.get(23)  # Left hip
    rh = lm.get(24)  # Right hip
    le = lm.get(13)  # Left elbow (for sleeve extension)
    re = lm.get(14)  # Right elbow

    if not ls or not rs:
        return None

    # Fall back to estimated hip positions if not detected
    if not lh or not rh:
        torso_height = (ls["y"] + rs["y"]) / 2
        hip_y = torso_height + (img_h * 0.3)
        lh = {"x": ls["x"], "y": hip_y}
        rh = {"x": rs["x"], "y": hip_y}

    # Compute derived points
    shoulder_midpoint_x = (ls["x"] + rs["x"]) / 2
    shoulder_midpoint_y = (ls["y"] + rs["y"]) / 2

    # Collar is slightly above shoulder midpoint
    collar_top = (shoulder_midpoint_x, shoulder_midpoint_y - abs(ls["y"] - rs["y"]) * 0.3 - img_h * 0.02)
    collar_bottom = (shoulder_midpoint_x, shoulder_midpoint_y + img_h * 0.04)

    # Armpit slightly below shoulder (where sleeve meets body)
    armpit_offset_y = img_h * 0.03
    left_armpit = (ls["x"], ls["y"] + armpit_offset_y)
    right_armpit = (rs["x"], rs["y"] + armpit_offset_y)

    # Hip + hem (slightly below hip for shirt coverage)
    hem_offset_y = img_h * 0.035
    left_hem = (lh["x"], lh["y"] + hem_offset_y)
    right_hem = (rh["x"], rh["y"] + hem_offset_y)

    return [
        (ls["x"], ls["y"]),       # 0: left shoulder
        (rs["x"], rs["y"]),       # 1: right shoulder
        left_armpit,              # 2: left armpit
        right_armpit,             # 3: right armpit
        (lh["x"], lh["y"]),       # 4: left hip
        (rh["x"], rh["y"]),       # 5: right hip
        collar_top,               # 6: collar top center
        collar_bottom,            # 7: collar bottom center (sternum)
        left_hem,                 # 8: left hem
        right_hem,                # 9: right hem
    ]


def extract_shirt_keypoints(cloth_w: int, cloth_h: int) -> List[Tuple[float, float]]:
    """
    Generate a standard 10-point template for a flat-lay shirt image.
    These percentages correspond roughly to where the same anchor points
    sit on a typical front-facing shirt image.

    Points:
      0: left shoulder
      1: right shoulder
      2: left armpit
      3: right armpit
      4: left hip
      5: right hip
      6: collar top center
      7: collar bottom center (sternum)
      8: left hem bottom
      9: right hem bottom
    """
    w, h = cloth_w, cloth_h
    return [
        (w * 0.18, h * 0.10),  # 0: left shoulder
        (w * 0.82, h * 0.10),  # 1: right shoulder
        (w * 0.10, h * 0.27),  # 2: left armpit
        (w * 0.90, h * 0.27),  # 3: right armpit
        (w * 0.20, h * 0.78),  # 4: left hip
        (w * 0.80, h * 0.78),  # 5: right hip
        (w * 0.50, h * 0.02),  # 6: collar top center
        (w * 0.50, h * 0.15),  # 7: collar bottom / sternum
        (w * 0.12, h * 0.97),  # 8: left hem
        (w * 0.88, h * 0.97),  # 9: right hem
    ]


def warp_triangle(
    src: np.ndarray,
    dst: np.ndarray,
    src_tri: np.ndarray,
    dst_tri: np.ndarray,
    mask: np.ndarray,
) -> None:
    """
    Warp a single triangle from src into dst in-place.
    Also updates mask to mark warped regions.
    """
    # Bounding rectangles
    src_rect = cv2.boundingRect(src_tri.astype(np.float32))
    dst_rect = cv2.boundingRect(dst_tri.astype(np.float32))

    sx, sy, sw, sh = src_rect
    dx, dy, dw, dh = dst_rect

    # Crop src patch
    src_patch = src[sy:sy+sh, sx:sx+sw]
    if src_patch.size == 0 or sw <= 0 or sh <= 0 or dw <= 0 or dh <= 0:
        return

    # Relative triangle coords
    src_tri_rel = src_tri - np.array([sx, sy], dtype=np.float32)
    dst_tri_rel = dst_tri - np.array([dx, dy], dtype=np.float32)

    # Build triangle mask for the destination patch
    tri_mask = np.zeros((dh, dw), dtype=np.uint8)
    cv2.fillConvexPoly(tri_mask, dst_tri_rel.astype(np.int32), 255)

    # Affine warp from source patch to destination size
    M = cv2.getAffineTransform(src_tri_rel.astype(np.float32), dst_tri_rel.astype(np.float32))
    warped_patch = cv2.warpAffine(src_patch, M, (dw, dh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)

    # Blend warped patch into dst using triangle mask
    roi = dst[dy:dy+dh, dx:dx+dw]
    if roi.shape[:2] != warped_patch.shape[:2]:
        return

    alpha = tri_mask.astype(np.float32) / 255.0

    if warped_patch.shape[2] == 4:
        # RGBA — incorporate the cloth alpha channel
        cloth_a = warped_patch[:, :, 3].astype(np.float32) / 255.0
        combined_alpha = alpha * cloth_a
        for c in range(3):
            roi[:, :, c] = (warped_patch[:, :, c] * combined_alpha + roi[:, :, c] * (1 - combined_alpha)).astype(np.uint8)
        mask[dy:dy+dh, dx:dx+dw] = np.maximum(mask[dy:dy+dh, dx:dx+dw], (combined_alpha * 255).astype(np.uint8))
    else:
        for c in range(3):
            roi[:, :, c] = (warped_patch[:, :, c] * alpha + roi[:, :, c] * (1 - alpha)).astype(np.uint8)
        mask[dy:dy+dh, dx:dx+dw] = np.maximum(mask[dy:dy+dh, dx:dx+dw], tri_mask)

    dst[dy:dy+dh, dx:dx+dw] = roi


def get_triangles(points: List[Tuple[float, float]]) -> List[Tuple[int, int, int]]:
    """
    Compute Delaunay triangulation for a list of 2D points.
    Returns list of (i, j, k) index triples referring to `points`.
    """
    pts_array = np.array(points, dtype=np.float32)
    min_x = pts_array[:, 0].min() - 1
    min_y = pts_array[:, 1].min() - 1
    max_x = pts_array[:, 0].max() + 1
    max_y = pts_array[:, 1].max() + 1

    subdiv = cv2.Subdiv2D((int(min_x), int(min_y), int(max_x - min_x + 2), int(max_y - min_y + 2)))
    for p in points:
        try:
            subdiv.insert((float(p[0]), float(p[1])))
        except Exception:
            pass

    triangles = []
    for tri in subdiv.getTriangleList():
        pts = [(tri[0], tri[1]), (tri[2], tri[3]), (tri[4], tri[5])]
        idxs = []
        for pt in pts:
            # Find closest point index
            dists = [np.hypot(pt[0] - p[0], pt[1] - p[1]) for p in points]
            idx = int(np.argmin(dists))
            if dists[idx] < 2.0:
                idxs.append(idx)
        if len(idxs) == 3:
            triangles.append((idxs[0], idxs[1], idxs[2]))

    return triangles


def remove_background_cloth(img: Image.Image) -> Image.Image:
    """Remove white/near-white background from a garment image. Returns RGBA."""
    rgba = img.convert("RGBA")
    data = np.array(rgba)
    r, g, b, a = data[:, :, 0], data[:, :, 1], data[:, :, 2], data[:, :, 3]
    # White or very-light pixels → transparent
    white_mask = (r > 230) & (g > 230) & (b > 230)
    data[:, :, 3] = np.where(white_mask, 0, a)
    return Image.fromarray(data, "RGBA")


def feather_mask(mask_np: np.ndarray, radius: int = 12) -> np.ndarray:
    """Apply Gaussian blur to a uint8 mask to feather edges."""
    ksize = radius * 2 + 1
    return cv2.GaussianBlur(mask_np, (ksize, ksize), radius / 2)


def pose_warped_overlay(
    person_pil: Image.Image,
    cloth_pil: Image.Image,
    lm: dict,
) -> Optional[Image.Image]:
    """
    Primary try-on method.
    
    1. Extract 10 anchor keypoints from the person's pose landmarks.
    2. Build a corresponding flat-lay shirt template with the same 10 points.
    3. Perform Delaunay triangulation over the point sets.
    4. Warp each triangle from the shirt onto the person image.
    5. Feather the edges and alpha-blend for a natural look.
    
    The person's face, hair, background, and body dimensions remain pixel-identical
    to the input image. Only the torso region is replaced by the warped shirt.

    Returns None if pose cannot be detected.
    """
    pw, ph = person_pil.size
    person_kps = extract_person_keypoints(lm, pw, ph)
    if person_kps is None:
        print("⚠️  pose_warped_overlay: no pose detected, skipping warp.")
        return None

    # Remove cloth background and convert to RGBA for alpha-aware warping
    cloth_rgba = remove_background_cloth(cloth_pil)
    cw, ch = cloth_rgba.size
    shirt_kps = extract_shirt_keypoints(cw, ch)

    # Convert images to numpy
    person_np = cv2.cvtColor(np.array(person_pil.convert("RGB")), cv2.COLOR_RGB2BGR)
    cloth_np = cv2.cvtColor(np.array(cloth_rgba), cv2.COLOR_RGBA2BGRA)

    # Output canvas starts as a copy of person
    result_np = person_np.copy()
    warp_mask = np.zeros((ph, pw), dtype=np.uint8)

    # Triangulate on the SHIRT keypoints (source)
    triangles = get_triangles(shirt_kps)

    for tri_idxs in triangles:
        i, j, k = tri_idxs
        src_tri = np.array([shirt_kps[i], shirt_kps[j], shirt_kps[k]], dtype=np.float32)
        dst_tri = np.array([person_kps[i], person_kps[j], person_kps[k]], dtype=np.float32)

        # Sanity-check: skip degenerate triangles
        area = abs(cv2.contourArea(dst_tri))
        if area < 4:
            continue

        warp_triangle(cloth_np, result_np, src_tri, dst_tri, warp_mask)

    # Feather the warp mask for soft edges
    feathered = feather_mask(warp_mask, radius=14)

    # Composite: blend result only in the warped region
    alpha = feathered.astype(np.float32)[:, :, None] / 255.0
    final_np = (result_np * alpha + person_np * (1 - alpha)).astype(np.uint8)

    return Image.fromarray(cv2.cvtColor(final_np, cv2.COLOR_BGR2RGB))


# ── Old helpers kept for fallback ────────────────────────────────────────────

def _clothing_mask(person_pil: Image.Image, landmarks: dict, product_category: str) -> Image.Image:
    """Create a black-and-white mask image for inpainting the garment area."""
    w, h = person_pil.size
    mask = Image.new("L", (w, h), 0)
    
    ls = landmarks.get(11)
    rs = landmarks.get(12)
    lh = landmarks.get(23)
    rh = landmarks.get(24)
    
    if not ls or not rs:
        # pyrefly: ignore [missing-import]
        from PIL import ImageDraw
        draw = ImageDraw.Draw(mask)
        draw.rectangle([w * 0.25, h * 0.25, w * 0.75, h * 0.75], fill=255)
        return mask
        
    # pyrefly: ignore [missing-import]
    from PIL import ImageDraw
    draw = ImageDraw.Draw(mask)
    
    s_width = abs(ls["x"] - rs["x"])
    s_height = abs(lh["y"] - ls["y"]) if (lh and rh) else h * 0.4
    
    ext_x = s_width * 0.15
    ext_y_top = s_height * 0.1
    ext_y_bottom = s_height * 0.15
    
    p1 = (max(0, min(ls["x"] - ext_x, rs["x"] - ext_x)), max(0, min(ls["y"], rs["y"]) - ext_y_top))
    p2 = (min(w, max(ls["x"] + ext_x, rs["x"] + ext_x)), max(0, min(ls["y"], rs["y"]) - ext_y_top))
    
    if lh and rh:
        p3 = (min(w, max(lh["x"] + ext_x, rh["x"] + ext_x)), min(h, max(lh["y"], rh["y"]) + ext_y_bottom))
        p4 = (max(0, min(lh["x"] - ext_x, rh["x"] - ext_x)), min(h, max(lh["y"], rh["y"]) + ext_y_bottom))
    else:
        p3 = (p2[0], min(h, p2[1] + s_height + ext_y_bottom))
        p4 = (p1[0], min(h, p1[1] + s_height + ext_y_bottom))
        
    draw.polygon([p1, p2, p3, p4], fill=255)
    return mask


async def download_image_from_url(url: str) -> Optional[Image.Image]:
    """Download an image from a URL and return a PIL Image."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception as e:
        print(f"Error downloading image from {url}: {e}")
    return None


# ── Stability AI Check ───────────────────────────────────────────────────────
STABILITY_API_KEY = os.getenv("STABILITY_API_KEY") or ""

def sd_available() -> bool:
    """Check if Stability AI is configured and enabled."""
    return bool(STABILITY_API_KEY and STABILITY_API_KEY != "your_stability_key_here")


# ── Stability AI Inpainting ──────────────────────────────────────────────────

async def stable_diffusion_tryon(
    person_pil: Image.Image,
    cloth_pil: Optional[Image.Image],
    product_name: str,
    product_color: str,
    product_category: str,
    landmarks: dict
) -> Optional[Image.Image]:
    """Use Stability AI's Image-to-Image Masking/Inpainting API to perform virtual try-on."""
    if not sd_available():
        return None
        
    try:
        target_size = (1024, 1024)
        orig_w, orig_h = person_pil.size
        person_resized = person_pil.resize(target_size, Image.Resampling.LANCZOS)
        
        scaled_landmarks = {}
        for idx, pt in landmarks.items():
            scaled_landmarks[idx] = {
                "x": pt["x"] * (1024 / orig_w),
                "y": pt["y"] * (1024 / orig_h),
                "visibility": pt["visibility"]
            }
            
        mask_pil = _clothing_mask(person_resized, scaled_landmarks, product_category)
        
        init_buf = io.BytesIO()
        person_resized.save(init_buf, format="PNG")
        init_bytes = init_buf.getvalue()
        
        mask_buf = io.BytesIO()
        mask_pil.save(mask_buf, format="PNG")
        mask_bytes = mask_buf.getvalue()
        
        prompt = f"A person wearing a {product_color} {product_name}, catalog product photography, high fashion, photorealistic, highly detailed, studio lighting"
        negative_prompt = "mutated hands, blurry, low resolution, bad anatomy, deformed clothing, messy, drawing, painting"
        
        url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/image-to-image/masking"
        headers = {
            "Authorization": f"Bearer {STABILITY_API_KEY}",
            "Accept": "application/json"
        }
        
        files = {
            "init_image": ("init.png", init_bytes, "image/png"),
            "mask_image": ("mask.png", mask_bytes, "image/png")
        }
        
        data = {
            "mask_source": "MASK_IMAGE_WHITE",
            "text_prompts[0][text]": prompt,
            "text_prompts[0][weight]": 1.0,
            "text_prompts[1][text]": negative_prompt,
            "text_prompts[1][weight]": -1.0,
            "cfg_scale": 7,
            "samples": 1,
            "steps": 30
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            print("🎨 Sending inpainting request to Stability AI...")
            resp = await client.post(url, headers=headers, files=files, data=data)
            
            if resp.status_code != 200:
                print(f"❌ Stability API Error {resp.status_code}: {resp.text}")
                return None
                
            resp_data = resp.json()
            if "artifacts" in resp_data and len(resp_data["artifacts"]) > 0:
                img_b64 = resp_data["artifacts"][0]["base64"]
                res_img = Image.open(io.BytesIO(base64.b64decode(img_b64)))
                return res_img.resize((orig_w, orig_h), Image.Resampling.LANCZOS)
                
    except Exception as e:
        print(f"❌ Error in stable_diffusion_tryon: {e}")
        
    return None


def remove_background(img: Image.Image) -> Image.Image:
    """Remove white or near-white background from a garment image."""
    rgba = img.convert("RGBA")
    data = rgba.getdata()
    new_data = []
    for item in data:
        if item[0] > 240 and item[1] > 240 and item[2] > 240:
            new_data.append((item[0], item[1], item[2], 0))
        else:
            new_data.append(item)
    rgba.putdata(new_data)
    return rgba


def overlay_garment_fallback(
    person_pil: Image.Image,
    cloth_pil: Image.Image,
    landmarks: dict,
    product_category: str
) -> Image.Image:
    """Overlay the garment image on top of the person image using pose landmarks."""
    ls = landmarks.get(11)
    rs = landmarks.get(12)
    lh = landmarks.get(23)
    rh = landmarks.get(24)
    
    result = person_pil.copy()
    
    if not ls or not rs:
        pw, ph = person_pil.size
        cw, ch = cloth_pil.size
        scale = (pw * 0.5) / cw
        nw = int(cw * scale)
        nh = int(ch * scale)
        cloth_resized = cloth_pil.resize((nw, nh), Image.Resampling.LANCZOS)
        cloth_rgba = remove_background(cloth_resized)
        
        paste_x = (pw - nw) // 2
        paste_y = int(ph * 0.25)
        result.paste(cloth_rgba, (paste_x, paste_y), cloth_rgba)
        return result

    sc_x = (ls["x"] + rs["x"]) / 2
    sc_y = (ls["y"] + rs["y"]) / 2
    s_width = np.sqrt((ls["x"] - rs["x"])**2 + (ls["y"] - rs["y"])**2)
    
    if lh and rh:
        t_height = ((lh["y"] + rh["y"]) / 2) - sc_y
    else:
        t_height = s_width * 1.2
        
    width_scale = 1.35
    height_scale = 1.15
    y_offset_pct = 0.15
    
    if product_category == "pants":
        la = landmarks.get(27)
        ra = landmarks.get(28)
        hip_center_x = (lh["x"] + rh["x"]) / 2 if (lh and rh) else sc_x
        hip_center_y = (lh["y"] + rh["y"]) / 2 if (lh and rh) else sc_y + t_height
        hip_width = np.sqrt((lh["x"] - rh["x"])**2 + (lh["y"] - rh["y"])**2) if (lh and rh) else s_width * 0.8
        
        leg_height = ((la["y"] + ra["y"])/2 - hip_center_y) if (la and ra) else t_height * 1.5
        
        new_width = int(hip_width * 1.25)
        new_height = int(leg_height * 1.05)
        
        new_width = max(10, new_width)
        new_height = max(10, new_height)
        
        cloth_resized = cloth_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)
        cloth_rgba = remove_background(cloth_resized)
        
        paste_x = int(hip_center_x - (new_width / 2))
        paste_y = int(hip_center_y - (new_height * 0.05))
        
        result.paste(cloth_rgba, (paste_x, paste_y), cloth_rgba)
        return result
        
    new_width = int(s_width * width_scale)
    new_height = int(t_height * height_scale)
    
    new_width = max(10, new_width)
    new_height = max(10, new_height)
    
    cloth_resized = cloth_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)
    cloth_rgba = remove_background(cloth_resized)
    
    paste_x = int(sc_x - (new_width / 2))
    paste_y = int(sc_y - (new_height * y_offset_pct))
    
    result.paste(cloth_rgba, (paste_x, paste_y), cloth_rgba)
    return result


# ── Main API endpoint ─────────────────────────────────────────────────────────

@router.post("")
@router.post("/")
async def api_tryon(
    person_image:     UploadFile = File(None),
    image:            UploadFile = File(None),
    clothing_image:   UploadFile = File(None),
    clothing_url:     str        = Form(None),
    product_name:     str        = Form("Fashion Item"),
    product_color:    str        = Form(""),
    product_category: str        = Form("shirts"),
):
    # ── Decode person image ──────────────────────────────────────────────────
    target_image = person_image or image
    if not target_image:
        raise HTTPException(status_code=400, detail="Missing person_image or image file.")
        
    p_bytes = await target_image.read()
    person_np = cv2.imdecode(np.frombuffer(p_bytes, np.uint8), cv2.IMREAD_COLOR)
    person_pil = Image.fromarray(cv2.cvtColor(person_np, cv2.COLOR_BGR2RGB))
    
    # ── Landmark Detection ───────────────────────────────────────────────────
    lm = detect_landmarks(person_np)
    
    # ── Resolve Clothing Image ───────────────────────────────────────────────
    cloth_pil = None
    if clothing_image:
        c_bytes = await clothing_image.read()
        if len(c_bytes) > 100:
            cloth_np = cv2.imdecode(np.frombuffer(c_bytes, np.uint8), cv2.IMREAD_COLOR)
            cloth_pil = Image.fromarray(cv2.cvtColor(cloth_np, cv2.COLOR_BGR2RGB))
    if not cloth_pil and clothing_url:
        cloth_pil = await download_image_from_url(clothing_url)

    result_pil = None
    method_used = "none"

    # ══════════════════════════════════════════════════════════════════════════
    # TRY-ON PRIORITY ORDER
    # 1. PRIMARY  — Pose-Aligned Delaunay Warp (face+body preserved, actual shirt)
    # 2. SECONDARY — Stability AI Inpainting (photorealistic, but generative)
    # 3. TERTIARY  — SD API img2img (external SD fallback)
    # 4. FALLBACK  — OpenCV centred overlay
    # 5. LAST      — Original photo
    # ══════════════════════════════════════════════════════════════════════════

    # 1. PRIMARY: Pose-Aligned Delaunay Warp
    if cloth_pil and lm and result_pil is None:
        print("🎯 Attempting Delaunay Pose-Warp try-on...")
        try:
            result_pil = pose_warped_overlay(person_pil, cloth_pil, lm)
            if result_pil:
                method_used = "pose-warped-overlay"
                print("✅ Delaunay warp successful.")
        except Exception as e:
            print(f"⚠️  Delaunay warp error: {e}")
            result_pil = None

    # 2. SECONDARY: Stability AI Inpainting (only if Delaunay failed)
    if sd_available() and result_pil is None:
        print("🚀 Falling back to Stability AI Inpainting...")
        result_pil = await stable_diffusion_tryon(
            person_pil, cloth_pil, product_name, product_color, product_category, lm
        )
        if result_pil:
            method_used = "stable-diffusion"

    # 3. TERTIARY: SD API img2img
    if _SDCLIENT_AVAILABLE and result_pil is None:
        print("🎨 Falling back to SD API Img2Img...")
        prompt = f"A person wearing a {product_color} {product_name}, photorealistic, high detail"
        res_b64 = await call_sd_api_img2img(p_bytes, prompt)
        if res_b64:
            header, encoded = res_b64.split(",", 1)
            result_pil = Image.open(io.BytesIO(base64.b64decode(encoded)))
            method_used = "sd-api-img2img"

    # 4. FALLBACK: OpenCV overlay
    if result_pil is None and cloth_pil:
        print("⚠️ Using OpenCV Overlay fallback...")
        result_pil = overlay_garment_fallback(person_pil, cloth_pil, lm, product_category)
        method_used = "opencv-overlay"

    # 5. LAST RESORT: Return original
    if result_pil is None:
        result_pil = person_pil
        method_used = "failed-fallback"

    # ── Calculate metrics ─────────────────────────────────────────────────────
    measurements = get_measurements(lm, person_pil.height, person_pil.width)
    
    if method_used == "pose-warped-overlay":
        curator_note = (
            f"The {product_color} {product_name} has been precisely warped and aligned "
            f"to your body using MediaPipe pose landmarks. Your face, hair, background, "
            f"and exact body proportions are preserved. Recommended size: {measurements['predicted_size']}."
        )
        sd_used_flag = False
    elif method_used in ["stable-diffusion", "sd-api-img2img"]:
        curator_note = (
            f"Our AI model has custom-fitted the {product_color} {product_name} onto your photo. "
            f"The drape and lighting are simulated to match your body shape."
        )
        sd_used_flag = (method_used == "stable-diffusion")
    else:
        curator_note = (
            f"Overlay fit applied. Based on your pose, we recommend size "
            f"{measurements['predicted_size']} for an optimal {measurements['fit_type'].lower()} fit."
        )
        sd_used_flag = False

    # ── Encode and return ─────────────────────────────────────────────────────
    buf = io.BytesIO()
    result_pil.save(buf, format="JPEG", quality=92)
    b64 = base64.b64encode(buf.getvalue()).decode()

    return JSONResponse({
        "success": True,
        "result_image": f"data:image/jpeg;base64,{b64}",
        "method": method_used,
        "landmarksDetected": len(lm),
        "fitAnalysis": measurements["fit_analysis"],
        "predictedSize": measurements["predicted_size"],
        "fitType": measurements["fit_type"],
        "shoulderSpan": measurements["shoulder_span_str"],
        "torsoAlignment": measurements["torso_alignment"],
        "sdUsed": sd_used_flag,
        "curatorNote": curator_note,
    })
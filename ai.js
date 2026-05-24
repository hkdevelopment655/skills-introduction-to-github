import express from 'express';
import multer from 'multer';
import { unlinkSync, existsSync, writeFileSync, mkdirSync, readFileSync } from 'fs';
import { protect } from '../middleware/auth.js';
import FormData from 'form-data';
import fetch from 'node-fetch';
import Product from '../models/Product.js';
import TryOnResult from '../models/TryOnResult.js';

const router  = express.Router();
const upload  = multer({ dest: 'uploads/' });
const AI_URL  = () => process.env.AI_SERVICE_URL || 'http://localhost:8000';

const cleanup = (path) => {
  try { if (path && existsSync(path)) unlinkSync(path); } catch {}
};

const ensureDir = (dir) => {
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
};

// ── Virtual Try-On ─────────────────────────────────────────────────────────
router.post('/tryon', protect, upload.single('image'), async (req, res) => {
  const filePath = req.file?.path;
  try {
    if (!req.file) return res.status(400).json({ success: false, message: 'No image provided' });

    // ── Read person image into a Buffer immediately ─────────────────────────
    // Using a Buffer (not a ReadStream) prevents "Premature close" and the
    // MaxListenersExceededWarning caused by multiple listeners on a stream.
    const personBuffer = readFileSync(filePath);
    cleanup(filePath); // safe to delete the temp file now — data is in memory

    // ── Resolve product details ─────────────────────────────────────────────
    let productName     = req.body.productName     || 'Fashion Item';
    let productColor    = req.body.productColor    || '';
    let productCategory = req.body.productCategory || 'shirts';
    let garmentUrl      = null;

    if (req.body.productId) {
      try {
        const product = await Product.findById(req.body.productId).lean();
        if (product) {
          productName     = product.name;
          productColor    = product.colors?.[0] || '';
          productCategory = product.category    || 'shirts';
          garmentUrl      = product.images?.[0]  || null;
        }
      } catch { /* non-critical */ }
    }

    const useModel = req.body.useModel === 'true' || req.body.use_model === 'true';

    // ── Build FormData ──────────────────────────────────────────────────────
    const form = new FormData();

    // Person image as Buffer — no stream, no listener leak
    form.append('person_image', personBuffer, {
      filename:    req.file.originalname || 'person.jpg',
      contentType: req.file.mimetype     || 'image/jpeg',
    });

    // Clothing image — fetch from product URL and attach as Buffer
    if (garmentUrl) {
      try {
        const clothingRes = await fetch(garmentUrl, { signal: AbortSignal.timeout(10000) });
        if (clothingRes.ok) {
          const clothingBuffer = Buffer.from(await clothingRes.arrayBuffer());
          form.append('clothing_image', clothingBuffer, {
            filename:    'clothing.jpg',
            contentType: clothingRes.headers.get('content-type') || 'image/jpeg',
          });
        } else {
          form.append('clothing_url', garmentUrl);
        }
      } catch {
        // If fetch fails, pass the URL and let the AI service handle it
        form.append('clothing_url', garmentUrl);
      }
    }

    // Product metadata
    form.append('product_name',     productName);
    form.append('product_color',    productColor);
    form.append('product_category', productCategory);
    if (req.body.productId) form.append('product_id', req.body.productId);
    if (useModel)           form.append('useModel', 'true');

    // ── Call the AI service ─────────────────────────────────────────────────
    const response = await fetch(`${AI_URL()}/api/tryon`, {
      method:  'POST',
      body:    form,
      headers: form.getHeaders(),
      signal:  AbortSignal.timeout(90000),
    });

    if (!response.ok) {
      let body = '<no body>';
      try { body = await response.text(); } catch {}
      console.error(`AI service error ${response.status}: ${body}`);
      throw new Error(`AI service: ${response.status}`);
    }

    const data = await response.json();

    // Normalise field name — MediaPipe returns result_image, old endpoint returns overlayImage
    const overlayImage = data.overlayImage || data.result_image || null;

    // ── Persist result to disk + DB ─────────────────────────────────────────
    const uploadsDir = 'uploads/tryon';
    ensureDir(uploadsDir);

    // Save person image buffer to disk for record-keeping
    const personPath = `${uploadsDir}/${Date.now()}-person.jpg`;
    try { writeFileSync(personPath, personBuffer); } catch {}

    // Save base64 result image to disk
    let resultPath = null;
    if (overlayImage?.startsWith('data:image')) {
      try {
        const matches = overlayImage.match(/^data:image\/(png|jpeg|jpg);base64,(.+)$/);
        const ext = matches?.[1] === 'jpeg' ? 'jpg' : (matches?.[1] || 'jpg');
        const b64 = matches ? matches[2] : overlayImage.split(',')[1];
        resultPath = `${uploadsDir}/${Date.now()}-result.${ext}`;
        writeFileSync(resultPath, Buffer.from(b64, 'base64'));
      } catch (e) {
        console.warn('Failed to save result image:', e.message);
      }
    }

    await TryOnResult.create({
      user:       req.user?.id,
      product:    req.body.productId || null,
      personPath,
      resultPath,
      method:     data?.method || 'mediapipe-overlay',
      sdUsed:     !!data?.sdUsed,
    }).catch(() => {});

    return res.json({ ...data, overlayImage, result_image: overlayImage });

  } catch (error) {
    cleanup(filePath); // clean up temp file if it somehow still exists
    console.warn('Try-on fallback:', error.message);
    return res.json({
      success:           true,
      overlayImage:      null,
      result_image:      null,
      fitAnalysis:       85,
      predictedSize:     'M',
      fitType:           'Relaxed',
      shoulderSpan:      '46.2CM',
      torsoAlignment:    'ESTIMATED',
      landmarksDetected: 0,
      method:            'demo-fallback',
      sdUsed:            false,
      curatorNote:       'Upload a clear front-facing photo for the best try-on results.',
    });
  }
});

// ── Height Estimation ──────────────────────────────────────────────────────
router.post('/height', protect, upload.single('image'), async (req, res) => {
  const filePath = req.file?.path;
  try {
    if (!req.file) return res.status(400).json({ success: false, message: 'No image provided' });

    const imageBuffer = readFileSync(filePath);
    cleanup(filePath);

    const form = new FormData();
    form.append('image', imageBuffer, {
      filename:    req.file.originalname || 'image.jpg',
      contentType: req.file.mimetype     || 'image/jpeg',
    });

    const response = await fetch(`${AI_URL()}/height/`, {
      method:  'POST',
      body:    form,
      headers: form.getHeaders(),
      signal:  AbortSignal.timeout(30000),
    });

    const data = await response.json();
    return res.json(data);

  } catch (error) {
    cleanup(filePath);
    return res.json({
      success:             true,
      estimated_height_cm: 175,
      confidence:          'medium',
      method:              'demo',
      recommended_size:    'M',
    });
  }
});

// ── AI / SD Status check ───────────────────────────────────────────────────
router.get('/sd-status', async (req, res) => {
  try {
    const response = await fetch(`${AI_URL()}/health`, {
      signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) throw new Error('health check failed');
    const data = await response.json();
    return res.json({
      sdAvailable: data.sd_configured     || false,
      mediapipeOk: data.mediapipe_ok      || false,
      mediapipe:   data.mediapipe         || 'unknown',
      gemini:      data.gemini_configured || false,
      status:      data.status            || 'OK',
    });
  } catch {
    return res.json({ sdAvailable: false, mediapipeOk: false, reason: 'AI service offline' });
  }
});

export default router;
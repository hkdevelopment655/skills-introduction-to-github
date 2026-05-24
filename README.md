AI service try-on tests
=======================

This folder contains a tiny test runner to validate the `/tryon/` endpoint with
portrait and landscape input images.

Prerequisites
-------------
- AI service running locally (default `http://localhost:8000`).
- Optional: `STABILITY_API_KEY` set in `ai-service/.env` to test Stable Diffusion flow.

Run the tests
-------------
Copy two sample images (one portrait, one landscape) somewhere on your machine, then:

```bash
python ai-service/tests/run_tryon_tests.py \
  --portrait /path/to/portrait.jpg \
  --landscape /path/to/landscape.jpg \
  --garment-url https://example.com/path/to/garment.jpg \
  --ai-url http://localhost:8000
```

Notes
-----
- The script prints full JSON responses and a short summary for each image.
- If the AI service returns non-JSON (error page), the script will include `status_code` and `text`.

#!/usr/bin/env python3
"""Simple test runner for the AI service /tryon endpoint.

Usage:
  python run_tryon_tests.py --portrait /path/to/portrait.jpg --landscape /path/to/landscape.jpg [--garment-url URL] [--ai-url http://localhost:8000]

This script posts two images (portrait and landscape) to the AI service and prints a short summary.
"""
import argparse
import asyncio
import json
import sys
import httpx


async def post_tryon(ai_url, image_path, garment_url=None):
    url = ai_url.rstrip('/') + '/tryon/'
    files = {}
    data = {
        'product_name': 'Test Item',
        'product_color': 'blue',
        'product_category': 'shirts',
    }
    if garment_url:
        data['garment_url'] = garment_url

    with open(image_path, 'rb') as f:
        files['image'] = (image_path.split('/')[-1], f.read(), 'image/jpeg')
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(url, data=data, files=files)
        except Exception as e:
            return {'error': str(e)}

    try:
        return resp.json()
    except Exception:
        return {'status_code': resp.status_code, 'text': resp.text}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ai-url', default='http://localhost:8000', help='AI service base URL')
    parser.add_argument('--portrait', required=True, help='Path to portrait-oriented person image')
    parser.add_argument('--landscape', required=True, help='Path to landscape-oriented person image')
    parser.add_argument('--garment-url', help='Optional garment image URL to pass through')
    args = parser.parse_args()

    print('Testing Portrait image...')
    p_res = await post_tryon(args.ai_url, args.portrait, args.garment_url)
    print('\nPortrait result:')
    print(json.dumps(p_res if isinstance(p_res, dict) else {'result': str(p_res)}, indent=2, ensure_ascii=False))

    print('\nTesting Landscape image...')
    l_res = await post_tryon(args.ai_url, args.landscape, args.garment_url)
    print('\nLandscape result:')
    print(json.dumps(l_res if isinstance(l_res, dict) else {'result': str(l_res)}, indent=2, ensure_ascii=False))

    # Summaries
    print('\nSummary:')
    for name, r in (('portrait', p_res), ('landscape', l_res)):
        if not isinstance(r, dict):
            print(f"- {name}: unexpected response: {r}")
            continue
        if r.get('error'):
            print(f"- {name}: ERROR - {r.get('error')}")
            continue
        ok = r.get('success', False)
        method = r.get('method') or ('sd' if r.get('sdUsed') else 'overlay')
        lm = r.get('landmarksDetected')
        print(f"- {name}: success={ok} method={method} landmarks={lm}")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)

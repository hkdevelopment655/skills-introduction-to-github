"""Generate two sample images (portrait and landscape) for local tests.

Outputs:
 - ai-service/tests/sample_portrait.jpg
 - ai-service/tests/sample_landscape.jpg
"""
from PIL import Image
import os

SRC = os.path.join(os.path.dirname(__file__), '..', 'myenv', 'Lib', 'site-packages', 'matplotlib', 'mpl-data', 'sample_data', 'grace_hopper.jpg')
OUT_P = os.path.join(os.path.dirname(__file__), 'sample_portrait.jpg')
OUT_L = os.path.join(os.path.dirname(__file__), 'sample_landscape.jpg')

def make():
    img = Image.open(SRC).convert('RGB')
    w, h = img.size
    # create portrait crop
    if h < w:
        img_p = img.crop(((w-h)//2, 0, (w+h)//2, h))
    else:
        img_p = img.copy()
    img_p = img_p.resize((720, 1080), Image.LANCZOS)
    img_p.save(OUT_P, quality=90)

    # create landscape crop
    if w < h:
        img_l = img.crop((0, (h-w)//2, w, (h+w)//2))
    else:
        img_l = img.copy()
    img_l = img_l.resize((1280, 720), Image.LANCZOS)
    img_l.save(OUT_L, quality=90)

if __name__ == '__main__':
    make()
    print('Generated:', OUT_P, OUT_L)

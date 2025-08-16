from PIL import Image
import os


def image_compress(img_path):
    # if os.path.getsize(img_path) > 1024 * 1024:
    with Image.open(img_path) as img:
        img = img.convert("RGB")
        img.save(img_path, "JPEG", quality=70, optimize=True)

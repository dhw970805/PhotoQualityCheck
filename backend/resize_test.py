"""对比不同分辨率下图片的大小，帮助选择合适的 LLM_IMAGE_MAX_WIDTH。"""
import os
import sys
from PIL import Image, ImageOps

IMAGE_PATH = sys.argv[1] if len(sys.argv) > 1 else None
WIDTHS = [2048, 1280, 1024, 768, 512, 384, 256]
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '_resize_test')


def resize_and_save(image_path, max_width, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(image_path))[0]

    with Image.open(image_path) as img:
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        orig_size = img.size
        w, h = img.size
        if w <= max_width:
            new_w, new_h = w, h
            img_resized = img
        else:
            ratio = max_width / w
            new_h = int(h * ratio)
            new_w = max_width
            img_resized = img.resize((new_w, new_h), Image.LANCZOS)

        if img_resized.mode in ('RGBA', 'P'):
            img_resized = img_resized.convert('RGB')

        out_path = os.path.join(output_dir, f"{base}_{max_width}px.jpg")
        img_resized.save(out_path, format='JPEG', quality=85)
        size_kb = os.path.getsize(out_path) / 1024
        print(f"{max_width:>5}px | {new_w}x{new_h} | {size_kb:>8.1f} KB | {out_path}")


if __name__ == '__main__':
    if not IMAGE_PATH or not os.path.isfile(IMAGE_PATH):
        print(f"用法: python {sys.argv[0]} <图片路径>")
        sys.exit(1)

    with Image.open(IMAGE_PATH) as img:
        print(f"原图: {img.size[0]}x{img.size[1]} ({os.path.getsize(IMAGE_PATH)/1024:.1f} KB)")
    print("-" * 70)
    for w in WIDTHS:
        resize_and_save(IMAGE_PATH, w, OUTPUT_DIR)

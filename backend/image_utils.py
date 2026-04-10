import io
import os
import logging
from PIL import Image, ImageOps

from config import RAW_EXTENSIONS

logger = logging.getLogger(__name__)


def open_image(file_path):
    """Open an image file, handling RAW formats via embedded JPEG extraction. Returns PIL Image."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext in RAW_EXTENSIONS:
        img = _extract_embedded_jpeg(file_path)
        if img is not None:
            return img
        raise ValueError(f"Cannot open RAW file: {file_path}")

    return Image.open(file_path)


def open_and_prepare_image(file_path, max_width=None):
    """Open an image with correct orientation applied. Optionally resize.

    Handles RAW files, EXIF orientation, and conversion to RGB.
    This is the single canonical way to open an image for processing.
    """
    img = open_image(file_path)
    try:
        img = ImageOps.exif_transpose(img)

        if max_width and img.size[0] > max_width:
            ratio = max_width / img.size[0]
            new_h = int(img.size[1] * ratio)
            img = img.resize((max_width, new_h), Image.LANCZOS)

        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        return img
    except Exception:
        img.close()
        raise


# --- EXIF helpers ---

def get_exif_orientation(img):
    """Read EXIF orientation from a PIL Image object."""
    try:
        exif = img.getexif()
        return exif.get(0x0112)
    except Exception:
        return None


def _clear_exif_orientation(img):
    """Set EXIF orientation to 1 (normal) to prevent double-rotation."""
    try:
        exif = img.getexif()
        if 0x0112 in exif:
            exif[0x0112] = 1
            img.info['exif'] = exif.tobytes()
    except Exception:
        pass


def _get_orientation_via_exiftool(file_path):
    """Read EXIF orientation from any image file using ExifTool."""
    import subprocess

    # ExifTool bundled at backend/exiftool-13.54_64/
    exiftool_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'exiftool-13.54_64')
    exiftool_path = os.path.join(exiftool_dir, 'exiftool(-k).exe')

    if not os.path.isfile(exiftool_path):
        logger.debug(f"ExifTool not found at {exiftool_path}")
        return None

    try:
        result = subprocess.run(
            [exiftool_path, '-Orientation#', file_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            val = result.stdout.strip()
            # val may be "8" or "Orientation                     : 8" — extract first integer
            parts = val.split()
            for part in parts:
                if part.isdigit():
                    orientation = int(part)
                    return orientation if orientation != 0 else None
    except Exception as e:
        logger.debug(f"exiftool failed for {os.path.basename(file_path)}: {e}")
    return None


# --- RAW file support ---

def _extract_embedded_jpeg(file_path):
    """Extract the largest embedded JPEG preview from a RAW file.

    All RAW formats (CR2, CR3, NEF, ARW, etc.) contain embedded JPEG previews.
    This fallback works when rawpy/libraw cannot decode a specific format.
    """
    fname = os.path.basename(file_path)
    try:
        with open(file_path, 'rb') as f:
            data = f.read()

        # Find all JPEG streams by SOI (FFD8FF) and EOI (FFD9) markers
        jpegs = []
        pos = 0
        while True:
            idx = data.find(b'\xff\xd8\xff', pos)
            if idx == -1:
                break
            eoi = data.find(b'\xff\xd9', idx + 3)
            if eoi == -1:
                break
            jpegs.append((idx, eoi + 2))
            pos = eoi + 2

        if not jpegs:
            logger.warning(f"[{fname}] No embedded JPEG found in RAW file")
            return None

        # Pick the largest JPEG (full-size preview, not tiny thumbnail)
        start, end = max(jpegs, key=lambda x: x[1] - x[0])
        jpeg_size_kb = (end - start) / 1024
        img = Image.open(io.BytesIO(data[start:end]))

        # Check EXIF orientation in the JPEG itself
        jpeg_exif_orientation = get_exif_orientation(img)

        # Read orientation from the original file via exiftool (handles CR3, NEF, etc.)
        file_orientation = _get_orientation_via_exiftool(file_path)

        logger.info(f"[{fname}] embedded JPEG: {jpeg_size_kb:.0f}KB, "
                     f"JPEG EXIF orientation={jpeg_exif_orientation}, "
                     f"file orientation={file_orientation}")

        # Prefer file-level orientation (authoritative for CR3/NEF/etc.)
        orientation = file_orientation or jpeg_exif_orientation
        if orientation and orientation != 1:
            _TRANSPOSE_MAP = {
                2: Image.Transpose.FLIP_LEFT_RIGHT,
                3: Image.Transpose.ROTATE_180,
                4: Image.Transpose.FLIP_TOP_BOTTOM,
                5: Image.Transpose.TRANSPOSE,
                6: Image.Transpose.ROTATE_270,
                7: Image.Transpose.TRANSVERSE,
                8: Image.Transpose.ROTATE_90,
            }
            transpose_op = _TRANSPOSE_MAP.get(orientation)
            if transpose_op:
                logger.info(f"[{fname}] Applying rotation: orientation={orientation} -> {transpose_op}")
                img = img.transpose(transpose_op)
                # Clear EXIF orientation tag to prevent double-rotation by callers
                _clear_exif_orientation(img)

        if img.mode != 'RGB':
            img = img.convert('RGB')
        return img
    except Exception as e:
        logger.warning(f"[{fname}] Embedded JPEG extraction failed: {e}")
        return None

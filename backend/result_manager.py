import json
import hashlib
import io
import os
import logging
from PIL import Image

from config import IMAGE_EXTENSIONS, THUMBNAIL_WIDTH, THUMBNAIL_SUBDIR, RAW_EXTENSIONS

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
        jpeg_exif_orientation = _get_exif_orientation_from_image(img)

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


def _get_exif_orientation_from_image(img):
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


def compute_file_hash(file_path):
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception:
        return ''


def get_image_files(folder_path):
    """Get all image files in the folder."""
    files = []
    if not os.path.isdir(folder_path):
        return files
    for fname in os.listdir(folder_path):
        ext = os.path.splitext(fname)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            files.append(fname)
    return sorted(files)


def load_result_json(folder_path):
    """Load or create result.json from the folder."""
    result_path = os.path.join(folder_path, 'result.json')
    if os.path.exists(result_path):
        try:
            with open(result_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {'photos': []}


def save_result_json(folder_path, data):
    """Save result.json to the folder."""
    result_path = os.path.join(folder_path, 'result.json')
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _generate_thumbnail(folder_path, file_name):
    """Generate a thumbnail for one image. Returns True on success."""
    src_path = os.path.join(folder_path, file_name)
    thumb_dir = os.path.join(folder_path, THUMBNAIL_SUBDIR)
    thumb_path = os.path.join(thumb_dir, file_name + '.jpg')

    if os.path.exists(thumb_path):
        return True

    try:
        os.makedirs(thumb_dir, exist_ok=True)
        img = open_image(src_path)
        try:
            # EXIF orientation (for non-RAW images; RAW images already oriented by open_image)
            try:
                from PIL import ImageOps
                exif_orient = _get_exif_orientation_from_image(img)
                if exif_orient and exif_orient != 1:
                    logger.info(f"[{file_name}] exif_transpose: orientation={exif_orient}")
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass

            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            w, h = img.size
            if w <= THUMBNAIL_WIDTH:
                img.save(thumb_path, format='JPEG', quality=85)
            else:
                ratio = THUMBNAIL_WIDTH / w
                new_h = int(h * ratio)
                img = img.resize((THUMBNAIL_WIDTH, new_h), Image.LANCZOS)
                img.save(thumb_path, format='JPEG', quality=85)
        finally:
            img.close()
        return True
    except Exception as e:
        logger.warning(f"Failed to generate thumbnail for {file_name}: {e}")
        return False


def ensure_thumbnails(folder_path, file_names, on_progress=None):
    """Generate thumbnails for all given files. Skips existing ones.
    on_progress(current, total) is called after each thumbnail."""
    thumb_dir = os.path.join(folder_path, THUMBNAIL_SUBDIR)
    os.makedirs(thumb_dir, exist_ok=True)

    total = len(file_names)
    for i, fname in enumerate(file_names):
        _generate_thumbnail(folder_path, fname)
        done = i + 1
        if on_progress:
            on_progress(done, total)
        if done % 100 == 0 or done == total:
            logger.info(f"Thumbnails: {done}/{total}")


def init_photos(folder_path, on_progress=None):
    """Initialize result.json with all photos in the folder.
    Also ensures thumbnails exist for all images.
    on_progress(current, total) is called during thumbnail generation.
    Returns the full result data."""
    result = load_result_json(folder_path)
    existing_names = {
        p['photo_metadata']['file_info']['file_name'] for p in result['photos']
    }

    image_files = get_image_files(folder_path)

    # Always ensure thumbnails exist (skips already generated ones)
    logger.info(f"Ensuring thumbnails for {len(image_files)} images...")
    ensure_thumbnails(folder_path, image_files, on_progress=on_progress)

    for fname in image_files:
        if fname not in existing_names:
            file_path = os.path.join(folder_path, fname)
            file_hash = compute_file_hash(file_path)
            result['photos'].append({
                'photo_metadata': {
                    'file_info': {
                        'file_name': fname,
                        'file_path': file_path,
                        'hash': file_hash,
                    },
                    'quality': [],
                    'status': '未检测',
                    'scores': {
                        'expression': 0,
                        'composition': 0,
                        'exposure': 0,
                    },
                    'advise': '',
                    'reason': '',
                },
            })

    save_result_json(folder_path, result)
    return result


def update_photo_result(folder_path, file_name, updates):
    """Update a single photo's result in result.json."""
    result = load_result_json(folder_path)
    for photo in result['photos']:
        if photo['photo_metadata']['file_info']['file_name'] == file_name:
            meta = photo['photo_metadata']
            if 'status' in updates:
                meta['status'] = updates['status']
            if 'quality' in updates:
                meta['quality'] = updates['quality']
            if 'scores' in updates:
                meta['scores'] = updates['scores']
            if 'advise' in updates:
                meta['advise'] = updates['advise']
            if 'reason' in updates:
                meta['reason'] = updates['reason']
            break
    save_result_json(folder_path, result)
    return result


def reset_photo_status(folder_path, file_name):
    """Reset a photo's status to '未检测' for retry."""
    return update_photo_result(folder_path, file_name, {
        'status': '未检测',
        'quality': [],
        'advise': '',
        'reason': '',
        'scores': {'expression': 0, 'composition': 0, 'exposure': 0},
    })

import json
import hashlib
import os
import logging

from config import IMAGE_EXTENSIONS, THUMBNAIL_WIDTH, THUMBNAIL_SUBDIR
from image_utils import open_and_prepare_image

logger = logging.getLogger(__name__)


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


# --- result.json management ---

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


# --- Thumbnails ---

def _generate_thumbnail(folder_path, file_name):
    """Generate a thumbnail for one image. Returns True on success."""
    src_path = os.path.join(folder_path, file_name)
    thumb_dir = os.path.join(folder_path, THUMBNAIL_SUBDIR)
    thumb_path = os.path.join(thumb_dir, file_name + '.jpg')

    if os.path.exists(thumb_path):
        return True

    try:
        os.makedirs(thumb_dir, exist_ok=True)
        img = open_and_prepare_image(src_path, max_width=THUMBNAIL_WIDTH)
        try:
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


# --- Photo initialization ---

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


# --- Photo result updates ---

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

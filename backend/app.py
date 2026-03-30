import logging
import os
import sys
import threading
import traceback

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO

# Ensure backend package imports work when run as `python app.py`
from config import FLASK_HOST, FLASK_PORT, DEBUG, LOG_FILE, LOG_FORMAT, USE_MOCK_LLM, THUMBNAIL_SUBDIR
from result_manager import init_photos, load_result_json, update_photo_result
from mediapipe_engine import analyze_image

if USE_MOCK_LLM:
    from mock_llm_response import mock_analyze as analyze_with_llm
    logger_info_mode = "Mock LLM (随机模拟)"
else:
    from llm_client import analyze_with_llm
    logger_info_mode = "Qwen-3.5Plus (真实API)"
from export_manager import export_photos

# Chroma DB placeholder (not implemented per spec)
# from .chroma_store import ChromaStore

# --- Logging setup ---
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
    ],
)
logger = logging.getLogger(__name__)

# --- Flask App ---
app = Flask(__name__)
CORS(app, resources={r'/api/*': {'origins': '*'}})
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

# --- Pipeline State ---
_pipeline_thread = None
_cancel_event = threading.Event()


# --- REST API Routes ---

@app.route('/api/photos', methods=['POST'])
def api_load_photos():
    """Load photos from a folder, initialize result.json if needed."""
    data = request.get_json()
    folder_path = data.get('folder_path', '')

    if not folder_path or not os.path.isdir(folder_path):
        return jsonify({'error': '无效的文件夹路径'}), 400

    try:
        result = init_photos(folder_path)
        return jsonify({'photos': result['photos']})
    except Exception as e:
        logger.error(f"Failed to load photos: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/start', methods=['POST'])
def api_start_detection():
    """Start the photo analysis pipeline."""
    global _pipeline_thread, _cancel_event

    data = request.get_json()
    folder_path = data.get('folder_path', '')

    if not folder_path or not os.path.isdir(folder_path):
        return jsonify({'error': '无效的文件夹路径'}), 400

    if _pipeline_thread and _pipeline_thread.is_alive():
        return jsonify({'error': '检测正在进行中'}), 409

    _cancel_event.clear()
    _pipeline_thread = threading.Thread(
        target=run_pipeline,
        args=(folder_path,),
        daemon=True,
    )
    _pipeline_thread.start()

    return jsonify({'status': 'started'})


@app.route('/api/cancel', methods=['POST'])
def api_cancel_detection():
    """Cancel the running pipeline."""
    global _cancel_event
    _cancel_event.set()
    return jsonify({'status': 'cancelled'})


@app.route('/api/retry/<filename>', methods=['POST'])
def api_retry_photo(filename):
    """Reset and retry a single photo."""
    data = request.get_json()
    folder_path = data.get('folder_path', '')

    if not folder_path:
        return jsonify({'error': '缺少文件夹路径'}), 400

    try:
        update_photo_result(folder_path, filename, {
            'status': '未检测',
            'quality': [],
            'advise': '',
            'reason': '',
            'scores': {'expression': 0, 'composition': 0, 'exposure': 0},
        })

        # Process this single photo in a background thread
        t = threading.Thread(
            target=process_single_photo,
            args=(folder_path, filename),
            daemon=True,
        )
        t.start()

        return jsonify({'status': 'retrying'})
    except Exception as e:
        logger.error(f"Retry failed for {filename}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/update-result', methods=['POST'])
def api_update_result():
    """Update a photo's result (from user edits in detail panel)."""
    data = request.get_json()
    folder_path = data.get('folder_path', '')
    file_name = data.get('file_name', '')
    updates = data.get('updates', {})

    if not folder_path or not file_name:
        return jsonify({'error': '缺少参数'}), 400

    try:
        update_photo_result(folder_path, file_name, updates)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Update result failed: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/export', methods=['POST'])
def api_export():
    """Export photos to categorized subfolders."""
    data = request.get_json()
    folder_path = data.get('folder_path', '')

    if not folder_path or not os.path.isdir(folder_path):
        return jsonify({'error': '无效的文件夹路径'}), 400

    try:
        result = export_photos(folder_path)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Export failed: {e}")
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/image/<path:filepath>')
def api_serve_image(filepath):
    """Serve original image from any folder (used for detail panel preview)."""
    # filepath is like "D:/photos/IMG001.JPG" or "D:\\photos\\IMG001.JPG"
    safe_path = os.path.normpath(filepath)
    # Security: only allow absolute paths that exist
    if not os.path.isabs(safe_path) or not os.path.isfile(safe_path):
        return jsonify({'error': 'file not found'}), 404
    directory = os.path.dirname(safe_path)
    filename = os.path.basename(safe_path)
    return send_from_directory(directory, filename)


@app.route('/api/thumb/<path:filepath>')
def api_serve_thumbnail(filepath):
    """Serve thumbnail for an image."""
    safe_path = os.path.normpath(filepath)
    if not os.path.isabs(safe_path) or not os.path.isfile(safe_path):
        return jsonify({'error': 'file not found'}), 404

    directory = os.path.dirname(safe_path)
    filename = os.path.basename(safe_path)
    thumb_dir = os.path.join(directory, THUMBNAIL_SUBDIR)
    thumb_path = os.path.join(thumb_dir, filename)

    if os.path.isfile(thumb_path):
        return send_from_directory(thumb_dir, filename)

    # Fallback to original if thumbnail doesn't exist
    return send_from_directory(directory, filename)


# --- Analysis Pipeline ---

def run_pipeline(folder_path):
    """Main pipeline: process all undetected photos."""
    global _cancel_event

    try:
        result = load_result_json(folder_path)
        photos_to_process = [
            p for p in result['photos']
            if p['photo_metadata']['status'] == '未检测'
        ]

        total = len(photos_to_process)
        logger.info(f"Pipeline started: {total} photos to process from {folder_path}")

        socketio.emit('pipeline_progress', {'type': 'progress', 'current': 0, 'total': total})

        processed = 0
        for photo in photos_to_process:
            if _cancel_event.is_set():
                logger.info("Pipeline cancelled by user")
                socketio.emit('pipeline_error', {
                    'type': 'error',
                    'message': '检测已被用户取消',
                })
                break

            file_name = photo['photo_metadata']['file_info']['file_name']
            file_path = photo['photo_metadata']['file_info']['file_path']

            try:
                process_one_photo(folder_path, file_name, file_path)
            except Exception as e:
                logger.error(f"Error processing {file_name}: {e}")
                traceback.print_exc()

            processed += 1
            socketio.emit('pipeline_progress', {'type': 'progress', 'current': processed, 'total': total})

        socketio.emit('pipeline_complete', {'type': 'complete', 'processed': processed})
        logger.info(f"Pipeline complete: {processed}/{total} photos processed")

    except Exception as e:
        logger.error(f"Pipeline fatal error: {e}")
        traceback.print_exc()
        socketio.emit('pipeline_error', {'type': 'error', 'message': str(e)})


def process_single_photo(folder_path, file_name):
    """Process a single photo (for retry)."""
    result = load_result_json(folder_path)
    file_path = None
    for p in result['photos']:
        if p['photo_metadata']['file_info']['file_name'] == file_name:
            file_path = p['photo_metadata']['file_info']['file_path']
            break

    if not file_path:
        logger.error(f"Photo not found: {file_name}")
        return

    try:
        process_one_photo(folder_path, file_name, file_path)
        socketio.emit('pipeline_complete', {'type': 'complete', 'processed': 1})
    except Exception as e:
        logger.error(f"Retry error for {file_name}: {e}")
        socketio.emit('pipeline_error', {'type': 'error', 'message': str(e)})


def process_one_photo(folder_path, file_name, file_path):
    """Process a single photo through the pipeline."""
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return

    # Step 1: MediaPipe analysis
    mp_result = analyze_image(file_path)

    if not mp_result['face_found']:
        # No face detected -> mark as 需复核, skip LLM
        logger.info(f"No face in {file_name}, marking as 需复核")
        update_photo_result(folder_path, file_name, {
            'status': '需复核',
            'quality': ['需复核'],
            'reason': '未检测到人脸，需要人工复核',
        })
        _emit_photo_update(folder_path, file_name)
        return

    # Step 2: LLM analysis
    llm_result = analyze_with_llm(file_path)

    if llm_result is None:
        # LLM failed -> keep as 未检测, don't block pipeline
        logger.warning(f"LLM failed for {file_name}, keeping as 未检测")
        return

    # Step 3: Aggregate results
    is_bad = llm_result.get('is_bad_photo', False)
    reasons = llm_result.get('reasons', [])

    # Ensure reasons only contain valid quality tags
    valid_qualities = {'闭眼', '表情差', '构图差', '欠曝', '过曝', '合格', '需复核'}
    reasons = [r for r in reasons if r in valid_qualities]

    if is_bad:
        status = '需复核'
        quality = reasons if reasons else ['需复核']
    else:
        status = '合格'
        quality = ['合格']

    # If MediaPipe detected closed eyes but LLM didn't flag it, trust MediaPipe
    if mp_result.get('eyes_closed') and not mp_result.get('smile_detected'):
        if '闭眼' not in quality:
            quality.append('闭眼')
        if status == '合格':
            status = '需复核'

    detailed_analysis = llm_result.get('detailed_analysis', '')

    updates = {
        'status': status,
        'quality': quality,
        'scores': {
            'expression': llm_result.get('expressionScore', 0),
            'composition': llm_result.get('compositionScore', 0),
            'exposure': llm_result.get('exposureScore', 0),
        },
        'advise': detailed_analysis,
        'reason': '; '.join(reasons) if reasons else '',
    }

    update_photo_result(folder_path, file_name, updates)
    logger.info(f"Processed {file_name}: status={status}, quality={quality}")

    _emit_photo_update(folder_path, file_name)


def _emit_photo_update(folder_path, file_name):
    """Read the latest result for a photo and emit via WebSocket."""
    result = load_result_json(folder_path)
    for photo in result['photos']:
        if photo['photo_metadata']['file_info']['file_name'] == file_name:
            # Add folder path for frontend thumbnail rendering
            photo_with_path = dict(photo)
            photo_with_path['_folderPath'] = folder_path
            socketio.emit('photo_update', {'type': 'photo_result', 'photo': photo_with_path})
            break


# --- Run ---
def main():
    logger.info(f"Starting Flask server on {FLASK_HOST}:{FLASK_PORT}")
    socketio.run(app, host=FLASK_HOST, port=FLASK_PORT, debug=DEBUG, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    main()

import logging
import os
import sys
import threading

from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
from flask_socketio import SocketIO

from config import FLASK_HOST, FLASK_PORT, DEBUG, LOG_FILE, LOG_FORMAT, USE_MOCK_LLM, THUMBNAIL_SUBDIR
from result_manager import init_photos, update_photo_result
from export_manager import export_photos
import pipeline

# --- LLM backend selection ---
if USE_MOCK_LLM:
    from mock_llm_response import mock_analyze as analyze_with_llm
    from mock_llm_response import mock_analyze_batch as analyze_batch_with_llm
    logger_info_mode = "Mock LLM (随机模拟)"
else:
    from llm_client import analyze_with_llm
    from llm_client import analyze_batch_with_llm
    logger_info_mode = "Qwen-3.5Plus (真实API)"

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

# Initialize pipeline module with socketio instance
pipeline.init(socketio)

# --- Pipeline thread ---
_pipeline_thread = None


# --- REST API Routes ---

@app.route('/api/photos', methods=['POST'])
def api_load_photos():
    """Load photos from a folder, initialize result.json if needed."""
    data = request.get_json()
    folder_path = data.get('folder_path', '')

    if not folder_path or not os.path.isdir(folder_path):
        return jsonify({'error': '无效的文件夹路径'}), 400

    try:
        def on_import_progress(current, total):
            socketio.emit('import_progress', {'type': 'import_progress', 'current': current, 'total': total})

        result = init_photos(folder_path, on_progress=on_import_progress)
        socketio.emit('import_progress', {'type': 'import_progress', 'current': 0, 'total': 0})
        return jsonify({'photos': result['photos']})
    except Exception as e:
        logger.error(f"Failed to load photos: {e}")
        socketio.emit('import_progress', {'type': 'import_progress', 'current': 0, 'total': 0})
        return jsonify({'error': str(e)}), 500


@app.route('/api/start', methods=['POST'])
def api_start_detection():
    """Start the photo analysis pipeline."""
    global _pipeline_thread

    data = request.get_json()
    folder_path = data.get('folder_path', '')

    if not folder_path or not os.path.isdir(folder_path):
        return jsonify({'error': '无效的文件夹路径'}), 400

    if _pipeline_thread and _pipeline_thread.is_alive():
        return jsonify({'error': '检测正在进行中'}), 409

    pipeline.cancel()
    _pipeline_thread = threading.Thread(
        target=pipeline.run_pipeline,
        args=(folder_path, analyze_batch_with_llm),
        daemon=True,
    )
    _pipeline_thread.start()

    return jsonify({'status': 'started'})


@app.route('/api/cancel', methods=['POST'])
def api_cancel_detection():
    """Cancel the running pipeline."""
    pipeline.cancel()
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

        t = threading.Thread(
            target=pipeline.process_single_photo,
            args=(folder_path, filename, analyze_with_llm),
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
    safe_path = os.path.normpath(filepath)
    if not os.path.isabs(safe_path) or not os.path.isfile(safe_path):
        return jsonify({'error': 'file not found'}), 404
    directory = os.path.dirname(safe_path)
    filename = os.path.basename(safe_path)
    resp = make_response(send_from_directory(directory, filename))
    resp.headers['Cache-Control'] = 'public, max-age=86400'
    return resp


@app.route('/api/thumb/<path:filepath>')
def api_serve_thumbnail(filepath):
    """Serve thumbnail for an image."""
    safe_path = os.path.normpath(filepath)
    if not os.path.isabs(safe_path) or not os.path.isfile(safe_path):
        return jsonify({'error': 'file not found'}), 404

    directory = os.path.dirname(safe_path)
    filename = os.path.basename(safe_path)
    thumb_dir = os.path.join(directory, THUMBNAIL_SUBDIR)
    thumb_path = os.path.join(thumb_dir, filename + '.jpg')

    if os.path.isfile(thumb_path):
        resp = make_response(send_from_directory(thumb_dir, filename + '.jpg'))
        resp.headers['Cache-Control'] = 'public, max-age=604800'
        return resp

    # Fallback to original if thumbnail doesn't exist
    resp = make_response(send_from_directory(directory, filename))
    resp.headers['Cache-Control'] = 'public, max-age=86400'
    return resp


# --- Run ---
def main():
    logger.info(f"Starting Flask server on {FLASK_HOST}:{FLASK_PORT} (LLM: {logger_info_mode})")
    socketio.run(app, host=FLASK_HOST, port=FLASK_PORT, debug=DEBUG, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    main()

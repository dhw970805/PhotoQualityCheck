import concurrent.futures
import logging
import os
import threading
import traceback

from config import BATCH_SIZE, MAX_CONCURRENCY
from result_manager import load_result_json, update_photo_result
from tag_mapper import map_llm_result_to_updates

logger = logging.getLogger(__name__)

_socketio = None
_cancel_event = None
_result_lock = None


def init(socketio):
    """Initialize pipeline with Flask-SocketIO instance."""
    global _socketio, _cancel_event, _result_lock
    _socketio = socketio
    _cancel_event = threading.Event()
    _result_lock = threading.Lock()


def cancel():
    """Cancel the running pipeline."""
    if _cancel_event:
        _cancel_event.set()


def is_cancelled():
    """Check if pipeline has been cancelled."""
    return _cancel_event.is_set() if _cancel_event else False


def get_result_lock():
    """Get the result lock for concurrent result.json access."""
    return _result_lock


# --- Pipeline orchestration ---

def run_pipeline(folder_path, analyze_batch_fn):
    """Main pipeline: process all undetected photos concurrently.

    Args:
        folder_path: Path to the photo folder.
        analyze_batch_fn: Callable(list[str]) -> list[dict|None] for batch LLM analysis.
    """
    try:
        result = load_result_json(folder_path)
        photos_to_process = [
            p for p in result['photos']
            if p['photo_metadata']['status'] == '未检测'
        ]

        total = len(photos_to_process)
        if total == 0:
            _socketio.emit('pipeline_complete', {'type': 'complete', 'processed': 0})
            return

        logger.info(f"Pipeline started: {total} photos to process (concurrency={MAX_CONCURRENCY}) from {folder_path}")
        _socketio.emit('pipeline_progress', {'type': 'progress', 'current': 0, 'total': total})

        # Build (file_name, file_path) list and split into batches
        photo_list = [
            (p['photo_metadata']['file_info']['file_name'], p['photo_metadata']['file_info']['file_path'])
            for p in photos_to_process
        ]

        batches = []
        for i in range(0, len(photo_list), BATCH_SIZE):
            batch = photo_list[i:i + BATCH_SIZE]
            batches.append(([fn for fn, _ in batch], [fp for _, fp in batch]))

        # Thread-safe progress counter
        progress_lock = threading.Lock()
        processed_count = [0]

        def on_batch_done(batch_size):
            with progress_lock:
                processed_count[0] += batch_size
                current = processed_count[0]
            _socketio.emit('pipeline_progress', {'type': 'progress', 'current': current, 'total': total})

        # Submit batches to thread pool, process concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as executor:
            future_to_size = {}
            for batch_names, batch_paths in batches:
                if _cancel_event.is_set():
                    break
                future = executor.submit(process_batch, folder_path, batch_names, batch_paths, analyze_batch_fn)
                future_to_size[future] = len(batch_names)

            for future in concurrent.futures.as_completed(future_to_size):
                if _cancel_event.is_set():
                    break
                batch_size = future_to_size[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Batch error: {e}")
                    traceback.print_exc()
                on_batch_done(batch_size)

        if _cancel_event.is_set():
            logger.info("Pipeline cancelled by user")
            _socketio.emit('pipeline_error', {
                'type': 'error',
                'message': '检测已被用户取消',
            })
        else:
            with progress_lock:
                final = processed_count[0]
            _socketio.emit('pipeline_complete', {'type': 'complete', 'processed': final})
            logger.info(f"Pipeline complete: {final}/{total} photos processed")

    except Exception as e:
        logger.error(f"Pipeline fatal error: {e}")
        traceback.print_exc()
        _socketio.emit('pipeline_error', {'type': 'error', 'message': str(e)})


def process_single_photo(folder_path, file_name, analyze_fn):
    """Process a single photo (for retry).

    Args:
        folder_path: Path to the photo folder.
        file_name: Name of the photo file.
        analyze_fn: Callable(str) -> dict|None for single image LLM analysis.
    """
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
        process_one_photo(folder_path, file_name, file_path, analyze_fn)
        _socketio.emit('pipeline_complete', {'type': 'complete', 'processed': 1})
    except Exception as e:
        logger.error(f"Retry error for {file_name}: {e}")
        _socketio.emit('pipeline_error', {'type': 'error', 'message': str(e)})


# --- Internal helpers ---

def _apply_llm_result(folder_path, file_name, llm_result):
    """Apply a parsed LLM result to a photo's record and emit WebSocket update."""
    with _result_lock:
        updates = map_llm_result_to_updates(llm_result)
        update_photo_result(folder_path, file_name, updates)
        logger.info(f"Processed {file_name}: status={updates['status']}, quality={updates['quality']}")
        _emit_photo_update(folder_path, file_name)


def process_batch(folder_path, file_names, file_paths, analyze_batch_fn):
    """Process a batch of photos through the LLM pipeline."""
    if _cancel_event.is_set():
        return

    # Filter to existing files
    valid = [(n, p) for n, p in zip(file_names, file_paths) if os.path.exists(p)]
    if not valid:
        return

    valid_names = [n for n, p in valid]
    valid_paths = [p for n, p in valid]

    llm_results = analyze_batch_fn(valid_paths)

    for name, result in zip(valid_names, llm_results):
        if result is not None:
            _apply_llm_result(folder_path, name, result)
        else:
            logger.warning(f"No LLM result for {name}, keeping as 未检测")


def process_one_photo(folder_path, file_name, file_path, analyze_fn):
    """Process a single photo through the pipeline (used for retry)."""
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return

    llm_result = analyze_fn(file_path)

    if llm_result is None:
        logger.warning(f"LLM failed for {file_name}, keeping as 未检测")
        return

    _apply_llm_result(folder_path, file_name, llm_result)


def _emit_photo_update(folder_path, file_name):
    """Read the latest result for a photo and emit via WebSocket."""
    result = load_result_json(folder_path)
    for photo in result['photos']:
        if photo['photo_metadata']['file_info']['file_name'] == file_name:
            # Add folder path for frontend thumbnail rendering
            photo_with_path = dict(photo)
            photo_with_path['_folderPath'] = folder_path
            _socketio.emit('photo_update', {'type': 'photo_result', 'photo': photo_with_path})
            break

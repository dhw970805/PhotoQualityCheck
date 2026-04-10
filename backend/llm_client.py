import base64
import io
import json
import logging
import os
import time
import requests

from config import QWEN_API_KEY, QWEN_API_URL, QWEN_MODEL, QWEN_TIMEOUT, LLM_IMAGE_MAX_WIDTH
from image_utils import open_and_prepare_image
from prompts import PROMPT_TEMPLATE, BATCH_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


# --- Helpers ---

def _parse_llm_json(content):
    """Strip markdown wrappers and parse JSON from LLM response."""
    content = content.strip()
    if content.startswith('```'):
        lines = content.split('\n')
        lines = [l for l in lines if not l.strip().startswith('```')]
        content = '\n'.join(lines).strip()
    return json.loads(content)


def _log_token_usage(data, label=""):
    """Log token usage from API response. Returns token_usage dict or None."""
    if 'usage' not in data:
        return None
    token_usage = data['usage']
    logger.info(f"Token usage{label}: prompt={token_usage.get('prompt_tokens')}, "
                f"cached={token_usage.get('prompt_tokens_details', {}).get('cached_tokens', 0)}, "
                f"completion={token_usage.get('completion_tokens')}, "
                f"total={token_usage.get('total_tokens')}")
    return token_usage


def _post_to_llm(payload):
    """Send payload to Qwen API. Returns (data, elapsed) or raises."""
    headers = {
        'Authorization': f'Bearer {QWEN_API_KEY}',
        'Content-Type': 'application/json',
    }
    response = requests.post(QWEN_API_URL, json=payload, headers=headers, timeout=QWEN_TIMEOUT)
    if response.status_code != 200:
        logger.error(f"LLM API error {response.status_code}: {response.text[:200]}")
        raise RuntimeError(f"API error {response.status_code}")
    return response.json()


# --- Encoding ---

def encode_image_base64(image_path):
    """Encode an image file to base64, resizing if necessary to stay under API limits."""
    try:
        img = open_and_prepare_image(image_path, max_width=LLM_IMAGE_MAX_WIDTH)
        try:
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=85)
            return base64.b64encode(buf.getvalue()).decode('utf-8')
        finally:
            img.close()
    except Exception as e:
        logger.error(f"Failed to encode image {image_path}: {e}")
        return None


# --- Analysis ---

def analyze_with_llm(image_path):
    """Send image to Qwen-3.5Plus for quality analysis.

    Returns:
        dict or None: Parsed LLM response, or None on failure.
    """
    t0 = time.time()
    image_b64 = encode_image_base64(image_path)
    if not image_b64:
        return None
    t_encode = time.time() - t0
    payload_size_mb = len(image_b64) * 3 / 4 / 1024 / 1024

    payload = {
        'model': QWEN_MODEL,
        'messages': [
            {
                'role': 'system',
                'content': PROMPT_TEMPLATE,
                'cache_control': {'type': 'ephemeral'},
            },
            {
                'role': 'user',
                'content': [
                    {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{image_b64}'}},
                ],
            },
        ],
        'max_tokens': 500,
        'temperature': 0.8,
        'top_p': 0.9,
        'enable_thinking': True,
    }

    fname = os.path.basename(image_path)
    try:
        logger.info(f"Sending image to LLM: {fname} "
                     f"(encode={t_encode:.2f}s, payload={payload_size_mb:.1f}MB)")
        t1 = time.time()
        data = _post_to_llm(payload)
        t_request = time.time() - t1
        logger.info(f"LLM response for {fname}: total={t_encode + t_request:.1f}s")

        logger.info(f"Full API response: {json.dumps(data, ensure_ascii=False)[:1000]}")
        token_usage = _log_token_usage(data)

        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        if not content:
            logger.error(f"Empty LLM response for {fname}")
            return None

        result = _parse_llm_json(content)
        result['_token_usage'] = token_usage
        result['_elapsed_seconds'] = round(t_encode + t_request, 2)
        return result

    except requests.Timeout:
        logger.error(f"LLM request timeout for {fname}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response for {fname}: {e}")
        return None
    except RuntimeError:
        return None
    except Exception as e:
        logger.error(f"LLM request error for {fname}: {e}")
        return None


def analyze_batch_with_llm(image_paths):
    """Send up to 5 images to LLM for batch quality analysis.

    Args:
        image_paths: List of image file paths (max BATCH_SIZE).

    Returns:
        list[dict|None]: Results list with same length as input. Each element is the
                         parsed LLM result dict, or None if encoding failed / missing.
    """
    t0 = time.time()

    # Encode all images, track which succeeded
    encoded = []
    valid_indices = []
    for i, path in enumerate(image_paths):
        b64 = encode_image_base64(path)
        if b64:
            encoded.append(b64)
            valid_indices.append(i)
        else:
            logger.error(f"Failed to encode {path}, will skip")

    if not encoded:
        logger.error("All images failed to encode in batch")
        return [None] * len(image_paths)

    filenames = [os.path.basename(image_paths[i]) for i in valid_indices]
    filename_list = '\n'.join(f'{i + 1}. {fn}' for i, fn in enumerate(filenames))

    user_content = [
        {
            'type': 'text',
            'text': f'请按以下顺序分析 {len(filenames)} 张图片，返回与图片顺序对应的 JSON 数组：\n{filename_list}',
        }
    ]
    for b64 in encoded:
        user_content.append({
            'type': 'image_url',
            'image_url': {'url': f'data:image/jpeg;base64,{b64}'},
        })

    payload = {
        'model': QWEN_MODEL,
        'messages': [
            {
                'role': 'system',
                'content': BATCH_PROMPT_TEMPLATE,
                'cache_control': {'type': 'ephemeral'},
            },
            {
                'role': 'user',
                'content': user_content,
            },
        ],
        'max_tokens': 3000,
        'temperature': 0.8,
        'top_p': 0.9,
        'enable_thinking': False,
    }

    try:
        logger.info(f"Sending batch of {len(encoded)} images to LLM: {filenames}")
        t1 = time.time()
        data = _post_to_llm(payload)
        t_request = time.time() - t1
        t_encode = t1 - t0
        logger.info(f"LLM batch response: total={t_encode + t_request:.1f}s")

        token_usage = _log_token_usage(data, " (batch)")

        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        if not content:
            logger.error("Empty LLM batch response")
            return [None] * len(image_paths)

        results_list = _parse_llm_json(content)
        if not isinstance(results_list, list):
            logger.error(f"Expected JSON array but got {type(results_list).__name__}")
            return [None] * len(image_paths)

        elapsed = round(t_encode + t_request, 2)

        # Build result list mapped back to original input indices
        results = [None] * len(image_paths)
        for i, item in enumerate(results_list):
            if not isinstance(item, dict):
                logger.warning(f"Batch result [{i}] is not a dict, skipping")
                continue
            if i < len(valid_indices):
                orig_idx = valid_indices[i]
                item['_token_usage'] = token_usage
                item['_elapsed_seconds'] = elapsed
                results[orig_idx] = item
                logger.info(f"  [{i}] {filenames[i]}: is_bad={item.get('is_bad_photo')}, "
                             f"reasons={item.get('reasons')}")

        missing = sum(1 for r in results if r is None) - (len(image_paths) - len(encoded))
        if missing > 0:
            logger.warning(f"LLM returned {len(results_list)} results for {len(encoded)} encoded images, "
                           f"{missing} results missing")

        return results

    except requests.Timeout:
        logger.error(f"LLM batch request timeout for {filenames}")
        return [None] * len(image_paths)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM batch JSON response: {e}")
        return [None] * len(image_paths)
    except RuntimeError:
        return [None] * len(image_paths)
    except Exception as e:
        logger.error(f"LLM batch request error: {e}")
        return [None] * len(image_paths)

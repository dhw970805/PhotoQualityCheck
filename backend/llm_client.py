import base64
import json
import logging
import os
import time
import requests

from config import QWEN_API_KEY, QWEN_API_URL, QWEN_MODEL, QWEN_TIMEOUT

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """你是一位拥有20年经验的资深婚庆摄影修图师和选片专家。

## 目标
快速从大量婚礼照片中筛选出"废片"。摄影师拍摄约3000张，你需要剔除严重质量问题照片。请采用"商业交付级"标准，降低宽容度。

## 判定标准
满足任意一条即视为"坏照片"：

1. **表情不自然**：
   - 嘴巴微张/歪斜（说话中）、眼神空洞/失焦、面部肌肉用力过度（假笑酝酿）、抿嘴过紧。
   - 自检：如果新人看到这个表情会觉得尴尬，则判为坏照片。

2. **主要人物闭眼**：
   - 主要人物双眼闭合，面部松弛。
   - **例外**：如果是开怀大笑导致的闭眼（眼角有笑纹，嘴角上扬），则是好照片。

3. **构图不好**：
   - 主要人物被遮挡（脸部被挡）、切头切脚、画面严重倾斜、背景杂乱干扰主体。

4. **曝光问题**：
   - 欠曝：人物面部暗沉发黑，强行提亮会噪点爆炸。
   - 过曝：高光溢出（如婚纱死白），面部无细节，肤色惨白。

## 输出要求
输出必须是纯JSON，不要包含任何Markdown代码块标记（如```json）。
只关注主要人物（新郎/新娘），忽略背景路人。
如果图片模糊无法判断，输出status为"需复核"，防止误删珍贵瞬间。

quality枚举值：闭眼、表情差、构图差、欠曝、过曝、合格

请严格按以下JSON格式输出：
{
  "is_bad_photo": true或false,
  "expressionScore": 0到100的整数,
  "compositionScore": 0到100的整数,
  "exposureScore": 0到100的整数,
  "reasons": ["原因标签，必须使用quality枚举值"],
  "detailed_analysis": "详细分析说明"
}"""


def encode_image_base64(image_path):
    """Encode an image file to base64."""
    try:
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to encode image {image_path}: {e}")
        return None


def analyze_with_llm(image_path):
    """Send image to Qwen-3.5Plus for quality analysis.

    Returns:
        dict or None: Parsed LLM response, or None on failure.
    """
    image_b64 = encode_image_base64(image_path)
    if not image_b64:
        return None

    # Detect image MIME type
    ext = os.path.splitext(image_path)[1].lower()
    mime_map = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.bmp': 'image/bmp',
        '.webp': 'image/webp',
        '.tiff': 'image/tiff',
        '.tif': 'image/tiff',
    }
    mime_type = mime_map.get(ext, 'image/jpeg')

    payload = {
        'model': QWEN_MODEL,
        'messages': [
            {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': PROMPT_TEMPLATE},
                    {'type': 'image_url', 'image_url': {'url': f'data:{mime_type};base64,{image_b64}'}},
                ],
            }
        ],
        'max_tokens': 500,
        'temperature': 0.3,
    }

    headers = {
        'Authorization': f'Bearer {QWEN_API_KEY}',
        'Content-Type': 'application/json',
    }

    start_time = time.time()
    token_usage = None

    try:
        logger.info(f"Sending image to LLM: {os.path.basename(image_path)}")
        response = requests.post(
            QWEN_API_URL,
            json=payload,
            headers=headers,
            timeout=QWEN_TIMEOUT,
        )

        elapsed = time.time() - start_time
        logger.info(f"LLM response for {os.path.basename(image_path)}: {response.status_code}, {elapsed:.1f}s")

        if response.status_code != 200:
            logger.error(f"LLM API error {response.status_code}: {response.text[:200]}")
            return None

        data = response.json()

        # Log token usage
        if 'usage' in data:
            token_usage = data['usage']
            logger.info(f"Token usage: prompt={token_usage.get('prompt_tokens')}, "
                       f"completion={token_usage.get('completion_tokens')}, "
                       f"total={token_usage.get('total_tokens')}")

        # Extract content
        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        if not content:
            logger.error(f"Empty LLM response for {os.path.basename(image_path)}")
            return None

        # Parse JSON from response (handle possible markdown wrapping)
        content = content.strip()
        if content.startswith('```'):
            # Remove markdown code block markers
            lines = content.split('\n')
            lines = [l for l in lines if not l.strip().startswith('```')]
            content = '\n'.join(lines).strip()

        result = json.loads(content)

        # Add token usage info
        result['_token_usage'] = token_usage
        result['_elapsed_seconds'] = round(elapsed, 2)

        return result

    except requests.Timeout:
        elapsed = time.time() - start_time
        logger.error(f"LLM request timeout ({elapsed:.1f}s) for {os.path.basename(image_path)}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response for {os.path.basename(image_path)}: {e}")
        logger.debug(f"Raw response: {content[:500] if 'content' in dir() else 'N/A'}")
        return None
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"LLM request error for {os.path.basename(image_path)} ({elapsed:.1f}s): {e}")
        return None

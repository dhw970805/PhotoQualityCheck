import base64
import io
import json
import logging
import os
import time
import requests
from PIL import Image, ImageOps

from config import QWEN_API_KEY, QWEN_API_URL, QWEN_MODEL, QWEN_TIMEOUT, LLM_IMAGE_MAX_WIDTH

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """Role 你是一名拥有 20 年经验的资深婚庆摄影修图师和选片专家。你的任务是快速、准确地从大量婚礼现场照片中筛选出“废片”（不合格照片）。摄影师每次拍摄约 3000 张，你需要帮他剔除有严重质量问题的照片，保留可用照片。 请摒弃“能看见就行”的大众标准，降低你的宽容度，采用“商业交付级”的专业标准,。请务必严格按照以下标准进行判定，确保筛选结果准确可靠。

Goal 分析输入的图片，判断其是否属于“坏照片”。如果是坏照片，必须明确指出原因；如果是好照片（或仅有轻微瑕疵但不影响使用），则标记为合格。

Critical Definitions (坏照片判定标准) 请严格基于以下 4 个维度进行判定，只要满足任意一条，即视为“坏照片”：

表情不自然 (Unnatural Expression) - [严格抓拍标准] 请摒弃“只要不丑就是自然”的宽松标准，采用“商业修图级”的严苛眼光： 判定为【表情不自然】 (Bad Photo) 的关键特征：

过渡态/中途态 (Mid-Action)： 嘴巴微张、歪斜，明显是在说话或咀嚼过程中被抓拍。 眼神正在移动，未聚焦，显得空洞或迷茫。 面部肌肉处于用力的过渡阶段（如假笑前的酝酿，或大笑后的回落），导致五官不对称。 眼神失焦 (Dead Eyes)： 眼神没有落在伴侣、宾客或特定物体上，而是看向虚无，缺乏情感交流感。 翻白眼或眼神涣散。 尴尬的微表情： 抿嘴过紧（显得紧张）、嘴角单侧上扬（显得轻蔑或怪异）、下巴过度前伸或后缩。 判定为【自然】 (Good Photo) 的特征：

情绪饱满且稳定（无论是大笑、感动流泪还是庄重严肃）。 眼神有明确的落点（Looking at something/someone with intent）。 面部肌肉放松或处于完美的微笑定格。 -> 自检问题： "如果这张照片被放大打印出来挂在婚礼现场，新人看到这个表情会觉得尴尬吗？" 如果会，请坚决判为 Bad。

主要人物闭眼 (Blinking) - [关键逻辑]

判定为坏照片：主要人物（新郎、新娘或核心家庭成员）双眼闭合，且面部肌肉松弛，呈现非自愿的眨眼状态。 例外情况（不算坏照片）：如果主要人物正在开怀大笑，这属于自然的情感流露，绝对不能判定为坏照片。 判断技巧：观察眼角是否有笑纹，嘴角是否上扬。如果有笑意，即使闭眼也是好照片。重要：如果拍摄场景和氛围表明此时不该闭眼，则是坏照片 构图不好 (Poor Composition)

包括：主要人物被严重遮挡（如被路人、物体挡住脸部）,脸部未完全展现在画面中、主要人物被切头切脚、画面严重倾斜导致视觉不适、背景杂乱干扰主体。 排除：正常的特写裁剪或具有艺术感的留白不算坏照片。 曝光问题 (Exposure Issues) 请摒弃“能看见就行”的大众标准，采用“商业交付级”的专业标准：

判定为【严重欠曝】 (Bad Photo) 的情况：

现场光不足：环境昏暗，导致人物面部光线不足，肤色暗沉、发灰、发黑。 后期修复困难：虽然隐约可见五官，但若强行提亮，会导致画面噪点爆炸或色彩失真。 主体不突出：人物与黑暗背景混为一体，缺乏层次感。 特例：只有当黑暗是刻意的艺术创作（如完美剪影）且轮廓极佳时，才可豁免。但在婚礼纪实中，99% 的昏暗都是失误。 判定为【严重过曝】 (Bad Photo) 的情况：

高光溢出：新娘婚纱的白色纹理消失变成死白，或人物面部高光处无任何细节。 惨白无力：肤色因过曝显得苍白无血色。 Output Format 你必须严格遵守以下 JSON 格式输出，不要包含任何 Markdown 标记（如 ```json),不要输出任何额外的解释性文字。

{ "is_bad_photo": boolean, // true 表示是坏照片需剔除,false 表示是好照片可保留 "expressionScore": integer, // 0-100 分，坏照片通常低于 60 分 "compositionScore": integer, // 0-100 分，坏照片通常低于 60 分 "exposureScore": integer, // 0-100 分，坏照片通常低于 60 分 "reasons": [ // 数组，列出所有触发的坏照片原因代码，若无则为空数组 "unnatural_expression", "blinking", // 仅当微笑且闭眼且不合格时填写此项 "poor_composition", "over_exposure", "under_exposure" ], "detailed_analysis": "string" // 用一句话简短描述具体问题，例如："新娘在严肃时刻意外眨眼" 或 "笑容灿烂虽闭眼但情感自然，保留" }

Workflow 首先观察主要人物的面部表情，重点区分“意外闭眼”和“欢笑闭眼”。 检查构图是否完整，主体是否被遮挡。 检查直方图视觉效果，判断是否存在严重过曝或欠曝。 Constraints 婚礼的情感瞬间比完美技术更重要。 只关注主要人物（新郎/新娘/父母/亲属），背景路人的表情忽略不计。 输出必须是纯文本 JSON，不能包含任何 Markdown 代码块标记或额外说明。 请严格按照上述标准进行判定，确保筛选结果准确可靠。"""


def encode_image_base64(image_path):
    """Encode an image file to base64, resizing if necessary to stay under API limits."""
    try:
        with Image.open(image_path) as img:
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass

            w, h = img.size
            if w > LLM_IMAGE_MAX_WIDTH:
                ratio = LLM_IMAGE_MAX_WIDTH / w
                new_h = int(h * ratio)
                img = img.resize((LLM_IMAGE_MAX_WIDTH, new_h), Image.LANCZOS)

            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=85)
            return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to encode image {image_path}: {e}")
        return None


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
    payload_size_mb = len(image_b64) * 3 / 4 / 1024 / 1024  # base64 ~1.33x raw

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
        'enable_thinking': False,
    }

    headers = {
        'Authorization': f'Bearer {QWEN_API_KEY}',
        'Content-Type': 'application/json',
    }

    t1 = time.time()
    token_usage = None

    try:
        logger.info(f"Sending image to LLM: {os.path.basename(image_path)} "
                    f"(encode={t_encode:.2f}s, payload={payload_size_mb:.1f}MB)")
        response = requests.post(
            QWEN_API_URL,
            json=payload,
            headers=headers,
            timeout=QWEN_TIMEOUT,
        )

        t_request = time.time() - t1
        logger.info(f"LLM response for {os.path.basename(image_path)}: "
                    f"{response.status_code}, total={t_encode + t_request:.1f}s "
                    f"(encode={t_encode:.2f}s, api={t_request:.1f}s)")

        if response.status_code != 200:
            logger.error(f"LLM API error {response.status_code}: {response.text[:200]}")
            return None

        data = response.json()

        # Log full API response for debugging
        logger.info(f"Full API response: {json.dumps(data, ensure_ascii=False)[:1000]}")

        # Log token usage
        if 'usage' in data:
            token_usage = data['usage']
            logger.info(f"Token usage: prompt={token_usage.get('prompt_tokens')}, "
                       f"cached={token_usage.get('prompt_tokens_details', {}).get('cached_tokens', 0)}, "
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
        result['_elapsed_seconds'] = round(t_encode + t_request, 2)

        return result

    except requests.Timeout:
        logger.error(f"LLM request timeout for {os.path.basename(image_path)}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response for {os.path.basename(image_path)}: {e}")
        logger.debug(f"Raw response: {content[:500] if 'content' in dir() else 'N/A'}")
        return None
    except Exception as e:
        logger.error(f"LLM request error for {os.path.basename(image_path)}: {e}")
        return None

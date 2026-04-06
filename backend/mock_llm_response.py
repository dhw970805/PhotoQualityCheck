"""模拟大模型响应，随机生成检测结果，无需调用真实API。"""

import random
import logging
import time

logger = logging.getLogger(__name__)

# 合格照片的分析模板
GOOD_ANALYSIS_TEMPLATES = [
    "新人表情自然大方，构图合理，光线充足，整体画面效果优秀。",
    "新郎新娘互动自然，画面构图均衡，曝光准确，色彩还原良好。",
    "人物姿态优美，面部表情生动自然，背景虚化适度，整体氛围感强。",
    "光影运用得当，人物肤色还原真实，构图饱满，是一张合格的照片。",
    "双人站位合理，表情轻松自然，画面层次分明，色彩和谐。",
]

# 废片分析模板（按质量问题分类）
BAD_ANALYSIS_TEMPLATES = {
    '闭眼': [
        "主要人物双眼闭合，面部表情松弛，疑似抓拍时机不对。",
        "新郎/新娘在拍摄瞬间闭眼，眼睛完全闭合，面部无笑意。",
        "人物眨眼未睁开，面部表情呆滞，需要重新拍摄。",
    ],
    '表情差': [
        "人物嘴巴微张，疑似说话中被抓拍，表情不够自然。",
        "面部肌肉僵硬，笑容不自然，眼神略显空洞，缺乏互动感。",
        "抿嘴过紧，表情严肃，缺乏婚礼应有的愉悦氛围。",
        "人物表情尴尬，眼神偏移镜头，面部略显紧张。",
    ],
    '构图差': [
        "主要人物被前景遮挡，面部细节不完整。",
        "画面边缘切头/切脚，构图不完整，需要裁切处理。",
        "画面明显倾斜，水平线不正，影响观感。",
        "背景杂乱，有路人入镜，干扰画面主体表达。",
    ],
    '欠曝': [
        "人物面部暗沉，整体画面偏暗，提亮后噪点明显。",
        "光线不足导致面部细节丢失，背景与人物亮度差异过大。",
        "曝光补偿不足，人物肤色发灰，暗部细节几乎不可见。",
    ],
    '过曝': [
        "高光区域溢出，婚纱细节丢失，面部肤色过亮。",
        "过曝严重，人物面部细节模糊，整体画面苍白无力。",
        "逆光拍摄未补光，高光部分完全死白，无法通过后期恢复。",
    ],
}

# 分数范围配置
SCORE_RANGES = {
    '合格': {'expression': (70, 95), 'composition': (70, 95), 'exposure': (70, 95)},
    '闭眼': {'expression': (20, 50), 'composition': (60, 85), 'exposure': (60, 85)},
    '表情差': {'expression': (15, 45), 'composition': (55, 80), 'exposure': (55, 80)},
    '构图差': {'expression': (50, 75), 'composition': (15, 40), 'exposure': (50, 75)},
    '欠曝': {'expression': (40, 65), 'composition': (50, 75), 'exposure': (10, 35)},
    '过曝': {'expression': (40, 65), 'composition': (50, 75), 'exposure': (10, 30)},
}

VALID_QUALITIES = ['闭眼', '表情差', '构图差', '欠曝', '过曝']


def _rand_score(low, high):
    return random.randint(low, high)


def _rand_analysis(reasons):
    """根据质量问题随机组合分析文本。"""
    parts = []
    for reason in reasons:
        templates = BAD_ANALYSIS_TEMPLATES.get(reason, [])
        if templates:
            parts.append(random.choice(templates))
    if parts:
        return '；'.join(parts)
    return "存在质量问题，建议人工复核。"


def mock_analyze(image_path):
    """模拟大模型分析，返回与 llm_client.analyze_with_llm 相同格式的结果。

    Returns:
        dict: 与真实 LLM 返回格式一致的结果。
    """
    import os
    filename = os.path.basename(image_path)

    # 模拟网络延迟 (0.3~1.5秒)
    delay = random.uniform(0.3, 1.5)
    time.sleep(delay)

    # 随机决定是否为废片 (约35%概率为废片)
    is_bad = random.random() < 0.35

    if is_bad:
        # 随机选1~2个质量问题
        num_issues = random.choices([1, 2], weights=[0.7, 0.3])[0]
        reasons = random.sample(VALID_QUALITIES, num_issues)
    else:
        reasons = []

    # 生成分数
    if is_bad:
        # 取所有问题的最低分范围
        score_key = reasons[0]
        ranges = SCORE_RANGES.get(score_key, SCORE_RANGES['合格'])
        expression_score = _rand_score(*ranges['expression'])
        composition_score = _rand_score(*ranges['composition'])
        exposure_score = _rand_score(*ranges['exposure'])

        # 如果有第二个问题，取更低的范围
        if len(reasons) > 1:
            ranges2 = SCORE_RANGES.get(reasons[1], SCORE_RANGES['合格'])
            expression_score = min(expression_score, _rand_score(*ranges2['expression']))
            composition_score = min(composition_score, _rand_score(*ranges2['composition']))
            exposure_score = min(exposure_score, _rand_score(*ranges2['exposure']))
    else:
        ranges = SCORE_RANGES['合格']
        expression_score = _rand_score(*ranges['expression'])
        composition_score = _rand_score(*ranges['composition'])
        exposure_score = _rand_score(*ranges['exposure'])

    # 生成分析文本
    if is_bad:
        detailed_analysis = _rand_analysis(reasons)
    else:
        detailed_analysis = random.choice(GOOD_ANALYSIS_TEMPLATES)

    result = {
        'is_bad_photo': is_bad,
        'expressionScore': expression_score,
        'compositionScore': composition_score,
        'exposureScore': exposure_score,
        'reasons': reasons,
        'detailed_analysis': detailed_analysis,
        '_token_usage': {
            'prompt_tokens': random.randint(800, 1200),
            'completion_tokens': random.randint(80, 200),
            'total_tokens': random.randint(900, 1400),
        },
        '_elapsed_seconds': round(delay, 2),
    }

    logger.info(f"[Mock LLM] {filename}: is_bad={is_bad}, reasons={reasons}, scores=({expression_score},{composition_score},{exposure_score})")
    return result


def mock_analyze_batch(image_paths):
    """模拟批量大模型分析，对多张图片进行模拟分析。

    Args:
        image_paths: 图片路径列表。

    Returns:
        list[dict|None]: 与输入列表等长的结果列表，失败项为 None。
    """
    import os
    filenames = [os.path.basename(p) for p in image_paths]

    # 模拟单次批量网络延迟
    delay = random.uniform(0.5, 2.0)
    time.sleep(delay)

    results = []
    for i, image_path in enumerate(image_paths):
        result = mock_analyze(image_path)
        results.append(result)
        logger.info(f"[Mock LLM Batch] [{i}] {filenames[i]}: is_bad={result['is_bad_photo']}")

    logger.info(f"[Mock LLM Batch] Processed {len(results)}/{len(image_paths)} images in {delay:.2f}s")
    return results

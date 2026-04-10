REASON_TAG_MAP = {
    'unnatural_expression': '表情差',
    'blinking': '闭眼',
    'poor_composition': '构图差',
    'over_exposure': '过曝',
    'under_exposure': '欠曝',
}


def map_llm_result_to_updates(llm_result):
    """Convert raw LLM response to photo metadata updates.

    Returns:
        dict with keys: status, quality, scores, advise, reason
    """
    is_bad = llm_result.get('is_bad_photo', False)
    reasons = [REASON_TAG_MAP[r] for r in llm_result.get('reasons', []) if r in REASON_TAG_MAP]

    if is_bad:
        status = '需复核'
        quality = reasons if reasons else ['需复核']
    else:
        status = '合格'
        quality = ['合格']

    return {
        'status': status,
        'quality': quality,
        'scores': {
            'expression': llm_result.get('expressionScore', 0),
            'composition': llm_result.get('compositionScore', 0),
            'exposure': llm_result.get('exposureScore', 0),
        },
        'advise': llm_result.get('detailed_analysis', ''),
        'reason': '; '.join(reasons) if reasons else '',
    }

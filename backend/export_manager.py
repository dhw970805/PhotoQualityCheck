import logging
import os
import shutil

logger = logging.getLogger(__name__)


def export_photos(folder_path):
    """Export photos to subfolders based on their status.

    Creates:
      - 合格/ - photos marked as 合格
      - 需复核/ - photos marked as 需复核
      - 未检测/ - photos that haven't been checked

    Returns:
        dict with 'success', 'summary', and optionally 'error'.
    """
    from result_manager import load_result_json

    result = load_result_json(folder_path)
    if not result.get('photos'):
        return {'success': True, 'summary': {'合格': 0, '需复核': 0, '未检测': 0}}

    summary = {'合格': 0, '需复核': 0, '未检测': 0}
    errors = []

    for photo in result['photos']:
        meta = photo['photo_metadata']
        file_info = meta['file_info']
        file_name = file_info['file_name']
        file_path = file_info['file_path']
        status = meta.get('status', '未检测')

        # Determine target subfolder
        if status == '合格':
            target_dir = '合格'
        elif status == '需复核':
            target_dir = '需复核'
        else:
            target_dir = '未检测'

        target_path = os.path.join(folder_path, target_dir, file_name)

        # Skip if source doesn't exist
        if not os.path.exists(file_path):
            logger.warning(f"Source file not found: {file_path}")
            errors.append(f"文件不存在: {file_name}")
            continue

        # Create target directory
        os.makedirs(os.path.join(folder_path, target_dir), exist_ok=True)

        # Copy file (not move, to preserve originals)
        try:
            shutil.copy2(file_path, target_path)
            summary[target_dir] = summary.get(target_dir, 0) + 1
        except Exception as e:
            logger.error(f"Failed to copy {file_name}: {e}")
            errors.append(f"复制失败: {file_name} - {str(e)}")

    logger.info(f"Export complete. Summary: {summary}")
    if errors:
        return {'success': True, 'summary': summary, 'errors': errors}
    return {'success': True, 'summary': summary}

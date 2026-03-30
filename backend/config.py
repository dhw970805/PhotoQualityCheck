import os

# Flask settings
FLASK_PORT = int(os.environ.get('FLASK_PORT', 5000))
FLASK_HOST = '127.0.0.1'
DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

# LLM settings
USE_MOCK_LLM = os.environ.get('USE_MOCK_LLM', 'true').lower() == 'true'

# Qwen API settings (DashScope)
QWEN_API_KEY = os.environ.get('QWEN_API_KEY', 'your-api-key-here')
QWEN_API_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'
QWEN_MODEL = 'qwen-vl-max-latest'
QWEN_TIMEOUT = 30  # seconds

# MediaPipe settings
MEDIAPIPE_MODEL_COMPLEXITY = 1
MEDIAPIPE_MIN_DETECTION_CONFIDENCE = 0.5
MEDIAPIPE_MIN_TRACKING_CONFIDENCE = 0.5

# Eye Aspect Ratio threshold for closed eyes
EAR_THRESHOLD = 0.2

# Thumbnail settings
THUMBNAIL_WIDTH = 400
THUMBNAIL_SUBDIR = '.thumbnails'

# Supported image extensions
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}

# Logging
LOG_FILE = 'photo_quality_check.log'
LOG_FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'

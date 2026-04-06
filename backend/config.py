import os

# Flask settings
FLASK_PORT = int(os.environ.get('FLASK_PORT', 5000))
FLASK_HOST = '127.0.0.1'
DEBUG = True

# LLM settings
USE_MOCK_LLM = False

# Qwen API settings (DashScope)
QWEN_API_KEY = 'sk-c516597c460f49cd9015ec616b753eee'
QWEN_API_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'
QWEN_MODEL = 'qwen3.5-plus'
QWEN_TIMEOUT = 120  # seconds

# MediaPipe settings
MEDIAPIPE_MODEL_COMPLEXITY = 1
MEDIAPIPE_MIN_DETECTION_CONFIDENCE = 0.5
MEDIAPIPE_MIN_TRACKING_CONFIDENCE = 0.5

# Eye Aspect Ratio threshold for closed eyes
EAR_THRESHOLD = 0.2

# LLM image settings
LLM_IMAGE_MAX_WIDTH = 512  # Max image width sent to LLM API (base64 data-uri has 10MB limit)
BATCH_SIZE = 5  # Number of images to send to LLM in one batch
MAX_CONCURRENCY = 5  # Max concurrent API requests (threads)

# Thumbnail settings
THUMBNAIL_WIDTH = 400
THUMBNAIL_SUBDIR = '.thumbnails'

# Supported image extensions
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}

# Logging
LOG_FILE = 'photo_quality_check.log'
LOG_FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'

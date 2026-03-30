import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Lazy-loaded MediaPipe model
_face_mesh = None


def get_face_mesh():
    global _face_mesh
    if _face_mesh is None:
        import mediapipe as mp
        mp_face_mesh = mp.solutions.face_mesh
        _face_mesh = mp_face_mesh.FaceMesh(
            max_num_faces=3,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        logger.info("MediaPipe FaceMesh model loaded")
    return _face_mesh


def compute_ear(landmarks, eye_indices):
    """Compute Eye Aspect Ratio from facial landmarks."""
    # Vertical distances
    v1 = np.linalg.norm(np.array(landmarks[eye_indices[1]]) - np.array(landmarks[eye_indices[5]]))
    v2 = np.linalg.norm(np.array(landmarks[eye_indices[2]]) - np.array(landmarks[eye_indices[4]]))
    # Horizontal distance
    h = np.linalg.norm(np.array(landmarks[eye_indices[0]]) - np.array(landmarks[eye_indices[3]]))
    if h == 0:
        return 0
    return (v1 + v2) / (2.0 * h)


# Left eye landmark indices
LEFT_EYE = [33, 160, 158, 133, 153, 144]
# Right eye landmark indices
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
# Mouth landmark indices (for smile detection)
MOUTH_OUTER = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185]


def analyze_image(image_path):
    """Analyze an image using MediaPipe face detection.

    Returns:
        dict: {
            'face_found': bool,
            'eyes_closed': bool,
            'ear_left': float,
            'ear_right': float,
            'smile_detected': bool,
            'face_count': int,
        }
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            logger.warning(f"Cannot read image: {image_path}")
            return _no_face_result()

        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w = img.shape[:2]

        face_mesh = get_face_mesh()
        results = face_mesh.process(img_rgb)

        if not results.multi_face_landmarks or len(results.multi_face_landmarks) == 0:
            logger.info(f"No face detected in: {image_path}")
            return _no_face_result()

        face_count = len(results.multi_face_landmarks)
        # Use the first (largest/main) face
        landmarks = results.multi_face_landmarks[0]

        # Convert normalized landmarks to pixel coords
        lm_points = []
        for lm in landmarks.landmark:
            lm_points.append([lm.x * w, lm.y * h])

        # Compute Eye Aspect Ratio
        ear_left = compute_ear(lm_points, LEFT_EYE)
        ear_right = compute_ear(lm_points, RIGHT_EYE)
        avg_ear = (ear_left + ear_right) / 2.0

        # Simple smile detection: mouth width vs height
        mouth_width = np.linalg.norm(np.array(lm_points[61]) - np.array(lm_points[291]))
        mouth_height = np.linalg.norm(np.array(lm_points[13]) - np.array(lm_points[14]))
        smile_ratio = mouth_width / mouth_height if mouth_height > 0 else 0
        smile_detected = smile_ratio > 4.5  # Threshold for smiling

        eyes_closed = avg_ear < 0.2

        return {
            'face_found': True,
            'eyes_closed': eyes_closed,
            'ear_left': round(ear_left, 4),
            'ear_right': round(ear_right, 4),
            'avg_ear': round(avg_ear, 4),
            'smile_detected': smile_detected,
            'face_count': face_count,
        }

    except Exception as e:
        logger.error(f"MediaPipe analysis error for {image_path}: {e}")
        return _no_face_result(error=str(e))


def _no_face_result(error=None):
    return {
        'face_found': False,
        'eyes_closed': False,
        'ear_left': 0,
        'ear_right': 0,
        'avg_ear': 0,
        'smile_detected': False,
        'face_count': 0,
        'error': error,
    }

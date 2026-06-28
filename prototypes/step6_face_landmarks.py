import cv2
import mediapipe as mp
import numpy as np
from PIL import Image
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

INPUT_IMAGE  = "./outputs_part2/nana_osaki_stage.png"
OUTPUT_IMAGE = "./outputs_part2/landmarks_preview.png"

MODEL_PATH = "/tmp/face_landmarker.task"

def _ensure_model():
    import urllib.request, os
    if not os.path.exists(MODEL_PATH):
        print("Downloading face landmarker model (~30MB)...")
        urllib.request.urlretrieve(
            "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task",
            MODEL_PATH,
        )
        print("Downloaded.")


def detect_landmarks(image_path: str) -> tuple:
    _ensure_model()

    img_pil = Image.open(image_path).convert("RGB")
    img_np  = np.array(img_pil)
    h, w    = img_np.shape[:2]

    options = vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
        num_faces=1,
        min_face_detection_confidence=0.3,
    )

    with vision.FaceLandmarker.create_from_options(options) as landmarker:
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_np)
        result   = landmarker.detect(mp_image)

    if not result.face_landmarks:
        return None, img_np, w, h

    class LandmarkList:
        def __init__(self, lms): self.landmark = lms

    return LandmarkList(result.face_landmarks[0]), img_np, w, h


def draw_landmarks(image_path: str, output_path: str):
    landmarks, img_np, w, h = detect_landmarks(image_path)

    if landmarks is None:
        print("No face detected.")
        return False

    print(f"Face detected. Total landmarks: {len(landmarks.landmark)}")

    # draw all landmarks
    overlay = img_np.copy()
    for lm in landmarks.landmark:
        x, y = int(lm.x * w), int(lm.y * h)
        cv2.circle(overlay, (x, y), 1, (0, 255, 0), -1)

    # highlight key regions with different colors
    key_points = {
        # left eye
        "left_eye":   [33, 7, 163, 144, 145, 153, 154, 155, 133],
        # right eye
        "right_eye":  [362, 382, 381, 380, 374, 373, 390, 249, 263],
        # mouth outer
        "mouth":      [61, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185],
        # eyebrows
        "left_brow":  [70, 63, 105, 66, 107],
        "right_brow": [336, 296, 334, 293, 300],
        # nose tip
        "nose":       [1, 2, 98, 327],
    }

    colors = {
        "left_eye":   (255, 100, 100),
        "right_eye":  (255, 100, 100),
        "mouth":      (100, 100, 255),
        "left_brow":  (255, 255, 0),
        "right_brow": (255, 255, 0),
        "nose":       (0, 255, 255),
    }

    for region, indices in key_points.items():
        for idx in indices:
            lm = landmarks.landmark[idx]
            x, y = int(lm.x * w), int(lm.y * h)
            cv2.circle(overlay, (x, y), 4, colors[region], -1)

    # print some key coordinates
    print("\nKey landmark positions (normalized 0-1):")
    named = {
        "nose tip":        landmarks.landmark[1],
        "left eye center": landmarks.landmark[33],
        "right eye center":landmarks.landmark[263],
        "mouth left":      landmarks.landmark[61],
        "mouth right":     landmarks.landmark[291],
        "mouth top":       landmarks.landmark[0],
        "mouth bottom":    landmarks.landmark[17],
    }
    for name, lm in named.items():
        print(f"  {name:20s}: ({lm.x:.3f}, {lm.y:.3f})")

    # estimate face region bounding box
    xs = [int(lm.x * w) for lm in landmarks.landmark]
    ys = [int(lm.y * h) for lm in landmarks.landmark]
    x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (200, 200, 200), 1)
    print(f"\nFace bounding box: ({x1},{y1}) → ({x2},{y2})")
    print(f"Face size: {x2-x1}x{y2-y1}px out of {w}x{h}px image")

    result = Image.fromarray(overlay)
    result.save(output_path)
    print(f"\nSaved → {output_path}")
    return True


if __name__ == "__main__":
    print(f"Input: {INPUT_IMAGE}")
    print("=" * 60)
    draw_landmarks(INPUT_IMAGE, OUTPUT_IMAGE)

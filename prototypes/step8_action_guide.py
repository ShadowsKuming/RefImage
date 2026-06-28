import cv2
import numpy as np
import anthropic
import base64
import os
import io
import urllib.request
from PIL import Image, ImageDraw
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
import mediapipe as mp
from dotenv import load_dotenv

load_dotenv('.env')

INPUT_IMAGE    = "./outputs_part2/nana_osaki_stage.png"
OUTPUT_DIR     = "./outputs_part2/guide"
POSE_MODEL     = "/tmp/pose_landmarker_full.task"

# MediaPipe Pose 33-point skeleton connections
SKELETON = [
    (11, 12),  # shoulders
    (11, 13), (13, 15),  # left arm
    (12, 14), (14, 16),  # right arm
    (11, 23), (12, 24),  # torso sides
    (23, 24),            # hips
    (23, 25), (25, 27),  # left leg
    (24, 26), (26, 28),  # right leg
    (0, 11), (0, 12),    # neck to shoulders
]

JOINT_COLORS = {
    "head":        (255, 200, 100),
    "arms":        (100, 200, 255),
    "torso":       (150, 255, 150),
    "legs":        (255, 150, 200),
}


def ensure_model():
    if not os.path.exists(POSE_MODEL):
        print("Downloading pose landmarker model (~30MB)...")
        urllib.request.urlretrieve(
            "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task",
            POSE_MODEL,
        )
        print("Downloaded.")


def detect_pose(image_path: str):
    ensure_model()

    img_pil = Image.open(image_path).convert("RGB")
    img_np  = np.array(img_pil)
    h, w    = img_np.shape[:2]

    options = vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=POSE_MODEL),
        num_poses=1,
        min_pose_detection_confidence=0.1,
    )
    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        result = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=img_np))

    if not result.pose_landmarks:
        return None, img_np, w, h
    return result.pose_landmarks[0], img_np, w, h


def draw_skeleton_overlay(img_np, landmarks, w, h) -> np.ndarray:
    overlay = img_np.copy()

    pts = {i: (int(lm.x * w), int(lm.y * h)) for i, lm in enumerate(landmarks)}

    for a, b in SKELETON:
        if a in pts and b in pts:
            cv2.line(overlay, pts[a], pts[b], (255, 255, 255), 3)
            cv2.line(overlay, pts[a], pts[b], (50, 150, 255), 2)

    for i, (x, y) in pts.items():
        cv2.circle(overlay, (x, y), 6, (255, 255, 255), -1)
        cv2.circle(overlay, (x, y), 4, (0, 220, 255), -1)

    return overlay


def draw_clean_stick_figure(landmarks, w, h) -> np.ndarray:
    """Draw a clean white-background stick figure."""
    canvas = np.ones((h, w, 3), dtype=np.uint8) * 245  # off-white

    pts = {i: (int(lm.x * w), int(lm.y * h)) for i, lm in enumerate(landmarks)}

    # draw skeleton lines
    for a, b in SKELETON:
        if a in pts and b in pts:
            cv2.line(canvas, pts[a], pts[b], (60, 60, 60), 4)

    # draw joints
    for i, (x, y) in pts.items():
        cv2.circle(canvas, (x, y), 8, (60, 60, 60), -1)
        cv2.circle(canvas, (x, y), 6, (255, 100, 80), -1)

    # draw head circle around landmark 0 (nose)
    if 0 in pts:
        nose = pts[0]
        # estimate head size from shoulder distance
        if 11 in pts and 12 in pts:
            shoulder_w = abs(pts[11][0] - pts[12][0])
            head_r = max(int(shoulder_w * 0.35), 20)
        else:
            head_r = 30
        head_center = (nose[0], nose[1] - head_r // 2)
        cv2.circle(canvas, head_center, head_r, (60, 60, 60), 3)

    return canvas


def get_action_guide(overlay_img: np.ndarray, stick_img: np.ndarray) -> str:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    def to_b64(arr):
        buf = io.BytesIO()
        Image.fromarray(arr).save(buf, format="PNG")
        return base64.standard_b64encode(buf.getvalue()).decode()

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": to_b64(overlay_img)}},
                {"type": "text", "text": """You are a photography director helping recreate this exact pose in a real photoshoot.

Analyze the body pose and write a practical on-set guide.

## Pose Description
Describe the exact body position: weight distribution, spine angle, shoulder set, arm positions, leg positions, overall energy.

## How to Direct the Model
Write 5-6 specific verbal directions for achieving this pose.
Be concrete — reference specific body parts. Example: "Shift your weight onto your left hip, let your right knee bend slightly."

## Camera & Framing
- Recommended camera angle and height
- Suggested framing (full body / 3/4 / waist up)
- Distance from subject

## Key Details to Check
4 specific physical checkpoints the photographer should verify on set.

## Common Mistakes
2-3 things that would make the pose look wrong or stiff.

Keep it practical."""}
            ]
        }]
    )
    return response.content[0].text


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Input: {INPUT_IMAGE}")
    print("=" * 60)

    landmarks, img_np, w, h = detect_pose(INPUT_IMAGE)
    if landmarks is None:
        print("No pose detected.")
        exit(1)

    detected = sum(1 for lm in landmarks if lm.visibility > 0.3)
    print(f"Pose detected. Visible joints: {detected}/33")

    # skeleton overlay on original
    print("Drawing skeleton overlay...")
    overlay = draw_skeleton_overlay(img_np, landmarks, w, h)
    overlay_path = os.path.join(OUTPUT_DIR, "action_overlay.png")
    Image.fromarray(overlay).save(overlay_path)
    print(f"Overlay saved → {overlay_path}")

    # clean stick figure
    print("Drawing stick figure...")
    stick = draw_clean_stick_figure(landmarks, w, h)
    stick_path = os.path.join(OUTPUT_DIR, "action_stick.png")
    Image.fromarray(stick).save(stick_path)
    print(f"Stick figure saved → {stick_path}")

    # guide
    print("Generating photography guide...")
    guide = get_action_guide(overlay, stick)

    guide_path = os.path.join(OUTPUT_DIR, "action_guide.md")
    with open(guide_path, "w", encoding="utf-8") as f:
        f.write("# Action / Pose Guide\n\n")
        f.write(f"**Source image:** {INPUT_IMAGE}\n\n")
        f.write("---\n\n")
        f.write(guide)
    print(f"Guide saved → {guide_path}")

    print("\nDone. Check outputs_part2/guide/")
    print("  action_overlay.png — skeleton on original image")
    print("  action_stick.png   — clean stick figure")
    print("  action_guide.md    — photography directions")

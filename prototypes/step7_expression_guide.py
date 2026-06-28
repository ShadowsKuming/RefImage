import cv2
import numpy as np
import anthropic
import base64
import os
import io
from PIL import Image
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
import mediapipe as mp
from dotenv import load_dotenv

load_dotenv('.env')

INPUT_IMAGE  = "./outputs_part2/nana_osaki_stage.png"
OUTPUT_DIR   = "./outputs_part2/guide"
MODEL_PATH   = "/tmp/face_landmarker.task"


def detect_landmarks(image_path: str):
    img_pil = Image.open(image_path).convert("RGB")
    img_np  = np.array(img_pil)
    h, w    = img_np.shape[:2]

    options = vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
        num_faces=1,
        min_face_detection_confidence=0.3,
    )
    with vision.FaceLandmarker.create_from_options(options) as landmarker:
        result = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=img_np))

    if not result.face_landmarks:
        return None, img_np, w, h
    return result.face_landmarks[0], img_np, w, h


def crop_face(img_np, landmarks, w, h, padding: float = 0.3):
    xs = [int(lm.x * w) for lm in landmarks]
    ys = [int(lm.y * h) for lm in landmarks]
    x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)

    pw = int((x2 - x1) * padding)
    ph = int((y2 - y1) * padding)
    x1 = max(0, x1 - pw)
    y1 = max(0, y1 - ph)
    x2 = min(w, x2 + pw)
    y2 = min(h, y2 + ph)

    return img_np[y1:y2, x1:x2], (x1, y1, x2, y2)


def to_sketch(img_np: np.ndarray) -> np.ndarray:
    gray  = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    # invert + blur + divide = pencil sketch effect
    inv   = 255 - gray
    blur  = cv2.GaussianBlur(inv, (21, 21), 0)
    sketch = cv2.divide(gray, 255 - blur, scale=256.0)
    # sharpen edges
    kernel = np.array([[0,-1,0],[-1,5,-1],[0,-1,0]])
    sketch = cv2.filter2D(sketch, -1, kernel)
    return cv2.cvtColor(sketch, cv2.COLOR_GRAY2RGB)


def get_expression_guide(face_img_np: np.ndarray) -> str:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    buf = io.BytesIO()
    Image.fromarray(face_img_np).save(buf, format="PNG")
    img_b64 = base64.standard_b64encode(buf.getvalue()).decode()

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
                {"type": "text", "text": """You are a photography director helping a photographer recreate this exact expression in a real photoshoot.

Analyze the facial expression in this image and write a practical on-set guide.

## Expression Description
Describe exactly what the expression looks like (eyes, brows, mouth, jaw, cheeks).

## How to Direct the Model
Write 4-6 specific verbal directions a photographer would say to the model to achieve this expression.
Use natural language like you're actually on set. Example: "Look just above the camera lens, not at it."

## Key Details to Check
3-4 specific things the photographer should check/adjust to nail this expression.

## Common Mistakes to Avoid
2-3 things that would make the expression look wrong.

Keep it practical and specific. No generic advice."""}
            ]
        }]
    )
    return response.content[0].text


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Input: {INPUT_IMAGE}")
    print("=" * 60)

    landmarks, img_np, w, h = detect_landmarks(INPUT_IMAGE)
    if landmarks is None:
        print("No face detected.")
        exit(1)

    print("Face detected, cropping...")
    face_crop, bbox = crop_face(img_np, landmarks, w, h, padding=0.35)

    # save cropped face
    face_path = os.path.join(OUTPUT_DIR, "expression_crop.png")
    Image.fromarray(face_crop).save(face_path)
    print(f"Face crop saved → {face_path}")

    # generate sketch
    print("Generating sketch...")
    sketch = to_sketch(face_crop)
    sketch_path = os.path.join(OUTPUT_DIR, "expression_sketch.png")
    Image.fromarray(sketch).save(sketch_path)
    print(f"Sketch saved → {sketch_path}")

    # generate guide
    print("Generating photography guide...")
    guide_text = get_expression_guide(face_crop)

    # save guide as md
    guide_path = os.path.join(OUTPUT_DIR, "expression_guide.md")
    with open(guide_path, "w", encoding="utf-8") as f:
        f.write("# Expression Guide\n\n")
        f.write(f"**Source image:** {INPUT_IMAGE}\n\n")
        f.write("---\n\n")
        f.write(guide_text)
    print(f"Guide saved → {guide_path}")

    print("\nDone. Check outputs_part2/guide/")
    print("  expression_crop.png   — original face crop")
    print("  expression_sketch.png — line art sketch")
    print("  expression_guide.md   — photography directions")

import anthropic
import base64
import os
from dotenv import load_dotenv

load_dotenv('.env')

IMAGE_PATH     = "./Nana Osaki.jpg"
CHARACTER_NAME = "Nana Osaki"
SERIES_NAME    = "NANA"

def encode_image(path: str) -> tuple[str, str]:
    with open(path, "rb") as f:
        data = f.read()
    # detect actual format from magic bytes, ignore file extension
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        media_type = "image/webp"
    elif data[:8] == b"\x89PNG\r\n\x1a\n":
        media_type = "image/png"
    elif data[:3] == b"\xff\xd8\xff":
        media_type = "image/jpeg"
    else:
        media_type = "image/jpeg"
    return base64.standard_b64encode(data).decode("utf-8"), media_type

def extract_visual_traits(image_path: str, character_name: str, series_name: str) -> dict:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    image_data, media_type = encode_image(image_path)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data,
                    },
                },
                {
                    "type": "text",
                    "text": f"""This is a reference image of {character_name} from the anime/manga series "{series_name}".

Your task is NOT to describe this image. Your task is to extract a CHARACTER DESIGN SPECIFICATION — a precise spec sheet that would allow any artist or image generation model to reproduce this character accurately, even without seeing this image.

The image may be a figure, fan art, screenshot, or any angle/pose. Reason through the pose and perspective to infer the character's standard design proportions.

---

## 1. Proportions & Measurements (estimate from image, note confidence)
- Head-to-body ratio (e.g. 6-head, 7-head, 7.5-head body)
- Head shape: width-to-height ratio, face shape (oval/round/sharp/etc.)
- Shoulder width relative to head width (e.g. 1.5x head width)
- Waist width relative to shoulder width
- Leg length as proportion of total height (e.g. legs = 55% of height)
- For each estimate, note: [HIGH / MED / LOW confidence] and why

## 2. Face Design Spec
- Eye size relative to face (large/medium/small, specific to anime style)
- Eye spacing (close-set / normal / wide-set)
- Eye shape (almond / round / droopy / upturned — be precise)
- Nose style (small dot / button / defined bridge / etc.)
- Mouth size relative to face
- Distinctive facial features that MUST be preserved

## 3. Hair Design Spec
- Exact color (use specific descriptors: blue-black, ash brown, strawberry blonde, etc.)
- Length relative to body (to chin / to shoulder / to waist, etc.)
- Volume and silhouette shape
- Part placement (center / side / no part)
- Key styling details that define this character's hair

## 4. Clothing Design Spec
- List each garment with: name, color, cut/silhouette, key details
- Note which elements are SIGNATURE to this character vs. generic
- Fabric/material impression where visible

## 5. Color Palette
- Dominant colors (list 3-5 hex-approximate colors)
- Skin tone descriptor
- Hair color descriptor
- Outfit color scheme

## 6. Signature Features
- 3-5 visual elements that are ESSENTIAL to recognizing this character — if these are wrong, the character is unrecognizable

## 7. Anime Style Spec
- What anime art style era/genre does this character's design belong to?
- Line weight impression (bold/fine/medium)
- Shading style (flat / cell-shaded / soft gradient)

## 8. Character Design Tags
- Comma-separated, spec-level descriptors for image generation
- Focus on DESIGN elements, not pose or image-specific details

Note: This image appears to be a {'{3D figure/fan art/screenshot — use your best judgment}'}. Account for perspective distortion when estimating proportions."""
                }
            ],
        }]
    )

    return {
        "character": character_name,
        "series": series_name,
        "visual_profile": response.content[0].text,
        "image_path": image_path,
    }


if __name__ == "__main__":
    print(f"Extracting visual traits from: {IMAGE_PATH}")
    print(f"Character: {CHARACTER_NAME} / Series: {SERIES_NAME}")

    result = extract_visual_traits(IMAGE_PATH, CHARACTER_NAME, SERIES_NAME)

    output_path = f"{CHARACTER_NAME.replace(' ', '_')}_step1.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# {CHARACTER_NAME} — Character Design Spec\n\n")
        f.write(f"**Series:** {SERIES_NAME}  \n")
        f.write(f"**Source Image:** {IMAGE_PATH}  \n\n")
        f.write("---\n\n")
        f.write(result["visual_profile"])

    print(f"Saved → {output_path}")

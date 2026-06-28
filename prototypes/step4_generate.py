import base64
import os
from openai import OpenAI
from dotenv import load_dotenv
from PIL import Image
import io

load_dotenv('.env')

CHARACTER_NAME   = "Nana Osaki"
SERIES_NAME      = "NANA"
REFERENCE_IMAGE  = "./Nana Osaki.jpg"
OUTPUT_DIR       = "./outputs_part2"

# Scene 1 from step3 recommendations
SCENE = """
Scene: On Stage (Performance Peak)
Nana Osaki is mid-song during a band performance, commanding the stage.
Pose: slight forward lean, one hand near microphone, head tilted slightly upward.
Expression: intense focused gaze, mouth slightly open mid-lyric, no smile — serious artistry.
Mood: electric intensity, raw energy channeled into precision.
Background: dark venue interior, dramatic stage lighting in blue/purple/red, crowd silhouettes blurred behind her.
Framing: waist-up, camera at slight upward angle.
"""

CHARACTER_TAGS = """
Character must have: short blue-black center-parted bob hair, extreme porcelain pale skin,
heavy-lidded almond eyes with heavy black eyeliner, deep wine-red lips,
black leather cropped biker jacket, black leather O-ring choker,
punk aesthetic, early 2000s josei anime style, Ai Yazawa character design.
"""

def convert_to_png(image_path: str) -> bytes:
    """Convert any image format to PNG bytes for OpenAI API."""
    img = Image.open(image_path).convert("RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_scene(reference_path: str, scene: str, character_tags: str) -> bytes:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = f"""Generate an anime-style illustration in the visual style of Ai Yazawa's NANA manga (early 2000s josei art style).

Character reference is provided. Maintain the character's exact appearance.

{character_tags}

{scene}

Style: detailed anime illustration, josei manga aesthetic, fashion-forward, sophisticated.
"""

    print(f"Prompt:\n{prompt}\n")

    image_png = convert_to_png(reference_path)

    result = client.images.edit(
        model="gpt-image-2",
        image=("reference.png", image_png, "image/png"),
        prompt=prompt,
        size="1024x1024",
    )

    return base64.b64decode(result.data[0].b64_json)


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Generating scene for {CHARACTER_NAME}...")
    print(f"Reference image: {REFERENCE_IMAGE}")
    print("=" * 60)

    image_bytes = generate_scene(REFERENCE_IMAGE, SCENE, CHARACTER_TAGS)

    output_path = os.path.join(OUTPUT_DIR, "nana_osaki_stage.png")
    with open(output_path, "wb") as f:
        f.write(image_bytes)

    print(f"Saved → {output_path}")

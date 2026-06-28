import anthropic
import base64
import os
import io
import numpy as np
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFilter
from dotenv import load_dotenv

load_dotenv('.env')

CHARACTER_NAME   = "Nana Osaki"
SERIES_NAME      = "NANA"
SCENE_MOOD       = "On Stage (Performance Peak) — electric intensity, punk rock, commanding presence"
PROFILE_PATH     = "./Nana_Osaki_step2.md"
GENERATED_IMAGE  = "./outputs_part2/guide/style_transfer_real.png"
OUTPUT_DIR       = "./outputs_part2/guide"


def extract_color_palette(image_path: str, n_colors: int = 6) -> list[tuple]:
    """Extract dominant background colors from image edges (likely background area)."""
    img = Image.open(image_path).convert("RGB")
    w, h = img.size

    # sample from edges + top corners (background regions)
    regions = [
        img.crop((0, 0, w//4, h//3)),           # top-left
        img.crop((3*w//4, 0, w, h//3)),          # top-right
        img.crop((0, 2*h//3, w//4, h)),          # bottom-left
        img.crop((3*w//4, 2*h//3, w, h)),        # bottom-right
    ]

    pixels = []
    for region in regions:
        region_small = region.resize((20, 20))
        pixels.extend(list(region_small.getdata()))

    # quantize to get dominant colors
    palette_img = Image.new("RGB", (len(pixels), 1))
    palette_img.putdata(pixels)
    palette_img = palette_img.quantize(colors=n_colors)
    palette_img = palette_img.convert("RGB")

    colors = []
    seen = set()
    for x in range(palette_img.width):
        c = palette_img.getpixel((x, 0))
        if c not in seen:
            seen.add(c)
            colors.append(c)
        if len(colors) >= n_colors:
            break
    return colors


def make_palette_swatch(colors: list[tuple], output_path: str):
    """Save a color palette swatch image."""
    sw, sh = 80, 80
    canvas = Image.new("RGB", (sw * len(colors), sh))
    draw = ImageDraw.Draw(canvas)
    for i, c in enumerate(colors):
        draw.rectangle([i*sw, 0, (i+1)*sw, sh], fill=c)
        hex_color = f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"
        draw.text((i*sw + 5, sh - 18), hex_color, fill="white")
    canvas.save(output_path)


def get_background_guide(character_name: str, series_name: str,
                          scene_mood: str, character_profile: str,
                          colors: list[tuple], generated_image_path: str) -> str:
    client_a = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # encode generated image for vision
    buf = io.BytesIO()
    Image.open(generated_image_path).save(buf, format="PNG")
    img_b64 = base64.standard_b64encode(buf.getvalue()).decode()

    color_desc = ", ".join([f"#{r:02x}{g:02x}{b:02x}" for r, g, b in colors])

    profile_snippet = character_profile[:1500] if character_profile else ""

    response = client_a.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
                {"type": "text", "text": f"""You are a photography location scout helping plan a real photoshoot for {character_name} from "{series_name}".

Scene mood: {scene_mood}

Character profile summary:
{profile_snippet}

Background color palette extracted from reference image: {color_desc}

Based on the character's personality, story background, and the atmosphere in this reference image, recommend real-world locations for a photoshoot. Do NOT just describe what's in the image — INFER what real places would create this same feeling.

## Atmosphere Analysis
Describe the emotional atmosphere and visual mood of this background in 2-3 sentences. What does it feel like?

## Location Recommendations
Give 4 specific real-world location types, ordered from most to least accessible:

For each location:
**[Location Name]**
- Where: Specific type of place (e.g. "underground live music venue", "rooftop at dusk")
- Why it fits: How this location connects to the character's personality/story
- Best time: Time of day / season
- What to look for: Specific visual details to find in this location
- How to frame it: Camera position and framing suggestion

## Color & Mood Direction
3 keywords that describe the color direction a photographer should aim for.

## What to Avoid
2 background types that would feel wrong for this character."""}
            ]
        }]
    )
    return response.content[0].text


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Character: {CHARACTER_NAME} / Scene: {SCENE_MOOD}")
    print("=" * 60)

    # extract color palette from background
    print("Extracting background color palette...")
    colors = extract_color_palette(GENERATED_IMAGE)
    palette_path = os.path.join(OUTPUT_DIR, "background_palette.png")
    make_palette_swatch(colors, palette_path)
    print(f"Palette saved → {palette_path}")

    # load character profile
    profile = open(PROFILE_PATH).read() if os.path.exists(PROFILE_PATH) else ""

    # generate location guide
    print("Generating location scouting guide...")
    guide = get_background_guide(
        CHARACTER_NAME, SERIES_NAME, SCENE_MOOD,
        profile, colors, GENERATED_IMAGE
    )

    # save
    guide_path = os.path.join(OUTPUT_DIR, "background_guide.md")
    with open(guide_path, "w", encoding="utf-8") as f:
        f.write(f"# Background / Location Guide — {CHARACTER_NAME}\n\n")
        f.write(f"**Scene:** {SCENE_MOOD}  \n\n")
        f.write("---\n\n")
        f.write(guide)

    print(f"Guide saved → {guide_path}")
    print("\nOutputs:")
    print("  background_palette.png — dominant background colors")
    print("  background_guide.md    — location scouting guide")

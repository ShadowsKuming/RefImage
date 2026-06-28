import anthropic
import base64
import os
import io
import json
import math
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

load_dotenv('.env')

CHARACTER_NAME  = "Nana Osaki"
SCENE_MOOD      = "On Stage (Performance Peak)"
GENERATED_IMAGE = "./outputs_part2/guide/style_transfer_real.png"
OUTPUT_DIR      = "./outputs_part2/guide"


def analyze_lighting(image_path: str, character_name: str, scene_mood: str) -> dict:
    """Ask Vision LLM to analyze lighting and return structured data."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    buf = io.BytesIO()
    Image.open(image_path).save(buf, format="PNG")
    img_b64 = base64.standard_b64encode(buf.getvalue()).decode()

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
                {"type": "text", "text": f"""Analyze the lighting setup in this photo of {character_name} ({scene_mood}).

First, output a JSON block for the lighting diagram, then write the photography guide.

JSON format (output this first, between ```json and ```):
{{
  "lights": [
    {{
      "name": "Key Light",
      "angle_degrees": 45,
      "distance": "medium",
      "height": "above",
      "color": "#ffffff",
      "intensity": "strong",
      "type": "spot"
    }}
  ],
  "camera_angle_degrees": 180,
  "subject_facing_degrees": 0
}}

Angle convention: 0 = directly in front of subject, 90 = camera-right, 180 = behind, 270 = camera-left.
Include all visible light sources (key, fill, rim, background lights, practical lights).
Use actual observed colors for concert/stage lighting.

After the JSON, write:

## Lighting Analysis
What kind of lighting setup is this? Describe the overall quality and mood.

## Light Sources
For each light source identified:
- **[Name]**: position, color, intensity, purpose

## How to Recreate This
Step-by-step setup instructions for a photographer:
1. What equipment is needed
2. Setup order
3. Key settings/adjustments

## Budget Alternatives
How to approximate this lighting setup with limited gear (2-3 options from DIY to professional).

## What Makes This Lighting Work for This Character
Why does this specific lighting fit {character_name}'s visual identity?"""}
            ]
        }]
    )

    text = response.content[0].text

    # extract json
    lighting_data = None
    if "```json" in text:
        try:
            json_str = text.split("```json")[1].split("```")[0].strip()
            lighting_data = json.loads(json_str)
        except Exception:
            pass

    # fallback if json parsing fails
    if not lighting_data:
        lighting_data = {
            "lights": [
                {"name": "Key Light", "angle_degrees": 30, "distance": "medium",
                 "height": "above", "color": "#4488ff", "intensity": "strong", "type": "spot"},
                {"name": "Rim Light", "angle_degrees": 150, "distance": "far",
                 "height": "above", "color": "#ff4466", "intensity": "medium", "type": "spot"},
            ],
            "camera_angle_degrees": 180,
            "subject_facing_degrees": 0
        }

    return lighting_data, text


def draw_lighting_diagram(lighting_data: dict, output_path: str):
    """Draw a top-down lighting diagram."""
    size = 600
    canvas = Image.new("RGB", (size, size), "#1a1a2e")
    draw = ImageDraw.Draw(canvas)

    cx, cy = size // 2, size // 2
    radius = size // 2 - 60

    # grid circles
    for r in [80, 160, 240]:
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline="#2a2a4a", width=1)

    # axes
    draw.line([cx, 40, cx, size-40], fill="#2a2a4a", width=1)
    draw.line([40, cy, size-40, cy], fill="#2a2a4a", width=1)

    # labels
    draw.text((cx+5, 42), "FRONT", fill="#444466")
    draw.text((cx+5, size-30), "BACK", fill="#444466")
    draw.text((42, cy-14), "L", fill="#444466")
    draw.text((size-30, cy-14), "R", fill="#444466")

    # subject
    sr = 22
    draw.ellipse([cx-sr, cy-sr, cx+sr, cy+sr], fill="#e8e4e0", outline="#ffffff", width=2)
    draw.text((cx-8, cy-8), "SUB", fill="#1a1a2e")

    # camera
    cam_angle = lighting_data.get("camera_angle_degrees", 180)
    cam_rad   = math.radians(cam_angle - 90)
    cam_dist  = radius - 10
    cam_x = int(cx + cam_dist * math.cos(cam_rad))
    cam_y = int(cy + cam_dist * math.sin(cam_rad))
    draw.polygon([
        (cam_x, cam_y - 12),
        (cam_x - 10, cam_y + 8),
        (cam_x + 10, cam_y + 8),
    ], fill="#ffffff")
    draw.text((cam_x - 18, cam_y + 12), "CAM", fill="#ffffff")

    # draw each light
    for light in lighting_data.get("lights", []):
        angle_deg  = light.get("angle_degrees", 0)
        dist_label = light.get("distance", "medium")
        color_hex  = light.get("color", "#ffffff")
        name       = light.get("name", "Light")
        intensity  = light.get("intensity", "medium")

        dist_map = {"near": 0.45, "medium": 0.65, "far": 0.85}
        dist_frac = dist_map.get(dist_label, 0.65)
        dist_px   = int(radius * dist_frac)

        angle_rad = math.radians(angle_deg - 90)
        lx = int(cx + dist_px * math.cos(angle_rad))
        ly = int(cy + dist_px * math.sin(angle_rad))

        # parse color
        try:
            r = int(color_hex[1:3], 16)
            g = int(color_hex[3:5], 16)
            b = int(color_hex[5:7], 16)
            light_color = (r, g, b)
        except Exception:
            light_color = (255, 255, 255)

        # beam line from light to subject
        alpha_val = 180 if intensity == "strong" else 120 if intensity == "medium" else 70
        beam_color = (*light_color, alpha_val)
        draw.line([lx, ly, cx, cy], fill=light_color, width=2)

        # light circle
        lr = 18
        draw.ellipse([lx-lr, ly-lr, lx+lr, ly+lr],
                     fill=light_color, outline="#ffffff", width=2)

        # label
        label_x = lx + (20 if lx > cx else -70)
        label_y = ly - 8
        draw.text((label_x, label_y), name, fill="#ffffff")

    # title
    draw.text((10, 10), "LIGHTING DIAGRAM (top-down view)", fill="#666688")

    canvas.save(output_path)


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Character: {CHARACTER_NAME} / Scene: {SCENE_MOOD}")
    print("=" * 60)

    print("Analyzing lighting...")
    lighting_data, guide_text = analyze_lighting(GENERATED_IMAGE, CHARACTER_NAME, SCENE_MOOD)
    print(f"Detected {len(lighting_data.get('lights', []))} light sources")

    print("Drawing lighting diagram...")
    diagram_path = os.path.join(OUTPUT_DIR, "lighting_diagram.png")
    draw_lighting_diagram(lighting_data, diagram_path)
    print(f"Diagram saved → {diagram_path}")

    guide_path = os.path.join(OUTPUT_DIR, "lighting_guide.md")
    with open(guide_path, "w", encoding="utf-8") as f:
        f.write(f"# Lighting Guide — {CHARACTER_NAME}\n\n")
        f.write(f"**Scene:** {SCENE_MOOD}  \n\n")
        f.write("---\n\n")
        clean = guide_text
        if "```json" in clean:
            clean = clean.split("```json")[0] + clean.split("```")[2]
        f.write(clean.strip())
    print(f"Guide saved → {guide_path}")

    print("\nOutputs:")
    print("  lighting_diagram.png — top-down light position map")
    print("  lighting_guide.md    — setup instructions")

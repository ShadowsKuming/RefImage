import base64
import os
import io
from openai import OpenAI
from PIL import Image, ImageDraw
from dotenv import load_dotenv

load_dotenv('.env')

INPUT_IMAGE  = "./outputs_part2/nana_osaki_stage.png"
OUTPUT_DIR   = "./outputs_part2"

# Define what area to edit and what change to make
EDIT_REGION  = "face"       # "face" | "background" | "outfit" | custom (x1,y1,x2,y2)
EDIT_PROMPT  = "same character, slightly softer expression, lips parted as if about to sing, eyes still intense but with a trace of vulnerability"


def make_mask(image_size: tuple, region: str | tuple) -> Image.Image:
    """
    Create mask image: transparent = edit this area, black = keep this area.
    """
    w, h = image_size
    mask = Image.new("RGBA", (w, h), (0, 0, 0, 255))  # start all black (keep)
    draw = ImageDraw.Draw(mask)

    if region == "face":
        # rough face region: upper-center of image
        x1, y1, x2, y2 = int(w * 0.25), int(h * 0.05), int(w * 0.75), int(h * 0.45)
    elif region == "background":
        # everything except center character
        x1, y1, x2, y2 = 0, 0, w, h
        draw.rectangle([int(w*0.15), int(h*0.05), int(w*0.85), int(h*0.95)], fill=(0, 0, 0, 255))
        draw.rectangle([0, 0, w, h], fill=(0, 0, 0, 0))
        draw.rectangle([int(w*0.15), int(h*0.05), int(w*0.85), int(h*0.95)], fill=(0, 0, 0, 255))
        return mask
    elif region == "outfit":
        x1, y1, x2, y2 = int(w * 0.15), int(h * 0.4), int(w * 0.85), int(h * 0.95)
    elif isinstance(region, tuple):
        x1, y1, x2, y2 = region
    else:
        x1, y1, x2, y2 = 0, 0, w, h

    # make the selected region transparent (= will be edited)
    draw.rectangle([x1, y1, x2, y2], fill=(0, 0, 0, 0))
    return mask


def run_inpainting(image_path: str, region: str | tuple, edit_prompt: str) -> bytes:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    original = Image.open(image_path).convert("RGBA")
    w, h = original.size
    print(f"Image size: {w}x{h}")

    # resize to 1024x1024 if needed (gpt-image-2 requirement)
    if w != 1024 or h != 1024:
        original = original.resize((1024, 1024), Image.LANCZOS)
        print("Resized to 1024x1024")

    mask = make_mask((1024, 1024), region)

    # save mask preview so you can verify the region
    mask_preview_path = os.path.join(OUTPUT_DIR, "mask_preview.png")
    mask_vis = Image.new("RGBA", (1024, 1024))
    mask_vis.paste(original, (0, 0))
    # overlay semi-transparent red on the edit region
    overlay = Image.new("RGBA", (1024, 1024), (255, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    if region == "face":
        draw.rectangle([int(1024*0.25), int(1024*0.05), int(1024*0.75), int(1024*0.45)], fill=(255, 0, 0, 100))
    overlay_composite = Image.alpha_composite(mask_vis, overlay)
    overlay_composite.save(mask_preview_path)
    print(f"Mask preview saved → {mask_preview_path}")

    # convert to bytes
    img_buf = io.BytesIO()
    original.save(img_buf, format="PNG")
    img_bytes = img_buf.getvalue()

    mask_buf = io.BytesIO()
    mask.save(mask_buf, format="PNG")
    mask_bytes = mask_buf.getvalue()

    print(f"Sending to gpt-image-2 inpainting...")
    print(f"Edit region: {region}")
    print(f"Edit prompt: {edit_prompt}\n")

    result = client.images.edit(
        model="gpt-image-2",
        image=("image.png", img_bytes, "image/png"),
        mask=("mask.png", mask_bytes, "image/png"),
        prompt=edit_prompt,
        size="1024x1024",
    )

    return base64.b64decode(result.data[0].b64_json)


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.exists(INPUT_IMAGE):
        print(f"ERROR: input image not found at {INPUT_IMAGE}")
        print("Run step4_generate.py first.")
        exit(1)

    print(f"Input: {INPUT_IMAGE}")
    print("=" * 60)

    result_bytes = run_inpainting(INPUT_IMAGE, EDIT_REGION, EDIT_PROMPT)

    output_path = os.path.join(OUTPUT_DIR, f"nana_inpaint_{EDIT_REGION}.png")
    with open(output_path, "wb") as f:
        f.write(result_bytes)

    print(f"Saved → {output_path}")

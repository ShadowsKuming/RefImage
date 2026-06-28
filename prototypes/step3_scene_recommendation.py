import anthropic
import os
from dotenv import load_dotenv

load_dotenv('.env')

CHARACTER_NAME   = "Nana Osaki"
SERIES_NAME      = "NANA"
VISUAL_SPEC_PATH = "./Nana_Osaki_step1.md"
PROFILE_PATH     = "./Nana_Osaki_step2.md"


def recommend_scenes(character_name: str, series_name: str,
                     visual_spec: str, character_profile: str) -> str:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2500,
        messages=[{
            "role": "user",
            "content": f"""You are a creative director generating reference image scene ideas for the character {character_name} from "{series_name}".

You have:

## Character Visual Spec (Step 1)
{visual_spec[:2000]}

## Character Personality Profile (Step 2)
{character_profile[:2000]}

Generate 6 scene recommendations for reference images of this character.
Each scene should feel true to who this character is.

For each scene output:

### Scene [N]: [Short Title]
- **Situation:** What is happening / what context is this
- **Mood:** The emotional tone of this image
- **Pose:** Specific body language and posture
- **Expression:** Exact facial expression
- **Framing:** Close-up / half-body / full-body, camera angle
- **Background:** Setting, lighting, color palette
- **Why it fits:** Why this scene is authentic to this character
- **Personality slider adjustments:** Which sliders shift from baseline for this scene (e.g. INTENSITY: higher than default)

Cover a range:
- At least 1 performance/action scene
- At least 1 quiet/introspective scene
- At least 1 everyday/street scene
- At least 1 emotional scene (showing a side the character rarely reveals)
- The remaining 2 can be anything that fits the character well"""
        }]
    )

    return response.content[0].text


if __name__ == "__main__":
    print(f"Generating scene recommendations for {CHARACTER_NAME}...")

    visual_spec = open(VISUAL_SPEC_PATH).read() if os.path.exists(VISUAL_SPEC_PATH) else ""
    profile     = open(PROFILE_PATH).read()     if os.path.exists(PROFILE_PATH)     else ""

    if not visual_spec:
        print("Warning: step1 output not found")
    if not profile:
        print("Warning: step2 output not found")

    scenes = recommend_scenes(CHARACTER_NAME, SERIES_NAME, visual_spec, profile)

    output_path = f"{CHARACTER_NAME.replace(' ', '_')}_step3_scenes.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# {CHARACTER_NAME} — Scene Recommendations\n\n")
        f.write(f"**Series:** {SERIES_NAME}  \n\n")
        f.write("---\n\n")
        f.write(scenes)

    print(f"Saved → {output_path}")

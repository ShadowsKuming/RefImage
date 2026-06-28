import anthropic
import os
from ddgs import DDGS
from dotenv import load_dotenv

load_dotenv('.env')

CHARACTER_NAME = "Nana Osaki"
SERIES_NAME    = "NANA"
VISUAL_SPEC_PATH = "./Nana_Osaki_step1.md"

def search_character_info(character_name: str, series_name: str) -> tuple[str, int]:
    queries = [
        f'"{character_name}" {series_name} personality traits character',
        f'"{character_name}" {series_name} background story role',
        f'{series_name} anime setting world story context',
    ]

    snippets = []
    with DDGS() as ddgs:
        for q in queries:
            print(f"  Searching: {q}")
            results = list(ddgs.text(q, max_results=4))
            for r in results:
                snippets.append(f"[{r['title']}]\n{r['body'][:400]}")

    return "\n\n".join(snippets), len(snippets)


def extract_character_profile(character_name: str, series_name: str,
                               search_data: str, visual_spec: str) -> str:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": f"""You have two sources of information about {character_name} from "{series_name}":

## Source A: Visual Design Spec (extracted from reference image)
{visual_spec}

## Source B: Web Search Results
{search_data}

Using both sources, extract a CHARACTER PROFILE focused on how personality and background should influence image generation.

Output the following:

## 1. Personality Traits
- List 5-8 core traits
- For each trait, note: how it shows visually (expression, posture, energy)
- Mark each as: [CONFIRMED from search] or [INFERRED from visual style]

## 2. Background & Story Role
- Who is this character in the story?
- Key life events that shaped their appearance/attitude
- Mark as: [CONFIRMED] or [INFERRED]

## 3. Series Setting
- Time period, location, world context
- Genre and tone of the series
- How the setting affects character visual design

## 4. Default Visual Mood
- What emotional state should this character default to in images?
- Typical expression, posture, energy level
- What scenes/contexts fit this character?

## 5. Personality Sliders (baseline)
- List 6 personality dimensions as editable defaults
- Format: TRAIT: [default] (low_end ←→ high_end)
- Example: ENERGY: [low-key cool] (lethargic ←→ intense)
- These should directly affect how the character looks in an image

## 6. Image Generation Personality Tags
- Comma-separated descriptors capturing personality-driven visual cues"""
        }]
    )

    return response.content[0].text


if __name__ == "__main__":
    print(f"Character: {CHARACTER_NAME} / Series: {SERIES_NAME}")
    print("=" * 60)

    # load visual spec from step1
    if os.path.exists(VISUAL_SPEC_PATH):
        with open(VISUAL_SPEC_PATH, "r") as f:
            visual_spec = f.read()
        print(f"Loaded visual spec from {VISUAL_SPEC_PATH}")
    else:
        visual_spec = "No visual spec available."
        print("Warning: no step1 output found, proceeding without visual spec")

    # search
    print("\nSearching for character info...")
    search_data, count = search_character_info(CHARACTER_NAME, SERIES_NAME)
    print(f"Collected {count} snippets\n")

    # extract profile
    print("Extracting character profile...")
    profile = extract_character_profile(CHARACTER_NAME, SERIES_NAME, search_data, visual_spec)

    # save
    output_path = f"{CHARACTER_NAME.replace(' ', '_')}_step2.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# {CHARACTER_NAME} — Character Profile\n\n")
        f.write(f"**Series:** {SERIES_NAME}  \n\n")
        f.write("---\n\n")
        f.write(profile)

    print(f"Saved → {output_path}")

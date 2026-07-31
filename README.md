# RefImage — Anime Character Photo-Reference System

**[English](README.md) | [中文](README.zh.md)**

Upload a reference image of an anime or game character, and RefImage plans your cosplay shoot from "who am I shooting" all the way to "exactly how to shoot each frame" — auto-building a character profile, filling out the shoot plan as you chat, generating AI reference shots, and exporting shooting guides and a shoot handbook.

![RefImage home page](docs/screenshot-home.png)

---

## Quick Start

```bash
cp .env.example .env
# Fill in OPENAI_API_KEY (used for generation, vision, and chat)

docker compose up --build
```

Open `http://localhost:3001` and log in with your invite token.

---

## Full Walkthrough

### 1. Create a project

Click "New Project" on the home page and upload a character reference image (an official art piece, a screenshot, a character sheet — anything works). The AI looks at the image and guesses who the character is, naming the character and the source work for you to confirm — if it's wrong, just tell it the correct name. Once confirmed, it researches the character and builds a profile: personality, backstory, iconic moments.

### 2. The project workspace

Inside a project you get three panels:

- **Character** — personality/backstory/iconic moments, avatar art, a costume & prop checklist. Edit any of it by hand, or let the AI fill it in.
- **Shot Plan** — a grid of shots, each one a specific frame you plan to shoot.
- **Shoot Summary** — equipment, locations, schedule, and prep notes, automatically rolled up from the shots you've already worked out.

A mascot assistant sits in the corner of the project page, ready to chat whenever: roughly when you're shooting, whether a photographer is lined up, how the wig/costume prep is going, the overall mood you want this shoot to express, your own take on the character — she records what you tell her straight into the right panel as you talk, so you're not filling out forms by hand. When you're ready to work out an actual shot, click her "brainstorm a shot" suggestion to jump straight into a new one.

### 3. Individual shots

Every shot has its own canvas and its own assistant:

- **Describe the shot you want** — scene, pose, expression, mood. She'll ask for whatever details are still missing, then generate a reference image. Every version you generate stays on the canvas so you can compare them side by side.
- **Camera panel** — when you need to pin down an exact shot type (close-up / medium / full-body / wide), angle (high / eye-level / low), or aspect ratio (portrait / landscape), pick it directly on the panel instead of describing it in chat.
- **Reference-guided generation** — upload a pose sketch, a background photo, a prop photo, or a target expression, and generation will follow it.
- **Refine panel** — not happy with a version? Adjust composition, colour tone, expression intensity and generate a new variant — the original stays put.
- **Four shooting guides** — an action reference, expression cues, composition/lens suggestions, and location recommendations, ready to use on location.

### 4. Export the shoot handbook

Once your shots are locked in, compile a shoot handbook — a single-shot sheet, or a full project handbook (cover, a sheet per shot, the schedule, backup plans, the prep checklist). View it in the browser, or print/export it as a PDF to bring on location.

### 5. Manage your projects

The home page is where all your projects live: create, resume editing, export/import a project backup, or delete one. Each user can keep up to 5 projects at a time.

---

## Interface Settings

- **Theme** — switch between several colour themes from the top bar (dark, light, sakura, matcha, ocean, amber, cyber, parchment).
- **Language** — 中文 / English / 日本語, switchable anytime.

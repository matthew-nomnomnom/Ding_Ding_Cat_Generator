# Ding Ding Cat WhatsApp Sticker Generator

> Internal application for the Hong Kong Tramway Branding & Communication Team  
> **Mascot**: 叮叮貓 "Ding Ding Cat" — Hong Kong Tramway's official mascot  
> **Purpose**: Generate consistent, festival-themed WhatsApp stickers year-round

---

## Project Architecture

```
┌──────────────────────────────────────────────────────┐
│               Desktop Application (Tauri or Python)  │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐   │
│  │ Festival │  │  Prompt  │  │   Preview Grid    │   │
│  │ Selector │  │  Builder │  │   & Export        │   │
│  └──────────┘  └──────────┘  └───────────────────┘   │
│                      │                               │
│              ┌───────▼────────┐                      │
│              │  Replicate API │   (Cloud)            │
│              │  (SDXL + LoRA) │                      │
│              └───────┬────────┘                      │
│                      │                               │
│  ┌───────────────────▼────────────────────────────┐  │
│  │  Image Post-Processing (Local)                 │  │
│  │  rembg → resize 512 → WebP → sticker pack ZIP  │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

---

## 1. AI Generation — Replicate API + Custom LoRA

### Why Replicate

| Factor              | Self-hosted SD + LoRA        | Replicate API (chosen)    |
|---------------------|------------------------------|---------------------------|
| GPU needed locally  | Yes (NVIDIA 8GB+ or M2 Max)  | No — runs in cloud        |
| Infrastructure cost | $500+ GPU hardware           | $0                        |
| Per-image cost      | Electricity only             | ~$0.005/image             |
| LoRA training cost  | ~$2 GPU rental (RunPod)      | ~$3–5 (built-in trainer)  |
| Annual total        | $500+                        | ~$6                       |
| Setup complexity    | High (ComfyUI/diffusers)     | Low (API calls)           |
| Maintenance         | You manage dependencies      | Zero maintenance          |

### LoRA Training (one-time)

1. **Data prep**: Crop 10+ reference images of Ding Ding Cat to 1024×1024 square
2. **Captioning**: Write descriptions for each (e.g. `"dingdingcat, full body, waving paw, front view, white background"`)
3. **Training**: Use [Replicate FLUX LoRA trainer](https://replicate.com/ostris/flux-dev-lora-trainer) or rent RunPod GPU for 1–2 hours
4. **Output**: A `.safetensors` file (~100MB) — upload to Replicate as a private model
5. **Trigger word**: The LoRA learns a trigger like `dingdingcat` or `TOK` to activate the mascot appearance

### Generation API Call (pseudocode)

```python
import replicate

output = replicate.run(
    "your-username/dingdingcat-lora:version-hash",
    input={
        "prompt": "dingdingcat wearing a red cheongsam, holding red envelopes, "
                  "Chinese New Year fireworks background, festive red and gold, "
                  "3D cartoon style, high quality, adorable",
        "negative_prompt": "blurry, low quality, deformed, extra limbs, "
                           "bad anatomy, watermark, text",
        "width": 1024,
        "height": 1024,
        "num_outputs": 4,
        "num_inference_steps": 28,
    }
)
```

---

## 2. Festival Calendar & Prompt Templates

12 festivals covering a full year of Hong Kong-centric content:

| # | Festival                  | Typical Month | Key Visual Elements                                |
|---|---------------------------|---------------|----------------------------------------------------|
| 1 | New Year's Day            | January       | Fireworks, party hats, countdown clock             |
| 2 | Chinese New Year          | Jan/Feb       | Red envelopes, cheongsam, dragon dance, mandarins  |
| 3 | Cheung Chau Bun Festival  | April/May     | Steamed buns, parade drums, island backdrop        |
| 4 | Easter / Ching Ming       | April         | Bunny ears, eggs / chrysanthemums, ancestral       |
| 5 | Dragon Boat Festival      | May/June      | Zongzi (rice dumplings), dragon boat, drum         |
| 6 | Summer / Tuen Ng          | June          | Watermelon, beach, sun umbrella, sunglasses        |
| 7 | HKSAR Establishment Day   | July 1        | Bauhinia flag, fireworks over Victoria Harbour     |
| 8 | Qixi Festival             | August        | Magpie bridge, stars, romantic couple cats         |
| 9 | Mid-Autumn Festival       | September     | Mooncakes, lanterns, Chang'e rabbit, full moon     |
|10 | National Day / Halloween  | October       | PRC flag / pumpkins, ghosts, witch hat             |
|11 | Chung Yeung Festival      | November      | Chrysanthemums, hiking stick, hilltop              |
|12 | Christmas / Winter        | December      | Santa hat, snow, hotpot, dumplings, tram dressed   |

### Prompt Template Structure (`festivals.json`)

```json
{
  "festivals": [
    {
      "id": "mid-autumn",
      "name_en": "Mid-Autumn Festival",
      "name_zh": "中秋節",
      "month": 9,
      "templates": [
        {
          "id": "mid-autumn-01",
          "prompt": "dingdingcat holding a mooncake, wearing traditional Tang suit, "
                    "lanterns in background, full moon, warm orange tones, "
                    "3D cartoon style, adorable, high quality",
          "negative_prompt": "blurry, low quality, deformed, extra limbs, bad anatomy, watermark",
          "props": ["mooncake", "lantern", "osmanthus flower"],
          "backgrounds": ["full moon night", "lantern-lit garden", "Victoria Harbour"]
        }
      ]
    }
  ]
}
```

---

## 3. Desktop Application Design

### Tech Stack Options

| Approach                    | Pros                                      | Cons                                   | Best for           |
|-----------------------------|-------------------------------------------|----------------------------------------|--------------------|
| **Python + NiceGUI**        | Fast to build, simple, good docs          | Slightly heavier binary                | Quick prototype    |
| **Python + customtkinter**  | Native look, Python-native, lightweight   | Less modern feel                       | Simple tool        |
| **Tauri (Rust + HTML/JS)**  | Lightweight (~10MB), cross-platform       | Steeper learning curve, Rust required  | Production app     |
| **Electron**                | Full web tech, huge ecosystem             | Heavy (~150MB), resource-hungry        | Complex UI         |

### Recommended: Python + NiceGUI (for fast intern development)

- Single Python file can run a full GUI
- Built-in async support for API calls
- Easy bundling: `pyinstaller` → single `.app` / `.exe`
- Lightweight enough for a single-purpose tool

### UI Screens

```
┌────────────────────────────────────────────────┐
│  🚋 Ding Ding Cat Sticker Generator            │
│                                                │
│  Festival: [ Mid-Autumn Festival     ▼ ]       │
│                                                │
│  Prompt Templates:                             │
│  ○ Template 1: "holding mooncake + lanterns"   │
│  ● Template 2: "riding dragon boat + drums"    │
│  ○ Template 3: "custom prompt below..."         │
│                                                │
│  Variations:  [ 8  ] per template              │
│  Seed:        [ random ]                       │
│                                                │
│  ┌─────────────── Custom Prompt ──────────────┐│
│  │ dingdingcat holding a mooncake, wearing    ││
│  │ Tang suit, lanterns, full moon, warm tones ││
│  └────────────────────────────────────────────┘│
│                                                │
│  [ Generate Stickers ]  (estimated: ~8s each)  │
│                                                │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐          │
│  │ 🖼 │ │ 🖼 │ │ 🖼 │ │ 🖼 │ │ 🖼 │ ...      │
│  └────┘ └────┘ └────┘ └────┘ └────┘          │
│   ☑ Select All   [Remove BG]                  │
│                                                │
│  [ Export Sticker Pack (.zip) ]               │
│                                                │
│  Status: ✅ 8 stickers generated | 0 errors    │
└────────────────────────────────────────────────┘
```

### Key Features

1. **Festival Selector** — dropdown with all 12 festivals, highlights upcoming ones
2. **Prompt Template Browser** — shows pre-written templates per festival, user can tweak
3. **Custom Prompt Mode** — free-text input for bespoke stickers (e.g. event-specific)
4. **Batch Generation** — configure 4–16 images per run with identical LoRA seed for consistency
5. **Live Preview Grid** — generated images appear as they complete
6. **Background Removal Toggle** — per-image or bulk, uses local rembg (no API cost)
7. **Export** — converts to 512×512 WebP ≤100KB, packages as WhatsApp-compatible ZIP

---

## 4. Image Post-Processing Pipeline

All processing runs **locally** (no cloud cost):

```
Generated Image (1024×1024 PNG from Replicate)
      │
      ▼
┌─────────────────────────┐
│  1. Background Removal   │   rembg / RMBG-2.0
│     (optional, toggle)   │   → transparent PNG
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│  2. Resize to 512×512    │   Pillow LANCZOS
│     (WhatsApp minimum)   │
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│  3. Convert to WebP      │   Pillow .save(webp)
│     Quality 80, <100KB   │   + binary size check
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│  4. Sticker Pack Bundle  │   Python zipfile
│     stickermeta.json     │   + metadata files
│     + all .webp files    │
└─────────────────────────┘
```

### WhatsApp Sticker Pack Format

```
sticker_pack.zip
├── stickermeta.json        ← metadata: pack name, author, tray icon
├── sticker_01.webp          ← 512×512, ≤100KB
├── sticker_02.webp
├── ...
└── tray.webp                ← 96×96 tray icon
```

**`stickermeta.json`**:
```json
{
  "identifier": "dingding-mid-autumn-2026",
  "name": "Ding Ding Cat Mid-Autumn",
  "publisher": "HK Tramway",
  "tray_image": "tray.webp",
  "stickers": [
    { "image": "sticker_01.webp", "emojis": ["🌕", "🥮"] },
    { "image": "sticker_02.webp", "emojis": ["🏮", "🐱"] }
  ]
}
```

---

## 5. Development Milestones (8 Weeks)

```
Week 1  ██ Prepare LoRA training data
        │   - Crop 10+ mascot images to 1024×1024
        │   - Caption each image (pose, angle, expression)
        │   - Decide: FLUX LoRA vs SDXL LoRA
        └──────────────────────────────────────────

Week 2  ██ Train LoRA + validate
        │   - Run training on Replicate or RunPod
        │   - Test generation on 3 festival prompts
        │   - Iterate: re-crop, re-caption, re-train if needed
        └──────────────────────────────────────────

Week 3  ██ Scaffold desktop app
        │   - Set up Python project structure
        │   - Install NiceGUI, replicate SDK, Pillow, rembg
        │   - Build basic shell: window, festival dropdown, layout
        └──────────────────────────────────────────

Week 4  ██ Integrate Replicate API
        │   - API key config (env var or settings file)
        │   - Call generation endpoint with templated prompts
        │   - Show progress bar during generation
        │   - Load and display generated images in grid
        └──────────────────────────────────────────

Week 5  ██ Build prompt template system
        │   - Create festivals.json with all 12 festivals
        │   - 8–10 prompt templates per festival
        │   - UI: template selector, custom prompt editor
        │   - Preset props/backgrounds checkboxes
        └──────────────────────────────────────────

Week 6  ██ Image post-processing pipeline
        │   - Background removal (rembg integration)
        │   - Resize to 512×512
        │   - WebP conversion + size limit enforcement
        │   - Sticker pack ZIP bundling
        └──────────────────────────────────────────

Week 7  ██ Polish & testing
        │   - Full workflow test: generate → preview → export
        │   - Test sticker pack import on real WhatsApp
        │   - Error handling: API timeouts, bad prompts, disk full
        │   - UI polish: dark mode, i18n (English + 中文 labels)
        └──────────────────────────────────────────

Week 8  ██ Documentation & handover
        │   - User guide for Branding team (how to generate stickers)
        │   - Developer guide (how to add new festivals, update LoRA)
        │   - Package as .app (Mac) / .exe (Windows) with pyinstaller
        └──────────────────────────────────────────
```

---

## 6. Project Structure

```
dingding-sticker-gen/
├── PROJECT_PLAN.md              ← This file
├── README.md                    ← User-facing how-to
│
├── config/
│   ├── festivals.json           ← 12 festivals × 8–10 templates each
│   └── settings.yaml            ← Replicate API config, defaults
│
├── assets/
│   ├── lora/                    ← LoRA .safetensors (not committed)
│   ├── training_images/         ← 10+ reference images (not committed)
│   └── icons/                   ← App icon, tray icon
│
├── src/
│   ├── main.py                  ← App entry point
│   ├── ui/
│   │   ├── app.py               ← NiceGUI window & layout
│   │   ├── festival_selector.py ← Dropdown component
│   │   ├── prompt_editor.py     ← Template selector + custom prompt
│   │   ├── preview_grid.py      ← Generated image grid
│   │   └── styles.py            ← CSS / theme config
│   │
│   ├── generation/
│   │   ├── replicate_api.py     ← Replicate API client wrapper
│   │   ├── prompt_builder.py    ← Template interpolation
│   │   └── lora_manager.py      ← LoRA model version tracking
│   │
│   ├── processing/
│   │   ├── background.py        ← rembg background removal
│   │   ├── webp_converter.py    ← Resize + WebP conversion
│   │   └── packager.py          ← Sticker pack ZIP + stickermeta.json
│   │
│   └── utils/
│       ├── config_loader.py     ← Load YAML/JSON configs
│       └── image_cache.py       ← Local cache of generated images
│
├── tests/
│   ├── test_prompt_builder.py
│   ├── test_webp_converter.py
│   └── test_packager.py
│
├── requirements.txt             ← Python dependencies
├── pyproject.toml               ← Project metadata
└── .gitignore                   ← Ignore API keys, LoRA files, generated images
```

---

## 7. Dependencies (`requirements.txt`)

```
# AI generation
replicate>=1.0.0

# Desktop UI
nicegui>=2.0.0

# Image processing
Pillow>=10.0.0
rembg>=2.0.0            # Background removal
onnxruntime>=1.15.0     # rembg dependency

# Config
pyyaml>=6.0

# Packaging
pyinstaller>=6.0.0      # Build standalone .app / .exe

# Development
pytest>=8.0.0
```

---

## 8. Cost Summary

| Item                              | Cost (USD)        | Frequency    |
|-----------------------------------|-------------------|--------------|
| LoRA training (Replicate)         | $3–5              | Once         |
| Image generation (15/sticker × 12 festivals = 180/year) | ~$0.90 | Annual |
| Background removal                | $0 (local)        | N/A          |
| WebP conversion                   | $0 (local)        | N/A          |
| Desktop app                       | $0 (local)        | N/A          |
| **Total Year 1**                  | **~$6**           |              |
| **Annual ongoing**                | **~$1/year**      |              |

---

## 9. Key Decisions Checklist

- [ ] **LoRA model**: FLUX.1-Dev-LoRA vs SDXL-LoRA? (FLUX = better quality, SDXL = cheaper API)
- [ ] **Stylistic direction**: 3D cartoon (Pixar-like) vs 2D flat illustration vs Hong Kong comic style?
- [ ] **Desktop framework**: Python + NiceGUI (fast) vs Tauri (lightweight) vs customtkinter (simple)?
- [ ] **Background removal**: Always transparent stickers, or keep backgrounds for some?
- [ ] **App branding**: Include Tramway logo watermark on stickers?
- [ ] **i18n**: English-only UI, or bilingual English/Chinese?

---

## 10. Next Actions (immediate)

1. **Collect & organize mascot images** — gather all 10+ reference images, check quality
2. **Write image captions** — describe each image for LoRA training
3. **Set up Replicate account** — create account, get API key, test free generation
4. **Install Python environment** — set up virtualenv with NiceGUI + deps
5. **Run hello-world UI** — get a basic NiceGUI window running to confirm setup

---

*Plan last updated: June 2026*  
*For discussion with Tramplus interns and instructor*

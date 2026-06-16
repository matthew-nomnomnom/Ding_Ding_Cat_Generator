# Ding Ding Cat WhatsApp Sticker Generator

Generate festive WhatsApp stickers of Hong Kong Tramway's mascot — **Ding Ding Cat (叮叮貓)** — using AI.

## Quick Start

```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure Replicate API key
cp config/settings.yaml config/settings.local.yaml
# Edit settings.local.yaml — add your Replicate API key

# 4. Run the app
python main.py
```

## How It Works

1. Select a festival (Chinese New Year, Mid-Autumn, Christmas, etc.)
2. Choose or customize a prompt template
3. Click **Generate** — the app calls Replicate's hosted AI model
4. Preview generated stickers in the grid
5. Enable background removal if you want transparent stickers
6. **Export** as a WhatsApp-compatible sticker pack ZIP

## Project Structure

```
dingding-sticker-gen/
├── main.py                     ← Entry point
├── config/
│   ├── festivals.json          ← 12 festivals × 8–10 prompt templates
│   └── settings.yaml / .local  ← API keys & app config
├── src/
│   ├── ui/                     ← NiceGUI frontend
│   ├── generation/             ← Replicate API & prompt building
│   ├── processing/             ← Background removal, WebP, packaging
│   └── utils/                  ← Config loading, image caching
├── tests/
└── assets/                     ← LoRA models, reference images, icons
```

## Requirements

- Python 3.10+
- Replicate API key ([replicate.com](https://replicate.com))
- A trained Ding Ding Cat LoRA model (see `PROJECT_PLAN.md`)

## Documentation

See `PROJECT_PLAN.md` for the full project plan, architecture, and development milestones.

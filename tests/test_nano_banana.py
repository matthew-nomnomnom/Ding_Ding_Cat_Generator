"""Live test — Nano Banana 2 image generation with reference images.

Requires: AI_GATEWAY_API_KEY env var
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import yaml
from src.llm.nano_banana_client import NanoBananaClient


def main():
    if not os.environ.get("AI_GATEWAY_API_KEY"):
        print("FAIL: AI_GATEWAY_API_KEY not set")
        return 1

    base_dir = os.path.join(os.path.dirname(__file__), "..")

    with open(os.path.join(base_dir, "config", "llm_settings.yaml")) as f:
        llm_settings = yaml.safe_load(f)

    ref_dir = os.path.join(base_dir, "assets", "reference_images")
    output_dir = os.path.join(base_dir, "output", "test_stickers")
    os.makedirs(output_dir, exist_ok=True)

    client = NanoBananaClient(
        api_key=os.environ["AI_GATEWAY_API_KEY"],
        settings=llm_settings,
        ref_images_dir=ref_dir,
    )

    tests = [
        ("christmas", "Ding Ding Cat wearing a Santa hat and red scarf, holding a wrapped gift box, standing in front of a decorated Christmas tree, snow falling, warm festive lighting, 3D cartoon style, adorable, high quality, WhatsApp sticker"),
        ("chinese-new-year", "Ding Ding Cat wearing a red traditional cheongsam with gold embroidery, holding red envelopes (lai see), festive red and gold background with lanterns, 3D cartoon style, adorable, high quality, WhatsApp sticker"),
        ("mid-autumn", "Ding Ding Cat holding a mooncake, sitting under a bright full moon, glowing paper lanterns floating, warm orange and gold tones, 3D cartoon style, adorable, high quality, WhatsApp sticker"),
    ]

    passed = 0
    failed = 0

    for festival_id, prompt in tests:
        print(f"\n--- Generating [{festival_id}] ---")
        print(f"Prompt: {prompt[:100]}...")

        output = os.path.join(output_dir, f"sticker_{festival_id}.png")
        t0 = time.monotonic()
        try:
            paths = client.generate(prompt, output_path=output)
            elapsed = time.monotonic() - t0

            if not paths:
                print(f"  FAIL: No image returned")
                failed += 1
                continue

            file_size = os.path.getsize(paths[0]) if os.path.exists(paths[0]) else 0
            print(f"  PASS: {paths[0]} ({file_size:,} bytes) in {elapsed:.1f}s")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
            failed += 1

        time.sleep(2)

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"Output: {output_dir}/")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

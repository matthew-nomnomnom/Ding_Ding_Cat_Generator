"""Live test — Full pipeline: LLM refinement → Nano Banana 2 image generation.

Requires: AI_GATEWAY_API_KEY env var
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import yaml
from src.llm.sticker_generator import StickerGenerator, find_reference_images_dir


def main():
    if not os.environ.get("AI_GATEWAY_API_KEY"):
        print("FAIL: AI_GATEWAY_API_KEY not set")
        return 1

    base_dir = os.path.join(os.path.dirname(__file__), "..")

    with open(os.path.join(base_dir, "config", "festivals.json")) as f:
        festivals = json.load(f)
    with open(os.path.join(base_dir, "config", "llm_settings.yaml")) as f:
        llm_settings = yaml.safe_load(f)
    with open(os.path.join(base_dir, "config", "safety_blocklist.yaml")) as f:
        blocklist = yaml.safe_load(f)

    ref_dir = find_reference_images_dir()
    if not ref_dir:
        print("FAIL: No reference images found")
        return 1
    print(f"Reference images: {ref_dir} ({len(os.listdir(ref_dir))} files)")

    data_dir = os.path.join(base_dir, "data")
    output_dir = os.path.join(base_dir, "output", "full_pipeline")
    os.makedirs(output_dir, exist_ok=True)

    generator = StickerGenerator(
        app_config_dir=data_dir,
        festivals_config=festivals,
        llm_settings=llm_settings,
        blocklist_config=blocklist,
        ref_images_dir=ref_dir,
        output_dir=output_dir,
    )

    tests = [
        ("christmas", "cat with a Santa hat holding a present, snowy background"),
        ("chinese-new-year", "貓咪穿著紅色旗袍拿著利是封"),
        ("mid-autumn", "cat eating mooncake with family under the full moon"),
    ]

    passed = 0
    failed = 0

    for festival_id, user_input in tests:
        print(f"\n--- [{festival_id}] \"{user_input}\" ---")
        t0 = time.monotonic()
        try:
            path, result, warnings = generator.generate(festival_id, user_input)
            elapsed = time.monotonic() - t0
            file_size = os.path.getsize(path)

            print(f"  Refined: {result.prompt[:100]}...")
            print(f"  Props:   {result.suggested_props}")
            print(f"  BG:      {result.suggested_background}")
            print(f"  Image:   {path} ({file_size:,} bytes)")
            print(f"  Time:    {elapsed:.1f}s")
            if warnings:
                print(f"  Warnings: {warnings}")
            print(f"  PASS")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
            failed += 1

        time.sleep(2)

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

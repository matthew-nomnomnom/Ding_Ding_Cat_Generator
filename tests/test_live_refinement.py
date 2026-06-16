"""Live integration test — uses real Gemini API.

Run: python tests/test_live_refinement.py
Requires: GEMINI_API_KEY env var set
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import yaml
from src.llm import RefinementEngine, RefinementError, RefinementBlockedError


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

    data_dir = os.path.join(base_dir, "data")
    engine = RefinementEngine(
        app_config_dir=data_dir,
        festivals_config=festivals,
        llm_settings=llm_settings,
        blocklist_config=blocklist,
    )

    tests = [
        ("mid-autumn", "cat eating mooncake with family under full moon"),
        ("chinese-new-year", "貓貓穿著紅色旗袍 拿著利是"),
        ("christmas", "dingding cat with santa hat holding a gift"),
        ("dragon-boat", "cat paddling a dragon boat"),
        ("halloween", "cat wearing a cute ghost costume"),
    ]

    passed = 0
    failed = 0
    total = len(tests)

    for festival_id, user_input in tests:
        print(f"\n--- Test: [{festival_id}] \"{user_input[:60]}{'...' if len(user_input)>60 else ''}\" ---")
        t0 = time.monotonic()
        try:
            result, warnings = engine.refine_prompt(festival_id, user_input)
            elapsed = (time.monotonic() - t0) * 1000

            checks = [
                ("prompt starts with dingdingcat", result.prompt.strip().lower().startswith("dingdingcat")),
                ("prompt is not empty", len(result.prompt) > 20),
                ("negative_prompt set", len(result.negative_prompt) > 5),
                ("suggested_props list", isinstance(result.suggested_props, list)),
                ("latency recorded", result.latency_ms > 0),
            ]
            all_ok = all(c[1] for c in checks)

            print(f"  Latency: {elapsed:.0f}ms (reported: {result.latency_ms}ms)")
            print(f"  Prompt:  {result.prompt[:120]}{'...' if len(result.prompt)>120 else ''}")
            print(f"  Negative: {result.negative_prompt[:100]}{'...' if len(result.negative_prompt)>100 else ''}")
            print(f"  Props:   {result.suggested_props}")
            print(f"  BG:      {result.suggested_background}")
            for name, ok in checks:
                print(f"  {'PASS' if ok else 'FAIL'}: {name}")
            if warnings:
                print(f"  Warnings: {warnings}")

            if all_ok:
                passed += 1
            else:
                failed += 1

        except RefinementBlockedError as e:
            print(f"  BLOCKED (expected for safety tests): {e}")
            passed += 1
        except RefinementError as e:
            print(f"  FAIL: {e}")
            failed += 1

        time.sleep(1)

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {total} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

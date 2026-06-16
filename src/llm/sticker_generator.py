"""Full sticker generation orchestrator.

Pipeline:
  User Input → LLM Refinement (Gemini Flash) → Scene Prompt →
  Nano Banana 2 (reference images + prompt) → Sticker PNG

Combines RefinementEngine + NanoBananaClient into a single call.
"""

import logging
import os
from pathlib import Path

from .cache_manager import RefinementResult
from .nano_banana_client import NanoBananaClient, NanoBananaError
from .refinement_engine import RefinementEngine, RefinementError

logger = logging.getLogger(__name__)


class StickerGeneratorError(Exception):
    pass


class StickerGenerator:
    def __init__(
        self,
        app_config_dir: str,
        festivals_config: dict,
        llm_settings: dict,
        blocklist_config: dict | None = None,
        ref_images_dir: str | None = None,
        output_dir: str | None = None,
    ):
        self._refinement = RefinementEngine(
            app_config_dir=app_config_dir,
            festivals_config=festivals_config,
            llm_settings=llm_settings,
            blocklist_config=blocklist_config,
        )

        api_key_env = (
            llm_settings.get("nano_banana", {})
            .get("api_key_env", "AI_GATEWAY_API_KEY")
        )
        api_key = os.environ.get(api_key_env, "")
        if not api_key:
            raise StickerGeneratorError(
                f"API key not found. Set {api_key_env} environment variable."
            )

        self._image_gen = NanoBananaClient(
            api_key=api_key,
            settings=llm_settings,
            ref_images_dir=ref_images_dir,
        )

        self._output_dir = output_dir or os.path.join(app_config_dir, "output", "stickers")

    def generate(
        self,
        festival_id: str,
        user_input: str,
        filename: str | None = None,
    ) -> tuple[str, RefinementResult, list[str]]:
        result, warnings = self._refinement.refine_prompt(festival_id, user_input)

        output_dir = os.path.join(self._output_dir, festival_id)
        os.makedirs(output_dir, exist_ok=True)

        if filename is None:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sticker_{festival_id}_{timestamp}.png"

        output_path = os.path.join(output_dir, filename)

        try:
            paths = self._image_gen.generate(
                prompt=result.prompt,
                output_path=output_path,
            )
        except NanoBananaError as e:
            raise StickerGeneratorError(f"Image generation failed: {e}") from e

        if not paths:
            raise StickerGeneratorError("No image was generated")

        self._refinement.update_with_images(result.prompt, paths)

        return paths[0], result, warnings

    def generate_batch(
        self,
        festival_id: str,
        user_input: str,
        count: int = 4,
    ) -> tuple[list[str], RefinementResult, list[str]]:
        result, warnings = self._refinement.refine_prompt(festival_id, user_input)

        output_dir = os.path.join(self._output_dir, festival_id)
        os.makedirs(output_dir, exist_ok=True)

        paths: list[str] = []
        for i in range(count):
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sticker_{festival_id}_{timestamp}_{i+1:02d}.png"
            output_path = os.path.join(output_dir, filename)

            try:
                batch_paths = self._image_gen.generate(
                    prompt=f"{result.prompt}\n\nGenerate variation {i+1} with slightly different composition.",
                    output_path=output_path,
                )
                paths.extend(batch_paths)
            except NanoBananaError as e:
                logger.warning("Batch generation %d/%d failed: %s", i + 1, count, e)

        if not paths:
            raise StickerGeneratorError("No images were generated in batch")

        self._refinement.update_with_images(result.prompt, paths)

        return paths, result, warnings


def find_reference_images_dir() -> str | None:
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "reference_images"),
        os.path.join(os.path.dirname(__file__), "..", "assets", "reference_images"),
        "assets/reference_images",
    ]
    for c in candidates:
        resolved = os.path.abspath(c)
        if os.path.isdir(resolved) and os.listdir(resolved):
            return resolved
    return None

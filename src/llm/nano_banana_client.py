"""Nano Banana 2 image generation client via Vercel AI Gateway.

Uses google/gemini-3.1-flash-image-preview (Nano Banana 2) with
reference images for character consistency. No LoRA training needed.

Reference images are sent as multimodal input alongside the scene prompt.
Output: base64 PNG images (512x512 or 1024x1024 depending on config).
"""

import base64
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class NanoBananaError(Exception):
    pass


class NanoBananaClient:
    def __init__(self, api_key: str, settings: dict, ref_images_dir: str | None = None):
        self._api_key = api_key
        self._model = settings.get("nano_banana", {}).get(
            "model", "google/gemini-3.1-flash-image-preview"
        )
        self._base_url = settings.get("nano_banana", {}).get(
            "base_url", "https://ai-gateway.vercel.sh/v1"
        )
        self._timeout = settings.get("nano_banana", {}).get("timeout_seconds", 60)

        self._ref_images_dir = ref_images_dir
        self._ref_images_cache: list[dict] | None = None

        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client

    def _load_reference_images(self) -> list[dict]:
        if self._ref_images_cache is not None:
            return self._ref_images_cache

        if not self._ref_images_dir or not os.path.isdir(self._ref_images_dir):
            self._ref_images_cache = []
            return self._ref_images_cache

        images = []
        for fname in sorted(os.listdir(self._ref_images_dir)):
            if not fname.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                continue
            fpath = os.path.join(self._ref_images_dir, fname)
            b64 = _image_to_base64(fpath)
            mime = "image/png" if fname.lower().endswith(".png") else "image/jpeg"
            images.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
            })

        self._ref_images_cache = images
        logger.info("Loaded %d reference images from %s", len(images), self._ref_images_dir)
        return self._ref_images_cache

    def generate(
        self,
        prompt: str,
        output_path: str | None = None,
    ) -> list[str]:
        client = self._get_client()
        refs = self._load_reference_images()

        content: list[dict] = []
        content.extend(refs)

        instruction = (
            f"{prompt}\n\n"
            "CRITICAL CHARACTER DETAILS:\n"
            "- This is 'Ding Ding Cat' (叮叮貓), the official mascot of Hong Kong Tramways\n"
            "- The mascot has the text 'DING DING' displayed on its head or body — this text "
            "MUST be present in the image exactly as shown in the reference images\n"
            "- The text must read 'DING DING' — do NOT change it to any other word\n"
            "- Copy the mascot's face, body, proportions, colors, and text faithfully "
            "from the reference images\n"
            "- Only change the outfit, props, and background to match the scene\n\n"
            "CRITICAL STYLE REQUIREMENTS:\n"
            "- 2D vector-style flat graphic illustration — NO 3D rendering, NO realistic shading, NO gradients\n"
            "- Clean geometric lines, solid flat colors, no textures\n"
            "- Cartoon sticker aesthetic suitable for WhatsApp\n"
            "- The character must look exactly like the reference images — same face, same body, same vector style\n"
            "- Do NOT add shadows, depth, lighting effects, or 3D elements\n"
            "- Keep the image simple and clean like a vector sticker graphic"
        )
        content.append({"type": "text", "text": instruction})

        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": content}],
                modalities=["image"],
                n=1,
            )
        except Exception as e:
            raise NanoBananaError(f"Image generation failed: {_safe_str(e)}") from e

        message = response.choices[0].message
        images_data = getattr(message, "images", None)
        if not images_data:
            raise NanoBananaError("No image returned in response")

        saved_paths: list[str] = []
        for i, img in enumerate(images_data):
            b64_data = img.get("image_url", {}).get("url", "")
            if not b64_data:
                continue
            if output_path:
                if len(images_data) > 1:
                    base, ext = os.path.splitext(output_path)
                    save_path = f"{base}_{i}{ext or '.png'}"
                else:
                    save_path = output_path
            else:
                save_path = f"sticker_{int(time.time())}_{i}.png"

            _save_base64_image(b64_data, save_path)
            saved_paths.append(save_path)

        return saved_paths


def _image_to_base64(filepath: str) -> str:
    with open(filepath, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _save_base64_image(data_url: str, output_path: str) -> None:
    if data_url.startswith("data:"):
        payload = data_url.split(",", 1)[1]
    else:
        payload = data_url
    raw = base64.b64decode(payload)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(raw)


def _safe_str(exc: Exception) -> str:
    return str(exc)[:300]

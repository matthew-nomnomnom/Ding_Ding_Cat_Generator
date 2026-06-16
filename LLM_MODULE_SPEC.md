# LLM Prompt Refinement Module — Complete Specification

> **Module owner**: Intern (LLM Part)  
> **Project**: Ding Ding Cat WhatsApp Sticker Generator  
> **LLM model**: Google Gemini 2.5 Flash  
> **Last updated**: 2026-06-16

---

## 1. Pipeline Flow

```
USER OPENS APP
      │
      ▼
┌─ Step 1: Festival Selector ────────────────────────────────────────┐
│  Dropdown with all 12 festivals from festivals.json.               │
│  Defaults to current/upcoming festival.                            │
│  Shows contextual placeholder hint:                                │
│    e.g. Mid-Autumn → "e.g. eating mooncakes, holding lanterns..."  │
└──────────────────────┬─────────────────────────────────────────────┘
                       │
                       ▼
┌─ Step 2: User Types Need ─────────────────────────────────────────┐
│  Free-text input box. Max 500 characters.                          │
│  Bilingual (en / zh / mixed) supported.                            │
│  No minimum length — even "新年" or "🎄" is valid.                  │
└──────────────────────┬─────────────────────────────────────────────┘
                       │
                       ▼
┌─ Step 3: Input Validation ─────────────────────────────────────────┐
│  • Trim whitespace                                                  │
│  • Length check: max 500 chars (truncate + warn if exceeded)       │
│  • Language detection: auto-detect en / zh / mixed / emoji          │
│  • Strict content filter: block politics, violence, NSFW, hate,     │
│    self-harm (via safety_blocklist.yaml)                            │
│  • Brand/copyright mention detection → warn user, allow to proceed  │
│  • Festival vs input mismatch detection → warn user, allow proceed  │
│  • Empty string → warn "No input provided", don't send to LLM      │
└──────────────────────┬─────────────────────────────────────────────┘
                       │ passes validation
                       ▼
┌─ Step 4: Cache Check ─────────────────────────────────────────────┐
│  cache_key = SHA256(festival_id + raw_input.strip().lower())       │
│  If cache_key exists AND TTL < 24 hours:                           │
│    → Return cached RefinementResult, skip to Step 8                │
│  Else:                                                              │
│    → Proceed to Step 5                                              │
└──────────────────────┬─────────────────────────────────────────────┘
                       │ cache miss
                       ▼
┌─ Step 5: Context Assembler ────────────────────────────────────────┐
│  Builds the structured prompt for Gemini.                           │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ SYSTEM PROMPT (from config/system_prompt.txt):                │   │
│  │                                                               │   │
│  │   You are a prompt engineer for Stable Diffusion. Your job    │   │
│  │   is to convert a user's vague description into a precise,    │   │
│  │   detailed image generation prompt.                           │   │
│  │                                                               │   │
│  │   CONTEXT:                                                    │   │
│  │   - Mascot: Ding Ding Cat (叮叮貓), HK Tramway mascot        │   │
│  │   - Trigger word: "dingdingcat" — MUST be first token         │   │
│  │   - Style: 3D cartoon, Pixar-like, adorable, high quality     │   │
│  │   - Default negative: blurry, deformed, extra limbs,          │   │
│  │     bad anatomy, watermark, text, nsfw, ugly, distorted       │   │
│  │   - Festival: {festival.name_en} ({festival.name_zh})         │   │
│  │   - Color palette: {festival.color_palette}                   │   │
│  │   - Available props: [{props from festivals.json}]            │   │
│  │   - Available backgrounds: [{backgrounds from festivals.json}]│   │
│  │                                                               │   │
│  │   RULES:                                                      │   │
│  │   - ALWAYS start the prompt with "dingdingcat"                │   │
│  │   - Include the festival context and color palette            │   │
│  │   - Pick 1-3 props from the available list                    │   │
│  │   - Pick 1 background from the available list                 │   │
│  │   - End with: "3D cartoon style, adorable, high quality"      │   │
│  │   - NEVER include: politics, violence, gore, NSFW,            │   │
│  │     religious proselytizing, hate speech, self-harm           │   │
│  │   - NEVER reference third-party IP (Mickey Mouse, Hello Kitty)│   │
│  │   - If user input is very short, creatively expand it         │   │
│  │     using the available festival props and backgrounds        │   │
│  │   - If user input is emoji-only, interpret the emojis         │   │
│  │   - Respond ONLY in valid JSON, no markdown, no explanation   │   │
│  │                                                               │   │
│  │   OUTPUT FORMAT (strict JSON):                                │   │
│  │   {                                                           │   │
│  │     "prompt": "dingdingcat ... [full SD prompt]",             │   │
│  │     "negative_prompt": "...",                                 │   │
│  │     "suggested_props": ["prop1", "prop2"],                    │   │
│  │     "suggested_background": "background name"                 │   │
│  │   }                                                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ USER CONTEXT (raw JSON dump of last 5 history records):       │   │
│  │                                                               │   │
│  │   PAST INTERACTIONS:                                          │   │
│  │   [                                                           │   │
│  │     {"raw_input": "...", "refined_prompt": "...",             │   │
│  │      "user_action": "approved"},                              │   │
│  │     ...                                                       │   │
│  │   ]                                                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ USER INPUT (delimited to prevent prompt injection):           │   │
│  │                                                               │   │
│  │   <USER_INPUT>                                                │   │
│  │   {raw_input}                                                 │   │
│  │   </USER_INPUT>                                               │   │
│  └─────────────────────────────────────────────────────────────┘   │
└──────────────────────┬─────────────────────────────────────────────┘
                       │
                       ▼
┌─ Step 6: Gemini API Call ─────────────────────────────────────────┐
│  • Model: gemini-2.5-flash                                         │
│  • Temperature: 0.3                                                │
│  • Response format: JSON mode                                      │
│  • Timeout: 15 seconds                                             │
│  • Retry: 3 attempts with exponential backoff (2s → 4s → 8s)      │
│  • Circuit breaker: halt after 5 failures in 60s window            │
│    (auto-reset after 5 minutes of no failures)                     │
│  • Log latency and token counts for every call                     │
└──────────────────────┬─────────────────────────────────────────────┘
                       │
                       ▼
┌─ Step 7: Output Validation & Safety ──────────────────────────────┐
│                                                                     │
│  Structural checks:                                                 │
│  • Parse JSON → if malformed, retry once with explicit "You MUST   │
│    return valid JSON" instruction. If still fails, use raw text     │
│    stripped of markdown as the prompt.                              │
│  • Required field: "prompt" must exist and be non-empty             │
│  • Optional fields: "negative_prompt", "suggested_props",           │
│    "suggested_background" — fill defaults if missing                │
│  • Trigger word check: if "dingdingcat" not present, PREPEND it    │
│    to the prompt field                                              │
│                                                                     │
│  Safety checks (2-layer):                                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Layer 1 — Keyword Blocklist (safety_blocklist.yaml):          │   │
│  │   Scan entire output against blocklist. Categories:           │   │
│  │   - politics (keywords, party names, sensitive terms)         │   │
│  │   - violence_gore (kill, blood, weapons, etc.)                │   │
│  │   - nsfw_adult (sexual terms, nudity references)              │   │
│  │   - hate_speech (slurs, discriminatory terms)                 │   │
│  │   - self_harm (suicide, self-injury references)               │   │
│  │   If any keyword matches → BLOCK, re-prompt LLM with stronger │   │
│  │   safety instruction, log the blocked output.                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Layer 2 — LLM Safety Classifier (if Layer 1 passes):          │   │
│  │   Second Gemini call with safety classifier system prompt.    │   │
│  │   Input: the refined prompt and negative_prompt.              │   │
│  │   Output: {"safe": true/false, "reason": "..."}               │   │
│  │   If unsafe → BLOCK, re-prompt refinement LLM.                │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  On BLOCK:                                                          │
│  • Show user: "Your request couldn't be processed due to content   │
│    safety guidelines. Please rephrase your request."                │
│  • Auto-retry refinement once with stronger safety instructions     │
│  • If still blocked → permanent error, user must re-input           │
│  • Log every blocked output with reason and input                   │
└──────────────────────┬─────────────────────────────────────────────┘
                       │ passes all checks
                       ▼
┌─ Step 8: User Approval Gate ──────────────────────────────────────┐
│  Display to user in editable boxes:                                │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Prompt:                                                       │   │
│  │ ┌───────────────────────────────────────────────────────────┐│   │
│  │ │ dingdingcat holding a mooncake, wearing traditional Tang   ││   │
│  │ │ suit, lanterns in background, full moon, warm orange tones,││   │
│  │ │ 3D cartoon style, adorable, high quality                   ││   │
│  │ └───────────────────────────────────────────────────────────┘│   │
│  │                                                               │   │
│  │ Negative Prompt:                                              │   │
│  │ ┌───────────────────────────────────────────────────────────┐│   │
│  │ │ blurry, low quality, deformed, extra limbs, bad anatomy... ││   │
│  │ └───────────────────────────────────────────────────────────┘│   │
│  │                                                               │   │
│  │ Suggested Props: [mooncake] [lantern] [tea cup]               │   │
│  │ Suggested Background: full moon night                         │   │
│  │                                                               │   │
│  │  [✅ Approve & Generate]  [✏️ Edit & Generate]                │   │
│  │  [🔄 Try Again (re-refine)]                                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  User actions:                                                      │
│  • Approve → mark user_action="approved", proceed to Step 9        │
│  • Edit → mark user_action="edited", save user_edited_prompt,      │
│    use edited version. If >50% changed, log for review              │
│  • Try Again → mark user_action="rejected", loop back to Step 5    │
│    with additional context: "User rejected previous suggestion.     │
│    Please try a different approach."                                │
└──────────────────────┬─────────────────────────────────────────────┘
                       │ approved / edited
                       ▼
┌─ Step 9: Persist & Forward ───────────────────────────────────────┐
│                                                                     │
│  9a. Atomic write to history JSON:                                  │
│      • Write to temp file first, then os.replace()                  │
│      • Append new RefinementRecord to array                         │
│      • If >200 records, remove oldest, archive to .archive.json     │
│      • Catch all write errors, log, don't block forward flow        │
│                                                                     │
│  9b. Add to refinement cache:                                       │
│      • Key: SHA256(festival_id + raw_input.strip().lower())         │
│      • Value: full RefinementResult                                 │
│      • TTL: 24 hours (checked on every cache lookup)                │
│      • In-memory dict for performance, no file I/O for cache        │
│                                                                     │
│  9c. Forward to Replicate image generation:                         │
│      • Pass "prompt" and "negative_prompt" to replicate API         │
│      • On image generation complete, update record with image_urls  │
│      • Show "Generate More" button → same prompt, different seed    │
│        (no LLM re-call needed)                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Decision Table

| # | Category | Decision |
|---|----------|----------|
| 1 | LLM model | Google Gemini 2.5 Flash |
| 2 | System prompt | External file `config/system_prompt.txt` |
| 3 | Output format | Strict JSON: `{prompt, negative_prompt, suggested_props, suggested_background}` |
| 4 | Past records context | Last 5 records, raw JSON dump |
| 5 | Context format | System prompt + past records JSON + delimited user input |
| 6 | History file location | OS app config directory (macOS: `~/Library/Application Support/DingDingStickerGen/`, Windows: `%APPDATA%\DingDingStickerGen\`) |
| 7 | History file strategy | One file `refinement_history.json`, capped at 200 records |
| 8 | History overflow | Auto-prune oldest records, archive to `.archive.json` |
| 9 | History write | Atomic: write to temp file → `os.replace()` |
| 10 | Schema versioning | `schema_version: 1` field in every record |
| 11 | Input max length | 500 characters (truncate with warning if exceeded) |
| 12 | Input min length | None — accept any length including 1-character Chinese |
| 13 | Language support | Bilingual (en/zh), auto-detect |
| 14 | Input content filter | Strict: block politics, violence, NSFW, hate, self-harm |
| 15 | Brand mention | Detect, warn user of IP risk, allow to proceed |
| 16 | Festival selection | Explicit dropdown first, defaults to current/upcoming festival |
| 17 | Placeholder hints | Festival-specific contextual hints in input box |
| 18 | Festival/input mismatch | Warn user, allow to proceed |
| 19 | Emoji-only input | Pass to LLM with interpretation instruction |
| 20 | Duplicate detection | `SHA256(festival_id + raw_input.strip().lower())` |
| 21 | Refinement cache | In-memory, 24-hour TTL |
| 22 | Safety check | 2-layer: keyword blocklist → LLM safety classifier |
| 23 | Safety blocklist file | `config/safety_blocklist.yaml` |
| 24 | Blocked output handling | Show user message + auto-retry refinement once with stronger instructions |
| 25 | Trigger word enforcement | ALWAYS prepend "dingdingcat" — mandatory regardless of user input |
| 26 | Approval gate | Show refined prompt, user can Approve / Edit / Try Again |
| 27 | User edits | Use directly if edited, log as "edited" |
| 28 | Rejected prompts | Saved to history marked as "rejected" |
| 29 | LLM retry on failure | 3 attempts, exponential backoff (2s → 4s → 8s) |
| 30 | Malformed JSON output | Retry once with explicit instruction, fallback to raw text |
| 31 | Circuit breaker | Halt after 5 failures in 60s window, reset after 5 min clean |
| 32 | Error logging | JSON lines format → `{app_config_dir}/logs/refinement_errors.jsonl` |
| 33 | "Generate More" | Same refined prompt, different seed, no LLM re-call |

---

## 3. Data Schemas

### 3.1 RefinementRecord (stored in history JSON)

```json
{
  "id": "a1b2c3d4-...",
  "timestamp": "2026-06-16T14:30:00+08:00",
  "festival_id": "mid-autumn",
  "raw_input": "I want the cat to hold a mooncake",
  "detected_language": "en",
  "refined_prompt": "dingdingcat holding a mooncake, traditional Tang suit, ...",
  "negative_prompt": "blurry, low quality, deformed, extra limbs, ...",
  "suggested_props": ["mooncake", "lantern"],
  "suggested_background": "full moon night",
  "user_action": "approved",
  "user_edited_prompt": null,
  "image_urls": ["https://replicate.delivery/..."],
  "generation_params": {
    "seed": 12345,
    "num_inference_steps": 28,
    "guidance_scale": 7.5,
    "num_outputs": 4
  },
  "llm_model": "gemini-2.5-flash",
  "refinement_latency_ms": 1234,
  "schema_version": 1
}
```

### 3.2 RefinementResult (internal, in-memory)

```python
@dataclass
class RefinementResult:
    prompt: str
    negative_prompt: str
    suggested_props: list[str]
    suggested_background: str
    raw_llm_response: str     # original LLM response (for debugging)
    was_cached: bool          # True if from cache, False if fresh
    latency_ms: int           # LLM call duration (0 if cached)
```

### 3.3 ValidationResult (input validation output)

```python
@dataclass
class ValidationResult:
    is_valid: bool
    sanitized_input: str      # trimmed, truncated if needed
    detected_language: str    # "en" | "zh" | "mixed" | "emoji"
    warnings: list[str]       # non-blocking warnings to show user
    errors: list[str]         # blocking errors (is_valid=False if non-empty)
```

### 3.4 SafetyCheckResult (safety filter output)

```python
@dataclass
class SafetyCheckResult:
    is_safe: bool
    layer: str                # "blocklist" | "llm_classifier" | "both"
    blocked_category: str | None
    blocked_keyword: str | None
    reason: str | None
```

### 3.5 CacheEntry

```python
@dataclass
class CacheEntry:
    result: RefinementResult
    created_at: float         # time.time() epoch
    expires_at: float         # created_at + 86400 (24h)
```

---

## 4. File Structure

```
dingding-sticker-gen/
│
├── src/
│   ├── llm/                          ← NEW MODULE (your part)
│   │   ├── __init__.py
│   │   ├── refinement_engine.py      ← Orchestrator: ties all steps together
│   │   ├── input_validator.py        ← Step 3: validation, language detect, content filter
│   │   ├── context_assembler.py      ← Step 5: builds Gemini prompt with festival + history
│   │   ├── gemini_client.py          ← Step 6: Gemini API wrapper, retry, circuit breaker
│   │   ├── safety_filter.py          ← Step 7: 2-layer safety check
│   │   ├── output_parser.py          ← Step 7: JSON parsing, trigger word enforcement
│   │   ├── history_manager.py        ← Step 9a: atomic JSON read/write, pruning
│   │   └── cache_manager.py          ← Step 4/9b: 24h TTL in-memory cache
│   │
│   ├── generation/                   ← EXISTING (other intern's part)
│   │   ├── replicate_api.py
│   │   ├── prompt_builder.py
│   │   └── lora_manager.py
│   │
│   ├── processing/                   ← EXISTING (other intern's part)
│   │   ├── background.py
│   │   ├── webp_converter.py
│   │   └── packager.py
│   │
│   └── utils/
│       └── config_loader.py          ← EXISTING (shared)
│
├── config/
│   ├── festivals.json                ← EXISTING
│   ├── settings.yaml                 ← EXISTING
│   ├── system_prompt.txt             ← NEW: Gemini system prompt (version-controlled)
│   ├── safety_blocklist.yaml         ← NEW: forbidden keywords/patterns
│   └── llm_settings.yaml             ← NEW: model, temperature, retry, circuit breaker
│
├── logs/                             ← NEW (auto-created at runtime)
│   └── refinement_errors.jsonl       ← Structured error log, JSON lines
│
└── tests/
    ├── test_refinement_engine.py     ← NEW
    ├── test_input_validator.py       ← NEW
    ├── test_safety_filter.py         ← NEW
    ├── test_history_manager.py       ← NEW
    └── test_cache_manager.py         ← NEW
```

---

## 5. Config File Specifications

### 5.1 `config/llm_settings.yaml`

```yaml
# Gemini API configuration
gemini:
  model: "gemini-2.5-flash"
  temperature: 0.3
  max_output_tokens: 512
  timeout_seconds: 15
  api_key_env: "GEMINI_API_KEY"  # environment variable name

# Retry configuration
retry:
  max_attempts: 3
  backoff_seconds: [2, 4, 8]

# Circuit breaker
circuit_breaker:
  failure_threshold: 5
  window_seconds: 60
  reset_after_seconds: 300  # 5 minutes

# Safety
safety:
  blocklist_file: "config/safety_blocklist.yaml"
  enable_llm_classifier: true
  classifier_model: "gemini-2.5-flash"

# History
history:
  max_records: 200
  context_record_count: 5
  archive_overflow: true

# Cache
cache:
  ttl_seconds: 86400  # 24 hours
  max_entries: 1000
```

### 5.2 `config/safety_blocklist.yaml`

```yaml
# Content categories and blocked keywords/patterns
# Case-insensitive matching. Substring matching (e.g., "kill" matches "killing").

categories:
  politics:
    keywords:
      - protest
      - riot
      - revolution
      - regime
      - propaganda
      # Add HK-specific terms as needed by compliance team
    description: "Political imagery and slogans"

  violence_gore:
    keywords:
      - kill
      - murder
      - blood
      - gore
      - weapon
      - gun
      - knife
      - dead
      - corpse
      - zombie
      - horror
    description: "Violence, gore, weapons"
    note: "Allow mild Halloween spookiness when festival_id=halloween"

  nsfw_adult:
    keywords:
      - nude
      - naked
      - sex
      - porn
      - erotic
      - strip
    description: "Adult and explicit content"

  hate_speech:
    keywords:
      - slur
      - racist
      - discriminatory
    description: "Hate speech and discrimination"

  self_harm:
    keywords:
      - suicide
      - self-harm
      - cut myself
      - die
    description: "Self-harm and suicide references"

# Context-aware overrides
overrides:
  halloween:
    allow_keywords: ["ghost", "witch", "vampire", "spooky", "cute monster"]
    still_block: ["gore", "horror", "blood", "dead", "corpse"]
```

### 5.3 `config/system_prompt.txt`

```text
You are a prompt engineer for Stable Diffusion and FLUX image generation models.
Your job is to convert a user's vague description into a precise, detailed
image generation prompt for a WhatsApp sticker.

<MASCOT_CONTEXT>
The mascot is "Ding Ding Cat" (叮叮貓), the official mascot of Hong Kong Tramways.
The trigger word "dingdingcat" activates a custom LoRA model that ensures the
cat looks consistent across all images.

IMPORTANT: EVERY prompt you generate MUST start with the word "dingdingcat".
This is mandatory and non-negotiable.
</MASCOT_CONTEXT>

<STYLE_DIRECTIVE>
All stickers must follow this style:
- 3D cartoon rendering (Pixar-like)
- Adorable and cute expression
- High quality, clean lines
- Vibrant but harmonious colors
- Suitable for WhatsApp sticker format (512x512 WebP)
End every prompt with: "3D cartoon style, adorable, high quality"
</STYLE_DIRECTIVE>

<DEFAULT_NEGATIVE_PROMPT>
Always include this base negative prompt, adding festival-specific terms as needed:
"blurry, low quality, deformed, extra limbs, bad anatomy, watermark, text, nsfw,
ugly, distorted face, mutated, poorly drawn, out of frame, disfigured, bad proportions,
gross proportions, duplicate, multiple cats"
</DEFAULT_NEGATIVE_PROMPT>

<FESTIVAL_CONTEXT>
Current festival: {{festival_name_en}} ({{festival_name_zh}})
Color palette: {{festival_color_palette}}
Available props to choose from: {{festival_props}}
Available backgrounds to choose from: {{festival_backgrounds}}
</FESTIVAL_CONTEXT>

<RULES>
1. ALWAYS start the prompt with "dingdingcat"
2. Incorporate the festival's color palette into the description
3. Select 1-3 props from the available props list for this festival
4. Select 1 background from the available backgrounds list
5. End with "3D cartoon style, adorable, high quality"
6. If user input is very short or vague, creatively expand it using the festival context
7. If user input contains emojis, interpret them as the user's intent
8. NEVER include politically sensitive content, violence, gore, or adult material
9. NEVER reference trademarked characters (Disney, Sanrio, Pokémon, etc.)
10. Do NOT add text or words to the image (no speech bubbles, no labels)
11. Respond ONLY with valid JSON. No markdown, no explanations, no code blocks.
</RULES>

<OUTPUT_FORMAT>
You MUST respond with ONLY a JSON object in this exact structure:
{
  "prompt": "dingdingcat ... [full image generation prompt]",
  "negative_prompt": "... [image-specific negative additions + default base]",
  "suggested_props": ["prop1", "prop2"],
  "suggested_background": "background name"
}

Do not include any text before or after the JSON.
Do not wrap the JSON in markdown code blocks.
</OUTPUT_FORMAT>

<PAST_INTERACTIONS>
Here are 5 recent successful prompt refinements for context.
Use these to understand the expected style and quality level:
{{past_interactions_json}}
</PAST_INTERACTIONS>

<USER_INPUT>
{{user_input}}
</USER_INPUT>
```

---

## 6. API Contracts (Between Modules)

### 6.1 `refinement_engine.py` — main entry point

```python
def refine_prompt(
    festival_id: str,
    user_input: str,
    festivals_config: dict,
    llm_settings: dict,
) -> tuple[RefinementResult, list[str]]:
    """
    Main orchestrator. Called by the UI when user clicks "Refine" or "Generate".

    Args:
        festival_id: e.g. "mid-autumn"
        user_input: raw text from the input box
        festivals_config: parsed festivals.json
        llm_settings: parsed llm_settings.yaml

    Returns:
        (RefinementResult, warnings_list)
        Raises RefinementError on unrecoverable failure.
    """
```

### 6.2 `input_validator.py`

```python
def validate_input(
    raw_input: str,
    festival_id: str,
    festivals_config: dict,
    blocklist_config: dict,
) -> ValidationResult:
    """
    Validate and sanitize user input before sending to LLM.
    Checks: length, language, content policy, festival mismatch, brand mentions.
    """

def detect_language(text: str) -> str:
    """Returns 'en', 'zh', 'mixed', or 'emoji'."""

def check_festival_mismatch(
    user_input: str, festival_id: str, festivals_config: dict
) -> bool:
    """Returns True if input keywords contradict selected festival."""
```

### 6.3 `context_assembler.py`

```python
def build_system_prompt(
    festival_id: str,
    festivals_config: dict,
    system_prompt_template: str,
) -> str:
    """Render the system prompt with festival-specific values."""

def build_user_context(
    past_records: list[dict],
    user_input: str,
) -> str:
    """Assemble the past-interactions and delimited user input sections."""

def assemble_full_prompt(
    festival_id: str,
    user_input: str,
    festivals_config: dict,
    system_prompt_template: str,
    past_records: list[dict],
) -> str:
    """Combine system prompt + past records + user input into final Gemini prompt."""
```

### 6.4 `gemini_client.py`

```python
class GeminiClient:
    def __init__(self, api_key: str, settings: dict): ...

    def generate(
        self, prompt: str, temperature: float = 0.3
    ) -> str:
        """
        Send prompt to Gemini, return raw text response.
        Handles retry + circuit breaker internally.
        Raises GeminiError on failure after all retries exhausted.
        """

    def generate_json(
        self, prompt: str, temperature: float = 0.3
    ) -> dict:
        """
        Same as generate() but enforces JSON response mode.
        Returns parsed dict.
        """

    def is_circuit_open(self) -> bool: ...
    def reset_circuit(self) -> None: ...
```

### 6.5 `safety_filter.py`

```python
def check_blocklist(prompt: str, blocklist_config: dict, festival_id: str) -> SafetyCheckResult:
    """Layer 1: keyword-based safety check."""

def check_with_classifier(
    prompt: str, gemini_client: GeminiClient
) -> SafetyCheckResult:
    """Layer 2: LLM-based safety classification."""

def full_safety_check(
    prompt: str,
    negative_prompt: str,
    blocklist_config: dict,
    gemini_client: GeminiClient,
    enable_classifier: bool,
    festival_id: str,
) -> SafetyCheckResult:
    """Run both layers. Returns first failure or passes."""
```

### 6.6 `output_parser.py`

```python
def parse_llm_output(raw_response: str) -> RefinementResult:
    """
    Parse Gemini JSON output into RefinementResult.
    Handles: valid JSON, malformed JSON (retry flag),
    markdown-wrapped JSON, and raw text fallback.
    """

def enforce_trigger_word(prompt: str) -> str:
    """
    Ensure "dingdingcat" is present at the start of the prompt.
    If missing, prepend it. If present elsewhere, move to start.
    """

def parse_with_fallback(raw_response: str) -> RefinementResult:
    """
    Try JSON parse → if fails, extract prompt from raw text.
    Always enforce trigger word.
    """
```

### 6.7 `history_manager.py`

```python
class HistoryManager:
    def __init__(self, app_config_dir: str, max_records: int = 200): ...

    def load_history(self) -> list[dict]:
        """Load all records from refinement_history.json."""

    def get_recent(self, count: int = 5) -> list[dict]:
        """Get the N most recent records for context assembly."""

    def add_record(self, record: dict) -> None:
        """
        Atomic append to history file.
        Uses temp file + os.replace() for crash safety.
        Auto-prunes if > max_records.
        """

    def archive_old_records(self) -> None:
        """Move records beyond max_records limit to .archive.json."""

    def _atomic_write(self, data: list[dict]) -> None:
        """Write to temp file, then os.replace() for atomicity."""

    def get_cache_key(self, festival_id: str, raw_input: str) -> str:
        """Generate SHA256 key for cache/dedup lookup."""
```

### 6.8 `cache_manager.py`

```python
class CacheManager:
    def __init__(self, ttl_seconds: int = 86400, max_entries: int = 1000): ...

    def get(self, cache_key: str) -> RefinementResult | None:
        """Return cached result if exists and not expired. None otherwise."""

    def set(self, cache_key: str, result: RefinementResult) -> None:
        """Store result in cache. Auto-evicts oldest if over max_entries."""

    def clear_expired(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""

    def clear_all(self) -> None:
        """Wipe entire cache."""
```

---

## 7. Error Handling Strategy

| Error Type | Handling |
|------------|----------|
| Empty user input | Warn user, don't call LLM, return immediately |
| Input > 500 chars | Truncate with warning, proceed |
| Input fails content filter | Show specific blocked category, ask to rephrase |
| LLM API timeout | Retry (max 3, backoff 2s/4s/8s). On final failure → show error |
| LLM API rate limited | Wait for Retry-After header, retry once |
| LLM API auth error | Show "Check Gemini API key in settings" |
| Gemini returns non-JSON | Retry once with explicit instruction. Fallback: strip markdown, use raw text as prompt |
| JSON parse OK but missing "prompt" field | Retry once. Fallback: use first text-like field |
| Missing "dingdingcat" in output | AUTO-PREPEND. Log warning. Proceed. |
| Keyword blocklist hit | Log, retry refinement once with stronger safety instruction |
| LLM safety classifier flags | Log, retry refinement once with stronger safety instruction |
| Blocked after retry | Permanent error. Show user message. Must re-input. |
| History file corrupted | Backup corrupted file, create fresh, log error, continue |
| History file disk full | Log error, skip persistence gracefully, continue |
| Cache memory full (>1000 entries) | Evict oldest entries |
| Circuit breaker open | Show "Service temporarily unavailable. Please wait X seconds." |

---

## 8. Implementation Order

Priority order for building files (each step is independently testable):

```
1. history_manager.py     ← Foundation (everything reads/writes history)
2. cache_manager.py       ← Simple, no dependencies
3. input_validator.py     ← Gatekeeper, depends on blocklist config
4. output_parser.py       ← JSON parsing + trigger word enforcement
5. gemini_client.py       ← API wrapper with retry + circuit breaker
6. context_assembler.py   ← Builds prompts from templates + festival data
7. safety_filter.py       ← 2-layer safety, depends on gemini_client
8. refinement_engine.py   ← Orchestrator, depends on ALL above
```

---

*Specification complete. Ready for implementation.*

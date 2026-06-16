"""Context assembler — builds the structured Gemini prompt.

Injects festival data from festivals.json, past interaction records,
and user input into the system prompt template.
"""

import json


def build_system_prompt(
    festival_id: str,
    festivals_config: dict,
    system_prompt_template: str,
) -> str:

    festival = _find_festival(festival_id, festivals_config)
    if festival is None:
        raise ValueError(f"Festival '{festival_id}' not found in festivals.json")

    all_props: list[str] = []
    all_backgrounds: list[str] = []
    for template in festival.get("templates", []):
        for prop in template.get("props", []):
            if prop not in all_props:
                all_props.append(prop)
        for bg in template.get("backgrounds", []):
            if bg not in all_backgrounds:
                all_backgrounds.append(bg)

    mascot = festivals_config.get("mascot", {})
    rendered = system_prompt_template.replace(
        "{{festival_name_en}}", festival.get("name_en", festival_id)
    )
    rendered = rendered.replace(
        "{{festival_name_zh}}", festival.get("name_zh", festival_id)
    )
    rendered = rendered.replace(
        "{{festival_color_palette}}",
        festival.get("color_palette", "vibrant, festive"),
    )
    rendered = rendered.replace(
        "{{festival_props}}", _format_list(all_props)
    )
    rendered = rendered.replace(
        "{{festival_backgrounds}}", _format_list(all_backgrounds)
    )

    return rendered


def build_user_context(
    past_records: list[dict],
    user_input: str,
) -> str:
    past_json = json.dumps(past_records, ensure_ascii=False, indent=2)
    return f"<USER_INPUT>\n{user_input}\n</USER_INPUT>"


def assemble_full_prompt(
    festival_id: str,
    user_input: str,
    festivals_config: dict,
    system_prompt_template: str,
    past_records: list[dict],
) -> str:
    system_part = build_system_prompt(
        festival_id, festivals_config, system_prompt_template
    )

    past_json = json.dumps(past_records, ensure_ascii=False, indent=2)

    full_prompt = system_part.replace(
        "{{past_interactions_json}}",
        past_json if past_records else "[] (no past interactions available)",
    )
    full_prompt = full_prompt.replace("{{user_input}}", user_input)

    return full_prompt


def _find_festival(festival_id: str, config: dict) -> dict | None:
    for festival in config.get("festivals", []):
        if festival.get("id") == festival_id:
            return festival
    return None


def _format_list(items: list[str]) -> str:
    if not items:
        return "[none specified]"
    return ", ".join(f'"{item}"' for item in items)

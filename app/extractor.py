import base64
import json
import mimetypes
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

FIELDS = ["first_name", "last_name", "designation", "email", "phone", "location"]

PROMPT = """You are reading a business card image.
Extract the details and reply with ONLY a JSON object, no explanation, no markdown.
Use exactly these keys:
first_name, last_name, designation, email, phone, location

Rules:
- Split the person's full name into first_name and last_name. Leave out titles like Mr, Dr, Prof.
- If there is only one name, put it in first_name and use null for last_name.
- designation is the job title or role (e.g. "Marketing Manager").
- phone: if there are several numbers, join them with ", ".
- location is the address as printed on the card. If only a city/country is shown, use that.
- If a field is not on the card, use null.
- Copy text exactly as printed. Do not guess or invent anything."""

_client = None


def _get_client():
    global _client
    if _client is None:
        base_url = os.getenv("VLM_BASE_URL")
        api_key = os.getenv("VLM_API_KEY")
        if not base_url or not api_key or not os.getenv("VLM_MODEL"):
            raise RuntimeError("VLM_BASE_URL, VLM_API_KEY and VLM_MODEL must be set in .env")
        _client = OpenAI(base_url=base_url, api_key=api_key, timeout=90)
    return _client


def image_to_data_url(path: str) -> str:
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def parse_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)  # drop reasoning, if any
    text = re.sub(r"```(?:json)?", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON found in model output: {text[:200]}")
    return json.loads(text[start : end + 1])


def clean(data: dict) -> dict:
    out = {}
    for key in FIELDS:
        value = data.get(key)
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        if isinstance(value, str):
            value = value.strip()
            if value.lower() in ("", "null", "none", "n/a"):
                value = None
        out[key] = value
    return out


def extract_card(image_path: str):
    """Returns (cleaned_fields_dict, raw_model_text)."""
    response = _get_client().chat.completions.create(
        model=os.getenv("VLM_MODEL"),
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_to_data_url(image_path)}},
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
    )
    raw = response.choices[0].message.content or ""
    return clean(parse_json(raw)), raw
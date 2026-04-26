import json
import os
import re
from pathlib import Path
from typing import Dict, List, Literal, Optional
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_env_file() -> None:
    env_path = Path(__file__).resolve().with_name(".env")
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()
API_KEY = os.getenv("OPENROUTER_API_KEY", "")

SESSION_MEMORY: Dict[str, List[dict]] = {}
MAX_MEMORY_MESSAGES = 6


class Ingredient(BaseModel):
    name: str


class RequestModel(BaseModel):
    ingredients: List[Ingredient] = []
    ingredients_text: str = ""
    image_url: Optional[str] = None
    image_data_url: Optional[str] = None
    session_id: str = "default"
    creativity: Literal["strict", "balanced", "creative"] = "balanced"
    response_mode: Literal["concise", "detailed"] = "concise"


def _extract_json_payload(text: str):
    cleaned = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()
    return json.loads(cleaned)


def _normalize_status(status: str) -> str:
    normalized = (status or "").strip().lower().replace("_", " ")
    if normalized in {"available", "yes", "in stock", "have", "on hand"}:
        return "available"
    return "not available"


def _parse_ingredient_text(value: str) -> List[str]:
    if not value.strip():
        return []
    parts = [p.strip() for p in re.split(r",|\n", value) if p.strip()]
    return parts


def _build_system_prompt(creativity: str, response_mode: str) -> str:
    creativity_map = {
        "strict": "Stay practical and conservative. Prefer familiar recipes.",
        "balanced": "Balance reliability and creativity.",
        "creative": "Be inventive and chef-like while still realistic.",
    }
    detail_map = {
        "concise": "Keep steps compact (5-7 short steps per meal).",
        "detailed": "Give more cooking detail (7-10 clear steps per meal).",
    }

    return f"""
You are AI Chef Assistant. Speak like a real friendly chef.
Guide the user step-by-step to a meal decision and never skip key cooking steps.
Use previous conversation context when provided.

Style controls:
- Creativity: {creativity_map[creativity]}
- Response detail: {detail_map[response_mode]}

Return ONLY valid JSON as a list of meals. No markdown, no explanation text.
Each meal item MUST have exactly these keys:
- meal: string
- cooking_time: string
- servings: string
- ingredients: list of objects with keys:
  - name: string
  - status: "available" or "not available"
- instructions: list of strings in strict order step-by-step (no missing steps)

Rules:
- Use user-provided ingredients as "available".
- If extra ingredient is needed and not explicitly provided, mark as "not available".
- Provide 1 to 3 meal options.
""".strip()


def _sanitize_meals(payload, available_names: set) -> List[dict]:
    if not isinstance(payload, list):
        raise HTTPException(status_code=502, detail="AI response must be a list of meals.")

    sanitized: List[dict] = []
    for raw_meal in payload[:3]:
        if not isinstance(raw_meal, dict):
            continue

        ingredients = raw_meal.get("ingredients", [])
        normalized_ingredients = []
        for item in ingredients:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            status = _normalize_status(str(item.get("status", "")))
            if name.lower() in available_names:
                status = "available"
            normalized_ingredients.append({"name": name, "status": status})

        instructions = raw_meal.get("instructions", [])
        normalized_steps = []
        for idx, step in enumerate(instructions, start=1):
            step_text = str(step).strip()
            if not step_text:
                continue
            if not re.match(r"^step\s+\d+", step_text, flags=re.IGNORECASE):
                step_text = f"Step {idx}: {step_text}"
            normalized_steps.append(step_text)

        sanitized.append(
            {
                "meal": str(raw_meal.get("meal", "Untitled Meal")).strip() or "Untitled Meal",
                "cooking_time": str(raw_meal.get("cooking_time", "N/A")).strip() or "N/A",
                "servings": str(raw_meal.get("servings", "N/A")).strip() or "N/A",
                "ingredients": normalized_ingredients,
                "instructions": normalized_steps,
            }
        )

    if not sanitized:
        raise HTTPException(status_code=502, detail="AI did not return valid meal data.")

    return sanitized


def _fallback_meals(ingredients: List[str], creativity: str, response_mode: str) -> List[dict]:
    base = ingredients[:]
    while len(base) < 3:
        base.append("salt")

    primary = ingredients[0] if ingredients else "mixed vegetables"
    secondary = ingredients[1] if len(ingredients) > 1 else "rice"

    detailed_steps = [
        f"Step 1: Prepare all ingredients: {', '.join(ingredients) if ingredients else 'whatever is available'}.",
        f"Step 2: Heat a pan and start cooking {primary} with a little oil.",
        f"Step 3: Add {secondary} or a suitable base ingredient and stir well.",
        "Step 4: Season gradually, tasting as you go so the flavor stays balanced.",
        "Step 5: Finish the dish, plate it neatly, and serve while hot.",
    ]

    if response_mode == "detailed":
        detailed_steps.insert(2, "Step 3: Add aromatics like onion or garlic if available for better flavor.")
        detailed_steps.append("Step 6: Garnish if you have fresh herbs, then serve immediately.")

    if creativity == "creative":
        meal_name = f"Chef's Signature {primary.title()} Bowl"
    elif creativity == "strict":
        meal_name = f"Simple {primary.title()} Plate"
    else:
        meal_name = f"{primary.title()} Comfort Bowl"

    return [
        {
            "meal": meal_name,
            "cooking_time": "25 minutes",
            "servings": "2",
            "ingredients": [
                {"name": item, "status": "available" if item.lower() in {i.lower() for i in ingredients} else "not available"}
                for item in [primary, secondary, "salt", "pepper", "oil"]
            ],
            "instructions": detailed_steps if response_mode == "detailed" else detailed_steps[:5],
        }
    ]


@app.post("/generate")
def generate(req: RequestModel):
    provided_names = [i.name.strip() for i in req.ingredients if i.name.strip()]
    text_names = _parse_ingredient_text(req.ingredients_text)

    seen = set()
    cleaned_ingredients = []
    for item in provided_names + text_names:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            cleaned_ingredients.append(item)

    if not cleaned_ingredients and not req.image_url and not req.image_data_url:
        raise HTTPException(
            status_code=400,
            detail="Provide ingredients text/list or an ingredient image.",
        )

    memory = SESSION_MEMORY.get(req.session_id, [])

    user_text = (
        "User request:\n"
        f"- Ingredients from text/list: {', '.join(cleaned_ingredients) if cleaned_ingredients else 'None explicitly listed'}\n"
        "- Task: analyze available food, suggest meal options, and guide cooking steps clearly."
    )

    user_content = [{"type": "text", "text": user_text}]
    if req.image_data_url:
        user_content.append({"type": "image_url", "image_url": {"url": req.image_data_url}})
    elif req.image_url:
        user_content.append({"type": "image_url", "image_url": {"url": req.image_url}})

    messages = [{"role": "system", "content": _build_system_prompt(req.creativity, req.response_mode)}]
    messages.extend(memory[-MAX_MEMORY_MESSAGES:])
    messages.append({"role": "user", "content": user_content})

    use_fallback = not API_KEY

    if not use_fallback:
        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": messages,
                    "temperature": 0.2 if req.creativity == "strict" else (0.6 if req.creativity == "balanced" else 0.9),
                },
                timeout=60,
            )
            response.raise_for_status()
        except (requests.exceptions.Timeout, requests.exceptions.HTTPError, requests.exceptions.RequestException):
            use_fallback = True

    if use_fallback:
        meals = _fallback_meals(cleaned_ingredients, req.creativity, req.response_mode)
    else:
        raw_data = response.json()
        try:
            content = raw_data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise HTTPException(status_code=502, detail="Unexpected AI response format.") from exc

        try:
            parsed = _extract_json_payload(content)
        except (json.JSONDecodeError, TypeError) as exc:
            raise HTTPException(status_code=502, detail="AI returned non-JSON recipe content.") from exc

        meals = _sanitize_meals(parsed, {name.lower() for name in cleaned_ingredients})

    SESSION_MEMORY[req.session_id] = [
        *memory[-(MAX_MEMORY_MESSAGES - 2):],
        {"role": "user", "content": user_content},
        {"role": "assistant", "content": json.dumps(meals)},
    ]

    return {"data": meals}

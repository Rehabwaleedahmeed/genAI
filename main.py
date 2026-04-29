import csv
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Literal, Optional
from urllib.parse import quote_plus
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
SESSION_SUMMARIES: Dict[str, str] = {}
MAX_MEMORY_MESSAGES = 6
CSV_LOG_PATH = Path(__file__).resolve().with_name("nutrition_agent_log.csv")


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


class AssistantRequestModel(BaseModel):
    meal_text: str = ""
    meal_description: str = ""
    location_query: str = ""
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


def _extract_meal_terms(*values: str) -> List[str]:
    seen = set()
    terms: List[str] = []
    for value in values:
        for item in _parse_ingredient_text(value):
            key = item.lower()
            if key not in seen:
                seen.add(key)
                terms.append(item)
    return terms


def _estimate_nutrition(terms: List[str]) -> dict:
    text = " ".join(terms).lower()
    calories = 250
    protein = 12
    carbs = 20
    fat = 10
    fiber = 4

    if re.search(r"chicken|turkey|fish|salmon|tuna|beef|tofu|eggs|lentil|beans|yogurt", text):
        calories += 180
        protein += 22
    if re.search(r"rice|pasta|bread|potato|oats|noodle|quinoa|wrap", text):
        calories += 160
        carbs += 34
    if re.search(r"avocado|olive oil|nuts|peanut|seed|cheese|butter", text):
        calories += 140
        fat += 12
    if re.search(r"broccoli|spinach|salad|lettuce|cucumber|carrot|pepper|tomato|vegetable", text):
        calories += 40
        fiber += 5
    if re.search(r"fruit|berry|apple|banana|orange", text):
        calories += 60
        carbs += 14
        fiber += 3

    return {
        "estimated_calories": int(calories),
        "protein_g": int(protein),
        "carbs_g": int(carbs),
        "fat_g": int(fat),
        "fiber_g": int(fiber),
    }


def _build_nutrition_prompt(creativity: str, response_mode: str, nearby_search: bool) -> str:
    creativity_map = {
        "strict": "Keep the tone conservative and practical.",
        "balanced": "Balance reliability and helpfulness.",
        "creative": "Offer a little more variety while staying realistic.",
    }
    detail_map = {
        "concise": "Keep the response short and structured.",
        "detailed": "Include a little more explanatory detail.",
    }

    search_note = (
        "The user asked for nearby healthy food options, so include a brief search-oriented suggestion."
        if nearby_search
        else "Do not invent nearby food locations unless the user asked for them."
    )

    return f"""
You are a Nutrition AI Assistant.
{creativity_map[creativity]}
{detail_map[response_mode]}

Return ONLY valid JSON with these keys:
- meal_analysis: string
- nutrition_summary: object with estimated_calories, protein_g, carbs_g, fat_g, fiber_g
- recommendations: array of 2 to 4 short strings
- search_query_hint: string

Rules:
- Do not give medical diagnoses or strict diet plans.
- Keep advice general and safety-focused.
- {search_note}
""".strip()


def _build_search_query(location_query: str, terms: List[str]) -> str:
    base_query = location_query.strip() or "near me"
    category = "healthy restaurants grocery stores organic food"
    meal_hint = " ".join(terms[:3]).strip()
    if meal_hint:
        return f"{category} {base_query} {meal_hint}".strip()
    return f"{category} {base_query}".strip()


def _search_nearby_food(location_query: str, terms: List[str]) -> List[dict]:
    query = location_query.strip()
    if not query:
        return []

    encoded_query = quote_plus(query)
    geocode_response = requests.get(
        f"https://nominatim.openstreetmap.org/search?q={encoded_query}&format=jsonv2&limit=1",
        headers={"User-Agent": "genAI-nutrition-agent/1.0"},
        timeout=20,
    )
    geocode_response.raise_for_status()
    geocode_data = geocode_response.json()
    if not geocode_data:
        return []

    lat = float(geocode_data[0]["lat"])
    lon = float(geocode_data[0]["lon"])
    search_tags = [
        ("amenity", "restaurant"),
        ("amenity", "cafe"),
        ("shop", "supermarket"),
        ("shop", "organic"),
        ("shop", "greengrocer"),
    ]

    overpass_query = "[out:json][timeout:25];(" + "".join(
        f'node(around:3000,{lat},{lon})["{key}"="{value}"];' for key, value in search_tags
    ) + ");out center 10;"

    response = requests.post(
        "https://overpass-api.de/api/interpreter",
        data={"data": overpass_query},
        headers={"User-Agent": "genAI-nutrition-agent/1.0"},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    results = []
    for element in data.get("elements", [])[:8]:
        tags = element.get("tags", {}) if isinstance(element, dict) else {}
        name = tags.get("name") or tags.get("brand") or "Nearby option"
        category = tags.get("amenity") or tags.get("shop") or "food"
        results.append(
            {
                "name": name,
                "category": category,
                "address": ", ".join(
                    part for part in [tags.get("addr:housenumber"), tags.get("addr:street"), tags.get("addr:city")] if part
                ),
            }
        )

    return results


def _append_csv_log(record: dict) -> str:
    CSV_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    file_exists = CSV_LOG_PATH.exists()
    with CSV_LOG_PATH.open("a", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "timestamp",
                "session_id",
                "meal_text",
                "meal_analysis",
                "calories",
                "recommendations",
                "location_query",
                "search_count",
            ],
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow(record)
    return str(CSV_LOG_PATH)


def _summarize_context(session_id: str, meal_analysis: str, search_count: int) -> str:
    summary = f"Meal analyzed with {search_count} nearby options" if search_count else "Meal analyzed with no nearby search"
    if meal_analysis:
        summary = f"{summary}. {meal_analysis[:220].strip()}"
    SESSION_SUMMARIES[session_id] = summary
    return summary


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


@app.post("/assistant")
def assistant(req: AssistantRequestModel):
    terms = _extract_meal_terms(req.meal_text, req.meal_description)
    if not terms and not req.image_url and not req.image_data_url:
        raise HTTPException(status_code=400, detail="Provide meal text, a meal description, or an image.")

    memory = SESSION_MEMORY.get(req.session_id, [])
    summary_context = SESSION_SUMMARIES.get(req.session_id, "")
    nearby_search = bool(req.location_query.strip())
    nutrition = _estimate_nutrition(terms)

    user_text = (
        "User request:\n"
        f"- Meal text: {req.meal_text.strip() or 'None'}\n"
        f"- Meal description: {req.meal_description.strip() or 'None'}\n"
        f"- Nearby food query: {req.location_query.strip() or 'None'}\n"
        f"- Existing session summary: {summary_context or 'None'}\n"
        "Task: analyze the meal, estimate nutrition, recommend safe improvements, and search nearby healthy options when requested."
    )

    user_content = [{"type": "text", "text": user_text}]
    if req.image_data_url:
        user_content.append({"type": "image_url", "image_url": {"url": req.image_data_url}})
    elif req.image_url:
        user_content.append({"type": "image_url", "image_url": {"url": req.image_url}})

    messages = [{"role": "system", "content": _build_nutrition_prompt(req.creativity, req.response_mode, nearby_search)}]
    if summary_context:
        messages.append({"role": "system", "content": f"Session summary: {summary_context}"})
    messages.extend(memory[-MAX_MEMORY_MESSAGES:])
    messages.append({"role": "user", "content": user_content})

    meal_analysis = ""
    recommendations = []
    nutrition_summary = nutrition

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
                    "temperature": 0.3 if req.creativity == "strict" else (0.6 if req.creativity == "balanced" else 0.85),
                },
                timeout=60,
            )
            response.raise_for_status()
            raw_data = response.json()
            content = raw_data["choices"][0]["message"]["content"]
            parsed = _extract_json_payload(content)
            meal_analysis = str(parsed.get("meal_analysis", "")).strip()
            nutrition_summary = parsed.get("nutrition_summary", nutrition)
            recommendations = [str(item).strip() for item in parsed.get("recommendations", []) if str(item).strip()]
        except (requests.exceptions.Timeout, requests.exceptions.HTTPError, requests.exceptions.RequestException, KeyError, IndexError, TypeError, json.JSONDecodeError):
            meal_analysis = ""
            recommendations = []

    if not meal_analysis:
        joined_terms = ", ".join(terms) if terms else "the provided meal"
        meal_analysis = f"This meal appears to center on {joined_terms}. It looks workable, but portion balance and vegetables would improve the overall nutrition profile."
        recommendations = [
            "Add a vegetable side or salad for extra fiber.",
            "Use water or an unsweetened drink to keep the meal lighter.",
            "Choose a protein source if the meal is mostly starch-based.",
        ]

    if nearby_search:
        recommendations.append("Compare nearby options for lower-sodium and higher-fiber choices.")

    nearby_results = []
    if nearby_search:
        try:
            nearby_results = _search_nearby_food(req.location_query, terms)
        except requests.exceptions.RequestException:
            nearby_results = []

    storage_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": req.session_id,
        "meal_text": req.meal_text.strip() or req.meal_description.strip(),
        "meal_analysis": meal_analysis,
        "calories": nutrition_summary.get("estimated_calories", nutrition["estimated_calories"]),
        "recommendations": " | ".join(recommendations[:4]),
        "location_query": req.location_query.strip(),
        "search_count": len(nearby_results),
    }
    csv_path = _append_csv_log(storage_record)
    context_summary = _summarize_context(req.session_id, meal_analysis, len(nearby_results))

    SESSION_MEMORY[req.session_id] = [
        *memory[-(MAX_MEMORY_MESSAGES - 2):],
        {"role": "user", "content": user_content},
        {
            "role": "assistant",
            "content": json.dumps(
                {
                    "meal_analysis": meal_analysis,
                    "nutrition_summary": nutrition_summary,
                    "recommendations": recommendations,
                    "search_results": nearby_results,
                    "csv_path": csv_path,
                    "session_summary": context_summary,
                }
            ),
        },
    ]

    return {
        "meal_analysis": meal_analysis,
        "nutrition_summary": nutrition_summary,
        "recommendations": recommendations,
        "search_results": nearby_results,
        "csv_storage": {
            "saved": True,
            "path": csv_path,
            "session_summary": context_summary,
        },
        "disclaimer": "This is not medical or dietary advice. Consult a qualified professional.",
    }

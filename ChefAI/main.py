import json
import os
import re
import requests
from pathlib import Path
from typing import Dict, List, Literal, Optional, Any, Set

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

def _load_env():
    env_path = Path(__file__).resolve().with_name(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

_load_env()
API_KEY = os.getenv("OPENROUTER_API_KEY", "")
SESSION_MEMORY: Dict[str, List[dict]] = {}
MAX_MEMORY_MESSAGES = 6

# --- Models ---
class Ingredient(BaseModel):
    name: str

class RequestModel(BaseModel):
    ingredients: List[Ingredient] = []
    ingredients_text: str = ""
    image_url: Optional[str] = None
    image_data_url: Optional[str] = None
    session_id: str = "default"
    creativity: Literal["strict", "balanced", "creative"] = "balanced"
    response_mode: Literal["concise", "detailed"] = "detailed"

# --- Utility Functions ---
def _process_ingredients(req: RequestModel) -> List[str]:
    """Combines structured and text ingredients into a unique list."""
    raw_list = [i.name.strip() for i in req.ingredients if i.name.strip()]
    raw_text = [p.strip() for p in re.split(r",|\n", req.ingredients_text) if p.strip()]
    
    seen: Set[str] = set()
    return [i for i in (raw_list + raw_text) if i.lower() not in seen and not seen.add(i.lower())]

def _extract_json_payload(text: str) -> Any:
    """Safely extracts JSON from markdown code blocks."""
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = match.group(1).strip() if match else text.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None

def _build_system_prompt(creativity: str, mode: str) -> str:
    creativity_settings = {
        "strict": "Stay practical and conservative. Prefer familiar recipes.",
        "balanced": "Balance reliability and creativity.",
        "creative": "Be inventive and chef-like while still realistic."
    }
    detail_settings = {
        "concise": "Keep steps compact (5-7 steps).",
        "detailed": "Give more cooking detail (7-10 steps)."
    }

    return (
        f"You are AI Chef Assistant. {creativity_settings[creativity]} {detail_settings[mode]} "
        "Return ONLY a valid JSON list of meals. Each meal must have: "
        "'meal', 'cooking_time', 'servings', 'ingredients' (list of {name, status}), and 'instructions' (list of strings)."
    ).strip()

def _fallback_meals(ingredients: List[str], creativity: str, response_mode: str) -> List[dict]:
    """Generates fallback meals when API is unavailable."""
    fallback_recipes = {
        "simple": [
            {
                "meal": "Simple Stir-Fry",
                "cooking_time": "15 mins",
                "servings": "2-3",
                "ingredients": [{"name": ing, "status": "available"} for ing in ingredients[:3]] + [
                    {"name": "Oil", "status": "available"},
                    {"name": "Salt and Pepper", "status": "available"}
                ],
                "instructions": [
                    "Step 1: Heat oil in a large pan over medium-high heat",
                    "Step 2: Add your ingredients and stir-fry for 5 minutes",
                    "Step 3: Season with salt and pepper to taste",
                    "Step 4: Serve hot"
                ]
            }
        ],
        "detailed": [
            {
                "meal": "Hearty Ingredient Bowl",
                "cooking_time": "25 mins",
                "servings": "2-4",
                "ingredients": [{"name": ing, "status": "available"} for ing in ingredients] + [
                    {"name": "Olive Oil", "status": "available"},
                    {"name": "Garlic", "status": "available"},
                    {"name": "Salt and Pepper", "status": "available"}
                ],
                "instructions": [
                    "Step 1: Prepare all your ingredients by washing and cutting as needed",
                    "Step 2: Heat 2 tablespoons of olive oil in a large pan",
                    "Step 3: Sauté minced garlic for 30 seconds until fragrant",
                    "Step 4: Add your prepared ingredients and cook for 12-15 minutes",
                    "Step 5: Stir occasionally to ensure even cooking",
                    "Step 6: Season with salt and pepper to your preference",
                    "Step 7: Plate and serve immediately while hot"
                ]
            }
        ]
    }
    
    recipes = fallback_recipes["detailed"] if response_mode == "detailed" else fallback_recipes["simple"]
    return recipes

# --- Core Logic ---
def _sanitize_meals(payload: Any, available_names: Set[str]) -> List[dict]:
    if not isinstance(payload, list):
        return []

    sanitized = []
    for meal in payload[:3]:
       
        ingredients = []
        for ing in meal.get("ingredients", []):
            name = str(ing.get("name", "")).strip()
            if not name: continue
            
            status = str(ing.get("status", "")).lower()
            is_avail = name.lower() in available_names or any(x in status for x in ["avail", "yes", "stock"])
            ingredients.append({"name": name, "status": "available" if is_avail else "not available"})

        # Normalize instructions
        steps = [f"Step {i+1}: {str(s).strip()}" for i, s in enumerate(meal.get("instructions", [])) if str(s).strip()]
        
        sanitized.append({
            "meal": meal.get("meal", "Untitled Meal"),
            "cooking_time": meal.get("cooking_time", "N/A"),
            "servings": meal.get("servings", "N/A"),
            "ingredients": ingredients,
            "instructions": steps
        })
    return sanitized

@app.post("/generate")
def generate(req: RequestModel):
    cleaned_ingredients = _process_ingredients(req)

    if not cleaned_ingredients and not (req.image_url or req.image_data_url):
        raise HTTPException(status_code=400, detail="Missing ingredients or image input.")

    # Context management
    memory = SESSION_MEMORY.get(req.session_id, [])
    user_msg_content = [{"type": "text", "text": f"Ingredients: {', '.join(cleaned_ingredients)}"}]
    
    img_url = req.image_data_url or req.image_url
    if img_url:
        user_msg_content.append({"type": "image_url", "image_url": {"url": img_url}})

    messages = [
        {"role": "system", "content": _build_system_prompt(req.creativity, req.response_mode)},
        *memory[-MAX_MEMORY_MESSAGES:],
        {"role": "user", "content": user_msg_content}
    ]

    meals = []
    if API_KEY:
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": messages,
                    "temperature": {"strict": 0.2, "balanced": 0.6, "creative": 0.9}[req.creativity]
                },
                timeout=60
            )
            resp.raise_for_status()
            raw_content = resp.json()["choices"][0]["message"]["content"]
            parsed = _extract_json_payload(raw_content)
            meals = _sanitize_meals(parsed, {i.lower() for i in cleaned_ingredients})
        except Exception:
            pass 

    if not meals:
        meals = _fallback_meals(cleaned_ingredients, req.creativity, req.response_mode)

    SESSION_MEMORY[req.session_id] = [
        *messages[1:], # Keep history minus current system prompt
        {"role": "assistant", "content": json.dumps(meals)}
    ]

    return {"data": meals}

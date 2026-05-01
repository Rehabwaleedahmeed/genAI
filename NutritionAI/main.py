import csv
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# --- CONFIGURATION & ENV ---
DATA_DIR = Path(__file__).resolve().with_name("nutrition_data")
DATA_DIR.mkdir(exist_ok=True)
CSV_PATH = DATA_DIR / "meals.csv"

def _load_env():
    env_path = Path(__file__).resolve().with_name(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

_load_env()

API_KEY = os.getenv("OPENROUTER_API_KEY", "")
MODEL_NAME = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
DISCLAIMER = "This is not medical or dietary advice. Consult a qualified professional."

# --- MODELS ---
class AnalyzeRequest(BaseModel):
    text: str = ""
    image_url: Optional[str] = None
    session_id: str = "default"

class AgentRequest(AnalyzeRequest):
    do_search: bool = False
    do_store: bool = False
    search_query: Optional[str] = None

class SearchRequest(BaseModel):
    query: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    limit: int = 5

class StoreRequest(BaseModel):
    session_id: str = "default"
    meal_text: str
    items: List[dict]
    total_calories: float
    summary: str = ""
    recommendations: List[str] = []

# --- STATE MANAGEMENT ---
SESSION_MEMORY: Dict[str, List[dict]] = {}
MAX_MEMORY = 10

def update_session(session_id: str, role: str, content: Any):
    SESSION_MEMORY.setdefault(session_id, [])
    SESSION_MEMORY[session_id].append({"role": role, "content": content})
    if len(SESSION_MEMORY[session_id]) > MAX_MEMORY:
        SESSION_MEMORY[session_id] = SESSION_MEMORY[session_id][-MAX_MEMORY:]

# --- SERVICES ---
class NutritionService:
    COMMON_CALORIES = {
        "banana": 105, "apple": 95, "egg": 78, "bread": 80, 
        "rice": 200, "chicken": 250, "salad": 150, "pizza": 285
    }

    @staticmethod
    def heuristic_estimate(text: str, image_url: Optional[str]) -> Dict[str, Any]:
        """Combines text tokens and image keywords for a basic estimate."""
        tokens = re.split(r"[,\n; ]", (text or "").lower())
        img_hints = (image_url or "").lower()
        
        items = []
        total = 0.0
        
        # Check tokens against dictionary
        for word in set(tokens + ([img_hints] if image_url else [])):
            if word in NutritionService.COMMON_CALORIES:
                cal = NutritionService.COMMON_CALORIES[word]
                items.append({"name": word, "est_calories": cal, "confidence": "medium"})
                total += cal
        
        if not items: # Fallback
            items.append({"name": "generic_meal", "est_calories": 400, "confidence": "low"})
            total = 400.0
            
        return {"meal_analysis": items, "nutrition_summary": {"total_calories": total}}

    @staticmethod
    def ai_analyze(text: str, image_url: Optional[str]) -> Optional[Dict[str, Any]]:
        if not API_KEY: return None
        
        prompt = (
            "Analyze nutrition. Return ONLY JSON with keys: meal_analysis (list of {name, est_calories, confidence}), "
            "nutrition_summary ({total_calories}), recommendations (list of strings)."
        )
        
        content = [{"type": "text", "text": text or "Analyze this meal"}]
        if image_url:
            content.append({"type": "image_url", "image_url": {"url": image_url}})

        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}"},
                json={
                    "model": MODEL_NAME,
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": content}
                    ]
                },
                timeout=30
            )
            r.raise_for_status()
            raw = r.json()['choices'][0]['message']['content']
            # Extraction logic
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            return json.loads(match.group()) if match else None
        except Exception:
            return None

class SearchService:
    @staticmethod
    def find_places(query: str, lat=None, lon=None, limit=5):
        params = {"q": query, "format": "jsonv2", "limit": limit}
        if lat and lon:
            params.update({"viewbox": f"{lon-0.05},{lat-0.05},{lon+0.05},{lat+0.05}", "bounded": 1})
        
        try:
            r = requests.get("https://nominatim.openstreetmap.org/search", 
                             params=params, headers={"User-Agent": "NutritionAgent/1.0"}, timeout=10)
            return [{"name": d.get("display_name"), "type": d.get("type")} for d in r.json()]
        except:
            return []

class StorageService:
    @staticmethod
    def log_meal(entry: Dict[str, Any]):
        file_exists = CSV_PATH.exists()
        with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "session_id", "meal_text", "total_calories", "recommendations"])
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_id": entry.get("session_id"),
                "meal_text": entry.get("meal_text"),
                "total_calories": entry.get("total_calories"),
                "recommendations": "|".join(entry.get("recommendations", []))
            })

# --- API APP ---
app = FastAPI(title="Nutrition AI Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.post("/analyze")
def analyze_endpoint(req: AnalyzeRequest):
    # Try AI first, then Heuristic
    result = NutritionService.ai_analyze(req.text, req.image_url)
    source = "ai"
    
    if not result:
        result = NutritionService.heuristic_estimate(req.text, req.image_url)
        result["recommendations"] = ["Consider a balanced plate of protein and fiber."]
        source = "heuristic"

    # Auto-trigger search if keywords exist
    search_results = None
    if any(k in req.text.lower() for k in ["near", "find", "restaurant"]):
        search_results = SearchService.find_places(req.text or "healthy food")

    response = {
        **result,
        "search_results": search_results,
        "source": source,
        "disclaimer": DISCLAIMER
    }
    
    update_session(req.session_id, "user", req.text)
    update_session(req.session_id, "assistant", response["nutrition_summary"])
    
    return response

@app.post("/agent")
def orchestrator_endpoint(req: AgentRequest):
    # 1. Analyze
    analysis = analyze_endpoint(AnalyzeRequest(text=req.text, image_url=req.image_url, session_id=req.session_id))
    
    # 2. Search
    search = None
    if req.do_search or analysis.get("search_results"):
        search = SearchService.find_places(req.search_query or req.text or "healthy food")
    
    # 3. Store
    if req.do_store:
        StorageService.log_meal({
            "session_id": req.session_id,
            "meal_text": req.text or "Image Analysis",
            "total_calories": analysis["nutrition_summary"]["total_calories"],
            "recommendations": analysis.get("recommendations", [])
        })

    return {
        "analysis": analysis,
        "search": search,
        "storage": "saved" if req.do_store else "skipped",
        "disclaimer": DISCLAIMER
    }

@app.post("/store")
def manual_store(req: StoreRequest):
    StorageService.log_meal(req.dict())
    return {"status": "success", "path": str(CSV_PATH)}
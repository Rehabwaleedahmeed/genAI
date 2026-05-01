import os
import json
import logging
import traceback
from datetime import datetime
from typing import Optional, Any, List, Dict
import pandas as pd
import openai
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv


load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

# --- Domain Models ---
class Message(BaseModel):
    role: str
    content: str
    tool_calls: Optional[List[Any]] = None

class ChatRequest(BaseModel):
    messages: List[Dict[str, Any]]
    user_id: str = "default"

class ChatResponse(BaseModel):
    message: str
    tool_used: Optional[str] = None
    data: Optional[Any] = None


class StoreService:
    def __init__(self):
        self.inventory_df = self._load_inventory()
        self.catalog_info = self._load_catalog()

    def _load_inventory(self) -> pd.DataFrame:
        path = os.path.join(SCRIPT_DIR, "inventory.csv")
        try:
            return pd.read_csv(path)
        except Exception as e:
            logger.error(f"Failed to load inventory: {e}")
            return pd.DataFrame(columns=['product_id', 'name', 'category', 'size', 'color', 'price', 'stock', 'description'])

    def _load_catalog(self) -> Dict:
        path = os.path.join(SCRIPT_DIR, "catalog.json")
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load catalog: {e}")
            return {"store_name": "StyleHub", "store_info": {"categories": []}}

    def search_inventory(self, query: str) -> str:
        query_lower = query.lower()
        df = self.inventory_df
        mask = (
            df['name'].str.lower().str.contains(query_lower, na=False) |
            df['category'].str.lower().str.contains(query_lower, na=False) |
            df['description'].str.lower().str.contains(query_lower, na=False)
        )
        results = df[mask].head(10)
        
        if results.empty:
            return json.dumps({"status": "no_results", "message": f"No items found for '{query}'"})
        
        items = results.to_dict(orient='records')
        # Clean numeric types for JSON serialization
        for item in items:
            item['price'] = f"${item['price']:.2f}"
            item['in_stock'] = item['stock'] > 0
            
        return json.dumps({"status": "success", "items": items})

    def get_info(self) -> str:
        return json.dumps({**self.catalog_info, "status": "success"})

class AIService:
    def __init__(self, store_service: StoreService):
        self.store = store_service
        self.client = openai.OpenAI(
            api_key=os.getenv("OPENROUTE_API_KEY"),
            base_url="https://openrouter.ai/api/v1"
        )
        self.system_prompt = self._get_system_prompt()
        self.tools = self._get_tool_definitions()

    def _get_system_prompt(self) -> str:
        return "You are StyleHub's intelligent fashion consultant. Help customers find items and give styling advice."

    def _get_tool_definitions(self) -> List[Dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_inventory",
                    "description": "Search store inventory for clothing items.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_store_info",
                    "description": "Get store policies and promotions.",
                    "parameters": {"type": "object", "properties": {}}
                }
            }
        ]

    def call_tool(self, name: str, args: Dict) -> str:
        if name == "search_inventory":
            return self.store.search_inventory(args.get("query", ""))
        if name == "get_store_info":
            return self.store.get_info()
        return json.dumps({"error": "Tool not found"})

app = FastAPI(title="StyleHub AI")
store_service = StoreService()
ai_service = AIService(store_service)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routes ---
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    messages = request.messages
    if not messages or messages[0].get("role") != "system":
        messages.insert(0, {"role": "system", "content": ai_service.system_prompt})

    try:
        response = ai_service.client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=ai_service.tools,
            tool_choice="auto"
        )

        last_tool_name = None
        last_tool_data = None

        for _ in range(5):  
            message = response.choices[0].message
            if not message.tool_calls:
                break
            messages.append(message)

            for tool_call in message.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                
                logger.info(f"Executing tool: {name} with args: {args}")
                result = ai_service.call_tool(name, args)
                
                last_tool_name = name
                last_tool_data = result

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": name,
                    "content": result
                })

            
            response = ai_service.client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages
            )

        return ChatResponse(
            message=response.choices[0].message.content,
            tool_used=last_tool_name,
            data=last_tool_data
        )

    except Exception as e:
        logger.error(f"Chat error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal assistant error")

@app.get("/health")
def health():
    return {"status": "online", "inventory_count": len(store_service.inventory_df)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
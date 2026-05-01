# NutritionAI

Multi-modal Nutrition AI assistant backend with dynamic tool orchestration.

## Features
- Meal analysis from text and optional image URL
- Optional OpenRouter-powered analysis (when `OPENROUTER_API_KEY` is set)
- Dynamic search tool for nearby healthy places
- CSV storage tool for structured meal logs
- Session memory trimming + summarization behavior

## Endpoints
- `POST /analyze`
- `POST /agent`
- `POST /search`
- `POST /store`

## OpenRouter Setup
Create `.env` in this folder:

```env
OPENROUTER_API_KEY=your_openrouter_key_here
OPENROUTER_MODEL=openai/gpt-4o-mini
```

If the key is missing or the request fails, the backend falls back to built-in heuristic estimation.

## Run
```bash
pip install fastapi uvicorn requests pydantic
cd /home/rehabwaleed/genAI/NutritionAI
uvicorn main:app --port 8001 --reload
```

## Quick Test
```bash
curl -X POST http://127.0.0.1:8001/agent \
  -H 'Content-Type: application/json' \
  -d '{"text":"grilled chicken, rice, salad. find nearby healthy restaurants","session_id":"demo-1","do_search":true,"do_store":true}'
```

This is not medical or dietary advice. Consult a qualified professional.

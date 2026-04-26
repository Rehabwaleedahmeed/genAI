# genAI

## Environment Setup

1. Create a `.env` file in the project root.
2. Add your OpenRouter key:

```bash
OPENROUTER_API_KEY=your_openrouter_key_here
```

3. Export it before starting backend:

```bash
export OPENROUTER_API_KEY="your_openrouter_key_here"
uvicorn main:app --reload
```

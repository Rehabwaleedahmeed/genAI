# genAI

## Multi-Modal Nutrition AI Agent Assignment

This project is being used as a nutrition assistant assignment. The agent should:

- Analyze text input and meal or food-image descriptions.
- Estimate nutrition values and generate structured meal summaries.
- Decide dynamically when to use tools for search and CSV storage.
- Support context trimming and summary memory for longer conversations.
- Provide safe, non-diagnostic guidance only.
- Include the disclaimer: "This is not medical or dietary advice. Consult a qualified professional."

## Required Capabilities

### Inputs

- Text input is required.
- Food image or meal description is optional but supported.

### Tools

- Search tool for healthy restaurants, grocery stores, and nutrition information.
- CSV storage tool for meals, calories, summaries, and goals.

### Expected Outputs

- Meal analysis.
- Nutrition summary.
- Recommendations.
- Search results.
- CSV storage.

### Constraints

- Do not provide medical diagnoses or strict diet plans.
- Always keep advice general and safety-focused.

## Current Project Setup

The current app provides a local multimodal meal-planning workflow with image and text input, plus session memory in the backend. The nutrition-agent requirements above are now documented in the project so the implementation can be extended toward the assignment brief.

Example flow: user enters a meal, the agent analyzes nutrition, the user asks for nearby healthy food, the agent searches, and the agent stores the structured result in CSV.

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

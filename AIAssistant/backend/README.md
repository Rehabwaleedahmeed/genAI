# Backend README

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables
```bash
export OPENAI_API_KEY="your-api-key-here"
```

### 3. Run the Server
```bash
python main.py
```

Server will be available at `http://localhost:8000`

## API Documentation

Once the server is running, view interactive API docs at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Files

- **main.py**: FastAPI application with the AI agent and all endpoints
- **inventory.csv**: Local database of clothing products
- **catalog.json**: Store information and resources
- **requirements.txt**: Python package dependencies

## Environment Variables

- `OPENAI_API_KEY`: Your OpenAI API key (required)

## Database Schema

### inventory.csv columns:
- product_id: Unique identifier
- name: Product name
- category: Product category (Tops, Bottoms, etc.)
- size: Size (S, M, L, XL, or number for shoes)
- color: Product color
- price: Product price
- stock: Available quantity
- description: Product description

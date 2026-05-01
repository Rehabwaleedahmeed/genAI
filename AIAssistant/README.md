# StyleHub AI Assistant - Clothes Store AI Agent

A full-stack AI-powered customer service agent for a clothes store with React frontend and Python FastAPI backend.

## Project Overview

**Scenario:** StyleHub is a premium online clothing store that uses an intelligent AI assistant to help customers find the perfect clothing items, get fashion advice, and learn about current promotions and policies.

### Key Features

1. **Local Inventory Database (inventory.csv)**
   - Comprehensive clothing inventory with 34+ products
   - Searchable by product name, category, size, color, price, and stock status
   - Real-time stock information

2. **Store Catalog Resource (catalog.json)**
   - Store information and mission
   - Current fashion trends for Spring-Summer 2026
   - Active promotions and discounts
   - Return policies and customer support details
   - Payment methods accepted

3. **AI Agent with Three Main Tools:**
   - **Search Local Inventory**: Query the database for specific clothing items
   - **Search Online Trends**: Get fashion advice and styling recommendations
   - **Get Store Info**: Access store policies, promotions, and support information

4. **Intelligent System Prompt**
   - Guides the agent to use tools strategically
   - Provides context-aware responses
   - Combines inventory data with fashion trends for better recommendations

## Project Structure

```
AIAssistant/
├── backend/
│   ├── main.py                  # FastAPI application with AI agent
│   ├── inventory.csv            # Local database of clothing items
│   ├── catalog.json             # Store information and resources
│   └── requirements.txt          # Python dependencies
└── ui/
    ├── package.json             # React dependencies
    ├── public/
    │   └── index.html           # HTML entry point
    └── src/
        ├── App.js               # Main React component
        ├── App.css              # Styling
        ├── index.js             # React DOM render
        └── index.css            # Global styles
```

## Installation & Setup

### Backend Setup

1. **Navigate to backend directory:**
   ```bash
   cd AIAssistant/backend
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set OpenAI API Key:**
   ```bash
   export OPENAI_API_KEY="your-openai-api-key"
   ```
   Or create a `.env` file:
   ```
   OPENAI_API_KEY=your-openai-api-key
   ```

5. **Run the backend server:**
   ```bash
   python main.py
   ```
   The server will start on `http://localhost:8000`

### Frontend Setup

1. **Navigate to UI directory:**
   ```bash
   cd AIAssistant/ui
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start the React application:**
   ```bash
   npm start
   ```
   The app will open on `http://localhost:3000`

## API Endpoints

### Chat Endpoint
- **POST** `/chat`
- Processes user messages and returns AI agent responses
- Request body:
  ```json
  {
    "messages": [
      {"role": "system", "content": "..."},
      {"role": "user", "content": "..."}
    ],
    "user_id": "web_user"
  }
  ```

### Inventory Endpoints
- **GET** `/inventory/categories` - Get all product categories
- **GET** `/inventory/stats` - Get inventory statistics
- **GET** `/health` - Health check

## How the AI Agent Works

### Example User Query: "Do you have black t-shirts in size M?"

1. **User Input** → Sent to the agent
2. **Agent Analysis** → Determines the best tool to use
3. **Tool Execution** → Calls `search_local_inventory` with query "black t-shirt size M"
4. **Database Search** → Searches inventory.csv for matching items
5. **Response Generation** → Combines search results with helpful fashion tips
6. **User Receives** → Formatted response with product details, prices, and availability

### Example User Query: "What's trending for summer?"

1. **User Input** → Sent to the agent
2. **Agent Analysis** → Determines fashion trends query is needed
3. **Tool Execution** → Calls `search_online_trends` with query "summer"
4. **Trend Database** → Returns summer fashion recommendations
5. **Response Generation** → Provides styling tips and current trends
6. **User Receives** → Fashion advice with specific item recommendations

## Agent System Prompt Highlights

The agent is configured with a sophisticated system prompt that:
- Identifies itself as a fashion consultant for StyleHub
- Knows when to use each tool based on the customer's needs
- Combines data from multiple sources for better recommendations
- Proactively suggests alternatives when items are out of stock
- Provides personalized fashion advice
- Maintains a helpful and professional tone

## Tools Description

### 1. search_local_inventory(query)
Searches the local CSV database for clothing items
- **Use case**: Customer asks about specific items, availability, or prices
- **Returns**: Product details including size, color, price, stock status
- **Example queries**: "black jeans", "summer dress size S", "running shoes"

### 2. search_online_trends(query)
Searches trend database for fashion recommendations
- **Use case**: Customer asks about styles, trends, or fashion advice
- **Returns**: Trending styles, color recommendations, budget information
- **Example queries**: "casual wear", "formal dress code", "winter fashion"

### 3. get_store_info()
Retrieves comprehensive store information
- **Use case**: Customer asks about policies, promotions, or support
- **Returns**: Promotions, return policy, customer support info, store mission
- **Example queries**: "What's your return policy?", "Current promotions?"

## Sample Test Queries

Try these queries to test the agent:

1. "Do you have black t-shirts in size M?"
2. "What are the trending summer styles?"
3. "Show me athletic shorts available"
4. "Tell me about your current promotions"
5. "I need a formal outfit for a wedding"
6. "What's your return policy?"
7. "Do you have winter coats in stock?"
8. "What shoes do you recommend for running?"

## Technologies Used

### Backend
- **FastAPI**: Modern web framework for building APIs
- **Python**: Programming language
- **Pandas**: Data manipulation and CSV reading
- **OpenAI API**: GPT-4 for AI agent capabilities
- **Uvicorn**: ASGI server

### Frontend
- **React**: UI library
- **Axios**: HTTP client for API calls
- **React Icons**: Icon library
- **CSS3**: Modern styling with gradients and animations

## Customization

### Adding More Products
Edit `backend/inventory.csv` and add new rows following the same format.

### Modifying Store Info
Update `backend/catalog.json` with new store information, promotions, or trends.

### Changing the System Prompt
Edit the `SYSTEM_PROMPT` variable in `backend/main.py` to adjust agent behavior.

### Updating Trends
Modify the `trend_database` dictionary in the `search_online_trends()` function to add new fashion trends.

## Troubleshooting

### Backend Server Won't Start
- Check if port 8000 is in use: `lsof -i :8000`
- Ensure OPENAI_API_KEY is set correctly
- Verify all dependencies are installed

### React App Won't Connect
- Ensure backend is running on localhost:8000
- Check browser console for CORS errors
- Verify the proxy setting in `ui/package.json`

### No Response from Agent
- Check OpenAI API key validity
- Verify API key has sufficient credits
- Check backend logs for errors

## Future Enhancements

- Integration with real payment systems
- User authentication and order history
- Image uploads for style matching
- Real-time inventory synchronization
- Multi-language support
- Advanced analytics dashboard
- Integration with shipping providers

## License

This project is open source and available for educational purposes.

## Support

For issues or questions, please refer to the documentation or contact support@stylehub.com
